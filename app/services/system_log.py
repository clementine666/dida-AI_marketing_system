"""系统运行日志（SQLite）。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text

from app.db import get_engine


def ensure_schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS system_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT DEFAULT 'info',
                    module TEXT,
                    action TEXT,
                    message TEXT,
                    detail_json TEXT,
                    operator TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at DESC)"
            )
        )


def log(
    message: str,
    *,
    level: str = "info",
    module: str | None = None,
    action: str | None = None,
    detail: dict | None = None,
    operator: str | None = None,
) -> int:
    ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO system_logs (level, module, action, message, detail_json, operator, created_at)
                VALUES (:level, :module, :action, :message, :detail, :operator, :created_at)
                """
            ),
            {
                "level": level,
                "module": module,
                "action": action,
                "message": message,
                "detail": json.dumps(detail, ensure_ascii=False) if detail else None,
                "operator": operator,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return int(row.lastrowid or 0)


def list_logs(limit: int = 100, module: str | None = None, level: str | None = None) -> list[dict]:
    ensure_schema()
    engine = get_engine()
    clauses = ["1=1"]
    params: dict = {"limit": min(max(limit, 1), 500)}
    if module:
        clauses.append("module = :module")
        params["module"] = module
    if level:
        clauses.append("level = :level")
        params["level"] = level
    sql = f"""
        SELECT log_id, level, module, action, message, detail_json, operator, created_at
        FROM system_logs
        WHERE {' AND '.join(clauses)}
        ORDER BY log_id DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    out = []
    for r in rows:
        item = dict(r)
        if item.get("detail_json"):
            try:
                item["detail"] = json.loads(item["detail_json"])
            except json.JSONDecodeError:
                item["detail"] = item["detail_json"]
        out.append(item)
    return out
