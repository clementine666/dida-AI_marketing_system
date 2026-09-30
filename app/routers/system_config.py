"""系统配置 API：Agent 提示词、MCP 配置、日历状态。"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Body, File, UploadFile

from app.config import ROOT_DIR
from app.integrations.feishu_marketing_calendar import FeishuMarketingCalendarClient
from app.integrations.llm_client import LlmClient
from app.mcp.warehouse_client import WarehouseClient
from app.services.config_store import integrations_for_ui, load_integrations, save_integrations
from app.mcp.mcp_calendar_fetch import test_mcp_ping
from app.services.integration_health import (
    integration_status_summary,
    test_all_integrations,
    test_feishu_full,
    test_llm_full,
    test_mcp_full,
)

router = APIRouter(prefix="/v2/config", tags=["系统配置"])

AGENTS_CONFIG = ROOT_DIR / "config" / "agents.yaml"


def _load_agents_config() -> dict:
    if not AGENTS_CONFIG.exists():
        return {}
    with AGENTS_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_agents_config(data: dict) -> None:
    AGENTS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with AGENTS_CONFIG.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


@router.get("/agents")
def get_agents_config():
    return _load_agents_config()


@router.put("/agents")
def update_agents_config(body: dict = Body(...)):
    _save_agents_config(body)
    return {"ok": True}


@router.get("/agents/{agent_key}")
def get_agent_config(agent_key: str):
    cfg = _load_agents_config()
    if agent_key not in cfg:
        return {"error": "not found"}
    return {agent_key: cfg[agent_key]}


@router.patch("/agents/{agent_key}")
def patch_agent_config(agent_key: str, body: dict = Body(...)):
    cfg = _load_agents_config()
    if agent_key not in cfg:
        cfg[agent_key] = {}
    cfg[agent_key].update(body)
    _save_agents_config(cfg)
    return {"ok": True, agent_key: cfg[agent_key]}


@router.get("/integrations")
def get_integrations():
    """工作台可读配置（密钥脱敏）。"""
    return integrations_for_ui()


@router.put("/integrations")
def update_integrations(body: dict = Body(...)):
    """
    保存 MCP Key / 飞书 / LLM 配置。
    密钥字段若含 * 则保留原值不覆盖。
    """
    current = load_integrations()

    def _merge_secret(new_val: str | None, old_val: str | None) -> str | None:
        if not new_val or "*" in str(new_val):
            return old_val
        return new_val

    wh = body.get("warehouse_mcp", {})
    if wh:
        cur_wh = current["warehouse_mcp"]
        wh["api_key"] = _merge_secret(wh.get("api_key"), cur_wh.get("api_key"))
        current["warehouse_mcp"] = {**cur_wh, **wh}

    fs = body.get("feishu", {})
    if fs:
        cur_fs = current["feishu"]
        fs["app_secret"] = _merge_secret(fs.get("app_secret"), cur_fs.get("app_secret"))
        fs["bot_webhook_url"] = _merge_secret(fs.get("bot_webhook_url"), cur_fs.get("bot_webhook_url"))
        current["feishu"] = {**cur_fs, **fs}

    llm = body.get("llm", {})
    if llm:
        cur_llm = current["llm"]
        for prov in ("qwen", "deepseek"):
            if prov in llm and isinstance(llm[prov], dict):
                llm[prov]["api_key"] = _merge_secret(
                    llm[prov].get("api_key"), cur_llm.get(prov, {}).get("api_key")
                )
        current["llm"] = _deep_merge_llm(cur_llm, llm)

    saved = save_integrations(current)
    wh_client = WarehouseClient()
    return {
        "ok": True,
        "warehouse_mode": wh_client.mode,
        "llm_configured": LlmClient().is_configured(),
        "config": integrations_for_ui(),
    }


def _deep_merge_llm(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


@router.get("/integrations/status")
def get_integrations_status():
    """三大数据源连接状态（中文）。"""
    return integration_status_summary()


@router.post("/integrations/test-all")
def test_all_connections():
    """一键检测 MCP + 飞书 + LLM。"""
    return test_all_integrations()


@router.post("/integrations/test-mcp")
def test_mcp_connection():
    return test_mcp_full()


@router.post("/integrations/test-mcp-ping")
def test_mcp_ping_connection():
    """最小 3 步 Ping：配置 → 握手 → analyse_query 离店指标（不含 execute_sql）。"""
    return test_mcp_ping()


@router.post("/integrations/test-feishu")
def test_feishu_connection():
    return test_feishu_full()

@router.post("/integrations/test-llm")
def test_llm_connection():
    return test_llm_full()


@router.post("/integrations/test-feishu-bot")
def test_feishu_bot():
    """向飞书群发一条连通测试（含关键词「任务通知」）。"""
    from app.services.v2.task_reminder import send_test_message

    result = send_test_message()
    return {
        "ok": result.get("ok"),
        "title": "飞书催办机器人",
        "mode": "Webhook",
        "message": result.get("message") or result.get("error"),
        "checks": [
            {"项": "Webhook", "通过": result.get("ok", False), "说明": result.get("message") or result.get("error") or ""},
        ],
        "preview": result.get("preview"),
    }


@router.get("/reminders/status")
def reminders_status():
    from app.services.v2.task_reminder import reminder_status

    return reminder_status()


@router.post("/reminders/run")
def reminders_run():
    """立即检查到期任务并发送催办（不等每天 9:00）。"""
    from app.services.v2.task_reminder import run_due_reminders

    return run_due_reminders()


@router.get("/mcp")
def get_mcp_config():
    wh = WarehouseClient()
    feishu = FeishuMarketingCalendarClient()
    cfg = _load_agents_config().get("system", {})
    integ = integrations_for_ui()
    return {
        "warehouse": {
            **wh.get_status(),
            **integ.get("warehouse_mcp", {}),
        },
        "feishu_calendar": {
            "mode": "mock" if feishu.use_mock else "live",
            "app_token": feishu.app_token,
            "url": cfg.get("feishu_calendar_url"),
            **integ.get("feishu", {}),
        },
        "llm": integ.get("llm", {}),
    }


@router.get("/overview")
def get_system_overview():
    from app.services.v2.homepage_metrics import compute_homepage_metrics

    metrics = compute_homepage_metrics()
    return {
        "annual_plan_total": metrics["annual_plan_total"],
        "prep_urgent": metrics["prep_urgent"],
        "ready_to_launch": metrics["ready_to_launch"],
        "executing": metrics["executing"],
        "proposal_library_pending": metrics["proposal_library_pending"],
        # 兼容旧字段名
        "calendar_total": metrics["annual_plan_total"],
        "prep_in_progress": metrics["ready_to_launch"],
        "ai_suggestions_pending": metrics["proposal_library_pending"],
    }


@router.get("/calendar/local-status")
def calendar_local_status():
    """本地营销日历导入状态（无飞书 API 时使用）。"""
    import json
    from datetime import datetime

    target = ROOT_DIR / "data" / "feishu_marketing_calendar_mock.json"
    meta_path = ROOT_DIR / "data" / "feishu_marketing_calendar_meta.json"
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}

    rows = 0
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            rows = len(data) if isinstance(data, list) else 0
        except json.JSONDecodeError:
            rows = 0

    uploaded_at = meta.get("uploaded_at") or ""
    if not uploaded_at and target.exists() and rows > 0:
        uploaded_at = datetime.fromtimestamp(target.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    return {
        "ok": True,
        "has_local": rows > 0 and bool(meta.get("source") == "local_upload" or meta),
        "rows": rows,
        "filename": meta.get("filename") or "",
        "uploaded_at": uploaded_at,
        "source": meta.get("source") or ("local_upload" if meta else "demo"),
        "message": (
            f"已导入本地表格 {rows} 条"
            if meta.get("source") == "local_upload"
            else (f"当前 {rows} 条（演示数据）" if rows else "尚未导入，使用演示数据")
        ),
    }


@router.post("/calendar/upload")
async def upload_calendar(file: UploadFile = File(...)):
    """上传营销日历 XLSX/CSV/JSON，替换本地演示数据（无飞书 API 时的应急方案）。"""
    import json
    from datetime import datetime

    from app.services.calendar_import import parse_calendar_file

    content = await file.read()
    name = file.filename or ""
    target = ROOT_DIR / "data" / "feishu_marketing_calendar_mock.json"
    meta_path = ROOT_DIR / "data" / "feishu_marketing_calendar_meta.json"
    try:
        data = parse_calendar_file(content, name)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "source": "local_upload",
                "filename": name,
                "rows": len(data),
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "rows": len(data),
        "filename": name,
        "target": str(target.name),
        "message": f"已导入 {len(data)} 条营销日历，Agent1 将读取此本地数据",
    }
