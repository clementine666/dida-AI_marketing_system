"""全年营销日历导出 · 标准+创意字段并集（标准活动创意专属列留空）。"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.services.v2.agent1_planner import PlannerService

# 与 ui/dashboard/agent1_fields.js 对齐：STANDARD + CREATIVE 字段并集（按 key 去重）
EXPORT_COLUMNS: list[dict[str, str]] = [
    {"key": "session_group", "label": "活动场次", "path": "basic.session_group"},
    {"key": "activity_type", "label": "活动类型", "path": "basic.activity_type"},
    {"key": "main_theme", "label": "月度主活动主题", "path": "strategy.main_theme"},
    {"key": "theme_name", "label": "活动主题名称", "path": "basic.campaign_name"},
    {"key": "sub_theme", "label": "副活动主题（活动名称）", "path": "basic.campaign_name"},
    {"key": "theme_keyword", "label": "活动主题词", "path": "strategy.theme_keyword"},
    {"key": "sub_theme_pack", "label": "副主题包装说明", "path": "strategy.sub_theme_pack"},
    {"key": "demand_bg", "label": "需求背景", "path": "background.demand_bg"},
    {"key": "business_opportunity", "label": "业务契机", "path": "background.business_opportunity"},
    {"key": "data_insight", "label": "数据分析洞察", "path": "data_insights.summary"},
    {"key": "opportunity_judge", "label": "机会判断", "path": "data_insights.opportunity_judge"},
    {"key": "customer_profile", "label": "客户群体画像", "path": "customer_segment.profile"},
    {"key": "demand_scale", "label": "需求规模", "path": "data_insights.demand_scale"},
    {"key": "activity_creative", "label": "活动创意（玩法/形式）", "path": "strategy.playbook"},
    {"key": "target_goal", "label": "目标设定（TTV/GP/转化）", "path": "objectives.primary_goal"},
    {"key": "continent", "label": "目的地归属（大洲）", "path": "basic.continent"},
    {"key": "country", "label": "国家/地区", "path": "basic.country_region"},
    {"key": "city", "label": "城市", "path": "basic.city"},
    {"key": "district", "label": "热门商圈", "path": "basic.district"},
    {"key": "promotion_window", "label": "推广月份（对应出游/离店窗口）", "path": "basic.promotion_window"},
    {"key": "p75_days", "label": "关键P75（目标离店月·天）", "path": "basic.p75_days"},
    {"key": "selection_reason", "label": "选择理由", "path": "data_insights.selection_reason"},
    {"key": "tuesday_sort", "label": "场内周二排序依据", "path": "strategy.tuesday_sort"},
    {"key": "hotel_profile", "label": "酒店产品画像", "path": "hotel_solution.criteria"},
    {"key": "resource_handoff", "label": "资源对接时间", "path": "schedule.resource_handoff"},
    {"key": "resource_delivery", "label": "资源交付时间（T-30）", "path": "schedule.resource_delivery"},
    {"key": "material_done", "label": "营销物料制作完成时间（T-14）", "path": "schedule.material_done"},
    {"key": "launch_position", "label": "上线位置", "path": "strategy.launch_position"},
    {"key": "launch_date", "label": "活动上线时间（周二）", "path": "schedule.launch_date"},
    {"key": "promotion_period", "label": "活动推广时间（起止区间）", "path": "schedule.promotion_period"},
    {"key": "review_date", "label": "活动复盘时间", "path": "schedule.review_date"},
]

# 标准活动不填写的创意专属列
CREATIVE_ONLY_KEYS = {
    "demand_bg", "business_opportunity", "data_insight", "opportunity_judge",
    "customer_profile", "demand_scale", "activity_creative", "target_goal", "hotel_profile",
}


def _get_nested(obj: dict, path: str) -> str:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    if cur is None:
        return ""
    if isinstance(cur, (list, dict)):
        return str(cur)
    return str(cur).strip()


def _month_sort_key(promotion_month: str | None) -> tuple[int, str]:
    if not promotion_month:
        return (99, "")
    m = re.search(r"(\d{1,2})", str(promotion_month))
    if m:
        return (int(m.group(1)), str(promotion_month))
    return (99, str(promotion_month))


def _is_standard_activity(row: dict, structured: dict) -> bool:
    atype = _get_nested(structured, "basic.activity_type") or row.get("activity_type") or ""
    if atype in ("AI创意",):
        return False
    if atype in ("其他",):
        return False
    if "创意" in str(atype):
        return False
    return True


def _enrich_structured(row: dict, structured: dict) -> dict:
    """从扁平行补全结构化字段（导出时尽量有值）。"""
    basic = structured.setdefault("basic", {})
    strat = structured.setdefault("strategy", {})
    sched = structured.setdefault("schedule", {})
    data = structured.setdefault("data_insights", {})
    bg = structured.setdefault("background", {})

    if not basic.get("campaign_name") and row.get("campaign_name"):
        basic["campaign_name"] = row["campaign_name"]
    if not basic.get("promotion_month") and row.get("promotion_month"):
        basic["promotion_month"] = row["promotion_month"]
        basic.setdefault("promotion_window", row["promotion_month"])
    if not basic.get("target_dest") and row.get("target_dest"):
        basic["target_dest"] = row["target_dest"]
    if not basic.get("country_region") and row.get("destination_region"):
        basic["country_region"] = row["destination_region"]
    if not basic.get("activity_type"):
        basic["activity_type"] = row.get("activity_type") or row.get("campaign_type") or "人工标准"
    if not strat.get("theme_keyword") and row.get("theme_keyword"):
        strat["theme_keyword"] = row["theme_keyword"]
    if not data.get("selection_reason") and row.get("demand_analysis"):
        data["selection_reason"] = row["demand_analysis"]
    if not bg.get("demand_bg") and row.get("plan_summary"):
        bg["demand_bg"] = row["plan_summary"]
    if not sched.get("launch_date") and row.get("launch_date"):
        sched["launch_date"] = str(row["launch_date"])
    if not sched.get("launch_date") and row.get("start_date"):
        sched["launch_date"] = str(row["start_date"])
    return structured


def build_export_rows(planner: PlannerService | None = None) -> list[dict[str, str]]:
    planner = planner or PlannerService()
    ws = planner.build_marketing_workspace()
    activities = list(ws.get("human_calendar", {}).get("full_year") or [])
    activities.sort(key=lambda r: (_month_sort_key(r.get("promotion_month")), r.get("campaign_name") or ""))

    rows: list[dict[str, str]] = []
    for row in activities:
        structured = planner.build_structured_plan(row)
        structured = _enrich_structured(row, structured)
        is_std = _is_standard_activity(row, structured)

        out: dict[str, str] = {"campaign_id": row.get("campaign_id") or ""}
        for col in EXPORT_COLUMNS:
            val = _get_nested(structured, col["path"])
            if col["key"] == "main_theme" and not val:
                val = _get_nested(structured, "strategy.main_theme") or _get_nested(structured, "strategy.theme")
            if col["key"] == "theme_name" and is_std:
                val = val or _get_nested(structured, "basic.campaign_name")
            if is_std and col["key"] in CREATIVE_ONLY_KEYS:
                val = ""
            out[col["label"]] = val
        rows.append(out)
    return rows


def export_annual_calendar_csv(planner: PlannerService | None = None) -> tuple[str, str]:
    """返回 (filename, csv_text_utf8_sig)。"""
    rows = build_export_rows(planner)
    from datetime import date

    year = date.today().year
    filename = f"营销日历_{year}全年.csv"

    buf = io.StringIO()
    headers = ["campaign_id"] + [c["label"] for c in EXPORT_COLUMNS]
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return filename, buf.getvalue()
