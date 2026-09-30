"""Agent 1 - 信息数据分析 数据服务。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine


class Agent1Service:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def get_client_profile(self, client_id: str | None = None, limit: int = 50) -> list[dict]:
        sql = """
        SELECT * FROM dim_client
        WHERE (:client_id IS NULL OR client_id = :client_id)
        ORDER BY last_active_date DESC
        LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"client_id": client_id, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_behavior_trajectory(self, user_id: str, limit: int = 100) -> list[dict]:
        sql = """
        SELECT event_time, event_type, page_name, search_des_query, country_name,
               dida_hotel_id, quote_price, stay_time
        FROM fact_events WHERE user_id = :uid
        ORDER BY event_time DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"uid": user_id, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_search_preferences(self, destination: str | None = None, limit: int = 100) -> list[dict]:
        sql = """
        SELECT client_id, search_des_query, country_name, star_rating, brands,
               price_min, price_max, COUNT(*) AS search_count
        FROM fact_search
        WHERE (:dest IS NULL OR country_name LIKE '%' || :dest || '%'
               OR search_des_query LIKE '%' || :dest || '%')
        GROUP BY client_id, search_des_query, country_name, star_rating, brands, price_min, price_max
        ORDER BY search_count DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"dest": destination, "limit": limit})
            return [dict(r._mapping) for r in rows]

    def get_funnel_conversion(
        self, client_id: str | None = None, country: str | None = None
    ) -> list[dict]:
        sql = """
        SELECT step_code, step_name, step_no, COUNT(*) AS cnt
        FROM fact_funnel
        WHERE (:cid IS NULL OR client_id = :cid)
          AND (:country IS NULL OR country_name LIKE '%' || :country || '%')
        GROUP BY step_code, step_name, step_no
        ORDER BY step_no
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"cid": client_id, "country": country})
            return [dict(r._mapping) for r in rows]

    def get_demand_report(self, destination: str = "Singapore") -> dict:
        """输出客户需求报告（Agent 1 核心输出）。"""
        clients_sql = """
        SELECT DISTINCT c.client_id, c.client_group_cn, c.tag_customer_value,
               c.tag_activity_level, c.tag_preferred_dest, c.tag_churn_risk
        FROM dim_client c
        JOIN fact_search s ON c.client_id = s.client_id
        WHERE s.country_name LIKE '%' || :dest || '%'
           OR s.search_des_query LIKE '%' || :dest || '%'
        LIMIT 200
        """
        search_sql = """
        SELECT search_des_query, star_rating, AVG(CAST(price_min AS REAL)) AS avg_price_min,
               AVG(CAST(price_max AS REAL)) AS avg_price_max, COUNT(*) AS searches
        FROM fact_search
        WHERE country_name LIKE '%' || :dest || '%'
           OR search_des_query LIKE '%' || :dest || '%'
        GROUP BY search_des_query, star_rating
        ORDER BY searches DESC LIMIT 20
        """
        funnel = self.get_funnel_conversion(country=destination)
        events_sql = """
        SELECT event_type, COUNT(*) AS cnt FROM fact_events
        WHERE country_name LIKE '%' || :dest || '%'
        GROUP BY event_type ORDER BY cnt DESC LIMIT 10
        """
        ext_sql = """
        SELECT * FROM dim_destination_events
        WHERE destination LIKE '%' || :dest || '%'
        """
        with self.engine.connect() as conn:
            clients = [dict(r._mapping) for r in conn.execute(text(clients_sql), {"dest": destination})]
            searches = [dict(r._mapping) for r in conn.execute(text(search_sql), {"dest": destination})]
            events = [dict(r._mapping) for r in conn.execute(text(events_sql), {"dest": destination})]
            external = [dict(r._mapping) for r in conn.execute(text(ext_sql), {"dest": destination})]

        # 计算流失环节
        funnel_rates = []
        prev = None
        for step in funnel:
            rate = step["cnt"] / prev if prev else 1.0
            funnel_rates.append({**step, "step_conversion": round(rate, 4) if prev else 1.0})
            prev = step["cnt"]

        return {
            "destination": destination,
            "target_clients": clients,
            "client_count": len(clients),
            "search_preferences": searches,
            "behavior_summary": events,
            "funnel_analysis": funnel_rates,
            "external_events": external,
            "recommendation_direction": [
                f"针对 {destination} 目的地，优先触达 {len(clients)} 个有搜索行为的客户",
                "推荐星级: " + ", ".join({s.get("star_rating") or "不限" for s in searches[:5]}),
                "关注漏斗流失环节: " + (
                    funnel_rates[-2]["step_name"] if len(funnel_rates) > 1 else "RP点击→预订"
                ),
            ],
        }
