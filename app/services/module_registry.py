"""系统功能模块注册表（读 config/modules.yaml）。"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.config import ROOT_DIR
from app.services.prompt_store import list_prompts, prompt_status

MODULES_CONFIG = ROOT_DIR / "config" / "modules.yaml"


def load_modules_config() -> dict:
    if not MODULES_CONFIG.exists():
        return {"phases": [], "modules": []}
    with MODULES_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_phases() -> list[dict]:
    return load_modules_config().get("phases") or []


def get_modules(enriched: bool = True) -> list[dict]:
    raw = load_modules_config().get("modules") or []
    if not enriched:
        return raw
    prompts = {p["key"]: p for p in list_prompts()}
    out = []
    for m in raw:
        item = dict(m)
        pk = item.get("prompt_key")
        if pk and pk in prompts:
            ps = prompts[pk]
            item["prompt_status"] = ps.get("status")
            item["prompt_filled"] = bool((ps.get("content") or "").strip())
            if item.get("status") == "placeholder" and item["prompt_filled"]:
                item["effective_status"] = "ready"
            else:
                item["effective_status"] = item.get("status", "skeleton")
        else:
            item["effective_status"] = item.get("status", "skeleton")
        out.append(item)
    return out


def get_module_map() -> dict:
    """按阶段分组的模块树，供前端总览。"""
    phases = {p["id"]: {**p, "modules": []} for p in get_phases()}
    phases["system"] = {
        "id": "system",
        "name": "系统管理",
        "agent": "system",
        "agent_label": "系统管理",
        "steps": [],
        "modules": [],
    }
    for m in get_modules():
        pid = m.get("phase") or "system"
        if pid not in phases:
            phases[pid] = {"id": pid, "name": pid, "modules": []}
        phases[pid]["modules"].append(m)
    order = [p["id"] for p in get_phases()] + ["system"]
    return {
        "version": load_modules_config().get("version"),
        "sop_source": load_modules_config().get("sop_source"),
        "phases": [phases[pid] for pid in order if pid in phases],
        "summary": _summary(get_modules()),
    }


def _summary(modules: list[dict]) -> dict:
    counts = {"skeleton": 0, "placeholder": 0, "ready": 0}
    for m in modules:
        st = m.get("effective_status") or m.get("status") or "skeleton"
        if st in counts:
            counts[st] += 1
        else:
            counts["skeleton"] += 1
    return {"total": len(modules), **counts}
