"""飞书营销日历 — 本地文件导入（XLSX / CSV / JSON）。"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from app.integrations.feishu_marketing_calendar import MARKETING_CALENDAR_FIELD_MAP


# 导出 Excel 时列名可能是英文映射后的，也支持
COLUMN_ALIASES: dict[str, list[str]] = {
    "月度推荐主题": ["月度推荐主题", "campaign_name", "活动名称", "主题"],
    "推广月份": ["推广月份", "promotion_month", "月份"],
    "推广时间": ["推广时间", "promotion_time", "时间"],
    "目的地归属": ["目的地归属", "destination_region", "区域归属"],
    "地区": ["地区", "regions", "target_dest", "目的地"],
    "shopping端一级Banner位": ["shopping端一级Banner位", "banner_slot", "Banner位"],
}

# 人工标准活动初版日历（飞书 27年营销日历初版 A–M 列）
DRAFT_CALENDAR_ALIASES: dict[str, list[str]] = {
    "session_month": ["活动场次", "场次", "上线月份", "活动月份"],
    "main_theme": ["月度主活动主题", "主活动主题", "月度主主题", "主主题"],
    "sub_theme": ["副活动主题", "副主题", "活动主题"],
    "destinations": ["覆盖目的地块/城市", "覆盖目的地", "目的地", "覆盖目的地块", "地区"],
    "checkout_window": ["对应离店/预订窗口期", "离店窗口", "离店/预订窗口", "入住离店窗口"],
    "p75_days": ["提前预定天数 P75", "提前预订天数 P75", "P75", "提前预定天数"],
    "evidence": ["选目的地的数据依据", "数据依据", "选目的地依据"],
    "resource_connect": ["资源对接时间", "资源对接"],
    "resource_delivery": ["资源交付(T-30前)", "资源交付", "T-30"],
    "material_prep": ["策展物料准备(T-14前)", "物料准备", "T-14"],
    "go_live_date": ["活动上线时间", "上线时间", "活动上线"],
    "off_shelf_date": ["活动离档时间", "离档时间"],
    "review_note": ["活动复盘", "复盘"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    cols = [str(c).strip() for c in df.columns]
    df.columns = cols
    for target, aliases in COLUMN_ALIASES.items():
        for col in cols:
            if col in aliases and col != target:
                rename[col] = target
    return df.rename(columns=rename)


def parse_calendar_file(content: bytes, filename: str) -> list[dict[str, Any]]:
    """解析上传的营销日历文件为 mock JSON 记录列表。"""
    name = (filename or "").lower()

    if name.endswith(".json"):
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict) and "records" in data:
            return data["records"]
        if isinstance(data, list):
            return data
        raise ValueError("JSON 格式应为数组或 {records: [...]}")

    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    elif name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        raise ValueError("仅支持 .xlsx / .xls / .csv / .json")

    df = _normalize_columns(df)
    df = df.dropna(how="all")
    records: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        rec: dict[str, Any] = {"_record_id": f"upload_row_{i + 2}"}
        has_value = False
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                continue
            sval = str(val).strip()
            if sval:
                rec[str(col)] = sval
                has_value = True
        if has_value:
            records.append(rec)

    if not records:
        raise ValueError("文件中没有有效数据行")

    # 校验至少有一列核心字段
    core = set(MARKETING_CALENDAR_FIELD_MAP.keys()) | set(COLUMN_ALIASES.keys())
    first_keys = set(records[0].keys()) - {"_record_id"}
    if not first_keys.intersection(core):
        raise ValueError(
            "未识别到营销日历列名，请保留：月度推荐主题、推广月份、推广时间、目的地归属、地区 等列"
        )
    return records


def _normalize_draft_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 Excel 列名映射为 draft_row 标准字段。"""
    cols = [str(c).strip() for c in df.columns]
    df = df.copy()
    df.columns = cols
    rename: dict[str, str] = {}
    for target, aliases in DRAFT_CALENDAR_ALIASES.items():
        for col in cols:
            if col in aliases:
                rename[col] = target
                break
    return df.rename(columns=rename)


def _cell_str(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s else None


def parse_manual_calendar_draft(content: bytes, filename: str) -> list[dict[str, Any]]:
    """
    解析人工做好的标准活动初版日历（A–M 列），供送入初版评审池。
    至少需要：副活动主题 或 覆盖目的地 之一。
    """
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    elif name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content))
    else:
        raise ValueError("仅支持 .xlsx / .xls / .csv")

    df = _normalize_draft_columns(df)
    df = df.dropna(how="all")
    if df.empty:
        raise ValueError("文件中没有有效数据行")

    has_core = any(c in df.columns for c in ("sub_theme", "destinations", "main_theme"))
    if not has_core:
        raise ValueError(
            "未识别到初版日历列名。请保留：活动场次、月度主活动主题、副活动主题、"
            "覆盖目的地块/城市、对应离店/预订窗口期、选目的地的数据依据 等列"
        )

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        row: dict[str, Any] = {}
        for field in DRAFT_CALENDAR_ALIASES:
            if field not in df.columns:
                continue
            val = _cell_str(r[field])
            if val is not None:
                if field == "p75_days":
                    try:
                        row[field] = float(val.replace("天", ""))
                    except ValueError:
                        row[field] = val
                else:
                    row[field] = val
        if row.get("sub_theme") or row.get("destinations") or row.get("main_theme"):
            row["plan_source"] = "manual_upload"
            rows.append(row)

    if not rows:
        raise ValueError("未解析到有效活动行（需至少含副活动主题或目的地）")
    return rows
