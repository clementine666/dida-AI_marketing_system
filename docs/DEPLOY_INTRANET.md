# 内网部署指南

## 启动

```powershell
cd multi-agent-marketing-system
py -3.11 scripts/migrate_v2.py
py -3.11 scripts/import_data.py          # 可选：导入样本数仓
py -3.11 scripts/industry_intel_collector.py
py -3.11 -m app.main
```

## 访问地址

| 地址 | 说明 |
|------|------|
| `http://<内网IP>:8000/` | 自动跳转营销师工作台 |
| `http://<内网IP>:8000/ui/dashboard/index.html` | 工作台直接访问 |
| `http://<内网IP>:8000/docs` | API 文档 |
| `http://<内网IP>:8000/api/v2/...` | 后端 API |

## 工作台功能

- **左侧导航**：Agent1~5 竖排 + 系统配置入口
- **右侧内容**：每个 Agent 两个 Tab
  - **工作结果**：该 Agent 产出（日历/准备队列/AI建议/资源配置/监控/复盘/档案）
  - **提示词 · 功能配置**：System Prompt、工具、人工闸门（保存到 `config/agents.yaml`）
- **系统配置**
  - MCP 数据配置：数仓三张表 + 飞书凭证说明
  - 营销日历：飞书同步状态 + JSON 上传
  - 活动案例库：Agent5 归档检索

## 生产环境变量

```powershell
$env:WAREHOUSE_MCP_ENDPOINT = "https://dw-mcp.internal/api"
$env:FEISHU_APP_ID = "cli_xxx"
$env:FEISHU_APP_SECRET = "xxx"
$env:FEISHU_MARKETING_CALENDAR_TABLE_ID = "tblXXX"
```

## 内网服务器部署（示例）

```powershell
# 绑定 0.0.0.0 允许内网访问（config.yaml api.host 已默认 0.0.0.0）
py -3.11 -m app.main

# 或使用 uvicorn 多 worker
py -3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

可用 IIS / Nginx 反向代理到 8000 端口，配置内网域名如 `http://marketing.internal.dida.com`。
