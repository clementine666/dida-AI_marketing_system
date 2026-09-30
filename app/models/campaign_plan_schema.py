"""活动主文档 schema v3 — 同一份 JSON 从建档活到归档。

12 个业务模块 + AI 溯源。评审可空（黄字警告）；采纳后自动拆三线任务；
上线前锁定 ID/监控/素材链接；归档只补人工结论。
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any

# 活动主文档模块（schema v3）：同一份 JSON 从建档活到归档
PLAN_SECTIONS = [
    {
        "id": "source",
        "title": "① 活动来源与基本信息",
        "gate": "review",
        "hint": "从哪来、何时做、谁负责",
        "review_focus": "来源是否可信、推广窗口与上线日是否合理",
    },
    {
        "id": "background",
        "title": "② 活动背景",
        "gate": "review",
        "hint": "抓住什么机会、解决什么问题",
        "review_focus": "背景是否充分、与目的地/季节是否匹配",
    },
    {
        "id": "data_insights",
        "title": "③ 数据分析 · 为什么要做",
        "gate": "review",
        "hint": "用数据证明值得做",
        "review_focus": "结论是否支撑立项；空数据可采纳但无法评估达成",
    },
    {
        "id": "objectives",
        "title": "④ 活动目标",
        "gate": "review",
        "hint": "结果目标 + 过程监控指标 + 计算方式",
        "review_focus": "能否衡量成功；空目标可采纳但无法评估达成",
    },
    {
        "id": "strategy",
        "title": "⑤ 方案策划",
        "gate": "review",
        "hint": "主题、玩法、位置、素材需求清单",
        "review_focus": "是否可执行；素材清单供后续自动拆素材任务",
    },
    {
        "id": "customer_segment",
        "title": "⑥ 目标客户群体",
        "gate": "review",
        "hint": "评审填画像与圈选条件；客户 ID 上线前锁定",
        "review_focus": "客群假设是否精准；ID 列表不是本阶段必填",
    },
    {
        "id": "hotel_solution",
        "title": "⑦ 酒店产品解决方案",
        "gate": "review",
        "hint": "评审填选品条件；酒店 ID 上线前锁定",
        "review_focus": "供给假设是否匹配客群；ID 列表不是本阶段必填",
    },
    {
        "id": "product_delivery",
        "title": "⑧ 产品交付方式",
        "gate": "review",
        "hint": "展示/优惠券/渠道；落地页与埋点上线前补齐",
        "review_focus": "交付形态是否适合客群与目标",
    },
    {
        "id": "forecast",
        "title": "⑨ 效果预估与业务价值",
        "gate": "review",
        "hint": "选填预估，不与④重复必填",
        "review_focus": "预估是否有③支撑；数字可空",
    },
    {
        "id": "task_board",
        "title": "⑩ 三线任务板",
        "gate": "split",
        "hint": "资源 / 方案 / 素材 · 采纳后按模板自动拆",
        "review_focus": "上线日是否能算出截止日；三列独立、素材不嵌在方案里",
    },
    {
        "id": "launch_pack",
        "title": "⑪ 上线审核包",
        "gate": "launch",
        "hint": "锁定客户/酒店 ID、监控字段、素材预览、任务完成",
        "review_focus": "上线前对照本文档审核齐套",
    },
    {
        "id": "diagnosis",
        "title": "⑫ 效果诊断",
        "gate": "diagnose",
        "hint": "AI 读假设 + 过程漏斗 + 结果 + 任务完成，追总根源",
        "review_focus": "根因是否站得住；过程指标空则只能判定无法归因",
    },
    {
        "id": "archive",
        "title": "⑬ 归档",
        "gate": "archive",
        "hint": "实绩与诊断已在文档里；补人工结论即可归档",
        "review_focus": "人工结论是否足以沉淀经验",
    },
    {
        "id": "ai_provenance",
        "title": "⑭ AI 建议依据",
        "gate": "review",
        "hint": "仅 AI 建议活动展示",
        "review_focus": "AI 理由是否成立、是否采纳或合并",
    },
]


# 三线标准任务（相对上线日；资源线统一 T-7，方案/素材按周）
RESOURCE_TASK_DEADLINE_DAYS = -7

RESOURCE_TASK_TEMPLATES = [
    {"code": "A", "name": "淡旺季预订高峰分析", "owner": "萧蓉", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "QBI 时机+国家/城市需求：去年1–12月该城离店高峰月、建议活动上下线区间、淡旺季与节假日说明", "lane": "resource"},
    {"code": "B", "name": "城市/酒店需求分析", "owner": "萧蓉", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "QBI 酒店分层：区间有产酒店清单、P80 需求×转化标签、星级/价格/集团分布、优先高需求低转化", "lane": "resource"},
    {"code": "C", "name": "客户画像分析", "owner": "萧蓉", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "QBI 目的地×客群、客群×国家×酒店：订这些酒店的机构 ID、TMC/定制分布", "lane": "resource"},
    {"code": "D", "name": "预定提前期分析", "owner": "萧蓉", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "QBI 需求趋势：离店高峰对应的预订高峰日期、相隔天数、建议上线日", "lane": "resource"},
    {"code": "E", "name": "营销活动日历表汇总填写", "owner": "JIM", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "日历表含时间、酒店、客户建议", "lane": "resource"},
    {"code": "F", "name": "DC/TPS 确认参与意愿", "owner": "萧蓉", "t_offset_days": RESOURCE_TASK_DEADLINE_DAYS, "t_label": "T-7",
     "accept_criteria": "DC/TPS 反馈：参与、新酒店、返佣", "lane": "resource"},
]
PLAN_TASK_TEMPLATES = [
    {"code": "P1", "name": "活动主题与玩法确认", "owner": "JIM", "t_offset_days": -21, "t_label": "T-3周",
     "accept_criteria": "玩法规则可配置", "lane": "plan"},
    {"code": "P2", "name": "上线位置确认", "owner": "JIM", "t_offset_days": -14, "t_label": "T-2周",
     "accept_criteria": "Banner/专题页等位置清单", "lane": "plan"},
    {"code": "P3", "name": "优惠券或展示配置", "owner": "JIM", "t_offset_days": -14, "t_label": "T-2周",
     "accept_criteria": "券规则或纯展示方案已确认", "lane": "plan"},
    {"code": "P4", "name": "客户圈选确认", "owner": "JIM", "t_offset_days": -14, "t_label": "T-2周",
     "accept_criteria": "圈客条件或锁定 ID", "lane": "plan"},
    {"code": "P5", "name": "目标与监控字段确认", "owner": "侯颖新", "t_offset_days": -7, "t_label": "T-1周",
     "accept_criteria": "过程指标与预警阈值", "lane": "plan"},
]
MATERIAL_TYPE_TEMPLATES = {
    "Banner": {"name": "官网 Banner", "owner": "梓淮", "t_offset_days": -14, "t_label": "T-2周", "spec": "按位尺寸"},
    "海报": {"name": "落地页海报", "owner": "梓淮", "t_offset_days": -14, "t_label": "T-2周", "spec": "海报尺寸"},
    "文案": {"name": "活动文案", "owner": "JIM", "t_offset_days": -14, "t_label": "T-2周", "spec": "主标题+卖点"},
    "公众号文章": {"name": "公众号文章", "owner": "梓淮", "t_offset_days": -7, "t_label": "T-1周", "spec": "长图文"},
    "朋友圈物料": {"name": "朋友圈物料", "owner": "梓淮", "t_offset_days": -7, "t_label": "T-1周", "spec": "尺寸+文案"},
}


def default_plan(dest: str | None = None, plan_source: str = "human_calendar") -> dict[str, Any]:
    d = dest or "目标目的地"
    return {
        "schema_version": 3,
        "source": {
            "plan_source": plan_source,
            "source_detail": "",
            "feishu_record_id": "",
            "reference_campaign": "",
            "owner": "营销师",
            "priority": "P1",
        },
        "basic": {
            "campaign_name": "",
            "campaign_type": "Banner",
            "activity_type": "人工标准",
            "promotion_month": "",
            "promotion_time": "",
            "promotion_window": "",
            "start_date": "",
            "end_date": "",
            "target_dest": d,
            "destination_region": "",
            "continent": "",
            "country_region": "",
            "city": "",
            "district": "",
            "session_group": "",
            "p75_days": "",
        },
        "schedule": {
            "resource_handoff": "",
            "resource_delivery": "",
            "material_done": "",
            "launch_date": "",
            "promotion_period": "",
            "review_date": "",
        },
        "background": {
            "market_context": "",
            "business_trigger": "",
            "opportunity": "",
            "summary": "",
        },
        "data_insights": {
            "market_data": "",
            "client_behavior_data": "",
            "historical_reference": "",
            "competitive_landscape": "",
            "data_conclusion": "",
        },
        "objectives": {
            "primary_goal": "",
            "target_metrics": "订单数、TTV、转化率",
            "secondary_goals": "",
            "success_criteria": "",
            "budget_cny": "",
            "roi_expectation": "",
            "process_metrics": "",
            "calc_method": "",
            "baseline": "",
            "ttv_target": "",
            "gp_target": "",
            "order_target": "",
            "client_cover_target": "",
        },
        "strategy": {
            "positioning": "",
            "theme": "",
            "core_message": "",
            "creative_direction": "",
            "solution_summary": "",
            "differentiation": "",
            "key_mechanics": "",
            "placements": "",
            "material_needs": "",
        },
        "customer_segment": {
            "segment_name": f"{d} B端采购客户",
            "description": f"面向 {d} 有真实采购需求的 B 端客户",
            "client_groups": "",
            "behaviors": "近90天有搜索/浏览/下单行为",
            "pain_points": "",
            "geo_focus": d,
            "size_estimate": "",
            "selection_rationale": "",
            "locked_client_ids": [],
            "query_profile": {
                "destination": d,
                "time_window_days": 90,
                "client_group_ids": [],
                "behavior_source": "funnel",
                "step_codes": ["request", "click"],
                "min_funnel_events": 1,
                "exclude_test_account": True,
                "client_limit": 200,
                "sort_by": "rp_click_pv_desc",
            },
        },
        "hotel_solution": {
            "selection_strategy": f"{d}核心商圈高星酒店优先",
            "star_min": "4",
            "price_range": "中高端",
            "hotel_criteria": "高评分、库存稳定、价格有竞争力",
            "recommended_types": "",
            "inventory_notes": "",
            "price_competitiveness": "",
            "supply_risk": "",
            "locked_hotel_ids": [],
            "query_profile": {
                "destination": d,
                "time_window_days": 90,
                "star_min": 4,
                "price_min_cny": None,
                "price_max_cny": None,
                "sort_by": "click_cnt_desc",
                "hotel_limit": 20,
                "scope": "destination_hot",
                "keyword_boost": [],
            },
        },
        "product_delivery": {
            "delivery_type": "mixed",
            "delivery_type_label": "组合触达（展示+优惠券）",
            "coupon_strategy": "",
            "display_strategy": "官网 Banner + 活动专区推荐位",
            "channels": "官网 Banner · 活动专区 · 定向短信",
            "landing_experience": "",
            "execution_steps": "",
            "cost_control": "",
            "landing_url": "",
            "tracking_events": "",
        },
        "forecast": {
            "expected_exposure": "",
            "expected_clicks": "",
            "expected_orders": "",
            "expected_ttv": "",
            "expected_gp": "",
            "expected_roi": "",
            "value_proposition": "",
            "risk_assessment": "",
        },
        "execution": {
            "timeline_milestones": "",
            "prep_lead_notes": "提前3个月启动配置与测试",
            "dependencies": "",
            "agent2_handoff": "确认客群画像与选品条件后送 Agent2 圈客选品",
            "monitoring_focus": "Banner CTR、专区转化、订单/TTV",
            "review_checklist": "",
        },
        "task_board": {
            "launch_date": "",
            "generated": False,
            "lanes": {"resource": [], "plan": [], "material": []},
        },
        "launch_pack": {
            "client_ids": [],
            "hotel_ids": [],
            "landing_url": "",
            "coupon_config": "",
            "tracking": "",
            "materials": [],
            "task_completion_note": "",
        },
        "live_results": {
            "banner_expose_count": "",
            "banner_click_count": "",
            "banner_ctr": "",
            "order_count": "",
            "total_ttv": "",
            "total_gp": "",
            "as_of": "",
        },
        "diagnosis": {
            "status": "",
            "method": "",
            "funnel_break": "",
            "one_line_verdict": "",
            "root_causes": [],
            "optimizations": [],
            "generated_at": "",
        },
        "archive": {
            "human_conclusion": "",
            "experience": "",
            "pitfalls": "",
            "actual_ttv": "",
            "actual_gp": "",
            "actual_orders": "",
            "achievement_rate": "",
        },
        "ai_provenance": {
            "ai_rationale": "",
            "intel_source": "",
            "intel_report_date": "",
            "similar_calendar_name": "",
            "confidence": "",
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _migrate_legacy(stored: dict, row: dict) -> dict:
    """将 v1 扁平结构或旧 JSON 映射到 v2 模块。"""
    patch: dict[str, Any] = {}
    if stored.get("campaign_name") or row.get("campaign_name"):
        patch.setdefault("basic", {})["campaign_name"] = stored.get("campaign_name") or row.get("campaign_name")
    for k in ("promotion_month", "promotion_time", "target_dest", "campaign_type"):
        if stored.get(k) or row.get(k):
            patch.setdefault("basic", {})[k] = stored.get(k) or row.get(k)
    bg = stored.get("background") or row.get("plan_summary") or ""
    if bg:
        patch.setdefault("background", {})["summary"] = bg
    demand = stored.get("demand_analysis") or row.get("demand_analysis") or ""
    if demand:
        patch.setdefault("data_insights", {})["data_conclusion"] = demand
    solution = stored.get("solution_analysis") or row.get("solution_analysis") or ""
    if solution:
        patch.setdefault("strategy", {})["solution_summary"] = solution
    if stored.get("customer_segment"):
        patch["customer_segment"] = stored["customer_segment"]
    elif row.get("target_audience"):
        patch.setdefault("customer_segment", {})["description"] = row["target_audience"]
    if stored.get("hotel_profile"):
        patch["hotel_solution"] = stored["hotel_profile"]
    if stored.get("goals"):
        patch["objectives"] = stored["goals"]
    elif row.get("target_metrics"):
        patch.setdefault("objectives", {})["target_metrics"] = row["target_metrics"]
    if stored.get("delivery"):
        d = stored["delivery"]
        patch["product_delivery"] = {
            "delivery_type_label": d.get("mode", ""),
            "channels": d.get("channels", ""),
            "execution_steps": d.get("execution_steps", ""),
            "display_strategy": d.get("display_strategy", d.get("mode", "")),
        }
    elif row.get("execution_steps"):
        patch.setdefault("product_delivery", {})["execution_steps"] = row["execution_steps"]
    if stored.get("ai_rationale") or row.get("rationale"):
        patch.setdefault("ai_provenance", {})["ai_rationale"] = stored.get("ai_rationale") or row.get("rationale")
    if stored.get("intel_source") or row.get("intel_report_title"):
        patch.setdefault("ai_provenance", {})["intel_source"] = stored.get("intel_source") or row.get("intel_report_title")
    if stored.get("similar_calendar_name") or row.get("similar_calendar_name"):
        patch.setdefault("ai_provenance", {})["similar_calendar_name"] = (
            stored.get("similar_calendar_name") or row.get("similar_calendar_name")
        )
    if stored.get("source"):
        patch["source"] = stored["source"]
    if stored.get("forecast"):
        patch["forecast"] = stored["forecast"]
    if stored.get("execution"):
        patch["execution"] = stored["execution"]
    return patch


def build_full_structured_plan(
    row: dict,
    *,
    plan_source: str = "human_calendar",
    ai_rationale: str | None = None,
    intel_source: str | None = None,
) -> dict[str, Any]:
    dest = row.get("target_dest") or ""
    stored_raw = row.get("plan_structured_json") or row.get("plan_draft_json")
    stored: dict = {}
    if stored_raw:
        try:
            import json
            parsed = json.loads(stored_raw) if isinstance(stored_raw, str) else stored_raw
            if isinstance(parsed, dict):
                stored = parsed
        except Exception:
            stored = {}

    base = default_plan(dest, plan_source=row.get("plan_source") or plan_source)
    ver = stored.get("schema_version")
    if ver in (2, 3) or stored.get("source") or stored.get("basic"):
        plan = _deep_merge(base, stored)
    else:
        legacy_patch = _migrate_legacy(stored if stored else {}, row)
        plan = _deep_merge(base, legacy_patch)
    plan["schema_version"] = 3

    if ai_rationale:
        plan["ai_provenance"]["ai_rationale"] = ai_rationale
    if intel_source:
        plan["ai_provenance"]["intel_source"] = intel_source
    if row.get("feishu_record_id"):
        plan["source"]["feishu_record_id"] = row["feishu_record_id"]
    if row.get("plan_source"):
        plan["source"]["plan_source"] = row["plan_source"]
    from app.services.v2.activity_doc_parser import apply_dida_gp_rate
    return apply_dida_gp_rate(plan)


def structured_to_flat(structured: dict) -> dict:
    """v2 结构化方案 → dim_campaign 扁平行（Agent2 兼容）。"""
    basic = structured.get("basic") or {}
    bg = structured.get("background") or {}
    data = structured.get("data_insights") or {}
    obj = structured.get("objectives") or {}
    strat = structured.get("strategy") or {}
    cs = structured.get("customer_segment") or {}
    hs = structured.get("hotel_solution") or {}
    pd = structured.get("product_delivery") or {}

    audience = cs.get("description") or ""
    if cs.get("client_groups"):
        audience += f"；分组: {cs['client_groups']}"
    if cs.get("segment_name"):
        audience = f"{cs['segment_name']} — {audience}" if audience else cs["segment_name"]

    import json
    return {
        "campaign_name": basic.get("campaign_name"),
        "plan_summary": bg.get("summary") or bg.get("market_context") or "",
        "demand_analysis": data.get("data_conclusion") or data.get("market_data") or "",
        "solution_analysis": strat.get("solution_summary") or strat.get("core_message") or "",
        "target_audience": audience,
        "target_metrics": obj.get("target_metrics") or obj.get("primary_goal") or "",
        "execution_steps": pd.get("execution_steps") or "",
        "campaign_type": basic.get("campaign_type") or pd.get("delivery_type_label") or "Banner",
        "delivery_mode": pd.get("delivery_type_label") or pd.get("delivery_type"),
        "target_dest": basic.get("target_dest"),
        "promotion_month": basic.get("promotion_month"),
        "plan_structured_json": json.dumps(structured, ensure_ascii=False),
    }


def _parse_iso_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def _task_from_tpl(tpl: dict, launch: date | None, extra: dict | None = None) -> dict:
    deadline = ""
    if launch is not None:
        deadline = (launch + timedelta(days=int(tpl["t_offset_days"]))).isoformat()
    item = {
        "code": tpl.get("code", ""),
        "name": tpl["name"],
        "owner": tpl.get("owner", ""),
        "lane": tpl["lane"],
        "t_label": tpl.get("t_label", ""),
        "t_offset_days": tpl.get("t_offset_days"),
        "deadline": deadline,
        "accept_criteria": tpl.get("accept_criteria", ""),
        "deliverable_url": "",
        "deliverable_text": "",
        "deliverable_attachments": [],
        "status": "todo",
    }
    if extra:
        item.update(extra)
    return item


def generate_task_board(plan: dict) -> dict:
    """按上线日、素材需求清单生成三线任务（人可再改）。"""
    basic = plan.get("basic") or {}
    strat = plan.get("strategy") or {}
    launch = _parse_iso_date(basic.get("start_date") or (plan.get("task_board") or {}).get("launch_date"))
    needs_raw = strat.get("material_needs") or "Banner,海报,文案"
    needs = [x.strip() for x in str(needs_raw).replace("，", ",").split(",") if x.strip()]
    resource = [_task_from_tpl(t, launch) for t in RESOURCE_TASK_TEMPLATES]
    plan_tasks = [_task_from_tpl(t, launch) for t in PLAN_TASK_TEMPLATES]
    materials = []
    for i, need in enumerate(needs, 1):
        meta = MATERIAL_TYPE_TEMPLATES.get(need) or {
            "name": need,
            "owner": "梓淮",
            "t_offset_days": -14,
            "t_label": "T-2周",
            "spec": "",
        }
        materials.append(
            _task_from_tpl(
                {
                    "code": f"M{i}",
                    "name": meta["name"],
                    "owner": meta["owner"],
                    "lane": "material",
                    "t_offset_days": meta["t_offset_days"],
                    "t_label": meta["t_label"],
                    "accept_criteria": f"交付 {need}（{meta.get('spec') or '规格待补'}）并可点击预览",
                },
                launch,
            )
        )
    return {
        "launch_date": launch.isoformat() if launch else (basic.get("start_date") or ""),
        "generated": True,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lanes": {"resource": resource, "plan": plan_tasks, "material": materials},
    }


def ensure_task_board(plan: dict, *, force: bool = False) -> dict:
    board = plan.get("task_board") or {}
    lanes = board.get("lanes") or {}
    has_tasks = any(lanes.get(k) for k in ("resource", "plan", "material"))
    if has_tasks and not force:
        return plan
    plan["task_board"] = generate_task_board(plan)
    return plan


def _parse_display_date(val: str | None) -> str:
    """尽量从展示用日期字符串提取 YYYY-MM-DD。"""
    if not val:
        return ""
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    import re
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}-{mo:02d}-{d:02d}"
    return ""


def sync_schedule_dates(plan: dict) -> dict:
    """schedule 管展示日期，basic 管 ISO 锚点；保存时双向补齐。"""
    basic = plan.setdefault("basic", {})
    sched = plan.setdefault("schedule", {})
    launch_iso = basic.get("start_date") or _parse_display_date(sched.get("launch_date"))
    if launch_iso:
        basic["start_date"] = launch_iso
        if not sched.get("launch_date"):
            sched["launch_date"] = launch_iso
    period = str(sched.get("promotion_period") or "")
    end_part = period.split("~")[-1].strip() if "~" in period else period
    end_iso = basic.get("end_date") or _parse_display_date(end_part)
    if end_iso:
        basic["end_date"] = end_iso
    if basic.get("promotion_window") and not basic.get("promotion_month"):
        basic["promotion_month"] = basic["promotion_window"]
    tb = plan.setdefault("task_board", {})
    if basic.get("start_date") and not tb.get("launch_date"):
        tb["launch_date"] = basic["start_date"]
    return plan


def sync_launch_pack_ids(plan: dict) -> dict:
    """圈客锁定后的 ID 同步进上线包，供审核对照。"""
    cs = plan.get("customer_segment") or {}
    hs = plan.get("hotel_solution") or {}
    pd = plan.get("product_delivery") or {}
    pack = plan.setdefault("launch_pack", {})
    clients = cs.get("locked_client_ids") or pack.get("client_ids") or []
    hotels = hs.get("locked_hotel_ids") or pack.get("hotel_ids") or []
    pack["client_ids"] = clients
    pack["hotel_ids"] = hotels
    if pd.get("landing_url") and not pack.get("landing_url"):
        pack["landing_url"] = pd.get("landing_url")
    if pd.get("tracking_events") and not pack.get("tracking"):
        pack["tracking"] = pd.get("tracking_events")
    if (plan.get("objectives") or {}).get("process_metrics") and not pack.get("tracking"):
        pack["tracking"] = (plan.get("objectives") or {}).get("process_metrics")
    return plan

