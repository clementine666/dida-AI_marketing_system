# 系统模块骨架 · 建设策略

> **原则**：先留流程、模块、功能入口；细节 I/O / 判断机制等 Jim 提供后再实现。  
> **SOP 来源**：画板六阶段 · `docs/SOP_V2_WHITEBOARD_FLOW.md`

---

## 1. 三层结构

```
画板 SOP（六阶段）
    ↓
6 Agent 工作台（UI 页签）
    ↓
功能模块（config/modules.yaml）+ 占位配置（config/prompts/）
```

| 层级 | 文件/入口 | 说明 |
|---|---|---|
| 模块注册 | `config/modules.yaml` | 每个功能的 id、阶段、状态、负责人、UI 入口 |
| 占位内容 | `config/prompts/*.yaml` | 提示词/模板/字段规范 · 先空着 |
| 系统管理 API | `/api/v2/admin/*` | 模块总览、日志、占位 CRUD |
| 系统管理 UI | 侧栏「系统管理」 | 模块总览 · 运行日志 · 占位配置 |

---

## 2. 模块状态

| 状态 | 含义 |
|---|---|
| `skeleton` | 入口/UI/API 骨架已有，逻辑未实现 |
| `placeholder` | 等业务方填内容（永如/Jim/曼薇等） |
| `ready` | 内容已填或主路径可跑 |

---

## 3. 占位配置清单（待填入）

| key | 标题 | 负责人 |
|---|---|---|
| `ai_creative` | AI 创意活动提示词 | 永如 |
| `manual_plan_sop` | 人工规划全年日历 SOP | Jim |
| `task_templates` | 任务配置模板 | Jim + Rachel |
| `launch_checklist` | 预上线审核 Checklist | Jim |
| `monitor_fields` | 监控字段维度 | 曼薇 |
| `review_template` | 下线复盘模板 | Jim |
| `archive_field_spec` | 建档 vs 评审字段对照 | Jim |

填入方式：工作台 → **系统管理 → 占位配置**，或编辑 `config/prompts/<key>.yaml`。

---

## 4. 系统管理 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v2/admin/modules` | 按阶段分组的模块树 |
| GET | `/api/v2/admin/logs` | 运行日志 |
| GET/PUT | `/api/v2/admin/prompts/{key}` | 读/写占位配置 |
| POST | `/api/v2/admin/logs/test` | 日志通路测试 |

日志表：`system_logs`（SQLite，启动时自动建表）。

---

## 5. 六阶段 ↔ Agent ↔ 主要模块

| 阶段 | Agent | 骨架模块（节选） |
|---|---|---|
| 1 策划与评审 | 营销策划 | 评审池、AI 提示词占位、终版日历 |
| 2 建档与任务创建 | 方案策划 | 建档、看板、档案模板占位 |
| 3 任务进展 | 任务监督 | 任务配置占位、催办、验收 |
| 4 预上线审核 | 上线审核 | T-1 提醒、Checklist 占位 |
| 5 监控与推送 | 监控优化 | 看板、T+1 总结、复盘模板占位 |
| 6 档案库 | 复盘归档 | 知识沉淀、知识库问答 |
| 系统 | 系统管理 | 日志、连接配置、模块注册 |

---

## 6. 后续（Jim 细节到位后）

1. 占位 `ready` → 接入各 Agent Service 读取 `prompt_store`
2. 模块 `skeleton` → 实现具体 I/O、闸门、自动化规则
3. 业务操作写入 `system_log.log()` 便于运维排查
