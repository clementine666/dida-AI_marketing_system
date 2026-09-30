"""Agent1 行业情报：任务配置、采集、上传、LLM 生成活动建议。"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import ROOT_DIR
from app.db import get_engine
from app.integrations.llm_client import LlmClient
from app.models.planner import SUGGESTION_PENDING, SUGGESTION_REJECTED
from app.services.v2.activity_doc_parser import apply_dida_gp_rate, gp_from_ttv, parse_calendar_dir, plan_from_llm_suggestion

INTEL_TASKS_FILE = ROOT_DIR / "config" / "intel_tasks.yaml"
INTEL_UPLOAD_DIR = ROOT_DIR / "data" / "intel_uploads"
AGENTS_CONFIG = ROOT_DIR / "config" / "agents.yaml"


class IntelService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.llm = LlmClient()
        INTEL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ── 任务配置 ──────────────────────────────────────────────

    def load_tasks_config(self) -> dict:
        if not INTEL_TASKS_FILE.exists():
            return {"tasks": [], "collection_prompt": "", "output_schema_hint": ""}
        with INTEL_TASKS_FILE.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_tasks_config(self, data: dict) -> dict:
        INTEL_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with INTEL_TASKS_FILE.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return {"ok": True}

    def list_tasks(self) -> dict:
        cfg = self.load_tasks_config()
        return {
            "collection_prompt": cfg.get("collection_prompt", ""),
            "output_schema_hint": cfg.get("output_schema_hint", ""),
            "tasks": cfg.get("tasks", []),
            "llm_configured": self.llm.is_configured(),
        }

    # ── 情报入库 ──────────────────────────────────────────────

    def list_reports(self, limit: int = 50) -> list[dict]:
        sql = """
        SELECT * FROM fact_industry_intel
        ORDER BY report_date DESC, created_at DESC LIMIT :limit
        """
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), {"limit": limit})]

    def save_report(self, report: dict) -> dict:
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO fact_industry_intel
                (report_title, report_type, source_channel, collect_frequency, report_date,
                 destination_tags, summary, full_content, activity_suggestions, feature_suggestions)
                VALUES (:report_title,:report_type,:source_channel,:collect_frequency,:report_date,
                        :destination_tags,:summary,:full_content,:activity_suggestions,:feature_suggestions)
                """),
                {
                    "report_title": report.get("report_title") or f"上传报告 ({date.today()})",
                    "report_type": report.get("report_type") or "upload",
                    "source_channel": report.get("source_channel") or "manual_upload",
                    "collect_frequency": report.get("collect_frequency") or "manual",
                    "report_date": report.get("report_date") or str(date.today()),
                    "destination_tags": report.get("destination_tags") or "",
                    "summary": report.get("summary") or "",
                    "full_content": report.get("full_content") or "",
                    "activity_suggestions": report.get("activity_suggestions")
                    if isinstance(report.get("activity_suggestions"), str)
                    else json.dumps(report.get("activity_suggestions") or [], ensure_ascii=False),
                    "feature_suggestions": report.get("feature_suggestions")
                    if isinstance(report.get("feature_suggestions"), str)
                    else json.dumps(report.get("feature_suggestions") or [], ensure_ascii=False),
                },
            )
            intel_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
        return {"ok": True, "intel_id": intel_id}

    def upload_from_url(
        self,
        url: str,
        *,
        title: str | None = None,
        destinations: str = "",
    ) -> dict:
        from app.services.v2.article_fetcher import fetch_article_from_url

        fetched = fetch_article_from_url(url)
        report_title = (title or fetched.get("title") or "链接抓取").strip()
        summary = (
            f"自动抓取 · {fetched.get('source_type')} · {fetched.get('char_count', 0)} 字 · "
            f"{fetched.get('url', url)}"
        )
        path = INTEL_UPLOAD_DIR / f"{date.today()}_url_{len(list(INTEL_UPLOAD_DIR.glob('*')))}.txt"
        path.write_text(fetched.get("content") or "", encoding="utf-8")
        result = self.save_report(
            {
                "report_title": report_title,
                "report_type": fetched.get("source_type") or "url",
                "source_channel": "url_fetch",
                "collect_frequency": "manual",
                "destination_tags": destinations,
                "summary": summary,
                "full_content": fetched.get("content") or "",
                "activity_suggestions": "[]",
            }
        )
        result["fetch"] = {
            "url": fetched.get("url"),
            "source_type": fetched.get("source_type"),
            "char_count": fetched.get("char_count"),
            "title": fetched.get("title"),
        }
        return result

    def upload_text_report(
        self,
        title: str,
        content: str,
        *,
        summary: str | None = None,
        destinations: str = "",
        report_type: str = "upload",
    ) -> dict:
        path = INTEL_UPLOAD_DIR / f"{date.today()}_{len(list(INTEL_UPLOAD_DIR.glob('*')))}.txt"
        path.write_text(content, encoding="utf-8")
        return self.save_report(
            {
                "report_title": title,
                "report_type": report_type,
                "source_channel": "upload",
                "collect_frequency": "manual",
                "destination_tags": destinations,
                "summary": summary or content[:500],
                "full_content": content,
                "activity_suggestions": "[]",
            }
        )

    def run_collection_tasks(self) -> dict:
        """执行已启用的采集任务（URL 类为占位，生产可接爬虫）。"""
        cfg = self.load_tasks_config()
        saved = 0
        results = []
        for task in cfg.get("tasks", []):
            if not task.get("enabled"):
                continue
            if task.get("source_type") == "upload":
                continue
            report = {
                "report_title": f"{task.get('title')} ({date.today()})",
                "report_type": task.get("source_type", "url"),
                "source_channel": task.get("task_id", "task"),
                "collect_frequency": task.get("frequency", "manual"),
                "destination_tags": task.get("destinations", ""),
                "summary": (
                    f"【采集任务】{task.get('title')}。"
                    f"说明：{task.get('scrape_instruction', '')}。"
                    f"来源：{task.get('source_url') or '（待配置 URL，当前为框架占位）'}"
                ),
                "full_content": json.dumps(task, ensure_ascii=False),
                "activity_suggestions": json.dumps([], ensure_ascii=False),
            }
            self.save_report(report)
            saved += 1
            results.append({"task_id": task.get("task_id"), "title": task.get("title"), "status": "saved_placeholder"})
        return {"ok": True, "saved": saved, "results": results}

    # ── LLM 生成 AI 活动建议 ──────────────────────────────────

    def _load_agent1_intel_prompt(self) -> str:
        from app.services.prompt_store import get_prompt

        p = get_prompt("ai_creative")
        if p and (p.get("content") or "").strip():
            return p["content"].strip()
        if AGENTS_CONFIG.exists():
            with AGENTS_CONFIG.open(encoding="utf-8") as f:
                agents = yaml.safe_load(f) or {}
            extra = (agents.get("agent1") or {}).get("intel_collection_prompt")
            if extra:
                return extra.strip()
        cfg = self.load_tasks_config()
        return (cfg.get("collection_prompt") or "").strip()

    @staticmethod
    def _parse_llm_json(raw: str) -> dict:
        text_val = raw.strip()
        m = re.search(r"\{[\s\S]*\}", text_val)
        if m:
            text_val = m.group(0)
        return json.loads(text_val)

    def generate_suggestions_with_llm(
        self,
        intel_limit: int = 8,
        year: int | str | None = 2027,
        extra_instruction: str = "",
        *,
        intel_id: int | None = None,
        preview_only: bool = False,
    ) -> dict:
        if not self.llm.is_configured():
            return {"ok": False, "error": "LLM 未配置，请在工作台 MCP 配置页填写 Qwen/DeepSeek API Key"}

        if intel_id is not None:
            reports = [r for r in self.list_reports(limit=100) if r.get("intel_id") == intel_id]
            if not reports:
                return {"ok": False, "error": f"情报 #{intel_id} 不存在"}
        else:
            reports = self.list_reports(limit=int(intel_limit))
        if not reports:
            return {"ok": False, "error": "暂无行业情报，请先运行采集任务或上传报告"}

        intel_block = []
        for r in reports:
            intel_block.append(
                f"### {r.get('report_title')}\n"
                f"日期:{r.get('report_date')} 目的地:{r.get('destination_tags')}\n"
                f"摘要:{r.get('summary')}\n"
                f"全文:{(r.get('full_content') or '')[:8000]}\n"
            )

        cfg = self.load_tasks_config()
        system = self._load_agent1_intel_prompt() or "你是 B2B 酒店营销情报分析师。"
        schema = cfg.get("output_schema_hint") or '{"suggestions":[]}'
        plan_year = str(year or 2027)
        extra = (extra_instruction or "").strip()
        user_msg = (
            f"当前日期：{date.today().isoformat()}。本次任务：输出 {plan_year} 全年营销活动创意，"
            "覆盖 1–12 月，12–16 条，旅行社与 TMC 分条，只出画像不出 ID。"
            "亚洲至少提前 3 个月，非亚洲至少提前半年；太近的窗口不要出。\n"
            + (f"补充指令：{extra}\n" if extra else "")
            + "\n请基于以下行业情报与目的地日历生成（JSON）。\n\n"
            + "\n".join(intel_block)
            + f"\n\n输出格式：{schema}"
        )

        try:
            reply = self.llm.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=8000,
            )
            parsed = self._parse_llm_json(reply)
        except Exception as exc:
            return {"ok": False, "error": f"LLM 调用失败: {exc}"}

        suggestions = parsed.get("suggestions") or []
        if not isinstance(suggestions, list):
            return {"ok": False, "error": "LLM 返回格式无效，缺少 suggestions 数组"}

        source_intel = reports[0] if reports else {}
        if preview_only:
            return {
                "ok": True,
                "preview": True,
                "llm_provider": self.llm.get_active_provider(),
                "suggestions": suggestions,
                "raw_count": len(suggestions),
                "intel_id": source_intel.get("intel_id"),
                "intel_title": source_intel.get("report_title"),
            }

        inserted = self._insert_llm_suggestions(suggestions, source_intel)
        return {
            "ok": True,
            "llm_provider": self.llm.get_active_provider(),
            "generated": inserted,
            "raw_count": len(suggestions),
            "intel_id": source_intel.get("intel_id"),
        }

    def submit_suggestions(self, suggestions: list[dict], *, intel_id: int | None = None) -> dict:
        if not suggestions:
            return {"ok": False, "error": "没有可提交的活动建议"}
        source_intel: dict = {}
        if intel_id is not None:
            source_intel = next(
                (r for r in self.list_reports(limit=100) if r.get("intel_id") == intel_id),
                {},
            )
        inserted = self._insert_llm_suggestions(suggestions, source_intel)
        return {"ok": True, "inserted": inserted, "skipped": len(suggestions) - inserted}

    def _insert_llm_suggestions(self, suggestions: list[dict], source_intel: dict) -> int:
        import hashlib

        count = 0
        for sug in suggestions:
            name = (sug.get("campaign_name") or "").strip()
            if not name:
                continue
            derived_gp = gp_from_ttv(str(sug.get("expected_ttv") or ""))
            if derived_gp:
                sug["expected_gp"] = derived_gp
            extra_bits = []
            for label, key_name in (
                ("优先级", "priority"),
                ("评分", "score"),
                ("上线日", "go_live_date"),
                ("入住窗", "stay_window"),
                ("预期TTV", "expected_ttv"),
                ("预期GP", "expected_gp"),
            ):
                val = sug.get(key_name)
                if val not in (None, ""):
                    extra_bits.append(f"{label}：{val}")
            rationale = (sug.get("rationale") or f"LLM 基于情报「{source_intel.get('report_title', '')}」生成").strip()
            if extra_bits:
                rationale = rationale + "\n" + "；".join(extra_bits)
            demand = (sug.get("demand_analysis") or sug.get("customer_profile") or "").strip()
            solution = (sug.get("solution_analysis") or sug.get("hotel_profile") or "").strip()
            key = hashlib.md5(f"llm:{name}:{sug.get('target_dest')}:{source_intel.get('intel_id')}".encode()).hexdigest()
            structured = sug.get("plan") if isinstance(sug.get("plan"), dict) else plan_from_llm_suggestion(
                sug, source_intel.get("report_title") or ""
            )
            structured = apply_dida_gp_rate(structured if isinstance(structured, dict) else {})
            draft = json.dumps(structured, ensure_ascii=False)
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
                     intel_id, intel_report_title, status, plan_draft_json)
                    VALUES (:key, :name, :dest, :promo, :rationale, :demand, :solution,
                            :iid, :title, :status, :draft)
                    """),
                    {
                        "key": key,
                        "name": name[:200],
                        "dest": sug.get("target_dest"),
                        "promo": sug.get("promotion_month_hint"),
                        "rationale": rationale,
                        "demand": demand,
                        "solution": solution,
                        "iid": source_intel.get("intel_id"),
                        "title": source_intel.get("report_title"),
                        "status": SUGGESTION_PENDING,
                        "draft": draft,
                    },
                )
                count += 1
        return count

    def import_markdown_calendar(self, folder: str | Path, *, reject_thin_pending: bool = True) -> dict:
        """把月度决策卡 Markdown 导入 AI 创意池，写入完整评审方案。"""
        folder = Path(folder)
        items = parse_calendar_dir(folder)
        rejected = 0
        inserted = 0
        updated = 0
        with self.engine.begin() as conn:
            if reject_thin_pending:
                res = conn.execute(
                    text("""
                    UPDATE fact_ai_suggestions
                    SET status = :st, reviewed_by = 'system', reviewed_at = CURRENT_TIMESTAMP
                    WHERE status = :pending AND suggestion_key NOT LIKE :wb
                    """),
                    {"st": SUGGESTION_REJECTED, "pending": SUGGESTION_PENDING, "wb": "wb2027:%"},
                )
                rejected = res.rowcount or 0
            for item in items:
                draft = json.dumps(item["plan"], ensure_ascii=False)
                exists = conn.execute(
                    text("SELECT suggestion_id FROM fact_ai_suggestions WHERE suggestion_key = :k"),
                    {"k": item["suggestion_key"]},
                ).fetchone()
                params = {
                    "key": item["suggestion_key"],
                    "name": item["campaign_name"][:200],
                    "dest": item["target_dest"],
                    "promo": item["promotion_month_hint"],
                    "rationale": item["rationale"],
                    "demand": item["demand_analysis"],
                    "solution": item["solution_analysis"],
                    "title": f"WorkBuddy 2027营销活动日历 · {item['source_file']}",
                    "status": SUGGESTION_PENDING,
                    "draft": draft,
                }
                if exists:
                    conn.execute(
                        text("""
                        UPDATE fact_ai_suggestions
                        SET campaign_name = :name, target_dest = :dest,
                            promotion_month_hint = :promo, rationale = :rationale,
                            demand_analysis = :demand, solution_analysis = :solution,
                            intel_report_title = :title, status = :status,
                            plan_draft_json = :draft, reviewed_by = NULL, reviewed_at = NULL
                        WHERE suggestion_key = :key
                        """),
                        params,
                    )
                    updated += 1
                else:
                    conn.execute(
                        text("""
                        INSERT INTO fact_ai_suggestions
                        (suggestion_key, campaign_name, target_dest, promotion_month_hint,
                         rationale, demand_analysis, solution_analysis,
                         intel_report_title, status, plan_draft_json)
                        VALUES (:key, :name, :dest, :promo, :rationale, :demand, :solution,
                                :title, :status, :draft)
                        """),
                        params,
                    )
                    inserted += 1
        return {
            "ok": True,
            "folder": str(folder),
            "parsed": len(items),
            "inserted": inserted,
            "updated": updated,
            "rejected_thin": rejected,
        }
