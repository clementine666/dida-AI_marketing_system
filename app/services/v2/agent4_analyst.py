"""Agent4 - 活动分析师（v2）。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.integrations.feishu_bitable import FeishuBitableClient
from app.models.lifecycle import LifecycleStatus
from app.services.agent4_service import Agent4Service
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.snapshot_service import SnapshotService


class AnalystService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.legacy = Agent4Service(self.engine)
        self.lifecycle = ActivityLifecycleService(self.engine)
        self.snapshot = SnapshotService(self.engine)
        self.feishu = FeishuBitableClient()

    def generate_review_report(self, campaign_id: str) -> dict:
        chain = self.snapshot.get_full_chain(campaign_id)
        base_report = self.legacy.generate_review_report(campaign_id)

        with self.engine.connect() as conn:
            camp = conn.execute(
                text("SELECT * FROM dim_campaign WHERE campaign_id = :cid"), {"cid": campaign_id}
            ).fetchone()
        camp = dict(camp._mapping) if camp else {}

        report = {
            **base_report,
            "meta": {
                "activity_id": camp.get("activity_id"),
                "feishu_record_id": camp.get("feishu_record_id"),
                "lifecycle_status": camp.get("lifecycle_status"),
                "generated_at": datetime.now().isoformat(),
            },
            "agent1_plan": chain.get("snapshots", {}).get("agent1"),
            "agent2_resource": chain.get("snapshots", {}).get("agent2"),
            "agent3_monitor": chain.get("snapshots", {}).get("agent3"),
            "sections": self._build_prd_sections(camp, base_report, chain),
        }
        self.snapshot.save(campaign_id, "agent4", report, LifecycleStatus.REVIEW.value, "agent4")
        self.lifecycle.transition(campaign_id, LifecycleStatus.REVIEW.value, "agent4", "复盘报告生成")
        return report

    def _build_prd_sections(self, camp: dict, base: dict, chain: dict) -> dict:
        return {
            "1_meta": {"name": camp.get("campaign_name"), "activity_id": camp.get("activity_id")},
            "2_decision_summary": base.get("key_findings", []),
            "3_background": base.get("background"),
            "4_goals_vs_actual": base.get("target_vs_actual"),
            "5_process_analysis": base.get("funnel_analysis"),
            "6_attribution": chain.get("snapshots", {}),
            "7_decisions": base.get("optimization_suggestions", []),
            "8_appendix": base.get("orders_sample"),
        }

    def writeback_feishu(self, campaign_id: str, report: dict | None = None) -> dict:
        if report is None:
            report = self.generate_review_report(campaign_id)
        with self.engine.connect() as conn:
            camp = conn.execute(
                text("SELECT feishu_record_id FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": campaign_id},
            ).fetchone()
        if not camp or not camp.feishu_record_id:
            return {"ok": False, "error": "No feishu_record_id"}
        conclusion = "\n".join([
            "【类型】活动",
            f"【结果】{'成功可复制' if report.get('roi', {}).get('order_count', 0) >= 50 else '需调整后再做'}",
            f"【结论】{'; '.join(report.get('key_findings', [])[:2])}",
            f"【机会建议】{'; '.join(report.get('optimization_suggestions', [])[:2])}",
        ])
        url = f"local://reports/{campaign_id}.json"
        return self.feishu.update_review_fields(camp.feishu_record_id, url, conclusion)

    def confirm_review(self, campaign_id: str, operator: str = "marketer") -> dict:
        report = self.generate_review_report(campaign_id)
        self.writeback_feishu(campaign_id, report)
        return {"ok": True, "campaign_id": campaign_id, "ready_for_archive": True, "report_title": report.get("report_title")}
