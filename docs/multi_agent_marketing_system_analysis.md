# 多Agent营销协作系统 - 数据需求完整分析

**创建时间**: 2026-08-11  
**分析人**: 暴躁龙 🐉  
**输入**: Shopping网站埋点Excel(1万条样本) + 项目OKR文档 + 网站截图

---

## 一、我对项目的理解

### 1.1 你的核心诉求

你要建一个**本地数据库**，让 4 个 Agent + 1 个运营师能自动化完成营销全流程：

```
Agent 1（数据分析）→ Agent 2（资源匹配）→ Agent 3（方案策划+监控）→ Agent 4（效果复盘）
         ↑                                                              ↓
         └────────────── 运营师（定义规则、监督、处理异常）←──────────────┘
```

**关键问题**：你不知道这个本地数据库到底需要哪些字段，才能支撑 4 个 Agent 各自的工作。

### 1.2 人工做这件事的完整逻辑链

```
① 分析客户业务目的地需求
② 分析客户画像、历史订单画像、客户标签
③ 分析客户在网站的历史行为习惯
④ 结合旅游行业全球目的地重大活动/节假日/目的地特色
→ 输出：哪些客户有哪些需求

⑤ 分析产品数据（酒店资源、功能使用情况）
⑥ 匹配什么产品和功能能满足这些需求
→ 输出：策划活动方案 + 功能优化方案

⑦ 上线活动/功能
⑧ 做数据监控（目标是否达成）
 定期生成监控报告
⑩ 项目复盘（背景+客户+产品+目标+过程+结果+结论）
```

### 1.3 你的网站现状（从截图+数据看到）

- **首页搜索页**：目的地搜索 + 日期选择 + 入住人数
- **热门酒店小助手**：8个国家/地区每日更新热销酒店（墨西哥/新加坡/马来西亚/泰国/印尼/中国香港/阿联酋/韩国）
- **营销活动Banner**：新加坡F1赛事酒店预订、马来西亚独立69周年大促销等
- **大家都在看**：DIDA签约酒店直供、沙特夏日之旅、港澳专属促销、Sunway居旅、Yas主题乐园等 15+ 活动标签
- **选品集市**：高销酒店、优势酒店下载清单

---

## 二、现有数据完整总结

### 2.1 数据来源总览

| 数据源 | 表名 | 记录数 | 核心内容 |
|--------|------|--------|---------|
| **用户行为事件** | ods_amplitude_events | 10,000 | 用户在网站上的每一个操作（点击、曝光、搜索、下单等） |
| **用户基础信息** | ods_amplitude_users | 10,000 | 用户ID、设备ID、关联的客户机构(client_id) |
| **酒店购物漏斗** | dwd_hotel_shopping_funnel_detai | 10,000 | 从酒店详情请求→RP曝光→RP点击→下单→支付的完整漏斗 |
| **订单数据** | booking.channelbooking_v2 (伽利略) | - | 实际订单、价格、间夜数、TTV、GP |

### 2.2 用户行为事件表 (ods_amplitude_events) - 45个字段

#### A. 事件基础信息（12个字段）

| 字段 | 含义 | 用途 |
|------|------|------|
| pre_event_pk | 事件唯一ID（主键） | 去重、追踪 |
| event_time | 事件发生时间 | 时间分析 |
| server_time | 服务器接收时间 | 延迟分析 |
| event_date | 事件日期 | 日维度分析 |
| event_month | 事件月份 | 月维度分析 |
| event_hour | 事件小时 | 时段分析 |
| event_type | **事件类型（114种）** | **核心分析维度** |
| insert_id | 插入ID | 去重 |
| event_id | 事件ID | 事件分类 |
| created_at | 创建时间 | 数据入库时间 |
| updated_at | 更新时间 | 数据更新时间 |
| src_kafka_time | Kafka消息时间 | 数据延迟监控 |

#### B. 用户/设备标识（6个字段）

| 字段 | 含义 | 用途 |
|------|------|------|
| user_id | 用户ID（803个唯一值） | 用户行为追踪 |
| device_id | 设备ID（927个唯一值） | 设备维度分析 |
| identity_id | 统一身份标识 | 跨设备用户识别 |
| gaid | Google广告ID | 广告归因 |
| session_id | 会话ID | 会话分析 |
| search_session_id | 搜索会话ID | 搜索行为追踪 |

#### C. 页面信息（4个字段）

| 字段 | 含义 | 用途 |
|------|------|------|
| page_url | 当前页面URL | 页面分析 |
| page_name | **页面名称（48种）** | **页面维度分析** |
| referrer_url | 来源页面URL | 流量来源分析 |
| referrer_page_name | 来源页面名称（52种） | 流量路径分析 |

#### D. 设备/环境信息（7个字段）

| 字段 | 含义 | 用途 |
|------|------|------|
| user_agent | 用户代理字符串 | 设备识别 |
| platform | 平台（目前全是Web） | 平台分析 |
| os_name | 操作系统 | 设备分析 |
| os_version | 操作系统版本 | 兼容性分析 |
| browser | 浏览器名称 | 浏览器分析 |
| browser_version | 浏览器版本 | 兼容性分析 |
| language | 语言（14种） | 国际化分析 |

#### E. 地理位置（4个字段）

| 字段 | 含义 | 用途 |
|------|------|------|
| currency | 货币（6种） | 价格分析 |
| country | 国家 | 地域分析 |
| region | 地区 | 地域分析 |
| city | 城市 | 地域分析 |

#### F. JSON扩展字段（3个字段）⭐ 最重要

| 字段 | 含义 | 包含的关键信息 |
|------|------|---------------|
| **event_properties_json** | 事件属性（每个事件类型不同） | **价格、房型、酒店ID、供应商、搜索词、筛选条件、优惠券、停留时间等** |
| user_properties_json | 用户属性 | 客户ID、客户分组 |
| groups_json | 分组信息 | 组织分组 |

#### event_properties_json 中的关键字段（130+个）

**价格相关**：quote_price, preorder_price, base_price, price_min, price_max, coupon_amount, payment_fee, quote_currency, combined_rate

**酒店相关**：dida_hotel_id, dida_rpid, room_type, room_type_name, bed_type, meal_type, star_rating, supplier_id, rp_count, supplier_count, rp_area, rp_mask_id, cancellation_policy, check_type, room_nights, room_rank_no, rank_no

**搜索相关**：search_session_id, search_request_id, search_hoteldetail_request_id, search_des_query, search_type, is_quick_search, is_realtime, has_result, load_time, hotels_return, filter_name, filter_reason, sortby

**营销相关**：slide_id, slide_link, category_name, promotions, coupon_amount, home_card_id, home_category_name, home_sub_category_name

**订单相关**：preorder_id, order_id, order_total_amount, payment_method, result_code, result_msg, result_status, is_success

**用户行为**：stay_time, exit_type, button_name, click_id, click_type, trigger, from, dir, path, tab_name

**筛选相关**：pricerange_min, pricerange_max, specific_option, lables, brands, regions, city_list, nationality

**推荐相关**：rec_request_id, asso_dida_hotel_id, page_no

### 2.3 用户基础信息表 (ods_amplitude_users) - 13个字段

| 字段 | 含义 | 用途 |
|------|------|------|
| identity_id | 统一身份标识 | 关联事件表 |
| user_id | 用户ID | 用户分析 |
| device_id | 设备ID | 设备分析 |
| schema_version | 数据版本 | 数据质量 |
| updated_time | 更新时间 | 活跃度分析 |
| first_referrer_url | 首次来源URL | 获客渠道分析 |
| first_referrer_page_name | 首次来源页面 | 获客渠道分析 |
| **user_properties_json** | 用户属性 | **包含 dida_client_id（客户机构名）、dida_client_group_id（客户分组）** |
| groups_json | 分组信息 | 组织分析 |
| created_at | 创建时间 | 注册分析 |
| modified_at | 修改时间 | 活跃度分析 |
| **client_id** | **客户机构ID（5449个唯一值）** | **客户维度分析** |
| **client_group_id** | **客户分组ID（9个分组）** | **客户分层分析** |

**client_group_id 分布**：
- 2 = 国内线下Shopping（5081人，50.8%）
- 6 = 海外线下（1897人，19.0%）
- 3 = 国内线下API（630人，6.3%）
- 11 = 内部账号（518人，5.2%）
- 7 = 海外线上（313人，3.1%）
- 8 = 其他（154人）
- 12 = 其他（21人）
- 1 = 其他（1人）
- \N = 未登录（1385人，13.9%）

### 2.4 酒店购物漏斗表 (dwd_hotel_shopping_funnel_detai) - 38个字段

#### 漏斗11个步骤（完整转化链路）

| Step | step_code | step_name | 样本数 | 转化率 |
|------|-----------|-----------|--------|--------|
| 1 | request | 酒店详情请求 | 1,052 | 10.5% |
| 2 | available | 酒店详情有价返回 | 891 | 8.9% |
| 3 | expose | 酒店详情RP曝光 | 7,471 | 74.7% |
| 4 | click | 酒店详情RP点击 | 148 | 1.5% |
| 5 | prebook | preorder结果返回 | 133 | 1.3% |
| 6 | click_payment | 点击下一步支付 | 51 | 0.5% |
| 7 | payment_return | 下一步支付返回 | 52 | 0.5% |
| 8 | prebook_total | Shopping所有订单结果返回 | 54 | 0.5% |
| 9 | prebook_success | Shopping成功订单结果返回 | 53 | 0.5% |
| 10 | booking_with_fail | Booking含失败 | 37 | 0.4% |
| 11 | booking_valid | Booking确认+取消 | 58 | 0.6% |

#### 漏斗表字段分类

**酒店维度（14个字段）**：
- standard_hotel_id, dida_hotel_name, country_code, country_name, city_code, city_name, star_rating, destination_id, brand_id, brand_name, chain_id, chain_name, property_category

**客户维度（7个字段）**：
- user_id, client_id, client_name, client_group_id, client_category_id, parent_client_id, client_group, client_group_cn

**漏斗维度（7个字段）**：
- step_code, step_name, step_no, pv_key, rp_pv_key, rp_valid_type, inventory_status, is_consistent

**搜索条件（6个字段）**：
- check_in_date, check_out_date, adult_count, child_count, room_num, nationality

**其他**：
- metric_date, etl_time, is_test_account

### 2.5 事件类型完整清单（114种，按业务场景分类）

#### 搜索类（16种）
search_enter, Search, search_request, search_result_return, search_hoteldetail_request, search_hoteldetail_result_return, search_des_sugg_request, search_des_sugg_result_return, search_des_sugg_expose, search_des_sugg_click, search_des_hot_expose, Select_DestinationSuggestion, Change_SearchDate, Change_SearchOccupancy, Change_SearchNationality, search_shortcut_panel_click, hotel_searchmap_click, Clear_Keyword

#### 酒店详情类（10种）
page_view, hotel_detail_rp_expose, hotel_detail_rp_click, hotel_detail_filter_enter, hotel_detail_filter_click, Select_HotelRatePlanFilter_MealType, Toggle_HotelRatePlanFilter_Refundable, Select_HotelRatePlanFilter_BedType, Select_HotelRatePlanFilter_RoomType, Clear_HotelRatePlanFilter

#### 推荐类（7种）
hotel_recommend_expose, hotel_recommend_click, hotel_recommend_no_price_filter, hotel_recommend_change_expose, hotel_rec_card_expose, Click_RecommendHotel, booking_result_rec_expose

#### 订单类（14种）
Click_Reserve, preorder_result_return, preorder_payment_click, order_confirm_request, order_payment_confirm_click, order_result_return, order_payment_method_expose, order_payment_method_select, Add_OrderFillIn_Guest, Select_OrderFillIn_Coupon, Select_OrderPay_Coupon, preorder_expire_notice, booking_with_fail, booking_valid

#### 营销类（6种）
primary_banner_expose, primary_banner_click, banner_expose, ActivityHotelView, home_card_expose, frequently_booked_hotel_card_expose

#### 筛选/排序类（8种）
Select_HotelFilter_StarRating, Select_HotelFilter_Position, Select_HotelFilter_Feature, Switch_HotelList_SortType, filter_button_click, Remove_HotelFilterTag, hotel_card_expose, Select_OrderFillIn_Coupon

#### 页面导航类（10种）
navigation_bar_click, page_leave, ShowPicker, $identify, hotel_external_redirect, Change_SearchDate, Change_SearchOccupancy, Clear_Keyword

#### 其他业务类
积分商城、机票、用车、发票等

---

## 三、4个Agent各自需要什么数据

### Agent 1（信息数据分析）- 客户需求报告

**目标**：分析出"哪些客户有哪些需求"

| 数据需求 | 来源表 | 关键字段 | 用途 |
|---------|--------|---------|------|
| **客户基础画像** | ods_amplitude_users | client_id, client_group_id, client_group_cn, user_properties_json | 客户是谁、属于哪个分组 |
| **客户行为轨迹** | ods_amplitude_events | user_id, event_type, page_name, event_time, search_session_id | 客户在网站上做了什么 |
| **搜索行为分析** | ods_amplitude_events (event_properties_json) | search_des_query, destination_id, checkin_date, checkout_date, nationality, price_min, price_max, star_rating, brands, regions | 客户搜了什么目的地、什么日期、什么价格区间、什么品牌 |
| **浏览行为分析** | ods_amplitude_events | page_name, page_url, dida_hotel_id (from event_properties), stay_time | 客户看了哪些酒店、停留多久 |
| **筛选偏好分析** | ods_amplitude_events (event_properties_json) | filter_name, sortby, pricerange_min/max, meal_type, bed_type, cancellation_policy, star_rating | 客户用什么条件筛选 |
| **漏斗转化分析** | dwd_hotel_shopping_funnel_detai | step_code, step_name, client_id, standard_hotel_id, country_name, city_name | 客户在哪个环节流失 |
| **历史订单画像** | booking.channelbooking_v2 (伽利略) | clientid, didahotelname_cn, didahotelcountryname_en, pricecny, checkindate, roomnightcount | 客户过去订了什么酒店、什么目的地、什么价位 |
| **客户标签** | 待建设 | 客户分层标签、行为标签、偏好标签 | 客户分类 |
| **行业/目的地情报** | 外部数据源 | 全球目的地重大活动、节假日、签证政策、航班运力 | 外部需求触发因素 |

**Agent 1 输出**：
```
客户需求报告 = {
  客户ID: "XXX",
  客户分组: "国内线下Shopping",
  核心目的地需求: ["日本", "泰国", "新加坡"],
  价格偏好: "500-2000 CNY/晚",
  品牌偏好: ["Marriott", "IHG"],
  房型偏好: "大床房",
  出行时间偏好: "节假日前后",
  行为特征: "高频搜索低转化 / 搜索后直接下单 / 只看推荐",
  流失环节: "RP曝光→RP点击 (转化率2%)",
  需求触发因素: "新加坡F1赛事 9月",
  推荐策略方向: "推送F1赛事周边酒店 + 限时优惠券"
}
```

### Agent 2（资源匹配）- 资源匹配方案

**目标**：找出"什么产品和功能能满足这些需求"

| 数据需求 | 来源表 | 关键字段 | 用途 |
|---------|--------|---------|------|
| **酒店资源库** | dwd_hotel_shopping_funnel_detai | standard_hotel_id, dida_hotel_name, country_name, city_name, star_rating, brand_name, chain_name, property_category | 有哪些酒店可用 |
| **酒店价格数据** | ods_amplitude_events (event_properties_json) | quote_price, quote_currency, supplier_id, rp_count, supplier_count | 酒店价格竞争力 |
| **酒店库存状态** | dwd_hotel_shopping_funnel_detai | inventory_status, rp_valid_type, is_consistent | 酒店是否有房、有价 |
| **酒店标签** | 待建设 | 酒店静态标签、RP标签、POI标签 | 酒店特征描述 |
| **RP（房价计划）数据** | ods_amplitude_events (event_properties_json) | dida_rpid, rp_area, rp_mask_id, meal_type, bed_type, cancellation_policy, check_type, room_type, room_nights | 具体房型和价格计划 |
| **供应商数据** | ods_amplitude_events (event_properties_json) | supplier_id, supplier_count | 供应商覆盖情况 |
| **推荐系统数据** | ods_amplitude_events | hotel_recommend_expose, hotel_recommend_click, hotel_recommend_no_price_filter | 推荐系统的匹配结果 |
| **营销活动资源** | ods_amplitude_events (event_properties_json) | slide_id, slide_link, category_name, promotions | 现有营销活动资源 |
| **功能使用数据** | ods_amplitude_events | 各功能模块的曝光/点击/使用数据 | 哪些功能被使用、使用效果如何 |

**Agent 2 输出**：
```
资源匹配方案 = {
  匹配酒店清单: [
    {酒店ID, 酒店名, 城市, 星级, 品牌, 最低价, 供应商数, 有价RP数, 库存状态},
    ...
  ],
  匹配功能: ["热门酒店小助手-新加坡专区", "F1赛事落地页"],
  匹配营销活动: ["新加坡F1赛事酒店预订"],
  价格竞争力评估: {平均价差, 有价率, 库存覆盖率},
  资源缺口: ["缺少F1赛场周边3km内5星酒店", "缺少含早RP"]
}
```

### Agent 3（方案策划）- 策划方案 + 监控

**目标**：整合Agent 1+2 → 策划方案 + 搭建监控

| 数据需求 | 来源表 | 关键字段 | 用途 |
|---------|--------|---------|------|
| **Agent 1 输出** | - | 客户需求报告 | 知道要服务谁、什么需求 |
| **Agent 2 输出** | - | 资源匹配方案 | 知道有什么资源可用 |
| **营销活动效果历史** | ods_amplitude_events | primary_banner_expose, primary_banner_click, slide_id, ActivityHotelView | 历史活动效果参考 |
| **漏斗转化率基线** | dwd_hotel_shopping_funnel_detai | 各step转化率 | 设定目标基线 |
| **实时监控数据** | ods_amplitude_events + dwd_funnel | 实时事件流 | 监控活动效果 |
| **目标指标定义** | 运营师输入 | TTV目标、转化率目标、订单量目标 | 监控目标 |
| **优惠券/促销数据** | ods_amplitude_events (event_properties_json) | coupon_amount, Select_OrderFillIn_Coupon, Select_OrderPay_Coupon | 促销效果 |

**Agent 3 输出**：
```
策划方案 = {
  活动名称: "新加坡F1赛事酒店预订",
  目标客群: ["搜索过新加坡的客户", "历史订过东南亚的客户"],
  活动形式: "首页Banner + 落地页 + 专属优惠券",
  选品清单: [酒店ID列表 + 价格 + 库存],
  推送策略: {推送渠道, 推送时间, 推送内容},
  目标指标: {
    曝光量目标: 10000,
    点击率目标: 5%,
    转化率目标: 2%,
    订单量目标: 100单,
    TTV目标: 500000 CNY
  },
  监控看板: {
    实时指标: [曝光量, 点击量, 点击率, 订单量, TTV],
    预警规则: [点击率<3%报警, 转化率<1%报警],
    报告频率: "每日"
  }
}
```

### Agent 4（结果分析）- 效果复盘

**目标**：分析效果、计算ROI、输出优化建议

| 数据需求 | 来源表 | 关键字段 | 用途 |
|---------|--------|---------|------|
| **活动全量数据** | ods_amplitude_events | 活动期间所有相关事件 | 活动效果数据 |
| **漏斗转化数据** | dwd_hotel_shopping_funnel_detai | 活动期间漏斗各step数据 | 转化效率分析 |
| **订单数据** | booking.channelbooking_v2 | 活动期间订单明细 | 实际成交数据 |
| **目标 vs 实际** | Agent 3 设定的目标 | 目标指标 | 达成率计算 |
| **客户反馈数据** | 待建设 | 客户评价、投诉、咨询 | 定性分析 |
| **历史对比数据** | 历史同期数据 | 同比/环比 | 增长分析 |
| **ROI计算** | 订单TTV + 活动成本 | GP, TTV, 活动投入 | ROI计算 |

**Agent 4 输出**：
```
复盘报告 = {
  项目背景: "...",
  目标客群: "...",
  使用资源: "...",
  目标设定: {...},
  实际结果: {
    曝光量: 12000 (达成率120%),
    点击率: 4.5% (目标5%, 达成率90%),
    转化率: 1.8% (目标2%, 达成率90%),
    订单量: 95单 (目标100, 达成率95%),
    TTV: 480000 CNY (目标500000, 达成率96%)
  },
  ROI: "投入产出比 1:8.5",
  关键发现: ["Banner点击率低于预期", "F1赛场周边酒店库存不足"],
  优化建议: ["增加赛场周边酒店供给", "优化Banner文案"],
  可复用经验: ["东南亚赛事活动模板"]
}
```

---

## 四、本地数据库设计方案

### 4.1 数据库整体架构

```
┌─────────────────────────────────────────────────────────┐
│                  本地数据库 (SQLite/PostgreSQL)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 客户画像层    │  │ 行为数据层    │  │ 产品资源层    │  │
│  │              │  │              │  │              │  │
│  │ dim_client   │  │ fact_events  │  │ dim_hotel    │  │
│  │ dim_client_  │  │ fact_funnel  │  │ dim_rp       │  │
│  │   tags       │  │ fact_search  │  │ dim_supplier │  │
│  │              │  │ fact_session │  │ dim_brand    │  │
│  └──────────────┘  ──────────────┘  └──────────────┘  │
│                                                         │
│  ──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 营销活动层    │  │ 订单交易层    │  │ 外部情报层    │  │
│  │              │  │              │  │              │  │
│  │ dim_campaign │  │ fact_orders  │  │ dim_dest_    │  │
│  │ fact_campaign│  │ fact_revenue │  │   events     │  │
│  │   metrics    │  │              │  │ dim_holiday  │  │
│  │              │  │              │  │ dim_flight   │  │
│  ──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │ 监控告警层    │  │ 报告模板层    │                    │
│  │              │  │              │                    │
│  │ fact_monitor │  │ tpl_report   │                    │
│  │ dim_alert_   │  │ tpl_dashboard│                    │
│  │   rules      │  │              │                    │
│  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 核心表设计（完整字段清单）

#### 表1：dim_client（客户维度表）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| client_id | VARCHAR | 客户机构ID（主键） | ods_amplitude_users |
| client_name | VARCHAR | 客户机构名称 | dwd_funnel |
| client_group_id | INT | 客户分组ID | ods_amplitude_users |
| client_group | VARCHAR | 客户分组英文 | dwd_funnel |
| client_group_cn | VARCHAR | 客户分组中文 | dwd_funnel |
| client_category_id | INT | 客户类别ID | dwd_funnel |
| parent_client_id | VARCHAR | 上级组织ID | dwd_funnel |
| user_id | VARCHAR | 用户ID | ods_amplitude_users |
| identity_id | VARCHAR | 统一身份标识 | ods_amplitude_users |
| device_id | VARCHAR | 设备ID | ods_amplitude_users |
| first_referrer_url | VARCHAR | 首次来源URL | ods_amplitude_users |
| first_referrer_page_name | VARCHAR | 首次来源页面 | ods_amplitude_users |
| register_date | DATE | 注册日期 | ods_amplitude_users.created_at |
| last_active_date | DATE | 最后活跃日期 | ods_amplitude_users.updated_time |
| is_test_account | BOOLEAN | 是否测试账号 | dwd_funnel |
| language | VARCHAR | 语言偏好 | ods_amplitude_events |
| currency | VARCHAR | 货币偏好 | ods_amplitude_events |
| platform | VARCHAR | 平台偏好 | ods_amplitude_events |
| **标签字段（待建设）** | | | |
| tag_customer_value | VARCHAR | 客户价值标签（高/中/低） | 计算得出 |
| tag_activity_level | VARCHAR | 活跃度标签（活跃/休眠/新客） | 计算得出 |
| tag_preferred_dest | VARCHAR | 偏好目的地 | 计算得出 |
| tag_preferred_price | VARCHAR | 偏好价格区间 | 计算得出 |
| tag_preferred_brand | VARCHAR | 偏好品牌 | 计算得出 |
| tag_booking_freq | VARCHAR | 预订频率标签 | 计算得出 |
| tag_churn_risk | VARCHAR | 流失风险标签 | 计算得出 |

#### 表2：fact_events（用户行为事实表）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| event_pk | VARCHAR | 事件唯一ID（主键） | ods_amplitude_events.pre_event_pk |
| event_time | TIMESTAMP | 事件发生时间 | ods_amplitude_events.event_time |
| event_date | DATE | 事件日期 | ods_amplitude_events.event_date |
| event_hour | INT | 事件小时 | ods_amplitude_events.event_hour |
| user_id | VARCHAR | 用户ID | ods_amplitude_events.user_id |
| client_id | VARCHAR | 客户机构ID | ods_amplitude_users.client_id |
| identity_id | VARCHAR | 统一身份标识 | ods_amplitude_events.identity_id |
| device_id | VARCHAR | 设备ID | ods_amplitude_events.device_id |
| session_id | BIGINT | 会话ID | ods_amplitude_events.session_id |
| search_session_id | VARCHAR | 搜索会话ID | ods_amplitude_events.search_session_id |
| event_type | VARCHAR | 事件类型 | ods_amplitude_events.event_type |
| page_name | VARCHAR | 页面名称 | ods_amplitude_events.page_name |
| page_url | VARCHAR | 页面URL | ods_amplitude_events.page_url |
| referrer_page_name | VARCHAR | 来源页面 | ods_amplitude_events.referrer_page_name |
| referrer_url | VARCHAR | 来源URL | ods_amplitude_events.referrer_url |
| platform | VARCHAR | 平台 | ods_amplitude_events.platform |
| language | VARCHAR | 语言 | ods_amplitude_events.language |
| currency | VARCHAR | 货币 | ods_amplitude_events.currency |
| **解析自 event_properties_json** | | | |
| dida_hotel_id | BIGINT | 酒店ID | event_properties_json |
| dida_rpid | VARCHAR | RP ID | event_properties_json |
| room_type | BIGINT | 房型ID | event_properties_json |
| room_type_name | VARCHAR | 房型名称 | event_properties_json |
| bed_type | INT | 床型 | event_properties_json |
| meal_type | VARCHAR | 餐食类型 | event_properties_json |
| quote_price | DECIMAL | 报价 | event_properties_json |
| quote_currency | VARCHAR | 报价货币 | event_properties_json |
| preorder_price | VARCHAR | 预订价格 | event_properties_json |
| preorder_id | VARCHAR | 预订ID | event_properties_json |
| supplier_id | INT | 供应商ID | event_properties_json |
| rp_count | INT | RP数量 | event_properties_json |
| supplier_count | INT | 供应商数量 | event_properties_json |
| rp_area | VARCHAR | RP区域(normal/promoted) | event_properties_json |
| cancellation_policy | INT | 取消政策 | event_properties_json |
| check_type | VARCHAR | 确认类型 | event_properties_json |
| room_nights | INT | 间夜数 | event_properties_json |
| rank_no | INT | 排名序号 | event_properties_json |
| room_rank_no | INT | 房型排名 | event_properties_json |
| search_des_query | VARCHAR | 搜索关键词 | event_properties_json |
| search_request_id | VARCHAR | 搜索请求ID | event_properties_json |
| search_hoteldetail_request_id | VARCHAR | 酒店详情搜索请求ID | event_properties_json |
| search_type | VARCHAR | 搜索类型 | event_properties_json |
| is_quick_search | BOOLEAN | 是否快速搜索 | event_properties_json |
| is_realtime | BOOLEAN | 是否实时搜索 | event_properties_json |
| has_result | BOOLEAN | 是否有结果 | event_properties_json |
| load_time | INT | 加载时间(ms) | event_properties_json |
| hotels_return | INT | 返回酒店数 | event_properties_json |
| filter_name | VARCHAR | 筛选名称 | event_properties_json |
| sortby | VARCHAR | 排序方式 | event_properties_json |
| price_min | VARCHAR | 最低价格 | event_properties_json |
| price_max | VARCHAR | 最高价格 | event_properties_json |
| pricerange_min | INT | 价格范围最小值 | event_properties_json |
| pricerange_max | INT | 价格范围最大值 | event_properties_json |
| star_rating | VARCHAR | 星级筛选 | event_properties_json |
| brands | VARCHAR | 品牌筛选 | event_properties_json |
| regions | VARCHAR | 地区筛选 | event_properties_json |
| city_list | VARCHAR | 城市列表 | event_properties_json |
| nationality | VARCHAR | 国籍 | event_properties_json |
| checkin_date | VARCHAR | 入住日期 | event_properties_json |
| checkout_date | VARCHAR | 离店日期 | event_properties_json |
| adult_count | INT | 成人数 | event_properties_json |
| child_count | INT | 儿童数 | event_properties_json |
| room_num | INT | 房间数 | event_properties_json |
| total_adult_count | INT | 总成人 | event_properties_json |
| total_child_count | INT | 总儿童 | event_properties_json |
| room_des | VARCHAR | 房间描述JSON | event_properties_json |
| destination_id | VARCHAR | 目的地ID | event_properties_json |
| country_name | VARCHAR | 国家名称 | event_properties_json |
| slide_id | VARCHAR | Banner ID | event_properties_json |
| slide_link | VARCHAR | Banner链接 | event_properties_json |
| category_name | VARCHAR | 分类名称 | event_properties_json |
| promotions | VARCHAR | 促销信息 | event_properties_json |
| coupon_amount | DECIMAL | 优惠券金额 | event_properties_json |
| order_id | VARCHAR | 订单ID | event_properties_json |
| order_total_amount | DECIMAL | 订单总金额 | event_properties_json |
| payment_method | VARCHAR | 支付方式 | event_properties_json |
| payment_fee | DECIMAL | 支付费用 | event_properties_json |
| result_code | VARCHAR | 结果代码 | event_properties_json |
| result_msg | VARCHAR | 结果消息 | event_properties_json |
| result_status | VARCHAR | 结果状态 | event_properties_json |
| is_success | BOOLEAN | 是否成功 | event_properties_json |
| stay_time | BIGINT | 页面停留时间(ms) | event_properties_json |
| exit_type | VARCHAR | 离开类型 | event_properties_json |
| button_name | VARCHAR | 按钮名称 | event_properties_json |
| click_id | VARCHAR | 点击ID | event_properties_json |
| click_type | VARCHAR | 点击类型 | event_properties_json |
| home_card_id | VARCHAR | 首页卡片ID | event_properties_json |
| home_category_name | VARCHAR | 首页分类名称 | event_properties_json |
| home_sub_category_name | VARCHAR | 首页子分类 | event_properties_json |
| rec_request_id | VARCHAR | 推荐请求ID | event_properties_json |
| asso_dida_hotel_id | BIGINT | 关联酒店ID | event_properties_json |
| page_no | INT | 页码 | event_properties_json |
| combined_rate | VARCHAR | 组合价格 | event_properties_json |
| base_price | DECIMAL | 基础价格 | event_properties_json |
| rp_mask_id | VARCHAR | RP掩码ID | event_properties_json |
| rpid | VARCHAR | RP ID(旧) | event_properties_json |
| tab_name | VARCHAR | Tab名称 | event_properties_json |
| tab_rank_no | INT | Tab排名 | event_properties_json |
| trigger | VARCHAR | 触发方式 | event_properties_json |
| from | VARCHAR | 来源 | event_properties_json |
| dir | VARCHAR | 方向 | event_properties_json |
| path | VARCHAR | 路径 | event_properties_json |
| name | VARCHAR | 名称 | event_properties_json |
| title | VARCHAR | 标题 | event_properties_json |
| type | VARCHAR | 类型 | event_properties_json |
| value | VARCHAR | 值 | event_properties_json |
| object_type | VARCHAR | 对象类型 | event_properties_json |
| source | VARCHAR | 来源 | event_properties_json |
| event_category | VARCHAR | 事件分类 | event_properties_json |
| event_label | VARCHAR | 事件标签 | event_properties_json |
| evt_id | VARCHAR | 事件ID(内) | event_properties_json |
| biz_type | VARCHAR | 业务类型 | event_properties_json |
| lables | VARCHAR | 标签 | event_properties_json |
| specific_option | VARCHAR | 特定选项 | event_properties_json |
| is_backtomodify | BOOLEAN | 是否返回修改 | event_properties_json |
| inquiry_id | VARCHAR | 询价ID | event_properties_json |
| inquiry_item_id | VARCHAR | 询价项ID | event_properties_json |
| inquiry_msg | VARCHAR | 询价消息 | event_properties_json |
| inquiry_params_id | VARCHAR | 询价参数ID | event_properties_json |
| group_booking_num | INT | 团队预订数 | event_properties_json |
| pax_num | INT | 人数 | event_properties_json |
| luggage_num | INT | 行李数 | event_properties_json |
| traffic_facility_no | INT | 交通设施编号 | event_properties_json |
| start_name | VARCHAR | 起点名称 | event_properties_json |
| start_lat | DECIMAL | 起点纬度 | event_properties_json |
| start_lon | DECIMAL | 起点经度 | event_properties_json |
| end_name | VARCHAR | 终点名称 | event_properties_json |
| end_airport_code | VARCHAR | 终点机场代码 | event_properties_json |
| plan_dpt_local_time | VARCHAR | 出发本地时间 | event_properties_json |
| plan_arr_local_time | VARCHAR | 到达本地时间 | event_properties_json |
| plan_service_tm_biz | VARCHAR | 服务时间 | event_properties_json |
| special_requests | VARCHAR | 特殊要求 | event_properties_json |
| dida_room_type_id | BIGINT | 道旅房型ID | event_properties_json |
| roomTypeId | BIGINT | 房型ID(旧) | event_properties_json |
| dida_region_id | VARCHAR | 道旅地区ID | event_properties_json |
| des_type | VARCHAR | 目的地类型 | event_properties_json |
| card_id | VARCHAR | 卡片ID | event_properties_json |
| card_name | VARCHAR | 卡片名称 | event_properties_json |
| category_rank | INT | 分类排名 | event_properties_json |

#### 表3：fact_funnel（漏斗事实表）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| funnel_id | SERIAL | 自增主键 | - |
| metric_date | DATE | 统计日期 | dwd_funnel |
| standard_hotel_id | VARCHAR | 标准酒店ID | dwd_funnel |
| dida_hotel_name | VARCHAR | 酒店名称 | dwd_funnel |
| country_code | VARCHAR | 国家编码 | dwd_funnel |
| country_name | VARCHAR | 国家名称 | dwd_funnel |
| city_code | VARCHAR | 城市编码 | dwd_funnel |
| city_name | VARCHAR | 城市名称 | dwd_funnel |
| star_rating | VARCHAR | 酒店星级 | dwd_funnel |
| destination_id | VARCHAR | 目的地ID | dwd_funnel |
| brand_id | VARCHAR | 品牌ID | dwd_funnel |
| brand_name | VARCHAR | 品牌名称 | dwd_funnel |
| chain_id | VARCHAR | 连锁集团ID | dwd_funnel |
| chain_name | VARCHAR | 连锁集团名称 | dwd_funnel |
| property_category | VARCHAR | 物业类型 | dwd_funnel |
| user_id | VARCHAR | 用户ID | dwd_funnel |
| client_id | VARCHAR | 客户ID | dwd_funnel |
| client_name | VARCHAR | 客户名称 | dwd_funnel |
| client_group_id | INT | 客户分组ID | dwd_funnel |
| client_category_id | INT | 客户类别ID | dwd_funnel |
| parent_client_id | VARCHAR | 上级组织ID | dwd_funnel |
| client_group | VARCHAR | 客户分组英文 | dwd_funnel |
| client_group_cn | VARCHAR | 客户分组中文 | dwd_funnel |
| step_code | VARCHAR | 漏斗步骤编码 | dwd_funnel |
| step_name | VARCHAR | 漏斗步骤名称 | dwd_funnel |
| step_no | INT | 步骤序号 | dwd_funnel |
| pv_key | VARCHAR | 流量唯一标识 | dwd_funnel |
| rp_pv_key | VARCHAR | 房型流量唯一标识 | dwd_funnel |
| rp_valid_type | VARCHAR | 有价返回类型 | dwd_funnel |
| inventory_status | VARCHAR | 库存状态 | dwd_funnel |
| is_consistent | VARCHAR | 报价是否一致 | dwd_funnel |
| is_test_account | BOOLEAN | 是否测试账号 | dwd_funnel |
| check_in_date | DATE | 入住日期 | dwd_funnel |
| check_out_date | DATE | 离店日期 | dwd_funnel |
| adult_count | INT | 成人数 | dwd_funnel |
| child_count | INT | 儿童数 | dwd_funnel |
| room_num | INT | 房间数 | dwd_funnel |
| nationality | VARCHAR | 国籍 | dwd_funnel |
| etl_time | TIMESTAMP | ETL时间 | dwd_funnel |

#### 表4：dim_hotel（酒店维度表）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| standard_hotel_id | VARCHAR | 标准酒店ID（主键） | dwd_funnel |
| dida_hotel_id | BIGINT | 道旅酒店ID | event_properties_json |
| dida_hotel_name | VARCHAR | 酒店名称 | dwd_funnel |
| country_code | VARCHAR | 国家编码 | dwd_funnel |
| country_name | VARCHAR | 国家名称 | dwd_funnel |
| city_code | VARCHAR | 城市编码 | dwd_funnel |
| city_name | VARCHAR | 城市名称 | dwd_funnel |
| destination_id | VARCHAR | 目的地ID | dwd_funnel |
| star_rating | VARCHAR | 星级 | dwd_funnel |
| brand_id | VARCHAR | 品牌ID | dwd_funnel |
| brand_name | VARCHAR | 品牌名称 | dwd_funnel |
| chain_id | VARCHAR | 连锁集团ID | dwd_funnel |
| chain_name | VARCHAR | 连锁集团名称 | dwd_funnel |
| property_category | VARCHAR | 物业类型 | dwd_funnel |
| **标签字段（待建设）** | | | |
| tag_hotel_type | VARCHAR | 酒店类型标签（商务/度假/亲子） | 待建设 |
| tag_location_type | VARCHAR | 位置标签（市中心/机场/海边） | 待建设 |
| tag_price_level | VARCHAR | 价格层级（经济/中档/奢华） | 计算得出 |
| tag_popularity | VARCHAR | 热度标签（热门/冷门） | 计算得出 |
| tag_competitiveness | VARCHAR | 价格竞争力标签 | 计算得出 |
| tag_inventory_health | VARCHAR | 库存健康度标签 | 计算得出 |
| tag_conversion_rate | VARCHAR | 转化率标签 | 计算得出 |
| poi_tags | VARCHAR | POI标签（附近景点/设施） | 待建设 |

#### 表5：dim_campaign（营销活动维度表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| campaign_id | VARCHAR | 活动ID（主键） | 运营师定义 |
| campaign_name | VARCHAR | 活动名称 | 运营师定义 |
| campaign_type | VARCHAR | 活动类型（Banner/落地页/优惠券/闪购/促销） | 运营师定义 |
| slide_id | VARCHAR | Banner ID（关联埋点） | event_properties_json.slide_id |
| slide_link | VARCHAR | 活动链接 | event_properties_json.slide_link |
| category_name | VARCHAR | 分类名称 | event_properties_json.category_name |
| start_date | DATE | 活动开始日期 | 运营师定义 |
| end_date | DATE | 活动结束日期 | 运营师定义 |
| target_dest | VARCHAR | 目标目的地 | 运营师定义 |
| target_hotel_ids | TEXT | 目标酒店ID列表 | 运营师定义/Agent 2输出 |
| target_client_groups | VARCHAR | 目标客户分组 | 运营师定义/Agent 1输出 |
| target_metrics | JSON | 目标指标（曝光/点击/转化/订单/TTV） | 运营师定义 |
| budget | DECIMAL | 活动预算 | 运营师定义 |
| coupon_config | JSON | 优惠券配置 | 运营师定义 |
| status | VARCHAR | 活动状态（筹备/进行中/已结束） | 运营师定义 |
| created_by | VARCHAR | 创建人 | 运营师定义 |
| created_at | TIMESTAMP | 创建时间 | 系统自动 |

#### 表6：fact_campaign_metrics（营销活动效果事实表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| metric_id | SERIAL | 自增主键 | - |
| campaign_id | VARCHAR | 活动ID | dim_campaign |
| metric_date | DATE | 统计日期 | - |
| metric_hour | INT | 统计小时 | - |
| **曝光指标** | | | |
| banner_expose_count | INT | Banner曝光次数 | fact_events WHERE event_type='primary_banner_expose' |
| banner_click_count | INT | Banner点击次数 | fact_events WHERE event_type='primary_banner_click' |
| banner_ctr | DECIMAL | Banner点击率 | 计算 |
| landing_page_pv | INT | 落地页PV | fact_events WHERE page_url LIKE campaign link |
| landing_page_uv | INT | 落地页UV | fact_events 去重 |
| **转化指标** | | | |
| hotel_detail_pv | INT | 酒店详情页PV | fact_events WHERE page_name='hotel_detail' AND 关联活动酒店 |
| rp_expose_count | INT | RP曝光次数 | fact_events WHERE event_type='hotel_detail_rp_expose' |
| rp_click_count | INT | RP点击次数 | fact_events WHERE event_type='hotel_detail_rp_click' |
| rp_ctr | DECIMAL | RP点击率 | 计算 |
| preorder_count | INT | 预订次数 | fact_events WHERE event_type='preorder_result_return' |
| payment_count | INT | 支付次数 | fact_events WHERE event_type='order_payment_confirm_click' |
| order_count | INT | 订单数 | fact_orders |
| success_order_count | INT | 成功订单数 | fact_orders WHERE status='success' |
| **收入指标** | | | |
| total_ttv | DECIMAL | 总交易额 | fact_orders |
| total_gp | DECIMAL | 总毛利润 | fact_orders |
| avg_order_value | DECIMAL | 平均订单金额 | 计算 |
| coupon_usage_count | INT | 优惠券使用次数 | fact_events WHERE event_type='Select_OrderPay_Coupon' |
| coupon_total_amount | DECIMAL | 优惠券总金额 | fact_events |
| **漏斗指标** | | | |
| funnel_request_count | INT | 酒店详情请求数 | fact_funnel WHERE step_no=1 |
| funnel_available_count | INT | 有价返回数 | fact_funnel WHERE step_no=2 |
| funnel_expose_count | INT | RP曝光数 | fact_funnel WHERE step_no=3 |
| funnel_click_count | INT | RP点击数 | fact_funnel WHERE step_no=4 |
| funnel_prebook_count | INT | 预订数 | fact_funnel WHERE step_no=5 |
| funnel_success_count | INT | 成功订单数 | fact_funnel WHERE step_no=9 |
| conversion_rate_expose_click | DECIMAL | 曝光→点击转化率 | 计算 |
| conversion_rate_click_order | DECIMAL | 点击→订单转化率 | 计算 |
| conversion_rate_overall | DECIMAL | 整体转化率 | 计算 |
| **客户指标** | | | |
| unique_clients | INT | 参与客户数 | 去重 client_id |
| new_clients | INT | 新客数 | 首次参与活动客户 |
| returning_clients | INT | 复购客户数 | 历史有订单客户 |
| client_conversion_rate | DECIMAL | 客户转化率 | 计算 |

#### 表7：fact_orders（订单事实表）- 从伽利略同步

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| order_number | VARCHAR | 订单号（主键） | channelbooking_v2.number |
| client_id | VARCHAR | 客户ID | channelbooking_v2.clientid |
| client_name | VARCHAR | 客户名称 | channelbooking_v2 |
| client_bd | VARCHAR | 客户BD | channelbooking_v2.clientbd |
| client_op | VARCHAR | 客户OP | channelbooking_v2.clientop |
| client_belong_team | VARCHAR | 客户所属团队 | channelbooking_v2.clientbelongteam |
| dida_hotel_id | BIGINT | 酒店ID | channelbooking_v2.didahotelid |
| dida_hotel_name | VARCHAR | 酒店名称 | channelbooking_v2.didahotelname_cn |
| dida_hotel_chain | VARCHAR | 酒店连锁 | channelbooking_v2.didahotelchainname |
| dida_hotel_star | VARCHAR | 酒店星级 | channelbooking_v2.didahotelstarrating |
| country_name | VARCHAR | 国家 | channelbooking_v2.didahotelcountryname_en |
| destination_name | VARCHAR | 目的地 | channelbooking_v2.didahoteldestinationname_cn |
| room_name | VARCHAR | 房型名称 | channelbooking_v2.roomname |
| room_type | VARCHAR | 房型 | channelbooking_v2.roomtype |
| bed_type | VARCHAR | 床型 | channelbooking_v2.bedtype |
| board_type | VARCHAR | 餐食 | channelbooking_v2.boardtype |
| status | INT | 订单状态 | channelbooking_v2.status |
| check_in_date | DATE | 入住日期 | channelbooking_v2.checkindate |
| check_out_date | DATE | 离店日期 | channelbooking_v2.checkoutdate |
| room_night_count | INT | 间夜数 | channelbooking_v2.roomnightcount |
| price_cny | DECIMAL | 人民币价格 | channelbooking_v2.pricecny |
| net_rate_cny | DECIMAL | 净价 | channelbooking_v2.netratecny |
| combined_revenue_cny | DECIMAL | 组合收入 | channelbooking_v2.combinedrevenuecny |
| kpi_revenue_cny | DECIMAL | KPI收入 | channelbooking_v2.kpirevenuecny |
| vcc_payment_cny | DECIMAL | VCC支付 | channelbooking_v2.vccpaymentcny |
| commission_rate | DECIMAL | 佣金率 | channelbooking_v2.commissionrate |
| commission_amount | DECIMAL | 佣金金额 | channelbooking_v2.commissionamount |
| is_direct_contract | BOOLEAN | 是否DC直签 | channelbooking_v2.isdirectcontract |
| lead_time_hour | INT | 提前预订小时数 | channelbooking_v2.leadtimehour |
| create_time | TIMESTAMP | 创建时间 | channelbooking_v2.createtime |
| confirm_time | TIMESTAMP | 确认时间 | channelbooking_v2.confirmtime |
| last_modified_time | TIMESTAMP | 最后修改时间 | channelbooking_v2 |
| operator | VARCHAR | 操作员 | channelbooking_v2.operator |
| is_dispute | BOOLEAN | 是否争议单 | channelbooking_v2.isdisputebooking |
| is_fraud | BOOLEAN | 是否欺诈单 | channelbooking_v2.isfraudbooking |
| is_brg | BOOLEAN | 是否BRG单 | channelbooking_v2.isbrgbooking |
| error_type | VARCHAR | 错误类型 | channelbooking_v2.errortype |
| payment_status | VARCHAR | 支付状态 | channelbooking_v2.paymentstatus |
| settlement_date | DATE | 结算日期 | channelbooking_v2.settlementdate |
| risk_level | VARCHAR | 风险等级 | channelbooking_v2.risklevel |
| risk_tag | VARCHAR | 风险标签 | channelbooking_v2.risktag |
| **关联活动** | | | |
| campaign_id | VARCHAR | 关联活动ID | 待建设（需UTM/campaign追踪） |
| campaign_source | VARCHAR | 活动来源 | 待建设 |

#### 表8：dim_destination_events（目的地事件/情报表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| event_id | SERIAL | 自增主键 | - |
| destination | VARCHAR | 目的地（国家/城市） | 外部数据 |
| event_name | VARCHAR | 事件名称（F1/展会/节日） | 外部数据 |
| event_type | VARCHAR | 事件类型（体育/会展/节日/政治） | 外部数据 |
| start_date | DATE | 开始日期 | 外部数据 |
| end_date | DATE | 结束日期 | 外部数据 |
| impact_level | VARCHAR | 影响级别（高/中/低） | 评估 |
| expected_hotel_demand | VARCHAR | 预期酒店需求影响 | 评估 |
| target_hotel_radius | INT | 目标酒店辐射半径(km) | 评估 |
| target_star_rating | VARCHAR | 目标星级范围 | 评估 |
| description | TEXT | 事件描述 | 外部数据 |
| source | VARCHAR | 数据来源 | - |
| created_at | TIMESTAMP | 创建时间 | 系统自动 |

#### 表9：dim_holiday（节假日日历表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| holiday_id | SERIAL | 自增主键 | - |
| country | VARCHAR | 国家 | 外部数据 |
| holiday_name | VARCHAR | 节假日名称 | 外部数据 |
| holiday_date | DATE | 节假日日期 | 外部数据 |
| holiday_type | VARCHAR | 类型（法定/传统/宗教） | 外部数据 |
| is_long_weekend | BOOLEAN | 是否长周末 | 计算 |
| travel_peak | VARCHAR | 旅游高峰级别（高/中/低） | 评估 |
| description | TEXT | 描述 | 外部数据 |

#### 表10：fact_monitor（实时监控事实表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| monitor_id | SERIAL | 自增主键 | - |
| campaign_id | VARCHAR | 活动ID | dim_campaign |
| monitor_time | TIMESTAMP | 监控时间 | 系统自动 |
| metric_name | VARCHAR | 指标名称 | - |
| metric_value | DECIMAL | 指标值 | 实时计算 |
| target_value | DECIMAL | 目标值 | dim_campaign.target_metrics |
| achievement_rate | DECIMAL | 达成率 | 计算 |
| alert_triggered | BOOLEAN | 是否触发告警 | 规则判断 |
| alert_level | VARCHAR | 告警级别（红/黄/绿） | 规则判断 |
| alert_message | VARCHAR | 告警信息 | 规则判断 |

#### 表11：dim_alert_rules（告警规则表）⭐ 新建

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| rule_id | SERIAL | 自增主键 | - |
| campaign_id | VARCHAR | 活动ID | dim_campaign |
| metric_name | VARCHAR | 监控指标 | - |
| condition_type | VARCHAR | 条件类型（低于/高于/等于） | 运营师定义 |
| threshold_value | DECIMAL | 阈值 | 运营师定义 |
| alert_level | VARCHAR | 告警级别 | 运营师定义 |
| alert_action | VARCHAR | 告警动作（通知/暂停/调整） | 运营师定义 |
| is_active | BOOLEAN | 是否启用 | 运营师定义 |

#### 表12：fact_search（搜索分析事实表）⭐ 新建（从events聚合）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| search_id | SERIAL | 自增主键 | - |
| search_session_id | VARCHAR | 搜索会话ID | event_properties_json |
| search_request_id | VARCHAR | 搜索请求ID | event_properties_json |
| user_id | VARCHAR | 用户ID | events |
| client_id | VARCHAR | 客户ID | users |
| search_time | TIMESTAMP | 搜索时间 | events.event_time |
| search_des_query | VARCHAR | 搜索关键词 | event_properties_json |
| destination_id | VARCHAR | 目的地ID | event_properties_json |
| country_name | VARCHAR | 国家 | event_properties_json |
| checkin_date | DATE | 入住日期 | event_properties_json |
| checkout_date | DATE | 离店日期 | event_properties_json |
| adult_count | INT | 成人数 | event_properties_json |
| child_count | INT | 儿童数 | event_properties_json |
| room_num | INT | 房间数 | event_properties_json |
| nationality | VARCHAR | 国籍 | event_properties_json |
| price_min | DECIMAL | 最低价格 | event_properties_json |
| price_max | DECIMAL | 最高价格 | event_properties_json |
| star_rating | VARCHAR | 星级筛选 | event_properties_json |
| brands | VARCHAR | 品牌筛选 | event_properties_json |
| sortby | VARCHAR | 排序方式 | event_properties_json |
| is_quick_search | BOOLEAN | 是否快速搜索 | event_properties_json |
| is_realtime | BOOLEAN | 是否实时搜索 | event_properties_json |
| has_result | BOOLEAN | 是否有结果 | event_properties_json |
| hotels_return | INT | 返回酒店数 | event_properties_json |
| supplier_count | INT | 供应商数 | event_properties_json |
| load_time | INT | 加载时间(ms) | event_properties_json |
| rp_count | INT | RP数量 | event_properties_json |
| converted_to_order | BOOLEAN | 是否转化为订单 | 关联orders |
| converted_hotel_id | BIGINT | 转化酒店ID | 关联orders |

#### 表13：fact_session（会话分析事实表）⭐ 新建（从events聚合）

| 字段名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| session_id | BIGINT | 会话ID | events.session_id |
| user_id | VARCHAR | 用户ID | events |
| client_id | VARCHAR | 客户ID | users |
| session_start | TIMESTAMP | 会话开始时间 | MIN(event_time) |
| session_end | TIMESTAMP | 会话结束时间 | MAX(event_time) |
| session_duration | BIGINT | 会话时长(秒) | 计算 |
| page_views | INT | 页面浏览数 | COUNT(page_view) |
| searches | INT | 搜索次数 | COUNT(search相关事件) |
| hotel_details | INT | 酒店详情浏览数 | COUNT(hotel_detail) |
| rp_exposures | INT | RP曝光数 | COUNT(rp_expose) |
| rp_clicks | INT | RP点击数 | COUNT(rp_click) |
| orders | INT | 订单数 | COUNT(order相关事件) |
| converted | BOOLEAN | 是否转化 | orders > 0 |
| entry_page | VARCHAR | 入口页面 | MIN(event_time)的page_name |
| exit_page | VARCHAR | 退出页面 | MAX(event_time)的page_name |
| devices | VARCHAR | 设备信息 | events.user_agent |
| language | VARCHAR | 语言 | events.language |

---

## 五、现有数据 vs 需要数据的差距分析

### 5.1 ✅ 已有数据（可以直接用）

| 数据 | 来源 | 覆盖Agent |
|------|------|----------|
| 用户行为事件（114种事件类型） | ods_amplitude_events | Agent 1, 3, 4 |
| 用户基础信息 + 客户关联 | ods_amplitude_users | Agent 1 |
| 酒店购物漏斗（11步完整链路） | dwd_hotel_shopping_funnel_detai | Agent 1, 3, 4 |
| 搜索行为详细数据 | event_properties_json | Agent 1 |
| 酒店维度信息（国家/城市/星级/品牌/连锁） | dwd_funnel | Agent 2 |
| RP/房价计划数据 | event_properties_json | Agent 2 |
| 营销活动曝光/点击数据 | primary_banner_expose/click | Agent 3, 4 |
| 推荐系统数据 | hotel_recommend_* 事件 | Agent 2 |
| 订单数据（伽利略） | channelbooking_v2 | Agent 4 |
| 页面停留时间 | event_properties_json.stay_time | Agent 1 |
| 筛选/排序行为 | filter/sort 相关事件 | Agent 1 |
| 优惠券使用数据 | Select_OrderFillIn_Coupon/Pay_Coupon | Agent 3, 4 |

### 5.2 ⚠️ 有数据但需要加工

| 数据 | 现状 | 需要做什么 |
|------|------|-----------|
| 客户标签 | 只有 client_group_id 分组 | 需要建设：价值标签、活跃度标签、偏好标签、流失风险标签 |
| 酒店标签 | 只有基础维度（星级/品牌/连锁） | 需要建设：类型标签、位置标签、价格层级、热度标签、竞争力标签、POI标签 |
| 活动归因 | Banner有slide_id，但订单表没有campaign_id | 需要在订单表加 UTM/campaign 追踪字段 |
| 客户历史订单画像 | 伽利略有订单数据，但没和用户行为关联 | 需要打通 user_id ↔ client_id ↔ 订单 |
| 会话级分析 | 有session_id，但没有聚合表 | 需要按session聚合行为序列 |
| 搜索分析 | 有搜索事件，但没有独立分析表 | 需要按search_session_id聚合搜索→转化链路 |

### 5.3 ❌ 缺失数据（需要新建或外部获取）

| 数据 | 用途 | 解决方案 |
|------|------|---------|
| **营销活动配置表** | Agent 3 策划活动需要 | 新建 dim_campaign 表，运营师手动录入或Agent生成 |
| **活动效果监控表** | Agent 3 监控 + Agent 4 复盘 | 新建 fact_campaign_metrics 表，定时从events聚合 |
| **目的地事件/情报** | Agent 1 分析需求触发因素 | 新建 dim_destination_events 表，外部数据导入（赛事/展会/节日） |
| **节假日日历** | Agent 1 分析出行需求 | 新建 dim_holiday 表，外部数据导入 |
| **告警规则表** | Agent 3 自动监控告警 | 新建 dim_alert_rules 表，运营师定义 |
| **实时监控表** | Agent 3 定期生成报告 | 新建 fact_monitor 表，定时写入 |
| **报告模板** | Agent 4 输出复盘报告 | 新建 tpl_report 表，预定义模板 |
| **客户标签体系** | Agent 1 客户分群 | 需要数据部建设标签系统 |
| **酒店标签体系** | Agent 2 资源匹配 | 需要数据部建设标签系统 |
| **订单-活动关联** | Agent 4 效果归因 | 需要在订单表加 campaign_id 字段 |
| **功能使用统计** | Agent 2 分析功能效果 | 需要从events中按功能模块聚合 |
| **竞品价格数据** | Agent 2 价格竞争力评估 | 外部数据（汇智/竞品网站） |
| **航班运力数据** | Agent 1 需求预判 | 外部数据 |
| **签证政策数据** | Agent 1 需求预判 | 外部数据 |

---

## 六、给数据部的需求清单（可直接提交）

### 6.1 需要数据部新建/开通的数据

| 优先级 | 需求 | 用途 | 对应Agent |
|--------|------|------|----------|
| **P0** | 客户标签体系（价值/活跃度/偏好/流失风险） | 客户分群、精准营销 | Agent 1 |
| **P0** | 酒店标签体系（类型/位置/价格层级/热度/竞争力/POI） | 资源匹配、推荐 | Agent 2 |
| **P0** | 订单表增加 campaign_id / utm_source / utm_medium 字段 | 活动效果归因 | Agent 4 |
| **P1** | 搜索行为聚合表（按search_session_id聚合搜索→转化全链路） | 搜索效果分析 | Agent 1, 3 |
| **P1** | 会话行为聚合表（按session_id聚合完整用户旅程） | 用户旅程分析 | Agent 1 |
| **P1** | 功能模块使用统计表（各功能曝光/点击/使用/转化） | 功能效果评估 | Agent 2, 3 |
| **P1** | 推荐系统效果表（推荐曝光/点击/转化/订单） | 推荐效果评估 | Agent 2, 4 |
| **P2** | 客户历史行为画像表（30天/90天行为聚合） | 客户画像 | Agent 1 |
| **P2** | 酒店实时库存/价格快照表 | 资源匹配 | Agent 2 |
| **P2** | 营销活动配置管理表（活动创建/编辑/上下线） | 活动管理 | Agent 3 |

### 6.2 需要数据部开通的查询权限

| 表/数据 | 当前状态 | 需要权限 |
|---------|---------|---------|
| ods_amplitude_events | ✅ 有样本数据 | 需要实时/定时同步到本地数据库 |
| ods_amplitude_users | ✅ 有样本数据 | 需要实时/定时同步到本地数据库 |
| dwd_hotel_shopping_funnel_detai | ✅ 有样本数据 | 需要实时/定时同步到本地数据库 |
| booking.channelbooking_v2 | ✅ 伽利略可查 | 需要定时同步到本地数据库 |
| dim.dim_dida_client_info |  无权限 | 需要申请MCP SQL查询权限 |
| 客户标签表（待建设） | ❌ 不存在 | 需要数据部建设并开放查询 |
| 酒店标签表（待建设） | ❌ 不存在 | 需要数据部建设并开放查询 |

### 6.3 数据同步方案建议

```
方案：定时ETL同步（推荐每日凌晨同步T-1数据）

数据源                    →  本地数据库表              →  同步频率
─────────────────────────────────────────────────────────────
ods_amplitude_events      →  fact_events              →  每日
ods_amplitude_users       →  dim_client               →  每日
dwd_hotel_shopping_funnel →  fact_funnel              →  每日
channelbooking_v2         →  fact_orders              →  每日
外部目的地事件数据         →  dim_destination_events   →  每周
外部节假日数据             →  dim_holiday              →  每年
活动配置(运营师录入)       →  dim_campaign             →  实时
监控数据(Agent 3生成)     →  fact_monitor             →  每小时
```

---

## 七、实现路径建议

### Phase 1（1-2周）：基础数据层搭建
1. 本地数据库选型（推荐 PostgreSQL，支持JSON字段）
2. 导入现有3张表的样本数据
3. 解析 event_properties_json，将关键字段提取为独立列
4. 搭建 dim_client + fact_events + fact_funnel 三张核心表

### Phase 2（2-3周）：Agent 1 数据能力
1. 建设搜索分析表（fact_search）
2. 建设会话分析表（fact_session）
3. 导入伽利略订单数据（fact_orders）
4. 打通 user_id ↔ client_id ↔ 订单 关联
5. Agent 1 可以输出客户需求报告

### Phase 3（2-3周）：Agent 2+3 数据能力
1. 建设 dim_hotel 酒店维度表（含标签）
2. 建设 dim_campaign 营销活动表
3. 建设 fact_campaign_metrics 活动效果表
4. 建设 dim_destination_events + dim_holiday 外部情报表
5. Agent 2 可以输出资源匹配方案
6. Agent 3 可以策划活动 + 搭建监控

### Phase 4（2-3周）：Agent 4 + 闭环
1. 建设 fact_monitor 实时监控表
2. 建设 dim_alert_rules 告警规则表
3. 建设报告模板（tpl_report）
4. 订单表加 campaign_id 关联字段（需数据部配合）
5. Agent 4 可以输出复盘报告

### Phase 5（持续）：标签体系 + 优化
1. 推动数据部建设客户标签体系
2. 推动数据部建设酒店标签体系
3. 优化数据同步频率（从T-1到近实时）
4. 引入外部数据（竞品价格、航班运力、签证政策）

---

**最后更新**: 2026-08-11 18:45 (GMT+8)
