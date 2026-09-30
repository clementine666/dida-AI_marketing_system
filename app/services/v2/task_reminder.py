"""任务催办：三个时间点（中点 / 截止前 1 天 / 当天）→ 飞书群机器人。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import text

from app.db import get_engine
from app.integrations.feishu_bot import FeishuBotClient, format_remind_message

DEMO_CAMPAIGN_ID = "CAMP_CAL_08_新加坡F1赛事酒店预订"
DEMO_ACTIVITY = "新加坡F1赛事酒店预订"

TODO_COLUMNS = [
    ("deadline", "DATE"),
    ("lane", "TEXT"),
    ("remind_1_done", "INTEGER DEFAULT 0"),
    ("remind_2_done", "INTEGER DEFAULT 0"),
    ("remind_3_done", "INTEGER DEFAULT 0"),
    ("last_remind_at", "TIMESTAMP"),
]


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return bool(row)


def ensure_schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        if not _table_exists(conn, "fact_activity_todos"):
            return
        for col, typedef in TODO_COLUMNS:
            if not _column_exists(conn, "fact_activity_todos", col):
                conn.execute(text(f"ALTER TABLE fact_activity_todos ADD COLUMN {col} {typedef}"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS fact_remind_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    todo_id INTEGER,
                    remind_level INTEGER,
                    message_content TEXT,
                    send_result TEXT,
                    is_success INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    _seed_demo_tasks()


def _seed_demo_tasks() -> None:
    engine = get_engine()
    today = date.today()
    with engine.begin() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM fact_activity_todos
                WHERE campaign_id = :cid AND deadline IS NOT NULL
                """
            ),
            {"cid": DEMO_CAMPAIGN_ID},
        ).scalar()
        if n:
            return
        rows = [
            (DEMO_CAMPAIGN_ID, "resource", "DC/TPS 确认参与意愿", "萧蓉", today - timedelta(days=7), today, "resource", 2),
            (DEMO_CAMPAIGN_ID, "plan", "活动主题与玩法确认", "JIM", today - timedelta(days=14), today + timedelta(days=14), "plan", 3),
            (DEMO_CAMPAIGN_ID, "material", "官网 Banner", "梓淮", today - timedelta(days=5), today + timedelta(days=1), "material", 4),
        ]
        for cid, ttype, title, owner, created, deadline, lane, sort in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO fact_activity_todos
                    (campaign_id, todo_type, title, owner, created_at, deadline, lane, sort_order, is_done)
                    VALUES (:cid, :tt, :title, :owner, :created, :deadline, :lane, :sort, 0)
                    """
                ),
                {
                    "cid": cid,
                    "tt": ttype,
                    "title": title,
                    "owner": owner,
                    "created": created.isoformat(),
                    "deadline": deadline.isoformat(),
                    "lane": lane,
                    "sort": sort,
                },
            )


def _parse_d(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    text_val = str(val)[:10]
    try:
        return date.fromisoformat(text_val)
    except ValueError:
        return None


def _levels_due(created: date, deadline: date, today: date, flags: dict[int, int]) -> list[int]:
    span = max((deadline - created).days, 0)
    mid = created + timedelta(days=span // 2)
    mapping = {1: mid, 2: deadline - timedelta(days=1), 3: deadline}
    due = [lv for lv, d in mapping.items() if d == today and not flags.get(lv)]
    if not due:
        return []
    return [max(due)]


def _log(conn, todo_id, level, content, result: dict) -> None:
    conn.execute(
        text(
            """
            INSERT INTO fact_remind_logs (todo_id, remind_level, message_content, send_result, is_success)
            VALUES (:tid, :lv, :msg, :res, :ok)
            """
        ),
        {
            "tid": todo_id,
            "lv": level,
            "msg": content,
            "res": str(result)[:1000],
            "ok": 1 if result.get("ok") else 0,
        },
    )


def reminder_status() -> dict:
    ensure_schema()
    bot = FeishuBotClient()
    engine = get_engine()
    pending = 0
    last = None
    with engine.connect() as conn:
        if _table_exists(conn, "fact_activity_todos") and _column_exists(conn, "fact_activity_todos", "deadline"):
            pending = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM fact_activity_todos
                    WHERE COALESCE(is_done, 0) = 0 AND deadline IS NOT NULL
                    """
                )
            ).scalar() or 0
        if _table_exists(conn, "fact_remind_logs"):
            row = conn.execute(
                text("SELECT created_at, is_success, remind_level FROM fact_remind_logs ORDER BY log_id DESC LIMIT 1")
            ).fetchone()
            if row:
                last = {"at": str(row[0]), "ok": bool(row[1]), "level": row[2]}
    return {
        "webhook_configured": bot.is_configured(),
        "keyword": bot.keyword,
        "pending_tasks": pending,
        "schedule": "每天 09:00（服务器本地时区）",
        "last_send": last,
    }


def send_test_message(activity_name: str | None = None) -> dict:
    ensure_schema()
    bot = FeishuBotClient()
    msg = format_remind_message(
        level=1,
        activity_name=activity_name or DEMO_ACTIVITY,
        task_name="DC/TPS 确认参与意愿",
        assignee="萧蓉",
        deadline=date.today().isoformat(),
        days_left=3,
    )
    msg = msg.replace("📅 还剩3天", "📅 系统连通测试，群内可忽略")
    result = bot.send_text(msg)
    engine = get_engine()
    with engine.begin() as conn:
        if _table_exists(conn, "fact_remind_logs"):
            _log(conn, None, 0, msg, result)
    return {**result, "preview": msg}


def run_due_reminders(today: date | None = None) -> dict:
    ensure_schema()
    bot = FeishuBotClient()
    if not bot.is_configured():
        return {"ok": False, "error": "未配置飞书催办 Webhook", "sent": 0}
    today = today or date.today()
    engine = get_engine()
    sent: list[dict] = []
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT t.todo_id, t.campaign_id, t.title, t.owner, t.created_at, t.deadline,
                       t.remind_1_done, t.remind_2_done, t.remind_3_done, t.is_done,
                       c.campaign_name
                FROM fact_activity_todos t
                LEFT JOIN dim_campaign c ON c.campaign_id = t.campaign_id
                WHERE COALESCE(t.is_done, 0) = 0 AND t.deadline IS NOT NULL
                """
            )
        ).mappings().all()
        for row in rows:
            created = _parse_d(row["created_at"]) or today
            deadline = _parse_d(row["deadline"])
            if not deadline:
                continue
            flags = {
                1: int(row["remind_1_done"] or 0),
                2: int(row["remind_2_done"] or 0),
                3: int(row["remind_3_done"] or 0),
            }
            levels = _levels_due(created, deadline, today, flags)
            if not levels:
                continue
            level = levels[0]
            activity = row["campaign_name"] or DEMO_ACTIVITY
            days_left = (deadline - today).days
            msg = format_remind_message(
                level=level,
                activity_name=activity,
                task_name=row["title"],
                assignee=row["owner"] or "—",
                deadline=deadline.isoformat(),
                days_left=days_left,
            )
            result = bot.send_text(msg)
            _log(conn, row["todo_id"], level, msg, result)
            if result.get("ok"):
                col = {1: "remind_1_done", 2: "remind_2_done", 3: "remind_3_done"}[level]
                conn.execute(
                    text(
                        f"UPDATE fact_activity_todos SET {col} = 1, last_remind_at = CURRENT_TIMESTAMP WHERE todo_id = :id"
                    ),
                    {"id": row["todo_id"]},
                )
                sent.append({"todo_id": row["todo_id"], "title": row["title"], "level": level})
    return {
        "ok": True,
        "today": today.isoformat(),
        "sent": len(sent),
        "items": sent,
        "message": f"已发送 {len(sent)} 条催办到飞书群" if sent else "今天没有到期催办",
    }
