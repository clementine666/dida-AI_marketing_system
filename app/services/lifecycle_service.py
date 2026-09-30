"""活动生命周期状态流转服务。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.models.lifecycle import LifecycleStatus, can_transition


class ActivityLifecycleService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def get_status(self, campaign_id: str) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT lifecycle_status FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": campaign_id},
            ).fetchone()
            return row.lifecycle_status if row else None

    def transition(
        self,
        campaign_id: str,
        to_status: str,
        triggered_by: str = "system",
        note: str | None = None,
    ) -> dict:
        current = self.get_status(campaign_id)
        if current is None:
            return {"ok": False, "error": f"Campaign {campaign_id} not found"}
        if not can_transition(current, to_status):
            return {
                "ok": False,
                "error": f"Invalid transition: {current} -> {to_status}",
                "current": current,
            }
        now = datetime.now().isoformat()
        legacy_map = {
            LifecycleStatus.DRAFT.value: "筹备",
            LifecycleStatus.PLAN_REVIEW.value: "筹备",
            LifecycleStatus.MONITORING.value: "进行中",
            LifecycleStatus.LIVE.value: "进行中",
            LifecycleStatus.ARCHIVED.value: "已结束",
            LifecycleStatus.REVIEW.value: "已结束",
        }
        legacy_status = legacy_map.get(to_status, "筹备")
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign SET lifecycle_status = :st, status = :legacy, updated_at = :now
                WHERE campaign_id = :cid
                """),
                {"st": to_status, "legacy": legacy_status, "now": now, "cid": campaign_id},
            )
            conn.execute(
                text("""
                INSERT INTO fact_lifecycle_log (campaign_id, from_status, to_status, triggered_by, note)
                VALUES (:cid, :frm, :to, :by, :note)
                """),
                {"cid": campaign_id, "frm": current, "to": to_status, "by": triggered_by, "note": note},
            )
        return {"ok": True, "campaign_id": campaign_id, "from": current, "to": to_status}

    def list_by_status(self, status: str | None = None, limit: int = 100) -> list[dict]:
        sql = """
        SELECT campaign_id, campaign_name, lifecycle_status, start_date, end_date,
               target_dest, campaign_type, feishu_record_id, activity_id
        FROM dim_campaign
        WHERE (:st IS NULL OR lifecycle_status = :st)
        ORDER BY start_date ASC
        LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"st": status, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_calendar(self, months_ahead: int = 3) -> list[dict]:
        sql = """
        SELECT campaign_id, campaign_name, campaign_type, lifecycle_status,
               start_date, end_date, target_dest, plan_summary, target_audience,
               activity_id, feishu_record_id
        FROM dim_campaign
        WHERE start_date IS NOT NULL
          AND date(start_date) <= date('now', :offset)
          AND date(COALESCE(end_date, start_date)) >= date('now')
        ORDER BY start_date
        """
        offset = f"+{months_ahead} months"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"offset": offset})
            return [dict(r._mapping) for r in rows]
