"""Agent 4 - 效果复盘 数据服务。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.services.agent3_service import Agent3Service


class Agent4Service:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.agent3 = Agent3Service(self.engine)

    def get_campaign_orders(self, campaign_id: str) -> list[dict]:
        sql = """
        SELECT * FROM fact_orders WHERE campaign_id = :cid
        ORDER BY create_time DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": campaign_id})
            return [dict(r._mapping) for r in rows]

    def get_funnel_during_campaign(self, campaign_id: str) -> list[dict]:
        sql = """
        SELECT f.step_code, f.step_name, f.step_no, COUNT(*) AS cnt
        FROM fact_funnel f
        JOIN dim_campaign c ON c.campaign_id = :cid
        WHERE f.country_name LIKE '%' || c.target_dest || '%'
        GROUP BY f.step_code, f.step_name, f.step_no
        ORDER BY f.step_no
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": campaign_id})
            return [dict(r._mapping) for r in rows]

    def compare_target_vs_actual(self, campaign_id: str) -> dict:
        camp_sql = "SELECT target_metrics, budget FROM dim_campaign WHERE campaign_id = :cid"
        with self.engine.connect() as conn:
            camp = conn.execute(text(camp_sql), {"cid": campaign_id}).fetchone()
            if not camp:
                return {}
            targets = {}
            if camp.target_metrics:
                try:
                    targets = json.loads(camp.target_metrics)
                except (json.JSONDecodeError, TypeError):
                    targets = {"raw_target_metrics": camp.target_metrics}
            budget = camp.budget

        actual = self.agent3.compute_campaign_metrics(campaign_id)
        comparison = {}
        for key, target_val in targets.items():
            actual_val = actual.get(key) or actual.get(f"{key.replace('_rate', '_count')}")
            if actual_val is None:
                for k, v in actual.items():
                    if key in k or k in key:
                        actual_val = v
                        break
            achievement = (actual_val / target_val) if target_val and actual_val is not None else None
            comparison[key] = {
                "target": target_val,
                "actual": actual_val,
                "achievement_rate": round(achievement, 4) if achievement is not None else None,
            }
        return {"targets": targets, "actual": actual, "comparison": comparison, "budget": budget}

    def generate_review_report(self, campaign_id: str) -> dict:
        """输出复盘报告（Agent 4 核心输出）。"""
        with self.engine.connect() as conn:
            camp = conn.execute(
                text("SELECT * FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": campaign_id},
            ).fetchone()
            if not camp:
                return {"error": f"Campaign {campaign_id} not found"}
            camp = dict(camp._mapping)

        comparison = self.compare_target_vs_actual(campaign_id)
        orders = self.get_campaign_orders(campaign_id)
        funnel = self.get_funnel_during_campaign(campaign_id)
        actual = comparison.get("actual", {})
        budget = comparison.get("budget") or 0
        ttv = actual.get("total_ttv") or 0
        gp = actual.get("total_gp") or 0
        roi = ((gp - budget) / budget) if budget else None

        # 关键发现
        findings = []
        comp = comparison.get("comparison", {})
        for metric, data in comp.items():
            rate = data.get("achievement_rate")
            if rate is not None:
                if rate >= 1.0:
                    findings.append(f"{metric} 达成率 {rate:.0%}，超额完成")
                elif rate >= 0.7:
                    findings.append(f"{metric} 达成率 {rate:.0%}，基本达标")
                else:
                    findings.append(f"{metric} 达成率 {rate:.0%}，未达预期，需优化")

        if not findings:
            findings.append("活动数据尚在积累中，建议持续监控")

        optimizations = []
        if actual.get("banner_ctr", 1) < 0.03:
            optimizations.append("Banner CTR偏低，建议优化素材和投放位置")
        if actual.get("conversion_rate_overall", 1) < 0.01:
            optimizations.append("整体转化率偏低，建议优化选品和价格策略")
        if len(orders) < 50:
            optimizations.append("订单量不足，建议扩大目标客户群或加强推送")
        if not optimizations:
            optimizations.append("保持当前策略，下阶段可尝试A/B测试优化")

        return {
            "report_title": f"{camp['campaign_name']} - 活动复盘报告",
            "generated_at": datetime.now().isoformat(),
            "background": {
                "campaign_name": camp["campaign_name"],
                "campaign_type": camp.get("campaign_type"),
                "period": f"{camp.get('start_date')} ~ {camp.get('end_date')}",
                "target_dest": camp.get("target_dest"),
                "budget": budget,
            },
            "objectives": comparison.get("targets"),
            "actual_results": actual,
            "target_vs_actual": comparison.get("comparison"),
            "roi": {
                "total_ttv": ttv,
                "total_gp": gp,
                "budget": budget,
                "roi_rate": round(roi, 4) if roi is not None else None,
                "order_count": len(orders),
            },
            "funnel_analysis": funnel,
            "key_findings": findings,
            "optimization_suggestions": optimizations,
            "orders_sample": orders[:10],
        }
