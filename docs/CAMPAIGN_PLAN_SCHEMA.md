# 活动全套策划方案 — 字段结构（Schema v2 → 已升级 v3）

> **现行结构见 [`CAMPAIGN_DOC_V3.md`](./CAMPAIGN_DOC_V3.md)**。本文保留 v2 评审模块说明，供对照。
>
> 面向 B2B 酒店营销（portal.dida.com），供 Agent1 评审页展示、人工修改、确认后送 Agent2。
一套完整活动方案 = **10 个策划模块 + 1 个 AI 溯源模块**（仅 AI 建议时显示）。

---

## 总览：评审时看什么、改什么

| 模块 | 策划书对应章节 | 评审核心问题 |
|------|----------------|--------------|
| ① 活动来源 | 立项依据 | 这活动从哪来？时间对不对？ |
| ② 活动背景 | 背景说明 | 为什么在这个节点做？ |
| ③ 数据分析 | 立项论证 | **数据**是否证明值得做？ |
| ④ 活动目标 | 目标与预算 | 目标是否可量化、可验收？ |
| ⑤ 方案策划 | 创意与打法 | 怎么讲、怎么玩、怎么差异化？ |
| ⑥ 客户群体 | 圈客策略 | 圈谁？特性是什么？ |
| ⑦ 酒店解决方案 | 选品策略 | 用什么酒店满足这群客户？ |
| ⑧ 产品交付 | 触达与产品形态 | **优惠券还是纯展示**？渠道怎么组合？ |
| ⑨ 效果预估 | 价值评估 | 预期 TTV/ROI 是否合理？ |
| ⑩ 执行协作 | 项目计划 | 里程碑、Agent2 交接是否清晰？ |
| ⑪ AI 依据 | （仅 AI） | AI 为什么建议？是否采纳/合并？ |

---

## ① 活动来源与基本信息 `source` + `basic`

**回答：这个活动是谁提出的、什么时候做、优先级多高。**

| 字段 | 说明 | 示例 |
|------|------|------|
| `source.plan_source` | 来源类型 | `human_calendar` / `ai_intel` / `merged` |
| `source.source_detail` | 来源说明 | 「2026飞书日历·11月条目」 |
| `source.owner` | 负责人 | 张三 |
| `source.priority` | 优先级 | P0 / P1 / P2 |
| `basic.campaign_name` | 活动标题 | 双十一 Global Travel Day |
| `basic.promotion_month` | 推广月份 | 11月 |
| `basic.promotion_time` | 具体时段 | 11.1–11.15 |
| `basic.target_dest` | 目的地 | Japan |
| `basic.campaign_type` | 活动类型 | Banner / 专题页 / 组合活动 |

**评审动作**：改标题、调整推广月份、确认来源与优先级。

---

## ② 活动背景 `background`

**回答：市场大环境是什么、业务上为什么现在要启动。**

| 字段 | 说明 |
|------|------|
| `market_context` | 市场/行业/季节背景（如 F1 档期、红叶季、双十一大促） |
| `business_trigger` | 业务契机（库存压力、竞品动作、客户咨询增多） |
| `opportunity` | 机会判断（窗口期、供给优势） |
| `summary` | 背景摘要（一段话） |

**评审动作**：补充节点说明、校正机会判断是否夸大。

---

## ③ 数据分析 · 为什么要做 `data_insights`

**回答：用数据证明「值得做」，不是拍脑袋。**

| 字段 | 说明 | 数据来源建议 |
|------|------|--------------|
| `market_data` | 市场/目的地趋势 | 行业情报、公开数据 |
| `client_behavior_data` | 客户行为数据 | 数仓 MCP：搜索/浏览/下单 |
| `historical_reference` | 历史同类活动 | Agent5 案例库、往期复盘 |
| `competitive_landscape` | 竞争与供给环境 | 情报、比价 |
| `data_conclusion` | **数据结论（立项依据）** | 综合以上，一句话结论 |

**评审动作**：要求 Agent1/Agent2 补数据引用；结论与数据是否自洽。

---

## ④ 活动目标 `objectives`

**回答：做完要达成什么、花多少钱、怎样算成功。**

| 字段 | 说明 |
|------|------|
| `primary_goal` | 主目标（业务语言） |
| `target_metrics` | 量化指标（订单数、TTV、CTR…） |
| `secondary_goals` | 次要目标（品牌、拉新） |
| `success_criteria` | 成功标准 / 核心 KPI |
| `budget_cny` | 预算 |
| `roi_expectation` | ROI 预期 |

**评审动作**：指标是否 SMART；预算与⑨预估是否匹配。

---

## ⑤ 方案策划 `strategy`

**回答：活动怎么定位、主题是什么、核心玩法是什么。**

| 字段 | 说明 |
|------|------|
| `positioning` | 活动定位 |
| `theme` | 活动主题 / Slogan |
| `core_message` | 核心卖点 |
| `creative_direction` | 创意方向（视觉、文案调性） |
| `solution_summary` | 方案详述 |
| `differentiation` | 与竞品/往期差异 |
| `key_mechanics` | 关键机制（满减、限时、专题结构） |

**评审动作**：改主题、改玩法、对齐目标与客户群。

---

## ⑥ 目标客户群体 `customer_segment`

**回答：针对谁、他们有什么特性、为什么选这群人。**

| 字段 | 说明 |
|------|------|
| `segment_name` | 客群名称 |
| `description` | 客群描述 |
| `client_groups` | MCP 客户分组 ID |
| `behaviors` | 行为特征（近90天搜索/下单） |
| `pain_points` | 痛点与需求 |
| `geo_focus` | 地域/目的地偏好 |
| `size_estimate` | 预估规模 |
| `selection_rationale` | **圈选理由** |
| `query_profile` | **Agent2 执行 DSL**（见 `docs/AGENT_HANDOFF_CONTRACT.md`） |

**评审动作**：调整分组 ID、核对 `query_profile` 必填项；Agent2 将据此圈客。

---

## ⑦ 酒店产品解决方案 `hotel_solution`

**回答：用什么酒店供给匹配上述客群需求。**

| 字段 | 说明 |
|------|------|
| `selection_strategy` | 选品策略 |
| `star_min` | 最低星级 |
| `price_range` | 价格带 |
| `hotel_criteria` | 筛选条件（评分、商圈、库存） |
| `recommended_types` | 推荐酒店类型/ shortlist |
| `inventory_notes` | 库存与供给说明 |
| `price_competitiveness` | 比价与竞争力策略 |
| `supply_risk` | 供给风险 |
| `query_profile` | **Agent2 选品 DSL** |

**评审动作**：星级/价格带是否合理；核对 `query_profile.star_min` / `hotel_limit`。

---

## ⑧ 产品交付方式 `product_delivery`

**回答：产品以什么形式触达客户——这是您关心的核心之一。**

| 字段 | 说明 |
|------|------|
| `delivery_type` | `display_only` 纯展示 / `coupon` 优惠券 / `mixed` 组合 / `sms_push` / `bundle` |
| `delivery_type_label` | 中文说明 |
| `coupon_strategy` | 优惠券力度、门槛、有效期 |
| `display_strategy` | Banner/专区/推荐位策略 |
| `channels` | 触达渠道组合 |
| `landing_experience` | 落地页/专区体验 |
| `execution_steps` | 配置与上线步骤 |
| `cost_control` | 成本控制（补贴上限等） |

**评审动作**：选「纯展示」还是「发券」；渠道与成本是否可控。

---

## ⑨ 效果预估与业务价值 `forecast`

**回答：预期做到什么量级、业务价值是否大于投入。**

| 字段 | 说明 |
|------|------|
| `expected_exposure` | 预估曝光 |
| `expected_clicks` | 预估点击 |
| `expected_orders` | 预估订单 |
| `expected_ttv` | 预估 TTV |
| `expected_gp` | 预估 GP |
| `expected_roi` | 预估 ROI |
| `value_proposition` | 业务价值说明 |
| `risk_assessment` | 风险与应对 |

**评审动作**：预估是否有③数据支撑；与④目标、④预算交叉验证。

---

## ⑩ 执行计划与协作 `execution`

**回答：谁什么时候做什么、交给 Agent2 什么条件。**

| 字段 | 说明 |
|------|------|
| `timeline_milestones` | 里程碑时间表 |
| `prep_lead_notes` | 提前准备说明（默认提前3个月） |
| `dependencies` | 依赖项（设计、法务、库存） |
| `agent2_handoff` | **Agent2 交接说明**（圈客/选品/比价条件） |
| `monitoring_focus` | Agent3 监控重点 |
| `review_checklist` | 评审检查清单 |

**评审动作**：确认可执行性；完善 Agent2 交接字段。

---

## ⑪ AI 建议依据 `ai_provenance`（仅 AI 建议）

| 字段 | 说明 |
|------|------|
| `ai_rationale` | AI 为什么建议此活动 |
| `intel_source` | 行业情报来源 |
| `similar_calendar_name` | 可合并的相似日历活动 |
| `confidence` | 建议置信度 |

---

## 模块依赖关系（策划逻辑链）

```
来源 → 背景 → 数据分析 → 目标
              ↓
         方案策划 ←→ 客户群体 ←→ 酒店解决方案
              ↓
         产品交付方式
              ↓
         效果预估 ← 验证目标/预算
              ↓
         执行计划 → Agent2
```

---

## 技术说明

- **Schema 版本**：`schema_version: 2`
- **存储**：`dim_campaign.plan_structured_json`（完整 JSON）
- **兼容**：v1 扁平字段自动映射到 v2 模块
- **代码**：`app/models/campaign_plan_schema.py`
- **评审 UI**：Agent1 侧滑页 10+1 模块，左侧目录跳转
