"""数据仓库 MCP/SQL 客户端；MCP 不可用时 fallback 本地 SQLite。"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.mcp.warehouse_mcp_adapter import WarehouseMcpAdapter
from app.mcp.warehouse_schema import (
    DESTINATION_KEYWORDS,
    TABLES,
    destination_like_clause,
    sql_clients_by_destination,
    sql_funnel_by_destination,
    sql_hotel_prices,
    sql_hotels_by_destination,
)


from app.services.config_store import load_integrations


class WarehouseClient:
    """封装数仓查询；生产环境通过 MCP 读取三张核心表。"""

    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        cfg = load_integrations().get("warehouse_mcp", {})
        self.mcp = WarehouseMcpAdapter()
        self.use_local = (
            not self.mcp.is_configured
            or os.getenv("WAREHOUSE_USE_LOCAL", "").lower() in ("1", "true")
        )
        tables = cfg.get("tables") or {}
        self.tables = {
            "events": os.getenv("WAREHOUSE_TABLE_EVENTS", tables.get("events", TABLES["events"])),
            "users": os.getenv("WAREHOUSE_TABLE_USERS", tables.get("users", TABLES["users"])),
            "funnel": os.getenv("WAREHOUSE_TABLE_FUNNEL", tables.get("funnel", TABLES["funnel"])),
            "orders": os.getenv("WAREHOUSE_TABLE_ORDERS", tables.get("orders", TABLES.get("orders", "booking.channelbooking_v2"))),
        }

    @property
    def mode(self) -> str:
        return "local_sqlite" if self.use_local else "warehouse_mcp"

    def get_status(self) -> dict:
        return {
            "mode": self.mode,
            "tables": self.tables,
            "mcp_endpoint": self.mcp.endpoint or None,
            "mcp_configured": self.mcp.is_configured,
            "tracking_doc": "0.2 Shopping网站埋点（飞书云文档）",
        }

    def _resolve_keywords(self, destination: str) -> list[str]:
        for key, kws in DESTINATION_KEYWORDS.items():
            if key.lower() in destination.lower() or destination.lower() in key.lower():
                return kws
        # 中文/英文直接作为关键词
        return [destination]

    def _dest_clause_funnel(self, keywords: list[str]) -> str:
        return destination_like_clause(keywords, "f.country_name", "f.city_name")

    def _execute_mcp(self, sql: str, tables: list[str] | None = None) -> list[dict]:
        tables = tables or [
            self.tables["events"],
            self.tables["users"],
            self.tables["funnel"],
        ]
        return self.mcp.execute_sql(sql, tables=tables, data_type=3)

    def query_clients_by_destination(
        self, destination: str, client_groups: list[int] | None = None, limit: int = 200
    ) -> list[dict]:
        if self.use_local:
            return self._local_clients(destination, client_groups, limit)

        kws = self._resolve_keywords(destination)
        clause = self._dest_clause_funnel(kws)
        sql = sql_clients_by_destination(
            self.tables["events"], self.tables["users"], self.tables["funnel"], clause, limit
        )
        rows = self._execute_mcp(sql, [self.tables["events"], self.tables["users"], self.tables["funnel"]])
        if client_groups:
            rows = [r for r in rows if r.get("client_group_id") in client_groups]
        return self._normalize_clients(rows)

    def query_hotels_by_destination(
        self,
        destination: str,
        star_rating: str | None = None,
        star_min: int | None = None,
        limit: int = 20,
        keyword_boost: list[str] | None = None,
    ) -> list[dict]:
        if self.use_local:
            return self._local_hotels(destination, star_rating, star_min, limit, keyword_boost)

        kws = self._resolve_keywords(destination)
        clause = self._dest_clause_funnel(kws)
        sql = sql_hotels_by_destination(self.tables["funnel"], clause, limit * 3)
        rows = self._execute_mcp(sql, [self.tables["funnel"]])
        rows = self._filter_hotels(rows, star_rating, star_min, keyword_boost)
        return rows[:limit]

    def query_hotel_prices(self, hotel_id: int | str, limit: int = 10) -> list[dict]:
        if self.use_local:
            sql = """
            SELECT dida_hotel_id, quote_price, quote_currency, supplier_id, event_time
            FROM fact_events WHERE dida_hotel_id = :hid AND quote_price IS NOT NULL
            ORDER BY event_time DESC LIMIT :limit
            """
            with self.engine.connect() as conn:
                return [dict(r._mapping) for r in conn.execute(text(sql), {"hid": hotel_id, "limit": limit})]

        sql = sql_hotel_prices(self.tables["events"], hotel_id, limit)
        return self._execute_mcp(sql, [self.tables["events"]])

    def query_funnel_by_destination(self, destination: str) -> list[dict]:
        if self.use_local:
            sql = """
            SELECT step_code, step_name, step_no, COUNT(*) AS cnt
            FROM fact_funnel WHERE country_name LIKE :dest OR city_name LIKE :dest
            GROUP BY step_code, step_name, step_no ORDER BY step_no
            """
            with self.engine.connect() as conn:
                return [dict(r._mapping) for r in conn.execute(text(sql), {"dest": f"%{destination}%"})]

        kws = self._resolve_keywords(destination)
        clause = self._dest_clause_funnel(kws)
        sql = sql_funnel_by_destination(self.tables["funnel"], clause)
        return self._execute_mcp(sql, [self.tables["funnel"]])

    def query_search_insights(self, destination: str, limit: int = 20) -> list[dict]:
        """搜索行为洞察（埋点 event_properties_json.search_des_query）。"""
        if self.use_local:
            sql = """
            SELECT search_des_query, COUNT(*) AS cnt
            FROM fact_events
            WHERE (search_des_query LIKE :dest OR country_name LIKE :dest)
              AND search_des_query IS NOT NULL
            GROUP BY search_des_query ORDER BY cnt DESC LIMIT :limit
            """
            with self.engine.connect() as conn:
                return [dict(r._mapping) for r in conn.execute(text(sql), {"dest": f"%{destination}%", "limit": limit})]

        kws = self._resolve_keywords(destination)
        like_arr = ", ".join(f"'%{k}%'" for k in kws)
        sql = f"""
        SELECT
            e.event_properties_json::jsonb ->> 'search_des_query' AS search_des_query,
            COUNT(*) AS cnt
        FROM {self.tables['events']} e
        WHERE e.event_type IN ('search_des_sugg_click', 'hotel_find_search')
          AND e.event_properties_json::jsonb ->> 'search_des_query' ILIKE ANY (ARRAY[{like_arr}])
          AND e.event_date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY 1
        ORDER BY cnt DESC
        LIMIT {limit}
        """
        return self._execute_mcp(sql, [self.tables["events"]])

    def query_by_profile(self, profile: dict) -> dict:
        """
        按 Query Profile DSL 调 MCP 圈客选品。
        profile 来自 Agent1 方案 ⑥⑦ 的 query_profile，运营师可在 UI 修改后重新查询。
        """
        destination = profile.get("destination") or profile.get("target_dest") or "Singapore"
        client_groups = profile.get("client_group_ids") or profile.get("client_groups")
        if isinstance(client_groups, str):
            client_groups = [int(x.strip()) for x in client_groups.split(",") if x.strip().isdigit()]
        star_min = profile.get("star_min") or profile.get("min_star_rating")
        star_rating = profile.get("star_rating")
        if star_min is not None:
            try:
                star_min = int(star_min)
            except (TypeError, ValueError):
                star_min = None
        hotel_limit = int(profile.get("hotel_limit") or 20)
        client_limit = int(profile.get("client_limit") or 200)
        keyword_boost = profile.get("keyword_boost") or []
        if isinstance(keyword_boost, str):
            keyword_boost = [k.strip() for k in keyword_boost.split(",") if k.strip()]

        clients = self.query_clients_by_destination(destination, client_groups, client_limit)
        hotels = self.query_hotels_by_destination(
            destination,
            str(star_rating) if star_rating and not star_min else None,
            star_min=star_min,
            limit=hotel_limit,
            keyword_boost=keyword_boost or None,
        )
        hotels = self._filter_hotel_prices(hotels, profile)
        funnel = self.query_funnel_by_destination(destination)
        search = self.query_search_insights(destination, 10)

        applied = {
            **profile,
            "destination": destination,
            "client_group_ids": client_groups or [],
            "star_min": star_min or star_rating,
            "client_limit": client_limit,
            "hotel_limit": hotel_limit,
            "time_window_days": profile.get("time_window_days") or 90,
            "behavior_source": profile.get("behavior_source") or "funnel",
            "step_codes": profile.get("step_codes") or ["request", "click"],
        }

        return {
            "profile_applied": applied,
            "data_source": self.mode,
            "clients": clients,
            "client_ids": [c["client_id"] for c in clients if c.get("client_id")],
            "hotels": hotels,
            "hotel_ids": [h.get("dida_hotel_id") or h.get("standard_hotel_id") for h in hotels],
            "funnel_baseline": funnel,
            "search_insights": search,
            "client_count": len(clients),
            "hotel_count": len(hotels),
        }

    @staticmethod
    def _filter_hotels(
        rows: list[dict],
        star_rating: str | None,
        star_min: int | None,
        keyword_boost: list[str] | None,
    ) -> list[dict]:
        out = rows
        if star_min is not None:
            out = [r for r in out if (r.get("star_rating") or 0) >= star_min]
        elif star_rating:
            out = [r for r in out if str(r.get("star_rating")) == str(star_rating)]
        if keyword_boost:
            boosted = [
                r for r in out
                if any(k.lower() in (r.get("dida_hotel_name") or "").lower() for k in keyword_boost)
            ]
            others = [r for r in out if r not in boosted]
            out = boosted + others
        return out

    @staticmethod
    def _filter_hotel_prices(hotels: list[dict], profile: dict) -> list[dict]:
        pmin = profile.get("price_min_cny")
        pmax = profile.get("price_max_cny")
        if pmin is None and pmax is None:
            return hotels
        out = []
        for h in hotels:
            price = h.get("avg_price_cny") or h.get("quote_price")
            if price is None:
                out.append(h)
                continue
            if pmin is not None and price < pmin:
                continue
            if pmax is not None and price > pmax:
                continue
            out.append(h)
        return out or hotels

    def compare_price_vs_market(self, hotel_id: int, our_price: float, market_price: float | None = None) -> dict:
        market = market_price if market_price else round(our_price * 1.05, 2)
        advantage = our_price <= market
        gap_pct = round((market - our_price) / market * 100, 2) if market else 0
        suggested_coupon_pct = max(0, round(gap_pct + 2, 1)) if not advantage else 0
        return {
            "hotel_id": hotel_id,
            "our_price": our_price,
            "market_price": market,
            "has_advantage": advantage,
            "price_gap_pct": gap_pct,
            "suggested_coupon_pct": suggested_coupon_pct,
        }

    def _normalize_clients(self, rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            out.append({
                "client_id": r.get("client_id"),
                "client_name": r.get("client_name"),
                "client_group_id": r.get("client_group_id"),
                "client_group_cn": r.get("client_group_cn"),
                "tag_customer_value": r.get("tag_customer_value"),
                "tag_activity_level": "high" if (r.get("rp_click_pv") or 0) > 5 else "medium",
                "tag_preferred_dest": r.get("tag_preferred_dest"),
                "funnel_pv": r.get("funnel_pv"),
                "rp_click_pv": r.get("rp_click_pv"),
            })
        return out

    def _local_clients(self, destination: str, client_groups: list[int] | None, limit: int) -> list[dict]:
        group_filter = ""
        params: dict[str, Any] = {"dest": f"%{destination}%", "limit": limit}
        if client_groups:
            placeholders = ", ".join(str(g) for g in client_groups)
            group_filter = f"AND c.client_group_id IN ({placeholders})"
        sql = f"""
        SELECT DISTINCT c.client_id, c.client_name, c.client_group_cn,
               c.tag_customer_value, c.tag_activity_level, c.tag_preferred_dest
        FROM dim_client c
        JOIN fact_funnel f ON c.client_id = f.client_id
        WHERE (f.country_name LIKE :dest OR f.city_name LIKE :dest)
        {group_filter}
        LIMIT :limit
        """
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    def _local_hotels(
        self,
        destination: str,
        star_rating: str | None,
        star_min: int | None,
        limit: int,
        keyword_boost: list[str] | None = None,
    ) -> list[dict]:
        sql = """
        SELECT standard_hotel_id AS dida_hotel_id, dida_hotel_name, country_name, city_name, star_rating
        FROM dim_hotel
        WHERE country_name LIKE :dest OR city_name LIKE :dest
        """
        params: dict[str, Any] = {"dest": f"%{destination}%", "limit": limit}
        if star_min is not None:
            sql += " AND star_rating >= :star_min"
            params["star_min"] = star_min
        elif star_rating:
            sql += " AND star_rating = :star"
            params["star"] = star_rating
        sql += " LIMIT :limit"
        with self.engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(text(sql), params)]
        return self._filter_hotels(rows, star_rating, star_min, keyword_boost)[:limit]
