# Agent1 行业情报工作流（OpenClaw 式）

## 流程

```
配置采集任务 (intel_tasks.yaml / 行业情报页)
    ↓
定时或手动：运行采集 / 上传报告 → fact_industry_intel
    ↓
LLM 汇总 (collection_prompt + 情报全文) → fact_ai_suggestions
    ↓
Agent1 评审方案 → 采纳并入日历 / 拒绝
    ↓
人工活动评审 → 送 Agent2
```

## 配置位置

| 内容 | 位置 |
|------|------|
| 采集任务列表 | 侧边栏 **行业情报** 页，或 `config/intel_tasks.yaml` |
| LLM 汇总 Prompt | 行业情报页 / Agent1 **提示词·功能配置** → `intel_collection_prompt` |
| AI 模型 Key | **MCP 数据配置** → AI 模型（Qwen / DeepSeek） |
| 定时执行 | Windows 任务计划运行 `py -3.11 scripts/industry_intel_collector.py` |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v2/intel/tasks` | 任务列表 |
| PUT | `/api/v2/intel/tasks` | 保存任务 |
| POST | `/api/v2/intel/tasks/run` | 立即采集（占位） |
| POST | `/api/v2/intel/reports/upload` | 粘贴文本上传 |
| POST | `/api/v2/intel/reports/upload-file` | 文件上传 |
| POST | `/api/v2/intel/generate-suggestions` | LLM 生成 AI 建议 |

## 定时任务示例（每周一 9:00）

```powershell
cd "...\multi-agent-marketing-system"
py -3.11 scripts/industry_intel_collector.py
# 若已配置 LLM Key，脚本末尾可调用 generate-suggestions
```

## 与 OpenClaw 的对应

| OpenClaw | 本系统 |
|----------|--------|
| 给 Agent 一个定时任务 | `intel_tasks.yaml` + 计划任务 |
| 指定网站抓什么 | `source_url` + `scrape_instruction` |
| 上传参考材料 | 行业情报页上传 / `data/intel_uploads/` |
| 输出结构化结果 | LLM → `fact_ai_suggestions` |
| 人工确认 | Agent1 评审页 |

## 待扩展

- 真实 URL 爬虫（Playwright / RSS）
- PDF 解析
- 飞书文档同步为情报源
