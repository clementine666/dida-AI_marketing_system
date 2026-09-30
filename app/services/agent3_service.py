"""Agent 3 - 方案策划+监控 数据服务。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine


class Agent3Service:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def get_campaigns(self, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM dim_campaign WHERE (:st IS NULL OR status = :st)"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"st": status})
            return [dict(r._mapping) for r in rows]

    def get_campaign_metrics(self, campaign_id: str) -> list[dict]:
        sql = """
        SELECT * FROM fact_campaign_metrics
        WHERE campaign_id = :cid ORDER BY metric_date DESC, metric_hour DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": campaign_id})
            return [dict(r._mapping) for r in rows]

    def get_alert_rules(self, campaign_id: str) -> list[dict]:
        sql = "SELECT * FROM dim_alert_rules WHERE campaign_id = :cid AND is_active = 1"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": campaign_id})
            return [dict(r._mapping) for r in rows]

    def get_monitor_data(self, campaign_id: str, limit: int = 50) -> list[dict]:
        sql = """
        SELECT * FROM fact_monitor WHERE campaign_id = :cid
        ORDER BY monitor_time DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": campaign_id, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def compute_campaign_metrics(self, campaign_id: str) -> dict:
        """从 fact_events 聚合活动效果指标。"""
        camp_sql = "SELECT * FROM dim_campaign WHERE campaign_id = :cid"
        with self.engine.connect() as conn:
            camp = conn.execute(text(camp_sql), {"cid": campaign_id}).fetchone()
            if not camp:
                return {"error": f"Campaign {campaign_id} not found"}
            camp = dict(camp._mapping)
            slide_id = camp.get("slide_id")

            metrics_sql = """
            SELECT
                SUM(CASE WHEN event_type = 'primary_banner_expose' AND slide_id = :sid THEN 1 ELSE 0 END) AS banner_expose,
                SUM(CASE WHEN event_type = 'primary_banner_click' AND slide_id = :sid THEN 1 ELSE 0 END) AS banner_click,
                SUM(CASE WHEN event_type = 'hotel_detail_rp_expose' THEN 1 ELSE 0 END) AS rp_expose,
                SUM(CASE WHEN event_type = 'hotel_detail_rp_click' THEN 1 ELSE 0 END) AS rp_click,
                SUM(CASE WHEN event_type = 'preorder_result_return' THEN 1 ELSE 0 END) AS preorder,
                COUNT(DISTINCT client_id) AS unique_clients
            FROM fact_events WHERE slide_id = :sid OR country_name LIKE '%' || :dest || '%'
            """
            m = conn.execute(
                text(metrics_sql),
                {"sid": slide_id, "dest": camp.get("target_dest", "")},
            ).fetchone()
            m = dict(m._mapping)

            order_sql = """
            SELECT COUNT(*) AS orders, SUM(price_cny) AS ttv, SUM(combined_revenue_cny) AS gp
            FROM fact_orders WHERE campaign_id = :cid
            """
            o = conn.execute(text(order_sql), {"cid": campaign_id}).fetchone()
            o = dict(o._mapping) if o else {"orders": 0, "ttv": 0, "gp": 0}

        banner_ctr = (m["banner_click"] / m["banner_expose"]) if m["banner_expose"] else 0
        rp_ctr = (m["rp_click"] / m["rp_expose"]) if m["rp_expose"] else 0

        return {
            "campaign_id": campaign_id,
            "banner_expose_count": m["banner_expose"] or 0,
            "banner_click_count": m["banner_click"] or 0,
            "banner_ctr": round(banner_ctr, 4),
            "rp_expose_count": m["rp_expose"] or 0,
            "rp_click_count": m["rp_click"] or 0,
            "rp_ctr": round(rp_ctr, 4),
            "preorder_count": m["preorder"] or 0,
            "order_count": o["orders"] or 0,
            "total_ttv": o["ttv"] or 0,
            "total_gp": o["gp"] or 0,
            "unique_clients": m["unique_clients"] or 0,
        }

    def run_monitoring(self, campaign_id: str) -> list[dict]:
        """执行监控并写入 fact_monitor，检查告警规则。"""
        metrics = self.compute_campaign_metrics(campaign_id)
        rules = self.get_alert_rules(campaign_id)

        camp_sql = "SELECT target_metrics FROM dim_campaign WHERE campaign_id = :cid"
        with self.engine.connect() as conn:
            row = conn.execute(text(camp_sql), {"cid": campaign_id}).fetchone()
            targets = {}
            if row and row.target_metrics:
                try:
                    targets = json.loads(row.target_metrics)
                except (json.JSONDecodeError, TypeError):
                    targets = {"raw_target_metrics": row.target_metrics}

        alerts = []
        monitor_rows = []
        now = datetime.now().isoformat()

        for metric_name, value in metrics.items():
            if not isinstance(value, (int, float)):
                continue
            target = targets.get(metric_name)
            achievement = (value / target) if target else None

            alert_triggered = False
            alert_level = "绿"
            alert_message = None

            for rule in rules:
                if rule["metric_name"] != metric_name:
                    continue
                threshold = rule["threshold_value"]
                cond = rule["condition_type"]
                triggered = (
                    (cond == "低于" and value < threshold)
                    or (cond == "高于" and value > threshold)
                    or (cond == "等于" and value == threshold)
                )
                if triggered:
                    alert_triggered = True
                    alert_level = rule["alert_level"]
                    alert_message = f"{metric_name} {cond} 阈值 {threshold}，当前值 {value}"

            monitor_rows.append({
                "campaign_id": campaign_id,
                "monitor_time": now,
                "metric_name": metric_name,
                "metric_value": value,
                "target_value": target,
                "achievement_rate": round(achievement, 4) if achievement else None,
                "alert_triggered": alert_triggered,
                "alert_level": alert_level,
                "alert_message": alert_message,
            })
            if alert_triggered:
                alerts.append(monitor_rows[-1])

        insert_sql = """
        INSERT INTO fact_monitor
        (campaign_id, monitor_time, metric_name, metric_value, target_value,
         achievement_rate, alert_triggered, alert_level, alert_message)
        VALUES (:campaign_id, :monitor_time, :metric_name, :metric_value, :target_value,
                :achievement_rate, :alert_triggered, :alert_level, :alert_message)
        """
        with self.engine.begin() as conn:
            for row in monitor_rows:
                conn.execute(text(insert_sql), row)

        return alerts

    def create_campaign_plan(
        self, campaign_id: str, demand_report: dict, resource_match: dict
    ) -> dict:
        """整合 Agent 1+2 输出，生成策划方案。"""
        campaigns = self.get_campaigns()
        camp = next((c for c in campaigns if c["campaign_id"] == campaign_id), None)
        if not camp:
            return {"error": "Campaign not found"}

        metrics = self.compute_campaign_metrics(campaign_id)
        rules = self.get_alert_rules(campaign_id)

        return {
            "campaign_id": campaign_id,
            "campaign_name": camp["campaign_name"],
            "target_audience": {
                "client_groups": camp.get("target_client_groups"),
                "client_count": demand_report.get("client_count"),
                "profiles": demand_report.get("target_clients", [])[:10],
            },
            "product_selection": resource_match.get("matched_hotels", []),
            "push_strategy": {
                "channels": ["首页Banner", "热门酒店小助手", "邮件推送"],
                "timing": "赛事前45天开始预热，赛前2周加大投放",
                "promotions": resource_match.get("recommended_promotions", []),
            },
            "target_metrics": json.loads(camp["target_metrics"]) if camp.get("target_metrics") else {},
            "current_metrics": metrics,
            "monitoring_dashboard": {
                "metrics_tracked": list(metrics.keys()),
                "alert_rules": rules,
                "monitor_url": f"/api/agent3/monitor/{campaign_id}",
            },
            "status": camp.get("status"),
        }
