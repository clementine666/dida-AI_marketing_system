"""行业情报定时收集：读任务配置 → 采集占位 → 可选 LLM 生成建议。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.v2.intel_service import IntelService


def main(run_llm: bool = False) -> None:
    from scripts.migrate_v2 import migrate_v2

    migrate_v2()
    svc = IntelService()
    result = svc.run_collection_tasks()
    print(f"Collection: saved {result.get('saved', 0)} reports")

    if run_llm and svc.llm.is_configured():
        gen = svc.generate_suggestions_with_llm()
        print(f"LLM suggestions: {gen}")
    elif run_llm:
        print("LLM not configured, skip generate-suggestions")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true", help="采集后调用 LLM 生成 AI 建议")
    args = p.parse_args()
    main(run_llm=args.llm)
