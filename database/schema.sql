-- 多Agent营销协作系统 - 13张核心表
-- 兼容 SQLite / PostgreSQL

-- 1. dim_client 客户维度表
CREATE TABLE IF NOT EXISTS dim_client (
    client_id TEXT PRIMARY KEY,
    client_name TEXT,
    client_group_id INTEGER,
    client_group TEXT,
    client_group_cn TEXT,
    client_category_id INTEGER,
    parent_client_id TEXT,
    user_id TEXT,
    identity_id TEXT,
    device_id TEXT,
    first_referrer_url TEXT,
    first_referrer_page_name TEXT,
    register_date DATE,
    last_active_date DATE,
    is_test_account BOOLEAN DEFAULT 0,
    language TEXT,
    currency TEXT,
    platform TEXT,
    tag_customer_value TEXT,
    tag_activity_level TEXT,
    tag_preferred_dest TEXT,
    tag_preferred_price TEXT,
    tag_preferred_brand TEXT,
    tag_booking_freq TEXT,
    tag_churn_risk TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_client_user ON dim_client(user_id);
CREATE INDEX IF NOT EXISTS idx_dim_client_group ON dim_client(client_group_id);

-- 2. fact_events 用户行为事实表
CREATE TABLE IF NOT EXISTS fact_events (
    event_pk TEXT PRIMARY KEY,
    event_time TIMESTAMP,
    event_date DATE,
    event_hour INTEGER,
    user_id TEXT,
    client_id TEXT,
    identity_id TEXT,
    device_id TEXT,
    session_id BIGINT,
    search_session_id TEXT,
    event_type TEXT,
    page_name TEXT,
    page_url TEXT,
    referrer_page_name TEXT,
    referrer_url TEXT,
    platform TEXT,
    language TEXT,
    currency TEXT,
    dida_hotel_id BIGINT,
    dida_rpid TEXT,
    room_type BIGINT,
    room_type_name TEXT,
    bed_type INTEGER,
    meal_type TEXT,
    quote_price REAL,
    quote_currency TEXT,
    preorder_price TEXT,
    preorder_id TEXT,
    supplier_id INTEGER,
    rp_count INTEGER,
    supplier_count INTEGER,
    rp_area TEXT,
    cancellation_policy INTEGER,
    check_type TEXT,
    room_nights INTEGER,
    rank_no INTEGER,
    room_rank_no INTEGER,
    search_des_query TEXT,
    search_request_id TEXT,
    search_hoteldetail_request_id TEXT,
    search_type TEXT,
    is_quick_search BOOLEAN,
    is_realtime BOOLEAN,
    has_result BOOLEAN,
    load_time INTEGER,
    hotels_return INTEGER,
    filter_name TEXT,
    sortby TEXT,
    price_min TEXT,
    price_max TEXT,
    pricerange_min INTEGER,
    pricerange_max INTEGER,
    star_rating TEXT,
    brands TEXT,
    regions TEXT,
    city_list TEXT,
    nationality TEXT,
    checkin_date TEXT,
    checkout_date TEXT,
    adult_count INTEGER,
    child_count INTEGER,
    room_num INTEGER,
    destination_id TEXT,
    country_name TEXT,
    slide_id TEXT,
    slide_link TEXT,
    category_name TEXT,
    promotions TEXT,
    coupon_amount REAL,
    order_id TEXT,
    order_total_amount REAL,
    payment_method TEXT,
    result_code TEXT,
    result_msg TEXT,
    result_status TEXT,
    is_success BOOLEAN,
    stay_time BIGINT,
    exit_type TEXT,
    button_name TEXT,
    click_id TEXT,
    home_card_id TEXT,
    rec_request_id TEXT,
    asso_dida_hotel_id BIGINT,
    event_properties_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_events_user ON fact_events(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_client ON fact_events(client_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_type ON fact_events(event_type);
CREATE INDEX IF NOT EXISTS idx_fact_events_date ON fact_events(event_date);
CREATE INDEX IF NOT EXISTS idx_fact_events_session ON fact_events(session_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_search ON fact_events(search_session_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_hotel ON fact_events(dida_hotel_id);
CREATE INDEX IF NOT EXISTS idx_fact_events_dest ON fact_events(country_name);

-- 3. fact_funnel 漏斗事实表
CREATE TABLE IF NOT EXISTS fact_funnel (
    funnel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE,
    standard_hotel_id TEXT,
    dida_hotel_name TEXT,
    country_code TEXT,
    country_name TEXT,
    city_code TEXT,
    city_name TEXT,
    star_rating TEXT,
    destination_id TEXT,
    brand_id TEXT,
    brand_name TEXT,
    chain_id TEXT,
    chain_name TEXT,
    property_category TEXT,
    user_id TEXT,
    client_id TEXT,
    client_name TEXT,
    client_group_id INTEGER,
    client_category_id INTEGER,
    parent_client_id TEXT,
    client_group TEXT,
    client_group_cn TEXT,
    step_code TEXT,
    step_name TEXT,
    step_no INTEGER,
    pv_key TEXT,
    rp_pv_key TEXT,
    rp_valid_type TEXT,
    inventory_status TEXT,
    is_consistent TEXT,
    is_test_account BOOLEAN DEFAULT 0,
    check_in_date DATE,
    check_out_date DATE,
    adult_count INTEGER,
    child_count INTEGER,
    room_num INTEGER,
    nationality TEXT,
    etl_time TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_funnel_client ON fact_funnel(client_id);
CREATE INDEX IF NOT EXISTS idx_fact_funnel_hotel ON fact_funnel(standard_hotel_id);
CREATE INDEX IF NOT EXISTS idx_fact_funnel_step ON fact_funnel(step_code);
CREATE INDEX IF NOT EXISTS idx_fact_funnel_country ON fact_funnel(country_name);

-- 4. dim_hotel 酒店维度表
CREATE TABLE IF NOT EXISTS dim_hotel (
    standard_hotel_id TEXT PRIMARY KEY,
    dida_hotel_id BIGINT,
    dida_hotel_name TEXT,
    country_code TEXT,
    country_name TEXT,
    city_code TEXT,
    city_name TEXT,
    destination_id TEXT,
    star_rating TEXT,
    brand_id TEXT,
    brand_name TEXT,
    chain_id TEXT,
    chain_name TEXT,
    property_category TEXT,
    tag_hotel_type TEXT,
    tag_location_type TEXT,
    tag_price_level TEXT,
    tag_popularity TEXT,
    tag_competitiveness TEXT,
    tag_inventory_health TEXT,
    tag_conversion_rate TEXT,
    poi_tags TEXT,
    latitude REAL,
    longitude REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_hotel_city ON dim_hotel(city_name);
CREATE INDEX IF NOT EXISTS idx_dim_hotel_country ON dim_hotel(country_name);

-- 5. dim_campaign 营销活动维度表
CREATE TABLE IF NOT EXISTS dim_campaign (
    campaign_id TEXT PRIMARY KEY,
    campaign_name TEXT NOT NULL,
    campaign_type TEXT,
    slide_id TEXT,
    slide_link TEXT,
    category_name TEXT,
    start_date DATE,
    end_date DATE,
    target_dest TEXT,
    target_hotel_ids TEXT,
    target_client_groups TEXT,
    target_metrics TEXT,
    budget REAL,
    coupon_config TEXT,
    status TEXT DEFAULT '筹备',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. fact_campaign_metrics 活动效果事实表
CREATE TABLE IF NOT EXISTS fact_campaign_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    metric_date DATE,
    metric_hour INTEGER,
    banner_expose_count INTEGER DEFAULT 0,
    banner_click_count INTEGER DEFAULT 0,
    banner_ctr REAL,
    landing_page_pv INTEGER DEFAULT 0,
    landing_page_uv INTEGER DEFAULT 0,
    hotel_detail_pv INTEGER DEFAULT 0,
    rp_expose_count INTEGER DEFAULT 0,
    rp_click_count INTEGER DEFAULT 0,
    rp_ctr REAL,
    preorder_count INTEGER DEFAULT 0,
    payment_count INTEGER DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    success_order_count INTEGER DEFAULT 0,
    total_ttv REAL DEFAULT 0,
    total_gp REAL DEFAULT 0,
    avg_order_value REAL,
    coupon_usage_count INTEGER DEFAULT 0,
    coupon_total_amount REAL DEFAULT 0,
    funnel_request_count INTEGER DEFAULT 0,
    funnel_available_count INTEGER DEFAULT 0,
    funnel_expose_count INTEGER DEFAULT 0,
    funnel_click_count INTEGER DEFAULT 0,
    funnel_prebook_count INTEGER DEFAULT 0,
    funnel_success_count INTEGER DEFAULT 0,
    conversion_rate_expose_click REAL,
    conversion_rate_click_order REAL,
    conversion_rate_overall REAL,
    unique_clients INTEGER DEFAULT 0,
    new_clients INTEGER DEFAULT 0,
    returning_clients INTEGER DEFAULT 0,
    client_conversion_rate REAL,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_campaign_metrics_cid ON fact_campaign_metrics(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_metrics_date ON fact_campaign_metrics(metric_date);

-- 7. fact_orders 订单事实表
CREATE TABLE IF NOT EXISTS fact_orders (
    order_number TEXT PRIMARY KEY,
    client_id TEXT,
    client_name TEXT,
    client_bd TEXT,
    client_op TEXT,
    client_belong_team TEXT,
    dida_hotel_id BIGINT,
    dida_hotel_name TEXT,
    dida_hotel_chain TEXT,
    dida_hotel_star TEXT,
    country_name TEXT,
    destination_name TEXT,
    room_name TEXT,
    room_type TEXT,
    bed_type TEXT,
    board_type TEXT,
    status INTEGER,
    check_in_date DATE,
    check_out_date DATE,
    room_night_count INTEGER,
    price_cny REAL,
    net_rate_cny REAL,
    combined_revenue_cny REAL,
    kpi_revenue_cny REAL,
    is_direct_contract BOOLEAN,
    lead_time_hour INTEGER,
    create_time TIMESTAMP,
    confirm_time TIMESTAMP,
    campaign_id TEXT,
    campaign_source TEXT,
    user_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_orders_client ON fact_orders(client_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_hotel ON fact_orders(dida_hotel_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_campaign ON fact_orders(campaign_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON fact_orders(create_time);

-- 8. dim_destination_events 目的地事件/情报表
CREATE TABLE IF NOT EXISTS dim_destination_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_type TEXT,
    start_date DATE,
    end_date DATE,
    impact_level TEXT,
    expected_hotel_demand TEXT,
    target_hotel_radius INTEGER,
    target_star_rating TEXT,
    description TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. dim_holiday 节假日日历表
CREATE TABLE IF NOT EXISTS dim_holiday (
    holiday_id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    holiday_name TEXT NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_type TEXT,
    is_long_weekend BOOLEAN DEFAULT 0,
    travel_peak TEXT,
    description TEXT
);

-- 10. fact_monitor 实时监控事实表
CREATE TABLE IF NOT EXISTS fact_monitor (
    monitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    monitor_time TIMESTAMP NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    target_value REAL,
    achievement_rate REAL,
    alert_triggered BOOLEAN DEFAULT 0,
    alert_level TEXT,
    alert_message TEXT,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_monitor_cid ON fact_monitor(campaign_id);
CREATE INDEX IF NOT EXISTS idx_fact_monitor_time ON fact_monitor(monitor_time);

-- 11. dim_alert_rules 告警规则表
CREATE TABLE IF NOT EXISTS dim_alert_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    condition_type TEXT NOT NULL,
    threshold_value REAL NOT NULL,
    alert_level TEXT,
    alert_action TEXT,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

-- 12. fact_search 搜索分析事实表
CREATE TABLE IF NOT EXISTS fact_search (
    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_session_id TEXT,
    search_request_id TEXT,
    user_id TEXT,
    client_id TEXT,
    search_time TIMESTAMP,
    search_des_query TEXT,
    destination_id TEXT,
    country_name TEXT,
    checkin_date DATE,
    checkout_date DATE,
    adult_count INTEGER,
    child_count INTEGER,
    room_num INTEGER,
    nationality TEXT,
    price_min REAL,
    price_max REAL,
    star_rating TEXT,
    brands TEXT,
    sortby TEXT,
    is_quick_search BOOLEAN,
    is_realtime BOOLEAN,
    has_result BOOLEAN,
    hotels_return INTEGER,
    supplier_count INTEGER,
    load_time INTEGER,
    rp_count INTEGER,
    converted_to_order BOOLEAN DEFAULT 0,
    converted_hotel_id BIGINT
);

CREATE INDEX IF NOT EXISTS idx_fact_search_client ON fact_search(client_id);
CREATE INDEX IF NOT EXISTS idx_fact_search_dest ON fact_search(country_name);
CREATE INDEX IF NOT EXISTS idx_fact_search_query ON fact_search(search_des_query);

-- 13. fact_session 会话分析事实表
CREATE TABLE IF NOT EXISTS fact_session (
    session_id BIGINT PRIMARY KEY,
    user_id TEXT,
    client_id TEXT,
    session_start TIMESTAMP,
    session_end TIMESTAMP,
    session_duration BIGINT,
    page_views INTEGER DEFAULT 0,
    searches INTEGER DEFAULT 0,
    hotel_details INTEGER DEFAULT 0,
    rp_exposures INTEGER DEFAULT 0,
    rp_clicks INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    converted BOOLEAN DEFAULT 0,
    entry_page TEXT,
    exit_page TEXT,
    devices TEXT,
    language TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_session_user ON fact_session(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_session_client ON fact_session(client_id);

-- ETL 同步日志
CREATE TABLE IF NOT EXISTS etl_sync_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    sync_date DATE,
    status TEXT,
    rows_affected INTEGER,
    message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
