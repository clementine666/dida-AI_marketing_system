"""JSON 字段解析与类型转换工具。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def safe_json_loads(value: Any) -> dict:
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value or value in ("\\N", "null", "None"):
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def get_prop(props: dict, key: str, default=None):
    val = props.get(key, default)
    if val in (None, "", "\\N", "null"):
        return default
    return val


def to_bool(val: Any) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def to_int(val: Any) -> int | None:
    if val is None or val == "" or val == "\\N":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def to_float(val: Any) -> float | None:
    if val is None or val == "" or val == "\\N":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def to_date(val: Any) -> date | None:
    if val is None or val == "" or val == "\\N":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val)[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_datetime(val: Any) -> datetime | None:
    if val is None or val == "" or val == "\\N":
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# event_properties_json 中需要提取到 fact_events 独立列的字段
EVENT_JSON_FIELDS = [
    "dida_hotel_id", "dida_rpid", "room_type", "room_type_name", "bed_type", "meal_type",
    "quote_price", "quote_currency", "preorder_price", "preorder_id", "supplier_id",
    "rp_count", "supplier_count", "rp_area", "cancellation_policy", "check_type",
    "room_nights", "rank_no", "room_rank_no", "search_des_query", "search_request_id",
    "search_hoteldetail_request_id", "search_type", "is_quick_search", "is_realtime",
    "has_result", "load_time", "hotels_return", "filter_name", "sortby", "price_min",
    "price_max", "pricerange_min", "pricerange_max", "star_rating", "brands", "regions",
    "city_list", "nationality", "checkin_date", "checkout_date", "adult_count",
    "child_count", "room_num", "destination_id", "country_name", "slide_id", "slide_link",
    "category_name", "promotions", "coupon_amount", "order_id", "order_total_amount",
    "payment_method", "result_code", "result_msg", "result_status", "is_success",
    "stay_time", "exit_type", "button_name", "click_id", "home_card_id", "rec_request_id",
    "asso_dida_hotel_id",
]

INT_FIELDS = {
    "bed_type", "supplier_id", "rp_count", "supplier_count", "cancellation_policy",
    "room_nights", "rank_no", "room_rank_no", "load_time", "hotels_return",
    "pricerange_min", "pricerange_max", "adult_count", "child_count", "room_num", "stay_time",
}
FLOAT_FIELDS = {"quote_price", "coupon_amount", "order_total_amount"}
BOOL_FIELDS = {"is_quick_search", "is_realtime", "has_result", "is_success"}
BIGINT_FIELDS = {"dida_hotel_id", "room_type", "asso_dida_hotel_id"}


def extract_event_fields(props: dict) -> dict:
    row: dict[str, Any] = {}
    for key in EVENT_JSON_FIELDS:
        raw = get_prop(props, key)
        if key in INT_FIELDS:
            row[key] = to_int(raw)
        elif key in FLOAT_FIELDS:
            row[key] = to_float(raw)
        elif key in BOOL_FIELDS:
            row[key] = to_bool(raw)
        elif key in BIGINT_FIELDS:
            v = to_int(raw)
            row[key] = v
        else:
            row[key] = None if raw is None else str(raw)
    return row
