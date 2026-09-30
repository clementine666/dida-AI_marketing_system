# 部署指南

## 环境要求

- Python 3.10+
- Windows / Linux / macOS
- 可选：PostgreSQL 15+（生产环境推荐）

## 本地开发部署

```bash
# 1. 进入项目目录
cd multi-agent-marketing-system

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化
python scripts/init_db.py

# 5. 验证
python agents/workflow_f1.py

# 6. 启动 API
python -m app.main
```

## 生产部署（PostgreSQL）

1. 创建数据库 `marketing`
2. 修改 `config.yaml` 中 database 配置
3. 执行 schema（需将 AUTOINCREMENT 改为 SERIAL）
4. 配置数据源路径或对接数据仓库 API
5. 使用 gunicorn/uvicorn 部署：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 定时任务

### Windows 任务计划程序

| 任务 | 脚本 | 频率 |
|------|------|------|
| 每日 ETL | `python scripts/etl_daily.py` | 每天 02:00 |
| 小时监控 | `python scripts/etl_hourly_monitor.py` | 每小时 |

### Linux cron

```cron
0 2 * * * cd /path/to/project && .venv/bin/python scripts/etl_daily.py
0 * * * * cd /path/to/project && .venv/bin/python scripts/etl_hourly_monitor.py
```

## 接入真实数据

1. 从 Amplitude / 数据仓库导出 CSV 到 `data/raw/`
2. 设置 `generate_sample_if_missing: false`
3. 运行 `python scripts/import_data.py`

## 接入 Agent 框架（LangGraph 示例）

```python
from app.services.agent1_service import Agent1Service
from app.services.agent2_service import Agent2Service

def agent1_node(state):
    report = Agent1Service().get_demand_report(state["destination"])
    return {"demand_report": report}

def agent2_node(state):
    match = Agent2Service().match_resources(state["destination"])
    return {"resource_match": match}
```

数据访问层与 LLM Agent 解耦，Agent 框架负责推理编排，本系统提供结构化数据接口。
