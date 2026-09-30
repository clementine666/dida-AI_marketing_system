# 5-Agent 营销协作系统 — 逻辑对齐文档

## Agent 分工

| Agent | 定位 | 核心输出 |
|-------|------|---------|
| Agent1 | 方案策划师 | 未来3个月营销日历 + 完整活动方案草案 |
| Agent2 | 客户资源配置师 | 圈客清单 + 选品比价 + 上线待办清单 |
| Agent3 | 活动监控师 | 转化看板 + 实时告警 |
| Agent4 | 活动分析师 | 复盘报告（PRD 八章） |
| Agent5 | 活动归档师 | 结构化活动档案库 |

## 活动生命周期状态机

```
draft → plan_review → sent_to_agent2 → resource_config → todo_execution
  → testing → scheduled → live → monitoring → review → archived
```

## 飞书字段映射（活动信息汇总表）

| 飞书字段 | Agent |
|---------|-------|
| 活动名称、开始/结束时间 | Agent1 |
| 活动介绍/说明、具体活动方案 | Agent1→Agent2 |
| 活动规模（客户群体） | Agent2 |
| 活动目标、关键数据指标 | Agent2→Agent3 |
| 活动清单 | Agent2 |
| 复盘状态、活动总结报告、活动功能结论 | Agent4 |

## 人工闸门

1. Agent1 方案 → 营销师编辑 → **确认发送** → Agent2
2. Agent2 待办 → 营销师打钩 → **提交测试** → Agent3 准备
3. Agent3 看板 → 营销师 **预览确认** → 正式监控
4. Agent4 复盘 → 营销师 **验收** → Agent5 归档
