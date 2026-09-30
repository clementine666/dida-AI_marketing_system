"""初始化数据库并导入数据。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import get_engine, init_database
from scripts.import_data import run_full_import
from scripts.industry_intel_collector import collect_intel, save_reports
from scripts.migrate_v2 import migrate_v2


def main():
    engine = get_engine()
    print("Initializing database schema...")
    init_database(engine)
    print("Running v2 migration...")
    migrate_v2()
    print("Running full data import...")
    stats = run_full_import()
    print("Collecting industry intel...")
    intel_count = save_reports(collect_intel())
    print("Done:", stats, "intel_reports:", intel_count)


if __name__ == "__main__":
    main()
