"""从活动主文档 + 过程/结果数据生成根因诊断（复盘用）。"""

from __future__ import annotations

import json
import re
from datetime import datetime

from app.integrations.llm_client import LlmClient
from app.models.campaign_plan_schema import build_full_structured_plan
from app.services.agent3_service import Agent3Service
from app.services.agent4_service import Agent4Service
from app.services.v2.agent1_planner import PlannerService

ROOT_CAUSE_LABELS = {
    "targeting": "圈客不准",
    "supply": "供给/价格",
    "creative": "素材/CTR",
    "offer": "券或玩法",
    "placement": "上线位置",
    "timing": "档期窗口",
    "tracking": "埋点缺失无法归因",
    "execution_gap": "准备任务没做完",
}


def _num(val) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"[\d.]+", str(val).replace(",", ""))
    return float(m.group()) if m else None


def _task_stats(plan: dict) -> dict:
    lanes = ((plan.get("task_board") or {}).get("lanes")) or {}
    all_tasks = []
    for lane, items in lanes.items():
        for t in items or []:
            all_tasks.append({**t, "lane": t.get("lane") or lane})
    total = len(all_tasks)
    done = sum(1 for t in all_tasks if str(t.get("status") or "") in ("done", "已完成", "已验收"))
    missing_url = [t.get("name") for t in all_tasks if not t.get("deliverable_url") and str(t.get("status")) not in ("done", "已完成")]
    return {
        "total": total,
        "done": done,
        "completion_rate": round(done / total, 4) if total else None,
        "open_without_deliverable": missing_url[:8],
    }


def build_ai_read_pack(plan: dict, live: dict) -> dict:
    """AI 只读这个压缩包，不扫整份散文。"""
    basic = plan.get("basic") or {}
    obj = plan.get("objectives") or {}
    cs = plan.get("customer_segment") or {}
    hs = plan.get("hotel_solution") or {}
    strat = plan.get("strategy") or {}
    pd = plan.get("product_delivery") or {}
    pack = plan.get("launch_pack") or {}
    bg = plan.get("background") or {}
    data = plan.get("data_insights") or {}
    return {
        "hypothesis": {
            "name": basic.get("campaign_name"),
            "dest": basic.get("target_dest"),
            "window": basic.get("promotion_time") or f"{basic.get('start_date')}~{basic.get('end_date')}",
            "why": (bg.get("summary") or bg.get("opportunity") or "")[:400],
            "data_conclusion": (data.get("data_conclusion") or "")[:400],
            "theme": strat.get("theme"),
            "mechanics": strat.get("key_mechanics") or strat.get("solution_summary"),
            "placements": strat.get("placements") or pd.get("display_strategy"),
            "audience": cs.get("description") or cs.get("segment_name"),
            "hotel_strategy": hs.get("selection_strategy") or hs.get("hotel_criteria"),
            "goals": obj.get("target_metrics") or obj.get("primary_goal"),
            "process_kpis": obj.get("process_metrics") or pack.get("tracking"),
            "forecast_ttv": (plan.get("forecast") or {}).get("expected_ttv") or obj.get("ttv_target"),
            "forecast_orders": (plan.get("forecast") or {}).get("expected_orders") or obj.get("order_target"),
        },
        "execution": {
            "locked_client_count": len(pack.get("client_ids") or cs.get("locked_client_ids") or []),
            "locked_hotel_count": len(pack.get("hotel_ids") or hs.get("locked_hotel_ids") or []),
            "landing_url": pack.get("landing_url") or pd.get("landing_url"),
            "materials": pack.get("materials") or [],
            "tasks": _task_stats(plan),
        },
        "live": {
            "banner_expose": live.get("banner_expose_count"),
            "banner_click": live.get("banner_click_count"),
            "banner_ctr": live.get("banner_ctr"),
            "rp_ctr": live.get("rp_ctr"),
            "orders": live.get("order_count") or live.get("orders"),
            "ttv": live.get("total_ttv"),
            "gp": live.get("total_gp"),
            "unique_clients": live.get("unique_clients"),
        },
    }


def rule_diagnosis(read_pack: dict) -> dict:
    h = read_pack.get("hypothesis") or {}
    ex = read_pack.get("execution") or {}
    live = read_pack.get("live") or {}
    causes: list[dict] = []
    opts: list[dict] = []

    if not h.get("process_kpis") and not h.get("goals"):
        causes.append({
            "type": "tracking",
            "label": ROOT_CAUSE_LABELS["tracking"],
            "evidence": "评审时未写过程指标与结果目标，无法判断达成与断点",
            "confidence": "high",
        })
        opts.append({"action": "下次评审必须补过程 KPI（曝光/点击/CTR/CVR）和结果目标", "owner_hint": "营销负责人"})

    tasks = ex.get("tasks") or {}
    if tasks.get("total") and (tasks.get("completion_rate") or 0) < 0.8:
        causes.append({
            "type": "execution_gap",
            "label": ROOT_CAUSE_LABELS["execution_gap"],
            "evidence": f"三线任务完成率 {tasks.get('completion_rate')}",
            "confidence": "high",
        })
        opts.append({"action": "先补齐未验收任务与交付链接，再判断方案对错", "owner_hint": "任务监督"})

    ctr = live.get("banner_ctr")
    orders = live.get("order_count") or live.get("orders") or 0
    expose = live.get("banner_expose") or live.get("banner_expose_count") or 0
    if ctr is not None and ctr < 0.02 and expose > 0:
        causes.append({
            "type": "creative",
            "label": ROOT_CAUSE_LABELS["creative"],
            "evidence": f"Banner CTR={ctr}，曝光有但点击弱，优先查素材与位置",
            "confidence": "medium",
        })
        opts.append({"action": "对照 11.materials 预览链接复盘主视觉与投放位置", "owner_hint": "素材/方案"})
    elif ctr is not None and ctr >= 0.02 and orders == 0:
        causes.append({
            "type": "offer",
            "label": ROOT_CAUSE_LABELS["offer"],
            "evidence": "点击正常但无订单，查券规则、房价竞争力、库存",
            "confidence": "medium",
        })
        opts.append({"action": "用锁定酒店 ID 做有价率/优势率复核", "owner_hint": "资源"})

    if not ex.get("locked_client_count"):
        causes.append({
            "type": "targeting",
            "label": ROOT_CAUSE_LABELS["targeting"],
            "evidence": "上线包无锁定客户 ID，无法验证圈客是否落地",
            "confidence": "medium",
        })
    if not ex.get("locked_hotel_count"):
        causes.append({
            "type": "supply",
            "label": ROOT_CAUSE_LABELS["supply"],
            "evidence": "上线包无锁定酒店 ID",
            "confidence": "medium",
        })

    funnel_break = "unknown"
    if (live.get("banner_expose") or 0) == 0:
        funnel_break = "expose"
    elif ctr is not None and ctr < 0.02:
        funnel_break = "click"
    elif orders == 0 and (live.get("banner_click") or 0) > 0:
        funnel_break = "convert"
    elif orders:
        funnel_break = "order"

    if not causes:
        causes.append({
            "type": "timing",
            "label": ROOT_CAUSE_LABELS["timing"],
            "evidence": "尚未发现单一断点，需对照档期与假设再看",
            "confidence": "low",
        })

    return {
        "status": "draft",
        "method": "rules",
        "funnel_break": funnel_break,
        "root_causes": causes,
        "optimizations": opts,
        "one_line_verdict": causes[0]["evidence"] if causes else "",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _llm_diagnosis(read_pack: dict, seed: dict) -> dict | None:
    llm = LlmClient()
    if not llm.is_configured():
        return None
    prompt = (
        "你是道旅 B2B 酒店营销复盘专家。根据「当初假设 / 执行保真 / 过程与结果」判断活动效果的总根源。"
        "必须从这些类型中选：targeting,supply,creative,offer,placement,timing,tracking,execution_gap。"
        "只输出 JSON：funnel_break, root_causes([{type,evidence,confidence}]), optimizations([{action,owner_hint}]), one_line_verdict。"
        "规则：任务没做完时不要先怪客群；没有过程指标时 type=tracking；CTR 低先看素材/位置；CTR 正常无订单看供给/券。\n\n"
        f"读包：{json.dumps(read_pack, ensure_ascii=False)[:6000]}\n"
        f"规则初判：{json.dumps(seed, ensure_ascii=False)[:2000]}"
    )
    try:
        raw = llm.chat([{"role": "user", "content": prompt}], temperature=0.2)
        text = raw.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        parsed["status"] = "draft"
        parsed["method"] = "llm"
        parsed["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        for c in parsed.get("root_causes") or []:
            c["label"] = ROOT_CAUSE_LABELS.get(c.get("type"), c.get("type"))
        return parsed
    except Exception:
        return None


class CampaignDiagnosisService:
    def __init__(self):
        self.planner = PlannerService()
        self.metrics = Agent3Service()
        self.analyst = Agent4Service()

    def diagnose(self, campaign_id: str, persist: bool = True) -> dict:
        plan_row = self.planner.get_activity_plan(campaign_id)
        if not plan_row:
            return {"ok": False, "error": "活动不存在"}
        plan = build_full_structured_plan(plan_row)
        live = self.metrics.compute_campaign_metrics(campaign_id)
        if live.get("error"):
            live = {}
        read_pack = build_ai_read_pack(plan, live)
        seed = rule_diagnosis(read_pack)
        llm = _llm_diagnosis(read_pack, seed)
        diagnosis = llm or seed
        diagnosis["read_pack"] = read_pack
        plan["live_results"] = {
            **{k: live.get(k) for k in (
                "banner_expose_count", "banner_click_count", "banner_ctr",
                "rp_ctr", "order_count", "total_ttv", "total_gp", "unique_clients",
            )},
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        plan["diagnosis"] = {k: v for k, v in diagnosis.items() if k != "read_pack"}
        if persist:
            self.planner.save_structured_plan(campaign_id, plan, editor="agent6")
        return {"ok": True, "campaign_id": campaign_id, "diagnosis": diagnosis, "read_pack": read_pack}

    def get_pack(self, campaign_id: str) -> dict:
        plan_row = self.planner.get_activity_plan(campaign_id)
        if not plan_row:
            return {"ok": False, "error": "活动不存在"}
        plan = build_full_structured_plan(plan_row)
        live = self.metrics.compute_campaign_metrics(campaign_id)
        if live.get("error"):
            live = {}
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "diagnosis": plan.get("diagnosis") or {},
            "archive": plan.get("archive") or {},
            "read_pack": build_ai_read_pack(plan, live),
            "live": live,
        }
