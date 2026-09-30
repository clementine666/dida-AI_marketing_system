"""列出飞书营销日历 Base 下的数据表，用于获取 FEISHU_MARKETING_CALENDAR_TABLE_ID。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrations.feishu_marketing_calendar import FeishuMarketingCalendarClient


def main() -> None:
    client = FeishuMarketingCalendarClient()
    if client.use_mock:
        print("当前为 Mock 模式。请设置环境变量：")
        print("  FEISHU_APP_ID")
        print("  FEISHU_APP_SECRET")
        print("  FEISHU_MARKETING_CALENDAR_TABLE_ID  (运行本脚本后可获得)")
        print(f"\nBase app_token: {client.app_token}")
        print("\nMock 样本记录：")
        records = client.list_calendar_records()
        print(json.dumps(client.group_by_month(records), ensure_ascii=False, indent=2))
        return

    tables = client.list_tables()
    print(f"Base: {client.app_token}\n")
    for t in tables:
        print(f"  table_id: {t.get('table_id')}")
        print(f"  name:     {t.get('name')}")
        print()


if __name__ == "__main__":
    main()
