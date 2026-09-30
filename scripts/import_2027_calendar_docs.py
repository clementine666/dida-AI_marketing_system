"""把 WorkBuddy 2027 月度决策卡导入 AI 创意池（完整评审字段）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.v2.intel_service import IntelService

DEFAULT_DIRS = [
    ROOT / "data" / "intel_uploads" / "2027营销活动日历",
    Path(r"c:\Users\jw107\WorkBuddy\2026-08-26-10-17-50\2027营销活动日历"),
]


def resolve_folder() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    for folder in DEFAULT_DIRS:
        if folder.exists() and any(folder.glob("2027年*.md")):
            return folder
    raise SystemExit("未找到 2027 月度活动 Markdown，请传入目录路径")


def main() -> None:
    folder = resolve_folder()
    result = IntelService().import_markdown_calendar(folder)
    print(result)


if __name__ == "__main__":
    main()
