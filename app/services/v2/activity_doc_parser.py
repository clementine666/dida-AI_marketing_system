"""Parse WorkBuddy / Agent1 月度决策卡 Markdown → schema v3 评审方案。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from app.models.campaign_plan_schema import default_plan

ACTIVITY_HEAD = re.compile(r"^##\s+活动\d+[：:]\s*(.+)\s*$", re.M)
ISO_DATE = re.compile(r"(20\d{2}-\d{1,2}-\d{1,2})")
CN_DATE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
FILE_MONTH = re.compile(r"(\d{4})年(\d{1,2})月")
SCORE_RE = re.compile(r"(\d{2,3})\s*/\s*100")
STAR_RE = re.compile(r"([3-5])\s*[-~到至]?\s*[3-5]?\s*星")
PRIORITY_RE = re.compile(r"\b(P[012])\b")

SECTION_ALIASES = (
    ("决策摘要", "decision"),
    ("一句话决策", "one_liner"),
    ("为什么做", "why"),
    ("执行要点", "why"),
    ("配什么产品", "hotels"),
    ("执行库存", "hotels"),
    ("卖给谁", "customers"),
    ("执行客群", "customers"),
    ("解决什么需求", "needs"),
    ("怎么玩", "play"),
    ("活动周期", "cycle"),
    ("营销怎么做", "marketing"),
    ("风险评估", "risks"),
    ("预期效果", "forecast"),
    ("执行目标", "forecast"),
    ("下一步行动", "next"),
)

DEST_HINTS = (
    ("北海道", "日本北海道"),
    ("京都", "日本"),
    ("日本", "日本"),
    ("泰国", "泰国"),
    ("曼谷", "泰国"),
    ("马尔代夫", "马尔代夫"),
    ("巴厘", "印尼巴厘岛"),
    ("韩国", "韩国"),
    ("首尔", "韩国"),
    ("法国", "法国"),
    ("意大利", "意大利"),
    ("瑞士", "瑞士"),
    ("德国", "德国"),
    ("慕尼黑", "德国慕尼黑"),
    ("北欧", "北欧"),
    ("欧洲", "欧洲"),
    ("东南亚", "东南亚"),
    ("全目的地", "全目的地"),
)

TTV_RANGE = re.compile(r"(\d+\s*[-~—至到]+\s*\d+\s*万)")
MD_RANGE = re.compile(r"(\d{1,2})/(\d{1,2})\s*[-~—至到]+\s*(\d{1,2})/(\d{1,2})")
WAN_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]+\s*(\d+(?:\.\d+)?)\s*万")
WAN_SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*万")
GP_RATE_LOW = 0.01
GP_RATE_HIGH = 0.02
GP_RATE_LABEL = "预订GP率约1%-2%"
GP_VALUE_RE = re.compile(r"(GP[：:]\s*)([0-9,\.\-—~至到]+万)")


def parse_wan_range(text: str) -> tuple[float, float] | None:
    m = WAN_RANGE.search(text or "")
    if m:
        return float(m.group(1)), float(m.group(2))
    m = WAN_SINGLE.search(text or "")
    if m:
        n = float(m.group(1))
        return n, n
    return None


def format_wan_range(lo: float, hi: float) -> str:
    def fmt(n: float) -> str:
        if n < 10:
            return f"{n:.1f}".rstrip("0").rstrip(".")
        return str(int(round(n)))
    return f"{fmt(lo)}-{fmt(hi)}万"


def gp_from_ttv(ttv_text: str) -> str:
    """道旅活动预订 GP = TTV × 1%–2%。"""
    rng = parse_wan_range(ttv_text)
    if not rng:
        return ""
    lo, hi = rng
    return format_wan_range(lo * GP_RATE_LOW, hi * GP_RATE_HIGH)


def apply_dida_gp_rate(plan: dict[str, Any]) -> dict[str, Any]:
    """所有道旅活动：有 TTV 就覆盖 GP / ROI 文案为 1%–2%。"""
    if not isinstance(plan, dict):
        return plan
    fc = plan.setdefault("forecast", {})
    obj = plan.setdefault("objectives", {})
    ttv = fc.get("expected_ttv") or obj.get("ttv_target") or ""
    gp = gp_from_ttv(str(ttv))
    if not gp:
        return plan
    fc["expected_gp"] = gp
    fc["expected_roi"] = GP_RATE_LABEL
    obj["gp_target"] = gp
    obj["roi_expectation"] = GP_RATE_LABEL
    calc = str(obj.get("calc_method") or "")
    if (not calc) or ("15%" in calc and "转化" not in calc):
        obj["calc_method"] = "预订GP = TTV × 1%–2%"

    def _rewrite(text: Any) -> Any:
        if not isinstance(text, str) or not text:
            return text
        text = GP_VALUE_RE.sub(lambda m, g=gp: f"{m.group(1)}{g}", text)
        text = text.replace("综合ROI约15%", GP_RATE_LABEL)
        text = re.sub(r"ROI\s*15%", GP_RATE_LABEL, text)
        return text

    for bag, key in (
        (obj, "target_metrics"),
        (obj, "primary_goal"),
        (fc, "value_proposition"),
    ):
        bag[key] = _rewrite(bag.get(key))
    return plan



def _norm_date(raw: str) -> str:
    raw = (raw or "").strip()
    m = ISO_DATE.search(raw)
    if m:
        y, mo, d = m.group(1).split("-")
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m = CN_DATE.search(raw)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _all_iso_dates(text: str) -> list[str]:
    found = []
    for m in ISO_DATE.finditer(text or ""):
        y, mo, d = m.group(1).split("-")
        found.append(f"{int(y):04d}-{int(mo):02d}-{int(d):02d}")
    for m in CN_DATE.finditer(text or ""):
        found.append(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    return found


def _plain(text: str) -> str:
    text = text or ""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    return text.strip()


def _split_activities(md: str) -> list[tuple[str, str]]:
    matches = list(ACTIVITY_HEAD.finditer(md))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        title = m.group(1).strip()
        title = re.sub(r"（[^）]*战役[^）]*）", "", title).strip()
        out.append((title, md[start:end].strip()))
    return out


def _section_key(heading: str) -> str | None:
    h = re.sub(r"^[^\w\u4e00-\u9fff]+", "", heading)
    h = h.split("（")[0].split("(")[0].strip()
    for alias, key in SECTION_ALIASES:
        if alias in h:
            return key
    return None


def _split_sections(body: str) -> dict[str, str]:
    parts = re.split(r"^###\s+", body, flags=re.M)
    sections: dict[str, str] = {}
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        key = _section_key(lines[0])
        if not key:
            continue
        sections[key] = "\n".join(lines[1:]).strip()
    return sections


def _bullet_map(section: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    current = ""
    buf: list[str] = []
    for line in (section or "").splitlines():
        m = re.match(r"^[-*]\s+\*\*(.+?)\*\*[：:]\s*(.*)$", line)
        if m:
            if current:
                mapping[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = [m.group(2).strip()]
            continue
        if current:
            buf.append(line.rstrip())
    if current:
        mapping[current] = "\n".join(buf).strip()
    for chunk in re.split(r"[｜|]", section or ""):
        m = re.search(r"\*\*(.+?)\*\*[：:]\s*(.+)", chunk.strip())
        if not m:
            continue
        key = m.group(1).strip()
        val = _plain(m.group(2))
        if key not in mapping or len(val) < len(mapping.get(key, val) or val):
            mapping[key] = val
    return mapping


def _infer_dest(text: str) -> str:
    for token, dest in DEST_HINTS:
        if token in (text or ""):
            return dest
    return ""


def _ttv_from_text(text: str) -> str:
    m = TTV_RANGE.search(text or "")
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def _slash_range_end(text: str, year: str) -> str:
    m = MD_RANGE.search(text or "")
    if not m:
        return ""
    y = int(year or 2027)
    return f"{y:04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"


def _unlabeled_body(section: str) -> str:
    text = _plain(section or "")
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^[-*]\s+", "", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _pick(mapping: dict[str, str], *keys: str) -> str:
    for want in keys:
        for key, val in mapping.items():
            if want in key:
                return _plain(val)
    return ""


def _parse_table(section: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lines = [ln for ln in (section or "").splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return rows
    headers = [_plain(c.replace("*", "")) for c in lines[0].split("|")[1:-1]]
    for line in lines[1:]:
        if re.match(r"^\|?\s*:?-{2,}", line.replace(" ", "")):
            continue
        cols = [_plain(c.replace("*", "")) for c in line.split("|")[1:-1]]
        if len(cols) < 2:
            continue
        rows.append({headers[i] if i < len(headers) else str(i): cols[i] for i in range(len(cols))})
    return rows


def _table_text(rows: list[dict[str, str]], keys: tuple[str, ...]) -> str:
    lines = []
    for row in rows:
        vals = [row.get(k, "") for k in keys if row.get(k)]
        if not vals:
            vals = [v for v in row.values() if v]
        lines.append(" · ".join(vals))
    return "\n".join(lines)


def _month_from_file(path: Path) -> tuple[str, str]:
    m = FILE_MONTH.search(path.name)
    if not m:
        return "", ""
    year, month = m.group(1), str(int(m.group(2)))
    return year, f"{month}月"


def _priority_and_score(decision: str) -> tuple[str, str, str]:
    score_m = SCORE_RE.search(decision or "")
    score = f"{score_m.group(1)}/100" if score_m else ""
    pri_m = PRIORITY_RE.search(decision or "")
    priority = pri_m.group(1) if pri_m else "P1"
    conf = f"{score} · {priority}" if score else priority
    return priority, score, conf


def _decision_cell(rows: list[dict[str, str]], dim: str, col: str = "说明") -> str:
    for row in rows:
        label = row.get("维度") or next(iter(row.values()), "")
        if dim in label:
            return _plain(row.get(col) or row.get("评分") or "")
    return ""


def _star_min(text: str) -> str:
    m = STAR_RE.search(text or "")
    if m:
        return m.group(1)
    if "评分≥4.5" in (text or "") or "评分>=4.5" in (text or ""):
        return "4"
    return "4"


def _keywords(text: str) -> list[str]:
    keys = []
    for token in ("滑雪", "樱花", "赏枫", "温泉", "亲子", "水屋", "蜜月", "商务", "展会", "极光", "啤酒"):
        if token in (text or ""):
            keys.append(token)
    return keys[:6]


def _lane_for_action(name: str) -> str:
    if any(x in name for x in ("库存", "DC", "TPS", "圈选酒店", "供应链")):
        return "resource"
    if any(x in name for x in ("素材", "Banner", "海报")):
        return "material"
    return "plan"


def activity_to_plan(
    title: str,
    body: str,
    *,
    source_file: str,
    promotion_month: str,
    year: str = "2027",
) -> dict[str, Any]:
    sec = _split_sections(body)
    why = _bullet_map(sec.get("why", ""))
    hotels = _bullet_map(sec.get("hotels", ""))
    customers = _bullet_map(sec.get("customers", ""))
    needs = _bullet_map(sec.get("needs", ""))
    play = _bullet_map(sec.get("play", ""))
    cycle = _bullet_map(sec.get("cycle", ""))
    marketing = _bullet_map(sec.get("marketing", ""))
    forecast_b = _bullet_map(sec.get("forecast", ""))
    decision_rows = _parse_table(sec.get("decision", ""))
    risk_rows = _parse_table(sec.get("risks", ""))
    next_rows = _parse_table(sec.get("next", ""))

    dest = _pick(hotels, "目的地") or _infer_dest(title) or _infer_dest(_plain(sec.get("hotels", "")))
    dest = re.split(r"[（(]", dest, maxsplit=1)[0].strip() or dest
    plan = default_plan(dest, plan_source="ai_intel")

    one_liner = _plain(sec.get("one_liner", "")).replace("建议做：", "").replace("建议做:", "").strip()
    priority, score, confidence = _priority_and_score(sec.get("decision", "") + " " + _decision_cell(decision_rows, "推荐"))
    ttv = _decision_cell(decision_rows, "TTV", "评分") or _pick(forecast_b, "TTV")
    gp = _decision_cell(decision_rows, "GP", "评分") or _pick(forecast_b, "GP")
    ttv = _ttv_from_text(ttv) or ttv
    if ttv in ("—", "-", "–"):
        ttv = _ttv_from_text(_decision_cell(decision_rows, "TTV", "说明") + sec.get("decision", ""))
    if gp in ("—", "-", "–"):
        gp = ""
    if not ttv and sec.get("forecast"):
        fm = re.search(r"TTV[：:]\s*([0-9,\.\-—~至到万千万]+)", sec["forecast"])
        ttv = (fm.group(1).strip() if fm else "") or _ttv_from_text(sec.get("forecast", ""))
    if not gp and sec.get("forecast"):
        fm = re.search(r"GP[：:]\s*([0-9,\.\-—~至到万千万]+)", sec["forecast"])
        gp = fm.group(1).strip() if fm else ""
    derived_gp = gp_from_ttv(ttv)
    if derived_gp:
        gp = derived_gp

    go_live = _norm_date(_pick(cycle, "上线"))
    if not go_live:
        live_m = re.search(r"(\d{1,2})/(\d{1,2})已上线", sec.get("decision", "") + one_liner)
        if live_m:
            go_live = f"{int(year or 2027):04d}-{int(live_m.group(1)):02d}-{int(live_m.group(2)):02d}"
    book_raw = _pick(cycle, "预订")
    book_dates = _all_iso_dates(book_raw)
    stay_raw = _pick(cycle, "入住")
    stay_dates = _all_iso_dates(stay_raw)
    end_date = book_dates[-1] if book_dates else ""
    if not end_date:
        end_date = _slash_range_end(book_raw, year) or (stay_dates[-1] if stay_dates else "")
    stay_window = stay_raw or (" ~ ".join(stay_dates[:2]) if stay_dates else "")

    external = _pick(why, "外部信号")
    advantage = _pick(why, "道旅优势")
    history = _pick(why, "历史验证")
    opportunity = _pick(why, "机会判断")
    hotel_guide = _pick(hotels, "运营圈选", "圈选指引", "执行库存", "酒店画像")
    hotel_types = _pick(hotels, "酒店类型", "推荐类型", "主要客群", "酒店画像")
    hotel_price = _pick(hotels, "价格")
    hotel_need = _pick(hotels, "核心刚需", "筛选")
    hotel_block = _plain(sec.get("hotels", ""))
    if not hotel_guide:
        hotel_guide = hotel_block
    if not hotel_types:
        hotel_types = hotel_block
    cust_type = _pick(customers, "客户类型", "主要客群")
    cust_sub = _pick(customers, "次要客群", "终端客群")
    cust_biz = _pick(customers, "业务特征")
    cust_size = _pick(customers, "规模")
    cust_guide = _pick(customers, "运营圈选", "圈选指引")
    if not cust_type:
        cust_type = _unlabeled_body(sec.get("customers", ""))
    pain = _pick(needs, "痛点") or _pick(customers, "痛点", "需求")
    demand = _pick(needs, "客户需求", "需求") or _unlabeled_body(sec.get("needs", ""))
    solution = _pick(needs, "解决方案")
    mechanics = "\n".join(filter(None, [
        f"优惠形式：{_pick(play, '优惠')}" if _pick(play, "优惠") else "",
        f"参与条件：{_pick(play, '参与')}" if _pick(play, "参与") else "",
        f"活动规则：{_pick(play, '规则')}" if _pick(play, "规则") else "",
    ])) or _plain(sec.get("play", "")) or _pick(why, "执行策略")
    channels = _pick(marketing, "推广渠道", "渠道")
    materials = _pick(marketing, "素材")
    cadence = _pick(marketing, "推广节奏", "节奏")
    script = _pick(marketing, "销售话术", "话术")
    forecast_line = _plain(sec.get("forecast", ""))
    resource_need = _decision_cell(decision_rows, "资源")
    risk_level = _decision_cell(decision_rows, "风险")
    roi_hint = GP_RATE_LABEL if gp_from_ttv(ttv) else ""
    if gp:
        forecast_line = re.sub(
            r"(GP[：:]\s*)([0-9,\.\-—~至到]+万)",
            lambda m: m.group(1) + gp,
            forecast_line,
        )

    orders = ""
    om = re.search(r"订单量[：:]\s*([^｜|]+)", forecast_line)
    if om:
        orders = om.group(1).strip()
    clients_n = ""
    cm = re.search(r"参与客户[：:]\s*([^｜|]+)", forecast_line)
    if cm:
        clients_n = cm.group(1).strip()
    cvr = ""
    vm = re.search(r"转化率[：:]\s*([^｜|\n]+)", forecast_line)
    if vm:
        cvr = vm.group(1).strip()

    play_text = _plain(sec.get("play", ""))
    campaign_type = "组合活动"
    if any(x in play_text for x in ("折", "券", "锁价", "特惠")):
        campaign_type = "Coupon"

    plan["source"].update({
        "plan_source": "ai_intel",
        "source_detail": f"2027全年营销活动日历 · {source_file}",
        "owner": "营销师",
        "priority": priority,
        "reference_campaign": "",
    })
    plan["basic"].update({
        "campaign_name": title,
        "campaign_type": campaign_type,
        "promotion_month": promotion_month,
        "promotion_time": stay_window or f"{year}年{promotion_month}",
        "start_date": go_live,
        "end_date": end_date,
        "target_dest": dest,
        "destination_region": dest.split("/")[0].split("、")[0],
    })
    plan["background"].update({
        "market_context": external,
        "business_trigger": one_liner,
        "opportunity": opportunity,
        "summary": one_liner,
    })
    plan["data_insights"].update({
        "market_data": external,
        "client_behavior_data": "\n".join(filter(None, [cust_type, cust_sub, cust_biz])),
        "historical_reference": history,
        "competitive_landscape": advantage,
        "data_conclusion": "\n".join(filter(None, [
            f"机会判断：{opportunity}" if opportunity else "",
            f"历史验证：{history}" if history else "",
            f"道旅优势：{advantage}" if advantage else "",
        ])),
    })
    metrics_bits = [x for x in (
        f"TTV {ttv}" if ttv else "",
        f"GP {gp}" if gp else "",
        f"订单 {orders}" if orders else "",
        f"客户 {clients_n}" if clients_n else "",
        f"转化率 {cvr}" if cvr else "",
    ) if x]
    plan["objectives"].update({
        "primary_goal": forecast_line.replace("\n", "；") or one_liner,
        "target_metrics": "；".join(metrics_bits) or "订单数、TTV、转化率",
        "secondary_goals": clients_n,
        "success_criteria": cvr or (f"达到预期 TTV {ttv}" if ttv else ""),
        "roi_expectation": roi_hint,
        "process_metrics": "Banner CTR、专区转化、订单/TTV/GP",
        "calc_method": "基于历史同类活动 TTV/GP 与搜索/价格涨幅校准",
        "baseline": history or "去年同期同类活动",
        "ttv_target": ttv,
        "gp_target": gp,
        "order_target": orders,
        "client_cover_target": clients_n,
        "budget_cny": resource_need,
    })
    plan["strategy"].update({
        "positioning": cust_type or title,
        "theme": title,
        "core_message": script,
        "creative_direction": materials or cadence,
        "solution_summary": "\n".join(filter(None, [solution, mechanics, play_text])),
        "differentiation": advantage,
        "key_mechanics": mechanics or play_text,
        "placements": channels or "飞书群 · 销售1v1 · 公众号",
        "material_needs": materials,
    })
    desc_parts = [x for x in (cust_type, cust_sub, cust_biz) if x]
    plan["customer_segment"].update({
        "segment_name": (cust_type.split("（")[0] if cust_type else f"{dest} B端采购客户")[:80],
        "description": "\n".join(desc_parts),
        "client_groups": "",
        "behaviors": cust_biz,
        "pain_points": "\n".join(filter(None, [demand, pain])),
        "geo_focus": dest,
        "size_estimate": cust_size,
        "selection_rationale": cust_guide,
        "locked_client_ids": [],
    })
    plan["customer_segment"]["query_profile"].update({
        "destination": dest,
        "time_window_days": 180 if "TMC" in (cust_type + cust_sub) else 90,
        "client_limit": 200,
    })
    plan["hotel_solution"].update({
        "selection_strategy": hotel_guide or hotel_block,
        "star_min": _star_min(hotel_block + hotel_guide),
        "price_range": hotel_price or "中高端",
        "hotel_criteria": "\n".join(filter(None, [hotel_need, hotel_guide])),
        "recommended_types": hotel_types or hotel_block,
        "inventory_notes": hotel_guide,
        "price_competitiveness": solution or _pick(play, "优惠"),
        "supply_risk": risk_level,
        "locked_hotel_ids": [],
    })
    plan["hotel_solution"]["query_profile"].update({
        "destination": dest,
        "star_min": int(_star_min(hotel_block + hotel_guide) or 4),
        "hotel_limit": 30,
        "keyword_boost": _keywords(title + hotel_block),
    })
    plan["product_delivery"].update({
        "delivery_type": "coupon" if campaign_type == "Coupon" else "mixed",
        "delivery_type_label": "优惠券驱动" if campaign_type == "Coupon" else "组合触达（展示+优惠券）",
        "coupon_strategy": _pick(play, "优惠") or mechanics,
        "display_strategy": channels,
        "channels": channels,
        "landing_experience": "活动专区 + 指定酒店清单",
        "execution_steps": cadence,
        "cost_control": resource_need,
        "tracking_events": "Banner点击、专题页访问、订单/TTV",
    })
    plan["forecast"].update({
        "expected_orders": orders,
        "expected_ttv": ttv,
        "expected_gp": gp,
        "expected_roi": roi_hint,
        "value_proposition": forecast_line.replace("\n", "；"),
        "risk_assessment": "\n".join(filter(None, [
            f"综合风险：{risk_level}" if risk_level else "",
            _table_text(risk_rows, ("风险", "等级", "应对措施")),
        ])),
    })
    next_lines = _table_text(next_rows, ("行动", "责任人", "截止时间"))
    lanes = {"resource": [], "plan": [], "material": []}
    for row in next_rows:
        name = row.get("行动") or ""
        if not name:
            continue
        lane = _lane_for_action(name)
        lanes[lane].append({
            "name": name,
            "owner": row.get("责任人") or "",
            "deadline": _norm_date(row.get("截止时间") or "") or (row.get("截止时间") or ""),
            "status": "todo",
            "deliverable_url": "",
            "lane": lane,
            "accept_criteria": "",
        })
    plan["execution"].update({
        "timeline_milestones": next_lines or cadence,
        "prep_lead_notes": f"上线日 {go_live or '待定'}；入住窗 {stay_window or '待定'}",
        "dependencies": resource_need,
        "agent2_handoff": "确认客群画像与选品条件后送方案策划Agent圈客选品（本阶段不锁 ID）。"
        + (f"\n客户圈选：{cust_guide}" if cust_guide else "")
        + (f"\n酒店圈选：{hotel_guide}" if hotel_guide else ""),
        "monitoring_focus": "Banner CTR、专区转化、订单/TTV",
        "review_checklist": "核对①窗口 ②为什么做 ③客群 ⑦酒店 ⑤玩法 ⑨TTV/GP 后再采纳",
    })
    plan["task_board"].update({
        "launch_date": go_live,
        "generated": bool(any(lanes.values())),
        "lanes": lanes,
    })
    plan["ai_provenance"].update({
        "ai_rationale": one_liner,
        "intel_source": f"2027营销活动日历/{source_file}",
        "intel_report_date": "",
        "similar_calendar_name": "",
        "confidence": confidence,
    })
    return plan


def parse_monthly_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    year, month = _month_from_file(path)
    items = []
    for title, body in _split_activities(text):
        plan = activity_to_plan(
            title,
            body,
            source_file=path.name,
            promotion_month=month,
            year=year or "2027",
        )
        items.append({
            "campaign_name": title,
            "target_dest": plan["basic"]["target_dest"],
            "promotion_month_hint": f"{year}-{int(month.replace('月', '')):02d}" if month else year,
            "rationale": plan["ai_provenance"]["ai_rationale"],
            "demand_analysis": plan["data_insights"]["data_conclusion"] or plan["customer_segment"]["description"],
            "solution_analysis": plan["strategy"]["solution_summary"],
            "plan": plan,
            "suggestion_key": "wb2027:" + hashlib.md5(f"{title}:{plan['basic']['target_dest']}".encode()).hexdigest(),
            "source_file": path.name,
        })
    return items


MONTHLY_FILE = re.compile(r"^2027年\d{2}月-")


def parse_calendar_dir(folder: Path) -> list[dict[str, Any]]:
    if not folder.exists():
        raise FileNotFoundError(str(folder))
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("2027年*.md")):
        if not MONTHLY_FILE.search(path.name):
            continue
        items.extend(parse_monthly_file(path))
    return items


def plan_from_llm_suggestion(sug: dict, source_title: str = "") -> dict[str, Any]:
    """Best-effort map of thin LLM JSON into the review form (not a full 决策卡)."""
    dest = (sug.get("target_dest") or "").strip() or "目标目的地"
    plan = default_plan(dest, plan_source="ai_intel")
    month_hint = str(sug.get("promotion_month_hint") or "")
    month_label = ""
    mm = re.search(r"(?:^|\D)(1[0-2]|[1-9])(?:月)?$", month_hint.replace("-", " "))
    if re.search(r"-(\d{2})$", month_hint):
        month_label = f"{int(month_hint[-2:])}月"
    elif mm:
        month_label = f"{mm.group(1)}月"
    go_live = _norm_date(str(sug.get("go_live_date") or ""))
    stay = str(sug.get("stay_window") or sug.get("promotion_time") or "")
    stay_dates = _all_iso_dates(stay)
    demand = (sug.get("demand_analysis") or sug.get("customer_profile") or "").strip()
    solution = (sug.get("solution_analysis") or sug.get("hotel_profile") or "").strip()
    rationale = (sug.get("rationale") or "").strip()
    priority = str(sug.get("priority") or "P1")
    if priority not in ("P0", "P1", "P2"):
        priority = "P1"
    score = str(sug.get("score") or "")
    ttv = str(sug.get("expected_ttv") or "")
    gp = gp_from_ttv(ttv) or str(sug.get("expected_gp") or "")
    plan["source"].update({
        "plan_source": "ai_intel",
        "source_detail": source_title,
        "priority": priority,
        "owner": "营销师",
    })
    plan["basic"].update({
        "campaign_name": (sug.get("campaign_name") or "").strip(),
        "target_dest": dest,
        "promotion_month": month_label,
        "promotion_time": stay,
        "start_date": go_live,
        "end_date": stay_dates[-1] if stay_dates else "",
        "campaign_type": "组合活动",
    })
    plan["background"].update({
        "market_context": rationale,
        "business_trigger": rationale,
        "opportunity": rationale,
        "summary": rationale,
    })
    plan["data_insights"].update({
        "market_data": rationale,
        "client_behavior_data": demand,
        "data_conclusion": demand or rationale,
    })
    plan["objectives"].update({
        "primary_goal": f"TTV {ttv} / GP {gp}".strip(" /") if (ttv or gp) else rationale,
        "target_metrics": "；".join(x for x in (f"TTV {ttv}" if ttv else "", f"GP {gp}" if gp else "") if x) or "订单数、TTV、转化率",
        "ttv_target": ttv,
        "gp_target": gp,
    })
    plan["strategy"].update({
        "theme": sug.get("campaign_name") or "",
        "solution_summary": solution,
        "key_mechanics": solution,
        "core_message": rationale,
    })
    plan["customer_segment"].update({
        "segment_name": f"{dest} B端采购客户",
        "description": demand,
        "pain_points": demand,
        "selection_rationale": demand,
        "geo_focus": dest,
        "locked_client_ids": [],
    })
    plan["hotel_solution"].update({
        "selection_strategy": solution,
        "hotel_criteria": solution,
        "recommended_types": solution,
        "locked_hotel_ids": [],
    })
    plan["forecast"].update({
        "expected_ttv": ttv,
        "expected_gp": gp,
        "expected_roi": GP_RATE_LABEL if gp else "",
        "value_proposition": rationale,
    })
    plan["task_board"]["launch_date"] = go_live
    plan["ai_provenance"].update({
        "ai_rationale": rationale,
        "intel_source": source_title,
        "confidence": f"{score}/100 · {priority}" if str(score).isdigit() else priority,
    })
    return plan


GP_TABLE_ROW = re.compile(
    r"(\|\s*\*\*预期GP\*\*\s*\|\s*)([^|]+?)(\s*\|)([^|\n]*)(\|)"
)
GP_INLINE = re.compile(r"(\*\*GP\*\*[：:]\s*)([0-9,\.\-—~至到]+万)")


def _gp_note(old_note: str) -> str:
    note = (old_note or "").strip()
    extra = ""
    if "促销" in note:
        extra = "（促销让利）"
    elif any(x in note for x in ("走量", "毛利低", "毛利率略低", "周转")):
        extra = "（走量/周转快）"
    elif "商旅" in note:
        extra = "（商旅量大）"
    if extra or re.search(r"ROI|毛利|GP率", note) or not note:
        return f" {GP_RATE_LABEL}{extra} "
    return f" {GP_RATE_LABEL}；{note} "


def rewrite_gp_in_markdown(text: str) -> str:
    """按 TTV × 1%–2% 重写月度决策卡里的预期 GP。"""
    chunks = re.split(r"(^## 活动\d+[：:].+$)", text, flags=re.M)
    out = [chunks[0]]
    for i in range(1, len(chunks), 2):
        title = chunks[i]
        body = chunks[i + 1] if i + 1 < len(chunks) else ""
        ttv_m = re.search(r"\|\s*\*\*预期TTV\*\*\s*\|\s*([^|]+)\|", body)
        gp = gp_from_ttv(ttv_m.group(1) if ttv_m else "")
        if gp:
            body = GP_TABLE_ROW.sub(
                lambda m, g=gp: f"{m.group(1)}{g}{m.group(3)}{_gp_note(m.group(4))}{m.group(5)}",
                body,
            )
            body = GP_INLINE.sub(lambda m, g=gp: f"{m.group(1)}{g}", body)
        out.extend([title, body])
    return "".join(out)
