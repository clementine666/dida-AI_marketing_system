# Agent1 方案评审流程（人工闸门）

## 场景目标

营销师在 Agent1 工作台中，**不能直接从列表一键「送 Agent2」**，而必须先进入**结构化方案评审页**，查看/修改完整策划内容，确认无误后再回到主界面推送 Agent2。

AI 行业情报建议同样走评审：需展示 **AI 为什么建议**、可编辑方案、选择 **推广月份** 后 **采纳入日历**。

---

## 用户旅程

### A. 人工日历活动（准备队列 / 全年日历）

```
列表「评审方案」→ 侧滑评审页 → 编辑结构化字段 → 保存
→ 「确认评审完成」→ 回到列表（标记「已评审」）→ 「送 Agent2」
```

| 步骤 | 操作 | 系统行为 |
|------|------|----------|
| 1 | 点击「评审方案」 | `GET /api/v2/activities/{id}/plan-structured` |
| 2 | 修改标题、背景、客群、酒店画像、目标、交付方式 | 本地表单编辑 |
| 3 | 保存修改 | `PUT /api/v2/activities/{id}/plan-structured` |
| 4 | 确认评审完成 | `POST /api/v2/activities/{id}/confirm-plan-review` → `plan_review_confirmed_at` |
| 5 | 送 Agent2 | `POST /api/v2/activities/{id}/send-to-agent2`（未评审则拒绝） |

### B. AI 建议待审

```
列表「评审方案」→ 侧滑页（含 AI 依据区块）→ 编辑 + 选推广月份
→ 「采纳并入日历」 或 「拒绝」
```

| 步骤 | 操作 | 系统行为 |
|------|------|----------|
| 1 | 评审方案 | `GET /api/v2/suggestions/{id}/plan-structured` |
| 2 | 查看 AI 依据 / 情报来源 | `ai_rationale` + `intel_source` |
| 3 | 保存草稿（可选） | `PUT /api/v2/suggestions/{id}/plan-structured` |
| 4 | 采纳并入日历 | `POST /api/v2/suggestions/{id}/review` + `structured_plan` + `promotion_month` → 新建 `dim_campaign` 且自动标记已评审 |

---

## 结构化方案字段（Schema v2）

完整字段定义见 **[CAMPAIGN_PLAN_SCHEMA.md](./CAMPAIGN_PLAN_SCHEMA.md)**。

十一个大模块：`source/basic` · `background` · `data_insights` · `objectives` · `strategy` · `customer_segment` · `hotel_solution` · `product_delivery` · `forecast` · `execution` · `ai_provenance`（AI 专用）。

```json
{
  "schema_version": 2,
  "source": { "plan_source": "human_calendar", "owner": "营销师", "priority": "P1" },
  "basic": { "campaign_name": "…", "promotion_month": "11月", "target_dest": "Japan" },
  "background": { "market_context": "…", "business_trigger": "…" },
  "data_insights": { "data_conclusion": "为什么要做（数据结论）" },
  "objectives": { "target_metrics": "订单数、TTV", "budget_cny": "50000" },
  "strategy": { "theme": "…", "solution_summary": "方案详述" },
  "customer_segment": { "description": "…", "client_groups": "2,6,11" },
  "hotel_solution": { "selection_strategy": "…", "star_min": "4" },
  "product_delivery": { "delivery_type": "mixed", "coupon_strategy": "…", "display_strategy": "…" },
  "forecast": { "expected_ttv": "…", "expected_roi": "…" },
  "execution": { "agent2_handoff": "圈客选品条件…" },
  "ai_provenance": { "ai_rationale": "…", "intel_source": "…" }
}
```

持久化：`dim_campaign.plan_structured_json` + 同步扁平行（`plan_summary`、`target_audience` 等）供 Agent2 使用。

---

## 状态机

```
draft
  ↓ 营销师打开评审并保存
plan_review（编辑中，plan_review_confirmed_at 为空）
  ↓ 确认评审完成
plan_review（已确认，plan_review_confirmed_at 有值）
  ↓ 送 Agent2
sent_to_agent2 → resource_config → ...
```

**闸门规则**：`send-to-agent2` 必须 `plan_review_confirmed_at IS NOT NULL`。

---

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/activities/{id}/plan-structured` | 获取人工活动结构化方案 |
| PUT | `/api/v2/activities/{id}/plan-structured` | 保存方案 |
| POST | `/api/v2/activities/{id}/confirm-plan-review` | 确认评审 |
| GET | `/api/v2/suggestions/{id}/plan-structured` | 获取 AI 建议方案 |
| PUT | `/api/v2/suggestions/{id}/plan-structured` | 保存 AI 建议草稿 |
| POST | `/api/v2/suggestions/{id}/review` | 采纳/拒绝（采纳带 structured_plan + promotion_month） |
| POST | `/api/v2/activities/{id}/send-to-agent2` | 推送 Agent2（需已评审） |

---

## UI 布局（工作台）

- **主列表**：操作列 = `评审方案` + `送 Agent2`（未评审时禁用）
- **侧滑评审页**（720px）：分区展示 — AI 依据（如有）/ 基本信息 / 需求方案 / 客群 / 酒店画像 / 目标与交付
- **AI 建议列表**：`评审方案` + `拒绝`（采纳在评审页内完成）

---

## 与 Agent2 衔接

评审确认后的结构化字段会写入：

- `target_audience` ← 客群描述 + 分组
- `target_metrics` ← 目标指标
- `execution_steps` ← 交付执行步骤
- `plan_structured_json` ← 完整 JSON（Agent2 可扩展读取 `customer_segment` / `hotel_profile` 调 MCP）

---

## 后续可扩展

1. 评审历史版本：`fact_activity_snapshot` 已记录每次保存
2. 多人协作：评审人、评论线程
3. 与飞书日历双向同步推广月份
4. LLM 自动生成 `ai_rationale` 长文解释
