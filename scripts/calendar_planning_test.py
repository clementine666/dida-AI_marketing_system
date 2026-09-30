#!/usr/bin/env python3
"""Learn + test: auto-generate 2027 marketing calendar from raw data vs human draft."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data" / "feishu_import" / "2027_calendar_workbook.xlsx"
MAPPING = ROOT / "data" / "feishu_import" / "continent_l2_mapping.json"
OUT_DIR = ROOT / "data" / "feishu_import" / "calendar_test_output"
MONTHS = [
    "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01",
    "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07",
]


@dataclass
class CandidateActivity:
    analysis_unit: str  # 洲二 or 国家
    continent: str
    unit_type: str  # l2_group | country
    target_checkout_month: str  # YYYY-MM
    month_ttv: float
    month_share: float
    month_rank: int
    p75_days: float | None
    annual_p75: float | None
    countries: list[str] = field(default_factory=list)
    evidence: str = ""


@dataclass
class HumanActivity:
    row: int
    session: str
    sub_theme: str
    destinations: str
    checkout_window: str
    p75: float | None
    evidence: str
    is_inbound: bool = False


def load_mapping() -> tuple[dict[str, dict[str, list[str]]], dict[str, list[str]]]:
    data = json.loads(MAPPING.read_text(encoding="utf-8"))
    return data["with_l2"], data["blank_l2"]


def sheet_by_index(xl: pd.ExcelFile, idx: int) -> pd.DataFrame:
    return pd.read_excel(XLSX, sheet_name=idx)


def build_unit_map(with_l2: dict, blank_l2: dict) -> dict[str, dict[str, Any]]:
    """analysis_unit -> {continent, type, countries}."""
    units: dict[str, dict[str, Any]] = {}
    for cont, groups in with_l2.items():
        for l2, countries in groups.items():
            units[l2] = {"continent": cont, "type": "l2_group", "countries": countries}
    for cont, countries in blank_l2.items():
        for c in countries:
            units[c] = {"continent": cont, "type": "country", "countries": [c]}
    return units


def aggregate_checkout(df: pd.DataFrame, units: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Sum checkout TTV by month × analysis unit."""
    country_col, cont_col, c2_col = df.columns[2], df.columns[3], df.columns[4]
    ttv_col, bks_col = df.columns[5], df.columns[6]
    month_col = df.columns[0]

    # country -> unit
    country_to_unit: dict[str, str] = {}
    for unit, meta in units.items():
        for c in meta["countries"]:
            country_to_unit[c] = unit

    rows = []
    for _, r in df.iterrows():
        month = str(r[month_col]).strip()
        if month not in MONTHS:
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

    agg = pd.DataFrame(rows).groupby(["unit", "continent", "unit_type", "month"], as_index=False).agg(
        ttv=("ttv", "sum"), bks=("bks", "sum")
    )
    return agg


def load_p75_matrix(sheet_idx: int = 3) -> dict[str, dict[str, float | None]]:
    """Parse P75 sheet: unit -> {month: p75, annual: p75}."""
    df = pd.read_excel(XLSX, sheet_name=sheet_idx, header=None)
    header = df.iloc[0].tolist()
    month_cols = [str(h).strip() for h in header[2:-1]]

    result: dict[str, dict[str, float | None]] = {}
    for i in range(1, len(df)):
        row = df.iloc[i].tolist()
        unit = row[1]
        if pd.isna(unit) or str(unit).strip() in ("", "nan"):
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
        annual = row[-1]
        try:
            entry["annual"] = float(annual) if pd.notna(annual) else None
        except (TypeError, ValueError):
            entry["annual"] = None
        result[unit] = entry
    return result


def weighted_p75(units: list[str], month: str, p75_map: dict, weights: dict[str, float]) -> float | None:
    """TTV-weighted P75 for combined marketing units (e.g. 新马泰)."""
    num = den = 0.0
    for u in units:
        p = p75_map.get(u, {}).get(month)
        w = weights.get(u, 0)
        if p is not None and w > 0:
            num += p * w
            den += w
    return round(num / den, 1) if den else None


def top_continents_by_ttv(agg: pd.DataFrame, top_n: int = 5) -> list[str]:
    totals = agg.groupby("continent")["ttv"].sum().sort_values(ascending=False)
    return totals.head(top_n).index.tolist()


def top_units_in_continent(agg: pd.DataFrame, continent: str, top_n: int = 5) -> list[str]:
    sub = agg[agg["continent"] == continent]
    totals = sub.groupby("unit")["ttv"].sum().sort_values(ascending=False)
    return totals.head(top_n).index.tolist()


def generate_candidates(
    agg: pd.DataFrame,
    p75_map: dict[str, dict[str, float | None]],
    units: dict[str, dict[str, Any]],
    top_months: int = 3,
    min_share: float = 0.06,
) -> list[CandidateActivity]:
    """A/B/C: per continent top units, per unit top months, attach monthly P75."""
    candidates: list[CandidateActivity] = []
    continents = top_continents_by_ttv(agg, top_n=8)

    for cont in continents:
        unit_list = top_units_in_continent(agg, cont, top_n=5)
        for unit in unit_list:
            sub = agg[agg["unit"] == unit].sort_values("month")
            total_ttv = sub["ttv"].sum()
            if total_ttv <= 0:
                continue
            sub = sub.copy()
            sub["share"] = sub["ttv"] / total_ttv
            ranked = sub.sort_values("share", ascending=False).head(top_months)
            for rank, (_, r) in enumerate(ranked.iterrows(), start=1):
                if r["share"] < min_share:
                    continue
                month = r["month"]
                p75_month = p75_map.get(unit, {}).get(month)
                p75_annual = p75_map.get(unit, {}).get("annual")
                month_label = month.replace("2025-", "2025年").replace("2026-", "2026年") + "月"
                evidence = (
                    f"{month_label}{unit}离店TTV={r['ttv']/1e6:.1f}M，占全年{r['share']*100:.1f}%"
                    f"（排名第{rank}）"
                )
                if p75_month is not None:
                    evidence += f"；目标月P75={p75_month:.0f}天"
                candidates.append(
                    CandidateActivity(
                        analysis_unit=unit,
                        continent=cont,
                        unit_type=units[unit]["type"],
                        target_checkout_month=month,
                        month_ttv=float(r["ttv"]),
                        month_share=float(r["share"]),
                        month_rank=rank,
                        p75_days=p75_month,
                        annual_p75=p75_annual,
                        countries=units[unit]["countries"],
                        evidence=evidence,
                    )
                )
    return candidates


def parse_human_draft(sheet_idx: int = 5) -> list[HumanActivity]:
    df = pd.read_excel(XLSX, sheet_name=sheet_idx, header=0)
    cols = df.columns.tolist()
    # A session, C sub_theme, D destinations, E checkout, F p75, G evidence
    activities: list[HumanActivity] = []
    for i, row in df.iterrows():
        sub = str(row[cols[2]] if len(cols) > 2 else "").strip()
        if not sub or sub == "nan":
            continue
        dest = str(row[cols[3]]).strip() if len(cols) > 3 else ""
        checkout = str(row[cols[4]]).strip() if len(cols) > 4 else ""
        p75_raw = row[cols[5]] if len(cols) > 5 else None
        evidence = str(row[cols[6]]).strip() if len(cols) > 6 else ""
        session = str(row[cols[0]]).strip() if len(cols) > 0 else ""
        try:
            p75 = float(p75_raw) if pd.notna(p75_raw) else None
        except (TypeError, ValueError):
            p75 = None
        is_inbound = "入境" in sub or "zihuai" in evidence.lower() or "来源zihuai" in evidence
        activities.append(
            HumanActivity(
                row=i + 2,
                session=session if session != "nan" else "",
                sub_theme=sub,
                destinations=dest,
                checkout_window=checkout,
                p75=p75,
                evidence=evidence,
                is_inbound=is_inbound,
            )
        )
    return activities


# keyword -> analysis unit for fuzzy match
UNIT_ALIASES = {
    "澳新": "澳新", "澳大利亚": "澳新", "新西兰": "澳新",
    "日本": "日本", "韩国": "韩国", "中国": "中国",
    "泰国": "泰国", "新加坡": "新加坡", "马来西亚": "马来西亚", "越南": "越南", "印尼": "印度尼西亚", "印度尼西亚": "印度尼西亚",
    "美加": "美加", "美国": "美加", "加拿大": "美加", "墨西哥": "墨西哥",
    "港澳": "港澳台", "香港": "港澳台", "澳门": "港澳台", "台湾": "港澳台",
    "西欧": "西欧", "南欧": "南欧", "北欧": "北欧", "东欧": "东欧", "欧洲": "西欧",
    "全欧": "西欧", "阿联酋": "阿联酋", "迪拜": "阿联酋", "土耳其": "土耳其",
    "斐济": "斐济", "巴西": "巴西", "东南亚": "泰国",
}


def infer_human_unit(act: HumanActivity) -> str | None:
    text = act.sub_theme + act.destinations + act.evidence
    for kw, unit in UNIT_ALIASES.items():
        if kw in text:
            return unit
    return None


def infer_checkout_month(checkout_window: str, evidence: str = "") -> list[str]:
    """Map human checkout text to data months (2025-08~2026-07 window)."""
    text = checkout_window + evidence
    found: list[str] = []
    # explicit YYYY-MM
    for m in MONTHS:
        if m.replace("-", "年") + "月" in text or m in text:
            found.append(m)
    month_map = {
        "2028": "2026-02",  # 2028春节 proxied to Feb peak in window
        "2027": "2026-02",
        "1月": "2026-01", "2月": "2026-02", "3月": "2026-03", "4月": "2026-04",
        "5月": "2026-05", "6月": "2026-06", "7月": "2026-07",
        "8月": "2026-07",  # 8月暑期 often maps to Jul-Aug peak in data
        "9月": "2026-07", "10月": "2026-10", "11月": "2026-11", "12月": "2026-12",
    }
    for k, v in month_map.items():
        if k in text and v not in found:
            found.append(v)
    return found


def build_system_draft(candidates: list[CandidateActivity], max_per_unit: int = 1) -> pd.DataFrame:
    """One row per unit top peak month — mimics human draft columns A-G."""
    seen: set[str] = set()
    rows = []
    ranked = sorted(candidates, key=lambda c: (-c.month_ttv, c.month_rank))
    for c in ranked:
        if c.analysis_unit in seen:
            continue
        if c.month_rank > max_per_unit:
            continue
        seen.add(c.analysis_unit)
        month_cn = c.target_checkout_month.replace("2025-", "").replace("2026-", "2026-") + "离店"
        rows.append({
            "副活动主题(系统生成)": f"{c.analysis_unit}·{month_cn}高峰",
            "覆盖目的地/城市": "、".join(c.countries[:5]) + ("…" if len(c.countries) > 5 else ""),
            "对应出游/离店窗口": month_cn,
            "关键P75": c.p75_days,
            "数据依据": c.evidence,
            "分析单元": c.analysis_unit,
            "归属洲": c.continent,
        })
    return pd.DataFrame(rows)


def compare(human: list[HumanActivity], candidates: list[CandidateActivity]) -> dict[str, Any]:
    outbound_human = [h for h in human if not h.is_inbound]

    # Build candidate lookup: unit -> top months
    cand_by_unit: dict[str, list[CandidateActivity]] = defaultdict(list)
    for c in candidates:
        cand_by_unit[c.analysis_unit].append(c)

    matches = []
    partial = []
    misses = []

    for h in outbound_human:
        unit = infer_human_unit(h)
        if not unit:
            misses.append({"human": asdict(h), "reason": "无法识别分析单元"})
            continue
        cands = cand_by_unit.get(unit, [])
        if not cands:
            misses.append({"human": asdict(h), "unit": unit, "reason": "系统未生成该单元候选"})
            continue
        human_months = infer_checkout_month(h.checkout_window, h.evidence)
        best = None
        for c in cands:
            if human_months and c.target_checkout_month in human_months:
                best = c
                break
        if not best:
            # fallback: closest by rank 1
            best = cands[0]
            partial.append({
                "human": asdict(h),
                "unit": unit,
                "human_months": human_months,
                "system_peak_months": [c.target_checkout_month for c in cands[:3]],
                "p75_human": h.p75,
                "p75_system_month": best.p75_days,
                "note": "离店月份不完全一致，但单元匹配",
            })
        else:
            p75_diff = None
            if h.p75 is not None and best.p75_days is not None:
                p75_diff = abs(h.p75 - best.p75_days)
            matches.append({
                "human_sub_theme": h.sub_theme,
                "unit": unit,
                "checkout_human": h.checkout_window,
                "checkout_month_system": best.target_checkout_month,
                "p75_human": h.p75,
                "p75_system": best.p75_days,
                "p75_diff": p75_diff,
                "evidence_system": best.evidence,
            })

    # Units in system top candidates but not in human draft
    human_units = {infer_human_unit(h) for h in outbound_human}
    human_units.discard(None)
    system_top_units = {c.analysis_unit for c in candidates if c.month_rank == 1}
    extra_units = sorted(system_top_units - human_units)

    return {
        "human_outbound_count": len(outbound_human),
        "human_inbound_count": len(human) - len(outbound_human),
        "system_candidate_count": len(candidates),
        "strong_match_count": len(matches),
        "partial_match_count": len(partial),
        "miss_count": len(misses),
        "match_rate": round(len(matches) / max(len(outbound_human), 1), 3),
        "p75_exact_matches": sum(1 for m in matches if m.get("p75_diff") == 0),
        "p75_close_matches": sum(1 for m in matches if m.get("p75_diff") is not None and m["p75_diff"] <= 3),
        "strong_matches": matches[:20],
        "partial_matches": partial[:15],
        "misses": misses[:10],
        "system_extra_top_units": extra_units,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with_l2, blank_l2 = load_mapping()
    units = build_unit_map(with_l2, blank_l2)

    checkout_df = pd.read_excel(XLSX, sheet_name=0)
    agg = aggregate_checkout(checkout_df, units)
    p75_map = load_p75_matrix()

    candidates = generate_candidates(agg, p75_map, units, top_months=3, min_share=0.06)
    human = parse_human_draft()

    # continent summary (Analysis A)
    cont_totals = agg.groupby("continent")["ttv"].sum().sort_values(ascending=False)
    unit_totals = agg.groupby(["continent", "unit"])["ttv"].sum().reset_index().sort_values("ttv", ascending=False)

    system_draft = build_system_draft(candidates)
    system_draft.to_csv(OUT_DIR / "system_draft_v1.csv", index=False, encoding="utf-8-sig")

    report = compare(human, candidates)

    # save outputs
    cand_rows = [asdict(c) for c in candidates]
    (OUT_DIR / "system_candidates.json").write_text(
        json.dumps(cand_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "comparison_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # markdown summary
    lines = [
        "# 营销日历自动规划 · 学习测试报告",
        "",
        "## 方法摘要（A/B/C）",
        "1. **A 定单元**：按归属洲汇总离店TTV，每洲取TOP5分析单元（洲二或国家）",
        "2. **B 定月份**：每单元取离店TTV占比TOP3月份（阈值≥6%）",
        "3. **C 定P75**：从「提前预订P75」表取目标离店月的月度P75",
        "",
        "## 数据覆盖",
        f"- 分析单元数：{len(units)}",
        f"- 离店数据聚合行：{len(agg)}",
        f"- P75表单元数：{len(p75_map)}",
        "",
        "## 大洲TOP（Analysis A）",
    ]
    for cont, ttv in cont_totals.items():
        lines.append(f"- **{cont}**：{ttv/1e6:.1f}M")

    lines += ["", "## 各洲TOP5分析单元"]
    for cont in cont_totals.index[:6]:
        sub = unit_totals[unit_totals["continent"] == cont].head(5)
        items = ", ".join(f"{r.unit}({r.ttv/1e6:.1f}M)" for _, r in sub.iterrows())
        lines.append(f"- **{cont}**：{items}")

    lines += [
        "",
        "## 与人工初版对比",
        f"- 人工出境活动：{report['human_outbound_count']} 场（入境 {report['human_inbound_count']} 场未纳入自动对比）",
        f"- 系统候选活动：{report['system_candidate_count']} 条（每单元×TOP3月）",
        f"- **强匹配**（单元+月份一致）：{report['strong_match_count']} / {report['human_outbound_count']}（{report['match_rate']*100:.1f}%）",
        f"- 部分匹配（单元一致、月份不同）：{report['partial_match_count']}",
        f"- P75完全一致：{report['p75_exact_matches']} 场",
        f"- P75差≤3天：{report['p75_close_matches']} 场",
        "",
        "## 强匹配样例",
    ]
    for m in report["strong_matches"][:10]:
        lines.append(
            f"- **{m['human_sub_theme']}** ({m['unit']}) "
            f"人工P75={m['p75_human']} / 系统P75={m['p75_system']} · 月={m['checkout_month_system']}"
        )

    lines += ["", "## 差异说明（为何不能100%复刻人工46场）", ""]
    lines += [
        "- 人工版含 **46场周二排程**、主题命名、zihuai入境4场、业务底稿目的地保留 — 本测试仅验证 **数据层 A/B/C**",
        "- 人工会 **合并多场**（新马泰、全欧洲）与 **拆城市线**（日本5场）— 需在规则引擎层实现",
        "- 人工 **P75取目标离店月** 且组合场按TTV加权 — 系统已从P75表读取月度值",
        f"- 系统TOP单元但人工未单独成场：{', '.join(report['system_extra_top_units'][:10]) or '无'}",
    ]

    (OUT_DIR / "CALENDAR_PLANNING_TEST_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "candidates": len(candidates),
        "human_outbound": report["human_outbound_count"],
        "strong_match": report["strong_match_count"],
        "match_rate": report["match_rate"],
        "p75_exact": report["p75_exact_matches"],
        "report": str(OUT_DIR / "CALENDAR_PLANNING_TEST_REPORT.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
