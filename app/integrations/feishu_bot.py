"""飞书群自定义机器人（Webhook）— 任务催办通知。"""

from __future__ import annotations

import httpx

from app.services.config_store import load_integrations

DEFAULT_KEYWORD = "任务通知"


class FeishuBotClient:
    def __init__(self, webhook_url: str | None = None, keyword: str | None = None):
        cfg = load_integrations().get("feishu", {})
        self.webhook_url = (webhook_url or cfg.get("bot_webhook_url") or "").strip()
        self.keyword = (keyword or cfg.get("bot_keyword") or DEFAULT_KEYWORD).strip() or DEFAULT_KEYWORD

    def is_configured(self) -> bool:
        return self.webhook_url.startswith("https://") and "/bot/v2/hook/" in self.webhook_url

    def send_text(self, message: str) -> dict:
        if not self.is_configured():
            return {"ok": False, "error": "未配置飞书催办 Webhook URL"}
        text = message or ""
        if self.keyword not in text:
            text = f"{self.keyword}：{text}"
        try:
            resp = httpx.post(
                self.webhook_url,
                json={"msg_type": "text", "content": {"text": text}},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:300]}
            ok = resp.status_code == 200 and int(data.get("code", -1) or -1) == 0
            return {
                "ok": ok,
                "status_code": resp.status_code,
                "feishu": data,
                "message": "已发送到飞书群" if ok else (data.get("msg") or data.get("error") or "飞书拒绝或网络失败"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "message": f"发送失败：{e}"}


def format_remind_message(
    *,
    level: int,
    activity_name: str,
    task_name: str,
    assignee: str,
    deadline: str,
    days_left: int | None = None,
    detail_url: str = "http://172.16.16.45:8000/app",
) -> str:
    if level >= 3:
        prefix, status = "🚨 任务已到期", "🚨 已到期，请立即处理"
    elif level == 2:
        prefix, status = "⚠️ 任务即将到期", "⚠️ 明天到期"
    else:
        remain = f"还剩{days_left}天" if days_left is not None else "请关注进度"
        prefix, status = "⏰ 任务提醒", f"📅 {remain}"
    return (
        f"任务通知：{prefix}\n\n"
        f"活动：{activity_name}\n"
        f"任务：{task_name}\n"
        f"负责人：{assignee or '—'}\n"
        f"截止：{deadline}\n"
        f"状态：{status}\n\n"
        f"查看详情：{detail_url}"
    )
