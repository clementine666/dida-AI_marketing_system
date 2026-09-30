"""5-Agent 编排器：状态机 + 人工闸门。"""

from __future__ import annotations

from app.models.lifecycle import LifecycleStatus
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.v2.agent1_planner import PlannerService
from app.services.v2.agent2_resource import ResourceConfiguratorService
from app.services.v2.agent3_monitor import MonitorService
from app.services.v2.agent4_analyst import AnalystService
from app.services.v2.agent5_archive import ArchiveService


class MarketingOrchestrator:
    """LangGraph 可替换的轻量编排实现。"""

    def __init__(self):
        self.planner = PlannerService()
        self.resource = ResourceConfiguratorService()
        self.monitor = MonitorService()
        self.analyst = AnalystService()
        self.archive = ArchiveService()
        self.lifecycle = ActivityLifecycleService()

    # --- Agent1 ---
    def step_build_calendar(self, months: int = 3) -> dict:
        return self.planner.build_marketing_workspace(prep_lead_months=months)

    def step_build_prep_queue(self, prep_lead_months: int = 3) -> dict:
        ws = self.planner.build_marketing_workspace(prep_lead_months=prep_lead_months)
        return ws["prep_queue"]

    def gate_confirm_send_to_agent2(self, campaign_id: str, operator: str = "marketer") -> dict:
        return self.planner.confirm_send_to_agent2(campaign_id, operator)

    # --- Agent2 ---
    def step_configure_resources(self, campaign_id: str) -> dict:
        return self.resource.configure_resources(campaign_id)

    def gate_complete_todos_and_test(self, campaign_id: str, operator: str = "marketer") -> dict:
        submit = self.resource.submit_for_testing(campaign_id, operator)
        if not submit.get("ok"):
            return submit
        return self.resource.approve_testing(campaign_id, operator)

    def gate_mark_todo_done(self, todo_id: int, operator: str = "marketer") -> dict:
        return self.resource.complete_todo(todo_id, operator)

    # --- Agent3 ---
    def step_preview_monitor(self, campaign_id: str) -> dict:
        return self.monitor.preview_dashboard(campaign_id)

    def gate_confirm_monitoring(self, campaign_id: str, operator: str = "marketer") -> dict:
        return self.monitor.confirm_monitoring(campaign_id, operator)

    # --- Agent4 ---
    def step_generate_review(self, campaign_id: str) -> dict:
        return self.analyst.generate_review_report(campaign_id)

    def gate_confirm_review(self, campaign_id: str, operator: str = "marketer") -> dict:
        return self.analyst.confirm_review(campaign_id, operator)

    # --- Agent5 ---
    def step_archive(self, campaign_id: str, operator: str = "marketer") -> dict:
        return self.archive.archive_activity(campaign_id, operator)

    def run_full_pipeline(self, campaign_id: str, operator: str = "marketer", auto_gates: bool = True) -> dict:
        """端到端演示（含自动通过人工闸门）。"""
        results = {"campaign_id": campaign_id, "steps": []}

        if auto_gates:
            send = self.gate_confirm_send_to_agent2(campaign_id, operator)
            results["steps"].append({"gate_send_agent2": send})
            if not send.get("ok"):
                return results

        cfg = self.step_configure_resources(campaign_id)
        results["steps"].append({"agent2_configure": cfg})

        if auto_gates:
            confirm_res = self.resource.confirm_resources(campaign_id, operator)
            results["steps"].append({"gate_confirm_resources": confirm_res})
            if not confirm_res.get("ok"):
                return results
            todos = self.resource.list_todos(campaign_id)
            for t in todos:
                self.gate_mark_todo_done(t["todo_id"], operator)
            test = self.gate_complete_todos_and_test(campaign_id, operator)
            results["steps"].append({"gate_testing": test})

        preview = self.step_preview_monitor(campaign_id)
        results["steps"].append({"agent3_preview": preview})

        if auto_gates:
            mon = self.gate_confirm_monitoring(campaign_id, operator)
            results["steps"].append({"gate_monitoring": mon})

        review = self.step_generate_review(campaign_id)
        results["steps"].append({"agent4_review": review})

        if auto_gates:
            confirm = self.gate_confirm_review(campaign_id, operator)
            results["steps"].append({"gate_review": confirm})
            arch = self.step_archive(campaign_id, operator)
            results["steps"].append({"agent5_archive": arch})

        results["final_status"] = self.lifecycle.get_status(campaign_id)
        return results
