"""飞书「2026营销日历」— 对内：旅游目的地营销日历 集成。

支持三种数据源（配置 calendar_type）：
- bitable：飞书多维表格
- sheet：飞书电子表格
- local：Excel 本地文件（拖拽上传）
- bitable：飞书多维表格
- sheet：飞书电子表格

Base: https://didatravel.feishu.cn/base/GpYkbnH9ga8nMAs0GUQcCXoInXe
View: 对内：旅游目的地营销日历（按推广月份分组）
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx

from app.config import ROOT_DIR

# 飞书字段 → 系统字段（对内营销日历）
MARKETING_CALENDAR_FIELD_MAP = {
    "月度推荐主题": "campaign_name",
    "推广月份": "promotion_month",
    "shopping端一级Banner位": "banner_slot",
    "shopping端一级Banner…": "banner_slot",
    "推广时间": "promotion_time",
    "目的地归属": "destination_region",
    "地区": "regions",
}

REGION_COLOR = {
    "欧洲EU": "europe",
    "北美": "north_america",
    "亚洲": "asia",
    "东南亚": "southeast_asia",
    "全目的地": "global",
}


def _unwrap_feishu_value(val: Any) -> Any:
    """飞书 API 返回的字段可能是 [{text: ...}] 或纯字符串。"""
    if val is None:
        return None
    if isinstance(val, str | int | float):
        return val
    if isinstance(val, list):
        if not val:
            return None
        first = val[0]
        if isinstance(first, dict):
            if "text" in first:
                return first["text"]
            if "name" in first:
                return first["name"]
        return ", ".join(str(x) for x in val)
    if isinstance(val, dict):
        return val.get("text") or val.get("name") or str(val)
    return str(val)


def _parse_month(month_val: Any) -> int | None:
    s = str(_unwrap_feishu_value(month_val) or "")
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _infer_start_date(promotion_time: str | None, promotion_month: int | None) -> str | None:
    """从「3月16日」+ 月份推断 start_date。"""
    if not promotion_time:
        return None
    s = str(promotion_time)
    day_m = re.search(r"(\d+)\s*日", s)
    if day_m and promotion_month:
        year = date.today().year
        try:
            return date(year, promotion_month, int(day_m.group(1))).isoformat()
        except ValueError:
            pass
    return None


class FeishuMarketingCalendarClient:
    """
    Agent1 营销日历数据源。
    与「活动信息汇总」复盘表分离：本表负责规划输入，复盘表负责 Agent4 回写。
    """

    DEFAULT_APP_TOKEN = "GpYkbnH9ga8nMAs0GUQcCXoInXe"

    def __init__(self):
        from app.services.config_store import load_integrations
        integ = load_integrations().get("feishu", {})
        self.app_id = os.getenv("FEISHU_APP_ID", "") or integ.get("app_id", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "") or integ.get("app_secret", "")
        self.calendar_type = (integ.get("calendar_type") or "bitable").strip().lower()
        self.app_token = os.getenv("FEISHU_MARKETING_CALENDAR_APP_TOKEN", "") or integ.get(
            "app_token", self.DEFAULT_APP_TOKEN
        )
        self.table_id = os.getenv("FEISHU_MARKETING_CALENDAR_TABLE_ID", "") or integ.get("marketing_calendar_table_id", "")
        self.view_id = os.getenv("FEISHU_MARKETING_CALENDAR_VIEW_ID", "") or integ.get("marketing_calendar_view_id", "")
        self.spreadsheet_token = os.getenv("FEISHU_SPREADSHEET_TOKEN", "") or integ.get("spreadsheet_token", "")
        self.sheet_id = os.getenv("FEISHU_SHEET_ID", "") or integ.get("sheet_id", "")
        self.sheet_range = os.getenv("FEISHU_SHEET_RANGE", "") or integ.get("sheet_range", "")
        self.mock_path = ROOT_DIR / "data" / "feishu_marketing_calendar_mock.json"
        self.use_mock = not self._is_live_configured()

    def _is_live_configured(self) -> bool:
        if self.calendar_type == "local":
            return False
        if not (self.app_id and self.app_secret):
            return False
        if self.calendar_type == "sheet":
            return bool(self.spreadsheet_token and (self.sheet_id or self.sheet_range))
        return bool(self.table_id)

    def _missing_config_fields(self) -> list[str]:
        if self.calendar_type == "local":
            from app.services.config_store import local_calendar_meta

            return [] if local_calendar_meta() else ["请上传 Excel 文件"]
        missing: list[str] = []
        if not self.app_id:
            missing.append("飞书应用 ID")
        if not self.app_secret:
            missing.append("飞书应用密钥")
        if self.calendar_type == "sheet":
            if not self.spreadsheet_token:
                missing.append("电子表格 Token")
            if not self.sheet_id and not self.sheet_range:
                missing.append("工作表 ID 或读取范围")
        elif self.calendar_type != "local":
            if not self.table_id:
                missing.append("数据表 Table ID")
        return missing

    def calendar_type_label(self) -> str:
        if self.calendar_type == "local":
            return "Excel 本地文件"
        return "飞书电子表格" if self.calendar_type == "sheet" else "飞书多维表格"

    def test_connection(self) -> dict:
        """测试营销日历是否可读。"""
        if self.calendar_type == "local":
            from app.services.config_store import local_calendar_meta

            meta = local_calendar_meta()
            records = self.list_calendar_records()
            sample = [
                {
                    "活动名称": r.get("campaign_name"),
                    "推广月份": r.get("promotion_month"),
                    "地区": r.get("regions") or r.get("target_dest"),
                }
                for r in records[:3]
            ]
            ok = bool(meta and records)
            return {
                "ok": ok,
                "title": "营销日历",
                "mode": f"Excel 本地（{len(records)} 条）" if ok else "Excel 本地（待上传）",
                "calendar_type": self.calendar_type,
                "calendar_type_label": self.calendar_type_label(),
                "record_count": len(records),
                "sample_records": sample if ok else [],
                "message": (
                    f"已读取本地 Excel {len(records)} 条"
                    if ok
                    else "请先拖拽上传飞书导出的 Excel 文件"
                ),
                "checks": [
                    {"项": "数据来源", "通过": True, "说明": "Excel 本地文件"},
                    {"项": "已上传文件", "通过": bool(meta), "说明": meta.get("filename", "—") if meta else "未上传"},
                    {"项": "读取记录", "通过": len(records) > 0, "说明": f"{len(records)} 条"},
                ],
            }
        missing = self._missing_config_fields()
        if missing and not self.use_mock:
            return {
                "ok": False,
                "title": "飞书营销日历",
                "mode": "未配置",
                "calendar_type": self.calendar_type,
                "calendar_type_label": self.calendar_type_label(),
                "missing_fields": missing,
                "message": f"请先填写：{'、'.join(missing)}",
                "checks": [{"项": f, "通过": False, "说明": "必填"} for f in missing],
            }
        try:
            if not self.use_mock:
                self._get_tenant_token()
            records = self.list_calendar_records()
            sample = [
                {
                    "活动名称": r.get("campaign_name"),
                    "推广月份": r.get("promotion_month"),
                    "地区": r.get("regions") or r.get("target_dest"),
                }
                for r in records[:3]
            ]
            mode = "演示数据" if self.use_mock else f"{self.calendar_type_label()}已连接"
            return {
                "ok": True,
                "title": "飞书营销日历",
                "mode": mode,
                "calendar_type": self.calendar_type,
                "calendar_type_label": self.calendar_type_label(),
                "record_count": len(records),
                "sample_records": sample,
                "message": f"成功读取 {len(records)} 条营销日历（{self.calendar_type_label()}）",
                "checks": [
                    {"项": "表格类型", "通过": True, "说明": self.calendar_type_label()},
                    {"项": "读取记录", "通过": len(records) > 0, "说明": f"{len(records)} 条"},
                ],
            }
        except Exception as e:
            return {
                "ok": False,
                "title": "飞书营销日历",
                "mode": "连接失败",
                "calendar_type": self.calendar_type,
                "calendar_type_label": self.calendar_type_label(),
                "error": str(e),
                "message": f"{self.calendar_type_label()}读取失败，请检查凭证、权限与 ID",
                "checks": [{"项": "读表", "通过": False, "说明": str(e)}],
            }

    def _get_tenant_token(self) -> str:
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(data.get("msg", "Feishu auth failed"))
        return data["tenant_access_token"]

    def list_tables(self) -> list[dict]:
        """列出 Base 下所有数据表（用于配置 table_id）。"""
        token = self._get_tenant_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}/tables"
        resp = httpx.get(
            url, headers={"Authorization": f"Bearer {token}"}, params={"page_size": 100}, timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])

    def _normalize_record(self, fields: dict) -> dict:
        raw: dict[str, Any] = {"feishu_record_id": fields.get("_record_id"), "source": "marketing_calendar"}
        for cn, en in MARKETING_CALENDAR_FIELD_MAP.items():
            if cn in fields and fields[cn] is not None:
                raw[en] = _unwrap_feishu_value(fields[cn])

        month = _parse_month(raw.get("promotion_month"))
        regions = raw.get("regions") or ""
        raw["promotion_month_num"] = month
        raw["target_dest"] = regions.split("、")[0].split(",")[0].strip() if regions else None
        raw["destination_region_key"] = REGION_COLOR.get(str(raw.get("destination_region", "")), "other")
        raw["start_date"] = _infer_start_date(raw.get("promotion_time"), month)
        raw["plan_summary"] = (
            f"{raw.get('campaign_name', '')} — {regions}（{raw.get('destination_region', '')}）"
            f" 推广时间：{raw.get('promotion_time', '待定')}"
        )
        raw["campaign_type"] = "Banner" if raw.get("banner_slot") else "目的地专题"
        raw["activity_id"] = self._make_activity_id(raw)
        return raw

    def _make_activity_id(self, rec: dict) -> str:
        name = rec.get("campaign_name") or "ACT"
        month = rec.get("promotion_month_num") or 0
        slug = re.sub(r"[^A-Za-z0-9]", "", str(name))[:12]
        if not slug:
            slug = hashlib.md5(str(name).encode()).hexdigest()[:8].upper()
        return f"CAL_{month:02d}_{slug}"

    def _default_mock_records(self) -> list[dict]:
        """基于飞书截图「对内：旅游目的地营销日历」样本。"""
        records = [
            {
                "_record_id": "rec_cal_0301",
                "月度推荐主题": "德法意瑞春季促销",
                "推广月份": "3月",
                "推广时间": "3月16日",
                "目的地归属": "欧洲EU",
                "地区": "德国、法国、意大利、瑞士",
            },
            {
                "_record_id": "rec_cal_0302",
                "月度推荐主题": "西葡春季促销",
                "推广月份": "3月",
                "推广时间": "3月16日",
                "目的地归属": "欧洲EU",
                "地区": "西班牙、葡萄牙",
            },
            {
                "_record_id": "rec_cal_0303",
                "月度推荐主题": "美国促销",
                "推广月份": "3月",
                "推广时间": "3月17日",
                "目的地归属": "北美",
                "地区": "美国",
            },
            {
                "_record_id": "rec_cal_0304",
                "月度推荐主题": "日本樱花季",
                "推广月份": "3月",
                "推广时间": "3月24日",
                "目的地归属": "亚洲",
                "地区": "日本",
            },
            {
                "_record_id": "rec_cal_0305",
                "月度推荐主题": "展会季",
                "推广月份": "3月",
                "推广时间": "3月17日",
                "目的地归属": "全目的地",
                "地区": "重点展会城市",
            },
            {
                "_record_id": "rec_cal_0401",
                "月度推荐主题": "东南亚专题",
                "推广月份": "4月",
                "推广时间": "4月8日",
                "目的地归属": "东南亚",
                "地区": "新加坡、马来西亚、泰国",
            },
            {
                "_record_id": "rec_cal_0402",
                "月度推荐主题": "五一促销",
                "推广月份": "4月",
                "推广时间": "4月14日",
                "目的地归属": "全目的地",
                "地区": "全目的地",
            },
            {
                "_record_id": "rec_cal_0501",
                "月度推荐主题": "新加坡F1赛事酒店预订",
                "推广月份": "8月",
                "推广时间": "8月1日",
                "目的地归属": "东南亚",
                "地区": "新加坡",
            },
        ]
        self.mock_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return records

    def _load_mock_records(self) -> list[dict]:
        if self.mock_path.exists():
            return json.loads(self.mock_path.read_text(encoding="utf-8"))
        return self._default_mock_records()

    def _list_bitable_records(self, token: str) -> list[dict]:
        url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}"
            f"/tables/{self.table_id}/records"
        )
        params: dict[str, Any] = {"page_size": 500}
        if self.view_id:
            params["view_id"] = self.view_id

        records: list[dict] = []
        page_token = None
        while True:
            if page_token:
                params["page_token"] = page_token
            resp = httpx.get(
                url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=60
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") not in (0, None):
                raise RuntimeError(body.get("msg", "Bitable API error"))
            data = body.get("data", {})
            for item in data.get("items", []):
                fields = item.get("fields", {})
                fields["_record_id"] = item.get("record_id")
                records.append(self._normalize_record(fields))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return records

    def _sheet_value_range(self) -> str:
        if self.sheet_range:
            return self.sheet_range.strip()
        if self.sheet_id:
            return f"{self.sheet_id}!A1:Z500"
        raise RuntimeError("请填写工作表 ID 或读取范围（如 Sheet1!A1:Z200）")

    def _list_sheet_records(self, token: str) -> list[dict]:
        """读取飞书电子表格：首行作为表头，映射到营销日历字段。"""
        range_str = self._sheet_value_range()
        encoded_range = quote(range_str, safe="!")
        url = (
            f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/"
            f"{self.spreadsheet_token}/values/{encoded_range}"
        )
        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg", "Sheet API error"))

        values = body.get("data", {}).get("valueRange", {}).get("values") or []
        if not values:
            return []

        headers = [str(h).strip() for h in values[0]]
        records: list[dict] = []
        for i, row in enumerate(values[1:], start=2):
            if not any(str(c).strip() for c in row if c is not None):
                continue
            fields: dict[str, Any] = {}
            for j, header in enumerate(headers):
                if not header:
                    continue
                val = row[j] if j < len(row) else None
                if val is not None and str(val).strip():
                    fields[header] = val
            if not fields:
                continue
            fields["_record_id"] = f"sheet_row_{i}"
            records.append(self._normalize_record(fields))
        return records

    def list_calendar_records(self, internal_only: bool = True) -> list[dict]:
        """
        读取营销日历记录。
        internal_only: 仅「对内」视图数据（Bitable 可通过 view_id 过滤）
        """
        if self.use_mock:
            return [self._normalize_record(r) for r in self._load_mock_records()]

        token = self._get_tenant_token()
        if self.calendar_type == "sheet":
            return self._list_sheet_records(token)
        return self._list_bitable_records(token)

    def group_by_month(self, records: list[dict] | None = None) -> dict[str, list[dict]]:
        records = records or self.list_calendar_records()
        grouped: dict[str, list[dict]] = {}
        for r in records:
            key = r.get("promotion_month") or "未分类"
            grouped.setdefault(str(key), []).append(r)
        return dict(sorted(grouped.items(), key=lambda x: _parse_month(x[0]) or 99))
