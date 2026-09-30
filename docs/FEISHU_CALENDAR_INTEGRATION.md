# 飞书「2026营销日历」接入说明

## 你的表格

| 项目 | 值 |
|------|-----|
| Base URL | https://didatravel.feishu.cn/base/GpYkbnH9ga8nMAs0GUQcCXoInXe |
| App Token | `GpYkbnH9ga8nMAs0GUQcCXoInXe` |
| 主要视图 | **对内：旅游目的地营销日历**（按「推广月份」分组） |

## 能否接入？

**可以。** 飞书 Bitable Open API 支持读取该 Base 的记录。系统已实现 `FeishuMarketingCalendarClient`，字段映射如下：

| 飞书字段 | 系统字段 | 用途 |
|---------|---------|------|
| 月度推荐主题 | campaign_name | 活动名称 |
| 推广月份 | promotion_month | 月份分组 / 3个月窗口过滤 |
| 推广时间 | promotion_time | 推断 start_date（如 3月16日） |
| 目的地归属 | destination_region | 区域标签 |
| 地区 | regions | 具体国家/城市 |

## 系统调整（相对原设计）

1. **双 Base 分离**
   - **Agent1 读**：2026营销日历（规划输入）
   - **Agent4 写**：活动信息汇总（复盘输出，app_token 不变）

2. **Agent1 逻辑**
   - `build_three_month_calendar()` 从营销日历拉取，叠加行业情报 + 档案库参考，生成 enriched 方案

3. **Mock 兜底**
   - 未配置 API 凭证时使用 `data/feishu_marketing_calendar_mock.json`（内容与截图一致）

4. **新增 API**
   - `GET /api/v2/feishu/calendar/raw` — 原始日历（按月份分组）
   - `GET /api/v2/feishu/calendar/status` — 接入状态
   - `GET /api/v2/calendar?include_all=true` — 全量 enriched 日历

## 配置步骤

```powershell
# 1. 飞书开放平台创建企业自建应用，开通 bitable 权限
# 2. 将应用添加为 Base 协作者

$env:FEISHU_APP_ID = "cli_xxx"
$env:FEISHU_APP_SECRET = "xxx"

# 3. 获取 table_id
python scripts/feishu_list_tables.py

$env:FEISHU_MARKETING_CALENDAR_TABLE_ID = "tblXXX"
# 可选：限定「对内」视图
$env:FEISHU_MARKETING_CALENDAR_VIEW_ID = "vewXXX"

# 4. 启动 API
python -m app.main
```

## 界面预览

- **静态交互预览**：双击打开 `ui/preview.html`
- **Canvas 预览**：在 Cursor 中打开 `marketing-system-feishu-preview.canvas.tsx`
- **API 数据**：`http://localhost:8000/api/v2/feishu/calendar/raw`

## 注意事项

- 「shopping端一级Banner位」字段已预留映射，截图中多为空，不影响 Agent1 方案生成
- 对外视图、节假日表可后续扩展为 Agent1 的补充情报源
- 若飞书字段名与截图不完全一致，在 `MARKETING_CALENDAR_FIELD_MAP` 中补充别名即可
