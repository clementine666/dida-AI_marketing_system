"""从 Excel 样本（部分数据明细导出.xlsx）导入三张数仓表到 data/raw/ CSV。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_EXCEL = Path(r"C:\Users\jw107\Downloads\部分数据明细导出.xlsx")
OUTPUT = {
    "ods_amplitude_events": ROOT / "data" / "raw" / "ods_amplitude_events.csv",
    "ods_amplitude_users": ROOT / "data" / "raw" / "ods_amplitude_users.csv",
    "dwd_hotel_shopping_funnel_detai": ROOT / "data" / "raw" / "dwd_hotel_shopping_funnel_detai.csv",
}


def import_excel(excel_path: Path = DEFAULT_EXCEL) -> dict[str, int]:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel not found: {excel_path}")

    x = pd.ExcelFile(excel_path)
    counts = {}
    for sheet, out in OUTPUT.items():
        if sheet not in x.sheet_names:
            print(f"Skip missing sheet: {sheet}")
            continue
        df = pd.read_excel(x, sheet)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False, encoding="utf-8-sig")
        counts[sheet] = len(df)
        print(f"Exported {len(df)} rows -> {out}")

    return counts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import warehouse sample Excel to CSV")
    parser.add_argument("--excel", default=str(DEFAULT_EXCEL), help="Path to 部分数据明细导出.xlsx")
    args = parser.parse_args()
    result = import_excel(Path(args.excel))
    print("\nDone:", result)
    print("\nNext: python scripts/import_data.py")
