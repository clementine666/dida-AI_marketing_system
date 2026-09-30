"""飞书多维表（活动信息汇总）集成。"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import httpx

from app.config import ROOT_DIR

FEISHU_FIELD_MAP = {
    "活动名称": "campaign_name",
    "activity_id": "activity_id",
    "负责人": "owner",
    "活动介绍/说明": "plan_summary",
    "活动规模（客户群体…）": "target_audience",
    "活动规模": "target_audience",
    "开始时间": "start_date",
    "结束时间": "end_date",
    "优惠券活动 id": "coupon_ids",
    "具体活动方案": "execution_steps",
    "活动清单": "activity_list",
    "活动目标": "target_metrics",
    "与目标相关的关键数据指标": "key_metrics_spec",
    "活动数据": "activity_data",
    "其他补充说明": "extra_notes",
    "复盘状态": "review_status",
    "活动总结报告": "review_report_url",
    "活动功能结论": "review_conclusion",
}


class FeishuBitableClient:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN", "ORgrby0BlamXTqsddAiclN77ncf")
        self.table_id = os.getenv("FEISHU_BITABLE_TABLE_ID", "")
        self.mock_path = ROOT_DIR / "data" / "feishu_calendar_mock.json"
        self.use_mock = not (self.app_id and self.app_secret and self.table_id)

    def _get_tenant_token(self) -> str:
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["tenant_access_token"]

    def _normalize_record(self, fields: dict) -> dict:
        out: dict[str, Any] = {"feishu_record_id": fields.get("_record_id")}
        for cn, en in FEISHU_FIELD_MAP.items():
            if cn in fields and fields[cn] is not None:
                out[en] = fields[cn]
        return out

    def _load_mock_records(self) -> list[dict]:
        if self.mock_path.exists():
            return json.loads(self.mock_path.read_text(encoding="utf-8"))
        return self._default_mock_records()

    def _default_mock_records(self) -> list[dict]:
        today = date.today()
        records = [
            {
                "_record_id": "rec_f1_2026",
                "活动名称": "新加坡F1赛事酒店预订",
                "activity_id": "F1_SG_2026",
                "负责人": "石军军",
                "活动介绍/说明": "F1新加坡大奖赛期间，针对有新加坡搜索行为的B端客户推广赛场周边酒店",
                "活动规模": "客群：海外线下+海外线上｜数量：约200",
                "开始时间": "2026-08-01",
                "结束时间": "2026-09-25",
                "活动目标": "主指标：订单数≥100；TTV≥50万",
                "与目标相关的关键数据指标": "1) Banner CTR≥5% 2) 转化率≥2%",
                "复盘状态": "待复盘",
            },
            {
                "_record_id": "rec_my_national_2026",
                "活动名称": "马来西亚独立日大促销",
                "activity_id": "ACT_MY_IND_2026",
                "负责人": "营销部",
                "活动介绍/说明": "马来西亚独立69周年促销",
                "活动规模": "客群：国内线下Shopping",
                "开始时间": str(date(today.year, today.month, 1)),
                "结束时间": str(date(today.year, min(today.month + 2, 12), 28)),
                "活动目标": "订单数≥80",
                "复盘状态": "待复盘",
            },
        ]
        self.mock_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return records

    def list_calendar_records(self) -> list[dict]:
        if self.use_mock:
            return [self._normalize_record(r) for r in self._load_mock_records()]
        token = self._get_tenant_token()
        url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}"
            f"/tables/{self.table_id}/records"
        )
        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, params={"page_size": 100}, timeout=30)
        resp.raise_for_status()
        records = []
        for item in resp.json().get("data", {}).get("items", []):
            fields = item.get("fields", {})
            fields["_record_id"] = item.get("record_id")
            records.append(self._normalize_record(fields))
        return records

    def update_review_fields(
        self, record_id: str, review_report_url: str, review_conclusion: str, review_status: str = "已复盘"
    ) -> dict:
        if self.use_mock:
            records = self._load_mock_records()
            for r in records:
                if r.get("_record_id") == record_id:
                    r["活动总结报告"] = review_report_url
                    r["活动功能结论"] = review_conclusion
                    r["复盘状态"] = review_status
            self.mock_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "mock": True}
        token = self._get_tenant_token()
        url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.app_token}"
            f"/tables/{self.table_id}/records/{record_id}"
        )
        resp = httpx.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"fields": {"复盘状态": review_status, "活动总结报告": review_report_url, "活动功能结论": review_conclusion}},
            timeout=30,
        )
        resp.raise_for_status()
        return {"ok": True}
