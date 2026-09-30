# Agent1 → Agent2 交接契约（Query Profile DSL）

本文定义 **最稳定** 的 Agent1→Agent2 协同方式：结构化 Query Profile 为主，人工兜底为辅。

## 原则

| 层级 | 内容 | 用途 |
|------|------|------|
| L1 结构化 | `query_profile` | Agent2 确定性调 MCP |
| L2 自然语言 | `behaviors`、`selection_rationale` | 运营师评审「为什么」 |
| L3 人工兜底 | 改条件重查 / 上传 ID | 最终控制权在运营师 |

**不要**让 Agent2 仅从自然语言猜 SQL；**不要**让 Agent1 写原始 SQL。

## Agent1 必填（送 Agent2 前 checklist）

### ⑥ 客户群体 `customer_segment.query_profile`

| 字段 | 必填 | 示例 |
|------|------|------|
| `destination` | ✓ | `Singapore` |
| `time_window_days` | ✓ | `90` |
| `client_group_ids` | ✓ | `[2, 6, 11]` |
| `behavior_source` | ✓ | `funnel` |
| `step_codes` | ✓ | `["request", "click"]` |
| `client_limit` | ✓ | `200` |

同步填写（给人看）：`selection_rationale`（引用 ③ 数据结论）

### ⑦ 酒店解决方案 `hotel_solution.query_profile`

| 字段 | 必填 | 示例 |
|------|------|------|
| `destination` | ✓ | `Singapore` |
| `star_min` | ✓ | `4` |
| `hotel_limit` | ✓ | `20` |
| `sort_by` | 建议 | `click_cnt_desc` |
| `keyword_boost` | 可选 | `["Marina", "Bay"]` |

## Agent2 工作流

```
读取 plan_structured_json ⑥⑦ query_profile
    ↓
POST /api/v2/activities/{id}/configure  （可带覆盖条件）
    ↓
运营师验收：预览 client/hotel 列表
    ↓
不满意 → POST profile-query 改条件重查 → 再 configure
    ↓
仍不满意 → POST resource-override 上传 client/hotel ID
    ↓
POST confirm-resources 锁定 → 生成待办
    ↓
待办完成 → POST submit-test
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/activities/{id}/query-profile` | 从方案提取 Query Profile + 校验缺项 |
| POST | `/api/v2/activities/{id}/profile-query` | 预览 MCP（不改库） |
| POST | `/api/v2/activities/{id}/configure` | 执行圈客选品，写入 resource_plan_json |
| POST | `/api/v2/activities/{id}/resource-override` | 人工 ID 覆盖/追加 |
| POST | `/api/v2/activities/{id}/confirm-resources` | 锁定资源配置，生成待办 |
| GET | `/api/v2/activities/{id}/resource-plan` | 读取当前资源配置 |

### resource-override 请求体

```json
{
  "mode": "mixed",
  "target_client_ids": ["c_5382", "c_8821"],
  "target_hotel_ids": ["12345"],
  "override_reason": "补入战略大客户"
}
```

- `mixed`：追加到 AI 结果
- `manual_ids`：完全替换为手动列表

## 代码位置

- DSL 定义与提取：`app/models/query_profile.py`
- Schema 默认字段：`app/models/campaign_plan_schema.py` ⑥⑦
- Agent2 执行：`app/services/v2/agent2_resource.py`
- MCP 查询：`app/mcp/warehouse_client.py` → `query_by_profile()`

## 校验

`validate_query_profile()` 返回缺项列表。缺 `client_group_ids` 等字段时 UI 会提示，运营师可在 Agent2 页面临时补全后查询，但 **正式流程应在 Agent1 评审时填好**。
