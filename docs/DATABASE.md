# 数据库设计文档

## 架构分层

```
原始数据层 → 事实/维度层 → Agent 服务层
ods_amplitude_* / dwd_funnel / channelbooking
    ↓ ETL
dim_client, fact_events, fact_funnel, fact_orders, ...
    ↓ 聚合
fact_search, fact_session, fact_campaign_metrics
    ↓ API
Agent 1 / 2 / 3 / 4
```

## 表关系

- `dim_client.client_id` ← `fact_events.client_id` ← `fact_orders.client_id`
- `dim_hotel.standard_hotel_id` ← `fact_funnel.standard_hotel_id`
- `dim_campaign.campaign_id` → `fact_campaign_metrics`, `fact_monitor`, `dim_alert_rules`
- `fact_orders.campaign_id` → `dim_campaign.campaign_id`（活动归因）

## event_properties_json 解析

导入时从 JSON 提取 60+ 关键字段到 `fact_events` 独立列，原始 JSON 保留在 `event_properties_json` 列。

## 标签体系（Phase 5 可扩展）

**客户标签**（ETL 自动计算初版）：
- tag_customer_value: 基于订单金额
- tag_activity_level: 基于 last_active_date
- tag_preferred_dest: 基于 fact_search 聚合
- tag_churn_risk: 基于活跃度

**酒店标签**（ETL 自动计算初版）：
- tag_popularity: 基于漏斗曝光量

## PostgreSQL 切换

修改 `config.yaml`:

```yaml
database:
  type: postgresql
  postgresql_url: postgresql://user:pass@localhost:5432/marketing
```

注意：schema.sql 中 `AUTOINCREMENT` 需改为 `SERIAL`（PostgreSQL）。

## 索引策略

- 高频查询：`user_id`, `client_id`, `event_type`, `event_date`, `country_name`
- 活动监控：`campaign_id`, `metric_date`
- 搜索分析：`search_des_query`, `country_name`

完整 DDL 见 `database/schema.sql`。
