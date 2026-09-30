"""使用者问题反馈 API。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Query

from app.services import feedback_service as fb

router = APIRouter(prefix="/v2/feedback", tags=["问题反馈"])


@router.post("")
def submit_feedback(body: dict = Body(...)):
    """
    使用者提交问题反馈。
    body: reporter, title, description, expected_behavior, module, page_view, tab_name, severity, context
    """
    title = (body.get("title") or "").strip()
    reporter = (body.get("reporter") or "").strip()
    if not title:
        return {"ok": False, "error": "请填写问题标题"}
    if not reporter:
        return {"ok": False, "error": "请填写反馈人姓名"}
    item = fb.create_feedback(
        reporter=reporter,
        title=title,
        description=body.get("description") or "",
        expected_behavior=body.get("expected_behavior") or "",
        module=body.get("module"),
        page_view=body.get("page_view"),
        tab_name=body.get("tab_name"),
        severity=body.get("severity") or "normal",
        context=body.get("context"),
    )
    return {"ok": True, "feedback": item}


@router.get("")
def list_feedback_api(status: str | None = None, limit: int = Query(50, ge=1, le=200)):
    return {"ok": True, "items": fb.list_feedback(status=status, limit=limit), "summary": fb.summary_counts()}


@router.get("/summary")
def feedback_summary():
    return {"ok": True, **fb.summary_counts()}


@router.get("/{feedback_id}")
def get_feedback_detail(feedback_id: int):
    item = fb.get_feedback_detail(feedback_id)
    if not item:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "feedback": item}


@router.patch("/{feedback_id}")
def update_feedback(feedback_id: int, body: dict = Body(...)):
    """后台处理：更新状态、根因、修复说明。"""
    item = fb.update_feedback(
        feedback_id,
        status=body.get("status"),
        admin_notes=body.get("admin_notes"),
        root_cause=body.get("root_cause"),
        resolution=body.get("resolution"),
        related_log_hint=body.get("related_log_hint"),
        operator=body.get("operator") or "admin",
    )
    if not item:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "feedback": item}
