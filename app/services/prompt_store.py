"""占位提示词 / 业务配置存储（config/prompts/*.yaml）。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from app.config import ROOT_DIR

PROMPTS_DIR = ROOT_DIR / "config" / "prompts"


def _path(key: str) -> Path:
    return PROMPTS_DIR / f"{key}.yaml"


def list_prompts() -> list[dict]:
    if not PROMPTS_DIR.exists():
        return []
    items = []
    for p in sorted(PROMPTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        data.setdefault("key", p.stem)
        data["content_length"] = len((data.get("content") or "").strip())
        items.append(data)
    return items


def get_prompt(key: str) -> dict | None:
    path = _path(key)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("key", key)
    return data


def prompt_status(key: str) -> str:
    p = get_prompt(key)
    if not p:
        return "missing"
    if (p.get("content") or "").strip():
        return "ready"
    return p.get("status") or "placeholder"


def save_prompt(key: str, content: str, operator: str = "system", notes: str | None = None) -> dict:
    path = _path(key)
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {key}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["content"] = content
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    data["updated_by"] = operator
    if notes is not None:
        data["notes"] = notes
    if content.strip():
        data["status"] = "ready"
    else:
        data["status"] = "placeholder"
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return data
