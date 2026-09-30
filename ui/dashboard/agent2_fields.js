/**
 * 活动建档 · 活动档案字段（SOP 五环节 · 环节内按业务自然顺序排列）
 * req: all | creative | launch | opt
 */
window.AGENT2_FIELDS = {
  groups: [
    {
      id: 'phase_generate',
      group: '① 活动生成环节',
      hint: '',
      fields: [
        // —— 来源与类型 ——
        { key: 'plan_source', label: '活动来源', path: 'source.plan_source', type: 'select', req: 'all',
          options: [
            { v: 'manual_standard', t: '人工标准活动' },
            { v: 'ai_creative', t: 'AI创意活动' },
            { v: 'temp_entry', t: '中途录入活动' },
          ],
          help: '区分活动从哪条链路来，决定评审表单分流与 AI 溯源展示；缺则无法追溯决策来源。' },
        { key: 'owner', label: '活动负责人', path: 'source.owner', req: 'all',
          help: '任务看板默认 @ 负责人、飞书提醒路由；缺则跨部门协同无人对接。' },
        { key: 'activity_type', label: '活动类型', path: 'basic.activity_type', req: 'all', type: 'select',
          options: [{ v: '人工标准', t: '人工标准' }, { v: 'AI创意', t: 'AI创意' }, { v: '其他', t: '其他' }],
          help: '仅三种：人工标准 / AI创意 / 其他。决定创意必填项是否触发、日历着色与任务模板。' },
        // —— 时间 ——
        { key: 'promotion_month', label: '活动推广月', path: 'basic.promotion_month', req: 'all', placeholder: '2027-09',
          help: '活动归属的规划月份，全年计划池与月历条带按此归组；缺则显示「0 场」、无法按月筛选。' },
        { key: 'launch_date', label: '活动上线时间（周二）', path: 'schedule.launch_date', req: 'all', syncIso: 'basic.start_date',
          help: '对外上线日，建议周二。保存后同步 basic.start_date，是拆任务与 SLA 的唯一锚点。' },
        // —— 主题与名称 ——
        { key: 'main_theme', label: '月度主活动主题', path: 'strategy.main_theme', req: 'all',
          help: '当月全场统一主题，日历侧栏「活动主题」筛选来源；缺则同月多场无法归组。' },
        { key: 'campaign_name', label: '活动名称', path: 'basic.campaign_name', req: 'all',
          help: '具体活动名称，常按目的地拆分，日历卡片展示名；缺则日历上无可点击标题。' },
        // —— 目的地（大 → 小 → 汇总）——
        { key: 'continent', label: '目的地归属（大洲）', path: 'basic.continent', req: 'all',
          help: '目的地层级第一层，与飞书日历字段对齐；缺则区域报表无法归类。' },
        { key: 'country_region', label: '国家/地区', path: 'basic.country_region', req: 'all',
          help: '国家/地区粒度，QBI 需求分析按国家聚合；缺则数据依据难核对。' },
        { key: 'city', label: '城市', path: 'basic.city', req: 'all',
          help: '核心城市清单，酒店选品与圈客按城拆分；缺则选品范围过大或不精准。' },
        { key: 'target_dest', label: '覆盖目的地/城市', path: 'basic.target_dest', req: 'all',
          help: '汇总目的地，Agent2 圈客/选品 MCP 按此拉数；缺则资源分析与日历「目的地」筛选为空。' },
        // —— 出游窗口 ——
        { key: 'promotion_window', label: '对应出游/离店窗口', path: 'basic.promotion_window', req: 'all', placeholder: '2027-11',
          help: '客户实际预订/离店高峰月份；资源 T-7 任务与 GP 测算窗口据此对齐。' },
        { key: 'p75_days', label: '关键 P75（目标离店月·天）', path: 'basic.p75_days', req: 'opt', placeholder: '11-18',
          help: 'P75=目标离店日第75百分位（月-日）。用于判断上线是否赶得上离店高峰，例：11-18 表示11月P75为18日。' },
        // —— 为什么做 ——
        { key: 'selection_reason', label: '选目的地数据依据·节庆/旺季', path: 'data_insights.selection_reason', req: 'all', rows: 3,
          help: 'Top/峰值/淡旺季文字依据，证明「为什么选这个目的地」；缺则评审无法论证、复盘缺立项假设。' },
        { key: 'summary', label: '立项背景摘要', path: 'background.summary', req: 'all', rows: 3,
          help: '3–5 句说明为什么现在做；缺则档案可读性差、知识库问答无摘要。' },
        // —— 预估价值 ——
        { key: 'primary_goal', label: '核心目标', path: 'objectives.primary_goal', req: 'all', rows: 2,
          help: '一句话总目标，监控与复盘判定成败的基准；缺则 T+1 总结与归档无法评估。' },
        { key: 'ttv_target', label: 'TTV 目标', path: 'objectives.ttv_target', req: 'all',
          help: '立项预估 TTV，例：100–200万；缺则达成率无法计算。' },
        { key: 'order_target', label: '订单目标', path: 'objectives.order_target', req: 'all',
          help: '立项目标订单量；缺则转化达成率无法计算。' },
        { key: 'gp_target', label: 'GP 目标', path: 'objectives.gp_target', req: 'all',
          help: '立项 GP 目标；缺则 GP 风控与 T+1 总结缺预期值。' },
        // —— 怎么做 ——
        { key: 'campaign_type', label: '交付形式', path: 'basic.campaign_type', req: 'all', type: 'select',
          options: ['Banner', 'Coupon', 'SMS', '专题页', '组合活动'].map(v => ({ v, t: v })),
          help: '决定券/展示/组合配置项；缺则后续审核不知道验收哪种交付形态。' },
        { key: 'key_mechanics', label: '活动玩法/机制', path: 'strategy.key_mechanics', req: 'all', rows: 2,
          help: '券/满减/专题等可执行机制，方案线与素材 brief 依据；缺则执行方案不可操作。' },
        { key: 'material_needs', label: '素材需求清单', path: 'strategy.material_needs', req: 'all', placeholder: 'Banner,海报,文案',
          help: '逗号分隔，每项自动生成 1 条素材任务；缺则素材线任务为 0。' },
        { key: 'launch_position', label: '上线位置', path: 'strategy.launch_position', req: 'all',
          help: '例：官网 Banner + 活动专区；缺则曝光位验收无对照。' },
        // —— 对谁做 ——
        { key: 'segment_name', label: '目标客户名称', path: 'customer_segment.segment_name', req: 'all',
          help: '客群命名，圈客 QueryProfile 展示用；缺则「对谁做」不明确。' },
        { key: 'description', label: '目标客户描述', path: 'customer_segment.description', req: 'all', rows: 3,
          help: '文字描述圈选逻辑，评审阶段填画像与条件；缺则 MCP 圈客无法构建规则。' },
        { key: 'profile', label: '客户群体画像', path: 'customer_segment.profile', req: 'creative', rows: 3,
          help: '创意类必填：结构化客群画像；缺则创意评审不完整。' },
        // —— 供给（酒店）——
        { key: 'selection_strategy', label: '酒店选品策略', path: 'hotel_solution.selection_strategy', req: 'all', rows: 2,
          help: 'Top N / 协议价优先等，MCP 选品输入；缺则供给方案不可执行。' },
        { key: 'star_min', label: '最低星级', path: 'hotel_solution.star_min', req: 'all', type: 'select', options: [{v:'',t:'不限'},{v:'1',t:'1星'},{v:'2',t:'2星'},{v:'3',t:'3星'},{v:'4',t:'4星'},{v:'5',t:'5星'}],
          help: '选品过滤条件，例：4星及以上；缺则圈品范围失控。' },
      ],
    },
    {
      id: 'phase_tasks',
      group: '② 活动任务管理环节',
      hint: '',
      appendTaskBoard: true,
      fields: [
        { key: 'start_date', label: '活动上线日（系统锚点）', path: 'basic.start_date', req: 'all',
          help: '由「活动上线时间」自动同步的 ISO 日期；缺则整板任务不生成、SLA 全部失效。' },
        { key: 'promotion_period', label: '活动推广起止', path: 'schedule.promotion_period', req: 'all', placeholder: '2027-09-14 ~ 2027-10-28',
          help: '推广可见起止区间，监控拉数时间范围据此设定。' },
        { key: 'resource_handoff', label: '资源对接时间', path: 'schedule.resource_handoff', req: 'opt',
          help: 'Rachel 确认资源对接节点；缺则资源线启动时点不明。' },
        { key: 'resource_delivery', label: '资源交付时间（T-7）', path: 'schedule.resource_delivery', req: 'opt',
          help: '上线前 7 天资源包交付，与资源线任务截止一致；缺则逾期无法预警。' },
        { key: 'material_done', label: '物料完成时间（T-14）', path: 'schedule.material_done', req: 'opt',
          help: '上线前 14 天物料齐套；缺则素材 T-2 周节点无法对齐。' },
        { key: 'qp_days', label: '圈客时间窗（天）', path: 'customer_segment.query_profile.time_window_days', req: 'all', type: 'number',
          help: '圈客 Query 默认近 N 天行为，例：90；缺则 MCP 时间窗为空。' },
        { key: 'qp_star', label: '选品最低星级', path: 'hotel_solution.query_profile.star_min', req: 'all', type: 'select', options: [{v:'',t:'不限'},{v:'1',t:'1星'},{v:'2',t:'2星'},{v:'3',t:'3星'},{v:'4',t:'4星'},{v:'5',t:'5星'}],
          help: '写入选品 QueryProfile 的星级阈值，例：4；缺则自动选品无过滤。' },
      ],
    },
    {
      id: 'phase_launch',
      group: '③ 上线审核环节',
      hint: '',
      fields: [
        { key: 'display_strategy', label: '展示策略', path: 'product_delivery.display_strategy', req: 'all', rows: 2,
          help: '首页轮播位次、专区展示规则；缺则前端/运营不知道展示规则，审核无法目视对照。' },
        { key: 'coupon_strategy', label: '优惠券策略', path: 'product_delivery.coupon_strategy', req: 'opt', rows: 2,
          help: '券类活动必填满减规则；纯 Banner 活动可空。' },
        { key: 'locked_client_ids', label: '锁定客户 ID', path: 'customer_segment.locked_client_ids', req: 'launch', type: 'ids',
          help: '确认版客户清单，萧蓉 T-7 前锁定；缺则审核不过闸、无法推送运营触达。' },
        { key: 'locked_hotel_ids', label: '锁定酒店 ID', path: 'hotel_solution.locked_hotel_ids', req: 'launch', type: 'ids',
          help: '确认版 hotel_id，GP 测算用；缺则 T-1 无法验收资源包。' },
        { key: 'landing_url', label: '落地页 URL', path: 'product_delivery.landing_url', req: 'launch',
          help: '活动专题页完整 URL；缺则 Checklist 红灯、监控无法关联页面。' },
        { key: 'tracking_events', label: '埋点/监控事件', path: 'product_delivery.tracking_events', req: 'launch',
          help: '逗号分隔 event，例：primary_banner_click；缺则 Agent3 漏斗拉数为 0。' },
        { key: 'end_date', label: '活动推广下线日', path: 'basic.end_date', req: 'launch', readonly: true,
          help: '推广结束 ISO，由推广起止同步；缺则无法自动下线。' },
      ],
    },
    {
      id: 'phase_monitor',
      group: '④ 上线监控环节',
      hint: '',
      fields: [
        { key: 'process_metrics', label: '过程监控指标', path: 'objectives.process_metrics', req: 'all', placeholder: '曝光/点击/CTR/CVR/TTV/GP',
          help: '看板维度配置，例：Banner CTR、专区 CVR；缺则过程无法评估、Agent3 看板无字段。' },
        { key: 'success_criteria', label: '成功标准', path: 'objectives.success_criteria', req: 'all', rows: 2,
          help: '例：TTV 达标且 CTR ≥ 基线 1.1x；缺则自动诊断无法 Pass/Fail。' },
        { key: 'banner_expose', label: 'Banner 曝光（实绩）', path: 'live_results.banner_expose_count', req: 'opt', readonly: true,
          help: '执行期由数仓/MCP 回写；用于监控漏斗上层，通常不需手工填。' },
        { key: 'banner_click', label: 'Banner 点击（实绩）', path: 'live_results.banner_click_count', req: 'opt', readonly: true,
          help: '执行期回写；与曝光合计算 CTR。' },
        { key: 'live_orders', label: '订单实绩', path: 'live_results.order_count', req: 'opt', readonly: true,
          help: '执行期累计订单，用于对比 order_target。' },
        { key: 'live_ttv', label: 'TTV 实绩', path: 'live_results.total_ttv', req: 'opt', readonly: true,
          help: '执行期累计 TTV，监控 Agent 定时拉数写入。' },
        { key: 'live_gp', label: 'GP 实绩', path: 'live_results.total_gp', req: 'opt', readonly: true,
          help: '执行期累计 GP，用于对比 gp_target。' },
        { key: 'live_as_of', label: '监控快照时间', path: 'live_results.as_of', req: 'opt', readonly: true,
          help: '最近一次拉数时间，判断看板数据新鲜度。' },
        { key: 'one_line_verdict', label: '异常/诊断说明', path: 'diagnosis.one_line_verdict', req: 'opt', rows: 2,
          help: '监控 Agent 异常时的一句话结论，例：CTR 低于基线需优化素材。' },
      ],
    },
    {
      id: 'phase_archive',
      group: '⑤ 复盘归档环节',
      hint: '活动结束后复盘、沉淀经验，反哺下一轮活动生成',
      fields: [
        { key: 'review_date', label: '活动复盘时间', path: 'schedule.review_date', req: 'opt',
          help: '建议结束后 7 天，例：2027-11-04；缺则复盘任务无法自动提醒。' },
        { key: 'actual_ttv', label: '实际 TTV（归档）', path: 'archive.actual_ttv', req: 'opt',
          help: '复盘定稿实绩，可与 live_results 对齐写入档案库。' },
        { key: 'actual_gp', label: '实际 GP（归档）', path: 'archive.actual_gp', req: 'opt',
          help: '复盘定稿 GP，供 GP 复盘与风控回溯。' },
        { key: 'actual_orders', label: '实际订单（归档）', path: 'archive.actual_orders', req: 'opt',
          help: '复盘定稿订单数，与立项 order_target 对比。' },
        { key: 'achievement_rate', label: '目标达成率', path: 'archive.achievement_rate', req: 'opt', placeholder: 'TTV 达成 112%',
          help: '例：TTV 达成 112%；缺则档案库无法按达成率检索。' },
        { key: 'root_causes', label: '根因分析', path: 'diagnosis.root_causes', req: 'opt', rows: 2, type: 'ids',
          help: '结构化根因列表，逗号分隔；用于归因（供给/客群/素材/节奏）。' },
        { key: 'human_conclusion', label: '人工复盘结论', path: 'archive.human_conclusion', req: 'opt', rows: 3,
          help: '运营师定稿结论，归档闸门人工验收项。' },
        { key: 'experience', label: '可复用经验', path: 'archive.experience', req: 'opt', rows: 2,
          help: '下一场活动可复用的做法，写入知识库反哺 Agent1。' },
        { key: 'pitfalls', label: '规避点', path: 'archive.pitfalls', req: 'opt', rows: 2,
          help: '踩坑记录，Agent1 检索历史档案时展示「规避」。' },
      ],
    },
  ],
};

window.isCreativeArchive = function isCreativeArchive(plan) {
  const t = String(plan?.basic?.activity_type || '');
  return t === 'AI创意' || t.includes('创意');
};

window.getPlanPath = function getPlanPath(plan, path) {
  const v = String(path || '').split('.').reduce((o, k) => (o && o[k] != null ? o[k] : ''), plan);
  if (path === 'diagnosis.root_causes' && Array.isArray(v)) return v.join(', ');
  return v ?? '';
};

window.setPlanPath = function setPlanPath(plan, path, val) {
  const keys = String(path || '').split('.');
  let o = plan;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!o[keys[i]] || typeof o[keys[i]] !== 'object') o[keys[i]] = {};
    o = o[keys[i]];
  }
  const last = keys[keys.length - 1];
  if (path.endsWith('_ids') || path.includes('locked_') || path === 'diagnosis.root_causes') {
    o[last] = String(val || '').split(/[,，\s]+/).map(s => s.trim()).filter(Boolean);
  } else {
    o[last] = val;
  }
};
