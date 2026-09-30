"""数仓三张核心表定义与 Agent2 查询 SQL 模板。"""

from __future__ import annotations

# 生产数仓表（用户提供）
TABLES = {
    "events": "shopping.ods_amplitude_events",
    "users": "shopping.ods_amplitude_users",
    "funnel": "dwd.dwd_hotel_shopping_funnel_detail_d_f",
    "orders": "booking.channelbooking_v2",
}

# 目的地关键词（营销日历「地区」→ 数仓检索词）
DESTINATION_KEYWORDS: dict[str, list[str]] = {
    "Singapore": ["Singapore", "新加坡"],
    "Hong Kong": ["Hong Kong", "HK", "香港"],
    "Malaysia": ["Malaysia", "马来西亚", "Kuala Lumpur", "吉隆坡"],
    "Thailand": ["Thailand", "泰国", "Bangkok", "曼谷"],
    "Japan": ["Japan", "日本", "Tokyo", "东京", "Osaka", "大阪"],
    "USA": ["USA", "United States", "美国", "New York", "Los Angeles"],
    "Germany": ["Germany", "德国", "Berlin", "Munich"],
    "France": ["France", "法国", "Paris", "巴黎"],
    "Italy": ["Italy", "意大利", "Rome", "Milan"],
    "Switzerland": ["Switzerland", "瑞士", "Zurich", "Geneva"],
    "Spain": ["Spain", "西班牙", "Madrid", "Barcelona"],
    "Portugal": ["Portugal", "葡萄牙", "Lisbon"],
}

# 埋点方案关键 event_type（参考 0.2 Shopping 网站埋点）
TRACKING_EVENTS = {
    "banner_expose": "primary_banner_expose",
    "banner_click": "primary_banner_click",
    "slide_expose": "slide_expose",
    "slide_click": "slide_click",
    "search_click": "search_des_sugg_click",
    "hotel_find": "hotel_find_search",
    "rp_expose": "hotel_detail_rp_expose",
    "rp_click": "hotel_detail_rp_click",
    "prebook": "hotel_prebook",
    "order_success": "hotel_order_success",
}

# funnel step_code 与 Agent 监控映射
FUNNEL_STEPS = {
    "request": ("1.酒店详情请求", 1),
    "available": ("2.酒店详情有价返回", 2),
    "expose": ("3.酒店详情RP曝光", 3),
    "click": ("4.酒店详情RP点击", 4),
    "prebook": ("5.酒店预订页", 5),
    "success": ("6.支付成功", 6),
}


def destination_like_clause(keywords: list[str], *columns: str) -> str:
    """生成 OR LIKE 条件。"""
    parts = []
    for col in columns:
        for kw in keywords:
            parts.append(f"{col} ILIKE '%{kw.replace(chr(39), '')}%'")
    return "(" + " OR ".join(parts) + ")"


def sql_clients_by_destination(events: str, users: str, funnel: str, dest_clause: str, limit: int) -> str:
    """
    圈客：漏斗目的地行为 + 用户表关联。
    优先选近90天在该目的地有漏斗行为的 client。
    """
    return f"""
    SELECT DISTINCT
        f.client_id,
        f.client_name,
        f.client_group_id,
        f.client_group_cn,
        COUNT(DISTINCT f.pv_key) AS funnel_pv,
        COUNT(DISTINCT CASE WHEN f.step_code = 'click' THEN f.pv_key END) AS rp_click_pv
    FROM {funnel} f
    JOIN {users} u ON f.user_id = u.user_id
    WHERE {dest_clause}
      AND (f.is_test_account IS NULL OR f.is_test_account = false)
      AND f.metric_date >= CURRENT_DATE - INTERVAL '90 days'
      AND f.client_id IS NOT NULL
    GROUP BY f.client_id, f.client_name, f.client_group_id, f.client_group_cn
    ORDER BY rp_click_pv DESC, funnel_pv DESC
    LIMIT {limit}
    """


def sql_clients_by_search(events: str, users: str, dest_clause_search: str, limit: int) -> str:
    """圈客补充：近90天搜索行为（event_properties_json.search_des_query）。"""
    return f"""
    SELECT DISTINCT
        u.client_id,
        u.client_group_id,
        COUNT(*) AS search_cnt
    FROM {events} e
    JOIN {users} u ON e.user_id = u.user_id
    WHERE e.event_type IN ('search_des_sugg_click', 'hotel_find_search')
      AND e.event_date >= CURRENT_DATE - INTERVAL '90 days'
      AND (
        e.event_properties_json::jsonb ->> 'search_des_query' ILIKE ANY (ARRAY[{dest_clause_search}])
        OR e.event_properties_json::jsonb ->> 'dida_region_id' IS NOT NULL
      )
      AND u.client_id IS NOT NULL
    GROUP BY u.client_id, u.client_group_id
    ORDER BY search_cnt DESC
    LIMIT {limit}
    """


def sql_hotels_by_destination(funnel: str, dest_clause: str, limit: int) -> str:
    """选品：按目的地漏斗曝光/点击排序的热门酒店。"""
    return f"""
    SELECT
        f.standard_hotel_id,
        MAX(f.dida_hotel_name) AS dida_hotel_name,
        MAX(f.country_name) AS country_name,
        MAX(f.city_name) AS city_name,
        MAX(f.star_rating) AS star_rating,
        MAX(f.brand_name) AS brand_name,
        COUNT(DISTINCT CASE WHEN f.step_code IN ('expose', 'available') THEN f.pv_key END) AS expose_cnt,
        COUNT(DISTINCT CASE WHEN f.step_code = 'click' THEN f.pv_key END) AS click_cnt
    FROM {funnel} f
    WHERE {dest_clause}
      AND (f.is_test_account IS NULL OR f.is_test_account = false)
      AND f.metric_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY f.standard_hotel_id
    HAVING expose_cnt > 0
    ORDER BY click_cnt DESC, expose_cnt DESC
    LIMIT {limit}
    """


def sql_hotel_prices(events: str, hotel_id: int | str, limit: int) -> str:
    """比价：从 RP 曝光埋点取 quote_price。"""
    return f"""
    SELECT
        (e.event_properties_json::jsonb ->> 'dida_hotel_id') AS dida_hotel_id,
        (e.event_properties_json::jsonb ->> 'quote_price')::numeric AS quote_price,
        e.event_properties_json::jsonb ->> 'quote_currency' AS quote_currency,
        (e.event_properties_json::jsonb ->> 'supplier_id') AS supplier_id,
        e.event_time
    FROM {events} e
    WHERE e.event_type = 'hotel_detail_rp_expose'
      AND (e.event_properties_json::jsonb ->> 'dida_hotel_id') = '{hotel_id}'
      AND (e.event_properties_json::jsonb ->> 'quote_price') IS NOT NULL
    ORDER BY e.event_time DESC
    LIMIT {limit}
    """


def sql_funnel_by_destination(funnel: str, dest_clause: str) -> str:
    """漏斗转化：按 step 聚合。"""
    return f"""
    SELECT
        f.step_code,
        MAX(f.step_name) AS step_name,
        MAX(f.step_no) AS step_no,
        COUNT(DISTINCT f.pv_key) AS cnt
    FROM {funnel} f
    WHERE {dest_clause}
      AND (f.is_test_account IS NULL OR f.is_test_account = false)
      AND f.metric_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY f.step_code
    ORDER BY step_no
    """
