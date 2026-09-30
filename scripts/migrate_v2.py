"""数据库 v2 迁移脚本。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db import get_engine, init_database

DIM_CAMPAIGN_COLUMNS = [
    ("lifecycle_status", "TEXT DEFAULT 'draft'"),
    ("feishu_record_id", "TEXT"),
    ("activity_id", "TEXT"),
    ("plan_summary", "TEXT"),
    ("demand_analysis", "TEXT"),
    ("solution_analysis", "TEXT"),
    ("execution_steps", "TEXT"),
    ("target_audience", "TEXT"),
    ("key_metrics_spec", "TEXT"),
    ("delivery_mode", "TEXT"),
    ("resource_plan_json", "TEXT"),
    ("updated_at", "TIMESTAMP"),
    ("plan_source", "TEXT DEFAULT 'human_calendar'"),
    ("prep_phase", "TEXT"),
    ("merged_from_suggestion_id", "INTEGER"),
    ("plan_structured_json", "TEXT"),
    ("plan_review_confirmed_at", "TIMESTAMP"),
    ("plan_review_confirmed_by", "TEXT"),
    ("promotion_month", "TEXT"),
    ("adoption_status", "TEXT DEFAULT 'proposal'"),
]

FACT_AI_SUGGESTION_COLUMNS = [
    ("plan_draft_json", "TEXT"),
]

FACT_TODO_COLUMNS = [
    ("deadline", "DATE"),
    ("lane", "TEXT"),
    ("remind_1_done", "INTEGER DEFAULT 0"),
    ("remind_2_done", "INTEGER DEFAULT 0"),
    ("remind_3_done", "INTEGER DEFAULT 0"),
    ("last_remind_at", "TIMESTAMP"),
]

CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS fact_industry_intel (
        intel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_title TEXT NOT NULL,
        report_type TEXT,
        source_channel TEXT,
        collect_frequency TEXT,
        report_date DATE,
        destination_tags TEXT,
        summary TEXT,
        full_content TEXT,
        activity_suggestions TEXT,
        feature_suggestions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_activity_todos (
        todo_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        todo_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        owner TEXT,
        is_done BOOLEAN DEFAULT 0,
        done_at TIMESTAMP,
        sort_order INTEGER DEFAULT 0,
        config_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_activity_snapshot (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        snapshot_version INTEGER DEFAULT 1,
        lifecycle_status TEXT,
        payload_json TEXT NOT NULL,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_activity_archive (
        archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT UNIQUE NOT NULL,
        activity_id TEXT,
        activity_name TEXT NOT NULL,
        activity_type TEXT,
        destination TEXT,
        target_audience TEXT,
        lifecycle_summary TEXT,
        goal_achievement TEXT,
        problems TEXT,
        conclusions TEXT,
        reusable_points TEXT,
        avoid_points TEXT,
        full_report_json TEXT,
        success_label TEXT,
        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_lifecycle_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        triggered_by TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_ai_suggestions (
        suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
        suggestion_key TEXT UNIQUE,
        campaign_name TEXT NOT NULL,
        target_dest TEXT,
        promotion_month_hint TEXT,
        rationale TEXT,
        demand_analysis TEXT,
        solution_analysis TEXT,
        intel_id INTEGER,
        intel_report_title TEXT,
        status TEXT DEFAULT 'pending',
        similar_calendar_id TEXT,
        similar_calendar_name TEXT,
        merged_campaign_id TEXT,
        reviewed_by TEXT,
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (intel_id) REFERENCES fact_industry_intel(intel_id)
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_campaign_lifecycle ON dim_campaign(lifecycle_status)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_feishu ON dim_campaign(feishu_record_id)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_activity ON dim_campaign(activity_id)",
    "CREATE INDEX IF NOT EXISTS idx_todos_campaign ON fact_activity_todos(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_snapshot_campaign ON fact_activity_snapshot(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_archive_dest ON dim_activity_archive(destination)",
    "CREATE INDEX IF NOT EXISTS idx_archive_type ON dim_activity_archive(activity_type)",
    "CREATE INDEX IF NOT EXISTS idx_suggestions_status ON fact_ai_suggestions(status)",
    "CREATE INDEX IF NOT EXISTS idx_campaign_source ON dim_campaign(plan_source)",
]


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def migrate_v2():
    engine = get_engine()
    init_database(engine)

    with engine.begin() as conn:
        for stmt in CREATE_STATEMENTS:
            conn.execute(text(stmt))
        if _table_exists(conn, "dim_campaign"):
            for col, typedef in DIM_CAMPAIGN_COLUMNS:
                if not _column_exists(conn, "dim_campaign", col):
                    conn.execute(text(f"ALTER TABLE dim_campaign ADD COLUMN {col} {typedef}"))
        if _table_exists(conn, "fact_ai_suggestions"):
            for col, typedef in FACT_AI_SUGGESTION_COLUMNS:
                if not _column_exists(conn, "fact_ai_suggestions", col):
                    conn.execute(text(f"ALTER TABLE fact_ai_suggestions ADD COLUMN {col} {typedef}"))
        if _table_exists(conn, "fact_activity_todos"):
            for col, typedef in FACT_TODO_COLUMNS:
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
        for stmt in INDEX_STATEMENTS:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
        if _table_exists(conn, "dim_campaign") and _column_exists(conn, "dim_campaign", "adoption_status"):
            conn.execute(
                text("""
                UPDATE dim_campaign
                SET adoption_status = 'adopted'
                WHERE (adoption_status IS NULL OR adoption_status = 'proposal')
                  AND plan_review_confirmed_at IS NOT NULL
                """)
            )
            conn.execute(
                text("""
                UPDATE dim_campaign
                SET adoption_status = 'proposal'
                WHERE adoption_status IS NULL
                """)
            )

    print("Migration v2 completed.")


if __name__ == "__main__":
    migrate_v2()
