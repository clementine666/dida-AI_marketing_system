"""使用者问题反馈 · 工单服务（提交 → 后台查因 → 修复结案）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import text

from app.db import get_engine
from app.services.system_log import list_logs, log

STATUS_OPEN = "open"
STATUS_INVESTIGATING = "investigating"
STATUS_RESOLVED = "resolved"
STATUS_WONT_FIX = "wont_fix"

STATUSES = [STATUS_OPEN, STATUS_INVESTIGATING, STATUS_RESOLVED, STATUS_WONT_FIX]


def ensure_schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS fact_user_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_no TEXT UNIQUE NOT NULL,
                    reporter TEXT NOT NULL,
                    module TEXT,
                    page_view TEXT,
                    tab_name TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    expected_behavior TEXT,
                    severity TEXT DEFAULT 'normal',
                    status TEXT DEFAULT 'open',
                    context_json TEXT,
                    admin_notes TEXT,
                    root_cause TEXT,
                    resolution TEXT,
                    related_log_hint TEXT,
                    resolved_by TEXT,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_feedback_status ON fact_user_feedback(status, created_at DESC)"
            )
        )


def _ticket_no(feedback_id: int) -> str:
    return f"FB-{datetime.now():%Y%m%d}-{feedback_id:04d}"


def create_feedback(
    *,
    reporter: str,
    title: str,
    description: str = "",
    expected_behavior: str = "",
    module: str | None = None,
    page_view: str | None = None,
    tab_name: str | None = None,
    severity: str = "normal",
    context: dict | None = None,
) -> dict:
    ensure_schema()
    engine = get_engine()
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO fact_user_feedback
                (ticket_no, reporter, module, page_view, tab_name, title, description,
                 expected_behavior, severity, status, context_json, created_at, updated_at)
                VALUES ('pending', :reporter, :module, :page_view, :tab, :title, :desc,
                        :expected, :severity, :status, :ctx, :now, :now)
                """
            ),
            {
                "reporter": reporter.strip()[:100],
                "module": (module or "")[:80] or None,
                "page_view": (page_view or "")[:80] or None,
                "tab": (tab_name or "")[:80] or None,
                "title": title.strip()[:200],
                "desc": (description or "")[:4000],
                "expected": (expected_behavior or "")[:2000],
                "severity": severity if severity in ("low", "normal", "high", "urgent") else "normal",
                "status": STATUS_OPEN,
                "ctx": json.dumps(context or {}, ensure_ascii=False),
                "now": now,
            },
        )
        fid = int(row.lastrowid or 0)
        ticket = _ticket_no(fid)
        conn.execute(
            text("UPDATE fact_user_feedback SET ticket_no = :tno WHERE feedback_id = :id"),
            {"tno": ticket, "id": fid},
        )

    log(
        f"用户反馈工单 {ticket}: {title[:80]}",
        module=module or "feedback",
        action="feedback_create",
        level="warn" if severity in ("high", "urgent") else "info",
        operator=reporter,
        detail={"feedback_id": fid, "ticket_no": ticket, "page_view": page_view, "tab": tab_name},
    )
    return get_feedback(fid)


def _row_to_dict(row) -> dict:
    item = dict(row)
    if item.get("context_json"):
        try:
            item["context"] = json.loads(item["context_json"])
        except json.JSONDecodeError:
            item["context"] = {}
    else:
        item["context"] = {}
    return item


def get_feedback(feedback_id: int) -> dict | None:
    ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM fact_user_feedback WHERE feedback_id = :id"),
            {"id": feedback_id},
        ).mappings().first()
    return _row_to_dict(row) if row else None


def list_feedback(
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    ensure_schema()
    engine = get_engine()
    clauses = ["1=1"]
    params: dict = {"limit": min(max(limit, 1), 200)}
    if status and status in STATUSES:
        clauses.append("status = :status")
        params["status"] = status
    sql = f"""
        SELECT * FROM fact_user_feedback
        WHERE {' AND '.join(clauses)}
        ORDER BY
          CASE status WHEN 'open' THEN 0 WHEN 'investigating' THEN 1 ELSE 2 END,
          feedback_id DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_dict(r) for r in rows]


def _related_logs(item: dict, window_minutes: int = 30) -> list[dict]:
    """按反馈时间与模块，自动关联前后窗口内的 system_logs。"""
    created = item.get("created_at")
    if not created:
        return []
    try:
        t0 = datetime.fromisoformat(str(created).replace("Z", ""))
    except ValueError:
        return []
    module = item.get("module")
    logs = list_logs(limit=200, module=module if module and module != "feedback" else None)
    out = []
    for lg in logs:
        ts = lg.get("created_at")
        if not ts:
            continue
        try:
            lt = datetime.fromisoformat(str(ts).replace("Z", ""))
        except ValueError:
            continue
        if abs((lt - t0).total_seconds()) <= window_minutes * 60:
            out.append(lg)
    return out[:40]


def get_feedback_detail(feedback_id: int) -> dict | None:
    item = get_feedback(feedback_id)
    if not item:
        return None
    item["related_logs"] = _related_logs(item)
    item["log_count"] = len(item["related_logs"])
    return item


def update_feedback(
    feedback_id: int,
    *,
    status: str | None = None,
    admin_notes: str | None = None,
    root_cause: str | None = None,
    resolution: str | None = None,
    related_log_hint: str | None = None,
    operator: str = "admin",
) -> dict | None:
    ensure_schema()
    existing = get_feedback(feedback_id)
    if not existing:
        return None

    fields = []
    params: dict = {"id": feedback_id, "now": datetime.now().isoformat(timespec="seconds")}
    if status and status in STATUSES:
        fields.append("status = :status")
        params["status"] = status
        if status in (STATUS_RESOLVED, STATUS_WONT_FIX):
            fields.append("resolved_by = :resolved_by")
            fields.append("resolved_at = :now")
            params["resolved_by"] = operator
    if admin_notes is not None:
        fields.append("admin_notes = :admin_notes")
        params["admin_notes"] = admin_notes[:4000]
    if root_cause is not None:
        fields.append("root_cause = :root_cause")
        params["root_cause"] = root_cause[:4000]
    if resolution is not None:
        fields.append("resolution = :resolution")
        params["resolution"] = resolution[:4000]
    if related_log_hint is not None:
        fields.append("related_log_hint = :hint")
        params["hint"] = related_log_hint[:2000]

    if not fields:
        return existing

    fields.append("updated_at = :now")
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE fact_user_feedback SET {', '.join(fields)} WHERE feedback_id = :id"),
            params,
        )

    log(
        f"处理反馈工单 {existing.get('ticket_no')} → {status or '更新备注'}",
        module="feedback",
        action="feedback_update",
        operator=operator,
        detail={"feedback_id": feedback_id, "status": status},
    )
    return get_feedback_detail(feedback_id)


def summary_counts() -> dict:
    ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt FROM fact_user_feedback GROUP BY status
                """
            )
        ).mappings().all()
    counts = {r["status"]: r["cnt"] for r in rows}
    open_cnt = counts.get(STATUS_OPEN, 0) + counts.get(STATUS_INVESTIGATING, 0)
    return {
        "open": counts.get(STATUS_OPEN, 0),
        "investigating": counts.get(STATUS_INVESTIGATING, 0),
        "resolved": counts.get(STATUS_RESOLVED, 0),
        "wont_fix": counts.get(STATUS_WONT_FIX, 0),
        "pending_total": open_cnt,
        "total": sum(counts.values()),
    }
