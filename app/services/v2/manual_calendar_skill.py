"""标准活动规划 Skill：MCP/本地数据 → A/B/C 分析 → 营销日历初版。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import text

from app.db import get_engine
from app.services.config_store import load_agent_config
from app.services.system_log import log

ROOT = Path(__file__).resolve().parents[3]
XLSX_DEFAULT = ROOT / "data" / "feishu_import" / "2027_calendar_workbook.xlsx"
MAPPING_JSON = ROOT / "data" / "feishu_import" / "continent_l2_mapping.json"
MAPPING_YAML = ROOT / "config" / "continent_l2_mapping.yaml"

MONTHS = [
    "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01",
    "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07",
]

SUGGESTION_PENDING = "pending"


@dataclass
class CalendarCandidate:
    analysis_unit: str
    continent: str
    unit_type: str
    target_checkout_month: str
    month_ttv: float
    month_share: float
    month_rank: int
    p75_days: float | None
    annual_p75: float | None
    countries: list[str] = field(default_factory=list)
    evidence: str = ""
    sub_theme: str = ""
    destinations: str = ""


class ManualCalendarSkillService:
    def __init__(self):
        self.engine = get_engine()

    def _resolved_fetch_prompt(self) -> str:
        """合并取数说明：优先单框 mcp_fetch_prompt，兼容旧版三字段。"""
        mc = self._manual_config()
        unified = (mc.get("mcp_fetch_prompt") or "").strip()
        if unified:
            return unified
        parts = [
            mc.get("fetch_checkout"),
            mc.get("fetch_booking"),
            mc.get("fetch_p75"),
            mc.get("mcp_query_profile"),
        ]
        return "\n\n".join(p.strip() for p in parts if p and str(p).strip())

    def _manual_config(self) -> dict:
        cfg = load_agent_config("agent1") or {}
        return cfg.get("manual_calendar") or {}

    def _months_from_config(self) -> list[str]:
        mc = self._manual_config()
        start = mc.get("data_window_start") or MONTHS[0]
        end = mc.get("data_window_end") or MONTHS[-1]
        if start in MONTHS and end in MONTHS:
            i0, i1 = MONTHS.index(start), MONTHS.index(end)
            if i0 <= i1:
                return MONTHS[i0 : i1 + 1]
        # 动态生成连续月（支持 2026-08 ~ 2027-07 等）
        try:
            from dateutil.relativedelta import relativedelta
            from datetime import datetime

            s = datetime.strptime(str(start).strip() + "-01", "%Y-%m-%d")
            e = datetime.strptime(str(end).strip() + "-01", "%Y-%m-%d")
            out: list[str] = []
            cur = s
            while cur <= e:
                out.append(cur.strftime("%Y-%m"))
                cur += relativedelta(months=1)
            return out or MONTHS
        except Exception:
            return MONTHS

    def _load_mapping(self) -> tuple[dict, dict, dict]:
        if MAPPING_YAML.exists():
            data = yaml.safe_load(MAPPING_YAML.read_text(encoding="utf-8")) or {}
            with_l2 = data.get("with_l2", {})
            blank_l2 = data.get("blank_l2", {})
            combined = data.get("combined_marketing_groups", {})
            if not blank_l2 and MAPPING_JSON.exists():
                blank_l2 = json.loads(MAPPING_JSON.read_text(encoding="utf-8")).get("blank_l2", {})
            return with_l2, blank_l2, combined
        data = json.loads(MAPPING_JSON.read_text(encoding="utf-8"))
        return data["with_l2"], data["blank_l2"], {}

    def _build_unit_map(self, with_l2: dict, blank_l2: dict) -> dict[str, dict[str, Any]]:
        units: dict[str, dict[str, Any]] = {}
        for cont, groups in with_l2.items():
            for l2, countries in groups.items():
                units[l2] = {"continent": cont, "type": "l2_group", "countries": list(countries)}
        for cont, countries in blank_l2.items():
            for c in countries:
                units[c] = {"continent": cont, "type": "country", "countries": [c]}
        return units

    def _load_checkout_df(self, xlsx: Path | None = None) -> pd.DataFrame:
        path = xlsx or XLSX_DEFAULT
        if not path.exists():
            raise FileNotFoundError(f"离店数据文件不存在: {path}")
        return pd.read_excel(path, sheet_name=0)

    def _load_p75_map(self, xlsx: Path | None = None) -> dict[str, dict[str, float | None]]:
        path = xlsx or XLSX_DEFAULT
        df = pd.read_excel(path, sheet_name=3, header=None)
        header = df.iloc[0].tolist()
        month_cols = [str(h).strip() for h in header[2:-1]]
        result: dict[str, dict[str, float | None]] = {}
        for i in range(1, len(df)):
            row = df.iloc[i].tolist()
            unit = row[1]
            if pd.isna(unit):
                continue
            unit = str(unit).strip()
            if unit == "总计":
                continue
            entry: dict[str, float | None] = {}
            for j, m in enumerate(month_cols):
                val = row[2 + j]
                try:
                    entry[m] = float(val) if pd.notna(val) else None
                except (TypeError, ValueError):
                    entry[m] = None
            try:
                entry["annual"] = float(row[-1]) if pd.notna(row[-1]) else None
            except (TypeError, ValueError):
                entry["annual"] = None
            result[unit] = entry
        return result

    def _aggregate_checkout(self, df: pd.DataFrame, units: dict, months: list[str] | None = None) -> pd.DataFrame:
        months = months or self._months_from_config()
        country_col, cont_col, c2_col = df.columns[2], df.columns[3], df.columns[4]
        ttv_col, bks_col = df.columns[5], df.columns[6]
        month_col = df.columns[0]
        country_to_unit = {c: u for u, meta in units.items() for c in meta["countries"]}
        rows = []
        for _, r in df.iterrows():
            month = str(r[month_col]).strip()
            if month not in months:
                continue
            country = str(r[country_col]).strip()
            if country not in country_to_unit:
                continue
            unit = country_to_unit[country]
            rows.append({
                "month": month,
                "unit": unit,
                "continent": units[unit]["continent"],
                "unit_type": units[unit]["type"],
                "ttv": float(r[ttv_col] or 0),
                "bks": float(r[bks_col] or 0),
            })
        if not rows:
            return pd.DataFrame(columns=["unit", "continent", "unit_type", "month", "ttv", "bks"])
        return pd.DataFrame(rows).groupby(["unit", "continent", "unit_type", "month"], as_index=False).agg(
            ttv=("ttv", "sum"), bks=("bks", "sum")
        )

    def _build_checkout_detail_table(
        self,
        checkout_rows: list[dict],
        units: dict,
        p75_map: dict,
        months: list[str],
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """对齐飞书「离店数据」行：checkout_month · 国家 · 归属洲 · 归属洲二 · total_ttv · total_bks · P75。"""
        country_to_unit = {c: u for u, meta in units.items() for c in meta["countries"]}
        out: list[dict[str, Any]] = []
        for r in checkout_rows:
            month = str(r.get("month", "")).strip()
            if month not in months:
                continue
            country = str(r.get("country", "")).strip()
            unit = country_to_unit.get(country) or country
            meta = units.get(unit, {"continent": "其他", "type": "country"})
            continent = meta.get("continent", "其他")
            l2 = unit if meta.get("type") == "l2_group" else ""
            p75 = p75_map.get(unit, {}).get(month) if unit in p75_map else None
            out.append({
                "checkout_month": month,
                "国家": country,
                "归属洲": continent,
                "归属洲二": l2 or "—",
                "total_ttv": round(float(r.get("ttv") or 0)),
                "total_bks": int(float(r.get("orders") or r.get("bks") or 0)),
                "leading_date_for_top75_percent": p75,
                "bks_until_75_percent": None,
            })
        out.sort(key=lambda x: (-x["total_ttv"], x["checkout_month"]))
        return out[:limit]

    def _load_checkout_detail_from_xlsx(self, months: list[str], limit: int = 50) -> list[dict]:
        """从飞书 Excel 底表读取含 bks_until_75 / leading_date 的原始行。"""
        xlsx = ROOT / "data" / "feishu_import" / "2027_calendar_workbook.xlsx"
        if not xlsx.exists():
            return []
        df = pd.read_excel(xlsx, sheet_name=0, header=0)
        if df.empty:
            return []
        month_col = df.columns[0]
        rows: list[dict] = []
        for _, r in df.iterrows():
            month = str(r[month_col]).strip()
            if month not in months:
                continue
            p75_col = df.columns[8] if len(df.columns) > 8 else None
            b75_col = df.columns[7] if len(df.columns) > 7 else None
            rows.append({
                "checkout_month": month,
                "国家": str(r[df.columns[2]]).strip(),
                "归属洲": str(r[df.columns[3]]).strip(),
                "归属洲二": str(r[df.columns[4]]).strip() if pd.notna(r[df.columns[4]]) else "—",
                "total_ttv": int(float(r[df.columns[5]] or 0)),
                "total_bks": int(float(r[df.columns[6]] or 0)),
                "bks_until_75_percent": int(float(r[b75_col])) if b75_col is not None and pd.notna(r[b75_col]) else None,
                "leading_date_for_top75_percent": float(r[p75_col]) if p75_col is not None and pd.notna(r[p75_col]) else None,
            })
        rows.sort(key=lambda x: -x["total_ttv"])
        return rows[:limit]

    def _month_label(self, month: str) -> str:
        return (
            month.replace("2025-", "2025年")
            .replace("2026-", "2026年")
            .replace("2027-", "2027年")
            + "月"
        )

    def _session_group(self, month: str) -> str:
        """飞书 A 列「活动场次」：按离店/上线月份。"""
        try:
            m = int(str(month).split("-", 1)[1])
            return f"{m}月场"
        except (IndexError, ValueError):
            return "待定场"

    def _build_ttv_share_table(
        self,
        agg: pd.DataFrame,
        months: list[str],
        *,
        top_units_per_continent: int = 5,
    ) -> list[dict[str, Any]]:
        """对齐飞书「离店TTV及占比」：归属洲 | 归属洲二 | 各月占比% | 总计(M)。"""
        if agg.empty:
            return []
        rows: list[dict[str, Any]] = []
        cont_totals = agg.groupby("continent")["ttv"].sum().sort_values(ascending=False)
        for cont in cont_totals.index:
            sub_cont = agg[agg["continent"] == cont]
            cont_by_month = sub_cont.groupby("month")["ttv"].sum()
            cont_total = float(cont_by_month.sum())
            cont_row: dict[str, Any] = {"归属洲": cont, "归属洲二": "总计", "总计_M": round(cont_total / 1e6, 2)}
            for m in months:
                pct = (float(cont_by_month.get(m, 0)) / cont_total * 100) if cont_total else 0
                cont_row[m] = f"{pct:.2f}%"
            rows.append(cont_row)
            top_units = (
                sub_cont.groupby("unit")["ttv"].sum().sort_values(ascending=False).head(top_units_per_continent).index
            )
            for unit in top_units:
                udf = sub_cont[sub_cont["unit"] == unit]
                u_total = float(udf["ttv"].sum())
                u_row: dict[str, Any] = {"归属洲": cont, "归属洲二": unit, "总计_M": round(u_total / 1e6, 2)}
                for m in months:
                    m_ttv = float(udf[udf["month"] == m]["ttv"].sum())
                    pct = (m_ttv / u_total * 100) if u_total else 0
                    u_row[m] = f"{pct:.2f}%"
                rows.append(u_row)
        return rows

    def _build_p75_table(
        self,
        p75_map: dict[str, dict[str, float | None]],
        agg: pd.DataFrame,
        months: list[str],
        *,
        top_units_per_continent: int = 5,
    ) -> list[dict[str, Any]]:
        """对齐飞书「提前预订P75」：归属洲 | 归属洲二 | 各月P75 | 全年P75。"""
        if agg.empty:
            return []
        rows: list[dict[str, Any]] = []
        cont_units = (
            agg.groupby(["continent", "unit"])["ttv"].sum().reset_index().sort_values("ttv", ascending=False)
        )
        seen_cont: set[str] = set()
        for cont in cont_units["continent"].unique():
            sub = cont_units[cont_units["continent"] == cont]
            top = sub.head(top_units_per_continent)["unit"].tolist()
            # 洲总计行（加权全年 P75 仅展示）
            if cont not in seen_cont:
                seen_cont.add(cont)
                cont_row: dict[str, Any] = {"归属洲": cont, "归属洲二": "总计", "全年P75": None}
                for m in months:
                    cont_row[m] = None
                rows.append(cont_row)
            for unit in top:
                entry = p75_map.get(unit, {})
                u_row: dict[str, Any] = {
                    "归属洲": cont,
                    "归属洲二": unit,
                    "全年P75": entry.get("annual"),
                }
                for m in months:
                    u_row[m] = entry.get(m)
                rows.append(u_row)
        return rows

    def _feishu_draft_row(self, c: CalendarCandidate) -> dict[str, Any]:
        """对齐飞书「27年营销日历初版」A–O 列 + 系统 legacy 字段。"""
        checkout = self._month_label(c.target_checkout_month) + "离店"
        return {
            "活动场次": self._session_group(c.target_checkout_month),
            "月度主活动主题": "",
            "副活动主题(按目的地/区域)": c.sub_theme,
            "覆盖目的地/城市": c.destinations,
            "对应出游/离店窗口(促销月份)": checkout,
            "关键P75(目标离店月·天)": c.p75_days,
            "选目的地数据依据·节庆/旺季(Top/峰值/淡旺季)": c.evidence,
            "资源对接时间(待Rachel确认)": None,
            "资源交付(T-30·遇假提前1周)": None,
            "营销物料制作(T-14·遇假提前1周)": None,
            "活动上线时间(周二·遇假提前2周)": None,
            "活动推广时间": None,
            "活动复盘(离店次月首周五·遇假延后)": None,
            "副主题包装说明": None,
            "场内周二排序依据": None,
            "sub_theme": c.sub_theme,
            "destinations": c.destinations,
            "checkout_window": checkout,
            "p75_days": c.p75_days,
            "evidence": c.evidence,
            "analysis_unit": c.analysis_unit,
            "continent": c.continent,
            "plan_source": "manual_data",
        }

    def _weighted_p75(self, members: list[str], month: str, p75_map: dict, agg: pd.DataFrame) -> float | None:
        num = den = 0.0
        for m in members:
            p = p75_map.get(m, {}).get(month)
            sub = agg[(agg["unit"] == m) & (agg["month"] == month)]
            w = float(sub["ttv"].sum()) if len(sub) else 0.0
            if p is not None and w > 0:
                num += p * w
                den += w
        return round(num / den, 1) if den else None

    def generate(
        self,
        *,
        top_units_per_continent: int = 5,
        top_months_per_unit: int = 5,
        min_month_share: float = 0.06,
        data_source: str = "local_xlsx",
    ) -> dict[str, Any]:
        months = self._months_from_config()
        mc = self._manual_config()
        with_l2, blank_l2, combined = self._load_mapping()
        units = self._build_unit_map(with_l2, blank_l2)
        checkout_df = self._load_checkout_df()
        agg = self._aggregate_checkout(checkout_df, units, months)
        p75_map = self._load_p75_map()
        checkout_detail = self._load_checkout_detail_from_xlsx(months)

        return self._build_calendar_result(
            agg, p75_map, units, combined, months, mc, data_source,
            top_units_per_continent, top_months_per_unit, min_month_share,
            checkout_detail_table=checkout_detail,
        )

    def generate_from_mcp_payload(
        self,
        mcp_payload: dict,
        *,
        top_units_per_continent: int = 5,
        top_months_per_unit: int = 5,
        min_month_share: float = 0.06,
        data_source: str = "simulate",
    ) -> dict[str, Any]:
        """从 MCP/虚拟 JSON 结构化数据走 A/B/C 分析。"""
        months = self._months_from_config()
        mc = self._manual_config()
        with_l2, blank_l2, combined = self._load_mapping()
        units = self._build_unit_map(with_l2, blank_l2)
        country_to_unit = {c: u for u, meta in units.items() for c in meta["countries"]}
        rows: list[dict] = []
        for r in mcp_payload.get("checkout_monthly") or []:
            month = str(r.get("month", "")).strip()
            if month not in months:
                continue
            country = str(r.get("country", "")).strip()
            from app.mcp.country_name_normalize import normalize_country_name

            country = normalize_country_name(country)
            unit = country_to_unit.get(country)
            if not unit:
                # 未映射国家：按国家单独作为分析单元
                unit = country
                if unit not in units:
                    units[unit] = {"continent": "其他", "type": "country", "countries": [country]}
                    country_to_unit[country] = unit
            rows.append({
                "month": month,
                "unit": unit,
                "continent": units[unit]["continent"],
                "unit_type": units[unit]["type"],
                "ttv": float(r.get("ttv") or 0),
                "bks": float(r.get("orders") or r.get("bks") or 0),
            })
        if not rows:
            return {
                "ok": False,
                "error": "虚拟/MCP 数据在配置的数据窗内无有效离店记录，请检查 mock 或映射表",
                "data_source": data_source,
            }
        agg = pd.DataFrame(rows).groupby(
            ["unit", "continent", "unit_type", "month"], as_index=False
        ).agg(ttv=("ttv", "sum"), bks=("bks", "sum"))

        p75_map: dict[str, dict[str, float | None]] = {}
        for r in mcp_payload.get("p75_monthly") or []:
            unit = str(r.get("unit", "")).strip()
            month = str(r.get("month", "")).strip()
            if not unit or not month:
                continue
            p75_map.setdefault(unit, {})[month] = float(r.get("p75")) if r.get("p75") is not None else None
        if not p75_map:
            p75_map = self._load_p75_map()

        checkout_monthly = mcp_payload.get("checkout_monthly") or []
        checkout_detail = self._build_checkout_detail_table(
            checkout_monthly, units, p75_map, months
        )
        xlsx_detail = self._load_checkout_detail_from_xlsx(months)
        if xlsx_detail and len(checkout_detail) < 5:
            checkout_detail = xlsx_detail
        elif xlsx_detail and checkout_detail:
            xlsx_idx = {(r["checkout_month"], r["国家"]): r for r in xlsx_detail}
            for row in checkout_detail:
                key = (row["checkout_month"], row["国家"])
                if key in xlsx_idx:
                    row["bks_until_75_percent"] = xlsx_idx[key].get("bks_until_75_percent")
                    if row.get("leading_date_for_top75_percent") is None:
                        row["leading_date_for_top75_percent"] = xlsx_idx[key].get(
                            "leading_date_for_top75_percent"
                        )

        return self._build_calendar_result(
            agg, p75_map, units, combined, months, mc, data_source,
            top_units_per_continent, top_months_per_unit, min_month_share,
            checkout_detail_table=checkout_detail,
        )

    def _build_calendar_result(
        self,
        agg: pd.DataFrame,
        p75_map: dict,
        units: dict,
        combined: dict,
        months: list[str],
        mc: dict,
        data_source: str,
        top_units_per_continent: int,
        top_months_per_unit: int,
        min_month_share: float,
        checkout_detail_table: list[dict] | None = None,
    ) -> dict[str, Any]:
        cont_totals = agg.groupby("continent")["ttv"].sum().sort_values(ascending=False)
        candidates: list[CalendarCandidate] = []

        for cont in cont_totals.index:
            sub = agg[agg["continent"] == cont]
            top_units = (
                sub.groupby("unit")["ttv"].sum().sort_values(ascending=False).head(top_units_per_continent).index
            )
            for unit in top_units:
                udf = sub[sub["unit"] == unit].sort_values("month")
                total_ttv = float(udf["ttv"].sum())
                if total_ttv <= 0:
                    continue
                udf = udf.copy()
                udf["share"] = udf["ttv"] / total_ttv
                ranked = udf.sort_values("share", ascending=False).head(top_months_per_unit)
                for rank, (_, r) in enumerate(ranked.iterrows(), start=1):
                    if float(r["share"]) < min_month_share:
                        continue
                    month = str(r["month"])
                    p75 = p75_map.get(unit, {}).get(month)
                    evidence = (
                        f"{self._month_label(month)}{unit}离店TTV={float(r['ttv'])/1e6:.1f}M，"
                        f"占全年{float(r['share'])*100:.1f}%（排名第{rank}）"
                    )
                    if p75 is not None:
                        evidence += f"；目标月P75={p75:.0f}天"
                    countries = units[unit]["countries"]
                    candidates.append(
                        CalendarCandidate(
                            analysis_unit=unit,
                            continent=cont,
                            unit_type=units[unit]["type"],
                            target_checkout_month=month,
                            month_ttv=float(r["ttv"]),
                            month_share=float(r["share"]),
                            month_rank=rank,
                            p75_days=p75,
                            annual_p75=p75_map.get(unit, {}).get("annual"),
                            countries=countries,
                            evidence=evidence,
                            sub_theme=f"{unit}·{self._month_label(month)}高峰",
                            destinations="、".join(countries[:6]) + ("…" if len(countries) > 6 else ""),
                        )
                    )

        combined_rows = []
        for name, spec in (combined or {}).items():
            members = spec.get("members", []) if isinstance(spec, dict) else list(spec)
            if not members:
                continue
            member_units = [m for m in members if m in units]
            if not member_units:
                continue
            sub = agg[agg["unit"].isin(member_units)]
            if sub.empty:
                continue
            total = sub.groupby("month")["ttv"].sum()
            peak_month = str(total.idxmax())
            peak_ttv = float(total.max())
            year_total = float(sub["ttv"].sum())
            share = peak_ttv / year_total if year_total else 0
            wp75 = self._weighted_p75(member_units, peak_month, p75_map, agg)
            combined_rows.append({
                "analysis_unit": name,
                "unit_type": "combined",
                "target_checkout_month": peak_month,
                "month_ttv": peak_ttv,
                "month_share": round(share, 4),
                "p75_days": wp75,
                "members": member_units,
                "evidence": f"{self._month_label(peak_month)}{name}组合离店TTV={peak_ttv/1e6:.1f}M（加权P75={wp75}天）",
                "sub_theme": f"{name}·{self._month_label(peak_month)}组合场",
            })

        seen: set[str] = set()
        draft_rows = []
        for c in sorted(candidates, key=lambda x: (-x.month_ttv, x.month_rank)):
            if c.analysis_unit in seen or c.month_rank > 1:
                continue
            seen.add(c.analysis_unit)
            draft_rows.append(self._feishu_draft_row(c))

        ttv_share_table = self._build_ttv_share_table(
            agg, months, top_units_per_continent=top_units_per_continent
        )
        p75_table = self._build_p75_table(
            p75_map, agg, months, top_units_per_continent=top_units_per_continent
        )

        log(
            "标准活动规划生成完成",
            module="agent1",
            action="manual_calendar_generate",
            detail={"candidates": len(candidates), "draft_rows": len(draft_rows), "source": data_source},
        )

        return {
            "ok": True,
            "data_source": data_source,
            "data_window": {"start": months[0], "end": months[-1], "planning_year": mc.get("planning_year")},
            "mcp_fetch_prompt": self._resolved_fetch_prompt(),
            "summary": {
                "continents": len(cont_totals),
                "candidates": len(candidates),
                "draft_rows": len(draft_rows),
                "combined_groups": len(combined_rows),
            },
            "continent_totals": {k: round(v / 1e6, 1) for k, v in cont_totals.items()},
            "ttv_share_table": ttv_share_table,
            "p75_table": p75_table,
            "checkout_detail_table": checkout_detail_table or [],
            "candidates": [asdict(c) for c in candidates],
            "combined_groups": combined_rows,
            "draft_rows": draft_rows,
        }

    def submit_to_review_pool(self, draft_rows: list[dict], operator: str = "marketer") -> dict:
        inserted = 0
        skipped = 0
        ids: list[int] = []
        with self.engine.begin() as conn:
            for row in draft_rows:
                source = row.get("plan_source") or "manual_data"
                key_src = "|".join([
                    "manual_calendar",
                    source,
                    str(row.get("sub_theme") or row.get("analysis_unit") or ""),
                    str(row.get("checkout_window") or row.get("go_live_date") or ""),
                    str(row.get("destinations") or "")[:40],
                ])
                key = hashlib.md5(key_src.encode()).hexdigest()
                exists = conn.execute(
                    text("SELECT suggestion_id FROM fact_ai_suggestions WHERE suggestion_key = :k"),
                    {"k": key},
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                name = row.get("sub_theme") or row.get("main_theme") or row.get("analysis_unit") or "标准活动规划"
                dest = row.get("destinations") or row.get("analysis_unit") or ""
                promo = row.get("checkout_window") or row.get("session_month") or row.get("go_live_date") or ""
                evidence = row.get("evidence") or ""
                p75 = row.get("p75_days")
                atype = row.get("activity_type") or "人工标准"
                is_temp = source in ("temp", "temp_entry")
                tag = {
                    "人工标准": "中途录入·人工标准" if is_temp else "人工标准规划",
                    "AI创意": "中途录入·AI创意" if is_temp else "AI创意",
                    "其他": "中途录入·其他" if is_temp else "其他",
                }.get(atype, "中途录入" if is_temp else "人工标准规划")
                rationale = f"[{tag}]"
                if row.get("main_theme"):
                    rationale += f" {row['main_theme']} ·"
                rationale += f" {evidence}".strip()
                if p75 is not None:
                    rationale += f" · P75={p75}天"
                conn.execute(
                    text("""
                    INSERT INTO fact_ai_suggestions
                    (suggestion_key, campaign_name, target_dest, promotion_month_hint,
                     rationale, demand_analysis, solution_analysis, status)
                    VALUES (:key, :name, :dest, :promo, :rationale, :demand, :solution, :status)
                    """),
                    {
                        "key": key,
                        "name": str(name)[:200],
                        "dest": str(dest)[:200],
                        "promo": str(promo)[:100],
                        "rationale": rationale[:1000],
                        "demand": evidence[:800],
                        "solution": json.dumps(row, ensure_ascii=False)[:2000],
                        "status": SUGGESTION_PENDING,
                    },
                )
                sid = conn.execute(text("SELECT last_insert_rowid()")).scalar()
                if sid:
                    ids.append(int(sid))
                inserted += 1

        log(
            f"标准活动规划送入评审池 {inserted} 条",
            module="agent1",
            action="manual_calendar_submit_pool",
            detail={"inserted": inserted, "skipped": skipped},
            operator=operator,
        )
        return {"ok": True, "inserted": inserted, "skipped": skipped, "suggestion_ids": ids}

    def upload_and_submit_pool(self, content: bytes, filename: str, operator: str = "marketer") -> dict:
        from app.services.calendar_import import parse_manual_calendar_draft

        rows = parse_manual_calendar_draft(content, filename)
        result = self.submit_to_review_pool(rows, operator=operator)
        return {**result, "parsed_rows": len(rows), "preview": rows[:5]}
