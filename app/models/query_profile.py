"""Agent1 → Agent2 圈客选品 Query Profile DSL（结构化交接契约）。"""

from __future__ import annotations

import json
import re
from typing import Any


def default_customer_query_profile(destination: str = "Singapore") -> dict[str, Any]:
    return {
        "destination": destination,
        "time_window_days": 90,
        "client_group_ids": [],
        "behavior_source": "funnel",
        "step_codes": ["request", "click"],
        "min_funnel_events": 1,
        "exclude_test_account": True,
        "client_limit": 200,
        "sort_by": "rp_click_pv_desc",
    }


def default_hotel_query_profile(destination: str = "Singapore") -> dict[str, Any]:
    return {
        "destination": destination,
        "time_window_days": 90,
        "star_min": 4,
        "price_min_cny": None,
        "price_max_cny": None,
        "sort_by": "click_cnt_desc",
        "hotel_limit": 20,
        "scope": "destination_hot",
        "keyword_boost": [],
    }


def parse_client_group_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(x) for x in value if str(x).strip().isdigit()]
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        return [int(x.strip()) for x in re.split(r"[,，\s]+", value) if x.strip().isdigit()]
    return []


def parse_price_range(price_range: str | None) -> tuple[int | None, int | None]:
    if not price_range:
        return None, None
    nums = [int(x) for x in re.findall(r"\d+", price_range)]
    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])
    if len(nums) == 1:
        return nums[0], None
    return None, None


def _load_structured(plan: dict) -> dict:
    raw = plan.get("plan_structured_json")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def sync_query_profiles(structured: dict) -> dict:
    """从 ⑥⑦ 扁平字段补全 query_profile（保存方案时调用）。"""
    basic = structured.get("basic") or {}
    cs = structured.get("customer_segment") or {}
    hs = structured.get("hotel_solution") or {}
    dest = basic.get("target_dest") or cs.get("geo_focus") or "Singapore"

    cqp = dict(default_customer_query_profile(dest))
    cqp.update(cs.get("query_profile") or {})
    cqp["destination"] = cqp.get("destination") or dest
    groups = parse_client_group_ids(cs.get("client_groups"))
    if groups:
        cqp["client_group_ids"] = groups
    cs["query_profile"] = cqp
    structured["customer_segment"] = cs

    hqp = dict(default_hotel_query_profile(dest))
    hqp.update(hs.get("query_profile") or {})
    hqp["destination"] = hqp.get("destination") or dest
    if hs.get("star_min"):
        try:
            hqp["star_min"] = int(str(hs["star_min"]).strip())
        except ValueError:
            pass
    pmin, pmax = parse_price_range(hs.get("price_range"))
    if pmin is not None:
        hqp["price_min_cny"] = hqp.get("price_min_cny") or pmin
    if pmax is not None:
        hqp["price_max_cny"] = hqp.get("price_max_cny") or pmax
    hs["query_profile"] = hqp
    structured["hotel_solution"] = hs
    return structured


def extract_query_profile_from_plan(plan: dict) -> dict[str, Any]:
    """从活动方案提取 Agent2 可执行的合并 Query Profile。"""
    structured = _load_structured(plan)
    if structured:
        structured = sync_query_profiles(structured)
        cs_qp = (structured.get("customer_segment") or {}).get("query_profile") or {}
        hs_qp = (structured.get("hotel_solution") or {}).get("query_profile") or {}
    else:
        dest = plan.get("target_dest") or "Singapore"
        cs_qp = default_customer_query_profile(dest)
        hs_qp = default_hotel_query_profile(dest)
        groups = parse_client_group_ids(plan.get("target_client_groups"))
        if groups:
            cs_qp["client_group_ids"] = groups

    dest = (
        cs_qp.get("destination")
        or hs_qp.get("destination")
        or plan.get("target_dest")
        or "Singapore"
    )
    merged: dict[str, Any] = {
        "destination": dest,
        "time_window_days": cs_qp.get("time_window_days") or hs_qp.get("time_window_days") or 90,
        "client_group_ids": cs_qp.get("client_group_ids") or [],
        "behavior_source": cs_qp.get("behavior_source") or "funnel",
        "step_codes": cs_qp.get("step_codes") or ["request", "click"],
        "min_funnel_events": cs_qp.get("min_funnel_events") or 1,
        "exclude_test_account": cs_qp.get("exclude_test_account", True),
        "client_limit": int(cs_qp.get("client_limit") or 200),
        "client_sort_by": cs_qp.get("sort_by") or "rp_click_pv_desc",
        "star_min": hs_qp.get("star_min"),
        "star_rating": hs_qp.get("star_min"),
        "price_min_cny": hs_qp.get("price_min_cny"),
        "price_max_cny": hs_qp.get("price_max_cny"),
        "hotel_limit": int(hs_qp.get("hotel_limit") or 20),
        "hotel_sort_by": hs_qp.get("sort_by") or "click_cnt_desc",
        "hotel_scope": hs_qp.get("scope") or "destination_hot",
        "keyword_boost": hs_qp.get("keyword_boost") or [],
        "selection_rationale": (structured.get("customer_segment") or {}).get("selection_rationale") if structured else "",
        "hotel_selection_strategy": (structured.get("hotel_solution") or {}).get("selection_strategy") if structured else "",
    }
    if isinstance(merged["client_group_ids"], str):
        merged["client_group_ids"] = parse_client_group_ids(merged["client_group_ids"])
    if not merged["client_group_ids"]:
        merged["client_group_ids"] = parse_client_group_ids(plan.get("target_client_groups"))
    return merged


def merge_profile_overrides(base: dict, overrides: dict | None) -> dict:
    if not overrides:
        return dict(base)
    out = dict(base)
    for k, v in overrides.items():
        if v is None:
            continue
        if k in ("client_group_ids", "client_groups") and isinstance(v, str):
            out["client_group_ids"] = parse_client_group_ids(v)
        else:
            out[k] = v
    if "star_rating" in out and out.get("star_min") is None:
        out["star_min"] = out["star_rating"]
    return out


def validate_query_profile(profile: dict) -> list[str]:
    """返回缺失的必填项（空列表表示可执行）。"""
    missing: list[str] = []
    if not profile.get("destination"):
        missing.append("destination")
    if not profile.get("time_window_days"):
        missing.append("time_window_days")
    if not profile.get("client_group_ids"):
        missing.append("client_group_ids")
    if not profile.get("behavior_source"):
        missing.append("behavior_source")
    if not profile.get("client_limit"):
        missing.append("client_limit")
    if profile.get("star_min") is None and profile.get("star_rating") is None:
        missing.append("star_min")
    if not profile.get("hotel_limit"):
        missing.append("hotel_limit")
    return missing


def build_selection_reason(profile: dict, client_count: int, hotel_count: int) -> str:
    groups = profile.get("client_group_ids") or []
    gtxt = ",".join(str(g) for g in groups) if groups else "全部"
    steps = profile.get("step_codes") or ["request", "click"]
    return (
        f"{profile.get('destination')} · 近{profile.get('time_window_days', 90)}天 · "
        f"分组[{gtxt}] · funnel步骤{steps} · 圈客{client_count} · 选品{hotel_count} · "
        f"星级≥{profile.get('star_min') or profile.get('star_rating') or '—'}"
    )
