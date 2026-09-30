"""LLM 客户端 — 千问 / DeepSeek，用于 Agent1 行业情报。"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.config_store import load_integrations


class LlmClient:
    def __init__(self):
        cfg = load_integrations().get("llm", {})
        self.default_provider = cfg.get("default_provider", "qwen")
        self.providers = {
            "qwen": cfg.get("qwen", {}),
            "deepseek": cfg.get("deepseek", {}),
        }
        self.intel_cfg = cfg.get("industry_intel", {})

    def get_active_provider(self) -> str:
        return self.intel_cfg.get("provider") or self.default_provider

    def is_configured(self) -> bool:
        p = self.get_active_provider()
        return bool(self.providers.get(p, {}).get("api_key"))

    def get_status(self) -> dict:
        p = self.get_active_provider()
        prov = self.providers.get(p, {})
        return {
            "active_provider": p,
            "model": prov.get("model"),
            "base_url": prov.get("base_url"),
            "configured": bool(prov.get("api_key")),
            "industry_intel_provider": self.intel_cfg.get("provider"),
        }

    def chat(self, messages: list[dict], provider: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> str:
        p = provider or self.get_active_provider()
        prov = self.providers.get(p, {})
        api_key = prov.get("api_key")
        if not api_key:
            raise RuntimeError(f"LLM {p} api_key 未配置，请在工作台「AI 模型配置」填写")

        url = f"{prov['base_url'].rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": prov.get("model"),
            "messages": messages,
            "temperature": temperature if temperature is not None else self.intel_cfg.get("temperature", 0.3),
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
