/** 活动类型（全系统仅三种；「临时」是录入入口，不是类型） */
window.AGENT1_ACTIVITY_TYPES = ['人工标准', 'AI创意', '其他'];

/** 录入入口标签（plan_source / entry_channel，与活动类型分流） */
window.AGENT1_ENTRY_LABEL = {
  manual_data: '人工标准规划',
  manual_standard: '人工标准规划',
  manual_ai: '人工标准规划',
  ai_creative: 'AI创意生成',
  ai_suggestion: 'AI创意生成',
  temp_entry: '中途录入',
  temp: '中途录入',
  manual_upload: '中途录入·上传',
  human_calendar: '飞书日历',
  ai_intel: '资讯补充',
};

/** 中途录入 · 标签 → 活动类型 */
window.AGENT1_TEMP_LABEL_MAP = {
  标准: '人工标准',
  创意: 'AI创意',
  其他: '其他',
};

/** Agent1 评审字段 · 对齐飞书 27年营销日历初版 */
window.AGENT1_FIELDS = {
  STANDARD: [
    { group: '活动定义', fields: [
      { key: 'session_group', label: '活动场次', path: 'basic.session_group' },
      { key: 'activity_type', label: '活动类型', path: 'basic.activity_type', default: '人工标准', readonly: true, required: true },
      { key: 'main_theme', label: '月度主活动主题', path: 'strategy.main_theme', required: true },
      { key: 'sub_theme', label: '活动名称', path: 'basic.campaign_name', required: true },
      { key: 'sub_theme_pack', label: '活动名称说明', path: 'strategy.sub_theme_pack' },
    ]},
    { group: '目的地与窗口', fields: [
      { key: 'continent', label: '目的地归属（大洲）', path: 'basic.continent', required: true },
      { key: 'country', label: '国家/地区', path: 'basic.country_region', required: true },
      { key: 'city', label: '城市', path: 'basic.city' },
      { key: 'district', label: '热门商圈', path: 'basic.district' },
      { key: 'promotion_window', label: '推广月份（对应出游/离店窗口）', path: 'basic.promotion_window' },
      { key: 'p75_days', label: '关键P75（目标离店月·天）', path: 'basic.p75_days' },
    ]},
    { group: '选题依据', fields: [
      { key: 'selection_reason', label: '选择理由·节庆/旺季数据依据', path: 'data_insights.selection_reason' },
      { key: 'tuesday_sort', label: '场内周二排序依据', path: 'strategy.tuesday_sort' },
    ]},
    { group: '排期与执行', fields: [
      { key: 'resource_handoff', label: '资源对接时间（待Rachel确认）', path: 'schedule.resource_handoff' },
      { key: 'resource_delivery', label: '资源交付时间（T-30）', path: 'schedule.resource_delivery' },
      { key: 'material_done', label: '营销物料制作完成时间（T-14）', path: 'schedule.material_done' },
      { key: 'launch_position', label: '上线位置', path: 'strategy.launch_position' },
      { key: 'launch_date', label: '活动上线时间（周二）', path: 'schedule.launch_date' },
      { key: 'promotion_period', label: '活动推广时间（起止区间）', path: 'schedule.promotion_period' },
    ]},
    { group: '收尾', fields: [
      { key: 'review_date', label: '活动复盘时间', path: 'schedule.review_date' },
    ]},
  ],
  CREATIVE: [
    { group: '活动定义', fields: [
      { key: 'session_group', label: '活动场次', path: 'basic.session_group' },
      { key: 'activity_type', label: '活动类型', path: 'basic.activity_type', default: 'AI创意', readonly: true },
      { key: 'theme_name', label: '活动主题名称', path: 'basic.campaign_name' },
      { key: 'theme_keyword', label: '活动主题词', path: 'strategy.theme_keyword' },
      { key: 'sub_theme_pack', label: '副主题包装说明', path: 'strategy.sub_theme_pack' },
    ]},
    { group: '机会论证', fields: [
      { key: 'demand_bg', label: '需求背景', path: 'background.demand_bg' },
      { key: 'business_opportunity', label: '业务契机', path: 'background.business_opportunity' },
      { key: 'data_insight', label: '数据分析洞察', path: 'data_insights.summary' },
      { key: 'opportunity_judge', label: '机会判断', path: 'data_insights.opportunity_judge' },
      { key: 'customer_profile', label: '客户群体画像', path: 'customer_segment.profile' },
      { key: 'demand_scale', label: '需求规模', path: 'data_insights.demand_scale' },
      { key: 'activity_creative', label: '活动创意（玩法/形式）', path: 'strategy.playbook' },
      { key: 'target_goal', label: '目标设定（TTV/GP/转化）', path: 'objectives.primary_goal' },
    ]},
    { group: '目的地与窗口', fields: [
      { key: 'continent', label: '目的地归属（大洲）', path: 'basic.continent' },
      { key: 'country', label: '国家/地区', path: 'basic.country_region' },
      { key: 'city', label: '城市', path: 'basic.city' },
      { key: 'district', label: '热门商圈', path: 'basic.district' },
      { key: 'promotion_window', label: '推广月份（对应出游/离店窗口）', path: 'basic.promotion_window' },
      { key: 'p75_days', label: '关键P75（目标离店月·天）', path: 'basic.p75_days' },
    ]},
    { group: '选题依据', fields: [
      { key: 'selection_reason', label: '选择理由', path: 'data_insights.selection_reason' },
      { key: 'tuesday_sort', label: '场内周二排序依据', path: 'strategy.tuesday_sort' },
    ]},
    { group: '产品与执行排期', fields: [
      { key: 'hotel_profile', label: '酒店产品画像', path: 'hotel_solution.criteria' },
      { key: 'resource_handoff', label: '资源对接时间', path: 'schedule.resource_handoff' },
      { key: 'resource_delivery', label: '资源交付时间（T-30）', path: 'schedule.resource_delivery' },
      { key: 'material_done', label: '营销物料制作完成时间（T-14）', path: 'schedule.material_done' },
      { key: 'launch_position', label: '上线位置', path: 'strategy.launch_position' },
      { key: 'launch_date', label: '活动上线时间（周二）', path: 'schedule.launch_date' },
      { key: 'promotion_period', label: '活动推广时间（起止区间）', path: 'schedule.promotion_period' },
    ]},
    { group: '收尾', fields: [
      { key: 'review_date', label: '活动复盘时间', path: 'schedule.review_date' },
    ]},
  ],
  OTHER: [
    { group: '活动定义', fields: [
      { key: 'activity_type', label: '活动类型', path: 'basic.activity_type', default: '其他', readonly: true },
      { key: 'campaign_name', label: '活动名称', path: 'basic.campaign_name' },
      { key: 'main_theme', label: '活动主题', path: 'strategy.main_theme' },
    ]},
    { group: '目的地与窗口', fields: [
      { key: 'target_dest', label: '活动目的地', path: 'basic.target_dest' },
      { key: 'promotion_window', label: '推广月份/出游窗口', path: 'basic.promotion_window' },
      { key: 'launch_date', label: '活动上线时间', path: 'schedule.launch_date' },
    ]},
    { group: '补充说明', fields: [
      { key: 'summary', label: '活动说明', path: 'background.summary' },
      { key: 'selection_reason', label: '立项理由', path: 'data_insights.selection_reason' },
    ]},
  ],
};

/** @deprecated 使用 AGENT1_ENTRY_LABEL；保留兼容 */
window.AGENT1_SOURCE_LABEL = window.AGENT1_ENTRY_LABEL;
