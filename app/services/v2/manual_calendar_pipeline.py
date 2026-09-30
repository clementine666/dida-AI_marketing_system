"""标准活动规划流水线：MCP 取数 → AI/Skill 分析 → 营销日历初版。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.integrations.llm_client import LlmClient
from app.mcp.warehouse_mcp_adapter import WarehouseMcpAdapter
from app.mcp.mcp_calendar_fetch import METRIC_CHECKOUT_BKS, METRIC_CHECKOUT_TTV
from app.services.prompt_store import get_prompt
from app.services.v2.manual_calendar_skill import ManualCalendarSkillService

ROOT = Path(__file__).resolve().parents[3]
MOCK_MCP_FILE = ROOT / "data" / "mock" / "mcp_calendar_fetch.json"


def _load_ai_prompt() -> tuple[str, str]:
    p = get_prompt("manual_calendar_ai") or {}
    content = (p.get("content") or "").strip()
    notes = (p.get("notes") or "").strip()
    return content, notes


def _summarize_mcp_payload(payload: dict) -> dict:
    checkout = payload.get("checkout_monthly") or []
    booking = payload.get("booking_monthly") or []
    p75 = payload.get("p75_monthly") or []
    return {
        "checkout_rows": len(checkout),
        "booking_rows": len(booking),
        "p75_rows": len(p75),
        "countries": len({r.get("country") for r in checkout if r.get("country")}),
        "months": sorted({str(r.get("month")) for r in checkout if r.get("month")}),
        "sample_checkout": checkout[:20],
        "sample_p75": p75[:6],
    }


def _analysis_context(skill_result: dict) -> dict:
    """供 LLM 使用的飞书同构过程表 + 候选摘要。"""
    cands = skill_result.get("candidates") or []
    top_cands = sorted(cands, key=lambda x: (-(x.get("month_ttv") or 0), x.get("month_rank") or 99))[:40]
    return {
        "data_window": skill_result.get("data_window"),
        "continent_totals": skill_result.get("continent_totals"),
        "ttv_share_table": skill_result.get("ttv_share_table") or [],
        "p75_table": skill_result.get("p75_table") or [],
        "combined_groups": skill_result.get("combined_groups") or [],
        "candidates": top_cands,
        "summary": skill_result.get("summary"),
    }


def load_mock_mcp_payload() -> dict:
    if MOCK_MCP_FILE.exists():
        return json.loads(MOCK_MCP_FILE.read_text(encoding="utf-8"))
    return {"source": "simulate", "checkout_monthly": [], "booking_monthly": [], "p75_monthly": []}


def fetch_mcp_data(fetch_prompt: str, mode: str, mc: dict) -> tuple[dict, dict]:
    """Step 1：MCP 取数。mode=simulate 用 mock；mcp/auto 走 analyse_query（接入指南 §5.1）。"""
    step: dict[str, Any] = {
        "step": 1,
        "name": "MCP 取数",
        "fetch_prompt_preview": (fetch_prompt or "")[:300],
    }
    win_start = mc.get("data_window_start") or "2026-08"
    win_end = mc.get("data_window_end") or "2027-07"

    if mode == "simulate":
        payload = load_mock_mcp_payload()
        payload["data_window"] = {"start": win_start, "end": win_end}
        payload["source"] = "simulate"
        step.update({
            "status": "simulate",
            "message": f"使用虚拟数仓数据（{payload.get('description', 'mock')}）",
            "detail": _summarize_mcp_payload(payload),
        })
        return payload, step

    adapter = WarehouseMcpAdapter()
    if mode == "mcp" and not adapter.is_configured:
        raise RuntimeError("MCP 未配置，请先在「通用底座」填写接口地址与 Key")

    mcp_error = None
    if adapter.is_configured and mode in ("mcp", "auto"):
        try:
            from app.mcp.mcp_calendar_fetch import fetch_calendar_payload_from_mcp

            health = adapter.health_check()
            if not health.get("ok"):
                raise RuntimeError(health.get("error") or "MCP 握手失败")
            payload = fetch_calendar_payload_from_mcp(
                adapter,
                data_window_start=win_start,
                data_window_end=win_end,
            )
            # P75 暂无官方指标：若 mock 存在则合并演示 Skill C
            if not payload.get("p75_monthly"):
                mock_p75 = load_mock_mcp_payload().get("p75_monthly") or []
                if mock_p75:
                    payload["p75_monthly"] = mock_p75
                    payload["p75_note"] = (payload.get("p75_note") or "") + " · 已合并 mock P75"
            step.update({
                "status": "mcp",
                "message": (
                    f"Data MCP analyse_query 成功：离店 {payload.get('checkout_row_count', 0)} 行"
                    f"（{METRIC_CHECKOUT_BKS}/{METRIC_CHECKOUT_TTV}）"
                ),
                "detail": _summarize_mcp_payload(payload),
            })
            return payload, step
        except Exception as e:
            mcp_error = str(e)
            if mode == "mcp":
                step.update({"status": "error", "message": mcp_error})
                raise

    payload = load_mock_mcp_payload()
    payload["source"] = "simulate_fallback"
    payload["mcp_error"] = mcp_error
    payload["data_window"] = {"start": win_start, "end": win_end}
    step.update({
        "status": "fallback_simulate",
        "message": f"MCP 暂不可用（{mcp_error}），已自动使用虚拟数据演示",
        "detail": _summarize_mcp_payload(payload),
    })
    return payload, step


def _parse_llm_draft_rows(raw: str) -> list[dict]:
    m = re.search(r"\{[\s\S]*\}", raw.strip())
    text = m.group(0) if m else raw
    data = json.loads(text)
    if isinstance(data, list):
        return data
    return data.get("draft_rows") or data.get("rows") or []


def analyze_calendar(
    skill: ManualCalendarSkillService,
    mcp_payload: dict,
    *,
    top_units: int,
    top_months: int,
    min_share: float,
) -> tuple[dict, dict]:
    """Step 2：先 Skill 生成飞书同构过程表，再 AI 按初版表 A–O 列输出。"""
    ai_content, ai_notes = _load_ai_prompt()
    llm = LlmClient()
    step: dict[str, Any] = {"step": 2, "name": "AI 分析与日历输出"}

    skill_result = skill.generate_from_mcp_payload(
        mcp_payload,
        top_units_per_continent=top_units,
        top_months_per_unit=top_months,
        min_month_share=min_share,
        data_source=mcp_payload.get("source", "simulate"),
    )
    if not skill_result.get("ok", True):
        step.update({"status": "error", "message": skill_result.get("error", "Skill 分析失败")})
        return skill_result, step

    ctx = _analysis_context(skill_result)

    if llm.is_configured() and ai_content:
        system = ai_content
        if ai_notes:
            system += f"\n\n【配置备注】\n{ai_notes}"
        user_msg = (
            "以下为 Skill 已按飞书过程表结构计算好的分析上下文（JSON）。\n"
            "请严格按 Prompt 输出「27年营销日历初版」A–O 列 draft_rows。\n"
            "优先使用 ttv_share_table / p75_table / candidates 中的数字，禁止编造。\n\n"
            f"{json.dumps(ctx, ensure_ascii=False, indent=2)}"
        )
        try:
            reply = llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0.2,
                max_tokens=8000,
            )
            draft_rows = _parse_llm_draft_rows(reply)
            for row in draft_rows:
                row.setdefault("plan_source", "manual_ai")
                row.setdefault("sub_theme", row.get("副活动主题(按目的地/区域)") or row.get("sub_theme"))
                row.setdefault("destinations", row.get("覆盖目的地/城市") or row.get("destinations"))
                row.setdefault(
                    "checkout_window",
                    row.get("对应出游/离店窗口(促销月份)") or row.get("checkout_window"),
                )
                row.setdefault("p75_days", row.get("关键P75(目标离店月·天)") or row.get("p75_days"))
                row.setdefault(
                    "evidence",
                    row.get("选目的地数据依据·节庆/旺季(Top/峰值/淡旺季)") or row.get("evidence"),
                )
            step.update({
                "status": "llm",
                "message": f"AI 已按飞书初版表格式输出 {len(draft_rows)} 条",
                "analyzer": "llm",
                "ai_prompt_length": len(ai_content),
            })
            if draft_rows:
                skill_result["draft_rows"] = draft_rows
            skill_result["ai_raw_preview"] = (reply or "")[:500]
            return skill_result, step
        except Exception as e:
            step["llm_error"] = str(e)

    step.update({
        "status": "skill_fallback",
        "message": (
            "AI Prompt 未填或 LLM 调用失败，已用 Skill A/B/C 输出飞书同构初版表"
            + (f"；LLM 错误：{step.get('llm_error')}" if step.get("llm_error") else "")
        ),
        "analyzer": "skill_abc",
        "ai_prompt_ready": bool(ai_content),
        "llm_configured": llm.is_configured(),
    })
    return skill_result, step


def run_manual_calendar_pipeline(
    skill: ManualCalendarSkillService,
    *,
    mode: str = "auto",
    top_units_per_continent: int = 5,
    top_months_per_unit: int = 5,
    min_month_share: float = 0.06,
) -> dict[str, Any]:
    mc = skill._manual_config()
    fetch_prompt = skill._resolved_fetch_prompt()
    fetch_step_payload, fetch_step = fetch_mcp_data(fetch_prompt, mode, mc)
    result, analyze_step = analyze_calendar(
        skill,
        fetch_step_payload,
        top_units=top_units_per_continent,
        top_months=top_months_per_unit,
        min_share=min_month_share,
    )
    result["pipeline"] = [fetch_step, analyze_step]
    result["mcp_fetch_prompt"] = fetch_prompt
    result["mcp_data_summary"] = _summarize_mcp_payload(fetch_step_payload)
    result["mode"] = mode
    return result
