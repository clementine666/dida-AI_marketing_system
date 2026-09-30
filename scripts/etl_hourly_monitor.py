"""每小时活动监控 ETL。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db import get_engine
from app.services.v2.agent3_monitor import MonitorService


def run_hourly_monitor():
    engine = get_engine()
    monitor = MonitorService(engine)

    launched = monitor.run_scheduled_launch_check()
    if launched:
        print(f"  Launched {len(launched)} campaigns")

    with engine.connect() as conn:
        campaigns = conn.execute(
            text("SELECT campaign_id FROM dim_campaign WHERE lifecycle_status = 'monitoring'")
        ).fetchall()

    print(f"[Hourly Monitor] {datetime.now().isoformat()} - {len(campaigns)} monitoring campaigns")
    all_alerts = []
    for (cid,) in campaigns:
        alerts = monitor.legacy.run_monitoring(cid)
        if alerts:
            print(f"  {cid}: {len(alerts)} alerts")
            all_alerts.extend(alerts)

    return {"campaigns_monitored": len(campaigns), "alerts": all_alerts}


if __name__ == "__main__":
    run_hourly_monitor()
