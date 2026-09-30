"""（可选）将来部署时打包发布目录。日常开发不需要运行本脚本。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 与「AI智能推荐酒店」等并列，放在 石军军的研发 目录下
DEFAULT_OUT = ROOT.parent.parent.parent / "多Agent营销协作系统"

# 复制这些顶层项
COPY_ITEMS = [
    "app",
    "agents",
    "ui",
    "config",
    "docs",
    "scripts",
    "database",
    "requirements.txt",
    "config.yaml",
    "README.md",
    "启动开发服务.bat",
]

# 跳过的目录/文件
SKIP_NAMES = {
    "__pycache__",
    ".git",
    ".env",
    "marketing.db",
    "integrations.yaml",  # 用模板生成，避免打包真实密钥
}

SKIP_SUFFIXES = {".pyc", ".pyo"}

# 可选：体积较大的演示输出，部署包可不带上
OPTIONAL_SKIP_FILES = {
    "data/v2_workflow_output.json",
    "data/f1_workflow_output.json",
}


def _should_skip(path: Path) -> bool:
    if path.name in SKIP_NAMES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    rel = path.relative_to(ROOT).as_posix()
    if rel in OPTIONAL_SKIP_FILES:
        return True
    return False


def _copy_tree(src: Path, dst: Path) -> None:
    if src.is_file():
        if _should_skip(src):
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    if not src.is_dir():
        return
    for item in src.iterdir():
        if _should_skip(item):
            continue
        _copy_tree(item, dst / item.name)


def _write_integrations_template(dest_config: Path) -> None:
    example = dest_config / "integrations.yaml.example"
    target = dest_config / "integrations.yaml"
    template = """# 集成密钥配置（工作台 MCP 配置页可编辑）

warehouse_mcp:
  enabled: true
  endpoint: "https://data-api-mcp.didaadmin.com/mcp/v1/query"
  protocol: "streamable_http"
  auth_header: "agent_user_key"
  api_key: ""
  use_local_fallback: true
  tables:
    events: shopping.ods_amplitude_events
    users: shopping.ods_amplitude_users
    funnel: dwd.dwd_hotel_shopping_funnel_detail_d_f

feishu:
  app_id: ""
  app_secret: ""
  marketing_calendar_table_id: ""
  marketing_calendar_view_id: ""

llm:
  default_provider: qwen
  qwen:
    api_key: ""
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: "qwen-plus"
  deepseek:
    api_key: ""
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-chat"
  industry_intel:
    provider: qwen
    temperature: 0.3
"""
    example.write_text(template, encoding="utf-8")
    if not target.exists():
        target.write_text(template, encoding="utf-8")


def _write_deploy_files(out: Path) -> None:
    (out / "启动服务.bat").write_text(
        """@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 多Agent营销协作系统

echo [1/3] 释放 8000 端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo [2/3] 初始化数据库...
py -3.11 scripts\\migrate_v2.py

echo [3/3] 启动服务...
echo 浏览器访问: http://localhost:8000
py -3.11 -m app.main

pause
""",
        encoding="utf-8",
    )

    (out / "首次安装.bat").write_text(
        """@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 多Agent营销协作系统 - 首次安装

echo 安装 Python 依赖...
py -3.11 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo 初始化数据库...
py -3.11 scripts\\migrate_v2.py

echo 导入样本数据（可选，Mock 模式）...
py -3.11 scripts\\import_data.py

echo.
echo 安装完成。请双击「启动服务.bat」或「启动开发服务.bat」
pause
""",
        encoding="utf-8",
    )

    (out / "部署说明.txt").write_text(
        """多Agent营销协作系统 — 部署说明
================================

【环境要求】
  Python 3.11+
  Windows 内网服务器或本机

【首次部署】
  1. 双击「首次安装.bat」（安装依赖 + 建库 + 样本数据）
  2. 编辑 config\\integrations.yaml 填写 MCP Key、飞书、LLM（或用工作台配置页）
  3. 双击「启动服务.bat」

【日常启动】
  - 生产：启动服务.bat
  - 开发（改代码自动重启）：启动开发服务.bat

【访问地址】
  本机：http://localhost:8000
  内网：http://<服务器IP>:8000

【验证新版本】
  http://localhost:8000/api/v2/health

【目录说明】
  app/ agents/   后端 API 与 5-Agent 逻辑
  ui/           营销师工作台
  config/       Agent 提示词、MCP/LLM 配置
  data/         数据库与样本/Mock 数据
  docs/         集成与流程文档
  scripts/      迁移、导入、情报采集脚本

【定时任务（可选）】
  每周行业情报：py -3.11 scripts\\industry_intel_collector.py --llm
""",
        encoding="utf-8",
    )


def package_release(out_dir: Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in COPY_ITEMS:
        src = ROOT / name
        if not src.exists():
            continue
        dst = out / name
        if src.is_dir():
            _copy_tree(src, dst)
        else:
            shutil.copy2(src, dst)

    # data 目录（mock 与样本，不含 db）
    data_src = ROOT / "data"
    if data_src.exists():
        _copy_tree(data_src, out / "data")
    (out / "data" / "intel_uploads").mkdir(parents=True, exist_ok=True)

    _write_integrations_template(out / "config")
    _write_deploy_files(out)

    print(f"Packaged to: {out}")
    print(f"Files: {sum(1 for _ in out.rglob('*') if _.is_file())}")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    package_release(target)
