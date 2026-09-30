#!/usr/bin/env python3
"""读取飞书云文档（docx）纯文本 / 基本信息，导出为 Markdown 文件。

用法:
  py -3.11 scripts/feishu_read_docx.py "https://didatravel.feishu.cn/docx/N0V5dJWHtom5BsxzlEXcJ2nqnlh"
  py -3.11 scripts/feishu_read_docx.py N0V5dJWHtom5BsxzlEXcJ2nqnlh -o docs/feishu_import/营销活动流程.md

凭证（任选其一，优先级从高到低）:
  1. 环境变量 FEISHU_USER_ACCESS_TOKEN  （用户令牌，可读有权限的个人/协作文档）
  2. 环境变量 FEISHU_APP_ID + FEISHU_APP_SECRET  （租户令牌）
  3. config/integrations.yaml 中 feishu.app_id / feishu.app_secret

飞书应用权限（租户令牌）:
  - docx:document:readonly  或  docx:document
  - 并在目标文档右上角「…」→「添加文档应用」授权该 App

注意:
  - raw_content 仅返回纯文本，流程图/图片不会保留结构，需人工对照原文档。
  - 若 403/1770032，多为文档未授权给应用，或需改用 user_access_token。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FEISHU_API = "https://open.feishu.cn/open-apis"
DOCX_ID_RE = re.compile(r"^[A-Za-z0-9]{22,30}$")


def load_feishu_creds() -> dict[str, str]:
    cfg: dict[str, Any] = {}
    path = ROOT / "config" / "integrations.yaml"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            cfg = data.get("feishu") or {}

    return {
        "app_id": (os_get("FEISHU_APP_ID") or cfg.get("app_id") or "").strip(),
        "app_secret": (os_get("FEISHU_APP_SECRET") or cfg.get("app_secret") or "").strip(),
        "user_token": os_get("FEISHU_USER_ACCESS_TOKEN", "").strip(),
    }


def os_get(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def parse_document_token(url_or_id: str) -> tuple[str, str]:
    """从 URL 或 token 解析 document_id。返回 (kind, token)。"""
    s = url_or_id.strip()
    if DOCX_ID_RE.match(s):
        return "docx", s

    parsed = urlparse(s)
    path = parsed.path.strip("/")
    parts = path.split("/")

    # .../docx/{token}
    if "docx" in parts:
        idx = parts.index("docx")
        if idx + 1 < len(parts):
            token = parts[idx + 1].split("?")[0]
            return "docx", token

    # .../wiki/{token}
    if "wiki" in parts:
        idx = parts.index("wiki")
        if idx + 1 < len(parts):
            token = parts[idx + 1].split("?")[0]
            return "wiki", token

    raise ValueError(f"无法从链接解析 document token: {url_or_id}")


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    resp = httpx.post(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
    return data["tenant_access_token"]


def resolve_access_token(creds: dict[str, str]) -> tuple[str, str]:
    if creds.get("user_token"):
        return creds["user_token"], "user_access_token"
    if creds.get("app_id") and creds.get("app_secret"):
        return get_tenant_access_token(creds["app_id"], creds["app_secret"]), "tenant_access_token"
    raise RuntimeError(
        "未配置飞书凭证。请设置 FEISHU_USER_ACCESS_TOKEN，"
        "或在 config/integrations.yaml / 环境变量中配置 FEISHU_APP_ID + FEISHU_APP_SECRET"
    )


def wiki_token_to_document_id(token: str, access_token: str) -> str:
    """Wiki 节点 token → 云文档 obj_token（document_id）。"""
    resp = httpx.get(
        f"{FEISHU_API}/wiki/v2/spaces/get_node",
        params={"token": token},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Wiki get_node 失败: {json.dumps(data, ensure_ascii=False)}")

    node = data.get("data", {}).get("node") or {}
    obj_token = node.get("obj_token")
    obj_type = node.get("obj_type")
    if obj_type != "docx" or not obj_token:
        raise RuntimeError(
            f"Wiki 节点不是 docx 或缺少 obj_token: type={obj_type}, node={json.dumps(node, ensure_ascii=False)}"
        )
    return obj_token


def feishu_get(path: str, access_token: str, params: dict | None = None) -> dict:
    resp = httpx.get(
        f"{FEISHU_API}{path}",
        params=params,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API 错误 {path}: {json.dumps(data, ensure_ascii=False)}")
    return data.get("data") or {}


def fetch_document(document_id: str, access_token: str) -> dict[str, Any]:
    meta = feishu_get(f"/docx/v1/documents/{document_id}", access_token)
    raw = feishu_get(f"/docx/v1/documents/{document_id}/raw_content", access_token)
    return {
        "document_id": document_id,
        "title": (meta.get("document") or {}).get("title") or "未命名文档",
        "revision_id": (meta.get("document") or {}).get("revision_id"),
        "content": raw.get("content") or "",
    }


def to_markdown(doc: dict[str, Any], source_url: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = doc["title"]
    body = doc["content"].strip()
    return (
        f"# {title}\n\n"
        f"> 自动导入 · {now}  \n"
        f"> 来源: {source_url}  \n"
        f"> document_id: `{doc['document_id']}`  \n"
        f"> 说明: 纯文本导出，流程图/图片需对照飞书原文。\n\n"
        f"---\n\n"
        f"{body}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="读取飞书 docx 文档并导出 Markdown")
    parser.add_argument("url_or_id", help="飞书 docx/wiki 链接或 document token")
    parser.add_argument("-o", "--output", help="输出文件路径（默认打印到 stdout）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    args = parser.parse_args()

    kind, token = parse_document_token(args.url_or_id)
    creds = load_feishu_creds()
    access_token, token_type = resolve_access_token(creds)

    print(f"[feishu] 使用 {token_type}", file=sys.stderr)

    document_id = token
    if kind == "wiki":
        print(f"[feishu] Wiki token → document_id …", file=sys.stderr)
        document_id = wiki_token_to_document_id(token, access_token)

    print(f"[feishu] 读取 document_id={document_id} …", file=sys.stderr)
    doc = fetch_document(document_id, access_token)

    source_url = args.url_or_id if args.url_or_id.startswith("http") else f"docx:{document_id}"

    if args.json:
        out = json.dumps(doc, ensure_ascii=False, indent=2)
    else:
        out = to_markdown(doc, source_url)

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        print(f"[feishu] 已写入 {out_path} ({len(doc['content'])} 字符)", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
