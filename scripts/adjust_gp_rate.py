"""按道旅 Shopping 预订 GP 率 1%–2% 重写 2027 日历文档中的预期 GP。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.v2.activity_doc_parser import rewrite_gp_in_markdown
from app.services.v2.intel_service import IntelService

FOLDERS = [
    ROOT / "data" / "intel_uploads" / "2027营销活动日历",
    Path(r"c:\Users\jw107\WorkBuddy\2026-08-26-10-17-50\2027营销活动日历"),
]


def main() -> None:
    rewritten = 0
    for folder in FOLDERS:
        if not folder.exists():
            print("skip missing", folder)
            continue
        for path in sorted(folder.glob("2027年*.md")):
            old = path.read_text(encoding="utf-8")
            new = rewrite_gp_in_markdown(old)
            if new != old:
                path.write_text(new, encoding="utf-8")
                rewritten += 1
                print("updated", path)
        overview = folder / "00-2027全年营销活动日历总览.md"
        if overview.exists():
            text = overview.read_text(encoding="utf-8")
            text2 = text.replace(
                "| 预期GP合计 | 约630-760万 | 综合ROI约15% |",
                "| 预期GP合计 | 约42-100万 | 预订GP率约1%-2%（道旅 Shopping 活动区间综合） |",
            ).replace(
                "2026年樱花季ROI 15%，TTV超目标107%",
                "2026年樱花季验证有效，TTV超目标107%；预订GP按1%-2%估算",
            )
            if text2 != text:
                overview.write_text(text2, encoding="utf-8")
                print("updated", overview)
    cal = ROOT / "data" / "intel_uploads" / "2027营销活动日历"
    result = IntelService().import_markdown_calendar(cal, reject_thin_pending=False)
    print("rewritten_files", rewritten)
    print("import", result)


if __name__ == "__main__":
    main()
