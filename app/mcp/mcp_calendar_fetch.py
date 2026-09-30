"""Agent1 标准活动 · 通过 Data MCP analyse_query 拉取离店/预订数据。

遵循飞书《Data MCP 接入指南》官方指标流程：
search_metrics → get_analyse_dimension → analyse_query

离店订单 ORD_0215 · 离店 TTV(双确认-CNY) ORD_0007 · 维度 dida_hotel_country_name · 按月 date_group_type=4
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.mcp.country_name_normalize import normalize_country_name
from app.mcp.warehouse_mcp_adapter import WarehouseMcpAdapter
from app.services.config_store import load_integrations

CST = timezone(timedelta(hours=8))

# 官方指标（伽利略）
METRIC_CHECKOUT_BKS = "ORD_0215"  # BKs(*checkout)
METRIC_CHECKOUT_TTV = "ORD_0007"  # TTV(*双确认-checkout-CNY)
METRIC_BOOKING_BKS = "ORD_0028"   # BKs(*取消前-checkout) 作预订辅助
METRIC_BOOKING_TTV = "ORD_0013"  # TTV(*取消前-checkout-CNY)
DIM_COUNTRY = "dida_hotel_country_name"


def month_window_to_iso(start_ym: str, end_ym: str) -> tuple[str, str]:
    """YYYY-MM 数据窗 → analyse_query 要求的 ISO UTC 时间（按北京时间日界）。"""
    sy, sm = (int(x) for x in start_ym.split("-", 1))
    ey, em = (int(x) for x in end_ym.split("-", 1))
    begin_local = datetime(sy, sm, 1, 0, 0, 0, tzinfo=CST)
    last_day = calendar.monthrange(ey, em)[1]
    end_local = datetime(ey, em, last_day, 23, 59, 59, 999000, tzinfo=CST)
    begin_iso = begin_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.999Z")
    return begin_iso, end_iso


def _row_month(row: dict) -> str | None:
    for v in row.values():
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}", v):
            return v
    return None


def parse_analyse_table(table_data: dict | None, *, orders_key: str, ttv_key: str) -> list[dict]:
    """将 analyse_query.tableData 转为 checkout_monthly 行列表。"""
    if not table_data:
        return []
    rows = table_data.get("rows") or []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        month = _row_month(row)
        raw_country = row.get(DIM_COUNTRY) or row.get("dida_hotel_country_name")
        if not month or not raw_country:
            continue
        country = normalize_country_name(str(raw_country))
        orders = row.get(orders_key.lower()) or row.get(orders_key)
        ttv = row.get(ttv_key.lower()) or row.get(ttv_key)
        try:
            orders_i = int(float(orders or 0))
        except (TypeError, ValueError):
            orders_i = 0
        try:
            ttv_f = float(ttv or 0)
        except (TypeError, ValueError):
            ttv_f = 0.0
        if orders_i <= 0 and ttv_f <= 0:
            continue
        out.append({"month": month, "country": str(country), "orders": orders_i, "ttv": ttv_f})
    return out


def fetch_calendar_payload_from_mcp(
    adapter: WarehouseMcpAdapter,
    *,
    data_window_start: str,
    data_window_end: str,
    include_booking: bool = True,
) -> dict[str, Any]:
    """调用 MCP analyse_query，返回 manual_calendar_skill 可用的 payload。"""
    begin_iso, end_iso = month_window_to_iso(data_window_start, data_window_end)

    checkout_raw = adapter.analyse_query(
        metrics=[METRIC_CHECKOUT_BKS, METRIC_CHECKOUT_TTV],
        begin_time=begin_iso,
        end_time=end_iso,
        dimensions=[DIM_COUNTRY],
        date_group_type=4,
        group_by_date=True,
    )
    qinfo = checkout_raw.get("queryInfo") or {}
    if qinfo.get("errorMsg"):
        raise RuntimeError(qinfo.get("errorMsg"))

    checkout_monthly = parse_analyse_table(
        checkout_raw.get("tableData"),
        orders_key=METRIC_CHECKOUT_BKS,
        ttv_key=METRIC_CHECKOUT_TTV,
    )
    if not checkout_monthly:
        raise RuntimeError("MCP analyse_query 返回空表，请检查指标权限或时间窗")

    booking_monthly: list[dict] = []
    if include_booking:
        try:
            booking_raw = adapter.analyse_query(
                metrics=[METRIC_BOOKING_BKS, METRIC_BOOKING_TTV],
                begin_time=begin_iso,
                end_time=end_iso,
                dimensions=[DIM_COUNTRY],
                date_group_type=4,
                group_by_date=True,
            )
            booking_monthly = parse_analyse_table(
                booking_raw.get("tableData"),
                orders_key=METRIC_BOOKING_BKS,
                ttv_key=METRIC_BOOKING_TTV,
            )
        except Exception:
            booking_monthly = []

    return {
        "source": "warehouse_mcp",
        "description": "Data MCP analyse_query · 官方离店指标",
        "data_window": {"start": data_window_start, "end": data_window_end},
        "mcp_metrics": {
            "checkout": [METRIC_CHECKOUT_BKS, METRIC_CHECKOUT_TTV],
            "booking": [METRIC_BOOKING_BKS, METRIC_BOOKING_TTV],
        },
        "checkout_monthly": checkout_monthly,
        "booking_monthly": booking_monthly,
        "p75_monthly": [],
        "p75_note": "P75 暂未接入伽利略官方指标，Skill C 在无 P75 行时跳过或沿用配置/mock",
        "query_sql_preview": (qinfo.get("sql") or "")[:500],
        "checkout_row_count": len(checkout_monthly),
    }


def probe_checkout_query(adapter: WarehouseMcpAdapter) -> dict[str, Any]:
    """健康检查：短窗离店指标试查（接入指南推荐 analyse_query 路径）。"""
    begin_iso, end_iso = month_window_to_iso("2026-08", "2026-08")
    raw = adapter.analyse_query(
        metrics=[METRIC_CHECKOUT_BKS, METRIC_CHECKOUT_TTV],
        begin_time=begin_iso,
        end_time=end_iso,
        dimensions=[DIM_COUNTRY],
        date_group_type=4,
        group_by_date=True,
    )
    rows = parse_analyse_table(
        raw.get("tableData"),
        orders_key=METRIC_CHECKOUT_BKS,
        ttv_key=METRIC_CHECKOUT_TTV,
    )
    countries = len({r["country"] for r in rows})
    return {
        "ok": bool(rows),
        "row_count": len(rows),
        "countries": countries,
        "sample": rows[:3],
        "query_id": (raw.get("queryInfo") or {}).get("queryId"),
    }


def test_mcp_ping() -> dict:
    """
    最小打通测试（3 步）—— 不依赖 execute_sql / 复杂 SQL。
    用于验证：配置 + 握手 + analyse_query 离店指标。
    """
    cfg = load_integrations().get("warehouse_mcp", {})
    steps: list[dict] = []

    if not cfg.get("endpoint"):
        steps.append({"step": 1, "name": "配置检查", "ok": False, "detail": "缺少接口地址"})
        return {"ok": False, "title": "MCP 快速Ping", "steps": steps, "message": "请先填写 MCP 接口地址"}
    if not cfg.get("api_key"):
        steps.append({"step": 1, "name": "配置检查", "ok": False, "detail": "缺少鉴权 Key"})
        return {"ok": False, "title": "MCP 快速Ping", "steps": steps, "message": "请先填写 agent_user_key"}

    steps.append({
        "step": 1,
        "name": "配置检查",
        "ok": True,
        "detail": f"endpoint={cfg.get('endpoint')} · header={cfg.get('auth_header') or 'agent_user_key'}",
    })

    adapter = WarehouseMcpAdapter()
    try:
        health = adapter.health_check()
        tool_count = len(health.get("tools") or [])
        steps.append({
            "step": 2,
            "name": "MCP 握手 tools/list",
            "ok": health.get("ok", False),
            "detail": f"工具 {tool_count} 个：{', '.join((health.get('tools') or [])[:5])}{'…' if tool_count > 5 else ''}",
        })
    except Exception as e:
        steps.append({"step": 2, "name": "MCP 握手", "ok": False, "detail": str(e)[:200]})
        return {
            "ok": False,
            "title": "MCP 快速Ping",
            "steps": steps,
            "message": "握手失败：请确认公司内网/SASE 深圳 POP 与 Key 是否正确",
        }

    try:
        probe = probe_checkout_query(adapter)
        steps.append({
            "step": 3,
            "name": "离店指标试查 analyse_query",
            "ok": probe.get("ok", False),
            "detail": (
                f"2026-08 · {probe.get('row_count', 0)} 行 · {probe.get('countries', 0)} 国"
                f" · queryId={probe.get('query_id', '—')}"
            ),
            "sample": probe.get("sample"),
        })
    except Exception as e:
        steps.append({"step": 3, "name": "离店指标试查", "ok": False, "detail": str(e)[:240]})
        return {
            "ok": False,
            "title": "MCP 快速Ping",
            "steps": steps,
            "message": "指标查数失败：Key 权限或网络问题（非 SQL 配置问题）",
        }

    ok = all(s["ok"] for s in steps)
    return {
        "ok": ok,
        "title": "MCP 快速Ping",
        "message": "✅ MCP 已打通（Agent1 标准活动可用）" if ok else "部分步骤失败",
        "steps": steps,
        "agent1_ready": ok,
        "note": "execute_sql 圈客选品为 Agent2 可选能力，需单独申请表权限，不影响本 Ping",
    }
