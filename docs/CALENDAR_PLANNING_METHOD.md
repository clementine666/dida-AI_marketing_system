# 标准活动规划 · 自动日历方法（学习测试版）

> 来源：飞书「2027年营销日历-初版」全表学习 + `scripts/calendar_planning_test.py` 实测  
> 测试报告：[`data/feishu_import/calendar_test_output/CALENDAR_PLANNING_TEST_REPORT.md`](../data/feishu_import/calendar_test_output/CALENDAR_PLANNING_TEST_REPORT.md)

---

## 1. 目标

点击 **「标准活动规划」** 后，系统自动：

1. MCP 拉取离店/预订/P75 数据  
2. 按 A/B/C 逻辑分析  
3. 叠加 v4 业务规则（可选阶段）  
4. 输出与「27年营销日历初版」同结构的表格 + 证据列  
5. 送入 **初版评审池**，与 AI 创意版并列审核  

---

## 2. 数据输入（MCP Query Profiles）

| Profile | 飞书子表 | 粒度 | 用途 |
|---|---|---|---|
| `checkout_monthly` | 离店数据 | 月 × 国家 | 原始 TTV/订单，聚合到洲二 |
| `booking_monthly` | 预订数据 | 月 × 国家 | 辅助验证需求 |
| `checkout_ttv_share` | 离店TTV及占比 | 洲/洲二 × 月 | 可直接用或自算占比 |
| `lead_time_p75` | 提前预订P75 | 洲/洲二 × 月 + 全年 | C 步最迟上线 |
| `continent_l2_mapping` | 离店数据列 E | 固定配置 | 国家→洲二映射 |

**固定配置**：[`data/feishu_import/continent_l2_mapping.json`](../data/feishu_import/continent_l2_mapping.json)

---

## 3. 分析方法（三层）

### Layer 1 · 数据层 A/B/C（可高度自动化 ✅）

```
FOR each 归属洲:
  A) TOP5 分析单元（洲二或单独国家）by 全年离店TTV
  FOR each 单元:
    B) TOP3 离店高峰月 by 月TTV占比（阈值≥6%）
    C) 取目标月的 月度P75（不用全年均值）
    生成 evidence 句：「{月}{单元}离店TTV=X.XM，占全年Y.Y%；P75=Z天」
```

**P75 组合场**（人工 v4 规则）：

```
P75(组合, 月) = Σ(成员月TTV × 成员月P75) / Σ(成员月TTV)
例：新马泰春节场 = 新/马/泰 按离店TTV加权 → 48 天（非泰国单独 56）
```

### Layer 2 · 规则层（半自动 ⚠️，需 `manual_plan_sop.yaml`）

来自「27年营销日历逻辑」v4，系统下一版实现：

| 规则 | 说明 |
|---|---|
| 46 场 / 周二 1 场 | 约束求解排期 |
| 业务底稿目的地 | 标色行不删，只重算时间链 |
| 同单元间隔 ≥6 周 | 反疲劳 |
| 日本/美加拆城市线 | 1 单元 → 多场不同副主题 |
| 合并场 | 新马泰、全欧洲、泰马越印等 |
| zihuai 入境 4 场 | 刚性插入，取中国当月 P75 |
| T-30 / T-14 / 工作日 | 算 H–P 列 |

### Layer 3 · 表达层（LLM 辅助 ⚠️）

| 列 | 自动化 |
|---|---|
| A 活动场次 | 规则层按上线月分组 |
| B 月度主主题 | LLM + 节庆表 |
| C 副活动主题 | LLM 或模板 `{单元}·{节庆/旺季}` |
| D 覆盖目的地 | 底稿 + 国家列表 |
| E 离店窗口 | B 步输出 |
| F 关键 P75 | C 步输出 |
| G 数据依据 | **100% 自动生成** |

---

## 4. 实测结果（vs 人工初版 42 场出境）

| 指标 | 结果 |
|---|---|
| 系统候选条数 | 117（每单元×TOP3月） |
| 单元+月份强匹配 | **15/42（35.7%）** |
| 单元匹配但月份不同 | 27 |
| P75 差 ≤3 天 | **6 场** |
| P75 典型一致 | 澳新春节 71.3≈71、北欧7月 60.2≈60、西欧7月 38.9≈39 |

**结论**：

- **数据层 A/B/C 已被验证可行**，与人工峰值月、P75 高度吻合  
- **35.7% 强匹配** 偏低，主因是人工做了 **合并/拆分/多场次**（非数据算错）  
- 例如「新马泰过年」人工用加权 P75=48，系统单测泰国 P75=56 — 需 Layer 2 组合规则  

---

## 5. 与人工差异清单（系统下一版要补）

| 差异 | 人工做法 | 系统 v1 | 系统 v2 修复 |
|---|---|---|---|
| 新马泰合并 | 加权 P75 | 单国泰国 | 组合加权函数 |
| 日本 5 场 | 拆城市季节线 | 1 条候选 | 规则：高热单元多场 |
| 全欧洲 | 按 TTV 加权 P75 | 西欧/南欧分开 | 组合 + 排期合并 |
| 46 场周二 | 完整排程 | 未做 | 约束求解引擎 |
| 主题命名 | 专业文案 | 模板 | LLM + 节庆表 |
| 入境 4 场 | zihuai 刚性 | 未做 | 展会配置表 |

---

## 6. Skill 接口设计（供 `manual_calendar_skill`）

### API

```
POST /api/v2/agent1/manual-calendar/generate
{
  "data_window": {"start": "2025-08", "end": "2026-07"},
  "top_units_per_continent": 5,
  "top_months_per_unit": 3,
  "min_month_share": 0.06,
  "apply_scheduling_rules": false,  // v2: true → 46场周二
  "include_inbound": false
}
```

### Response

```json
{
  "summary": {"candidates": 117, "continents": 8},
  "candidates": [
    {
      "analysis_unit": "澳新",
      "continent": "大洋洲",
      "target_checkout_month": "2026-02",
      "month_ttv": 19400000,
      "month_share": 0.239,
      "p75_days": 71.3,
      "evidence": "2026年02月澳新离店TTV=19.4M，占全年23.9%…",
      "countries": ["澳大利亚", "新西兰"]
    }
  ],
  "draft_rows": [ "…同初版表 A-G 列…" ]
}
```

### 前端（Agent1 · 标准活动规划 Tab）

1. 检测 MCP 连接  
2. 参数表单（数据窗、TOP N）  
3. **「生成标准活动规划」** 按钮  
4. 三 Tab：数据摘要 / 分析明细 / 日历初版（可编辑）  
5. **「送入初版评审池」**  

---

## 7. 复现测试

```bash
py -3.11 scripts/calendar_planning_test.py
```

产出：

| 文件 | 说明 |
|---|---|
| `calendar_test_output/system_candidates.json` | 全部候选 |
| `calendar_test_output/system_draft_v1.csv` | 系统版初版（每单元 1 条峰值） |
| `calendar_test_output/comparison_report.json` | 与人工对比明细 |
| `calendar_test_output/CALENDAR_PLANNING_TEST_REPORT.md` | 测试报告 |

---

## 8. 实施路线

| 阶段 | 范围 | 预期匹配率 |
|---|---|---|
| **P0（当前）** | MCP 拉数 + A/B/C + 证据 + 初版 CSV | 数据层验证 ✅ |
| **P1** | 组合 P75 + 底稿目的地 + 送评审池 | ~50% |
| **P2** | 46 场周二 + T-30/T-14 + 主题 LLM | ~80% |
| **P3** | 与 AI 创意版同池对比 + 人改后归档 | 生产可用 |
