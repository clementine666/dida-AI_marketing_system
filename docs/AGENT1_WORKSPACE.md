# Agent1 营销工作台逻辑

## 两类活动来源

| 来源 | 说明 | 是否自动执行 |
|------|------|-------------|
| **人工营销日历**（飞书） | 营销团队全年规划 | 进入准备队列后由营销师确认 → Agent2 |
| **AI 活动建议**（行业情报） | Agent1 分析情报生成 | **需营销师审核**，采纳后才入池/合并 |

## 读取范围

- 飞书有全年规划 → **读全年**（`human_calendar.full_year`）
- 不再只截断 3 个月

## 提前 3 个月准备

活动需提前 **3 个月** 开始准备（测试、配置 Banner/埋点/圈客等）。

| prep_phase | 含义 | 示例（今天 8 月） |
|------------|------|------------------|
| `urgent_prep` | 距推广约 3 个月 → **现在就要开始** | 11 月活动 |
| `in_prep` | 距推广 <3 个月 → 已在准备/执行窗口 | 9–10 月活动 |
| `planned` | 距推广 >3 个月 → 全年规划，暂不动 | 12 月及以后 |
| `past` | 已过期 | 3–7 月活动 |

**准备队列** = `urgent_prep` + `in_prep`（最高优先级，应送 Agent2 配置测试）

## AI 建议审核流

```
行业情报收集 → Agent1 生成 AI 建议 (pending)
                    ↓
              营销师审阅
           ┌────────┼────────┐
        reject    approve    merge
           ↓         ↓         ↓
         丢弃    入活动池   合并到类似人工日历项
                  (draft)   (plan_source=merged)
```

- **approve**：新建 draft 活动，进入「营销活动日历池」，等待营销师完善后送 Agent2
- **merge**：将 AI 建议内容合并到现有人工日历活动（如 AI 建议「新加坡赛事酒店」合并到「新加坡F1」）
- **reject**：标记拒绝，不进入日历

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/workspace` | 全年日历 + 准备队列 + AI建议 |
| GET | `/api/v2/calendar` | 兼容旧接口，返回准备队列活动 |
| GET | `/api/v2/suggestions` | AI 建议列表 |
| POST | `/api/v2/suggestions/{id}/review` | 审核 `{action, merge_with_campaign_id?}` |

## 人工闸门

1. AI 建议 → 营销师 approve/merge/reject
2. 准备队列活动 → 营销师确认方案 → send-to-agent2
3. Agent2 待办 → 营销师逐项完成
