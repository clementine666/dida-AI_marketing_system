"""开发模式：启动 API，修改代码后自动重启。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn

from app.config import get_settings
from scripts.migrate_v2 import migrate_v2


def main() -> None:
    migrate_v2()
    settings = get_settings()
    reload_dirs = [str(ROOT / "app"), str(ROOT / "ui"), str(ROOT / "config")]
    print("=" * 56)
    print("  道旅营销协作系统 · 开发模式")
    print(f"  浏览器打开: http://localhost:{settings.api_port}")
    print("  修改 app / ui / config 下文件后会自动重启")
    print("  关闭本窗口 = 停止服务")
    print("=" * 56)
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        reload_dirs=reload_dirs,
    )


if __name__ == "__main__":
    main()
