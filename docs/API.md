# API 文档

Base URL: `http://localhost:8000`

交互式文档: `/docs`

## Agent 1 - 信息数据分析

### GET /api/agent1/clients
查询客户画像。

| 参数 | 类型 | 说明 |
|------|------|------|
| client_id | string | 可选，指定客户 |
| limit | int | 默认 50 |

### GET /api/agent1/behavior/{user_id}
查询用户行为轨迹。

### GET /api/agent1/search-preferences
查询搜索偏好，支持 `destination` 过滤。

### GET /api/agent1/funnel
漏斗转化分析，支持 `client_id`, `country`。

### GET /api/agent1/demand-report ⭐
**核心输出** — 客户需求报告。

| 参数 | 默认 | 说明 |
|------|------|------|
| destination | Singapore | 目标目的地 |

返回：target_clients, search_preferences, funnel_analysis, external_events, recommendation_direction

---

## Agent 2 - 资源匹配

### GET /api/agent2/hotels
酒店资源查询。

### GET /api/agent2/price-inventory
价格库存数据。

### GET /api/agent2/rp/{hotel_id}
RP 房价计划数据。

### GET /api/agent2/resource-gaps
资源缺口分析。

### GET /api/agent2/match ⭐
**核心输出** — 资源匹配方案。

---

## Agent 3 - 方案策划+监控

### GET /api/agent3/campaigns
活动列表。

### GET /api/agent3/metrics/{campaign_id}
实时活动指标。

### GET /api/agent3/alert-rules/{campaign_id}
告警规则。

### GET /api/agent3/monitor/{campaign_id}
监控历史。

### POST /api/agent3/monitor/{campaign_id}/run
执行监控并触发告警。

---

## Agent 4 - 效果复盘

### GET /api/agent4/orders/{campaign_id}
活动关联订单。

### GET /api/agent4/compare/{campaign_id}
目标 vs 实际对比。

### GET /api/agent4/review/{campaign_id} ⭐
**核心输出** — 复盘报告（背景、目标、结果、ROI、优化建议）。

---

## 系统

### GET /health
数据库连接与表列表。

### GET /
API 入口与快捷链接。
