# 5-Agent v2 API 文档

Base URL: `http://localhost:8000/api/v2`

## Agent1 方案策划师

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/calendar?months=3` | 未来3个月营销日历 |
| GET | `/activities/{campaign_id}` | 活动方案详情 |
| PATCH | `/activities/{campaign_id}/plan` | 营销师编辑方案 |
| POST | `/activities/{campaign_id}/send-to-agent2` | 确认发送 Agent2 |

## Agent2 客户资源配置师

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/activities/{campaign_id}/configure` | 圈客+选品+待办 |
| GET | `/activities/{campaign_id}/todos` | 待办清单 |
| POST | `/todos/{todo_id}/complete` | 完成待办 |
| POST | `/activities/{campaign_id}/submit-test` | 提交测试 |
| POST | `/activities/{campaign_id}/approve-test` | 测试通过 |

## Agent3 活动监控师

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/activities/{campaign_id}/monitor/preview` | 看板预览 |
| POST | `/activities/{campaign_id}/monitor/confirm` | 确认监控 |

## Agent4 活动分析师

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/activities/{campaign_id}/review` | 复盘报告 |
| POST | `/activities/{campaign_id}/review/confirm` | 验收复盘 |

## Agent5 活动归档师

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/activities/{campaign_id}/archive` | 完结归档 |
| GET | `/archives?destination=Singapore` | 档案库检索 |

## 编排

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/pipeline/{campaign_id}/run` | 端到端流水线 |
| GET | `/lifecycle/{campaign_id}` | 当前生命周期状态 |
