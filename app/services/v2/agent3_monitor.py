"""Agent3 - 活动监控师（v2）。"""

from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.models.lifecycle import LifecycleStatus
from app.services.agent3_service import Agent3Service
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.snapshot_service import SnapshotService
from app.services.v2.agent2_resource import ResourceConfiguratorService


class MonitorService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.legacy = Agent3Service(self.engine)
        self.lifecycle = ActivityLifecycleService(self.engine)
        self.snapshot = SnapshotService(self.engine)
        self.resource = ResourceConfiguratorService(self.engine)

    def get_monitor_config_from_todos(self, campaign_id: str) -> dict:
        todos = self.resource.list_todos(campaign_id)
        metric_todo = next((t for t in todos if t.get("todo_type") == "monitor_metric"), None)
        cfg = {}
        if metric_todo and metric_todo.get("config_json"):
            cfg = json.loads(metric_todo["config_json"])
        with self.engine.connect() as conn:
            camp = conn.execute(
                text("SELECT target_metrics, key_metrics_spec FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": campaign_id},
            ).fetchone()
        return {
            "target_metrics_text": camp.target_metrics if camp else cfg.get("target_metrics"),
            "key_metrics_spec": camp.key_metrics_spec if camp else cfg.get("key_metrics_spec"),
            "parsed_metrics": self._parse_metrics_spec(camp.key_metrics_spec if camp else cfg.get("key_metrics_spec")),
        }

    def _parse_metrics_spec(self, spec: str | None) -> list[dict]:
        if not spec:
            return [
                {"name": "banner_ctr", "target": 0.05, "formula": "banner_click / banner_expose"},
                {"name": "order_count", "target": 100, "formula": "count(orders)"},
            ]
        metrics = []
        for line in str(spec).split("\n"):
            m = re.search(r"CTR[≥>=]*\s*([\d.]+)%?", line, re.I)
            if m:
                metrics.append({"name": "banner_ctr", "target": float(m.group(1)) / 100, "formula": line.strip()})
            m2 = re.search(r"转化率[≥>=]*\s*([\d.]+)%?", line)
            if m2:
                metrics.append({"name": "conversion_rate_overall", "target": float(m2.group(1)) / 100, "formula": line.strip()})
        return metrics or [{"name": "banner_ctr", "target": 0.05, "formula": spec}]

    def preview_dashboard(self, campaign_id: str) -> dict:
        config = self.get_monitor_config_from_todos(campaign_id)
        current = self.legacy.compute_campaign_metrics(campaign_id)
        rules = self.legacy.get_alert_rules(campaign_id)
        return {
            "campaign_id": campaign_id,
            "monitor_config": config,
            "current_metrics": current,
            "alert_rules": rules,
            "dashboard_format": "conversion_funnel + kpi_cards",
        }

    def confirm_monitoring(self, campaign_id: str, operator: str = "marketer") -> dict:
        preview = self.preview_dashboard(campaign_id)
        self.snapshot.save(campaign_id, "agent3", preview, LifecycleStatus.MONITORING.value, operator)
        status = self.lifecycle.get_status(campaign_id)
        if status == LifecycleStatus.SCHEDULED.value:
            self.lifecycle.transition(campaign_id, LifecycleStatus.LIVE.value, operator)
        if self.lifecycle.get_status(campaign_id) in (LifecycleStatus.LIVE.value, LifecycleStatus.SCHEDULED.value):
            self.lifecycle.transition(campaign_id, LifecycleStatus.MONITORING.value, operator, "监控看板确认")
        alerts = self.legacy.run_monitoring(campaign_id)
        return {"ok": True, "preview": preview, "alerts": alerts}

    def run_scheduled_launch_check(self) -> list[dict]:
        """检查 scheduled 活动是否到达上线时间。"""
        sql = """
        SELECT campaign_id, campaign_name, start_date FROM dim_campaign
        WHERE lifecycle_status = 'scheduled' AND date(start_date) <= date('now')
        """
        launched = []
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        for r in rows:
            result = self.lifecycle.transition(r.campaign_id, LifecycleStatus.LIVE.value, "scheduler")
            if result.get("ok"):
                self.lifecycle.transition(r.campaign_id, LifecycleStatus.MONITORING.value, "scheduler")
                launched.append({"campaign_id": r.campaign_id, "name": r.campaign_name})
        return launched

    def get_monitor_history(self, campaign_id: str, limit: int = 50) -> list[dict]:
        return self.legacy.get_monitor_data(campaign_id, limit)
