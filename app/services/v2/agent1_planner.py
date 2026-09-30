"""Agent1 - 方案策划师（v2）。

逻辑：
- 人工营销日历（飞书）：有全年就读全年
- 提前 PREP_LEAD_MONTHS 个月进入准备队列（现在就要开始测试/配置）
- AI 行业情报建议：独立产出，营销师审核后才进入日历池或合并
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.integrations.feishu_marketing_calendar import FeishuMarketingCalendarClient
from app.models.lifecycle import LifecycleStatus
from app.models.planner import (
    ADOPTION_ADOPTED,
    ADOPTION_PROPOSAL,
    ADOPTION_REJECTED,
    PHASE_IN_PREP,
    PHASE_PAST,
    PHASE_PLANNED,
    PHASE_URGENT_PREP,
    PLAN_SOURCE_AI,
    PLAN_SOURCE_HUMAN,
    PLAN_SOURCE_MERGED,
    PREP_LEAD_MONTHS,
    SUGGESTION_APPROVED,
    SUGGESTION_MERGED,
    SUGGESTION_PENDING,
    SUGGESTION_REJECTED,
)
from app.models.campaign_plan_schema import (
    PLAN_SECTIONS,
    build_full_structured_plan,
    ensure_task_board,
    structured_to_flat,
    sync_launch_pack_ids,
    sync_schedule_dates,
)
from app.models.query_profile import sync_query_profiles
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.snapshot_service import SnapshotService
from app.services.v2.activity_doc_parser import apply_dida_gp_rate
from app.services.v2.homepage_metrics import bucket_for_adopted_campaign, compute_homepage_metrics, is_adopted


class PlannerService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.feishu = FeishuMarketingCalendarClient()
        self.lifecycle = ActivityLifecycleService(self.engine)
        self.snapshot = SnapshotService(self.engine)

    # ── 行业情报 ──────────────────────────────────────────────

    def get_industry_intel(self, limit: int = 10) -> list[dict]:
        sql = """
        SELECT * FROM fact_industry_intel
        ORDER BY report_date DESC, created_at DESC LIMIT :limit
        """
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(sql), {"limit": limit})
                return [dict(r._mapping) for r in rows]
        except Exception:
            return []

    def search_archives_for_reference(self, destination: str | None = None, limit: int = 5) -> list[dict]:
        sql = """
        SELECT archive_id, campaign_id, activity_name, destination, success_label,
               reusable_points, avoid_points, conclusions
        FROM dim_activity_archive
        WHERE (:dest IS NULL OR destination LIKE :dest_like)
        ORDER BY archived_at DESC LIMIT :limit
        """
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(sql),
                    {"dest": destination, "dest_like": f"%{destination}%" if destination else None, "limit": limit},
                )
                return [dict(r._mapping) for r in rows]
        except Exception:
            return []

    # ── 核心：营销工作台 ──────────────────────────────────────

    def build_marketing_workspace(self, prep_lead_months: int = PREP_LEAD_MONTHS) -> dict:
        """
        Agent1 主入口：
        1. 同步飞书/本地日历 → 方案库（proposal，待运营师评审）
        2. 已采纳活动 → 全年营销计划池
        3. AI 建议 → 方案库（pending），采纳后进计划池
        """
        today = date.today()
        intel = self.get_industry_intel()
        human_records = self.feishu.list_calendar_records()

        synced_plans: list[dict] = []
        by_month: dict[str, list[dict]] = {}

        for rec in human_records:
            dest = rec.get("target_dest") or self._guess_destination(rec.get("regions") or rec.get("plan_summary", ""))
            archives = self.search_archives_for_reference(dest)
            promo_date = self._resolve_promotion_date(rec, today)
            months_until = self._months_until(today, promo_date)
            prep_phase = self._calc_prep_phase(months_until, prep_lead_months)

            enriched = self._enrich_plan(
                {
                    **rec,
                    "campaign_id": self._campaign_id_for_rec(rec),
                    "target_dest": dest,
                    "promotion_date": str(promo_date) if promo_date else None,
                    "months_until_promotion": months_until,
                    "prep_phase": prep_phase,
                    "plan_source": PLAN_SOURCE_HUMAN,
                    "adoption_status": ADOPTION_PROPOSAL,
                    "needs_action_now": False,
                },
                intel,
                archives,
            )
            self._upsert_campaign(enriched, plan_source=PLAN_SOURCE_HUMAN, prep_phase=prep_phase)
            synced_plans.append(enriched)
            month_key = rec.get("promotion_month") or "未分类"
            by_month.setdefault(str(month_key), []).append(enriched)

        metrics = compute_homepage_metrics(self.engine)
        annual = metrics["buckets"]["annual_plan"]
        calendar_proposals = metrics["buckets"]["calendar_proposals"]
        prep_urgent = metrics["buckets"]["prep_urgent"]
        ready_launch = metrics["buckets"]["ready_to_launch"]
        executing = metrics["buckets"]["executing"]

        self._attach_review_flags(synced_plans)
        self._attach_review_flags(annual)
        self._attach_review_flags(calendar_proposals)
        self._attach_review_flags(prep_urgent)
        for items in by_month.values():
            self._attach_review_flags(items)

        ai_suggestions = self.generate_ai_suggestions(intel, synced_plans)

        annual_by_month: dict[str, list[dict]] = {}
        for p in annual:
            mk = str(p.get("promotion_month") or "未分类")
            annual_by_month.setdefault(mk, []).append(p)

        return {
            "meta": {
                "today": str(today),
                "year": today.year,
                "prep_lead_months": prep_lead_months,
                "logic": (
                    "飞书/Excel 同步进方案库（待审）；运营师评审采纳后进全年计划池；"
                    f"已采纳且未来{prep_lead_months}个月内未上线=需立即准备"
                ),
            },
            "homepage_metrics": {
                "annual_plan_total": metrics["annual_plan_total"],
                "prep_urgent": metrics["prep_urgent"],
                "ready_to_launch": metrics["ready_to_launch"],
                "executing": metrics["executing"],
                "proposal_library_pending": metrics["proposal_library_pending"],
            },
            "proposal_library": {
                "description": "方案库：飞书营销规划 + AI 行业建议，待运营师评审补充后采纳",
                "calendar_proposals": calendar_proposals,
                "calendar_proposal_count": len(calendar_proposals),
                "ai_pending": ai_suggestions.get("pending_review", []),
                "ai_pending_count": metrics["proposal_ai_count"],
                "total_pending": metrics["proposal_library_pending"],
            },
            "human_calendar": {
                "description": "全年营销计划池：已采纳、确定要上的活动",
                "total_count": len(annual),
                "by_month": annual_by_month,
                "full_year": annual,
            },
            "prep_queue": {
                "description": f"需立即准备（① 的子集，未来{prep_lead_months}个月内、未上线）",
                "urgent_count": len(prep_urgent),
                "in_progress_count": len(ready_launch),
                "executing_count": len(executing),
                "urgent": prep_urgent,
                "in_progress": ready_launch,
                "executing": executing,
            },
            "synced_calendar": {
                "description": "最近一次同步的原始日历行（含未采纳规划）",
                "total_count": len(synced_plans),
                "by_month": by_month,
            },
            "ai_suggestions": ai_suggestions,
        }

    def build_three_month_calendar(self, months_ahead: int = 3, include_all: bool = False) -> dict:
        """兼容旧 API：返回准备队列 + 执行窗口内的活动。"""
        ws = self.build_marketing_workspace(prep_lead_months=months_ahead)
        if include_all:
            activities = ws["human_calendar"]["full_year"]
        else:
            pq = ws["prep_queue"]
            activities = pq["urgent"] + pq["in_progress"] + pq.get("executing", [])
        today = date.today()
        return {
            "period": {"from": str(today), "to": str(today + timedelta(days=months_ahead * 31)), "months": months_ahead},
            "prep_lead_months": months_ahead,
            "activity_count": len(activities),
            "activities": activities,
            "prep_queue": ws["prep_queue"],
            "ai_suggestions_pending": ws["ai_suggestions"]["pending_review"],
        }

    # ── AI 建议生成与审核 ─────────────────────────────────────

    def generate_ai_suggestions(self, intel: list[dict] | None = None, human_plans: list[dict] | None = None) -> dict:
        intel = intel or self.get_industry_intel()
        human_plans = human_plans or []
        generated = 0

        for item in intel:
            raw = item.get("activity_suggestions") or "[]"
            try:
                suggestions = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                suggestions = [raw] if raw else []
            if not isinstance(suggestions, list):
                suggestions = [str(suggestions)]

            for text_val in suggestions:
                if not text_val or not str(text_val).strip():
                    continue
                dest = self._guess_destination(str(text_val))
                similar = self._find_similar_calendar_item(str(text_val), dest, human_plans)
                key = hashlib.md5(f"{item.get('intel_id')}:{text_val}".encode()).hexdigest()
                promo_hint = self._suggest_promotion_month(dest, item)

                with self.engine.begin() as conn:
                    exists = conn.execute(
                        text("SELECT suggestion_id FROM fact_ai_suggestions WHERE suggestion_key = :k"),
                        {"k": key},
                    ).fetchone()
                    if exists:
                        continue
                    conn.execute(
                        text("""
                        INSERT INTO fact_ai_suggestions
                        (suggestion_key, campaign_name, target_dest, promotion_month_hint,
                         rationale, demand_analysis, solution_analysis,
                         intel_id, intel_report_title, status,
                         similar_calendar_id, similar_calendar_name)
                        VALUES (:key, :name, :dest, :promo, :rationale, :demand, :solution,
                                :iid, :title, :status, :sim_id, :sim_name)
                        """),
                        {
                            "key": key,
                            "name": str(text_val)[:200],
                            "dest": dest,
                            "promo": promo_hint,
                            "rationale": f"基于行业情报「{item.get('report_title', '')}」",
                            "demand": item.get("summary", "")[:500],
                            "solution": self._build_solution_analysis(dest, [str(text_val)]),
                            "iid": item.get("intel_id"),
                            "title": item.get("report_title"),
                            "status": SUGGESTION_PENDING,
                            "sim_id": similar.get("feishu_record_id") if similar else None,
                            "sim_name": similar.get("campaign_name") if similar else None,
                        },
                    )
                    generated += 1

        return {
            "newly_generated": generated,
            **self.list_ai_suggestions(),
        }

    def list_ai_suggestions(self, status: str | None = None) -> dict:
        sql = "SELECT * FROM fact_ai_suggestions"
        params: dict = {}
        if status:
            sql += " WHERE status = :st"
            params["st"] = status
        sql += " ORDER BY created_at DESC"
        with self.engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(text(sql), params)]

        grouped = {SUGGESTION_PENDING: [], SUGGESTION_APPROVED: [], SUGGESTION_REJECTED: [], SUGGESTION_MERGED: []}
        for r in rows:
            st = r.get("status") or SUGGESTION_PENDING
            grouped.setdefault(st, []).append(r)

        return {
            "pending_review": grouped.get(SUGGESTION_PENDING, []),
            "approved": grouped.get(SUGGESTION_APPROVED, []),
            "rejected": grouped.get(SUGGESTION_REJECTED, []),
            "merged": grouped.get(SUGGESTION_MERGED, []),
            "total": len(rows),
        }

    def review_ai_suggestion(
        self,
        suggestion_id: int,
        action: str,
        operator: str = "marketer",
        merge_with_campaign_id: str | None = None,
        promotion_month: str | None = None,
        structured_plan: dict | None = None,
    ) -> dict:
        """
        营销师审核 AI 建议：
        - approve: 采纳 → 进入营销活动日历池（新建 draft）
        - reject: 拒绝
        - merge: 合并到现有人工日历活动
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM fact_ai_suggestions WHERE suggestion_id = :id"),
                {"id": suggestion_id},
            ).fetchone()
        if not row:
            return {"ok": False, "error": "Suggestion not found"}
        sug = dict(row._mapping)

        if action == "reject":
            self._update_suggestion_status(suggestion_id, SUGGESTION_REJECTED, operator)
            return {"ok": True, "action": "rejected", "suggestion_id": suggestion_id}

        if action == "merge" and merge_with_campaign_id:
            plan = self.get_activity_plan(merge_with_campaign_id)
            if not plan:
                return {"ok": False, "error": "Target campaign not found"}
            merged_summary = (plan.get("plan_summary") or "") + f"\n[AI合并建议] {sug['campaign_name']}"
            self.update_plan(
                merge_with_campaign_id,
                {
                    "plan_summary": merged_summary,
                    "demand_analysis": (plan.get("demand_analysis") or "") + f"\n{sug.get('demand_analysis', '')}",
                    "solution_analysis": sug.get("solution_analysis") or plan.get("solution_analysis"),
                },
                editor=operator,
            )
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE dim_campaign SET plan_source = :src, merged_from_suggestion_id = :sid
                    WHERE campaign_id = :cid
                    """),
                    {"src": PLAN_SOURCE_MERGED, "sid": suggestion_id, "cid": merge_with_campaign_id},
                )
            self._update_suggestion_status(suggestion_id, SUGGESTION_MERGED, operator, merge_with_campaign_id)
            return {"ok": True, "action": "merged", "campaign_id": merge_with_campaign_id}

        if action == "approve":
            if structured_plan:
                self.save_suggestion_draft(suggestion_id, structured_plan, operator)
            month = promotion_month
            if not month and structured_plan:
                month = (structured_plan.get("basic") or {}).get("promotion_month") or structured_plan.get("promotion_month")
            month = month or sug.get("promotion_month_hint")
            campaign_id = f"CAMP_AI_{uuid.uuid4().hex[:8].upper()}"
            plan = {
                "campaign_id": campaign_id,
                "campaign_name": (structured_plan or {}).get("basic", {}).get("campaign_name")
                or (structured_plan or {}).get("campaign_name")
                or sug["campaign_name"],
                "target_dest": (structured_plan or {}).get("basic", {}).get("target_dest")
                or (structured_plan or {}).get("target_dest")
                or sug.get("target_dest"),
                "plan_summary": (structured_plan or {}).get("background", {}).get("summary")
                if structured_plan and structured_plan.get("background")
                else (structured_plan or {}).get("background")
                or f"[AI建议·待入日历] {sug['campaign_name']}",
                "demand_analysis": (structured_plan or {}).get("data_insights", {}).get("data_conclusion")
                or (structured_plan or {}).get("demand_analysis")
                or sug.get("demand_analysis"),
                "solution_analysis": (structured_plan or {}).get("strategy", {}).get("solution_summary")
                or (structured_plan or {}).get("solution_analysis")
                or sug.get("solution_analysis"),
                "promotion_month": month,
                "target_audience": (structured_plan or {}).get("customer_segment", {}).get("description") if structured_plan else None,
                "campaign_type": (structured_plan or {}).get("basic", {}).get("campaign_type")
                or (structured_plan or {}).get("campaign_type")
                or "Banner",
                "plan_source": PLAN_SOURCE_AI,
                "prep_phase": PHASE_PLANNED,
            }
            if structured_plan:
                flat = structured_to_flat(structured_plan)
                plan.update({k: v for k, v in flat.items() if v is not None and k != "campaign_id"})
            intel = self.get_industry_intel(limit=3)
            enriched = self._enrich_plan(plan, intel, self.search_archives_for_reference(sug.get("target_dest")))
            if structured_plan:
                enriched["plan_structured_json"] = plan.get("plan_structured_json")
                enriched["promotion_month"] = month
            self._upsert_campaign(enriched, plan_source=PLAN_SOURCE_AI, prep_phase=PHASE_PLANNED)
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE dim_campaign
                    SET plan_review_confirmed_at = CURRENT_TIMESTAMP,
                        plan_review_confirmed_by = :op,
                        adoption_status = :adopt,
                        promotion_month = :month,
                        plan_structured_json = :json
                    WHERE campaign_id = :cid
                    """),
                    {
                        "op": operator,
                        "adopt": ADOPTION_ADOPTED,
                        "month": month,
                        "json": plan.get("plan_structured_json"),
                        "cid": campaign_id,
                    },
                )
            self.lifecycle.transition(campaign_id, LifecycleStatus.PLAN_REVIEW.value, operator, "AI建议采纳入池并完成评审")
            self._update_suggestion_status(suggestion_id, SUGGESTION_APPROVED, operator, campaign_id)
            return {"ok": True, "action": "approved", "campaign_id": campaign_id, "plan": enriched, "promotion_month": month}

        return {"ok": False, "error": f"Unknown action: {action}"}

    def _update_suggestion_status(
        self, suggestion_id: int, status: str, operator: str, merged_campaign_id: str | None = None
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE fact_ai_suggestions
                SET status = :st, reviewed_by = :op, reviewed_at = CURRENT_TIMESTAMP,
                    merged_campaign_id = COALESCE(:cid, merged_campaign_id)
                WHERE suggestion_id = :id
                """),
                {"st": status, "op": operator, "cid": merged_campaign_id, "id": suggestion_id},
            )

    # ── 优先级计算 ────────────────────────────────────────────

    @staticmethod
    def _resolve_promotion_date(rec: dict, today: date) -> date | None:
        if rec.get("start_date"):
            try:
                return date.fromisoformat(str(rec["start_date"])[:10])
            except ValueError:
                pass
        month_num = rec.get("promotion_month_num")
        if month_num:
            year = today.year
            if month_num < today.month:
                year += 1
            try:
                return date(year, month_num, 15)
            except ValueError:
                pass
        return None

    @staticmethod
    def _months_until(today: date, promo: date | None) -> int | None:
        if not promo:
            return None
        return (promo.year - today.year) * 12 + (promo.month - today.month)

    @staticmethod
    def _calc_prep_phase(months_until: int | None, prep_lead: int) -> str:
        if months_until is None:
            return PHASE_PLANNED
        if months_until < 0:
            return PHASE_PAST
        if months_until == prep_lead:
            return PHASE_URGENT_PREP
        if 0 <= months_until < prep_lead:
            return PHASE_IN_PREP
        return PHASE_PLANNED

    @staticmethod
    def _find_similar_calendar_item(text_val: str, dest: str, human_plans: list[dict]) -> dict | None:
        for p in human_plans:
            name = (p.get("campaign_name") or "").lower()
            regions = (p.get("regions") or "").lower()
            if dest.lower() in name or dest.lower() in regions:
                return p
            if any(kw in name for kw in text_val.lower().split() if len(kw) > 2):
                return p
        return None

    @staticmethod
    def _suggest_promotion_month(dest: str, intel_item: dict) -> str:
        today = date.today()
        target = today + relativedelta(months=PREP_LEAD_MONTHS)
        return f"{target.month}月"

    # ── 方案丰富 ──────────────────────────────────────────────

    def _enrich_plan(self, record: dict, intel: list[dict], archives: list[dict]) -> dict:
        dest = record.get("target_dest") or self._guess_destination(record.get("plan_summary", ""))
        intel_hints = []
        for item in intel:
            tags = item.get("destination_tags") or ""
            if not dest or dest in tags or not tags:
                intel_hints.append(item.get("activity_suggestions") or item.get("summary"))

        archive_hints = []
        for a in archives:
            if a.get("reusable_points"):
                archive_hints.append(f"参考「{a['activity_name']}」: {a['reusable_points']}")
            if a.get("avoid_points"):
                archive_hints.append(f"规避: {a['avoid_points']}")

        return {
            **record,
            "target_dest": dest,
            "demand_analysis": record.get("demand_analysis") or self._build_demand_analysis(dest, intel),
            "solution_analysis": record.get("solution_analysis") or self._build_solution_analysis(dest, intel_hints),
            "execution_steps": record.get("execution_steps") or self._default_execution_steps(record),
            "intel_references": intel_hints[:3],
            "archive_references": archive_hints[:3],
            "campaign_type": record.get("campaign_type") or "Banner",
        }

    @staticmethod
    def _campaign_id_for_rec(rec: dict) -> str:
        """稳定且 URL 安全的 campaign_id（优先飞书 record_id）。"""
        fid = rec.get("feishu_record_id") or rec.get("_record_id")
        if fid:
            return f"CAMP_{fid}"
        aid = rec.get("activity_id")
        if aid and str(aid).isascii() and " " not in str(aid):
            return f"CAMP_{aid}"
        return f"CAMP_{uuid.uuid4().hex[:8].upper()}"

    def _guess_destination(self, text_val: str) -> str:
        mapping = [
            ("新加坡", "Singapore"), ("Singapore", "Singapore"), ("F1", "Singapore"),
            ("马来西亚", "Malaysia"), ("Malaysia", "Malaysia"),
            ("泰国", "Thailand"), ("Thailand", "Thailand"),
            ("日本", "Japan"), ("樱花", "Japan"), ("红叶", "Japan"),
            ("德", "Germany"), ("法", "France"), ("意", "Italy"), ("瑞", "Switzerland"),
            ("西", "Spain"), ("葡", "Portugal"), ("美国", "USA"),
            ("东南亚", "Singapore"),
        ]
        for kw, dest in mapping:
            if kw in (text_val or ""):
                return dest
        return "Singapore"

    def _build_demand_analysis(self, dest: str | None, intel: list[dict]) -> str:
        parts = [f"目的地 {dest or '待定'} 存在B端酒店预订需求。"]
        if intel:
            parts.append(f"行业情报: {intel[0].get('summary', '')[:200]}")
        return " ".join(parts)

    def _build_solution_analysis(self, dest: str | None, hints: list) -> str:
        base = f"针对 {dest} 推出官网营销活动专区 + 定向客群触达。"
        if hints:
            hint = hints[0]
            if isinstance(hint, str):
                base += f" 情报建议: {hint[:150]}"
        return base

    def _default_execution_steps(self, record: dict) -> str:
        phase = record.get("prep_phase", "")
        prefix = "【现在启动准备】" if record.get("needs_action_now") else "【规划阶段】"
        return prefix + "\n" + "\n".join([
            "1. 营销师确认方案 → Agent2 圈客选品",
            "2. 配置 Banner/优惠券/短信",
            "3. 埋点与监控字段配置",
            "4. 测试后按时上线",
            "5. Agent3 监控 → Agent4 复盘 → Agent5 归档",
        ])

    def _upsert_campaign(self, plan: dict, plan_source: str = PLAN_SOURCE_HUMAN, prep_phase: str | None = None) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(
                text("SELECT campaign_id, adoption_status, lifecycle_status, plan_review_confirmed_at FROM dim_campaign WHERE campaign_id = :cid"),
                {"cid": plan["campaign_id"]},
            ).fetchone()
            keep_adopted = False
            ex: dict = {}
            if existing:
                ex = dict(existing._mapping)
                if (ex.get("adoption_status") or "").strip().lower() == ADOPTION_REJECTED:
                    keep_adopted = False
                else:
                    keep_adopted = is_adopted(ex) or (ex.get("adoption_status") == ADOPTION_ADOPTED)

            if existing and (ex.get("adoption_status") or "").strip().lower() == ADOPTION_REJECTED:
                adoption = ADOPTION_REJECTED
            elif keep_adopted:
                adoption = ADOPTION_ADOPTED
            else:
                adoption = ADOPTION_PROPOSAL
            if plan_source == PLAN_SOURCE_AI and plan.get("adoption_status") == ADOPTION_ADOPTED:
                adoption = ADOPTION_ADOPTED

            lifecycle = (
                ex.get("lifecycle_status")
                if existing and (keep_adopted or adoption == ADOPTION_REJECTED)
                else (LifecycleStatus.PLAN_REVIEW.value if plan.get("needs_action_now") else LifecycleStatus.DRAFT.value)
            )
            fields = {
                "cid": plan["campaign_id"],
                "name": plan.get("campaign_name"),
                "type": plan.get("campaign_type", "Banner"),
                "start": plan.get("start_date") or plan.get("promotion_date"),
                "end": plan.get("end_date"),
                "dest": plan.get("target_dest"),
                "summary": plan.get("plan_summary"),
                "audience": plan.get("target_audience"),
                "demand": plan.get("demand_analysis"),
                "solution": plan.get("solution_analysis"),
                "steps": plan.get("execution_steps"),
                "metrics": plan.get("target_metrics"),
                "key_spec": plan.get("key_metrics_spec"),
                "fid": plan.get("feishu_record_id"),
                "aid": plan.get("activity_id"),
                "st": lifecycle,
                "psrc": plan_source,
                "pphase": prep_phase or plan.get("prep_phase"),
                "adopt": adoption,
            }
            if existing:
                conn.execute(
                    text("""
                    UPDATE dim_campaign SET
                        campaign_name=:name, campaign_type=:type, start_date=:start, end_date=:end,
                        target_dest=:dest, plan_summary=:summary, target_audience=:audience,
                        demand_analysis=:demand, solution_analysis=:solution, execution_steps=:steps,
                        target_metrics=:metrics, key_metrics_spec=:key_spec,
                        feishu_record_id=:fid, activity_id=:aid,
                        lifecycle_status=COALESCE(lifecycle_status, :st),
                        plan_source=:psrc, prep_phase=:pphase,
                        adoption_status=:adopt,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE campaign_id=:cid
                    """),
                    fields,
                )
            else:
                conn.execute(
                    text("""
                    INSERT INTO dim_campaign
                    (campaign_id, campaign_name, campaign_type, start_date, end_date, target_dest,
                     plan_summary, target_audience, demand_analysis, solution_analysis, execution_steps,
                     target_metrics, key_metrics_spec, feishu_record_id, activity_id, lifecycle_status,
                     plan_source, prep_phase, adoption_status, status)
                    VALUES (:cid,:name,:type,:start,:end,:dest,:summary,:audience,:demand,:solution,:steps,
                            :metrics,:key_spec,:fid,:aid,:st,:psrc,:pphase,:adopt,'筹备')
                    """),
                    fields,
                )

    def _attach_review_flags(self, plans: list[dict]) -> None:
        """从 dim_campaign 合并评审状态到工作台活动列表。"""
        if not plans:
            return
        ids = [p["campaign_id"] for p in plans if p.get("campaign_id")]
        if not ids:
            return
        placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
        params = {f"id{i}": cid for i, cid in enumerate(ids)}
        sql = f"""
        SELECT campaign_id, plan_review_confirmed_at, plan_review_confirmed_by,
               lifecycle_status, plan_structured_json, promotion_month, adoption_status
        FROM dim_campaign WHERE campaign_id IN ({placeholders})
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params)
            by_id = {r.campaign_id: dict(r._mapping) for r in rows}
        for p in plans:
            db = by_id.get(p.get("campaign_id"), {})
            p["plan_review_confirmed"] = bool(db.get("plan_review_confirmed_at")) or db.get("adoption_status") == ADOPTION_ADOPTED
            p["plan_review_confirmed_at"] = db.get("plan_review_confirmed_at")
            p["adoption_status"] = db.get("adoption_status")
            p["adopted"] = is_adopted(db) if db else is_adopted(p)
            p["lifecycle_status"] = db.get("lifecycle_status") or p.get("lifecycle_status")
            if db.get("promotion_month"):
                p["promotion_month"] = db["promotion_month"]

    def build_structured_plan(self, row: dict, *, ai_rationale: str | None = None, intel_source: str | None = None) -> dict:
        """将活动/建议记录组装为运营师可编辑的全套策划方案（schema v2）。"""
        plan = build_full_structured_plan(
            row,
            plan_source=row.get("plan_source") or "human_calendar",
            ai_rationale=ai_rationale,
            intel_source=intel_source,
        )
        # 从 _enrich_plan 补充情报/档案引用到数据洞察
        intel_refs = row.get("intel_references") or []
        archive_refs = row.get("archive_references") or []
        if intel_refs and not plan["data_insights"].get("market_data"):
            plan["data_insights"]["market_data"] = "；".join(str(x) for x in intel_refs[:2])
        if archive_refs and not plan["data_insights"].get("historical_reference"):
            plan["data_insights"]["historical_reference"] = "；".join(str(x) for x in archive_refs[:2])
        if row.get("execution_steps") and not plan["product_delivery"].get("execution_steps"):
            plan["product_delivery"]["execution_steps"] = row["execution_steps"]
        return plan

    def _structured_to_flat(self, structured: dict) -> dict:
        return structured_to_flat(structured)

    def get_structured_plan(self, campaign_id: str) -> dict:
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        structured = self.build_structured_plan(plan)
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "plan_review_confirmed": bool(plan.get("plan_review_confirmed_at")),
            "plan_review_confirmed_at": plan.get("plan_review_confirmed_at"),
            "lifecycle_status": plan.get("lifecycle_status"),
            "sections": PLAN_SECTIONS,
            "structured": structured,
        }

    def save_structured_plan(self, campaign_id: str, structured: dict, editor: str = "marketer") -> dict:
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        structured = apply_dida_gp_rate(sync_query_profiles(structured))
        structured = sync_schedule_dates(structured)
        structured = sync_launch_pack_ids(structured)
        flat = self._structured_to_flat(structured)
        allowed = {
            "campaign_name", "plan_summary", "target_audience", "demand_analysis",
            "solution_analysis", "execution_steps", "target_metrics", "campaign_type",
            "delivery_mode", "target_dest", "promotion_month", "plan_structured_json",
        }
        sets = []
        params = {"cid": campaign_id}
        for k, v in flat.items():
            if k in allowed and v is not None:
                sets.append(f"{k} = :{k}")
                params[k] = v
        if not sets:
            return {"ok": False, "error": "No valid fields"}
        sets.append("updated_at = CURRENT_TIMESTAMP")
        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE dim_campaign SET {', '.join(sets)} WHERE campaign_id = :cid"), params)
        updated = self.get_activity_plan(campaign_id)
        self.snapshot.save(campaign_id, "agent1", updated or {}, LifecycleStatus.PLAN_REVIEW.value, editor)
        return {"ok": True, "campaign_id": campaign_id, "structured": structured}

    def confirm_plan_review(self, campaign_id: str, operator: str = "marketer") -> dict:
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        structured = ensure_task_board(build_full_structured_plan(plan))
        self.save_structured_plan(campaign_id, structured, editor=operator)
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign
                SET plan_review_confirmed_at = CURRENT_TIMESTAMP,
                    plan_review_confirmed_by = :op,
                    adoption_status = :adopt,
                    lifecycle_status = :st,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {"op": operator, "adopt": ADOPTION_ADOPTED, "st": LifecycleStatus.PLAN_REVIEW.value, "cid": campaign_id},
            )
        self.lifecycle.transition(campaign_id, LifecycleStatus.PLAN_REVIEW.value, operator, "营销师确认方案并采纳进全年计划池")
        self.snapshot.save(campaign_id, "agent1", plan, LifecycleStatus.PLAN_REVIEW.value, operator)
        return {"ok": True, "campaign_id": campaign_id, "plan_review_confirmed": True, "adopted": True}

    def reject_calendar_proposal(self, campaign_id: str, operator: str = "marketer", reason: str | None = None) -> dict:
        """拒绝飞书营销规划条目：保留记录，不进入全年计划池。"""
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "规划条目不存在"}
        if is_adopted(plan):
            return {"ok": False, "error": "该活动已采纳进全年计划池，无法拒绝"}
        if (plan.get("adoption_status") or "").strip().lower() == ADOPTION_REJECTED:
            return {"ok": True, "campaign_id": campaign_id, "action": "rejected", "already_rejected": True}

        note = reason or "运营师拒绝飞书营销规划"
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign
                SET adoption_status = :st,
                    plan_review_confirmed_at = NULL,
                    plan_review_confirmed_by = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {"st": ADOPTION_REJECTED, "cid": campaign_id},
            )
        self.snapshot.save(campaign_id, "agent1", plan, LifecycleStatus.DRAFT.value, operator)
        return {"ok": True, "campaign_id": campaign_id, "action": "rejected", "message": note}

    def remove_from_annual_plan(self, campaign_id: str, operator: str = "marketer", reason: str | None = None) -> dict:
        """从全年计划池移除已采纳活动（标记为 rejected，不再展示）。"""
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "活动不存在"}
        if not is_adopted(plan):
            return {"ok": False, "error": "该活动不在全年计划池"}
        note = reason or "从全年计划池删除"
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign
                SET adoption_status = :st,
                    plan_review_confirmed_at = NULL,
                    plan_review_confirmed_by = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {"st": ADOPTION_REJECTED, "cid": campaign_id},
            )
        self.snapshot.save(campaign_id, "agent1", plan, LifecycleStatus.DRAFT.value, operator)
        return {"ok": True, "campaign_id": campaign_id, "action": "removed_from_annual", "message": note}

    def get_suggestion_review(self, suggestion_id: int) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM fact_ai_suggestions WHERE suggestion_id = :id"),
                {"id": suggestion_id},
            ).fetchone()
        if not row:
            return {"ok": False, "error": "Suggestion not found"}
        sug = dict(row._mapping)
        sug["plan_source"] = "ai_intel"
        if sug.get("plan_draft_json"):
            sug["plan_structured_json"] = sug["plan_draft_json"]
        structured = self.build_structured_plan(
            sug,
            ai_rationale=sug.get("rationale"),
            intel_source=sug.get("intel_report_title"),
        )
        return {"ok": True, "suggestion_id": suggestion_id, "status": sug.get("status"), "sections": PLAN_SECTIONS, "structured": structured}

    def save_suggestion_draft(self, suggestion_id: int, structured: dict, operator: str = "marketer") -> dict:
        structured = apply_dida_gp_rate(sync_query_profiles(structured))
        with self.engine.begin() as conn:
            exists = conn.execute(
                text("SELECT suggestion_id FROM fact_ai_suggestions WHERE suggestion_id = :id"),
                {"id": suggestion_id},
            ).fetchone()
            if not exists:
                return {"ok": False, "error": "Suggestion not found"}
            conn.execute(
                text("""
                UPDATE fact_ai_suggestions
                SET plan_draft_json = :draft,
                    campaign_name = COALESCE(:name, campaign_name),
                    target_dest = COALESCE(:dest, target_dest),
                    promotion_month_hint = COALESCE(:month, promotion_month_hint),
                    demand_analysis = COALESCE(:demand, demand_analysis),
                    solution_analysis = COALESCE(:solution, solution_analysis)
                WHERE suggestion_id = :id
                """),
                {
                    "draft": json.dumps(structured, ensure_ascii=False),
                    "name": (structured.get("basic") or {}).get("campaign_name") or structured.get("campaign_name"),
                    "dest": (structured.get("basic") or {}).get("target_dest") or structured.get("target_dest"),
                    "month": (structured.get("basic") or {}).get("promotion_month") or structured.get("promotion_month"),
                    "demand": (structured.get("data_insights") or {}).get("data_conclusion") or structured.get("demand_analysis"),
                    "solution": (structured.get("strategy") or {}).get("solution_summary") or structured.get("solution_analysis"),
                    "id": suggestion_id,
                },
            )
        return {"ok": True, "suggestion_id": suggestion_id, "structured": structured}

    def get_activity_plan(self, campaign_id: str) -> dict | None:
        sql = "SELECT * FROM dim_campaign WHERE campaign_id = :cid"
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"cid": campaign_id}).fetchone()
            return dict(row._mapping) if row else None

    def update_plan(self, campaign_id: str, updates: dict, editor: str = "marketer") -> dict:
        allowed = {
            "campaign_name", "plan_summary", "target_audience", "demand_analysis",
            "solution_analysis", "execution_steps", "target_metrics", "key_metrics_spec",
            "campaign_type", "start_date", "end_date", "target_dest",
        }
        sets = []
        params = {"cid": campaign_id}
        for k, v in updates.items():
            if k in allowed and v is not None:
                sets.append(f"{k} = :{k}")
                params[k] = v
        if not sets:
            return {"ok": False, "error": "No valid fields"}
        sets.append("updated_at = CURRENT_TIMESTAMP")
        with self.engine.begin() as conn:
            conn.execute(text(f"UPDATE dim_campaign SET {', '.join(sets)} WHERE campaign_id = :cid"), params)
        plan = self.get_activity_plan(campaign_id)
        self.snapshot.save(campaign_id, "agent1", plan or {}, LifecycleStatus.PLAN_REVIEW.value, editor)
        return {"ok": True, "campaign_id": campaign_id, "plan": plan}

    def confirm_send_to_agent2(self, campaign_id: str, operator: str = "marketer") -> dict:
        plan = self.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        if not plan.get("plan_review_confirmed_at"):
            return {
                "ok": False,
                "error": "请先完成方案评审并确认，再发送 Agent2",
                "require_plan_review": True,
            }
        status = self.lifecycle.get_status(campaign_id)
        if status == LifecycleStatus.DRAFT.value:
            self.lifecycle.transition(campaign_id, LifecycleStatus.PLAN_REVIEW.value, operator)
        if status == LifecycleStatus.SENT_TO_AGENT2.value:
            return {"ok": True, "campaign_id": campaign_id, "already_sent": True}
        self.snapshot.save(campaign_id, "agent1", plan, LifecycleStatus.SENT_TO_AGENT2.value, operator)
        return self.lifecycle.transition(
            campaign_id, LifecycleStatus.SENT_TO_AGENT2.value, operator, "营销师确认发送 Agent2"
        )
