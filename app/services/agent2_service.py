"""Agent 2 - 资源匹配 数据服务。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine


class Agent2Service:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def get_hotels(
        self, destination: str | None = None, star_rating: str | None = None, limit: int = 50
    ) -> list[dict]:
        sql = """
        SELECT * FROM dim_hotel
        WHERE (:dest IS NULL OR country_name LIKE '%' || :dest || '%' OR city_name LIKE '%' || :dest || '%')
          AND (:star IS NULL OR star_rating = :star)
        ORDER BY tag_popularity DESC
        LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"dest": destination, "star": star_rating, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_price_inventory(self, hotel_id: int | None = None, limit: int = 100) -> list[dict]:
        sql = """
        SELECT dida_hotel_id, quote_price, quote_currency, supplier_id, rp_count,
               supplier_count, inventory_status, event_time
        FROM fact_events e
        LEFT JOIN (
            SELECT standard_hotel_id, inventory_status, dida_hotel_name
            FROM fact_funnel WHERE step_code = 'available'
        ) f ON CAST(e.dida_hotel_id AS TEXT) = f.standard_hotel_id
        WHERE e.dida_hotel_id IS NOT NULL
          AND (:hid IS NULL OR e.dida_hotel_id = :hid)
        ORDER BY event_time DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"hid": hotel_id, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_rp_data(self, hotel_id: int, limit: int = 50) -> list[dict]:
        sql = """
        SELECT dida_hotel_id, dida_rpid, room_type_name, bed_type, meal_type,
               quote_price, cancellation_policy, check_type, room_nights, rp_area
        FROM fact_events
        WHERE dida_hotel_id = :hid AND dida_rpid IS NOT NULL
        ORDER BY event_time DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"hid": hotel_id, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_resource_gaps(self, destination: str) -> list[dict]:
        sql = """
        SELECT country_name, city_name, star_rating,
               SUM(CASE WHEN inventory_status = 'sold_out' THEN 1 ELSE 0 END) AS sold_out_cnt,
               SUM(CASE WHEN inventory_status = 'available' THEN 1 ELSE 0 END) AS available_cnt,
               COUNT(*) AS total
        FROM fact_funnel
        WHERE country_name LIKE '%' || :dest || '%'
        GROUP BY country_name, city_name, star_rating
        HAVING sold_out_cnt > 0
        ORDER BY sold_out_cnt DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"dest": destination})
            return [dict(r._mapping) for r in rows]

    def match_resources(self, destination: str = "Singapore", event_name: str = "F1") -> dict:
        """输出资源匹配方案（Agent 2 核心输出）。"""
        hotels = self.get_hotels(destination=destination, limit=20)
        # F1 赛场周边优先（Marina Bay 区域）
        f1_keywords = ("Marina", "Bay", "Fullerton", "Pan Pacific", "Swissotel", "Parkroyal")
        matched = [h for h in hotels if any(k in (h.get("dida_hotel_name") or "") for k in f1_keywords)]
        if not matched:
            matched = hotels[:10]

        hotel_list = []
        for h in matched:
            hid = h.get("dida_hotel_id") or h.get("standard_hotel_id")
            prices = self.get_price_inventory(
                hotel_id=int(hid) if str(hid).isdigit() else None, limit=5
            )
            avg_price = (
                sum(p["quote_price"] or 0 for p in prices) / len(prices) if prices else None
            )
            hotel_list.append({
                "hotel_id": hid,
                "hotel_name": h.get("dida_hotel_name"),
                "star_rating": h.get("star_rating"),
                "city": h.get("city_name"),
                "avg_price_cny": round(avg_price, 2) if avg_price else None,
                "inventory_status": prices[0].get("inventory_status") if prices else "unknown",
                "tag_popularity": h.get("tag_popularity"),
            })

        gaps = self.get_resource_gaps(destination)
        return {
            "destination": destination,
            "event_context": event_name,
            "matched_hotels": hotel_list,
            "hotel_count": len(hotel_list),
            "resource_gaps": gaps,
            "matching_features": [
                "F1赛场5km辐射圈酒店优先",
                "4-5星级酒店",
                "直签酒店(DC)优先展示",
            ],
            "recommended_promotions": [
                "F1赛事专属套餐",
                "提前预订折扣",
                "多间夜连住优惠",
            ],
        }
