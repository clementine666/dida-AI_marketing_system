"""资源准备分析：同一套线下 QBI 七步，两条入口。

自动抓取：读日历城市/月/客群/主题 → MCP/本地拉数 → 七段结论。
看板筛选：人改时间/国家/城市/客群后重跑，用来核对自动结果。
两条入口写入同一套七页签，不锁客户/酒店 ID。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.db import get_engine
from app.mcp.warehouse_client import WarehouseClient
from app.mcp.warehouse_schema import DESTINATION_KEYWORDS
from app.services.v2.agent1_planner import PlannerService


HOTEL_TAG_HH = "高需求高转化"
HOTEL_TAG_HL = "高需求低转化"
HOTEL_TAG_LH = "低需求高转化"
HOTEL_TAG_LL = "低需求低转化"
HOTEL_TAG_NONE = "无产"
THEME_HINTS = ("F1", "赛事", "节", "圣诞", "春节", "黄金周", "开斋", "樱花")


def _pct(values: list[float], p: float) -> float:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    if lo == hi:
        return float(xs[lo])
    return float(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def _month(val: Any) -> int | None:
    if val is None or val == "":
        return None
    if isinstance(val, int) and 1 <= val <= 12:
        return val
    m = re.search(r"(\d{1,2})", str(val))
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= 12 else None


def _date(val: Any) -> date | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def _keywords(destination: str) -> list[str]:
    dest = (destination or "").strip()
    if not dest:
        return []
    for key, kws in DESTINATION_KEYWORDS.items():
        if key.lower() in dest.lower() or dest.lower() in key.lower():
            return list(dict.fromkeys(kws + [dest]))
    return [dest]


def _biz_type(client_id: str | None, client_name: str | None, group_cn: str | None = None) -> str:
    blob = f"{client_id or ''} {client_name or ''} {group_cn or ''}".upper()
    if any(k in blob for k in ("TMC", "差旅", "商旅", "TRAVEL MANAGEMENT")):
        return "TMC"
    if any(k in blob for k in ("定制", "FIT", "休闲", "CUSTOM")):
        return "定制"
    return "其他"


class ResourcePrepAnalysisService:
    """读活动城市 → MCP/本地拉数 → 按线下七步输出分析结果。"""

    def __init__(self):
        self.engine = get_engine()
        self.warehouse = WarehouseClient(self.engine)
        self.planner = PlannerService(self.engine)

    def analyze_campaign(
        self, campaign_id: str, *, overrides: dict | None = None, with_llm: bool = True
    ) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        structured = self.planner.build_structured_plan(plan)
        basic = structured.get("basic") or {}
        cs = structured.get("customer_segment") or {}
        ov = overrides or {}
        cal_dest = basic.get("target_dest") or plan.get("target_dest") or cs.get("geo_focus") or ""
        dest = (ov.get("city") or ov.get("destination") or ov.get("country") or cal_dest or "").strip()
        cust = ov.get("customer_type")
        if cust in (None, "", "全部", "all"):
            cust = cs.get("segment_name") or cs.get("client_groups") or ""
        result = self.analyze(
            destination=dest,
            promotion_month=ov.get("promotion_month") or basic.get("promotion_month") or plan.get("promotion_month"),
            customer_type=cust,
            campaign_name=basic.get("campaign_name") or plan.get("campaign_name") or "",
            date_from=_date(ov.get("date_from")),
            date_to=_date(ov.get("date_to")),
            country=ov.get("country") or "",
            city=ov.get("city") or "",
            with_llm=with_llm and ov.get("mode") != "manual",
        )
        result["campaign_id"] = campaign_id
        result["mode"] = ov.get("mode") or "auto"
        result["filters"] = {
            "country": ov.get("country") or "",
            "city": ov.get("city") or dest,
            "date_from": ov.get("date_from") or "",
            "date_to": ov.get("date_to") or "",
            "customer_type": ov.get("customer_type") or "全部",
        }
        result["calendar_inputs"] = {
            "destination": cal_dest,
            "promotion_month": _month(basic.get("promotion_month") or plan.get("promotion_month")),
            "customer_segment": cs.get("segment_name") or cs.get("client_groups") or "",
            "theme": basic.get("campaign_name") or plan.get("campaign_name"),
        }
        return result

    def analyze(
        self,
        *,
        destination: str,
        promotion_month: int | str | None = None,
        customer_type: str | None = None,
        campaign_name: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
        country: str = "",
        city: str = "",
        with_llm: bool = True,
    ) -> dict:
        dest = (destination or "").strip()
        if not dest:
            return {"ok": False, "error": "请填写国家或城市"}
        kws = _keywords(dest)
        for extra in (country, city):
            if extra and extra.strip() and extra.strip().lower() not in {k.lower() for k in kws}:
                kws.extend(_keywords(extra.strip()))
        promo = _month(promotion_month)
        orders, funnel, source = self._load_facts(kws)
        years = sorted({d.year for o in orders if (d := _date(o.get("check_out_date")))})
        lookback = years[-2] if len(years) >= 2 else (years[-1] if years else date.today().year)
        year_orders = [o for o in orders if (d := _date(o.get("check_out_date"))) and d.year == lookback]
        if not year_orders:
            year_orders = orders
            lookback = years[-1] if years else date.today().year

        monthly = self._monthly(year_orders)
        peak = max(monthly, key=lambda m: monthly[m]["orders"]) if monthly else promo
        themed = any(k in (campaign_name or "") for k in THEME_HINTS)
        stay = promo if (themed and promo) else (peak or promo or date.today().month)
        if date_from or date_to:
            stay_orders = [
                o for o in orders
                if (d := _date(o.get("check_out_date")))
                and (not date_from or d >= date_from)
                and (not date_to or d <= date_to)
            ]
        else:
            stay_orders = [o for o in year_orders if (d := _date(o.get("check_out_date"))) and d.month == stay]
        extra_country, extra_city = country, city
        if extra_country:
            stay_orders = [
                o for o in stay_orders
                if extra_country.lower() in str(o.get("country_name") or "").lower()
            ]
        if extra_city:
            stay_orders = [
                o for o in stay_orders
                if extra_city.lower() in str(o.get("destination_name") or o.get("city_name") or "").lower()
            ]

        geo_orders = stay_orders if (date_from or date_to or extra_country or extra_city) else year_orders
        timing = self._timing(stay_orders, lookback, stay, peak, promo, themed)
        country = self._geo(geo_orders, "country_name", "国家")
        city = self._geo(geo_orders, "destination_name", "城市")
        dest_segment = self._dest_segment(stay_orders, customer_type)
        trend = self._trend(monthly, stay, peak)
        hotels = self._hotel_tier(stay_orders, funnel)
        grain = self._segment_country_hotel(hotels)
        motivation = self._motivation(dest, kws, lookback, stay, peak, promo, themed)
        conclusion = self._rule_conclusion(
            dest, lookback, stay, peak, promo, themed, timing, hotels, dest_segment, motivation
        )
        if with_llm:
            conclusion = self._llm_conclusion(conclusion, dest, campaign_name) or conclusion

        sections = [
            {"id": "timing", "title": "1. 活动时机分析", "result": timing},
            {"id": "country", "title": "2. 国家需求分析", "result": country},
            {"id": "city", "title": "3. 城市需求分析", "result": city},
            {"id": "dest_segment", "title": "4. 目的地 × 客群", "result": dest_segment},
            {"id": "trend", "title": "5. 需求趋势分析", "result": trend},
            {"id": "hotel_tier", "title": "6. 酒店需求分层分析", "result": hotels},
            {"id": "grain", "title": "7. 客群 × 国家 × 酒店", "result": grain},
        ]
        return {
            "ok": True,
            "method": "offline_qbi",
            "data_source": source,
            "destination": dest,
            "lookback_year": lookback,
            "order_count_year": len(year_orders),
            "order_count_window": len(stay_orders),
            "sections": sections,
            "timing": timing,
            "country": country,
            "city": city,
            "dest_segment": dest_segment,
            "trend": trend,
            "hotels": hotels,
            "grain": grain,
            "motivation": motivation,
            "conclusion": conclusion,
            "task_outputs": {
                "A": timing.get("summary"),
                "B": hotels.get("summary"),
                "C": dest_segment.get("summary"),
                "D": timing.get("go_live_summary"),
            },
        }

    def apply_to_campaign(
        self, campaign_id: str, operator: str = "marketer", overrides: dict | None = None
    ) -> dict:
        insight = self.analyze_campaign(campaign_id, overrides=overrides)
        if not insight.get("ok"):
            return insight
        plan = self.planner.get_activity_plan(campaign_id)
        structured = self.planner.build_structured_plan(plan)
        data = structured.setdefault("data_insights", {})
        data["demand_pack"] = {
            "method": insight.get("method"),
            "mode": insight.get("mode"),
            "filters": insight.get("filters"),
            "data_source": insight.get("data_source"),
            "lookback_year": insight.get("lookback_year"),
            "task_outputs": insight.get("task_outputs"),
            "hotels": {
                "p80_request_pv": (insight.get("hotels") or {}).get("p80_request_pv"),
                "p80_rns": (insight.get("hotels") or {}).get("p80_rns"),
                "tag_counts": (insight.get("hotels") or {}).get("tag_counts"),
                "candidate_ids": (insight.get("hotels") or {}).get("candidate_ids"),
            },
            "clients": (insight.get("dest_segment") or {}).get("ids") or [],
        }
        data["market_data"] = (insight.get("trend") or {}).get("summary") or ""
        data["client_behavior_data"] = (insight.get("dest_segment") or {}).get("summary") or ""
        data["data_conclusion"] = insight.get("conclusion") or ""
        hs = structured.setdefault("hotel_solution", {})
        hs["selection_strategy"] = (insight.get("hotels") or {}).get("summary") or hs.get("selection_strategy")
        hs["inventory_notes"] = (insight.get("hotels") or {}).get("summary") or ""
        hs["candidate_hotel_ids"] = (insight.get("hotels") or {}).get("candidate_ids") or []
        cs = structured.setdefault("customer_segment", {})
        cs["behaviors"] = (insight.get("dest_segment") or {}).get("summary") or cs.get("behaviors")
        cs["candidate_client_ids"] = (insight.get("dest_segment") or {}).get("ids") or []
        saved = self.planner.save_structured_plan(campaign_id, structured, editor=operator)
        self._store_pack(campaign_id, insight)
        return {"ok": True, "campaign_id": campaign_id, "saved": saved.get("ok"), "insight": insight}

    def _dest_sql(self, columns: list[str], keywords: list[str], params: dict, prefix: str) -> str:
        parts = []
        for i, kw in enumerate(keywords):
            key = f"{prefix}{i}"
            params[key] = f"%{kw}%"
            parts.append("(" + " OR ".join(f"{c} LIKE :{key}" for c in columns) + ")")
        return "(" + " OR ".join(parts) + ")" if parts else "1=0"

    def _load_facts(self, keywords: list[str]) -> tuple[list[dict], list[dict], str]:
        orders, funnel = [], []
        source = self.warehouse.mode
        if not self.warehouse.use_local and self.warehouse.mcp.is_configured:
            try:
                orders, funnel = self._load_mcp(keywords)
                source = "warehouse_mcp"
            except Exception:
                orders, funnel = [], []
                source = "local_sqlite_fallback"
        if not orders:
            orders = self._local_orders(keywords)
            source = "local_sqlite" if self.warehouse.use_local else source
        if not funnel:
            funnel = self._local_funnel(keywords)
        return orders, funnel, source

    def _load_mcp(self, keywords: list[str]) -> tuple[list[dict], list[dict]]:
        like = " OR ".join(
            f"country_name ILIKE '%{kw.replace(chr(39), '')}%' OR city_name ILIKE '%{kw.replace(chr(39), '')}%'"
            for kw in keywords
        )
        funnel_sql = f"""
        SELECT CAST(dida_hotel_id AS TEXT) AS hotel_id,
               MAX(dida_hotel_name) AS hotel_name,
               MAX(country_code) AS country_code,
               MAX(country_name) AS country_name,
               MAX(city_name) AS city_name,
               MAX(star_rating) AS star_rating,
               MAX(chain_name) AS chain_name,
               COUNT(DISTINCT CASE WHEN step_code = 'request' THEN pv_key END) AS request_pv,
               COUNT(DISTINCT CASE WHEN step_code IN ('available','expose') THEN pv_key END) AS valid_search_pv,
               COUNT(DISTINCT CASE WHEN step_code = 'success' THEN pv_key END) AS order_success_pv
        FROM {self.warehouse.tables['funnel']} f
        WHERE ({like}) AND (is_test_account IS NULL OR is_test_account = false)
        GROUP BY dida_hotel_id
        """
        funnel = self.warehouse.mcp.execute_sql(
            funnel_sql, tables=[self.warehouse.tables["funnel"]], data_type=3
        )
        order_like = " OR ".join(
            f"didahotelcountryname_en ILIKE '%{kw.replace(chr(39), '')}%' "
            f"OR didahoteldestinationname_cn ILIKE '%{kw.replace(chr(39), '')}%'"
            for kw in keywords
        )
        orders_sql = f"""
        SELECT clientid AS client_id, CAST(didahotelid AS TEXT) AS dida_hotel_id,
               didahotelname_cn AS dida_hotel_name, didahotelchainname AS dida_hotel_chain,
               didahotelstarrating AS dida_hotel_star, didahotelcountryname_en AS country_name,
               didahoteldestinationname_cn AS destination_name, checkoutdate AS check_out_date,
               checkindate AS check_in_date, roomnightcount AS room_night_count,
               pricecny AS price_cny, combinedrevenuecny AS combined_revenue_cny,
               kpirevenuecny AS kpi_revenue_cny, leadtimehour AS lead_time_hour,
               createtime AS create_time
        FROM {self.warehouse.tables['orders']}
        WHERE {order_like}
        LIMIT 20000
        """
        try:
            orders = self.warehouse.mcp.execute_sql(
                orders_sql, tables=[self.warehouse.tables["orders"]], data_type=2
            )
        except Exception:
            orders = []
        return orders or [], funnel or []

    def _local_orders(self, keywords: list[str]) -> list[dict]:
        params: dict[str, Any] = {}
        where = self._dest_sql(["country_name", "destination_name"], keywords, params, "o")
        sql = f"""
        SELECT order_number, client_id, client_name, dida_hotel_id, dida_hotel_name,
               dida_hotel_chain, dida_hotel_star, country_name, destination_name,
               check_in_date, check_out_date, room_night_count, price_cny,
               combined_revenue_cny, kpi_revenue_cny, lead_time_hour, create_time
        FROM fact_orders WHERE {where}
        """
        try:
            with self.engine.connect() as conn:
                return [dict(r._mapping) for r in conn.execute(text(sql), params)]
        except Exception:
            return []

    def _local_funnel(self, keywords: list[str]) -> list[dict]:
        params: dict[str, Any] = {}
        where = self._dest_sql(["country_name", "city_name", "country_code"], keywords, params, "f")
        sql = f"""
        SELECT CAST(dida_hotel_id AS TEXT) AS hotel_id,
               MAX(dida_hotel_name) AS hotel_name, MAX(country_code) AS country_code,
               MAX(country_name) AS country_name, MAX(city_name) AS city_name,
               MAX(star_rating) AS star_rating, MAX(chain_name) AS chain_name,
               COUNT(DISTINCT CASE WHEN step_code = 'request' THEN pv_key END) AS request_pv,
               COUNT(DISTINCT CASE WHEN step_code IN ('available','expose') THEN pv_key END) AS valid_search_pv,
               COUNT(DISTINCT CASE WHEN step_code = 'success' THEN pv_key END) AS order_success_pv
        FROM fact_funnel WHERE {where}
          AND (is_test_account IS NULL OR is_test_account = 0)
        GROUP BY dida_hotel_id
        """
        try:
            with self.engine.connect() as conn:
                return [dict(r._mapping) for r in conn.execute(text(sql), params)]
        except Exception:
            return []

    def _monthly(self, orders: list[dict]) -> dict[int, dict]:
        buckets: dict[int, dict] = {}
        for o in orders:
            d = _date(o.get("check_out_date"))
            if not d:
                continue
            b = buckets.setdefault(
                d.month, {"month": d.month, "label": f"{d.month}月", "orders": 0, "rns": 0, "ttv": 0.0}
            )
            b["orders"] += 1
            b["rns"] += int(o.get("room_night_count") or 0)
            b["ttv"] += float(o.get("combined_revenue_cny") or 0)
        for b in buckets.values():
            b["ttv"] = round(b["ttv"], 2)
        return buckets

    def _timing(self, stay_orders, year, stay_month, peak, promo, themed) -> dict:
        leads: list[float] = []
        book_months: Counter[int] = Counter()
        for o in stay_orders:
            hours = o.get("lead_time_hour")
            created, checkout = _date(o.get("create_time")), _date(o.get("check_out_date"))
            if hours is not None:
                try:
                    leads.append(float(hours) / 24.0)
                except (TypeError, ValueError):
                    pass
            elif created and checkout:
                leads.append(float((checkout - created).days))
            if created:
                book_months[created.month] += 1
        median = round(_pct(leads, 0.5), 1) if leads else None
        stay_start = date(year, stay_month, 1)
        stay_end = date(year, 12, 31) if stay_month == 12 else date(year, stay_month + 1, 1) - timedelta(days=1)
        go_live = (stay_start - timedelta(days=int(round(median)))).isoformat() if median is not None else None
        book_peak = book_months.most_common(1)[0][0] if book_months else None
        return {
            "peak_checkout_month": peak,
            "calendar_month": promo,
            "stay_month": stay_month,
            "aligned": promo is None or promo == peak,
            "themed_event": themed,
            "median_lead_days": median,
            "p25_lead_days": round(_pct(leads, 0.25), 1) if leads else None,
            "p75_lead_days": round(_pct(leads, 0.75), 1) if leads else None,
            "booking_peak_month": book_peak,
            "suggested_go_live": go_live,
            "suggested_go_offline": stay_end.isoformat(),
            "summary": (
                f"{year}年离店高峰 {peak}月；建议活动覆盖停留 {stay_month}月，"
                f"上线 {go_live or '待定'}（中位提前 {median} 天）"
            ),
            "go_live_summary": (
                f"预订高峰 {book_peak or '—'}月，相对离店提前 {median} 天，建议上线 {go_live or '待定'}"
            ),
        }

    def _geo(self, orders: list[dict], field: str, label: str) -> dict:
        agg: dict[str, dict] = {}
        for o in orders:
            key = str(o.get(field) or "未知")
            row = agg.setdefault(key, {"name": key, "orders": 0, "rns": 0, "ttv": 0.0})
            row["orders"] += 1
            row["rns"] += int(o.get("room_night_count") or 0)
            row["ttv"] += float(o.get("combined_revenue_cny") or 0)
        ranked = sorted(agg.values(), key=lambda x: -x["rns"])
        for r in ranked:
            r["ttv"] = round(r["ttv"], 2)
        top = ranked[0]["name"] if ranked else "—"
        return {
            "label": label,
            "top": top,
            "rows": ranked[:12],
            "summary": f"{label}需求最高：{top}（按间夜）" if ranked else f"{label}样本不足",
        }

    def _dest_segment(self, stay_orders: list[dict], customer_type: str | None) -> dict:
        mix: Counter[str] = Counter()
        clients: dict[str, dict] = {}
        for o in stay_orders:
            cid = str(o.get("client_id") or "")
            if not cid:
                continue
            biz = _biz_type(cid, o.get("client_name"))
            mix[biz] += 1
            row = clients.setdefault(
                cid,
                {"client_id": cid, "client_name": o.get("client_name"), "biz_type": biz, "orders": 0, "rns": 0},
            )
            row["orders"] += 1
            row["rns"] += int(o.get("room_night_count") or 0)
        want = None
        if customer_type:
            up = customer_type.upper()
            if "TMC" in up:
                want = "TMC"
            elif "定制" in customer_type:
                want = "定制"
        listed = sorted(clients.values(), key=lambda c: -c["rns"])
        if want:
            listed = [c for c in listed if c["biz_type"] == want] or listed
        total = max(sum(mix.values()), 1)
        mix_rows = [{"type": k, "count": v, "share_pct": round(v * 100 / total, 1)} for k, v in mix.most_common()]
        mix_txt = "、".join(f"{x['type']}{x['share_pct']}%" for x in mix_rows) or "—"
        return {
            "filter": want,
            "biz_type_mix": mix_rows,
            "client_count": len(listed),
            "ids": [c["client_id"] for c in listed[:200]],
            "preview": listed[:15],
            "summary": f"高峰窗机构 {len(listed)} 家（{mix_txt}）",
        }

    def _trend(self, monthly: dict[int, dict], stay: int, peak: int | None) -> dict:
        curve = [monthly[m] for m in range(1, 13) if m in monthly]
        stay_rns = (monthly.get(stay) or {}).get("rns", 0)
        peak_rns = (monthly.get(peak) or {}).get("rns", 0) if peak else 0
        if peak and stay == peak:
            season = "旺季"
        elif peak_rns and stay_rns >= peak_rns * 0.6:
            season = "次旺"
        else:
            season = "淡季"
        return {
            "season_label": season,
            "curve": curve,
            "summary": f"停留月属{season}；离店曲线共 {len(curve)} 个月有产",
        }

    def _hotel_tier(self, stay_orders: list[dict], funnel_rows: list[dict]) -> dict:
        by_id: dict[str, dict] = {}
        for f in funnel_rows:
            hid = str(f.get("hotel_id") or "")
            if not hid or hid == "None":
                continue
            by_id[hid] = {
                "dida_hotel_id": hid,
                "dida_hotel_name": f.get("hotel_name"),
                "country_code": f.get("country_code"),
                "city_name": f.get("city_name"),
                "star": f.get("star_rating"),
                "chain": f.get("chain_name"),
                "request_pv": int(f.get("request_pv") or 0),
                "valid_search_pv": int(f.get("valid_search_pv") or 0),
                "order_success_pv": int(f.get("order_success_pv") or 0),
                "bks": 0, "rns": 0, "ttv": 0.0, "gp": 0.0, "prices": [],
            }
        for o in stay_orders:
            hid = str(o.get("dida_hotel_id") or "")
            if not hid:
                continue
            row = by_id.setdefault(hid, {
                "dida_hotel_id": hid, "dida_hotel_name": o.get("dida_hotel_name"),
                "country_code": None, "city_name": o.get("destination_name"),
                "star": o.get("dida_hotel_star"), "chain": o.get("dida_hotel_chain"),
                "request_pv": 0, "valid_search_pv": 0, "order_success_pv": 0,
                "bks": 0, "rns": 0, "ttv": 0.0, "gp": 0.0, "prices": [],
            })
            row["dida_hotel_name"] = row["dida_hotel_name"] or o.get("dida_hotel_name")
            row["star"] = row["star"] or o.get("dida_hotel_star")
            row["chain"] = row["chain"] or o.get("dida_hotel_chain")
            row["bks"] += 1
            row["rns"] += int(o.get("room_night_count") or 0)
            row["ttv"] += float(o.get("combined_revenue_cny") or 0)
            row["gp"] += float(o.get("kpi_revenue_cny") or 0)
            if o.get("price_cny"):
                nights = max(int(o.get("room_night_count") or 1), 1)
                try:
                    row["prices"].append(float(o["price_cny"]) / nights)
                except (TypeError, ValueError):
                    pass
        hotels = list(by_id.values())
        demand_vals = [h["request_pv"] for h in hotels if h["request_pv"] > 0] or [
            h["bks"] for h in hotels if h["bks"] > 0
        ]
        conv_vals = [h["rns"] for h in hotels if h["rns"] > 0]
        p80_pv, p80_rn = round(_pct(demand_vals, 0.8), 2), round(_pct(conv_vals, 0.8), 2)
        use_pv = any(h["request_pv"] > 0 for h in hotels)
        tags: Counter[str] = Counter()
        stars, chains = Counter(), Counter()
        for h in hotels:
            demand = h["request_pv"] if use_pv else h["bks"]
            rns = h["rns"]
            if rns <= 0 and demand <= 0:
                tag = HOTEL_TAG_NONE
            elif rns <= 0:
                tag = HOTEL_TAG_HL if demand >= p80_pv else HOTEL_TAG_NONE
            elif demand >= p80_pv and rns >= p80_rn:
                tag = HOTEL_TAG_HH
            elif demand >= p80_pv:
                tag = HOTEL_TAG_HL
            elif rns >= p80_rn:
                tag = HOTEL_TAG_LH
            else:
                tag = HOTEL_TAG_LL
            h["hotel_tag"] = tag
            h["avg_price_cny"] = round(sum(h["prices"]) / len(h["prices"]), 2) if h["prices"] else None
            h["ttv"] = round(h["ttv"], 2)
            h["gp"] = round(h["gp"], 2)
            del h["prices"]
            tags[tag] += 1
            if rns > 0:
                stars[str(h.get("star") or "未知")] += 1
                chains[str(h.get("chain") or "独立")] += 1
        producing = [h for h in hotels if h["rns"] > 0]
        ranked = sorted(
            producing or hotels,
            key=lambda h: (
                0 if h["hotel_tag"] == HOTEL_TAG_HL else 1 if h["hotel_tag"] == HOTEL_TAG_HH else 2,
                -(h["request_pv"] or h["bks"]),
            ),
        )
        prices = [h["avg_price_cny"] for h in producing if h.get("avg_price_cny")]
        return {
            "p80_request_pv": p80_pv,
            "p80_rns": p80_rn,
            "demand_metric": "request_pv" if use_pv else "bookings",
            "hotel_count": len(hotels),
            "producing_count": len(producing),
            "tag_counts": dict(tags),
            "star_distribution": dict(stars),
            "chain_distribution": dict(chains.most_common(8)),
            "price_p25": round(_pct(prices, 0.25), 0) if prices else None,
            "price_p75": round(_pct(prices, 0.75), 0) if prices else None,
            "candidate_ids": [h["dida_hotel_id"] for h in ranked[:30]],
            "top_hotels": ranked[:15],
            "summary": (
                f"有产 {len(producing)} 家；P80 PV={p80_pv} / RNs={p80_rn}；"
                f"{HOTEL_TAG_HL} {tags.get(HOTEL_TAG_HL, 0)} 家（投放主靶）"
            ),
        }

    def _segment_country_hotel(self, hotels: dict) -> dict:
        rows = []
        for h in (hotels.get("top_hotels") or [])[:12]:
            rows.append({
                "dida_hotel_id": h["dida_hotel_id"],
                "dida_hotel_name": h.get("dida_hotel_name"),
                "city_name": h.get("city_name"),
                "hotel_tag": h.get("hotel_tag"),
                "request_pv": h.get("request_pv"),
                "bks": h.get("bks"),
                "rns": h.get("rns"),
                "ttv": h.get("ttv"),
                "gp": h.get("gp"),
            })
        return {"rows": rows, "summary": f"明细 {len(rows)} 家（优先 {HOTEL_TAG_HL}）"}

    def _motivation(self, dest, keywords, year, stay, peak, promo, themed) -> dict:
        notes = [
            f"{year}年{dest}离店最高月 {peak}月" if peak else "离店样本不足",
            f"日历月 {promo}月 与高峰 {'一致' if promo == peak else '不一致'}" if promo else "日历未写月份",
            "主题活动跟日历窗口" if themed else "非主题，窗口跟离店高峰",
        ]
        return {
            "notes": notes,
            "events": self._named_rows(
                "dim_destination_events", "destination", "event_name", "start_date", keywords, stay
            ),
            "holidays": self._named_rows(
                "dim_holiday", "country", "holiday_name", "holiday_date", keywords, stay
            ),
        }

    def _named_rows(
        self, table: str, dest_col: str, name_col: str, date_col: str, keywords: list[str], month: int
    ) -> list[str]:
        params: dict[str, Any] = {"month": f"{month:02d}"}
        where = self._dest_sql([dest_col], keywords, params, table[:1])
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT {name_col} AS nm, {date_col} AS dt FROM {table} "
                        f"WHERE {where} AND strftime('%m', {date_col}) = :month"
                    ),
                    params,
                ).mappings()
            return [f"{r['nm']} {r['dt']}" for r in rows]
        except Exception:
            return []

    def _rule_conclusion(self, dest, year, stay, peak, promo, themed, timing, hotels, segment, motivation) -> str:
        return (
            f"{dest} {year}年离店高峰 {peak}月（日历 {promo or '—'}月；"
            f"{'主题跟日历' if themed else '窗口跟高峰'}）。"
            f"{timing.get('summary')}。{hotels.get('summary')}。{segment.get('summary')}。"
            f"{'；'.join((motivation or {}).get('notes') or [])}。"
        )

    def _llm_conclusion(self, draft: str, dest: str, campaign_name: str) -> str | None:
        try:
            from app.integrations.llm_client import LlmClient
            llm = LlmClient()
            if not llm.is_configured():
                return None
            text = llm.chat([
                {"role": "system", "content": "你是道旅营销资源分析。用两三句中文总结动机：为何在该城该月做活动。不要编造数字。"},
                {"role": "user", "content": f"活动：{campaign_name}\n城市：{dest}\n数据结论：{draft}"},
            ])
            return (text or "").strip() or None
        except Exception:
            return None

    def _store_pack(self, campaign_id: str, insight: dict) -> None:
        with self.engine.begin() as conn:
            row = conn.execute(
                text("SELECT resource_plan_json FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": campaign_id},
            ).fetchone()
            rp = {}
            if row and row[0]:
                try:
                    rp = json.loads(row[0]) if isinstance(row[0], str) else dict(row[0])
                except Exception:
                    rp = {}
            rp["resource_prep_analysis"] = {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "mode": insight.get("mode") or "auto",
                "filters": insight.get("filters") or {},
                "calendar_inputs": insight.get("calendar_inputs") or {},
                "data_source": insight.get("data_source"),
                "destination": insight.get("destination"),
                "lookback_year": insight.get("lookback_year"),
                "conclusion": insight.get("conclusion"),
                "task_outputs": insight.get("task_outputs"),
                "timing": insight.get("timing"),
                "trend": {
                    "season_label": (insight.get("trend") or {}).get("season_label"),
                    "summary": (insight.get("trend") or {}).get("summary"),
                    "curve": (insight.get("trend") or {}).get("curve"),
                },
                "dest_segment": {
                    "summary": (insight.get("dest_segment") or {}).get("summary"),
                    "biz_type_mix": (insight.get("dest_segment") or {}).get("biz_type_mix"),
                    "client_count": (insight.get("dest_segment") or {}).get("client_count"),
                    "preview": (insight.get("dest_segment") or {}).get("preview"),
                },
                "hotels": {
                    "summary": (insight.get("hotels") or {}).get("summary"),
                    "p80_request_pv": (insight.get("hotels") or {}).get("p80_request_pv"),
                    "p80_rns": (insight.get("hotels") or {}).get("p80_rns"),
                    "tag_counts": (insight.get("hotels") or {}).get("tag_counts"),
                    "star_distribution": (insight.get("hotels") or {}).get("star_distribution"),
                    "chain_distribution": (insight.get("hotels") or {}).get("chain_distribution"),
                    "producing_count": (insight.get("hotels") or {}).get("producing_count"),
                    "candidate_ids": (insight.get("hotels") or {}).get("candidate_ids"),
                    "top_hotels": (insight.get("hotels") or {}).get("top_hotels"),
                },
                "grain": insight.get("grain"),
                "country": {"summary": (insight.get("country") or {}).get("summary"), "rows": (insight.get("country") or {}).get("rows")},
                "city": {"summary": (insight.get("city") or {}).get("summary"), "rows": (insight.get("city") or {}).get("rows")},
                "hotel_candidates": (insight.get("hotels") or {}).get("candidate_ids") or [],
                "client_candidates": (insight.get("dest_segment") or {}).get("ids") or [],
            }
            conn.execute(
                text(
                    "UPDATE dim_campaign SET resource_plan_json = :rp, updated_at = CURRENT_TIMESTAMP "
                    "WHERE campaign_id = :cid"
                ),
                {"rp": json.dumps(rp, ensure_ascii=False, default=str), "cid": campaign_id},
            )
