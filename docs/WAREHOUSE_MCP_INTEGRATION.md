# Agent2 数仓 MCP 接入说明

## 三张核心表

| 表名 | 用途 | Agent2 场景 |
|------|------|------------|
| `shopping.ods_amplitude_events` | 原始埋点 | 搜索行为、RP 价格（quote_price）、Banner 曝光点击 |
| `shopping.ods_amplitude_users` | 用户-客户关联 | user_id → client_id / client_group_id |
| `dwd.dwd_hotel_shopping_funnel_detail_d_f` | 酒店转化漏斗 | 圈客、选品、漏斗基线 |

埋点方案参考：**0.2 Shopping网站埋点**（飞书云文档）

## Agent2 数据流

```
营销日历(Agent1) → 目的地 dest
        ↓
┌───────────────────────────────────────────────────────┐
│  WarehouseClient                                      │
│  ├─ query_clients_by_destination   ← funnel + users   │
│  ├─ query_hotels_by_destination    ← funnel           │
│  ├─ query_hotel_prices             ← events (RP曝光)  │
│  ├─ query_search_insights          ← events (搜索)    │
│  └─ query_funnel_by_destination    ← funnel (基线)    │
└───────────────────────────────────────────────────────┘
        ↓
资源配置方案 + 待办清单（埋点/监控/优惠券/Banner）
```

## 接入方式

### 方式 A：MCP / SQL 网关（推荐生产）

设置环境变量后 Agent2 自动切换为数仓直查：

```powershell
$env:WAREHOUSE_MCP_ENDPOINT = "https://your-dw-mcp.internal/api"
$env:WAREHOUSE_MCP_SQL_PATH = "/query"          # 可选，默认 /query
$env:WAREHOUSE_MCP_API_KEY = "your-token"         # 可选

# 表名可覆盖（默认已是生产表名）
$env:WAREHOUSE_TABLE_EVENTS = "shopping.ods_amplitude_events"
$env:WAREHOUSE_TABLE_USERS = "shopping.ods_amplitude_users"
$env:WAREHOUSE_TABLE_FUNNEL = "dwd.dwd_hotel_shopping_funnel_detail_d_f"
```

MCP 接口约定（POST）：

```json
{
  "sql": "SELECT ... FROM shopping.ods_amplitude_events WHERE ...",
  "params": {}
}
```

返回：

```json
{ "rows": [ { "client_id": "...", "funnel_pv": 12 } ] }
```

健康检查：`GET /api/v2/warehouse/status`

### 方式 B：本地 SQLite fallback（当前默认）

未配置 MCP 时使用本地库（由 CSV/Excel 导入）：

```powershell
# 1. 从 Excel 导出 CSV
py -3.11 scripts/import_excel_sample.py

# 2. 导入 SQLite
py -3.11 scripts/import_data.py
```

## 关键埋点 event_type

| 业务 | event_type | event_properties_json 字段 |
|------|-----------|---------------------------|
| Banner 曝光 | primary_banner_expose | slide_id, category_name |
| Banner 点击 | primary_banner_click | slide_id |
| 搜索点击 | search_des_sugg_click | search_des_query, dida_hotel_id |
| RP 曝光 | hotel_detail_rp_expose | dida_hotel_id, quote_price, supplier_id |
| RP 点击 | hotel_detail_rp_click | dida_hotel_id, dida_rpid |
| 预订 | hotel_prebook | - |
| 支付成功 | hotel_order_success | - |

## funnel step_code

| step_code | 含义 |
|-----------|------|
| request | 酒店详情请求 |
| available | 有价返回 |
| expose | RP 曝光 |
| click | RP 点击 |
| prebook | 预订页 |
| success | 支付成功 |

## 你需要提供

1. **MCP 接口地址** 或 **SQL 网关 URL**（含鉴权方式）
2. 确认 SQL 方言（当前模板按 PostgreSQL / 数仓 JSONB 语法编写）
3. 若 MCP 协议与本文约定不同，提供接口文档，我可调整 `warehouse_mcp_adapter.py`

## 相关文件

- `app/mcp/warehouse_schema.py` — 表名 + SQL 模板
- `app/mcp/warehouse_mcp_adapter.py` — MCP HTTP 适配
- `app/mcp/warehouse_client.py` — 统一查询入口
- `app/services/v2/agent2_resource.py` — Agent2 调用
