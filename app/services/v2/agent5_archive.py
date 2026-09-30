"""Agent5 - 活动归档师（v2）。"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.models.lifecycle import LifecycleStatus
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.snapshot_service import SnapshotService
from app.services.v2.agent4_analyst import AnalystService


class ArchiveService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.lifecycle = ActivityLifecycleService(self.engine)
        self.snapshot = SnapshotService(self.engine)
        self.analyst = AnalystService(self.engine)

    def archive_activity(self, campaign_id: str, operator: str = "marketer") -> dict:
        from app.models.campaign_plan_schema import build_full_structured_plan
        from app.services.v2.agent1_planner import PlannerService

        chain = self.snapshot.get_full_chain(campaign_id)
        planner = PlannerService(self.engine)
        plan_row = planner.get_activity_plan(campaign_id)
        if not plan_row:
            return {"ok": False, "error": "Campaign not found"}
        structured = build_full_structured_plan(plan_row)
        human = ((structured.get("archive") or {}).get("human_conclusion") or "").strip()
        if not human:
            return {"ok": False, "error": "请先在主文档⑬填写人工结论，再归档"}

        camp = plan_row
        report_snap = chain.get("snapshots", {}).get("agent4")
        if not report_snap:
            report_snap = self.analyst.generate_review_report(campaign_id)

        diagnosis = structured.get("diagnosis") or {}
        roi = report_snap.get("roi", {})
        success = (roi.get("order_count") or 0) >= 50 or (roi.get("roi_rate") or 0) > 0
        archive = {
            "campaign_id": campaign_id,
            "activity_id": camp.get("activity_id"),
            "activity_name": camp.get("campaign_name"),
            "activity_type": camp.get("campaign_type"),
            "destination": camp.get("target_dest"),
            "target_audience": camp.get("target_audience"),
            "lifecycle_summary": camp.get("lifecycle_status"),
            "goal_achievement": json.dumps(report_snap.get("target_vs_actual"), ensure_ascii=False, default=str),
            "problems": json.dumps(diagnosis.get("root_causes") or report_snap.get("key_findings"), ensure_ascii=False),
            "conclusions": human,
            "reusable_points": (structured.get("archive") or {}).get("experience") or diagnosis.get("one_line_verdict") or "待补充",
            "avoid_points": (structured.get("archive") or {}).get("pitfalls") or "",
            "full_report_json": json.dumps(
                {"structured": structured, "review": report_snap, "diagnosis": diagnosis},
                ensure_ascii=False,
                default=str,
            ),
            "success_label": "成功" if success else "待优化",
        }

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT OR REPLACE INTO dim_activity_archive
                (campaign_id, activity_id, activity_name, activity_type, destination, target_audience,
                 lifecycle_summary, goal_achievement, problems, conclusions, reusable_points, avoid_points,
                 full_report_json, success_label)
                VALUES (:campaign_id,:activity_id,:activity_name,:activity_type,:destination,:target_audience,
                        :lifecycle_summary,:goal_achievement,:problems,:conclusions,:reusable_points,:avoid_points,
                        :full_report_json,:success_label)
                """),
                archive,
            )

        self.snapshot.save(campaign_id, "agent5", archive, LifecycleStatus.ARCHIVED.value, operator)
        self.lifecycle.transition(campaign_id, LifecycleStatus.ARCHIVED.value, operator, "活动完结归档")
        return {"ok": True, "archive": archive}

    def search_similar(self, destination: str | None = None, activity_type: str | None = None, limit: int = 10) -> list[dict]:
        sql = """
        SELECT * FROM dim_activity_archive
        WHERE (:dest IS NULL OR destination LIKE :dest_like)
          AND (:type IS NULL OR activity_type = :type)
        ORDER BY archived_at DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                {
                    "dest": destination,
                    "dest_like": f"%{destination}%" if destination else None,
                    "type": activity_type,
                    "limit": limit,
                },
            )
            return [dict(r._mapping) for r in rows]

    def get_archive(self, campaign_id: str) -> dict | None:
        sql = "SELECT * FROM dim_activity_archive WHERE campaign_id = :cid"
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"cid": campaign_id}).fetchone()
            return dict(row._mapping) if row else None
