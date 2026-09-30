"""Agent1 日历优先级与 AI 建议状态。"""

from __future__ import annotations

PREP_LEAD_MONTHS = 3  # 活动需提前 N 个月开始准备

PLAN_SOURCE_HUMAN = "human_calendar"
PLAN_SOURCE_AI = "ai_suggestion"
PLAN_SOURCE_MERGED = "merged"

SUGGESTION_PENDING = "pending"
SUGGESTION_APPROVED = "approved"
SUGGESTION_REJECTED = "rejected"
SUGGESTION_MERGED = "merged"

# 方案库 / 全年计划池
ADOPTION_PROPOSAL = "proposal"   # 方案库：飞书规划或 AI 建议，待运营师评审
ADOPTION_ADOPTED = "adopted"     # 已采纳，进入全年营销计划池
ADOPTION_REJECTED = "rejected"   # 已拒绝，不进入计划池

# 准备阶段标签
PHASE_URGENT_PREP = "urgent_prep"      # 距推广约3个月 → 现在就要开始配置测试
PHASE_IN_PREP = "in_prep"              # 距推广 <3个月 → 已在准备/执行窗口
PHASE_PLANNED = "planned"              # 距推广 >3个月 → 全年规划，暂不动
PHASE_PAST = "past"                    # 已过期
