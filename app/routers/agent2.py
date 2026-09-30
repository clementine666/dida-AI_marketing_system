from fastapi import APIRouter, Query

from app.services.agent2_service import Agent2Service

router = APIRouter(prefix="/agent2", tags=["Agent2-资源匹配"])
service = Agent2Service()


@router.get("/hotels")
def get_hotels(
    destination: str | None = None,
    star_rating: str | None = None,
    limit: int = Query(50, le=200),
):
    return service.get_hotels(destination, star_rating, limit)


@router.get("/price-inventory")
def get_price_inventory(hotel_id: int | None = None, limit: int = Query(100, le=500)):
    return service.get_price_inventory(hotel_id, limit)


@router.get("/rp/{hotel_id}")
def get_rp_data(hotel_id: int, limit: int = Query(50, le=200)):
    return service.get_rp_data(hotel_id, limit)


@router.get("/resource-gaps")
def get_gaps(destination: str):
    return service.get_resource_gaps(destination)


@router.get("/match")
def match_resources(destination: str = "Singapore", event_name: str = "F1"):
    """Agent 2 核心输出：资源匹配方案"""
    return service.match_resources(destination, event_name)
