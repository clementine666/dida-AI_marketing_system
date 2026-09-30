from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.routers import agent1, agent2, agent3, agent4, feedback, intel, system_admin, system_config, v2_workflow

UI_DIR = ROOT / "ui"
DASHBOARD_DIR = UI_DIR / "dashboard"

_scheduler = BackgroundScheduler()


def _run_morning_reminders():
    from app.services.v2.task_reminder import run_due_reminders

    run_due_reminders()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.services.v2.task_reminder import ensure_schema
    from app.services.feedback_service import ensure_schema as ensure_feedback_schema
    from app.services.system_log import ensure_schema as ensure_log_schema

    ensure_schema()
    ensure_log_schema()
    ensure_feedback_schema()
    from app.services.system_log import log

    log("API 服务启动", module="system", action="startup", level="info")
    _scheduler.add_job(
        _run_morning_reminders,
        CronTrigger(hour=9, minute=0),
        id="feishu_task_reminders",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    yield
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="多Agent营销协作系统 API",
    description="道旅科技 portal.dida.com 5-Agent 营销协作（v2）",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent1.router, prefix="/api")
app.include_router(agent2.router, prefix="/api")
app.include_router(agent3.router, prefix="/api")
app.include_router(agent4.router, prefix="/api")
app.include_router(v2_workflow.router, prefix="/api")
app.include_router(intel.router, prefix="/api")
app.include_router(system_config.router, prefix="/api")
app.include_router(system_admin.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")


def _html_no_cache(path: Path) -> FileResponse:
    """开发/演示时避免浏览器长期缓存旧版 index.html。"""
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


if UI_DIR.exists():
    app.mount("/ui", NoCacheStaticFiles(directory=str(UI_DIR)), name="ui")


@app.get("/")
def root():
    index = DASHBOARD_DIR / "index.html"
    if index.exists():
        return _html_no_cache(index)
    return {
        "service": "Multi-Agent Marketing System",
        "docs": "/docs",
        "dashboard": "/ui/dashboard/index.html",
    }


@app.get("/app")
def app_dashboard():
    return _html_no_cache(DASHBOARD_DIR / "index.html")


@app.get("/health")
def health():
    from app.db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ).fetchall()
    return {"status": "ok", "tables": [t[0] for t in tables]}


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="多Agent营销协作系统 API")
    parser.add_argument("--reload", action="store_true", help="开发模式：改代码自动重启")
    args = parser.parse_args()

    settings = get_settings()
    reload_dirs = [str(ROOT / "app"), str(ROOT / "ui"), str(ROOT / "config")] if args.reload else None
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=args.reload,
        reload_dirs=reload_dirs,
    )


if __name__ == "__main__":
    main()
