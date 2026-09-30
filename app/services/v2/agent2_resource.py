"""Agent2 - 客户资源配置师（v2）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine
from app.mcp.warehouse_client import WarehouseClient
from app.models.lifecycle import LifecycleStatus
from app.models.query_profile import (
    build_selection_reason,
    extract_query_profile_from_plan,
    merge_profile_overrides,
    validate_query_profile,
)
from app.services.lifecycle_service import ActivityLifecycleService
from app.services.snapshot_service import SnapshotService
from app.services.v2.agent1_planner import PlannerService


F1_HOTEL_KEYWORDS = ("Marina", "Bay", "Fullerton", "Pan Pacific", "Swissotel", "Parkroyal")


class ResourceConfiguratorService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()
        self.warehouse = WarehouseClient(self.engine)
        self.lifecycle = ActivityLifecycleService(self.engine)
        self.snapshot = SnapshotService(self.engine)
        self.planner = PlannerService(self.engine)

    def get_query_profile(self, campaign_id: str) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        profile = extract_query_profile_from_plan(plan)
        missing = validate_query_profile(profile)
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "query_profile": profile,
            "validation": {"ready": not missing, "missing_fields": missing},
        }

    def get_resource_plan(self, campaign_id: str) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        rp_raw = plan.get("resource_plan_json")
        resource_plan = {}
        if rp_raw:
            try:
                resource_plan = json.loads(rp_raw) if isinstance(rp_raw, str) else rp_raw
            except Exception:
                resource_plan = {}
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "lifecycle_status": plan.get("lifecycle_status"),
            "resource_plan": resource_plan,
            "query_profile": extract_query_profile_from_plan(plan),
        }

    def configure_resources(self, campaign_id: str, profile_overrides: dict | None = None) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}

        status = self.lifecycle.get_status(campaign_id)
        if status == LifecycleStatus.SENT_TO_AGENT2.value:
            self.lifecycle.transition(campaign_id, LifecycleStatus.RESOURCE_CONFIG.value, "agent2")
        elif status not in (
            LifecycleStatus.RESOURCE_CONFIG.value,
            LifecycleStatus.TODO_EXECUTION.value,
        ):
            self.lifecycle.transition(campaign_id, LifecycleStatus.RESOURCE_CONFIG.value, "agent2")

        base_profile = extract_query_profile_from_plan(plan)
        profile = merge_profile_overrides(base_profile, profile_overrides)
        missing = validate_query_profile(profile)
        query_result = self.warehouse.query_by_profile(profile)

        dest = profile.get("destination") or plan.get("target_dest") or "Singapore"
        clients = query_result.get("clients") or []
        client_ids = query_result.get("client_ids") or []
        hotels_raw = query_result.get("hotels") or []

        keyword_boost = profile.get("keyword_boost") or []
        if ("F1" in (plan.get("campaign_name") or "") or dest == "Singapore") and not keyword_boost:
            matched = [
                h for h in hotels_raw
                if any(k in (h.get("dida_hotel_name") or "") for k in F1_HOTEL_KEYWORDS)
            ]
            if matched:
                hotels_raw = matched + [h for h in hotels_raw if h not in matched]

        hotel_list = self._build_hotel_list(hotels_raw[: int(profile.get("hotel_limit") or 20)], dest, profile)
        delivery_mode = self._delivery_mode(plan)
        resource_plan = {
            "campaign_id": campaign_id,
            "data_source": query_result.get("data_source") or self.warehouse.get_status(),
            "query_profile_applied": query_result.get("profile_applied") or profile,
            "validation_missing": missing,
            "target_client_ids": client_ids[: int(profile.get("client_limit") or 200)],
            "client_selection_reason": build_selection_reason(
                query_result.get("profile_applied") or profile,
                len(client_ids),
                len(hotel_list),
            ),
            "client_count": len(client_ids),
            "client_preview": clients[:5],
            "hotel_list": hotel_list,
            "search_insights": query_result.get("search_insights"),
            "funnel_baseline": query_result.get("funnel_baseline"),
            "delivery_mode": delivery_mode,
            "delivery_description": "官网营销活动专区" if delivery_mode == "banner_zone" else "定向发券+短信",
            "tracking_events": {
                "banner": ["primary_banner_expose", "primary_banner_click"],
                "rp": ["hotel_detail_rp_expose", "hotel_detail_rp_click"],
                "conversion": ["hotel_prebook", "hotel_order_success"],
            },
            "resource_confirmed": False,
            "override_mode": "auto",
        }

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign SET resource_plan_json = :rp, delivery_mode = :dm,
                       target_hotel_ids = :hids, lifecycle_status = :st, updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {
                    "rp": json.dumps(resource_plan, ensure_ascii=False, default=str),
                    "dm": delivery_mode,
                    "hids": ",".join(str(h["hotel_id"]) for h in hotel_list if h.get("hotel_id")),
                    "st": LifecycleStatus.RESOURCE_CONFIG.value,
                    "cid": campaign_id,
                },
            )

        self.snapshot.save(
            campaign_id, "agent2", resource_plan, LifecycleStatus.RESOURCE_CONFIG.value, "agent2"
        )
        return {
            "ok": True,
            "resource_plan": resource_plan,
            "validation": {"ready": not missing, "missing_fields": missing},
            "needs_confirmation": True,
        }

    def preview_profile_query(self, campaign_id: str, profile_overrides: dict | None = None) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}
        base = extract_query_profile_from_plan(plan)
        profile = merge_profile_overrides(base, profile_overrides)
        result = self.warehouse.query_by_profile(profile)
        missing = validate_query_profile(profile)
        return {
            "ok": True,
            "campaign_id": campaign_id,
            "validation": {"ready": not missing, "missing_fields": missing},
            **result,
        }

    def apply_resource_override(
        self,
        campaign_id: str,
        *,
        target_client_ids: list[str] | None = None,
        target_hotel_ids: list[str] | None = None,
        override_reason: str = "",
        mode: str = "manual_ids",
        operator: str = "marketer",
    ) -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}

        rp = self._load_resource_plan(plan)
        existing_clients = rp.get("target_client_ids") or []
        existing_hotels = [h.get("hotel_id") for h in rp.get("hotel_list") or [] if h.get("hotel_id")]

        if mode == "mixed":
            clients = list(dict.fromkeys(existing_clients + (target_client_ids or [])))
            hotel_ids = list(dict.fromkeys([str(x) for x in existing_hotels] + [str(x) for x in (target_hotel_ids or [])]))
        else:
            clients = target_client_ids or existing_clients
            hotel_ids = [str(x) for x in (target_hotel_ids or existing_hotels)]

        rp["target_client_ids"] = clients
        rp["client_count"] = len(clients)
        rp["override_mode"] = mode
        rp["override_reason"] = override_reason
        rp["override_by"] = operator
        rp["override_at"] = datetime.now(timezone.utc).isoformat()
        rp["resource_confirmed"] = False

        if target_hotel_ids is not None:
            hotel_list = rp.get("hotel_list") or []
            known = {str(h.get("hotel_id")): h for h in hotel_list}
            new_list = []
            for hid in hotel_ids:
                if str(hid) in known:
                    new_list.append(known[str(hid)])
                else:
                    new_list.append({
                        "hotel_id": hid,
                        "hotel_name": f"手动指定 #{hid}",
                        "star_rating": None,
                        "selection_reason": override_reason or "运营师手动指定",
                        "avg_price_cny": None,
                        "price_compare": {},
                    })
            rp["hotel_list"] = new_list

        rp["client_selection_reason"] = (
            f"{rp.get('client_selection_reason', '')} · 人工覆盖({mode}): {override_reason or '无说明'}"
        ).strip(" · ")

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign SET resource_plan_json = :rp,
                       target_hotel_ids = :hids, updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {
                    "rp": json.dumps(rp, ensure_ascii=False, default=str),
                    "hids": ",".join(str(x) for x in hotel_ids),
                    "cid": campaign_id,
                },
            )
        return {"ok": True, "campaign_id": campaign_id, "resource_plan": rp}

    def confirm_resources(self, campaign_id: str, operator: str = "marketer") -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        if not plan:
            return {"ok": False, "error": "Campaign not found"}

        rp = self._load_resource_plan(plan)
        if not rp.get("target_client_ids") and not rp.get("hotel_list"):
            return {"ok": False, "error": "请先执行圈客选品或上传客户/酒店 ID"}

        rp["resource_confirmed"] = True
        rp["resource_confirmed_at"] = datetime.now(timezone.utc).isoformat()
        rp["resource_confirmed_by"] = operator
        todos = self._generate_todos(campaign_id, plan, rp)

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE dim_campaign SET resource_plan_json = :rp,
                       lifecycle_status = :st, updated_at = CURRENT_TIMESTAMP
                WHERE campaign_id = :cid
                """),
                {
                    "rp": json.dumps({**rp, "todos": todos}, ensure_ascii=False, default=str),
                    "st": LifecycleStatus.TODO_EXECUTION.value,
                    "cid": campaign_id,
                },
            )

        self.snapshot.save(
            campaign_id,
            "agent2",
            {**rp, "todos": todos},
            LifecycleStatus.TODO_EXECUTION.value,
            operator,
        )
        self.lifecycle.transition(campaign_id, LifecycleStatus.TODO_EXECUTION.value, operator, "运营师确认资源配置")
        return {"ok": True, "campaign_id": campaign_id, "resource_plan": rp, "todos": todos}

    def _build_hotel_list(self, hotels: list[dict], dest: str, profile: dict) -> list[dict]:
        hotel_list = []
        star_min = profile.get("star_min")
        for h in hotels:
            hid = h.get("dida_hotel_id") or h.get("standard_hotel_id")
            prices = self.warehouse.query_hotel_prices(int(hid), limit=5) if str(hid).isdigit() else []
            avg_price = sum(p["quote_price"] or 0 for p in prices) / len(prices) if prices else 500.0
            compare = self.warehouse.compare_price_vs_market(int(hid) if str(hid).isdigit() else 0, avg_price)
            hotel_list.append({
                "hotel_id": hid,
                "hotel_name": h.get("dida_hotel_name"),
                "star_rating": h.get("star_rating"),
                "selection_reason": (
                    f"{dest} · 星级≥{star_min or '—'} · "
                    f"{profile.get('hotel_selection_strategy') or profile.get('hotel_scope') or 'destination_hot'}"
                ),
                "avg_price_cny": round(avg_price, 2),
                "price_compare": compare,
            })
        return hotel_list

    @staticmethod
    def _delivery_mode(plan: dict) -> str:
        if "Banner" in (plan.get("campaign_type") or ""):
            return "banner_zone"
        structured_raw = plan.get("plan_structured_json")
        if structured_raw:
            try:
                structured = json.loads(structured_raw) if isinstance(structured_raw, str) else structured_raw
                dt = (structured.get("product_delivery") or {}).get("delivery_type")
                if dt in ("display_only", "mixed", "bundle"):
                    return "banner_zone"
            except Exception:
                pass
        return "coupon_sms"

    @staticmethod
    def _load_resource_plan(plan: dict) -> dict:
        raw = plan.get("resource_plan_json")
        if not raw:
            return {}
        try:
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            return {}

    def _generate_todos(self, campaign_id: str, plan: dict, resource: dict) -> list[dict]:
        templates = [
            ("poster", "首页Banner/营销活动专区海报", "设计部", {"size": "1920x600"}),
            ("coupon", "配置优惠券活动", "运营", {"coupon_ids": plan.get("coupon_config")}),
            ("sms", "配置短信通知模板", "运营", {"template": f"【道旅】{plan.get('campaign_name')}活动上线"}),
            ("tracking", "埋点设置（slide_id / activity_id）", "技术", {"activity_id": plan.get("activity_id")}),
            ("monitor_metric", "监控指标与计算公式配置", "数据", {
                "key_metrics_spec": plan.get("key_metrics_spec"),
                "target_metrics": plan.get("target_metrics"),
            }),
            ("launch_time", "确认上线时间", "运营", {"start_date": plan.get("start_date")}),
        ]
        todos = []
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM fact_activity_todos WHERE campaign_id = :cid"), {"cid": campaign_id})
            for i, (ttype, title, owner, cfg) in enumerate(templates):
                conn.execute(
                    text("""
                    INSERT INTO fact_activity_todos
                    (campaign_id, todo_type, title, description, owner, sort_order, config_json)
                    VALUES (:cid, :type, :title, :desc, :owner, :ord, :cfg)
                    """),
                    {
                        "cid": campaign_id,
                        "type": ttype,
                        "title": title,
                        "desc": title,
                        "owner": owner,
                        "ord": i,
                        "cfg": json.dumps(cfg, ensure_ascii=False, default=str),
                    },
                )
                todos.append({"todo_type": ttype, "title": title, "owner": owner, "is_done": False, "config": cfg})
        return todos

    def list_todos(self, campaign_id: str) -> list[dict]:
        sql = "SELECT * FROM fact_activity_todos WHERE campaign_id = :cid ORDER BY sort_order"
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), {"cid": campaign_id})]

    def complete_todo(self, todo_id: int, operator: str = "marketer") -> dict:
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE fact_activity_todos SET is_done = 1, done_at = CURRENT_TIMESTAMP WHERE todo_id = :id"),
                {"id": todo_id},
            )
            row = conn.execute(
                text("SELECT campaign_id FROM fact_activity_todos WHERE todo_id = :id"), {"id": todo_id}
            ).fetchone()
        return {"ok": True, "todo_id": todo_id, "campaign_id": row.campaign_id if row else None}

    def submit_for_testing(self, campaign_id: str, operator: str = "marketer") -> dict:
        plan = self.planner.get_activity_plan(campaign_id)
        rp = self._load_resource_plan(plan or {})
        if not rp.get("resource_confirmed"):
            return {"ok": False, "error": "请先确认锁定资源配置", "require_resource_confirm": True}
        todos = self.list_todos(campaign_id)
        pending = [t for t in todos if not t.get("is_done")]
        if pending:
            return {"ok": False, "error": "仍有未完成待办", "pending": [t["title"] for t in pending]}
        return self.lifecycle.transition(campaign_id, LifecycleStatus.TESTING.value, operator, "提交测试")

    def approve_testing(self, campaign_id: str, operator: str = "marketer") -> dict:
        return self.lifecycle.transition(campaign_id, LifecycleStatus.SCHEDULED.value, operator, "测试通过")
