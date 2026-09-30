from fastapi import APIRouter

from app.services.agent4_service import Agent4Service

router = APIRouter(prefix="/agent4", tags=["Agent4-效果复盘"])
service = Agent4Service()


@router.get("/orders/{campaign_id}")
def get_orders(campaign_id: str):
    return service.get_campaign_orders(campaign_id)


@router.get("/funnel/{campaign_id}")
def get_funnel(campaign_id: str):
    return service.get_funnel_during_campaign(campaign_id)


@router.get("/compare/{campaign_id}")
def compare_target(campaign_id: str):
    return service.compare_target_vs_actual(campaign_id)


@router.get("/review/{campaign_id}")
def get_review(campaign_id: str):
    """Agent 4 核心输出：复盘报告"""
    return service.generate_review_report(campaign_id)
