"""Agent1 行业情报 API。"""

from __future__ import annotations

from fastapi import APIRouter, Body, File, Form, UploadFile

from app.services.v2.intel_service import IntelService

router = APIRouter(prefix="/v2/intel", tags=["行业情报"])
intel_svc = IntelService()


@router.get("/tasks")
def get_intel_tasks():
    return intel_svc.list_tasks()


@router.put("/tasks")
def save_intel_tasks(body: dict = Body(...)):
    return intel_svc.save_tasks_config(body)


@router.get("/reports")
def list_intel_reports(limit: int = 50):
    return {"reports": intel_svc.list_reports(limit=limit), "count": len(intel_svc.list_reports(limit=limit))}


@router.post("/reports")
def create_intel_report(body: dict = Body(...)):
    return intel_svc.save_report(body)


@router.post("/reports/upload")
async def upload_intel_report(
    title: str = Body(...),
    content: str = Body(...),
    destinations: str = Body(default=""),
    summary: str = Body(default=""),
):
    return intel_svc.upload_text_report(title, content, summary=summary or None, destinations=destinations)


@router.post("/reports/upload-url")
async def upload_intel_from_url(
    url: str = Body(..., embed=True),
    title: str = Body(default=""),
    destinations: str = Body(default=""),
):
    """抓取公众号/网页链接正文并入库。"""
    try:
        return intel_svc.upload_from_url(url.strip(), title=title or None, destinations=destinations)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/reports/upload-file")
async def upload_intel_file(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    destinations: str = Form(default=""),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="ignore")
    name = title or file.filename or "上传报告"
    return intel_svc.upload_text_report(name, text, destinations=destinations, report_type="file_upload")


@router.post("/tasks/run")
def run_intel_tasks():
    """立即执行已启用的采集任务（占位采集，写入情报库）。"""
    return intel_svc.run_collection_tasks()


@router.post("/generate-suggestions")
def generate_ai_suggestions_from_intel(body: dict = Body(default={})):
    """调用 LLM 汇总情报 → 预览或写入 AI 建议待审队列。"""
    return intel_svc.generate_suggestions_with_llm(
        intel_limit=int(body.get("intel_limit") or 8),
        year=body.get("year") or 2027,
        extra_instruction=body.get("instruction") or "",
        intel_id=body.get("intel_id"),
        preview_only=bool(body.get("preview_only")),
    )


@router.post("/submit-suggestions")
def submit_ai_suggestions(body: dict = Body(...)):
    """将预览的 AI 创意活动送入初版评审池。"""
    return intel_svc.submit_suggestions(
        body.get("suggestions") or [],
        intel_id=body.get("intel_id"),
    )
