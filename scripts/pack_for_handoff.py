# -*- coding: utf-8 -*-
"""打包项目供同事继续开发（排除缓存与虚拟环境）"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT.parent
STAMP = datetime.now().strftime("%Y%m%d")
OUT_ZIP = OUT_DIR / f"multi-agent-marketing-system-handoff-{STAMP}.zip"

SKIP_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".git",
}
SKIP_SUFFIX = {".pyc", ".pyo", ".zip"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIRS:
        return True
    if path.suffix.lower() in SKIP_SUFFIX:
        return True
    if path.name.endswith(".zip") and path.parent == OUT_DIR:
        return True
    return False


def main() -> None:
    count = 0
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ROOT.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(ROOT)
            if should_skip(f):
                continue
            zf.write(f, rel.as_posix())
            count += 1
    print(f"Wrote {OUT_ZIP}")
    print(f"Files: {count}")
    print(f"Size: {OUT_ZIP.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
