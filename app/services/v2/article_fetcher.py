"""从 URL 抓取文章正文（公众号 / 普通网页）。"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import httpx

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _meta_content(html: str, prop: str) -> str:
    for pattern in (
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(prop)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            return unescape(m.group(1)).strip()
    return ""


def _tag_text(html: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>([\s\S]*?)</{tag}>", html, re.I)
    return _strip_html(m.group(1)) if m else ""


def _weixin_content(html: str) -> str:
    for pattern in (
        r'id="js_content"[^>]*>([\s\S]*?)</div>\s*<script',
        r'class="rich_media_content[^"]*"[^>]*id="js_content"[^>]*>([\s\S]*?)</div>',
        r'class="rich_media_content[^"]*"[^>]*>([\s\S]*?)</div>\s*<div[^>]+id="js_tags"',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            body = _strip_html(m.group(1))
            if len(body) >= 80:
                return body
    return ""


def _generic_article(html: str) -> str:
    for pattern in (
        r"<article[^>]*>([\s\S]*?)</article>",
        r'<div[^>]+class="[^"]*article[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]+class="[^"]*content[^"]*"[^>]*>([\s\S]*?)</div>',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            body = _strip_html(m.group(1))
            if len(body) >= 120:
                return body[:50000]
    body = _tag_text(html, "body")
    return body[:50000] if body else ""


def is_weixin_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return "mp.weixin.qq.com" in host or "weixin.qq.com" in host


def fetch_article_from_url(url: str, *, timeout: float = 45) -> dict:
    """
    抓取 URL 正文。返回 title / content / source_type / url。
    公众号链接优先解析 #js_content。
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("链接不能为空")
    if not url.startswith(("http://", "https://")):
        raise ValueError("请填写以 http:// 或 https:// 开头的完整链接")

    resp = httpx.get(url, headers=_BROWSER_HEADERS, follow_redirects=True, timeout=timeout)
    resp.raise_for_status()
    html = resp.text

    if "环境异常" in html or "完成验证后即可继续访问" in html:
        raise RuntimeError(
            "公众号页面需要人机验证，服务器无法自动抓取。"
            "请打开链接后复制正文粘贴，或使用微信「复制链接」在浏览器登录后再试。"
        )

    title = _meta_content(html, "og:title") or _tag_text(html, "title")
    author = _meta_content(html, "og:article:author") or _meta_content(html, "author")
    publish = _meta_content(html, "og:article:publish_time")

    if is_weixin_url(url):
        content = _weixin_content(html)
        source_type = "weixin_mp"
    else:
        content = _generic_article(html)
        source_type = "web_url"

    if not content:
        desc = _meta_content(html, "og:description") or _meta_content(html, "description")
        content = desc

    if not content or len(content) < 40:
        raise RuntimeError(
            "未能从链接提取足够正文（可能需登录、反爬或页面结构不支持）。"
            "请改用手动粘贴正文。"
        )

    header_bits = [f"来源链接：{url}"]
    if author:
        header_bits.append(f"作者：{author}")
    if publish:
        header_bits.append(f"发布时间：{publish}")
    full_content = "\n".join(header_bits) + "\n\n" + content

    if not title:
        title = content[:40].replace("\n", " ") + "…"

    return {
        "url": url,
        "title": title[:200],
        "author": author,
        "publish_time": publish,
        "content": full_content,
        "source_type": source_type,
        "char_count": len(full_content),
    }
