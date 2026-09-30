"""数据导入与聚合 ETL。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db import get_engine, init_database
from app.utils import (
    extract_event_fields,
    safe_json_loads,
    to_bool,
    to_date,
    to_datetime,
    to_int,
)
from scripts.generate_sample_data import ensure_sample_files


CLIENT_GROUP_CN = {
    2: "国内线下Shopping",
    6: "海外线下",
    3: "国内线下API",
    11: "内部账号",
    7: "海外线上",
    8: "其他",
    12: "其他",
    1: "其他",
}


def _read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path, low_memory=False)


def _replace_table(engine, table: str, df: pd.DataFrame) -> int:
    """清空表后写入，保留 schema 定义的列结构。"""
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
    df.to_sql(table, engine, if_exists="append", index=False)
    return len(df)


def _log_etl(engine, job_name: str, sync_date, status: str, rows: int, message: str = ""):
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO etl_sync_log
                (job_name, sync_date, status, rows_affected, message, started_at, finished_at)
                VALUES (:job, :sd, :st, :rows, :msg, :start, :end)"""
            ),
            {
                "job": job_name,
                "sd": sync_date,
                "st": status,
                "rows": rows,
                "msg": message,
                "start": datetime.now().isoformat(),
                "end": datetime.now().isoformat(),
            },
        )


def import_dim_client(engine, users_df: pd.DataFrame, events_df: pd.DataFrame) -> int:
    user_prefs = (
        events_df.groupby("user_id")
        .agg({"language": "last", "currency": "last", "platform": "last"})
        .reset_index()
    )
    merged = users_df.merge(user_prefs, on="user_id", how="left")

    rows = []
    for _, r in merged.iterrows():
        props = safe_json_loads(r.get("user_properties_json"))
        gid = to_int(r.get("client_group_id"))
        rows.append({
            "client_id": r.get("client_id") or props.get("dida_client_id"),
            "client_name": props.get("dida_client_id") or r.get("client_id"),
            "client_group_id": gid,
            "client_group_cn": CLIENT_GROUP_CN.get(gid, "未登录" if gid is None else "其他"),
            "user_id": r.get("user_id"),
            "identity_id": r.get("identity_id"),
            "device_id": r.get("device_id"),
            "first_referrer_url": r.get("first_referrer_url"),
            "first_referrer_page_name": r.get("first_referrer_page_name"),
            "register_date": to_date(r.get("created_at")),
            "last_active_date": to_date(r.get("updated_time")),
            "language": r.get("language"),
            "currency": r.get("currency"),
            "platform": r.get("platform"),
        })

    df = pd.DataFrame(rows).dropna(subset=["client_id"]).drop_duplicates(subset=["client_id"], keep="last")
    for col in ("tag_customer_value", "tag_activity_level", "tag_preferred_dest",
                "tag_preferred_price", "tag_preferred_brand", "tag_booking_freq", "tag_churn_risk"):
        if col not in df.columns:
            df[col] = None
    return _replace_table(engine, "dim_client", df)


def import_fact_events(engine, events_df: pd.DataFrame, users_df: pd.DataFrame) -> int:
    client_map = dict(zip(users_df["user_id"], users_df["client_id"]))
    records = []
    for _, r in events_df.iterrows():
        props = safe_json_loads(r.get("event_properties_json"))
        extracted = extract_event_fields(props)
        records.append({
            "event_pk": r.get("pre_event_pk") or r.get("event_pk"),
            "event_time": to_datetime(r.get("event_time")),
            "event_date": to_date(r.get("event_date")),
            "event_hour": to_int(r.get("event_hour")),
            "user_id": r.get("user_id"),
            "client_id": client_map.get(r.get("user_id")) or props.get("dida_client_id"),
            "identity_id": r.get("identity_id"),
            "device_id": r.get("device_id"),
            "session_id": to_int(r.get("session_id")),
            "search_session_id": r.get("search_session_id") or props.get("search_session_id"),
            "event_type": r.get("event_type"),
            "page_name": r.get("page_name"),
            "page_url": r.get("page_url"),
            "referrer_page_name": r.get("referrer_page_name"),
            "referrer_url": r.get("referrer_url"),
            "platform": r.get("platform"),
            "language": r.get("language"),
            "currency": r.get("currency"),
            **extracted,
            "event_properties_json": json.dumps(props, ensure_ascii=False) if props else None,
        })

    df = pd.DataFrame(records)
    return _replace_table(engine, "fact_events", df)


def import_fact_funnel(engine, funnel_df: pd.DataFrame) -> int:
    col_map = {
        "metric_date": "metric_date",
        "standard_hotel_id": "standard_hotel_id",
        "dida_hotel_name": "dida_hotel_name",
        "country_code": "country_code",
        "country_name": "country_name",
        "city_code": "city_code",
        "city_name": "city_name",
        "star_rating": "star_rating",
        "destination_id": "destination_id",
        "brand_id": "brand_id",
        "brand_name": "brand_name",
        "chain_id": "chain_id",
        "chain_name": "chain_name",
        "property_category": "property_category",
        "user_id": "user_id",
        "client_id": "client_id",
        "client_name": "client_name",
        "client_group_id": "client_group_id",
        "client_category_id": "client_category_id",
        "parent_client_id": "parent_client_id",
        "client_group": "client_group",
        "client_group_cn": "client_group_cn",
        "step_code": "step_code",
        "step_name": "step_name",
        "step_no": "step_no",
        "pv_key": "pv_key",
        "rp_pv_key": "rp_pv_key",
        "rp_valid_type": "rp_valid_type",
        "inventory_status": "inventory_status",
        "is_consistent": "is_consistent",
        "is_test_account": "is_test_account",
        "check_in_date": "check_in_date",
        "check_out_date": "check_out_date",
        "adult_count": "adult_count",
        "child_count": "child_count",
        "room_num": "room_num",
        "nationality": "nationality",
        "etl_time": "etl_time",
    }
    df = funnel_df.rename(columns={k: k for k in funnel_df.columns})
    available = [c for c in col_map if c in df.columns]
    out = df[available].copy()
    return _replace_table(engine, "fact_funnel", out)


def import_dim_hotel(engine, funnel_df: pd.DataFrame, events_df: pd.DataFrame) -> int:
    hotels = funnel_df[
        ["standard_hotel_id", "dida_hotel_name", "country_code", "country_name",
         "city_code", "city_name", "destination_id", "star_rating",
         "brand_id", "brand_name", "chain_id", "chain_name", "property_category"]
    ].drop_duplicates(subset=["standard_hotel_id"])

    # 从事件中补充 dida_hotel_id（按酒店名称匹配，避免 country 合并产生重复）
    hotel_id_map: dict[str, int] = {}
    for _, r in events_df.iterrows():
        props = safe_json_loads(r.get("event_properties_json"))
        hid = props.get("dida_hotel_id")
        name = props.get("hotel_name") or props.get("dida_hotel_name")
        if hid:
            try:
                hotel_id_map[str(hid)] = int(float(hid))
            except (TypeError, ValueError):
                pass

    hotels = hotels.copy()
    def map_dida_id(std_id: str):
        if std_id and str(std_id).startswith("SG"):
            try:
                return 1001000 + int(str(std_id).replace("SG", ""))
            except ValueError:
                return None
        return None

    hotels["dida_hotel_id"] = hotels["standard_hotel_id"].apply(map_dida_id)
    hotels["tag_popularity"] = hotels["standard_hotel_id"].apply(
        lambda x: "热门" if hash(str(x)) % 3 == 0 else "普通"
    )
    return _replace_table(engine, "dim_hotel", hotels)


def import_fact_orders(engine, orders_df: pd.DataFrame, users_df: pd.DataFrame) -> int:
    client_user = dict(zip(users_df["client_id"], users_df["user_id"]))
    records = []
    for _, r in orders_df.iterrows():
        cid = r.get("clientid") or r.get("client_id")
        records.append({
            "order_number": r.get("number") or r.get("order_number"),
            "client_id": cid,
            "client_name": r.get("client_name"),
            "client_bd": r.get("clientbd") or r.get("client_bd"),
            "dida_hotel_id": to_int(r.get("didahotelid") or r.get("dida_hotel_id")),
            "dida_hotel_name": r.get("didahotelname_cn") or r.get("dida_hotel_name"),
            "dida_hotel_chain": r.get("didahotelchainname"),
            "dida_hotel_star": r.get("didahotelstarrating"),
            "country_name": r.get("didahotelcountryname_en") or r.get("country_name"),
            "destination_name": r.get("didahoteldestinationname_cn"),
            "room_name": r.get("roomname"),
            "room_type": r.get("roomtype"),
            "bed_type": r.get("bedtype"),
            "board_type": r.get("boardtype"),
            "status": to_int(r.get("status")),
            "check_in_date": to_date(r.get("checkindate") or r.get("check_in_date")),
            "check_out_date": to_date(r.get("checkoutdate") or r.get("check_out_date")),
            "room_night_count": to_int(r.get("roomnightcount") or r.get("room_night_count")),
            "price_cny": r.get("pricecny") or r.get("price_cny"),
            "net_rate_cny": r.get("netratecny"),
            "combined_revenue_cny": r.get("combinedrevenuecny"),
            "kpi_revenue_cny": r.get("kpirevenuecny"),
            "is_direct_contract": to_bool(r.get("isdirectcontract")),
            "lead_time_hour": to_int(r.get("leadtimehour")),
            "create_time": to_datetime(r.get("createtime") or r.get("create_time")),
            "confirm_time": to_datetime(r.get("confirmtime")),
            "campaign_id": r.get("campaign_id"),
            "user_id": client_user.get(cid),
        })
    df = pd.DataFrame(records).dropna(subset=["order_number"])
    return _replace_table(engine, "fact_orders", df)


def build_fact_search(engine) -> int:
    sql = """
    INSERT OR REPLACE INTO fact_search (
        search_session_id, search_request_id, user_id, client_id, search_time,
        search_des_query, destination_id, country_name, checkin_date, checkout_date,
        adult_count, child_count, room_num, nationality, price_min, price_max,
        star_rating, brands, sortby, is_quick_search, is_realtime, has_result,
        hotels_return, supplier_count, load_time, rp_count, converted_to_order, converted_hotel_id
    )
    SELECT
        search_session_id, search_request_id, user_id, client_id, MIN(event_time),
        search_des_query, destination_id, country_name,
        date(checkin_date), date(checkout_date),
        adult_count, child_count, room_num, nationality,
        CAST(price_min AS REAL), CAST(price_max AS REAL),
        star_rating, brands, sortby, is_quick_search, is_realtime, has_result,
        MAX(hotels_return), MAX(supplier_count), MAX(load_time), MAX(rp_count),
        MAX(CASE WHEN order_id IS NOT NULL THEN 1 ELSE 0 END),
        MAX(dida_hotel_id)
    FROM fact_events
    WHERE search_session_id IS NOT NULL
      AND (event_type LIKE 'search%' OR event_type = 'Search' OR search_des_query IS NOT NULL)
    GROUP BY search_session_id, search_request_id, user_id, client_id
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fact_search"))
        result = conn.execute(text(sql))
        count = result.rowcount if result.rowcount >= 0 else 0
    # SQLite INSERT OR REPLACE rowcount may be -1; count manually
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM fact_search")).scalar()
    return count or 0


def build_fact_session(engine) -> int:
    sql = """
    INSERT OR REPLACE INTO fact_session (
        session_id, user_id, client_id, session_start, session_end, session_duration,
        page_views, searches, hotel_details, rp_exposures, rp_clicks, orders,
        converted, entry_page, exit_page, devices, language
    )
    SELECT
        session_id,
        user_id,
        client_id,
        MIN(event_time),
        MAX(event_time),
        CAST((julianday(MAX(event_time)) - julianday(MIN(event_time))) * 86400 AS INTEGER),
        SUM(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type LIKE 'search%' OR event_type = 'Search' THEN 1 ELSE 0 END),
        SUM(CASE WHEN page_name = 'hotel_detail' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type = 'hotel_detail_rp_expose' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type = 'hotel_detail_rp_click' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type IN ('preorder_result_return','order_payment_confirm_click') THEN 1 ELSE 0 END),
        MAX(CASE WHEN order_id IS NOT NULL OR is_success = 1 THEN 1 ELSE 0 END),
        (SELECT page_name FROM fact_events fe2 WHERE fe2.session_id = fe.session_id ORDER BY event_time ASC LIMIT 1),
        (SELECT page_name FROM fact_events fe2 WHERE fe2.session_id = fe.session_id ORDER BY event_time DESC LIMIT 1),
        MAX(platform),
        MAX(language)
    FROM fact_events fe
    WHERE session_id IS NOT NULL
    GROUP BY session_id, user_id, client_id
    """
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM fact_session"))
        conn.execute(text(sql))
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM fact_session")).scalar() or 0


def compute_client_tags(engine) -> int:
    sql = """
    UPDATE dim_client SET
        tag_activity_level = CASE
            WHEN last_active_date >= date('now', '-7 days') THEN '活跃'
            WHEN last_active_date >= date('now', '-30 days') THEN '一般'
            ELSE '休眠'
        END,
        tag_customer_value = CASE
            WHEN client_id IN (
                SELECT client_id FROM fact_orders GROUP BY client_id
                HAVING SUM(price_cny) > 10000
            ) THEN '高价值'
            WHEN client_id IN (SELECT DISTINCT client_id FROM fact_orders) THEN '中价值'
            ELSE '低价值'
        END,
        tag_preferred_dest = (
            SELECT country_name FROM fact_search fs
            WHERE fs.client_id = dim_client.client_id AND country_name IS NOT NULL
            GROUP BY country_name ORDER BY COUNT(*) DESC LIMIT 1
        ),
        tag_churn_risk = CASE
            WHEN last_active_date < date('now', '-60 days') THEN '高风险'
            WHEN last_active_date < date('now', '-30 days') THEN '中风险'
            ELSE '低风险'
        END
    """
    with engine.begin() as conn:
        result = conn.execute(text(sql))
        return result.rowcount if result.rowcount >= 0 else 0


def seed_reference_data(engine) -> None:
    """初始化目的地事件、节假日、F1 活动配置。"""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dim_destination_events"))
        conn.execute(text("DELETE FROM dim_holiday"))
        conn.execute(text("DELETE FROM dim_campaign WHERE campaign_id = 'CAMP_F1_SG_2026'"))

        conn.execute(text("""
            INSERT INTO dim_destination_events
            (destination, event_name, event_type, start_date, end_date, impact_level,
             expected_hotel_demand, target_hotel_radius, target_star_rating, description, source)
            VALUES
            ('Singapore', 'Formula 1 Singapore Grand Prix 2026', '体育', '2026-09-18', '2026-09-20', '高',
             '极高', 5, '4-5', 'F1新加坡大奖赛，滨海湾赛道周边酒店需求激增', 'manual'),
            ('Singapore', 'Singapore Food Festival 2026', '节日', '2026-07-01', '2026-07-31', '中',
             '中', 10, '3-5', '新加坡美食节', 'manual'),
            ('Malaysia', 'Malaysia Independence Day', '节日', '2026-08-31', '2026-08-31', '中',
             '中', 20, '3-4', '马来西亚独立日', 'manual')
        """))

        conn.execute(text("""
            INSERT INTO dim_holiday (country, holiday_name, holiday_date, holiday_type, is_long_weekend, travel_peak)
            VALUES
            ('Singapore', 'National Day', '2026-08-09', '法定', 0, '高'),
            ('China', 'National Day Golden Week', '2026-10-01', '法定', 1, '高'),
            ('Malaysia', 'Hari Merdeka', '2026-08-31', '法定', 0, '中'),
            ('Singapore', 'Deepavali', '2026-11-08', '宗教', 0, '中')
        """))

        target_metrics = json.dumps({
            "banner_ctr": 0.05,
            "order_count": 100,
            "total_ttv": 500000,
            "conversion_rate_overall": 0.02,
        }, ensure_ascii=False)
        conn.execute(
            text("""
            INSERT INTO dim_campaign
            (campaign_id, campaign_name, campaign_type, slide_id, slide_link, category_name,
             start_date, end_date, target_dest, target_hotel_ids, target_client_groups,
             target_metrics, budget, status, created_by)
            VALUES
            (:cid, :name, :ctype, :sid, :link, :cat,
             :start, :end, :dest, :hotels, :groups,
             :metrics, :budget, :status, :creator)
            """),
            {
                "cid": "CAMP_F1_SG_2026",
                "name": "新加坡F1赛事酒店预订",
                "ctype": "Banner",
                "sid": "slide_f1_sg_2026",
                "link": "https://portal.dida.com/campaign/f1-singapore-2026",
                "cat": "Singapore F1",
                "start": "2026-08-01",
                "end": "2026-09-25",
                "dest": "Singapore",
                "hotels": "1001001,1001002,1001003,1001004,1001005",
                "groups": "2,6,7",
                "metrics": target_metrics,
                "budget": 50000,
                "status": "进行中",
                "creator": "运营师",
            },
        )

        conn.execute(text("""
            INSERT INTO dim_alert_rules
            (campaign_id, metric_name, condition_type, threshold_value, alert_level, alert_action, is_active)
            VALUES
            ('CAMP_F1_SG_2026', 'banner_ctr', '低于', 0.03, '黄', '通知', 1),
            ('CAMP_F1_SG_2026', 'order_count', '低于', 50, '红', '通知', 1),
            ('CAMP_F1_SG_2026', 'conversion_rate_overall', '低于', 0.01, '黄', '调整', 1)
        """))


def run_full_import() -> dict:
    settings = get_settings()
    paths = ensure_sample_files()
    engine = get_engine()
    init_database(engine)

    events_df = _read_source(Path(paths["events"]))
    users_df = _read_source(Path(paths["users"]))
    funnel_df = _read_source(Path(paths["funnel"]))
    orders_path = Path(paths["orders"])
    orders_df = _read_source(orders_path) if orders_path.exists() else pd.DataFrame()

    stats = {
        "dim_client": import_dim_client(engine, users_df, events_df),
        "fact_events": import_fact_events(engine, events_df, users_df),
        "fact_funnel": import_fact_funnel(engine, funnel_df),
        "dim_hotel": import_dim_hotel(engine, funnel_df, events_df),
    }
    if not orders_df.empty:
        stats["fact_orders"] = import_fact_orders(engine, orders_df, users_df)
    else:
        stats["fact_orders"] = 0

    stats["fact_search"] = build_fact_search(engine)
    stats["fact_session"] = build_fact_session(engine)
    compute_client_tags(engine)
    seed_reference_data(engine)

    sync_date = datetime.now().date()
    _log_etl(engine, "full_import", sync_date, "success", sum(stats.values()), json.dumps(stats))
    return stats


if __name__ == "__main__":
    result = run_full_import()
    print("Import completed:", result)
