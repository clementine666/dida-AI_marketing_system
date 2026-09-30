"""Dida Data MCP 适配器 — Streamable HTTP + JSON-RPC（飞书 Data MCP 接入指南）。"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

from app.services.config_store import load_integrations


class WarehouseMcpAdapter:
    """
    道旅 Data MCP 官方接入方式：
    - URL: https://data-api-mcp.didaadmin.com/mcp/v1/query
    - 鉴权: HTTP Header `agent_user_key`
    - 协议: MCP Streamable HTTP (JSON-RPC 2.0)
    - 工具: execute_sql / search_meta_data / search_metrics / analyse_query
    """

    def __init__(self):
        cfg = load_integrations().get("warehouse_mcp", {})
        self.endpoint = (cfg.get("endpoint") or "").rstrip("/")
        self.api_key = cfg.get("api_key") or ""
        self.auth_header = cfg.get("auth_header") or "agent_user_key"
        self.protocol = cfg.get("protocol") or "streamable_http"
        self.timeout = float(os.getenv("WAREHOUSE_MCP_TIMEOUT", "120"))
        self.sql_timeout_seconds = int(os.getenv("WAREHOUSE_MCP_SQL_TIMEOUT", cfg.get("sql_timeout_seconds") or 120))
        self._initialized = False

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            self.auth_header: self.api_key,
        }

    def _ensure_initialized(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dida-marketing-system", "version": "2.0.0"},
            },
        )
        self._initialized = True

    def _rpc(self, method: str, params: dict | None = None) -> Any:
        if not self.is_configured:
            raise RuntimeError("Data MCP 未配置 endpoint 或 agent_user_key")

        if method != "initialize":
            self._ensure_initialized()

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        resp = httpx.post(self.endpoint, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message") or str(data["error"]))
        return data.get("result")

    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list")
        if isinstance(result, dict):
            return result.get("tools", [])
        return []

    def call_tool(self, name: str, arguments: dict) -> Any:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return self._parse_tool_result(result)

    def search_meta_data(self, keyword: str) -> Any:
        return self.call_tool("search_meta_data", {"keyword": keyword})

    def execute_sql(self, sql: str, tables: list[str], data_type: int = 3) -> list[dict]:
        """
        data_type（接入指南）: 1=实时订单, 2=离线订单, 3=其他表
        booking.channelbooking_v2 等订单表应使用 data_type=2
        """
        raw = self.call_tool(
            "execute_sql",
            {
                "sql": sql.strip(),
                "data_type": data_type,
                "tables": tables,
                "timeout_seconds": self.sql_timeout_seconds,
            },
        )
        rows = self._normalize_rows(raw)
        if rows and len(rows) == 1 and rows[0].get("raw", "").startswith("Error"):
            raise RuntimeError(rows[0]["raw"])
        return rows

    def search_metrics(self, *, metric_code: str | None = None, search_content: str | None = None) -> Any:
        return self.call_tool(
            "search_metrics",
            {"metric_code": metric_code, "search_content": search_content},
        )

    def get_analyse_dimension(self, metrics: list[str], date_group_type: int | None = 4) -> Any:
        args: dict[str, Any] = {"metrics": metrics}
        if date_group_type is not None:
            args["date_group_type"] = date_group_type
        return self.call_tool("get_analyse_dimension", args)

    def analyse_query(self, **kwargs: Any) -> dict:
        """官方指标分析查询（核心接口，见 Data MCP 接入指南 §5.1）。"""
        raw = self.call_tool("analyse_query", kwargs)
        if isinstance(raw, str):
            if raw.startswith("Error"):
                raise RuntimeError(raw)
            try:
                import json

                raw = json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
        if not isinstance(raw, dict):
            return {"raw": raw}
        qinfo = raw.get("queryInfo") or {}
        if qinfo.get("errorMsg"):
            raise RuntimeError(str(qinfo.get("errorMsg")))
        return raw

    @staticmethod
    def infer_sql_data_type(tables: list[str]) -> int:
        """按表名推断 execute_sql 的 data_type。"""
        joined = " ".join(tables).lower()
        if "channelbooking" in joined or joined.startswith("booking."):
            return 2
        return 3

    def execute_sql_auto_type(self, sql: str, tables: list[str]) -> list[dict]:
        return self.execute_sql(sql, tables=tables, data_type=self.infer_sql_data_type(tables))

    @staticmethod
    def _parse_tool_result(result: Any) -> Any:
        if result is None:
            return None
        if isinstance(result, dict) and "content" in result:
            texts = []
            for block in result.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            merged = "\n".join(texts)
            try:
                return json.loads(merged)
            except json.JSONDecodeError:
                return merged
        return result

    @staticmethod
    def _normalize_rows(raw: Any) -> list[dict]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [r if isinstance(r, dict) else {"value": r} for r in raw]
        if isinstance(raw, dict):
            if "rows" in raw:
                return raw["rows"]
            if "data" in raw:
                return raw["data"]
            if "columns" in raw and "values" in raw:
                cols = raw["columns"]
                return [dict(zip(cols, row)) for row in raw["values"]]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return WarehouseMcpAdapter._normalize_rows(parsed)
            except json.JSONDecodeError:
                return [{"raw": raw}]
        return [{"raw": str(raw)}]

    def health_check(self) -> dict:
        if not self.is_configured:
            return {"ok": False, "mode": "not_configured"}
        try:
            tools = self.list_tools()
            names = [t.get("name") for t in tools if isinstance(t, dict)]
            return {
                "ok": True,
                "mode": "dida_data_mcp",
                "endpoint": self.endpoint,
                "tools": names,
                "sql_timeout_seconds": self.sql_timeout_seconds,
            }
        except Exception as e:
            return {"ok": False, "mode": "dida_data_mcp", "endpoint": self.endpoint, "error": str(e)}
