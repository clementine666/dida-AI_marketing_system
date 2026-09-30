"""系统管理：模块总览、运行日志、占位配置。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Query

from app.services.module_registry import get_module_map, get_modules
from app.services.prompt_store import get_prompt, list_prompts, save_prompt
from app.services.system_log import list_logs, log

router = APIRouter(prefix="/v2/admin", tags=["系统管理"])


@router.get("/modules")
def admin_modules():
    return get_module_map()


@router.get("/modules/flat")
def admin_modules_flat():
    return {"modules": get_modules()}


@router.get("/prompts")
def admin_list_prompts():
    return {"prompts": list_prompts()}


@router.get("/prompts/{key}")
def admin_get_prompt(key: str):
    p = get_prompt(key)
    if not p:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "prompt": p}


@router.put("/prompts/{key}")
def admin_save_prompt(key: str, body: dict = Body(...)):
    try:
        saved = save_prompt(
            key,
            body.get("content") or "",
            operator=body.get("operator") or "admin",
            notes=body.get("notes"),
        )
        log(
            f"更新占位配置: {saved.get('title') or key}",
            module="system_admin",
            action="prompt_save",
            operator=body.get("operator") or "admin",
            detail={"key": key, "content_length": len(saved.get("content") or "")},
        )
        return {"ok": True, "prompt": saved}
    except FileNotFoundError:
        return {"ok": False, "error": "not_found"}


@router.get("/logs")
def admin_logs(
    limit: int = Query(100, ge=1, le=500),
    module: str | None = None,
    level: str | None = None,
):
    return {"logs": list_logs(limit=limit, module=module, level=level)}


@router.post("/logs/test")
def admin_log_test(body: dict = Body(default={})):
    msg = body.get("message") or "系统管理 · 日志通路测试"
    lid = log(msg, module="system_admin", action="test", operator=body.get("operator") or "admin")
    return {"ok": True, "log_id": lid, "message": msg}
