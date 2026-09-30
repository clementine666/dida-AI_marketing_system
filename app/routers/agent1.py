from fastapi import APIRouter, Query

from app.services.agent1_service import Agent1Service

router = APIRouter(prefix="/agent1", tags=["Agent1-数据分析"])
service = Agent1Service()


@router.get("/clients")
def get_clients(client_id: str | None = None, limit: int = Query(50, le=500)):
    return service.get_client_profile(client_id, limit)


@router.get("/behavior/{user_id}")
def get_behavior(user_id: str, limit: int = Query(100, le=1000)):
    return service.get_behavior_trajectory(user_id, limit)


@router.get("/search-preferences")
def get_search_prefs(destination: str | None = None, limit: int = Query(100, le=500)):
    return service.get_search_preferences(destination, limit)


@router.get("/funnel")
def get_funnel(client_id: str | None = None, country: str | None = None):
    return service.get_funnel_conversion(client_id, country)


@router.get("/demand-report")
def get_demand_report(destination: str = "Singapore"):
    """Agent 1 核心输出：客户需求报告"""
    return service.get_demand_report(destination)
