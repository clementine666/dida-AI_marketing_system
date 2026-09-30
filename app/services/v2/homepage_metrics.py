"""系统首页 5 桶统计 — 方案库 vs 全年计划池。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.models.lifecycle import LifecycleStatus
from app.models.planner import (
    ADOPTION_ADOPTED,
    ADOPTION_PROPOSAL,
    ADOPTION_REJECTED,
    PREP_LEAD_MONTHS,
    SUGGESTION_PENDING,
)

# 互斥执行分层（同一活动只落一个桶）
_BUCKET_EXECUTING = {LifecycleStatus.LIVE.value, LifecycleStatus.MONITORING.value}
_BUCKET_READY = {LifecycleStatus.SCHEDULED.value}
_BUCKET_PREP = {
    LifecycleStatus.DRAFT.value,
    LifecycleStatus.PLAN_REVIEW.value,
    LifecycleStatus.SENT_TO_AGENT2.value,
    LifecycleStatus.RESOURCE_CONFIG.value,
    LifecycleStatus.TODO_EXECUTION.value,
    LifecycleStatus.TESTING.value,
}
_BUCKET_ENDED = {LifecycleStatus.REVIEW.value, LifecycleStatus.ARCHIVED.value}


def _months_until(today: date, promo_year: int | None, promo_month: int | None) -> int | None:
    if promo_year is None or promo_month is None:
        return None
    return (promo_year - today.year) * 12 + (promo_month - today.month)


def _parse_promotion(row: dict, today: date) -> tuple[int | None, int | None]:
    pm = row.get("promotion_month") or ""
    if pm and len(str(pm)) >= 6:
        try:
            y, m = int(str(pm)[:4]), int(str(pm)[4:6])
            return y, m
        except ValueError:
            pass
    if pm and "月" in str(pm):
        import re

        m_match = re.search(r"(\d{1,2})\s*月", str(pm))
        if m_match:
            return today.year, int(m_match.group(1))
    start = row.get("start_date")
    if start:
        try:
            parts = str(start)[:10].split("-")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    return None, None


def is_adopted(row: dict) -> bool:
    st = (row.get("adoption_status") or "").strip().lower()
    if st == ADOPTION_ADOPTED:
        return True
    if st in (ADOPTION_PROPOSAL, ADOPTION_REJECTED):
        return False
    # 兼容旧数据
    return bool(row.get("plan_review_confirmed_at"))


def is_proposal(row: dict) -> bool:
    st = (row.get("adoption_status") or "").strip().lower()
    if st == ADOPTION_PROPOSAL:
        return True
    if st == ADOPTION_ADOPTED:
        return False
    if st == ADOPTION_REJECTED:
        return False
    return not row.get("plan_review_confirmed_at")


def bucket_for_adopted_campaign(row: dict, today: date | None = None, prep_lead: int = PREP_LEAD_MONTHS) -> str:
    """
    已采纳活动的执行分层（互斥）：
    prep_urgent | ready_launch | executing | annual_only
    """
    today = today or date.today()
    lc = row.get("lifecycle_status") or LifecycleStatus.DRAFT.value
    py, pm = _parse_promotion(row, today)
    months = _months_until(today, py, pm)

    if lc in _BUCKET_EXECUTING:
        return "executing"
    if lc in _BUCKET_READY:
        return "ready_launch"
    if lc in _BUCKET_ENDED or (months is not None and months < 0):
        return "annual_only"
    if months is not None and 0 <= months <= prep_lead and lc in _BUCKET_PREP:
        return "prep_urgent"
    return "annual_only"


def compute_homepage_metrics(engine: Engine | None = None) -> dict:
    engine = engine or get_engine()
    today = date.today()
    year = today.year

    with engine.connect() as conn:
        campaigns = [dict(r._mapping) for r in conn.execute(text("SELECT * FROM dim_campaign")).fetchall()]
        ai_pending = conn.execute(
            text("SELECT COUNT(*) AS c FROM fact_ai_suggestions WHERE status = :st"),
            {"st": SUGGESTION_PENDING},
        ).scalar() or 0

    calendar_proposals = [c for c in campaigns if is_proposal(c) and (c.get("plan_source") or "human_calendar") != "ai_suggestion"]
    adopted = [c for c in campaigns if is_adopted(c)]

    def in_year(c: dict) -> bool:
        py, pm = _parse_promotion(c, today)
        if py == year:
            return True
        start = c.get("start_date")
        if start and str(start).startswith(str(year)):
            return True
        return py is None and is_adopted(c)

    # 全年计划池含所有已采纳活动；前端按规划年（如 2027）筛选展示
    annual_plan = list(adopted)

    prep_urgent: list[dict] = []
    ready_launch: list[dict] = []
    executing: list[dict] = []

    for c in annual_plan:
        b = bucket_for_adopted_campaign(c, today)
        if b == "prep_urgent":
            prep_urgent.append(c)
        elif b == "ready_launch":
            ready_launch.append(c)
        elif b == "executing":
            executing.append(c)

    proposal_library_count = len(calendar_proposals) + int(ai_pending)

    return {
        "annual_plan_total": len(annual_plan),
        "prep_urgent": len(prep_urgent),
        "ready_to_launch": len(ready_launch),
        "executing": len(executing),
        "proposal_library_pending": proposal_library_count,
        "proposal_calendar_count": len(calendar_proposals),
        "proposal_ai_count": int(ai_pending),
        "buckets": {
            "annual_plan": annual_plan,
            "prep_urgent": prep_urgent,
            "ready_to_launch": ready_launch,
            "executing": executing,
            "calendar_proposals": calendar_proposals,
        },
        "meta": {
            "today": str(today),
            "year": year,
            "prep_lead_months": PREP_LEAD_MONTHS,
            "logic_version": "homepage-v2-five-buckets",
        },
    }
