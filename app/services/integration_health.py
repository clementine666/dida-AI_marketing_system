"""系统连接配置 — 健康检查与连通性测试（中文结果）。"""

from __future__ import annotations

from app.integrations.feishu_marketing_calendar import FeishuMarketingCalendarClient
from app.integrations.llm_client import LlmClient
from app.mcp.warehouse_client import WarehouseClient
from app.services.config_store import load_integrations, local_calendar_meta


def _local_calendar_meta() -> dict | None:
    return local_calendar_meta()


def integration_status_summary() -> dict:
    """三大数据源当前状态概览。"""
    wh = WarehouseClient()
    fs = FeishuMarketingCalendarClient()
    llm = LlmClient()
    cfg = load_integrations()

    mcp_ok = wh.mode == "warehouse_mcp"
    llm_ok = llm.is_configured()
    local_meta = _local_calendar_meta()
    cal_type = (cfg.get("feishu", {}).get("calendar_type") or "bitable").strip().lower()
    if cal_type == "local":
        fs_ok = bool(local_meta)
        fs_mode = f"Excel 本地（{local_meta.get('rows', '?')} 条）" if local_meta else "Excel 本地（待上传）"
        fs_hint = "拖拽上传飞书导出的 Excel，Agent1 将读取本地文件" if not local_meta else "已从本地 Excel 导入"
    elif local_meta:
        fs_ok = True
        fs_mode = f"本地表格（{local_meta.get('rows', '?')} 条）"
        fs_hint = "已从本地 Excel 导入，Agent1 可读取全年计划"
    elif fs.use_mock:
        fs_ok = False
        fs_mode = "演示数据"
        fs_hint = f"请选择数据来源：飞书表格或 Excel 本地文件（当前：{fs.calendar_type_label()}）"
    else:
        fs_ok = True
        fs_mode = fs.calendar_type_label() + "已连接"
        fs_hint = f"Agent1 可同步全年计划（{fs.calendar_type_label()}）"

    return {
        "data_sources": {
            "mcp": {
                "name": "数仓 MCP（圈客/监控/复盘）",
                "status": "已连通" if mcp_ok else "未连通（演示模式）",
                "ok": mcp_ok,
                "mode": wh.mode,
                "endpoint": cfg.get("warehouse_mcp", {}).get("endpoint"),
                "hint": "填写接口地址 + 鉴权 Key 后测试" if not mcp_ok else "Agent2/3/4 可读取业务数据",
            },
            "feishu": {
                "name": "飞书营销日历",
                "status": "已连接" if fs_ok else "演示数据",
                "ok": fs_ok,
                "mode": fs_mode,
                "calendar_type": fs.calendar_type,
                "calendar_type_label": fs.calendar_type_label(),
                "hint": fs_hint,
            },
            "feishu_bot": {
                "name": "飞书催办机器人",
                "status": "已配置 Webhook" if bool((cfg.get("feishu") or {}).get("bot_webhook_url")) else "未配置",
                "ok": bool((cfg.get("feishu") or {}).get("bot_webhook_url")),
                "hint": "任务监督每天 9:00 向群发送催办" if (cfg.get("feishu") or {}).get("bot_webhook_url") else "在系统连接配置填写群机器人 Webhook",
            },
            "llm": {
                "name": "AI 大模型（行业情报/建议）",
                "status": "已配置" if llm_ok else "未配置",
                "ok": llm_ok,
                "provider": llm.get_active_provider(),
                "model": llm.get_status().get("model"),
                "hint": "未配置时 AI 建议需手工录入；配置后可 LLM 生成" if not llm_ok else "行业情报中心可生成 AI 建议",
            },
        },
        "all_ready": mcp_ok and fs_ok and llm_ok,
    }


def test_mcp_full() -> dict:
    client = WarehouseClient()
    if client.use_local:
        return {
            "ok": False,
            "title": "数仓 MCP",
            "mode": "演示模式（本地 SQLite）",
            "message": "未检测到有效 MCP 配置。请填写「接口地址」和「鉴权 Key」后保存，再点测试。",
            "checks": [
                {"项": "接口地址", "通过": bool(load_integrations().get("warehouse_mcp", {}).get("endpoint")), "说明": "必填"},
                {"项": "鉴权 Key", "通过": bool(load_integrations().get("warehouse_mcp", {}).get("api_key")), "说明": "必填"},
            ],
        }

    checks = []
    health = {"ok": False}
    adapter = client.mcp
    try:
        health = adapter.health_check()
        checks.append({
            "项": "MCP 握手",
            "通过": health.get("ok", False),
            "说明": health.get("error") or f"工具 {len(health.get('tools') or [])} 个",
        })
    except Exception as e:
        checks.append({"项": "MCP 握手", "通过": False, "说明": str(e)})

    checkout_probe = {}
    try:
        from app.mcp.mcp_calendar_fetch import probe_checkout_query

        checkout_probe = probe_checkout_query(adapter)
        checks.append({
            "项": "试查离店指标（analyse_query）",
            "通过": checkout_probe.get("ok", False),
            "说明": (
                f"2026-08 离店订单 {checkout_probe.get('row_count', 0)} 行 · "
                f"{checkout_probe.get('countries', 0)} 国"
            ),
        })
    except Exception as e:
        err = str(e)
        hint = "请确认内网/SASE、agent_user_key 及伽利略指标权限"
        checks.append({"项": "试查离店指标（analyse_query）", "通过": False, "说明": f"{err[:180]} · {hint}"})

    sample = {}
    try:
        sample = client.query_by_profile({
            "destination": "Singapore",
            "client_group_ids": [2, 6],
            "client_limit": 5,
            "hotel_limit": 3,
            "star_min": 4,
        })
        checks.append({
            "项": "试查圈客选品（execute_sql · 可选）",
            "通过": bool(sample.get("client_count", 0) or sample.get("hotel_count", 0)),
            "optional": True,
            "说明": (
                f"客户 {sample.get('client_count', 0)} · 酒店 {sample.get('hotel_count', 0)}"
                if sample.get("client_count", 0) or sample.get("hotel_count", 0)
                else "漏斗 SQL 需表权限；Agent1 标准活动请用上方离店指标试查"
            ),
        })
    except Exception as e:
        checks.append({
            "项": "试查圈客选品（execute_sql · 可选）",
            "通过": False,
            "optional": True,
            "说明": f"{str(e)[:120]} · 需申请 shopping/dwd 表权限（Agent2 用）",
        })

    core_ok = len(checks) >= 2 and checks[0]["通过"] and checks[1]["通过"]
    ok = core_ok
    return {
        "ok": ok,
        "title": "数仓 MCP",
        "mode": "已连通",
        "message": (
            "MCP 离店指标试查成功（Agent1 可用 analyse_query）"
            if core_ok
            else "MCP 已连接但离店指标试查失败，请检查 Key/内网/指标权限"
        ),
        "checks": checks,
        "sample": {
            "离店试查行数": checkout_probe.get("row_count"),
            "离店试查国家数": checkout_probe.get("countries"),
            "离店样例": checkout_probe.get("sample"),
            "圈客客户数": sample.get("client_count"),
        },
        "guide": "https://didatravel.feishu.cn/wiki/UKjawhbpmimBOZk1PEpcdQYYnTh",
    }


def test_feishu_full() -> dict:
    result = FeishuMarketingCalendarClient().test_connection()
    result["title"] = "飞书营销日历"
    return result


def test_llm_full() -> dict:
    llm = LlmClient()
    if not llm.is_configured():
        prov = llm.get_active_provider()
        return {
            "ok": False,
            "title": "AI 大模型",
            "mode": "未配置",
            "message": f"请先填写「{'公司 Dragon API' if prov == 'qwen' else 'DeepSeek'}」的 API Key",
            "checks": [{"项": "API Key", "通过": False, "说明": "必填"}],
        }
    st = llm.get_status()
    try:
        reply = llm.chat([{"role": "user", "content": "请只回复：连接成功"}], temperature=0)
        return {
            "ok": True,
            "title": "AI 大模型",
            "mode": "已配置",
            "message": "模型调用成功",
            "checks": [
                {"项": "当前模型", "通过": True, "说明": f"{st.get('active_provider')} / {st.get('model')}"},
                {"项": "试发对话", "通过": True, "说明": (reply or "")[:40]},
            ],
        }
    except Exception as e:
        return {
            "ok": False,
            "title": "AI 大模型",
            "mode": "配置有误",
            "message": "Key 或地址有误，或当前网络无法访问内网 API",
            "checks": [
                {"项": "地址", "通过": bool(st.get("base_url")), "说明": st.get("base_url")},
                {"项": "试发对话", "通过": False, "说明": str(e)},
            ],
        }


def test_all_integrations() -> dict:
    mcp = test_mcp_full()
    feishu = test_feishu_full()
    llm = test_llm_full()
    return {
        "ok": mcp.get("ok") and feishu.get("ok") and llm.get("ok"),
        "results": {"mcp": mcp, "feishu": feishu, "llm": llm},
        "summary": integration_status_summary(),
    }
