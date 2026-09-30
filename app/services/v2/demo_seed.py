"""演示数据：2027 全年计划池 + 活动建档日历样例。"""

from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import text

from app.db import get_engine
from app.models.campaign_plan_schema import default_plan, ensure_task_board, sync_schedule_dates
from app.models.lifecycle import LifecycleStatus
from app.models.planner import ADOPTION_ADOPTED, PLAN_SOURCE_AI, PLAN_SOURCE_HUMAN
from app.services.v2.agent1_planner import PlannerService
from app.services.v2.homepage_metrics import is_adopted

# 2027 演示活动清单（全年计划池 + 建档日历共用）
DEMO_CALENDAR_2027: list[dict] = [
    {
        "id": "CAMP_DEMO_202701_滑雪季",
        "name": "北海道滑雪季·早鸟预售",
        "type": "人工标准",
        "theme": "滑雪季与暖冬海岛",
        "dest": "日本·北海道",
        "launch": "2027-01-12",
        "travel": "2027-02",
        "source": PLAN_SOURCE_HUMAN,
    },
    {
        "id": "CAMP_DEMO_202703_樱花季",
        "name": "日本樱花季·关西专线",
        "type": "人工标准",
        "theme": "樱花季与展会季",
        "dest": "日本·京都/大阪",
        "launch": "2027-03-09",
        "travel": "2027-04",
        "source": PLAN_SOURCE_HUMAN,
    },
    {
        "id": "CAMP_DEMO_202705_欧洲早鸟",
        "name": "欧洲暑期·早鸟锁价",
        "type": "AI创意",
        "theme": "五一与欧洲早鸟",
        "dest": "法国·巴黎",
        "launch": "2027-05-11",
        "travel": "2027-07",
        "source": PLAN_SOURCE_AI,
    },
    {
        "id": "CAMP_DEMO_202706_毕业季",
        "name": "毕业季·青春出行专场",
        "type": "AI创意",
        "theme": "暑期预售与毕业季",
        "dest": "泰国·曼谷",
        "launch": "2027-06-08",
        "travel": "2027-07",
        "source": PLAN_SOURCE_AI,
    },
    {
        "id": "CAMP_DEMO_202709_国庆冲刺",
        "name": "国庆出境·东南亚精选",
        "type": "人工标准",
        "theme": "国庆冲刺与啤酒节",
        "dest": "新加坡",
        "launch": "2027-09-14",
        "travel": "2027-10",
        "source": PLAN_SOURCE_HUMAN,
    },
    {
        "id": "CAMP_DEMO_202709_会展季",
        "name": "广交会配套·商务酒店包",
        "type": "其他",
        "theme": "会展商务配套",
        "dest": "中国·广州",
        "launch": "2027-09-21",
        "travel": "2027-10",
        "source": "temp_entry",
    },
    {
        "id": "CAMP_DEMO_202710_日本赏枫",
        "name": "日本关西赏枫·晚秋特惠",
        "type": "人工标准",
        "theme": "国庆冲刺与赏枫",
        "dest": "日本·京都/大阪",
        "launch": "2027-10-13",
        "travel": "2027-11",
        "source": PLAN_SOURCE_HUMAN,
    },
    {
        "id": "CAMP_DEMO_202711_双11",
        "name": "双11·Global Travel Day",
        "type": "人工标准",
        "theme": "双11与滑雪早鸟",
        "dest": "全球多目的地",
        "launch": "2027-11-09",
        "travel": "2027-12",
        "source": PLAN_SOURCE_HUMAN,
    },
    {
        "id": "CAMP_DEMO_202712_圣诞跨年",
        "name": "圣诞跨年·海岛暖冬",
        "type": "AI创意",
        "theme": "圣诞跨年与2028规划",
        "dest": "马尔代夫",
        "launch": "2027-12-07",
        "travel": "2028-01",
        "source": PLAN_SOURCE_AI,
    },
]


def _tuesday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() - 1) % 7)


def _build_structured(spec: dict) -> dict:
    launch = date.fromisoformat(spec["launch"])
    end = launch + timedelta(days=45)
    plan_source = spec.get("source") or PLAN_SOURCE_HUMAN
    plan = default_plan(spec["dest"], plan_source=plan_source)
    is_creative = spec["type"] == "AI创意"
    is_other = spec["type"] == "其他"

    plan["source"].update({
        "plan_source": plan_source,
        "source_detail": "2027 演示数据 · 全年计划池/建档日历",
        "owner": "石军军",
        "priority": "P1",
    })
    plan["basic"].update({
        "campaign_name": spec["name"],
        "activity_type": spec["type"],
        "campaign_type": "Coupon" if is_creative else "Banner",
        "session_group": f"2027年{launch.month}月演示场",
        "target_dest": spec["dest"],
        "promotion_month": f"2027-{launch.month:02d}",
        "promotion_window": spec["travel"],
        "start_date": spec["launch"],
        "end_date": end.isoformat(),
    })
    if not is_other:
        plan["basic"].update({
            "continent": "亚洲" if "日本" in spec["dest"] or "中国" in spec["dest"] or "泰国" in spec["dest"] or "新加坡" in spec["dest"] else "欧洲",
            "country_region": spec["dest"].split("·")[-1] if "·" in spec["dest"] else spec["dest"],
        })
    plan["schedule"].update({
        "launch_date": spec["launch"],
        "promotion_period": f"{spec['launch']} ~ {end.isoformat()}",
        "resource_delivery": (launch + timedelta(days=-7)).isoformat(),
        "material_done": (launch + timedelta(days=-14)).isoformat(),
        "review_date": (end + timedelta(days=7)).isoformat(),
    })
    plan["strategy"].update({
        "main_theme": spec["theme"],
        "theme": spec["theme"],
        "launch_position": "官网 Banner + 活动专区",
        "placements": "首页 Banner、专题页",
        "material_needs": "Banner,海报,文案",
    })
    plan["background"]["summary"] = f"{spec['name']} — {spec['theme']}主题演示活动，用于全年计划池与建档档案字段展示。"
    plan["data_insights"]["selection_reason"] = f"演示数据：{spec['dest']} {spec['travel']} 离店窗口需求依据。"
    plan["objectives"].update({
        "primary_goal": "TTV 100-200万 · 订单 500+",
        "ttv_target": "100-200万",
        "order_target": "500",
        "process_metrics": "Banner CTR、专题页 CVR、订单/TTV",
        "success_criteria": "达成 TTV 目标且 CTR 不低于基线",
    })
    if is_creative:
        plan["background"]["demand_bg"] = "竞品已启动同类主题，需快速跟进创意玩法。"
        plan["background"]["business_opportunity"] = "窗口期 2-3 周，适合创意快启。"
        plan["strategy"]["playbook"] = "限时券 + 专题页组合玩法"
        plan["strategy"]["theme_keyword"] = spec["theme"][:6]
        plan["customer_segment"]["profile"] = "高活跃 B 端采购 · 近90天有搜索行为"
    if is_other:
        plan["background"]["summary"] = f"其他类型演示：{spec['name']}，字段可按需填写。"

    plan = sync_schedule_dates(plan)
    return ensure_task_board(plan)


def _upsert_demo_activity(planner: PlannerService, engine, spec: dict, *, force: bool) -> str:
    cid = spec["id"]
    existing = planner.get_activity_plan(cid)
    if existing and is_adopted(existing) and not force:
        return "skipped"

    structured = _build_structured(spec)
    launch = spec["launch"]
    end = structured["basic"]["end_date"]
    pm = structured["basic"]["promotion_month"]
    flat = {
        "campaign_id": cid,
        "campaign_name": spec["name"],
        "campaign_type": structured["basic"]["campaign_type"],
        "target_dest": spec["dest"],
        "promotion_month": pm,
        "start_date": launch,
        "end_date": end,
        "plan_summary": structured["background"]["summary"],
        "target_audience": structured["customer_segment"]["description"],
        "demand_analysis": structured["data_insights"]["selection_reason"],
        "solution_analysis": structured["strategy"]["theme"],
        "target_metrics": structured["objectives"]["primary_goal"],
        "execution_steps": "上线 → 监控 → 复盘",
        "plan_source": spec.get("source") or PLAN_SOURCE_HUMAN,
        "adoption_status": ADOPTION_ADOPTED,
    }
    src = spec.get("source") or PLAN_SOURCE_HUMAN
    planner._upsert_campaign(flat, plan_source=src)
    planner.save_structured_plan(cid, structured, editor="demo_seed")

    with engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE dim_campaign SET
                adoption_status = :adopt,
                lifecycle_status = :st,
                plan_review_confirmed_at = CURRENT_TIMESTAMP,
                plan_review_confirmed_by = 'demo_seed',
                promotion_month = :pm,
                start_date = :start,
                end_date = :end,
                plan_structured_json = :json,
                plan_source = :psrc,
                updated_at = CURRENT_TIMESTAMP
            WHERE campaign_id = :cid
            """),
            {
                "adopt": ADOPTION_ADOPTED,
                "st": LifecycleStatus.PLAN_REVIEW.value,
                "pm": pm,
                "start": launch,
                "end": end,
                "json": json.dumps(structured, ensure_ascii=False),
                "psrc": src,
                "cid": cid,
            },
        )
    return "inserted"


def seed_demo_calendar_2027(*, force: bool = False) -> dict:
    """写入 2027 全年演示活动（全年计划池 + 活动建档日历）。"""
    planner = PlannerService()
    engine = get_engine()
    inserted = 0
    skipped = 0
    ids: list[str] = []
    for spec in DEMO_CALENDAR_2027:
        result = _upsert_demo_activity(planner, engine, spec, force=force)
        if result == "inserted":
            inserted += 1
            ids.append(spec["id"])
        else:
            skipped += 1
    return {
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "total": len(DEMO_CALENDAR_2027),
        "campaign_ids": ids,
        "message": f"已加载 {inserted} 场 2027 演示活动（跳过 {skipped} 场已存在）",
    }


def seed_agent2_demo_case(*, force: bool = False) -> dict:
    """兼容旧接口：加载完整 2027 演示日历。"""
    return seed_demo_calendar_2027(force=force)
