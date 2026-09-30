-- 5-Agent 重构：活动生命周期 + 快照 + 待办 + 档案 + 行业情报

-- 扩展 dim_campaign
ALTER TABLE dim_campaign ADD COLUMN lifecycle_status TEXT DEFAULT 'draft';
ALTER TABLE dim_campaign ADD COLUMN feishu_record_id TEXT;
ALTER TABLE dim_campaign ADD COLUMN activity_id TEXT;
ALTER TABLE dim_campaign ADD COLUMN plan_summary TEXT;
ALTER TABLE dim_campaign ADD COLUMN demand_analysis TEXT;
ALTER TABLE dim_campaign ADD COLUMN solution_analysis TEXT;
ALTER TABLE dim_campaign ADD COLUMN execution_steps TEXT;
ALTER TABLE dim_campaign ADD COLUMN target_audience TEXT;
ALTER TABLE dim_campaign ADD COLUMN key_metrics_spec TEXT;
ALTER TABLE dim_campaign ADD COLUMN delivery_mode TEXT;
ALTER TABLE dim_campaign ADD COLUMN resource_plan_json TEXT;
ALTER TABLE dim_campaign ADD COLUMN updated_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_campaign_lifecycle ON dim_campaign(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_campaign_feishu ON dim_campaign(feishu_record_id);
CREATE INDEX IF NOT EXISTS idx_campaign_activity ON dim_campaign(activity_id);

-- 行业情报报告
CREATE TABLE IF NOT EXISTS fact_industry_intel (
    intel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_title TEXT NOT NULL,
    report_type TEXT,
    source_channel TEXT,
    collect_frequency TEXT,
    report_date DATE,
    destination_tags TEXT,
    summary TEXT,
    full_content TEXT,
    activity_suggestions TEXT,
    feature_suggestions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent2 待办清单
CREATE TABLE IF NOT EXISTS fact_activity_todos (
    todo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    todo_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    is_done BOOLEAN DEFAULT 0,
    done_at TIMESTAMP,
    sort_order INTEGER DEFAULT 0,
    config_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_todos_campaign ON fact_activity_todos(campaign_id);

-- 各 Agent 阶段快照
CREATE TABLE IF NOT EXISTS fact_activity_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    snapshot_version INTEGER DEFAULT 1,
    lifecycle_status TEXT,
    payload_json TEXT NOT NULL,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_campaign ON fact_activity_snapshot(campaign_id);

-- Agent5 活动档案库
CREATE TABLE IF NOT EXISTS dim_activity_archive (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT UNIQUE NOT NULL,
    activity_id TEXT,
    activity_name TEXT NOT NULL,
    activity_type TEXT,
    destination TEXT,
    target_audience TEXT,
    lifecycle_summary TEXT,
    goal_achievement TEXT,
    problems TEXT,
    conclusions TEXT,
    reusable_points TEXT,
    avoid_points TEXT,
    full_report_json TEXT,
    success_label TEXT,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_archive_dest ON dim_activity_archive(destination);
CREATE INDEX IF NOT EXISTS idx_archive_type ON dim_activity_archive(activity_type);

-- 状态流转日志
CREATE TABLE IF NOT EXISTS fact_lifecycle_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    triggered_by TEXT,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
