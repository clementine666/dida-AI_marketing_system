# 多Agent营销协作系统

道旅科技 portal.dida.com 营销自动化 — 5-Agent 协作工作台

## 日常开发（只用本文件夹）

**项目根目录就是本仓库，不要再用旁边的「多Agent营销协作系统」部署包文件夹。**

| 要做的事 | 操作 |
|----------|------|
| 启动系统 + 打开浏览器 | 双击 **`打开最新系统.bat`** |
| 只启动后台服务 | 双击 **`启动开发服务.bat`** |
| 浏览器地址 | `http://localhost:8000/app` |
| 密钥与连接配置 | 左侧 **系统连接配置**（写入 `config/integrations.yaml`） |

改代码后服务会自动重启；配置保存后无需重启。

**将来要部署：** 把整个 `multi-agent-marketing-system` 文件夹拷到目标机器，安装依赖后运行 `py -3.11 scripts/run_dev.py` 或 `py -3.11 -m app.main` 即可。日常开发不需要打包。

---

```bash
python scripts/migrate_v2.py
python scripts/industry_intel_collector.py
python agents/workflow_v2.py
python -m app.main
# v2 API: http://localhost:8000/api/v2/calendar?months=3
```

| Agent | 定位 | v2 API |
|-------|------|--------|
| Agent1 | 方案策划师 | `/api/v2/calendar` |
| Agent2 | 客户资源配置师 | `/api/v2/activities/{id}/configure` |
| Agent3 | 活动监控师 | `/api/v2/activities/{id}/monitor/preview` |
| Agent4 | 活动分析师 | `/api/v2/activities/{id}/review` |
| Agent5 | 活动归档师 | `/api/v2/activities/{id}/archive` |

详见 [docs/API_V2.md](docs/API_V2.md) 与 [docs/ALIGNMENT.md](docs/ALIGNMENT.md)

## 快速开始（v1 遗留 API 仍可用）

```bash
cd 02-进行中任务/multi-agent-marketing-system

# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库 + 导入数据（无样本文件时自动生成 1 万条模拟数据）
python scripts/init_db.py

# 3. 运行新加坡 F1 完整工作流示例
python agents/workflow_f1.py

# 4. 启动 API 服务
python -m app.main
# 访问 http://localhost:8000/docs
```

## 导入真实样本数据

将 Excel/CSV 放到 `data/raw/` 并修改 `config.yaml`：

| 文件 | 对应源表 |
|------|---------|
| `ods_amplitude_events.csv` | 用户行为事件 |
| `ods_amplitude_users.csv` | 用户基础信息 |
| `dwd_hotel_shopping_funnel_detai.csv` | 购物漏斗 |
| `channelbooking_v2.csv` | 伽利略订单（可选） |

然后执行：`python scripts/import_data.py`

## 项目结构

```
multi-agent-marketing-system/
├── database/schema.sql      # 13张核心表 DDL
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── db.py                # 数据库连接
│   ├── services/            # Agent 1-4 数据服务
│   └── routers/             # REST API 路由
├── scripts/
│   ├── init_db.py           # 初始化
│   ├── import_data.py       # 数据导入 ETL
│   ├── etl_daily.py         # 每日 T-1 同步
│   └── etl_hourly_monitor.py # 每小时监控
├── agents/workflow_f1.py    # F1 示例工作流
├── config.yaml
└── docs/                    # 技术文档
```

## 13 张核心表

| 表名 | 用途 | 主要 Agent |
|------|------|-----------|
| dim_client | 客户维度 + 标签 | Agent 1 |
| fact_events | 用户行为（JSON 已解析） | Agent 1, 3, 4 |
| fact_funnel | 购物漏斗 | Agent 1, 3, 4 |
| dim_hotel | 酒店维度 + 标签 | Agent 2 |
| dim_campaign | 活动配置 | Agent 3 |
| fact_campaign_metrics | 活动效果 | Agent 3, 4 |
| fact_orders | 订单（含 campaign_id） | Agent 4 |
| dim_destination_events | 目的地情报 | Agent 1 |
| dim_holiday | 节假日 | Agent 1 |
| fact_monitor | 实时监控 | Agent 3 |
| dim_alert_rules | 告警规则 | Agent 3 |
| fact_search | 搜索聚合 | Agent 1 |
| fact_session | 会话聚合 | Agent 1 |

## API 概览

| Agent | 核心接口 | 说明 |
|-------|---------|------|
| Agent 1 | `GET /api/agent1/demand-report?destination=Singapore` | 客户需求报告 |
| Agent 2 | `GET /api/agent2/match?destination=Singapore` | 资源匹配方案 |
| Agent 3 | `POST /api/agent3/monitor/{campaign_id}/run` | 执行监控告警 |
| Agent 4 | `GET /api/agent4/review/CAMP_F1_SG_2026` | 复盘报告 |

## 数据同步

```bash
# 每日 T-1（可配置 cron / Windows 任务计划）
python scripts/etl_daily.py

# 每小时监控
python scripts/etl_hourly_monitor.py
```

## 技术选型

- **数据库**: SQLite（默认）/ PostgreSQL（修改 config.yaml）
- **API**: FastAPI + SQLAlchemy
- **Agent 框架**: 数据访问层已就绪，可接入 LangGraph / CrewAI

详细文档见 `docs/` 目录。
