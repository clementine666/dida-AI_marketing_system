"""模拟样本数据生成器（当原始 Excel/CSV 不可用时使用）。"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

import pandas as pd

from app.config import get_settings

CLIENT_GROUPS = {
    2: ("Domestic Offline Shopping", "国内线下Shopping"),
    6: ("Overseas Offline", "海外线下"),
    3: ("Domestic Offline API", "国内线下API"),
    11: ("Internal Account", "内部账号"),
    7: ("Overseas Online", "海外线上"),
}

EVENT_TYPES_WEIGHTS = [
    ("hotel_detail_rp_expose", 2682),
    ("page_leave", 1429),
    ("search_des_sugg_expose", 730),
    ("page_view", 409),
    ("search_hoteldetail_result_return", 377),
    ("search_hoteldetail_request", 374),
    ("search_enter", 257),
    ("search_des_sugg_result_return", 245),
    ("Search", 242),
    ("search_des_sugg_request", 238),
    ("primary_banner_expose", 120),
    ("primary_banner_click", 35),
    ("hotel_detail_rp_click", 80),
    ("preorder_result_return", 45),
    ("order_payment_confirm_click", 25),
]

FUNNEL_STEPS = [
    (1, "request", "酒店详情请求", 1052),
    (2, "available", "酒店详情有价返回", 891),
    (3, "expose", "酒店详情RP曝光", 7471),
    (4, "click", "酒店详情RP点击", 148),
    (5, "prebook", "preorder结果返回", 133),
    (6, "click_payment", "点击下一步支付", 51),
    (7, "payment_return", "下一步支付返回", 52),
    (8, "prebook_total", "Shopping所有订单结果返回", 54),
    (9, "prebook_success", "Shopping成功订单结果返回", 53),
    (10, "booking_with_fail", "Booking含失败", 37),
    (11, "booking_valid", "Booking确认+取消", 58),
]

DESTINATIONS = [
    ("Singapore", "Singapore", "SG"),
    ("Malaysia", "Kuala Lumpur", "MY"),
    ("Thailand", "Bangkok", "TH"),
    ("Indonesia", "Bali", "ID"),
    ("Japan", "Tokyo", "JP"),
    ("United Arab Emirates", "Dubai", "AE"),
    ("Hong Kong", "Hong Kong", "HK"),
    ("Mexico", "Cancun", "MX"),
    ("South Korea", "Seoul", "KR"),
]

HOTELS_SG_F1 = [
    ("SG001", 1001001, "Marina Bay Sands", "Singapore", "Singapore", "5"),
    ("SG002", 1001002, "The Fullerton Hotel Singapore", "Singapore", "Singapore", "5"),
    ("SG003", 1001003, "Pan Pacific Singapore", "Singapore", "Singapore", "5"),
    ("SG004", 1001004, "Swissotel The Stamford", "Singapore", "Singapore", "5"),
    ("SG005", 1001005, "Parkroyal Collection Marina Bay", "Singapore", "Singapore", "4"),
]


def _weighted_choice(items):
    total = sum(w for _, w in items)
    r = random.randint(1, total)
    acc = 0
    for val, w in items:
        acc += w
        if r <= acc:
            return val
    return items[0][0]


def generate_users(n: int = 10000) -> pd.DataFrame:
    rows = []
    group_ids = list(CLIENT_GROUPS.keys()) + [8, 12, 1, None]
    group_weights = [508, 189, 63, 52, 31, 15, 2, 1, 138]
    base_time = datetime(2026, 6, 1)

    for i in range(n):
        gid = random.choices(group_ids, weights=group_weights, k=1)[0]
        user_id = f"u_{10000 + i}"
        client_id = f"c_{5000 + (i % 5449)}"
        props = {"dida_client_id": client_id, "dida_client_group_id": gid}
        rows.append({
            "identity_id": str(uuid.uuid4()),
            "user_id": user_id,
            "device_id": f"d_{9000 + (i % 927)}",
            "schema_version": 1,
            "updated_time": (base_time + timedelta(days=random.randint(0, 60))).isoformat(),
            "first_referrer_url": "https://portal.dida.com/",
            "first_referrer_page_name": "home",
            "user_properties_json": json.dumps(props),
            "groups_json": "{}",
            "created_at": (base_time - timedelta(days=random.randint(30, 365))).isoformat(),
            "modified_at": datetime.now().isoformat(),
            "client_id": client_id if gid else None,
            "client_group_id": gid,
        })
    return pd.DataFrame(rows)


def generate_events(users: pd.DataFrame, n: int = 10000) -> pd.DataFrame:
    rows = []
    user_ids = users["user_id"].tolist()
    client_map = dict(zip(users["user_id"], users["client_id"]))
    base_time = datetime(2026, 7, 1)

    for i in range(n):
        user_id = random.choice(user_ids)
        dest = random.choice(DESTINATIONS)
        country, city, _ = dest
        hotel = random.choice(HOTELS_SG_F1 if country == "Singapore" else [
            ("H001", 2001001, f"Hotel {city}", country, city, "4")
        ])
        std_id, dida_id, hotel_name, _, city_name, star = hotel
        et = _weighted_choice(EVENT_TYPES_WEIGHTS)
        t = base_time + timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

        props = {
            "dida_hotel_id": dida_id,
            "search_des_query": city_name if "search" in et.lower() else None,
            "country_name": country,
            "quote_price": round(random.uniform(80, 800), 2),
            "quote_currency": "CNY",
            "star_rating": star,
            "room_nights": random.randint(1, 5),
            "load_time": random.randint(200, 3000),
            "has_result": True,
            "hotels_return": random.randint(5, 200),
            "stay_time": random.randint(1000, 120000),
        }
        if et in ("primary_banner_expose", "primary_banner_click"):
            props.update({
                "slide_id": "slide_f1_sg_2026",
                "slide_link": "https://portal.dida.com/campaign/f1-singapore-2026",
                "category_name": "Singapore F1",
            })
        if "rp" in et:
            props.update({
                "dida_rpid": f"rp_{dida_id}_{random.randint(1, 5)}",
                "rp_count": random.randint(1, 20),
                "supplier_count": random.randint(1, 8),
            })

        rows.append({
            "pre_event_pk": f"evt_{uuid.uuid4().hex[:16]}",
            "event_time": t.isoformat(),
            "server_time": t.isoformat(),
            "event_date": t.date().isoformat(),
            "event_month": t.strftime("%Y-%m"),
            "event_hour": t.hour,
            "event_type": et,
            "insert_id": str(uuid.uuid4()),
            "event_id": random.randint(1, 500),
            "created_at": t.isoformat(),
            "updated_at": t.isoformat(),
            "src_kafka_time": t.isoformat(),
            "user_id": user_id,
            "device_id": f"d_{random.randint(9000, 9926)}",
            "identity_id": str(uuid.uuid4()),
            "gaid": None,
            "session_id": random.randint(100000, 999999),
            "search_session_id": f"ss_{random.randint(10000, 99999)}",
            "page_url": f"https://portal.dida.com/hotel/{dida_id}",
            "page_name": "hotel_detail" if "hotel" in et else "home",
            "referrer_url": "https://portal.dida.com/",
            "referrer_page_name": "home",
            "user_agent": "Mozilla/5.0",
            "platform": "Web",
            "os_name": "Windows",
            "os_version": "10",
            "browser": "Chrome",
            "browser_version": "120",
            "language": random.choice(["zh-CN", "en-US", "ja-JP", "ko-KR"]),
            "currency": "CNY",
            "country": country,
            "region": city_name,
            "city": city_name,
            "event_properties_json": json.dumps({k: v for k, v in props.items() if v is not None}),
            "user_properties_json": json.dumps({"dida_client_id": client_map.get(user_id)}),
            "groups_json": "{}",
        })
    return pd.DataFrame(rows)


def generate_funnel(users: pd.DataFrame, n: int = 10000) -> pd.DataFrame:
    rows = []
    user_ids = users["user_id"].tolist()
    client_ids = users["client_id"].tolist()
    base_date = datetime(2026, 7, 1).date()

    step_pool = []
    for step_no, step_code, step_name, count in FUNNEL_STEPS:
        step_pool.extend([(step_no, step_code, step_name)] * count)
    random.shuffle(step_pool)
    step_pool = step_pool[:n]

    for i, (step_no, step_code, step_name) in enumerate(step_pool):
        user_id = random.choice(user_ids)
        idx = user_ids.index(user_id)
        client_id = client_ids[idx]
        gid = users.iloc[idx]["client_group_id"]
        group_en, group_cn = CLIENT_GROUPS.get(gid, ("Other", "其他"))
        dest = random.choice(DESTINATIONS)
        country, city, cc = dest
        hotel = random.choice(HOTELS_SG_F1 if country == "Singapore" else [
            ("H001", 2001001, f"Hotel {city}", country, city, "4", "BrandA", "ChainA")
        ])
        if len(hotel) == 6:
            std_id, dida_id, name, c, city_name, star = hotel
            brand, chain = "Luxury", "Global Chain"
        else:
            std_id, dida_id, name, c, city_name, star, brand, chain = hotel

        ci = base_date + timedelta(days=random.randint(30, 120))
        co = ci + timedelta(days=random.randint(1, 5))
        rows.append({
            "metric_date": (base_date + timedelta(days=random.randint(0, 30))).isoformat(),
            "standard_hotel_id": std_id,
            "dida_hotel_name": name,
            "country_code": cc,
            "country_name": country,
            "city_code": city_name[:3].upper(),
            "city_name": city_name,
            "star_rating": star,
            "destination_id": f"dest_{cc}",
            "brand_id": "b001",
            "brand_name": brand,
            "chain_id": "ch001",
            "chain_name": chain,
            "property_category": "Hotel",
            "user_id": user_id,
            "client_id": client_id,
            "client_name": f"Client_{client_id}",
            "client_group_id": gid,
            "client_category_id": 1,
            "parent_client_id": None,
            "client_group": group_en,
            "client_group_cn": group_cn,
            "step_code": step_code,
            "step_name": step_name,
            "step_no": step_no,
            "pv_key": f"pv_{uuid.uuid4().hex[:12]}",
            "rp_pv_key": f"rpv_{uuid.uuid4().hex[:12]}",
            "rp_valid_type": random.choice(["valid", "invalid", None]),
            "inventory_status": random.choice(["available", "sold_out", "limited"]),
            "is_consistent": random.choice(["Y", "N"]),
            "is_test_account": False,
            "check_in_date": ci.isoformat(),
            "check_out_date": co.isoformat(),
            "adult_count": random.randint(1, 4),
            "child_count": random.randint(0, 2),
            "room_num": random.randint(1, 3),
            "nationality": random.choice(["CN", "SG", "MY", "US", "JP"]),
            "etl_time": datetime.now().isoformat(),
        })
    return pd.DataFrame(rows)


def generate_orders(users: pd.DataFrame, n: int = 500) -> pd.DataFrame:
    rows = []
    sg_users = users[users["client_group_id"].isin([2, 6, 7])].head(200)
    for i in range(n):
        u = sg_users.iloc[i % len(sg_users)] if len(sg_users) else users.iloc[i % len(users)]
        hotel = random.choice(HOTELS_SG_F1)
        _, dida_id, name, country, city, star = hotel
        ci = datetime(2026, 9, 15).date() + timedelta(days=random.randint(0, 10))
        co = ci + timedelta(days=random.randint(2, 4))
        rn = (co - ci).days
        price = round(random.uniform(500, 5000), 2)
        rows.append({
            "number": f"ORD{2026090000 + i}",
            "clientid": u["client_id"],
            "clientbd": "BD_A",
            "didahotelid": dida_id,
            "didahotelname_cn": name,
            "didahotelcountryname_en": country,
            "didahoteldestinationname_cn": city,
            "didahotelstarrating": star,
            "didahotelchainname": "Global Chain",
            "roomname": "Deluxe Room",
            "roomtype": "Standard",
            "bedtype": "King",
            "boardtype": "Breakfast",
            "status": 1,
            "checkindate": ci.isoformat(),
            "checkoutdate": co.isoformat(),
            "roomnightcount": rn,
            "pricecny": price,
            "netratecny": round(price * 0.85, 2),
            "combinedrevenuecny": round(price * 0.15, 2),
            "kpirevenuecny": round(price * 0.12, 2),
            "isdirectcontract": random.choice([True, False]),
            "leadtimehour": random.randint(24, 720),
            "createtime": datetime(2026, 8, 1, random.randint(0, 23)).isoformat(),
            "confirmtime": datetime(2026, 8, 2).isoformat(),
            "campaign_id": "CAMP_F1_SG_2026" if country == "Singapore" and random.random() > 0.5 else None,
        })
    return pd.DataFrame(rows)


def ensure_sample_files() -> dict[str, str]:
    settings = get_settings()
    paths = {
        "events": settings.resolve_path(settings.events_file),
        "users": settings.resolve_path(settings.users_file),
        "funnel": settings.resolve_path(settings.funnel_file),
        "orders": settings.resolve_path(settings.orders_file),
    }
    if all(p.exists() for p in paths.values()):
        return {k: str(v) for k, v in paths.items()}

    if not settings.generate_sample_if_missing:
        missing = [str(p) for p in paths.values() if not p.exists()]
        raise FileNotFoundError(f"样本数据文件不存在: {missing}")

    n = settings.sample_size
    users = generate_users(n)
    events = generate_events(users, n)
    funnel = generate_funnel(users, n)
    orders = generate_orders(users, min(500, n // 20))

    users.to_csv(paths["users"], index=False, encoding="utf-8-sig")
    events.to_csv(paths["events"], index=False, encoding="utf-8-sig")
    funnel.to_csv(paths["funnel"], index=False, encoding="utf-8-sig")
    orders.to_csv(paths["orders"], index=False, encoding="utf-8-sig")
    return {k: str(v) for k, v in paths.items()}
