"""活动各阶段快照服务。"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine


class SnapshotService:
    def __init__(self, engine: Engine | None = None):
        self.engine = engine or get_engine()

    def save(
        self,
        campaign_id: str,
        agent_name: str,
        payload: dict,
        lifecycle_status: str | None = None,
        created_by: str = "system",
    ) -> int:
        with self.engine.connect() as conn:
            ver = conn.execute(
                text("""
                SELECT COALESCE(MAX(snapshot_version), 0) + 1 FROM fact_activity_snapshot
                WHERE campaign_id = :cid AND agent_name = :agent
                """),
                {"cid": campaign_id, "agent": agent_name},
            ).scalar()
        with self.engine.begin() as conn:
            result = conn.execute(
                text("""
                INSERT INTO fact_activity_snapshot
                (campaign_id, agent_name, snapshot_version, lifecycle_status, payload_json, created_by)
                VALUES (:cid, :agent, :ver, :st, :payload, :by)
                """),
                {
                    "cid": campaign_id,
                    "agent": agent_name,
                    "ver": ver,
                    "st": lifecycle_status,
                    "payload": json.dumps(payload, ensure_ascii=False, default=str),
                    "by": created_by,
                },
            )
            return result.lastrowid or ver

    def get_latest(self, campaign_id: str, agent_name: str | None = None) -> dict | list[dict] | None:
        if agent_name:
            sql = """
            SELECT * FROM fact_activity_snapshot
            WHERE campaign_id = :cid AND agent_name = :agent
            ORDER BY snapshot_version DESC LIMIT 1
            """
            params = {"cid": campaign_id, "agent": agent_name}
        else:
            sql = """
            SELECT * FROM fact_activity_snapshot
            WHERE campaign_id = :cid
            ORDER BY agent_name, snapshot_version DESC
            """
            params = {"cid": campaign_id}
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
            if not rows:
                return None
            results = []
            seen = set()
            for r in rows:
                d = dict(r._mapping)
                key = d["agent_name"]
                if agent_name or key not in seen:
                    d["payload"] = json.loads(d["payload_json"])
                    results.append(d)
                    seen.add(key)
            if agent_name:
                return results[0] if results else None
            return results

    def get_full_chain(self, campaign_id: str) -> dict:
        snapshots = self.get_latest(campaign_id)
        if not snapshots:
            return {"campaign_id": campaign_id, "snapshots": {}}
        if isinstance(snapshots, dict):
            snapshots = [snapshots]
        return {
            "campaign_id": campaign_id,
            "snapshots": {s["agent_name"]: s["payload"] for s in snapshots},
        }
