"""每日 T-1 ETL 同步脚本。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from scripts.import_data import run_full_import


def run_daily_etl():
    settings = get_settings()
    sync_date = (datetime.now() - timedelta(days=settings.t_minus_days)).date()
    print(f"[Daily ETL] Syncing T-{settings.t_minus_days} data for {sync_date}")
    stats = run_full_import()
    print(f"[Daily ETL] Completed: {stats}")
    return stats


if __name__ == "__main__":
    run_daily_etl()
