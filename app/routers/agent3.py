from fastapi import APIRouter, Query

from app.services.agent3_service import Agent3Service

router = APIRouter(prefix="/agent3", tags=["Agent3-方案策划+监控"])
service = Agent3Service()


@router.get("/campaigns")
def get_campaigns(status: str | None = None):
    return service.get_campaigns(status)


@router.get("/metrics/{campaign_id}")
def get_metrics(campaign_id: str):
    return service.compute_campaign_metrics(campaign_id)


@router.get("/metrics/history/{campaign_id}")
def get_metrics_history(campaign_id: str):
    return service.get_campaign_metrics(campaign_id)


@router.get("/alert-rules/{campaign_id}")
def get_alert_rules(campaign_id: str):
    return service.get_alert_rules(campaign_id)


@router.get("/monitor/{campaign_id}")
def get_monitor(campaign_id: str, limit: int = Query(50, le=200)):
    return service.get_monitor_data(campaign_id, limit)


@router.post("/monitor/{campaign_id}/run")
def run_monitor(campaign_id: str):
    """执行监控并触发告警"""
    alerts = service.run_monitoring(campaign_id)
    return {"alerts": alerts, "alert_count": len(alerts)}
