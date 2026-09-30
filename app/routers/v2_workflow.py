"""5-Agent v2 API 路由。"""

from fastapi import APIRouter, Body, File, Form, Query, UploadFile

from agents.orchestrator import MarketingOrchestrator
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.v2.agent1_planner import PlannerService
from app.services.v2.agent2_resource import ResourceConfiguratorService
from app.services.v2.agent3_monitor import MonitorService
from app.services.v2.agent4_analyst import AnalystService
from app.services.v2.agent5_archive import ArchiveService
from app.services.v2.manual_calendar_skill import ManualCalendarSkillService
from app.integrations.feishu_marketing_calendar import FeishuMarketingCalendarClient

router = APIRouter(prefix="/v2", tags=["5-Agent-v2"])
orchestrator = MarketingOrchestrator()
planner = PlannerService()
resource = ResourceConfiguratorService()
monitor = MonitorService()
analyst = AnalystService()
archive = ArchiveService()
lifecycle = ActivityLifecycleService()
manual_calendar = ManualCalendarSkillService()


@router.get("/health")
def health_check():
    return {
        "ok": True,
        "features": [
            "plan-structured",
            "plan-review-v2",
            "query-profile-handoff",
            "resource-confirm-override",
            "intel-hub",
            "llm-suggestions",
            "campaign-doc-v3",
            "campaign-diagnosis",
            "resource-prep-analysis",
            "manual-calendar-skill",
        ],
    }


@router.get("/workspace")
def get_workspace(prep_lead_months: int = Query(3, ge=1, le=6)):
    """Agent1 营销工作台：全年日历 + 准备队列 + AI建议。"""
    return planner.build_marketing_workspace(prep_lead_months=prep_lead_months)


@router.get("/agent1/annual-calendar/export")
def export_annual_calendar():
    """下载全年营销日历 CSV（标准+创意字段并集）。"""
    from fastapi.responses import Response
    from app.services.v2.agent1_calendar_export import export_annual_calendar_csv

    filename, content = export_annual_calendar_csv(planner)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/agent1/manual-calendar/generate")
def generate_manual_calendar(body: dict = Body(default={})):
    """标准活动规划：MCP 取数 → AI/Skill 分析 → 营销日历初版。"""
    mode = str(body.get("mode") or "auto").lower()
    kwargs = {
        "top_units_per_continent": int(body.get("top_units_per_continent", 5)),
        "top_months_per_unit": int(body.get("top_months_per_unit", 3)),
        "min_month_share": float(body.get("min_month_share", 0.06)),
    }
    try:
        if mode == "legacy":
            return manual_calendar.generate(**kwargs, data_source=str(body.get("data_source", "local_xlsx")))
        from app.services.v2.manual_calendar_pipeline import run_manual_calendar_pipeline

        return run_manual_calendar_pipeline(manual_calendar, mode=mode, **kwargs)
    except FileNotFoundError as e:
        from app.services.v2.manual_calendar_pipeline import run_manual_calendar_pipeline

        return run_manual_calendar_pipeline(manual_calendar, mode="simulate", **kwargs)
    except Exception as e:
        return {"ok": False, "error": f"生成失败: {e}"}


@router.post("/agent1/manual-calendar/submit-pool")
def submit_manual_calendar_pool(body: dict = Body(...)):
    """将标准活动规划初版送入评审池（fact_ai_suggestions · manual_data）。"""
    rows = body.get("draft_rows") or []
    if not rows:
        return {"ok": False, "error": "draft_rows 为空"}
    return manual_calendar.submit_to_review_pool(rows, operator=body.get("operator", "marketer"))


@router.post("/agent1/manual-calendar/upload-pool")
async def upload_manual_calendar_pool(
    file: UploadFile = File(...),
    operator: str = Form("marketer"),
):
    """上传线下做好的标准活动初版 Excel/CSV → 解析 A–M 列 → 送入初版评审池。"""
    content = await file.read()
    name = file.filename or "upload.xlsx"
    try:
        return manual_calendar.upload_and_submit_pool(content, name, operator=operator)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"上传解析失败: {e}"}


@router.get("/calendar")
def get_calendar(months: int = Query(3, ge=1, le=12), include_all: bool = Query(False)):
    return planner.build_three_month_calendar(months, include_all=include_all)


@router.get("/suggestions")
def list_suggestions(status: str | None = None):
    return planner.list_ai_suggestions(status)


@router.post("/suggestions/{suggestion_id}/review")
def review_suggestion(suggestion_id: int, body: dict = Body(...)):
    """
    body: {
      "action": "approve"|"reject"|"merge",
      "merge_with_campaign_id": "...",
      "promotion_month": "11月",
      "structured_plan": { ... }
    }
    """
    return planner.review_ai_suggestion(
        suggestion_id,
        action=body.get("action", "approve"),
        operator=body.get("operator", "marketer"),
        merge_with_campaign_id=body.get("merge_with_campaign_id"),
        promotion_month=body.get("promotion_month"),
        structured_plan=body.get("structured_plan"),
    )


@router.get("/suggestions/{suggestion_id}/plan-structured")
def get_suggestion_structured_plan(suggestion_id: int):
    return planner.get_suggestion_review(suggestion_id)


@router.put("/suggestions/{suggestion_id}/plan-structured")
def save_suggestion_structured_plan(suggestion_id: int, body: dict = Body(...)):
    return planner.save_suggestion_draft(
        suggestion_id,
        body.get("structured") or body,
        operator=body.get("operator", "marketer"),
    )


@router.get("/feishu/calendar/raw")
def get_feishu_calendar_raw():
    client = FeishuMarketingCalendarClient()
    records = client.list_calendar_records()
    return {
        "source": "mock" if client.use_mock else "feishu_api",
        "app_token": client.app_token,
        "table_id": client.table_id or "(未配置 FEISHU_MARKETING_CALENDAR_TABLE_ID)",
        "count": len(records),
        "by_month": client.group_by_month(records),
        "records": records,
    }


@router.get("/feishu/calendar/status")
def get_feishu_calendar_status():
    client = FeishuMarketingCalendarClient()
    return {
        "mode": "mock" if client.use_mock else "live",
        "marketing_calendar_app_token": client.app_token,
        "table_id_configured": bool(client.table_id),
        "view_id_configured": bool(client.view_id),
        "credentials_configured": bool(client.app_id and client.app_secret),
        "setup_hint": (
            "配置 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_MARKETING_CALENDAR_TABLE_ID 后重启 API"
            if client.use_mock
            else "已连接飞书营销日历 API"
        ),
    }


@router.get("/activities/{campaign_id}")
def get_activity(campaign_id: str):
    plan = planner.get_activity_plan(campaign_id)
    if not plan:
        return {"error": "not found"}
    return plan


@router.patch("/activities/{campaign_id}/plan")
def update_plan(campaign_id: str, body: dict = Body(...)):
    return planner.update_plan(campaign_id, body)


@router.get("/activities/{campaign_id}/plan-structured")
def get_structured_plan(campaign_id: str):
    return planner.get_structured_plan(campaign_id)


@router.put("/activities/{campaign_id}/plan-structured")
def save_structured_plan(campaign_id: str, body: dict = Body(...)):
    return planner.save_structured_plan(
        campaign_id,
        body.get("structured") or body,
        editor=body.get("operator", "marketer"),
    )


@router.post("/activities/{campaign_id}/confirm-plan-review")
def confirm_plan_review(campaign_id: str, body: dict = Body(default={})):
    return planner.confirm_plan_review(campaign_id, operator=body.get("operator", "marketer"))


@router.post("/activities/{campaign_id}/remove-from-annual-plan")
def remove_from_annual_plan(campaign_id: str, body: dict = Body(default={})):
    """从全年计划池删除活动（不再展示在日历）。"""
    return planner.remove_from_annual_plan(
        campaign_id,
        operator=body.get("operator", "marketer"),
        reason=body.get("reason"),
    )


@router.post("/activities/{campaign_id}/reject-proposal")
def reject_calendar_proposal(campaign_id: str, body: dict = Body(default={})):
    """拒绝飞书营销规划（方案库条目），不删除、不进全年计划池。"""
    return planner.reject_calendar_proposal(
        campaign_id,
        operator=body.get("operator", "marketer"),
        reason=body.get("reason"),
    )


@router.post("/activities/{campaign_id}/send-to-agent2")
def send_to_agent2(campaign_id: str):
    return orchestrator.gate_confirm_send_to_agent2(campaign_id)


@router.post("/demo/seed-agent2-case")
def seed_agent2_demo_case(body: dict = Body(default={})):
    """写入 2027 全年演示活动（全年计划池 + 活动建档日历）。"""
    from app.services.v2.demo_seed import seed_demo_calendar_2027

    return seed_demo_calendar_2027(force=bool(body.get("force")))


@router.post("/activities/{campaign_id}/generate-task-board")
def generate_task_board(campaign_id: str, body: dict = Body(default={})):
    """按建档内容自动拆三线任务（可 force 覆盖已有任务）。"""
    from app.models.campaign_plan_schema import build_full_structured_plan, ensure_task_board

    plan = planner.get_activity_plan(campaign_id)
    if not plan:
        return {"ok": False, "error": "Campaign not found"}
    structured = build_full_structured_plan(plan)
    structured = ensure_task_board(structured, force=bool(body.get("force")))
    return planner.save_structured_plan(campaign_id, structured, editor=body.get("operator", "marketer"))


@router.post("/activities/{campaign_id}/profile-query")
def query_profile(campaign_id: str, body: dict = Body(default={})):
    """运营师修改客户/产品画像条件，实时调 MCP 预览圈客选品结果。"""
    from app.services.v2.agent2_resource import ResourceConfiguratorService
    return ResourceConfiguratorService().preview_profile_query(campaign_id, body)


@router.post("/profile-query")
def query_profile_adhoc(body: dict = Body(...)):
    """不绑定活动，直接按画像条件查 MCP。"""
    from app.mcp.warehouse_client import WarehouseClient
    return WarehouseClient().query_by_profile(body)


@router.get("/warehouse/status")
def get_warehouse_status():
    from app.mcp.warehouse_client import WarehouseClient
    client = WarehouseClient()
    status = client.get_status()
    if not client.use_local:
        status["health"] = client.mcp.health_check()
    return status


@router.get("/activities/{campaign_id}/query-profile")
def get_query_profile(campaign_id: str):
    """Agent1 方案中的 Query Profile（Agent2 执行契约）。"""
    return resource.get_query_profile(campaign_id)


@router.get("/activities/{campaign_id}/resource-plan")
def get_resource_plan(campaign_id: str):
    return resource.get_resource_plan(campaign_id)


@router.get("/activities/{campaign_id}/resource-prep-analysis")
def get_resource_prep_analysis(campaign_id: str):
    """返回活动的 QBI 七步分析结果（自动或上次手动筛选缓存）。"""
    from app.services.v2.resource_prep_analysis import ResourcePrepAnalysisService
    return ResourcePrepAnalysisService().analyze_campaign(campaign_id)


def _analysis_overrides(body: dict) -> dict:
    return {
        "mode": body.get("mode") or "auto",
        "destination": body.get("destination"),
        "country": body.get("country"),
        "city": body.get("city"),
        "date_from": body.get("date_from"),
        "date_to": body.get("date_to"),
        "customer_type": body.get("customer_type"),
        "promotion_month": body.get("promotion_month"),
    }


@router.post("/activities/{campaign_id}/resource-prep-analysis")
def run_resource_prep_analysis(campaign_id: str, body: dict = Body(default={})):
    from app.services.v2.resource_prep_analysis import ResourcePrepAnalysisService
    svc = ResourcePrepAnalysisService()
    ov = _analysis_overrides(body or {})
    if body.get("apply_to_plan"):
        return svc.apply_to_campaign(campaign_id, operator=body.get("operator", "marketer"), overrides=ov)
    insight = svc.analyze_campaign(campaign_id, overrides=ov)
    if insight.get("ok"):
        svc._store_pack(campaign_id, insight)
    return insight


@router.post("/activities/{campaign_id}/configure")
def configure_resources(campaign_id: str, body: dict = Body(default={})):
    return resource.configure_resources(campaign_id, body or None)


@router.post("/activities/{campaign_id}/resource-override")
def resource_override(campaign_id: str, body: dict = Body(...)):
    """
    body: {
      "mode": "manual_ids"|"mixed",
      "target_client_ids": ["c_1", ...],
      "target_hotel_ids": ["123", ...],
      "override_reason": "补入战略客户"
    }
    """
    return resource.apply_resource_override(
        campaign_id,
        target_client_ids=body.get("target_client_ids"),
        target_hotel_ids=body.get("target_hotel_ids"),
        override_reason=body.get("override_reason", ""),
        mode=body.get("mode", "manual_ids"),
        operator=body.get("operator", "marketer"),
    )


@router.post("/activities/{campaign_id}/confirm-resources")
def confirm_resources(campaign_id: str, body: dict = Body(default={})):
    return resource.confirm_resources(campaign_id, operator=body.get("operator", "marketer"))


@router.get("/activities/{campaign_id}/todos")
def list_todos(campaign_id: str):
    return resource.list_todos(campaign_id)


@router.post("/todos/{todo_id}/complete")
def complete_todo(todo_id: int):
    return orchestrator.gate_mark_todo_done(todo_id)


@router.post("/activities/{campaign_id}/submit-test")
def submit_test(campaign_id: str):
    return resource.submit_for_testing(campaign_id)


@router.post("/activities/{campaign_id}/approve-test")
def approve_test(campaign_id: str):
    return resource.approve_testing(campaign_id)


@router.get("/activities/{campaign_id}/monitor/preview")
def preview_monitor(campaign_id: str):
    return monitor.preview_dashboard(campaign_id)


@router.post("/activities/{campaign_id}/monitor/confirm")
def confirm_monitor(campaign_id: str):
    return orchestrator.gate_confirm_monitoring(campaign_id)


@router.get("/activities/{campaign_id}/review")
def get_review(campaign_id: str):
    return analyst.generate_review_report(campaign_id)


@router.get("/activities/{campaign_id}/diagnosis")
def get_diagnosis(campaign_id: str):
    from app.services.v2.campaign_diagnosis import CampaignDiagnosisService

    return CampaignDiagnosisService().get_pack(campaign_id)


@router.post("/activities/{campaign_id}/diagnosis")
def run_diagnosis(campaign_id: str):
    from app.services.v2.campaign_diagnosis import CampaignDiagnosisService

    return CampaignDiagnosisService().diagnose(campaign_id)


@router.post("/activities/{campaign_id}/review/confirm")
def confirm_review(campaign_id: str):
    return orchestrator.gate_confirm_review(campaign_id)


@router.post("/activities/{campaign_id}/archive")
def archive_activity(campaign_id: str, body: dict = Body(default={})):
    conclusion = (body or {}).get("human_conclusion")
    if conclusion:
        from app.models.campaign_plan_schema import build_full_structured_plan

        plan = planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "活动不存在"}
        structured = build_full_structured_plan(plan)
        structured.setdefault("archive", {})
        structured["archive"]["human_conclusion"] = conclusion
        if body.get("experience") is not None:
            structured["archive"]["experience"] = body.get("experience")
        if body.get("pitfalls") is not None:
            structured["archive"]["pitfalls"] = body.get("pitfalls")
        planner.save_structured_plan(campaign_id, structured, editor=body.get("operator", "marketer"))
    return orchestrator.step_archive(campaign_id, operator=(body or {}).get("operator", "marketer"))


@router.get("/archives")
def search_archives(destination: str | None = None, activity_type: str | None = None):
    return archive.search_similar(destination, activity_type)


@router.post("/pipeline/{campaign_id}/run")
def run_pipeline(campaign_id: str, auto_gates: bool = True):
    return orchestrator.run_full_pipeline(campaign_id, auto_gates=auto_gates)


@router.get("/lifecycle/{campaign_id}")
def get_lifecycle(campaign_id: str):
    return {"campaign_id": campaign_id, "status": lifecycle.get_status(campaign_id)}
