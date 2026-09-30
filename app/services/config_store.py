"""集成配置读写（MCP / 飞书 / LLM），供工作台 UI 保存。"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.config import ROOT_DIR

INTEGRATIONS_FILE = ROOT_DIR / "config" / "integrations.yaml"
AGENTS_CONFIG_FILE = ROOT_DIR / "config" / "agents.yaml"

_DEFAULTS: dict[str, Any] = {
    "warehouse_mcp": {
        "enabled": True,
        "endpoint": "https://data-api-mcp.didaadmin.com/mcp/v1/query",
        "protocol": "streamable_http",
        "auth_header": "agent_user_key",
        "api_key": "",
        "use_local_fallback": True,
        "tables": {
            "events": "shopping.ods_amplitude_events",
            "users": "shopping.ods_amplitude_users",
            "funnel": "dwd.dwd_hotel_shopping_funnel_detail_d_f",
            "orders": "booking.channelbooking_v2",
        },
    },
        "feishu": {
            "calendar_type": "bitable",
            "app_id": "",
            "app_secret": "",
            "app_token": "GpYkbnH9ga8nMAs0GUQcCXoInXe",
            "marketing_calendar_table_id": "",
            "marketing_calendar_view_id": "",
            "spreadsheet_token": "",
            "sheet_id": "",
            "sheet_range": "",
            "bot_webhook_url": "",
            "bot_keyword": "任务通知",
        },
    "llm": {
        "default_provider": "qwen",
        "qwen": {"api_key": "", "base_url": "http://dragon-open-api.didainternal.com/v1", "model": "qwen3.7-plus"},
        "deepseek": {"api_key": "", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
        "industry_intel": {"provider": "qwen", "temperature": 0.3},
    },
    "image_gen": {
        "provider": "inherit",
        "api_key": "",
        "base_url": "",
        "model": "",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_integrations() -> dict:
    data = deepcopy(_DEFAULTS)
    if INTEGRATIONS_FILE.exists():
        with INTEGRATIONS_FILE.open(encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
        data = _deep_merge(data, file_cfg)

    # 环境变量优先级更高（运维可覆盖）
    wh = data["warehouse_mcp"]
    if os.getenv("WAREHOUSE_MCP_ENDPOINT"):
        wh["endpoint"] = os.getenv("WAREHOUSE_MCP_ENDPOINT", "")
    if os.getenv("WAREHOUSE_MCP_API_KEY"):
        wh["api_key"] = os.getenv("WAREHOUSE_MCP_API_KEY", "")
    if os.getenv("WAREHOUSE_MCP_SQL_PATH"):
        wh["sql_path"] = os.getenv("WAREHOUSE_MCP_SQL_PATH", wh["sql_path"])

    fs = data["feishu"]
    for key, env in [
        ("app_id", "FEISHU_APP_ID"),
        ("app_secret", "FEISHU_APP_SECRET"),
        ("marketing_calendar_table_id", "FEISHU_MARKETING_CALENDAR_TABLE_ID"),
        ("marketing_calendar_view_id", "FEISHU_MARKETING_CALENDAR_VIEW_ID"),
        ("bot_webhook_url", "FEISHU_BOT_WEBHOOK_URL"),
        ("bot_keyword", "FEISHU_BOT_KEYWORD"),
    ]:
        if os.getenv(env):
            fs[key] = os.getenv(env, "")

    llm = data["llm"]
    qwen = llm.setdefault("qwen", {})
    if os.getenv("LLM_API_KEY"):
        qwen["api_key"] = os.getenv("LLM_API_KEY", "")
    if os.getenv("LLM_BASE_URL"):
        qwen["base_url"] = os.getenv("LLM_BASE_URL", "")
    if os.getenv("LLM_MODEL"):
        qwen["model"] = os.getenv("LLM_MODEL", "")
    if os.getenv("QWEN_API_KEY"):
        qwen["api_key"] = os.getenv("QWEN_API_KEY", "")
    if os.getenv("DEEPSEEK_API_KEY"):
        llm["deepseek"]["api_key"] = os.getenv("DEEPSEEK_API_KEY", "")

    return data


def save_integrations(updates: dict) -> dict:
    current = load_integrations()
    merged = _deep_merge(current, updates)
    INTEGRATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INTEGRATIONS_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(merged, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return merged


def _feishu_configured(fs: dict) -> bool:
    cal_type = (fs.get("calendar_type") or "bitable").strip().lower()
    if cal_type == "local":
        return bool(local_calendar_meta())
    if not (fs.get("app_id") and fs.get("app_secret")):
        return False
    if cal_type == "sheet":
        return bool(fs.get("spreadsheet_token") and (fs.get("sheet_id") or fs.get("sheet_range")))
    return bool(fs.get("marketing_calendar_table_id"))


def local_calendar_meta() -> dict | None:
    import json

    meta_path = ROOT_DIR / "data" / "feishu_marketing_calendar_meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return meta if meta.get("source") == "local_upload" else None


def mask_secret(val: str | None, show: int = 4) -> str:
    if not val:
        return ""
    if len(val) <= show * 2:
        return "*" * len(val)
    return val[:show] + "*" * (len(val) - show * 2) + val[-show:]


def integrations_for_ui() -> dict:
    """返回给 UI 的配置（密钥脱敏）。"""
    cfg = load_integrations()
    wh = cfg["warehouse_mcp"]
    fs = cfg["feishu"]
    llm = cfg["llm"]
    return {
        "warehouse_mcp": {
            **wh,
            "api_key": mask_secret(wh.get("api_key")),
            "api_key_set": bool(wh.get("api_key")),
            "mode": "warehouse_mcp" if wh.get("endpoint") and wh.get("api_key") else "local_sqlite",
        },
        "feishu": {
            **fs,
            "app_secret": mask_secret(fs.get("app_secret")),
            "app_secret_set": bool(fs.get("app_secret")),
            "bot_webhook_url": mask_secret(fs.get("bot_webhook_url"), show=8),
            "bot_webhook_url_set": bool(fs.get("bot_webhook_url")),
            "connected": _feishu_configured(fs),
        },
        "llm": {
            "default_provider": llm.get("default_provider"),
            "industry_intel": llm.get("industry_intel"),
            "qwen": {**llm.get("qwen", {}), "api_key": mask_secret(llm["qwen"].get("api_key")), "api_key_set": bool(llm["qwen"].get("api_key"))},
            "deepseek": {**llm.get("deepseek", {}), "api_key": mask_secret(llm["deepseek"].get("api_key")), "api_key_set": bool(llm["deepseek"].get("api_key"))},
        },
        "image_gen": {
            **cfg.get("image_gen", {}),
            "api_key": mask_secret(cfg.get("image_gen", {}).get("api_key")),
            "api_key_set": bool(cfg.get("image_gen", {}).get("api_key")),
        },
    }


def load_agent_config(agent_key: str) -> dict | None:
    """读取单个 Agent 配置（agents.yaml）。"""
    if not AGENTS_CONFIG_FILE.exists():
        return None
    with AGENTS_CONFIG_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(agent_key)
