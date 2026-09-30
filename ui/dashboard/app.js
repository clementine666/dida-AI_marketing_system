/** 道旅营销协作系统 — 内网工作台 */
const App = {
  API: '',
  view: 'home',
  tab: 'work',
  data: {},
  agentConfig: {},
  review: null, // { type: 'campaign'|'suggestion', id, data, confirmed }
  agent1Focus: null, // proposal | prep | ready | executing | annual
  qbiTab: 'timing',
  adminTab: 'modules',
  adminPromptKey: null,
  configTab: 'infra',
  agent1ConfigSub: 'manual',
  agent1GenSub: 'manual',
  agent1ReviewMonth: null,
  agent1ReviewMonths: [],
  agent1AnnualMonth: new Date().getMonth() + 1,
  agent1PlanningYear: 2027,
  agent2Year: 2027,
  agent2Month: new Date().getMonth() + 1,
  agent2Day: null,
  agent2SidebarMode: 'date',
  agent2FilterTypes: [],
  agent2FilterThemes: [],
  agent2ScrollTask: null,
  agent2CalView: 'month',
  agent2Search: '',
  manualCalendarResult: null,
  agent1CreativePreview: null,
  lastApiError: null,
  selectedTicketId: null,
  feedbackSummary: null,

  AGENT_CONFIG_META: {
    agent1: { label: '① 活动生成Agent', sub: '标准活动 · 人工上传 · AI创意 · 资讯补充', phase: 1 },
    agent2: { label: '② 活动建档Agent', sub: '终版日历 · 档案补全', phase: 2, promptKey: 'archive_field_spec' },
    agent3: { label: '③ 任务监督Agent', sub: '任务模板 · 催办规则', phase: 3, promptKey: 'task_templates' },
    agent4: { label: '④ 上线审核Agent', sub: '预上线 Checklist', phase: 4, promptKey: 'launch_checklist' },
    agent5: { label: '⑤ 监控优化Agent', sub: '监控字段 · 看板格式', phase: 5, promptKey: 'monitor_fields' },
    agent6: { label: '⑥ 复盘归档Agent', sub: '复盘模板 · 归档规范', phase: 6, promptKey: 'review_template' },
  },

  SOP_PHASES: [
    { n: 1, name: '营销活动策划和评审', agent: 'agent1', agentLabel: '活动生成Agent', biz: '标准/创意定义 → 评审池 → 终审日历', sys: 'proposal → adopted · 评审池 · 占位提示词', steps: ['1.1 活动生成', '1.2 评审池', '1.3 AI初审', '1.4 初版日历', '1.5 跨部门终审'] },
    { n: 2, name: '建档和任务创建', agent: 'agent2', agentLabel: '活动建档Agent', biz: '跨部门终版日历 · 档案补全', sys: 'activity_id · 主档 · 营销日历看板', steps: ['2.1 活动建档', '2.2 全年营销日历看板'] },
    { n: 3, name: '活动任务进展管理', agent: 'agent3', agentLabel: '任务监督Agent', biz: '资源/素材/营销三线 · 催办 · 验收', sys: '任务板 · 飞书催办 · 未完成回退', steps: ['3.1 任务配置', '3.2 执行任务', '3.3 任务催办', '3.4 验收'] },
    { n: 4, name: '活动预上线审核', agent: 'agent4', agentLabel: '上线审核Agent', biz: 'T-1 提醒 · 预上线 Checklist', sys: '提醒 · Checklist占位 · 风险分级', steps: ['4.1 提醒审核', '4.2 预上线审核'] },
    { n: 5, name: '上线监控与效果推送', agent: 'agent5', agentLabel: '监控优化Agent', biz: '上线 · 看板 · T+1总结 · 下线复盘', sys: 'live · 看板 · 次日推送', steps: ['5.1 活动上线', '5.2 数据看板', '5.3 监控总结', '5.4 下线复盘'] },
    { n: 6, name: '档案库管理', agent: 'agent6', agentLabel: '复盘归档Agent', biz: '沉淀知识库 · Agent 问答', sys: 'archive · RAG反哺策划', steps: ['6.1 沉淀知识库', '6.2 知识库问答'] },
  ],

  DEMO_LIFECYCLE: [
    { phase: 1, label: '评审池', status: 'adopted', view: 'agent1' },
    { phase: 2, label: '建档', status: 'archived', view: 'agent2' },
    { phase: 3, label: '任务执行', status: 'prep', view: 'agent3' },
    { phase: 4, label: 'T-1审核', status: 'ready', view: 'agent4' },
    { phase: 5, label: '监控中', status: 'live', view: 'agent5' },
    { phase: 6, label: '待归档', status: 'closed', view: 'agent6' },
  ],

  async init() {
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', () => this.navigate(el.dataset.view === 'calendar-portal' ? 'agent1' : el.dataset.view, el.dataset.view === 'calendar-portal' ? { tab: 'generate', agent1GenSub: 'manual' } : {}));
    });
    await this.refresh();
    this.navigate('home');
  },

  async refresh() {
    try {
      const [overview, mcp, feishu, agents] = await Promise.all([
        this.fetch('/api/v2/config/overview'),
        this.fetch('/api/v2/config/mcp'),
        this.fetch('/api/v2/feishu/calendar/status'),
        this.fetch('/api/v2/config/agents'),
      ]);
      this.data.overview = overview;
      this.data.mcp = mcp;
      this.data.feishu = feishu;
      this.agentConfig = agents;
      const py = agents?.agent1?.manual_calendar?.planning_year;
      if (py) {
        this.agent1PlanningYear = py;
        if (!this.agent2Year || this.agent2Year === 2027) this.agent2Year = py;
      }
      try {
        this.feedbackSummary = await this.fetch('/api/v2/feedback/summary');
      } catch (_) {
        this.feedbackSummary = null;
      }
      this.updateStatusPills(mcp, feishu);
      const badge = document.getElementById('badge-agent1');
      if (badge) badge.textContent = overview.proposal_library_pending ?? overview.ai_suggestions_pending ?? '0';
    } catch (e) {
      console.error(e);
    }
  },

  updateStatusPills(mcp, feishu) {
    const wh = document.getElementById('mcp-status-pill');
    const fs = document.getElementById('feishu-status-pill');
    if (wh) {
      const live = mcp?.warehouse?.mode === 'warehouse_mcp';
      wh.className = 'status-pill' + (live ? '' : ' warn');
      wh.innerHTML = `<span class="status-dot"></span> 数仓 ${live ? 'MCP 已连接' : 'Mock'}`;
    }
    if (fs) {
      const live = feishu?.mode === 'live';
      fs.className = 'status-pill' + (live ? '' : ' warn');
      fs.innerHTML = `<span class="status-dot"></span> 飞书 ${live ? '已连接' : 'Mock'}`;
    }
  },

  async fetch(path, opts = {}) {
    const r = await fetch(this.API + path, opts);
    if (!r.ok) {
      const text = await r.text();
      this.lastApiError = { path, status: r.status, message: text, at: new Date().toISOString() };
      if (r.status === 404 && path.includes('plan-structured')) {
        throw new Error('评审接口未就绪，请重启 API 服务（py -3.11 -m app.main）后刷新页面');
      }
      throw new Error(text || `HTTP ${r.status}`);
    }
    return r.json();
  },

  _moduleFromView(view) {
    if (!view || view === 'home') return 'home';
    if (view.startsWith('agent')) return view;
    return view;
  },

  openFeedbackModal() {
    const el = document.getElementById('feedback-modal');
    if (!el) return;
    const ph = this.SOP_PHASES.find(p => p.agent === this.view);
    const ctx = `当前：${ph ? ph.name : this.view}${this.tab ? ' · ' + this.tab : ''}`;
    const hint = document.getElementById('fb-context-hint');
    if (hint) {
      hint.textContent = `将自动附带：${ctx}${this.lastApiError ? ' · 含最近一次报错' : ''}`;
    }
    el.style.display = 'flex';
  },

  closeFeedbackModal() {
    const el = document.getElementById('feedback-modal');
    if (el) el.style.display = 'none';
  },

  async submitFeedback() {
    const reporter = document.getElementById('fb-reporter')?.value?.trim();
    const title = document.getElementById('fb-title')?.value?.trim();
    if (!reporter || !title) {
      alert('请填写姓名和问题标题');
      return;
    }
    const body = {
      reporter,
      title,
      description: document.getElementById('fb-desc')?.value || '',
      expected_behavior: document.getElementById('fb-expected')?.value || '',
      severity: document.getElementById('fb-severity')?.value || 'normal',
      module: this._moduleFromView(this.view),
      page_view: this.view,
      tab_name: this.tab,
      context: {
        page_title: document.getElementById('page-title')?.textContent,
        last_api_error: this.lastApiError,
        user_agent: navigator.userAgent,
        submitted_at: new Date().toISOString(),
      },
    };
    try {
      const r = await this.fetch('/api/v2/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      this.closeFeedbackModal();
      alert(`反馈已提交\n工单号：${r.feedback?.ticket_no || '—'}\n后台会排查处理，可在系统通用配置→问题工单查看进度。`);
      document.getElementById('fb-title').value = '';
      document.getElementById('fb-desc').value = '';
      document.getElementById('fb-expected').value = '';
    } catch (e) {
      alert('提交失败：' + (e.message || '未知错误'));
    }
  },

  encId(id) {
    return encodeURIComponent(id || '');
  },

  escAttr(v) {
    return String(v || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  },

  isDemoCampaign(name) {
    return /F1|新加坡/i.test(String(name || ''));
  },

  demoLaneTasks(activityName) {
    const act = activityName || '新加坡F1赛事酒店预订';
    return {
      resource: [
        { title: '淡旺季预订高峰分析', owner: '萧蓉', status: 'done', meta: 'QBI · 建议 9 月上线' },
        { title: 'TOP 酒店 / 城市需求', owner: '萧蓉', status: 'doing', meta: '主打 Marina Bay 周边' },
        { title: 'DC/TPS 确认参与意愿', owner: '萧蓉', status: 'todo', meta: '线下回填酒店 ID' },
      ],
      plan: [
        { title: '活动主题与玩法确认', owner: 'JIM', status: 'review', meta: `归属方案线 · ${act}` },
        { title: '上线位置确认', owner: 'JIM', status: 'todo', meta: 'Banner / 专题页' },
        { title: '目标与监控字段确认', owner: '侯颖新', status: 'todo', meta: '曝光 CTR CVR GP' },
      ],
      material: [
        { title: '官网 Banner', owner: '梓淮', status: 'doing', meta: '独立素材线，不嵌在方案卡片内' },
        { title: '落地页海报', owner: '梓淮', status: 'todo', meta: '交付 T-1' },
        { title: '朋友圈物料', owner: '梓淮', status: 'todo', meta: '尺寸 + 文案' },
      ],
    };
  },

  laneStatusTag(status) {
    return {
      done: '<span class="badge-sm ok">已完成</span>',
      doing: '<span class="badge-sm info">进行中</span>',
      review: '<span class="badge-sm warn">待验收</span>',
      todo: '<span class="badge-sm">待办</span>',
    }[status] || '<span class="badge-sm">待办</span>';
  },

  kanbanColHtml(title, icon, tasks) {
    const cards = (tasks || []).map(t => `
      <div class="kanban-card">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
          <strong>${t.title}</strong>${this.laneStatusTag(t.status)}
        </div>
        <div class="meta">${t.owner || '—'} · ${t.meta || ''}</div>
      </div>`).join('');
    const materialAction = title === '素材' ? `<button class="btn btn-primary material-ai-poster-btn" onclick="App.openPosterGenerator()">AI 生成海报</button>` : '';
    return `<div class="kanban-col">
      <div class="kanban-col-head"><span>${icon} ${title}</span><span class="funnel-count">${(tasks || []).length}</span></div>
      ${materialAction}
      ${cards || '<div class="empty" style="padding:20px">暂无任务</div>'}
    </div>`;
  },

  openPosterGenerator() {
    const configured = !!this.data?.integrations?.image_gen?.api_key_set;
    if (!configured) {
      if (confirm('尚未配置生图 / 海报 AI 工具，是否前往系统配置？')) this.navigate('system-config', { configTab: 'infra' });
      return;
    }
    document.getElementById('poster-generator-modal')?.remove();
    const modal = document.createElement('div');
    modal.id = 'poster-generator-modal';
    modal.className = 'poster-modal-backdrop';
    modal.innerHTML = `<div class="poster-modal" role="dialog" aria-modal="true">
      <div class="poster-modal-head"><div><h3>AI 生成海报</h3><p>素材线 · 活动海报生成</p></div><button class="poster-close" onclick="document.getElementById('poster-generator-modal').remove()">×</button></div>
      <div class="poster-modal-body"><div class="poster-chat-history"><div class="poster-ai-msg">你好，我可以根据活动主题、目标人群和视觉要求生成海报。请告诉我你想要的效果。</div></div>
        <label>生成提示词 <span class="req">*</span><textarea id="poster-prompt" rows="4" placeholder="例如：为新加坡 F1 酒店预订活动生成一张年轻、动感、突出限时优惠的横版海报"></textarea></label>
        <div class="poster-form-row"><label>尺寸<select id="poster-size"><option>1200×628 横版</option><option>1080×1440 竖版</option><option>1080×1080 方形</option></select></label><label>视觉风格<select id="poster-style"><option>品牌营销</option><option>简约高级</option><option>活泼旅行</option><option>节日促销</option></select></label></div>
        <div id="poster-result" class="poster-result"><span>生成后的海报将在这里预览</span></div>
      </div><div class="poster-modal-foot"><button class="btn" onclick="document.getElementById('poster-generator-modal').remove()">取消</button><button class="btn btn-primary" onclick="App.generatePosterPreview()">生成海报</button></div>
    </div>`;
    document.body.appendChild(modal);
  },

  generatePosterPreview() {
    const prompt = document.getElementById('poster-prompt')?.value?.trim();
    if (!prompt) { alert('请先填写生成提示词'); return; }
    const result = document.getElementById('poster-result');
    if (result) result.innerHTML = `<div class="poster-generating">AI 正在生成海报预览…</div>`;
    setTimeout(() => { if (result) result.innerHTML = `<div class="poster-mock-result"><strong>海报预览</strong><span>${this.escHtml(prompt)}</span><small>可继续修改提示词后重新生成，确认后进入素材预览。</small></div>`; }, 700);
  },

  growthGapsFromForm() {
    const empty = v => !String(v || '').trim();
    const gaps = [];
    if (empty(document.getElementById('rv-data-concl')?.value) && empty(document.getElementById('rv-data-market')?.value)) {
      gaps.push('数据依据');
    }
    if (empty(document.getElementById('rv-obj-metrics')?.value) && empty(document.getElementById('rv-obj-primary')?.value)) {
      gaps.push('活动目标');
    }
    if (empty(document.getElementById('rv-obj-process')?.value) && empty(document.getElementById('rv-ex-mon')?.value)) {
      gaps.push('过程监控指标');
    }
    return gaps;
  },

  growthWarnHtml(gaps) {
    const list = gaps && gaps.length ? gaps : ['数据依据', '活动目标', '过程监控指标'];
    return `<div class="callout growth-warn" id="growth-warn-box">
      建议补充<strong>${list.join('、')}</strong>，否则无法评估活动是否达成。仍可采纳，进入全年计划池。
    </div>`;
  },

  refreshGrowthWarn() {
    const box = document.getElementById('growth-warn-box');
    if (!box) return;
    const gaps = this.growthGapsFromForm();
    box.style.display = gaps.length ? '' : 'none';
    if (gaps.length) {
      box.innerHTML = `建议补充<strong>${gaps.join('、')}</strong>，否则无法评估活动是否达成。仍可采纳，进入全年计划池。`;
    }
  },

  goBucket(bucket) {
    if (bucket === 'ready') return this.navigate('agent4');
    if (bucket === 'executing') return this.navigate('agent5');
    if (bucket === 'annual') return this.navigate('agent1', { tab: 'annual' });
    if (bucket === 'proposal') return this.navigate('agent1', { tab: 'work' });
    this.agent1Focus = bucket;
    this.navigate('agent1');
  },

  scrollToBucketFocus() {
    const focus = this.agent1Focus;
    if (!focus || this.view !== 'agent1') return;
    const id = {
      proposal: 'bucket-proposal',
      prep: 'bucket-prep',
      ready: 'bucket-ready',
      executing: 'bucket-executing',
      annual: 'bucket-annual',
    }[focus];
    this.agent1Focus = null;
    if (!id) return;
    requestAnimationFrame(() => {
      const target = document.getElementById(id);
      if (target) {
        target.classList.add('bucket-focus');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setTimeout(() => target.classList.remove('bucket-focus'), 2500);
      }
    });
  },

  navigate(view, opts = {}) {
    if (view === 'mcp-config') {
      view = 'system-config';
      if (!opts.configTab) opts.configTab = 'infra';
    } else if (view === 'system-admin') {
      view = 'system-config';
      if (!opts.configTab) {
        if (opts.adminTab === 'logs') opts.configTab = 'logs';
        else if (opts.adminTab === 'prompts') opts.configTab = 'agent1';
        else opts.configTab = 'modules';
      }
      if (opts.promptKey) {
        opts.configTab = 'agent1';
        opts.agent1Sub = ['manual_plan_sop', 'manual_theme', 'manual_calendar_ai'].includes(opts.promptKey) ? 'manual'
          : opts.promptKey === 'ai_creative' ? 'creative' : undefined;
      }
    }
    this.view = view;
    this.tab = opts.tab || 'work';
    if (opts.configTab) this.configTab = opts.configTab;
    if (opts.agent1Sub) this.agent1ConfigSub = opts.agent1Sub;
    if (opts.agent1GenSub) this.agent1GenSub = opts.agent1GenSub;
    if (opts.tab === 'manual-plan') {
      this.tab = 'generate';
      this.agent1GenSub = 'manual';
    }
    document.querySelectorAll('.nav-item').forEach(el => {
      const calendarAlias = view === 'agent1' && el.dataset.view === 'calendar-portal';
      el.classList.toggle('active', el.dataset.view === view || calendarAlias);
    });
    const titles = {
      home: ['系统首页', '快捷入口 · 全局概览 · 6-Agent v6'],
      'project-overview': ['主流程与四个扩展模块', '营销日历为主流程 · 其他四个模块按业务关系接入'],
      promotion: ['高请求低转化 Promotion', '每周实验 · MCP 数仓取数 · 酒店分组 · 人工审核'],
      'calendar-portal': ['营销日历', 'S1-S8 全流程工作台'],
      'tps-placeholder': ['TPS资源营销', '模块预留 · 当前版本暂不展开'],
      'dc-placeholder': ['DC上新宣发', '模块预留 · 当前版本暂不展开'],
      'sop-map': ['SOP 业务对照', '六阶段流程 · 业务逻辑 ↔ 系统模块 · 演示导航'],
      agent1: ['活动生成Agent', '阶段① · 活动生成 → 评审池 → 全年计划池'],
      agent2: ['活动建档Agent', '阶段② · 终版营销日历 · 完善活动档案'],
      agent3: ['任务监督Agent', '阶段③ · 三列看板：资源 / 方案 / 素材 · 催办验收'],
      agent4: ['上线审核Agent', '阶段④ · T-1 提醒 · 预上线 Checklist'],
      agent5: ['监控优化Agent', '阶段⑤ · 看板 · T+1 总结 · 优化建议'],
      agent6: ['复盘归档Agent', '阶段⑥ · 复盘 · 知识库 · 反哺策划'],
      'system-config': ['系统通用配置', '通用底座 · MCP / AI模型 / 飞书Bot / 生图工具'],
      'system-admin': ['系统通用配置', '通用底座 · MCP / AI模型 / 飞书Bot / 生图工具'],
      'mcp-config': ['系统通用配置', '通用底座 · MCP / AI模型 / 飞书Bot / 生图工具'],
      'calendar-upload': ['营销日历预览', '查看飞书同步结果（配置请在「系统通用配置」）'],
      'intel-hub': ['情报输入 · 营销策划', '采集任务 · 上传报告 · LLM 生成 AI 创意池'],
      'case-library': ['活动案例库', '历史活动档案 · 复盘归档Agent 知识库'],
    };
    const [t, s] = titles[view] || ['', ''];
    document.getElementById('page-title').textContent = t;
    document.getElementById('page-sub').textContent = s;
    this.render();
  },

  setTab(tab, sub) {
    this.tab = tab;
    if (sub) this.agent1GenSub = sub;
    this.render();
  },

  setAgent1GenSub(sub) {
    this.agent1GenSub = sub;
    this.tab = 'generate';
    this.render();
  },

  async render() {
    const el = document.getElementById('main-content');
    el.classList.remove('calendar-flow-layout');
    el.innerHTML = '<div class="loading">加载中…</div>';
    try {
      const html = await this.renderView(this.view);
      el.innerHTML = html;
      if (/^agent[1-6]$/.test(this.view)) this.wrapCalendarWorkspace(el);
      this.bindEvents();
      this.bindCalendarDropzone();
      this.scrollToBucketFocus();
    } catch (e) {
      el.innerHTML = `<div class="callout warn">加载失败：${e.message}<br>请确认 API 服务已启动（python -m app.main）</div>`;
    }
  },

  wrapCalendarWorkspace(el) {
    if (el.querySelector('.calendar-flow-rail')) return;
    const steps=[['S1-2','活动生成与评审','agent1'],['S3','活动建档','agent2'],['S4','任务监督','agent3'],['S5','上线审核','agent4'],['S6-7','监控与复盘','agent5'],['S8','归档沉淀','agent6']];
    const rail=document.createElement('aside'); rail.className='calendar-flow-rail';
    const planningYear = Number(this.agent1PlanningYear || 2027);
    const yearOptions = Array.from({length: 276}, (_, i) => 2025 + i).map(y => `<option value="${y}" ${y === planningYear ? 'selected' : ''}>${y}</option>`).join('');
    rail.innerHTML='<div class="calendar-year-picker"><label>规划归属年<select onchange="App.setAgent1PlanningYear(this.value)">'+yearOptions+'</select></label></div><div class="calendar-steps-title">营销日历流程</div>'+steps.map(s=>`<button class="calendar-step ${s[2]===this.view?'active':''}" onclick="App.navigate('${s[2]}')"><b>${s[1]}</b>${s[2]==='agent3'?'<small>含强化营销任务</small>':''}</button>`).join('');
    const body=document.createElement('section'); body.className='calendar-flow-page'; while(el.firstChild) body.appendChild(el.firstChild); el.appendChild(rail); el.appendChild(body); el.classList.add('calendar-flow-layout');
  },

  tabsHtml(agentKey = null) {
    const banner = agentKey ? this.phaseBannerHtml(agentKey) : '';
    return `${banner}<div class="tabs">
      <button class="tab ${this.tab === 'work' ? 'active' : ''}" onclick="App.setTab('work')">工作结果</button>
    </div>`;
  },

  agent1TabsHtml() {
    const sub = this.agent1GenSub || 'manual';
    const subTabs = this.tab === 'generate' ? `<span class="agent1-inline-subtabs"><button class="tab ${sub === 'manual' ? 'active' : ''}" onclick="App.setAgent1GenSub('manual')">人工标准活动</button><button class="tab ${sub === 'creative' ? 'active' : ''}" onclick="App.setAgent1GenSub('creative')">AI创意活动</button><button class="tab ${sub === 'temp' ? 'active' : ''}" onclick="App.setAgent1GenSub('temp')">中途活动录入</button></span>` : '';
    return `${this.phaseBannerHtml('agent1')}<div class="tabs agent1-main-tabs-inline">
      <button class="tab ${this.tab === 'generate' ? 'active' : ''}" onclick="App.setTab('generate')">① 活动生成</button>
      ${subTabs}
      <button class="tab ${this.tab === 'work' ? 'active' : ''}" onclick="App.setTab('work')">② 评审池</button>
      <button class="tab ${this.tab === 'annual' ? 'active' : ''}" onclick="App.setTab('annual')">③ 全年计划池</button>
    </div>`;
  },

  async downloadAnnualCalendar() {
    const btn = document.querySelector('.agent1-download-btn');
    if (btn) { btn.disabled = true; btn.textContent = '导出中…'; }
    try {
      const r = await fetch(this.API + '/api/v2/agent1/annual-calendar/export');
      if (!r.ok) {
        const text = await r.text();
        throw new Error(text || `HTTP ${r.status}`);
      }
      const blob = await r.blob();
      const dispo = r.headers.get('Content-Disposition') || '';
      const m = dispo.match(/filename="([^"]+)"/);
      const filename = m ? decodeURIComponent(m[1]) : `营销日历_${this.agent1PlanningYear || new Date().getFullYear()}全年.csv`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('下载失败：' + (e.message || e));
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '📥 下载营销日历'; }
    }
  },

  agent1GenSubTabsHtml() {
    const sub = this.agent1GenSub || 'manual';
    return `<div class="tabs agent1-config-tabs" style="margin:12px 0 16px;flex-wrap:wrap">
      <button class="tab ${sub === 'manual' ? 'active' : ''}" onclick="App.setAgent1GenSub('manual')">人工标准活动</button>
      <button class="tab ${sub === 'creative' ? 'active' : ''}" onclick="App.setAgent1GenSub('creative')">AI创意活动</button>
      <button class="tab ${sub === 'temp' ? 'active' : ''}" onclick="App.setAgent1GenSub('temp')">中途活动录入</button>
    </div>`;
  },

  async renderView(view) {
    const map = {
      'project-overview': () => this.renderProjectOverview(),
      promotion: () => this.renderPromotionDemo(),
      'calendar-portal': () => this.renderCalendarPortal(),
      'tps-placeholder': () => this.renderModulePlaceholder('TPS资源营销', '促销资源匹配与执行模块将在后续版本接入。'),
      'dc-placeholder': () => this.renderModulePlaceholder('DC上新宣发', '上新识别、宣发策略与素材流程将在后续版本接入。'),
      home: () => this.renderHome(),
      'sop-map': () => this.renderSopMap(),
      agent1: () => this.renderAgent1(),
      agent2: () => this.renderAgent2(),
      agent3: () => this.renderAgent3(),
      agent4: () => this.renderAgent4(),
      agent5: () => this.renderAgent5(),
      agent6: () => this.renderAgent6(),
      'system-config': () => this.renderSystemConfig(),
      'system-admin': () => this.renderSystemConfig(),
      'mcp-config': () => this.renderSystemConfig(),
      'calendar-upload': () => this.renderCalendarUpload(),
      'intel-hub': () => this.renderIntelHub(),
      'case-library': () => this.renderCaseLibrary(),
    };
    return (map[view] || map.home)();
  },

  renderProjectOverview() {
    return `
      <div class="page-head"><div><h3>营销全链路 AI 自动化</h3><p class="muted">当前版本已完整复制子流程一营销日历 Demo 的功能模块；后续以本目录为唯一维护版本。</p></div></div>
      <div class="callout info"><b>产品层级</b>　营销日历是第一个主流程（S1-S8）。高需求高转化强化营销已归入 S4 任务树；高需求低转化 Promotion、TPS、DC 暂保留为独立模块入口，关系待确认。</div>
      <div class="grid grid-3" style="margin-top:18px">
        <div class="card entry-card card-body" onclick="App.navigate('agent1')"><h3>① 营销日历全流程</h3><p>Agent 1-6：活动生成、建档、任务监督、上线审核、监控优化、复盘归档。</p><span class="badge badge-green">已接入完整 Demo</span></div>
        <div class="card entry-card card-body" onclick="App.navigate('agent3')"><h3>S4 · 高需求高转化</h3><p>作为任务树中的一类强化营销任务，由任务监督 Agent 编排、分派和催办。</p><span class="badge">已确认归属 S4</span></div>
        <div class="card entry-card card-body"><h3>② 高需求低转化</h3><p>保留独立模块入口，等待确认是独立触发还是由营销日历调用。</p><span class="badge badge-warn">关系待确认</span></div>
        <div class="card entry-card card-body"><h3>④ TPS 促销资源</h3><p>保留促销资源匹配和执行入口，后续接入实际流程。</p><span class="badge badge-warn">关系待确认</span></div>
        <div class="card entry-card card-body"><h3>⑤ DC 上新宣发</h3><p>保留上新识别、宣发策略和素材流程入口。</p><span class="badge badge-warn">关系待确认</span></div>
        <div class="card entry-card card-body" onclick="App.navigate('system-config')"><h3>公共底座与集成</h3><p>数据、Agent 配置、飞书/数仓连接、系统日志和现有 Marketing 系统对接。</p><span class="badge">系统配置</span></div>
      </div>`;
  },

  renderCalendarPortal() {
    const steps=[['S1-2','活动生成与评审','agent1'],['S3','活动建档','agent2'],['S4','任务监督','agent3'],['S5','上线审核','agent4'],['S6-7','监控与复盘','agent5'],['S8','归档沉淀','agent6']];
    return `<div class="calendar-portal-head"><div><h3>营销日历</h3><p class="muted">从活动规划到复盘归档的完整流程</p></div></div><div class="calendar-workspace"><aside class="calendar-steps"><div class="calendar-steps-title">营销日历流程</div>${steps.map((s,i)=>`<button class="calendar-step ${i===0?'active':''}" onclick="App.navigate('${s[2]}')"><b>${s[1]}</b>${s[2]==='agent3'?'<small>含强化营销任务</small>':''}</button>`).join('')}</aside><section class="calendar-main"><div class="card card-body"><h3>营销日历工作台</h3><p>请选择左侧流程进入对应工作区。</p><div class="grid grid-3" style="margin-top:18px"><div class="card"><div class="lbl">全年活动计划</div><div class="val">—</div></div><div class="card"><div class="lbl">待人工审核</div><div class="val">—</div></div><div class="card"><div class="lbl">进行中活动</div><div class="val">—</div></div></div></div></section></div>`;
  },

  renderModulePlaceholder(title, desc) {
    return `<div class="module-placeholder"><div class="card card-body"><h3>${title}</h3><p class="muted">${desc}</p><span class="badge badge-warn">暂未开放</span></div></div>`;
  },

  renderPromotionDemo() {
    setTimeout(()=>this.promoMergeSqlBox(),0);
    return `
      <div class="page-head promotion-page-head"><div><h3>高请求低转化酒店 Promotion</h3></div><nav class="promotion-subnav"><button class="promotion-subnav-item active" onclick="App.promotionSubpage('schedule')">定时取数与筛选</button><button class="promotion-subnav-item" onclick="App.promotionSubpage('activity')">促销活动</button></nav></div>
      <section id="promotion-schedule-section" class="promotion-schedule-section">
        <div class="promotion-schedule-bar card"><div class="card-head"><h3>定时取数与筛选</h3></div><div class="promotion-config-grid"><label>数据源<select id="promo-data-source" class="form-control"><option>系统默认 DataMCP</option><option>测试 DataMCP</option></select></label><label>取数频率<select id="promo-frequency" class="form-control"><option>每周</option><option>每天</option><option>每月</option></select></label><label>执行时间<input id="promo-run-time" type="datetime-local" class="form-control" value="2026-09-29T09:30"></label><label>数据窗口<select id="promo-window" class="form-control"><option>最近 30 天</option><option>最近 60 天</option><option>最近 90 天</option></select></label><label>运行模式<select id="promo-run-mode" class="form-control"><option>正式运行</option><option>模拟运行</option></select></label></div><div class="promotion-schedule-actions"><button class="btn btn-primary" onclick="App.savePromotionConfig()">保存配置</button><button class="btn btn-primary" onclick="App.runPromotionOnce()">立即执行</button><button class="btn" onclick="document.getElementById('promo-run-log')?.scrollIntoView({behavior:'smooth'})">查看取数日志</button><button class="btn" onclick="App.navigate('system-config',{configTab:'infra'})">DataMCP 配置</button></div><div id="promo-run-log" class="promo-run-log">最近执行：尚未执行 · 等待定时任务</div></div>
        <div class="promotion-schedule-content">${this.promoSqlHtml()}${this.promoRunHtml()}</div>
      </section>
      <section id="promotion-activity-section" class="promotion-activity-section" style="display:none"><div class="promotion-create-bar card"><label for="promotion-start-date">创建促销活动</label><input id="promotion-start-date" type="date" class="form-control"><input id="promotion-end-date" type="date" class="form-control"><input id="new-promotion-name" class="form-control" placeholder="活动名称（可选）"><label for="new-promotion-grouping">是否需要分组</label><select id="new-promotion-grouping" class="form-control"><option value="yes">需要分组</option><option value="no">不需要分组</option></select><button class="btn btn-primary promotion-create-btn" onclick="App.createPromotionActivity()">创建促销活动</button></div>
      <div class="promotion-activity-bar card"><label for="promotion-activity-select">选择促销活动</label><select id="promotion-activity-select" class="form-control" onchange="App.selectPromotionActivity(this.value)"><option value="">请选择活动</option><optgroup label="历史促销示例"><option value="promotion260713|2026-07-13~2026-07-19| |yes">promotion260713｜2026-07-13~2026-07-19</option><option value="promotion260729|2026-07-29~2026-08-06| |yes">promotion260729｜2026-07-29~2026-08-06</option><option value="promotion260907|2026-09-08~2026-09-13| |yes">promotion260907｜2026-09-08~2026-09-13</option><option value="promotion260914|2026-09-14~2026-09-20| |yes">promotion260914｜2026-09-14~2026-09-20</option><option value="promotion260921|2026-09-21~2026-09-27| |yes">promotion260921｜2026-09-21~2026-09-27</option></optgroup><optgroup label="新建促销示例"><option value="promotion261001|2026-10-01~2026-10-07| |yes">promotion261001｜2026-10-01~2026-10-07</option><option value="promotion261015|2026-10-15~2026-10-31| |yes">promotion261015｜2026-10-15~2026-10-31</option><option value="promotion261101|2026-11-01~2026-11-11| |yes">promotion261101｜2026-11-01~2026-11-11</option></optgroup></select><span id="promotion-activity-status" class="muted">未选择活动</span></div>
      <div id="promotion-steps-tabs" class="tabs" style="margin:16px 0;display:none"><button class="tab promo-groups-tab active" onclick="App.promoTab('groups')">① 酒店分组与审核</button><button class="tab" onclick="App.promoTab('launch')">② 配置与上线</button><button class="tab" onclick="App.promoTab('monitor')">③ 实验监控</button><button class="tab" onclick="App.promoTab('review')">④ 实验复盘</button></div>
      <div id="promo-demo-content" style="display:none"></div></section>`;
  },

  promoMergeSqlBox(){
    const grid=document.querySelector('.promotion-schedule-content .promo-sql-grid');
    if(!grid)return;
    grid.innerHTML=`<div class="promo-sql-box promo-sql-single"><div class="card-head"><h3>促销取数提示词</h3><span class="badge">默认规则</span></div><textarea id="promo-custom-sql" class="form-control" rows="16">${this.promoDefaultSqlShort}</textarea><div class="sql-action-row"><button class="btn btn-primary" onclick="App.promoRunDefault()">执行默认提示词</button><button class="btn btn-primary" onclick="alert('已保存提示词更改版本')">保存更改版本</button><button class="btn btn-primary" onclick="alert('已执行当前提示词，生成候选酒店清单')">执行提示词</button></div></div>`;
    fetch('/ui/dashboard/default_promotion.sql').then(r=>r.text()).then(full=>{const node=document.getElementById('promo-custom-sql');if(node)node.value=full;}).catch(()=>{});
  },

  promotionSubpage(page){
    const schedule=document.getElementById('promotion-schedule-section');
    const activity=document.getElementById('promotion-activity-section');
    if(schedule) schedule.style.display=page==='schedule'?'block':'none';
    if(activity) activity.style.display=page==='activity'?'block':'none';
    document.querySelectorAll('.promotion-subnav-item').forEach((b,i)=>b.classList.toggle('active',(page==='schedule'&&i===0)||(page==='activity'&&i===1)));
  },

  createPromotionActivity(){
    const start=document.getElementById('promotion-start-date')?.value;
    const end=document.getElementById('promotion-end-date')?.value;
    const input=document.getElementById('new-promotion-name');
    const name=(input?.value||'').trim();
    if(!start||!end){alert('请选择活动开始和结束时间');return;}
    if(end<start){alert('结束时间不能早于开始时间');return;}
    const grouping=document.getElementById('new-promotion-grouping')?.value||'yes';
    const promotionId=`promotion${start.replaceAll('-','').slice(2)}`;
    const range=`${start}~${end}`;
    const select=document.getElementById('promotion-activity-select');
    if(select){const option=document.createElement('option');option.value=`${promotionId}|${range}|${name}|${grouping}`;option.textContent=`${promotionId}｜${range}${name?`｜${name}`:''}`;select.appendChild(option);select.value=option.value;this.selectPromotionActivity(option.value);}
    alert(`活动已创建\n活动ID：${promotionId}\n分组设置：${grouping==='yes'?'需要分组':'不需要分组'}`);
    input.value='';
  },

  selectPromotionActivity(value) {
    const status=document.getElementById('promotion-activity-status');
    if(!status)return;
    const tabs=document.getElementById('promotion-steps-tabs');
    const content=document.getElementById('promo-demo-content');
    if(!value){status.textContent='未选择活动';if(tabs)tabs.style.display='none';if(content)content.style.display='none';return;}
    if(tabs)tabs.style.display='flex';
    if(content)content.style.display='block';
    const [promotionId,range,name,grouping]=value.split('|');
    status.textContent=`当前活动：${promotionId}｜${range}${name&&name.trim()?`｜${name.trim()}`:''}`;
    const groupTab=document.querySelector('#promotion-steps-tabs .promo-groups-tab');
    if(groupTab) groupTab.style.display=grouping==='no'?'none':'inline-flex';
    this.promoTab(grouping==='no'?'launch':'groups');
  },

  promoSqlHtml() {
    const sql=`-- promotion weekly candidate v1\nSELECT hotel_id, request_pv_30d, conversion_rate_30d,\n       available_rate_30d, future_available_days, gp_rate\nFROM mart.hotel_promotion_candidate\nWHERE request_pv_30d >= 10\n  AND request_user_cnt_30d >= 2\n  AND future_available_days >= 21\n  AND conversion_rate_30d < peer_p50_conversion_rate\n  AND gp_rate > 0.015;`;
    const previewRows=Array.from({length:100},(_,i)=>`<tr><td>${String(i+1).padStart(3,'0')}</td><td>Hotel ${String.fromCharCode(65+(i%26))} · ${10231+i}</td><td>${['法国 / 巴黎','日本 / 东京','意大利 / 罗马','美国 / 纽约'][i%4]}</td><td>${128-(i%41)}</td><td>${(0.31+(i%18)*0.03).toFixed(2)}%</td><td>${(0.95+(i%12)*0.04).toFixed(2)}%</td><td>${(0.018+(i%8)*0.002).toFixed(3)}</td></tr>`).join('');
    setTimeout(()=>fetch('/ui/dashboard/default_promotion.sql').then(r=>r.text()).then(full=>{['promo-default-sql','promo-custom-sql','monitor-analysis-sql'].forEach(id=>{const node=document.getElementById(id);if(node)node.value=full;});}).catch(()=>{}),0);
    return `<div class="promo-sql-grid"><div class="promo-sql-box"><h4>默认规则</h4><p class="muted">系统默认 SQL，已接入完整酒店促销分流和五组实验分组逻辑。</p><textarea id="promo-default-sql" readonly>${sql}</textarea><button class="btn btn-primary" onclick="App.promoRunDefault()">执行默认规则</button></div><div class="promo-sql-box"><h4>更改版本</h4><p class="muted">可调整时间范围、阈值和筛选条件。</p><textarea id="promo-custom-sql">${sql}</textarea><button class="btn btn-primary" onclick="alert('已执行本次 SQL，生成候选酒店清单')">执行本次 SQL</button> <button class="btn" onclick="alert('已保存本周 SQL 版本')">保存更改版本</button></div></div><div class="card card-body promo-data-preview"><div class="card-head"><h3>取数结果预览（前100条）</h3><button class="btn btn-sm" onclick="alert('前100条数据已导出')">导出数据</button></div><p class="muted">展示当前规则取数结果的前100条，完整结果可通过导出获得。</p><div class="table-wrap"><table class="data-table"><thead><tr><th>序号</th><th>酒店</th><th>国家/城市</th><th>请求PV</th><th>近30天CVR</th><th>同层P50</th><th>GP率</th></tr></thead><tbody>${previewRows}</tbody></table></div></div>`;
  },

  savePromotionConfig(){
    const cfg={taskName:document.getElementById('promo-task-name')?.value,source:document.getElementById('promo-data-source')?.value,frequency:document.getElementById('promo-frequency')?.value,runTime:document.getElementById('promo-run-time')?.value,window:document.getElementById('promo-window')?.value,mode:document.getElementById('promo-run-mode')?.value,requestThreshold:document.getElementById('promo-request-threshold')?.value,conversionThreshold:document.getElementById('promo-conversion-threshold')?.value,autoFilter:document.getElementById('promo-auto-filter')?.checked,autoCreate:document.getElementById('promo-auto-create')?.checked}; localStorage.setItem('promotionConfig',JSON.stringify(cfg)); alert('Promotion 取数配置已保存');
  },
  runPromotionOnce(){const log=document.getElementById('promo-run-log'); if(log) log.textContent='正在执行 DataMCP 取数与筛选…'; setTimeout(()=>{if(log)log.textContent=`最近执行：${new Date().toLocaleString('zh-CN')} · 已完成 · 结果预览已更新`;},700);},

  promoRunHtml() {
    const candidateRows=Array.from({length:100},(_,i)=>`<tr><td>Hotel ${String.fromCharCode(65+(i%26))} · ${10231+i}</td><td>${['法国 / 巴黎','日本 / 东京','意大利 / 罗马','美国 / 纽约'][i%4]}</td><td>${128-(i%41)}</td><td class="text-danger">${(0.42+(i%18)*0.03).toFixed(2)}%</td><td>${(1.36+(i%12)*0.04).toFixed(2)}%</td></tr>`).join('');
    return `<div class="promo-execution-time"><label>默认取数时间</label><input type="datetime-local" value="2026-09-29T09:30"><button class="btn" onclick="alert('已保存本周取数时间')">保存时间</button><button class="btn btn-primary" onclick="App.promoRunDefault()">执行默认规则取数</button></div><div class="grid grid-4" style="margin-bottom:18px"><div class="card stat-card"><div class="val">周一 09:30</div><div class="lbl">下一次自动触发</div></div><div class="card stat-card"><div class="val">MCP</div><div class="lbl">数据来源</div></div><div class="card stat-card"><div class="val">186</div><div class="lbl">候选酒店</div></div><div class="card stat-card"><div class="val">待导出</div><div class="lbl">当前状态</div></div></div><div class="card card-body"><div class="card-head"><h3>本周候选酒店清单 <button class="btn btn-sm promo-export" onclick="alert('候选酒店清单已导出')">导出清单</button></h3><button class="btn btn-sm" onclick="alert('候选酒店数据已导出')">导出数据</button></div><p class="muted">默认规则：近30天请求PV ≥ 10、请求用户数 ≥ 2、未来30天可售天数 ≥ 21、低于同层转化率中位数、利润率满足实验门槛。</p><div class="table-wrap candidate-list-wrap"><table class="data-table"><thead><tr><th>酒店</th><th>国家/城市</th><th>请求PV</th><th>近30天CVR</th><th>同层P50</th></tr></thead><tbody>${candidateRows}</tbody></table></div></div>`;
  },

  promoGroupsHtml() {
    const defaultPrompt = `请以酒店为实验单位，根据国家/城市、ADR、近30天请求量、历史转化率和利润率进行分层随机分组。默认分为三组，确保各组酒店数量、市场结构和核心指标尽量均衡，并输出分组依据及异常酒店。`;
    return `<div class="card card-body">
      <div class="card-head group-list-actions"><h3>酒店实验分组</h3><div class="group-list-buttons"><label class="btn btn-upload">上传分组名单<input type="file" accept=".csv,.xlsx,.xls" hidden onchange="App.uploadGroupList(this)"></label><button class="btn btn-primary promo-export-main" onclick="alert('分组名单已导出')">导出分组名单</button></div></div>
      <p class="muted">实验单位：酒店。默认三组，分组数量和促销力度可配置。</p>
      <div class="promo-sql-grid promo-prompt-grid">
        <div class="promo-sql-box">
          <h4>AI 分组提示词（默认）</h4>
          <p class="muted">系统默认提示词，可直接执行。</p>
          <textarea id="promo-default-group-prompt" readonly>${defaultPrompt}</textarea>
          <button class="btn btn-primary" onclick="App.promoGenerateGroupSuggestion('default')">执行默认提示词</button>
        </div>
        <div class="promo-sql-box">
          <h4>AI 分组提示词（更新）</h4>
          <p class="muted">数据分析师可根据本次实验调整提示词。</p>
          <textarea id="promo-custom-group-prompt">${defaultPrompt}</textarea>
          <button class="btn btn-primary" onclick="App.promoGenerateGroupSuggestion('custom')">执行更新提示词</button>
          <button class="btn" onclick="alert('已保存本次提示词版本')">保存更新版本</button>
        </div>
      </div>
      <div class="promo-sql-box promo-reply-tracker">
        <div class="card-head"><h4>AI 回复跟踪</h4><span class="badge">等待执行</span></div>
        <p class="muted">记录每次提示词执行后的 AI 分组建议，便于对比和追踪。</p>
        <textarea id="promo-ai-reply-tracker" readonly>暂未生成回复。请先执行默认提示词或更新提示词。</textarea>
      </div>
      <div class="callout warn" style="margin-top:14px">均衡性检查：待运营确认。确认后进入优惠券配置。</div>
      <button class="btn btn-primary" onclick="alert('分组已确认，进入下一步')">确认分组并进入下一步</button>
      <div class="promo-rules-box"><div class="card-head"><h3>促销规则</h3><span class="badge">人工填写</span></div><p class="muted">请根据本次活动和分组结果填写优惠金额、适用范围、流量上限及止损规则。</p><textarea class="form-control" rows="6" placeholder="例如：对照组不发券；实验组一满100减5；实验组二满100减15；实验组三按利润护栏内最高券额；单酒店首3单止损；流量上限20%。"></textarea><button class="btn btn-primary" onclick="alert('促销规则已保存')">保存促销规则</button></div>
    </div>`;
  },

  uploadGroupList(input){
    const file=input?.files?.[0];
    if(!file)return;
    alert(`已上传分组名单：${file.name}`);
  },

  promoTab(tab) {
    const tabIndex={sql:0,groups:0,launch:1,monitor:2,review:3};
    document.querySelectorAll('.tabs .tab').forEach((b,i)=>b.classList.toggle('active',i===(tabIndex[tab] ?? 0)));
    const el=document.getElementById('promo-demo-content'); if(!el)return;
    const pages={
      run:this.promoRunHtml(),
      sql:this.promoSqlHtml(),
      groups:this.promoGroupsHtml(),
      launch:`<div class="card card-body promotion-launch-page"><div class="promotion-launch-actions"><a class="btn btn-primary" href="https://marketing.didaadmin.com/admin/campaign/create" target="_blank" rel="noopener">一键跳转 Marketing 系统创建优惠券</a><span class="muted">优惠券在 Marketing 配置，Promotion 在道旅官网执行</span></div><section class="promotion-config-section"><h3>填写信息</h3><div class="form-row-2"><label>活动名称（对内）<input class="form-control" placeholder="例如：国庆东南亚精选"></label><label>优惠券展示名称（中文）<input class="form-control" value="满减券"></label><label>优惠券展示名称（英文）<input class="form-control" value="Discount on Spending Coupon"></label><label>优惠券币种<select class="form-control"><option>USD ($)</option><option>CNY (¥)</option></select></label></div></section><section class="promotion-config-section"><h3>资源设置</h3><div class="form-row-3"><label>限制酒店<input class="form-control" placeholder="不限制 / 选择酒店"></label><label>限制供应商<input class="form-control" placeholder="不限制 / 选择供应商"></label><label>限制国家<input class="form-control" placeholder="不限制 / 选择国家"></label></div></section><section class="promotion-config-section"><h3>时效设置</h3><div class="form-row-2"><label>生效日期<input type="date" class="form-control"></label><label>失效日期<input type="date" class="form-control"></label><label>预订日期范围<input class="form-control" placeholder="不限制或设置起止日期"></label><label>入住日期范围<input class="form-control" placeholder="不限制或设置起止日期"></label></div></section><section class="promotion-config-section"><h3>商品化设置</h3><label class="check-row"><input type="checkbox"> 活动商品化</label><p class="muted">开启后可按商品维度限制优惠券适用范围。</p></section><section class="promotion-config-section"><h3>优惠券配置</h3><div class="form-row-2"><label>优惠方式<select class="form-control"><option>价格优惠</option><option>折扣优惠</option></select></label><label>优惠规则<input class="form-control" value="满 100 减 10"></label><label>目标对象<input class="form-control" placeholder="点击选择优惠券发放对象"></label><label>预计发放数量<input class="form-control" type="number" placeholder="请输入数量"></label></div></section><div class="promotion-launch-footer"><span class="badge">待配置</span><button class="btn btn-primary" onclick="alert('配置已保存，等待提交上线')">保存配置</button><button class="btn" onclick="alert('已提交上线申请')">提交上线</button></div></div>`,
      monitor:`<div class="grid grid-4"><div class="card stat-card"><div class="val">1,240</div><div class="lbl">实验组请求</div></div><div class="card stat-card"><div class="val">18</div><div class="lbl">实验组订单</div></div><div class="card stat-card"><div class="val">1.45%</div><div class="lbl">当前CVR</div></div><div class="card stat-card"><div class="val">待复盘</div><div class="lbl">本周状态</div></div></div><div class="card card-body" style="margin-top:16px"><h3>本周复盘建议</h3><ul><li>系统将对比三组酒店的转化率、TTV、GP 和 ROI。</li><li>周四生成优惠券补发建议，补发仍需人工确认。</li><li>次周一生成下一期酒店筛选和促销力度调整建议。</li></ul><button class="btn btn-primary" onclick="alert('已提交人工复盘')">确认复盘结论</button></div><div class="card card-body manual-review-box"><div class="card-head"><h3>人工复盘记录</h3><span class="badge">待填写</span></div><div class="form-row-2"><label>复盘结论<textarea class="form-control" rows="4" placeholder="填写本周实验结论、优胜组和是否继续运行"></textarea></label><label>问题与后续动作<textarea class="form-control" rows="4" placeholder="记录异常、补发建议、下周调整事项"></textarea></label></div><div class="manual-review-actions"><button class="btn btn-primary" onclick="alert('人工复盘记录已保存')">保存复盘记录</button><button class="btn" onclick="alert('复盘记录已导出')">导出复盘记录</button></div></div>`,
      monitor:`<div class="monitor-kanban"><section class="monitor-column"><h3>数据表现</h3><div class="kanban-card"><strong>实验组请求</strong><b>1,240</b><span>本周累计</span></div><div class="kanban-card"><strong>实验组订单</strong><b>18</b><span>本周累计</span></div></section><section class="monitor-column"><h3>实验对比</h3><div class="kanban-card"><strong>当前 CVR</strong><b>1.45%</b><span>三组综合</span></div><div class="kanban-card"><strong>优胜组</strong><b>待计算</b><span>需要更多数据</span></div></section><section class="monitor-column"><h3>异常与提醒</h3><div class="kanban-card warning"><strong>状态</strong><b>待复盘</b><span>等待本周数据汇总</span></div><div class="kanban-card"><strong>下一步</strong><span>检查转化率、TTV、GP 和 ROI</span></div></section><section class="monitor-column monitor-review-column"><h3>人工复盘</h3><textarea class="form-control" rows="6" placeholder="填写复盘结论、异常说明和下周动作"></textarea><button class="btn btn-primary" onclick="alert('人工复盘记录已保存')">保存复盘</button><button class="btn" onclick="alert('复盘记录已导出')">导出复盘</button></section></div>`,
    };el.innerHTML=pages[tab]||pages.run;
    if(tab==='monitor'){
      el.insertAdjacentHTML('afterbegin', `<div class="monitor-sql-box card card-body"><div class="card-head"><h3>监控取数 SQL</h3><button class="btn btn-primary" onclick="alert('已执行监控取数 SQL')">执行 SQL</button></div><p class="muted">数据分析师可在此修改监控指标取数逻辑。</p><textarea id="monitor-analysis-sql" class="form-control" rows="8">SELECT experiment_group, COUNT(*) AS hotel_cnt, SUM(request_pv_30) AS request_pv_30, SUM(valid_bks_30) AS valid_bks_30, SUM(valid_gp_cny_30) AS valid_gp_cny_30 FROM final_output WHERE experiment_eligible = 1 GROUP BY experiment_group ORDER BY experiment_group;</textarea></div>`);
      el.insertAdjacentHTML('beforeend', `<div class="monitor-detail-grid"><div class="card card-body"><h3>实验监控安排</h3><p><strong>实验期间：</strong>7天，每日检查</p><p><strong>负责人：</strong>数据分析师 + 运营负责人</p><p><strong>频率：</strong>每日 10:00</p></div><div class="card card-body"><h3>核心指标跟踪</h3><ul><li>各组每日订单数</li><li>各组每日转化率</li><li>各组每日 GMV</li></ul></div><div class="card card-body"><h3>异常处理流程</h3><ol><li>发现异常后 10 分钟内通知运营负责人</li><li>运营负责人判断是否暂停实验</li><li>暂停则记录暂停时间并标记结论影响</li><li>继续则在复盘中标注异常时段，分析时排除</li></ol></div></div>`);
      el.insertAdjacentHTML('beforeend', `<div class="monitor-v2"><section class="monitor-row monitor-schedule card card-body"><div class="card-head"><h3>实验监控安排</h3><span class="badge">可修改</span></div><div class="monitor-edit-grid"><label>实验时间<input class="form-control" value="7天"></label><label>监控频率<select class="form-control"><option>每日 10:00</option><option>每日 09:00</option><option>每12小时</option></select></label><label>负责人<input class="form-control" value="数据分析师 + 运营负责人"></label><button class="btn btn-primary" onclick="alert('监控安排已保存')">保存安排</button></div></section><section class="monitor-row monitor-alert-row card card-body"><div class="card-head"><h3>异常波动预警</h3><span class="badge badge-warn">AI 监控</span></div><div class="monitor-alert-content"><div class="monitor-ai-prompt" style="width:100%"><label>AI 预警提示词<textarea class="form-control" rows="5">请每日 10:00 检查实验各组订单数、转化率、GMV、促销配置和首3单利润，按预设阈值识别异常并输出原因、影响和建议动作。</textarea></label><button class="btn btn-primary" onclick="alert('AI 预警任务已保存')">保存 AI 提示词</button></div></div></section><section class="monitor-row card card-body"><div class="card-head"><h3>核心指标跟踪</h3><span class="muted">实验期间每日更新</span></div><div class="monitor-metrics-row"><div class="metric-board"><span>各组每日订单数</span><b>18</b><small>较昨日 +12%</small></div><div class="metric-board"><span>各组每日转化率</span><b>1.45%</b><small>较昨日 +0.18pp</small></div><div class="metric-board"><span>各组每日 GMV</span><b>¥128,640</b><small>较昨日 +8.6%</small></div></div></section><section class="monitor-row monitor-suggestion card card-body"><h3>异常处理建议</h3><ol><li>发现异常后 10 分钟内通知运营负责人。</li><li>由运营负责人判断是否暂停实验。</li><li>若暂停，记录暂停时间并标记对本期结论的影响。</li><li>若继续，在复盘中标注异常时段，分析时排除。</li></ol></section></div>`);
    }
    if(tab==='sql'){
      const grid=el.querySelector('.promo-sql-grid');
      if(grid) grid.innerHTML=`<div class="promo-sql-box promo-sql-single"><div class="card-head"><h3>促销取数提示词</h3><span class="badge">默认规则</span></div><textarea id="promo-custom-sql" class="form-control" rows="16">${this.promoDefaultSqlShort}</textarea><div class="sql-action-row"><button class="btn" onclick="App.promoUseDefaultSql()">默认提示词</button><button class="btn" onclick="alert('已保存提示词更改版本')">保存更改</button><button class="btn btn-primary" onclick="alert('已执行当前提示词，生成候选酒店清单')">执行提示词</button></div></div>`;
      fetch('/ui/dashboard/default_promotion.sql').then(r=>r.text()).then(full=>{const node=document.getElementById('promo-custom-sql');if(node)node.value=full;}).catch(()=>{});
      el.insertAdjacentHTML('beforeend', this.promoRunHtml());
    }
    if(tab==='groups'){
      const grid=el.querySelector('.promo-prompt-grid');
      if(grid) grid.innerHTML=`<div class="promo-sql-box promo-sql-single"><div class="card-head"><h3>AI 分组提示词</h3><span class="badge">默认规则</span></div><p class="muted">数据分析师可在同一个提示词框内查看、修改和执行分组逻辑。</p><textarea id="promo-custom-group-prompt" class="form-control" rows="8">请以酒店为实验单位，根据国家/城市、ADR、近30天请求量、历史转化率和利润率进行分层随机分组。默认分为三组，确保各组酒店数量、市场结构和核心指标尽量均衡，并输出分组依据及异常酒店。</textarea><div class="sql-action-row"><button class="btn" onclick="App.promoUseDefaultPrompt()">默认提示词</button><button class="btn" onclick="alert('已保存提示词更改版本')">保存更改</button><button class="btn btn-primary" onclick="App.promoGenerateGroupSuggestion('custom')">执行提示词</button></div></div>`;
    }
    if(tab==='review'){
      const reviewSave=(label)=>`<div class="review-box"><label>${label}<textarea class="form-control" rows="6" placeholder="请填写${label}"></textarea><button class="btn btn-primary" onclick="alert('${label}已保存')">保存${label}</button></div>`;
      el.innerHTML=`<div class="card card-body review-page"><div class="card-head"><h3>实验复盘</h3><span class="badge">第 7 天后执行</span></div><p class="muted">汇总 7 天实验结果，结合监控期间异常时段形成最终结论。</p><div class="review-summary-grid"><label>实验结论<textarea class="form-control" rows="6" placeholder="填写各组订单、转化率、GMV、利润和最终推荐"></textarea></label><label>异常时段与影响<textarea class="form-control" rows="6" placeholder="记录异常发生时间、暂停情况及需要排除的数据区间"></textarea></label><label>后续动作<textarea class="form-control" rows="6" placeholder="填写下一期阈值、券额、流量和实验设计调整"></textarea></label></div><div class="manual-review-actions"><button class="btn btn-primary" onclick="alert('实验复盘已保存')">保存复盘</button><button class="btn" onclick="alert('实验复盘已导出')">导出复盘</button></div></div>`;
      const reviewGrid=el.querySelector('.review-summary-grid');
      if(reviewGrid) reviewGrid.innerHTML=reviewSave('实验结论')+reviewSave('异常时段与影响')+reviewSave('后续动作');
      const reviewActions=el.querySelector('.manual-review-actions');
      if(reviewActions) reviewActions.innerHTML='<button class="btn btn-primary" onclick="alert(\'复盘结论已统一导出\')">统一导出复盘结论</button>';
    }
  },

  promoDefaultSqlShort:`-- DidaShopping 周度酒店促销清单 + MECE分流 + 五组实验分组
-- 输出粒度：一行一个 standard_hotel_id。
-- 默认输出近30天请求PV>=10的完整MECE分类；experiment_eligible=1 为最终促销清单。
SELECT * FROM final_output WHERE experiment_eligible = 1 ORDER BY request_pv_30 DESC;`,

  promoUseDefaultSql(){ fetch('/ui/dashboard/default_promotion.sql').then(r=>r.text()).then(full=>{const node=document.getElementById('promo-custom-sql');if(node)node.value=full;}); },
  promoUseDefaultPrompt(){ const node=document.getElementById('promo-custom-group-prompt');if(node)node.value='请以酒店为实验单位，根据国家/城市、ADR、近30天请求量、历史转化率和利润率进行分层随机分组。默认分为三组，确保各组酒店数量、市场结构和核心指标尽量均衡，并输出分组依据及异常酒店。'; },

  promoGenerateGroupSuggestion(source) {
    const promptId=source==='default'?'promo-default-group-prompt':'promo-custom-group-prompt';
    const prompt=document.getElementById(promptId)?.value.trim();
    const tracker=document.getElementById('promo-ai-reply-tracker');
    if(!prompt||!tracker)return;
    const label=source==='default'?'默认提示词':'更新提示词';
    const time=new Date().toLocaleString('zh-CN',{hour12:false});
    tracker.value=`【${time}｜${label}】\nAI 已完成三组均衡分配建议：\n1. A/B/C 三组各 62 家酒店；\n2. 国家与城市分布差异控制在可接受范围；\n3. ADR、请求量、历史转化率和利润率分布基本均衡；\n4. 已标记异常酒店，建议在确认分组前重点检查。\n\n本次执行提示词：\n${prompt}`;
    const badge=tracker.closest('.promo-reply-tracker')?.querySelector('.badge');
    if(badge){badge.textContent='已生成';badge.className='badge badge-success';}
  },

  promoRunDefault(){ alert('已触发 MCP 默认规则取数。Demo 已生成 186 家候选酒店，等待人工审核。'); this.promoTab('run'); },

  /* ── Home ── */
  async renderHome() {
    const o = this.data.overview || {};
    return `
      <div class="grid grid-5 homepage-stats" style="margin-bottom:20px">
        <div class="card stat-card stat-card-clickable" onclick="App.goBucket('annual')" title="点击进入活动生成Agent 查看全年计划池">
          <div class="val">${o.annual_plan_total ?? '—'}</div><div class="lbl">① 全年活动计划</div><div class="stat-hint">已采纳，含执行中/已结束 · 点击查看</div></div>
        <div class="card stat-card stat-card-clickable" onclick="App.goBucket('prep')" title="点击进入活动生成Agent 需立即准备列表">
          <div class="val" style="color:#d97706">${o.prep_urgent ?? '—'}</div><div class="lbl">② 需立即准备</div><div class="stat-hint">未来3个月内，未上线 · 点击查看</div></div>
        <div class="card stat-card stat-card-clickable" onclick="App.goBucket('ready')" title="点击进入上线审核Agent">
          <div class="val" style="color:#059669">${o.ready_to_launch ?? '—'}</div><div class="lbl">③ 准备完毕待上线</div><div class="stat-hint">待上线审核Agent 验收 · 点击查看</div></div>
        <div class="card stat-card stat-card-clickable" onclick="App.goBucket('executing')" title="点击进入监控优化Agent">
          <div class="val" style="color:#2563eb">${o.executing ?? '—'}</div><div class="lbl">④ 执行中</div><div class="stat-hint">已上线，监控优化Agent · 点击查看</div></div>
        <div class="card stat-card stat-card-clickable" onclick="App.goBucket('proposal')" title="点击进入活动生成Agent 评审方案库">
          <div class="val" style="color:#6d28d9">${o.proposal_library_pending ?? '—'}</div><div class="lbl">⑤ 方案库待审</div><div class="stat-hint">飞书规划 + AI 建议 · 点击去评审</div></div>
      </div>
      <div class="nav-section" style="color:#6b7280;margin-bottom:12px">快捷入口</div>
      <div class="grid grid-3">
        <div class="card entry-card card-body" onclick="App.navigate('sop-map')" style="border:2px solid #2563eb">
          <div class="icon">◎</div><h3>SOP 业务对照 · 演示</h3>
          <p>六阶段流程 · 业务↔系统 · 点击进各 Agent（团队演示入口）</p>
        </div>
        <div class="card entry-card card-body" onclick="App.navigate('system-config')">
          <div class="icon">⚙️</div><h3>系统通用配置</h3>
          <p>通用底座 MCP/AI/Bot/生图 · Agent2–6 提示词 · 模块总览 · 运行日志</p>
        </div>
        <div class="card entry-card card-body" onclick="App.navigate('calendar-upload')">
          <div class="icon">📅</div><h3>营销日历预览</h3>
          <p>查看飞书同步到的活动列表（配置请在「系统连接配置」）</p>
        </div>
        <div class="card entry-card card-body" onclick="App.navigate('agent6')">
          <div class="icon">📚</div><h3>复盘归档</h3>
          <p>复盘归档Agent：完整复盘报告、有产客户/酒店清单、活动结论与经验入库</p>
        </div>
      </div>
      <div class="callout">
        <strong>项目管理：</strong>6 段 SOP 对应 6 个 Agent（建档、三线任务看板、催办、终审、监控、复盘）。
        细节 I/O 与判断机制待 Jim 等提供 — 当前已留<strong>模块入口</strong>，见
        <a href="#" onclick="App.navigate('system-config');return false" style="color:#1d4ed8">系统通用配置</a>。
        <strong>AI 增长引擎：</strong>人工规划与 AI 创意同一桌评审；圈客选品辅助人工。
      </div>
      <div class="grid grid-6" style="margin-top:16px;display:grid;grid-template-columns:repeat(6,1fr);gap:10px">
        ${[
          ['活动生成Agent','人工池+AI池对比评审 · 证据卡 · 定稿日历'],
          ['活动建档Agent','终版营销日历 · 完善活动档案 · 信息基座'],
          ['任务监督Agent','三列看板：资源 / 方案 / 素材 · 催办验收'],
          ['上线审核Agent','预备上线池终极审核 · 资源/位置/素材/字段/风险/机制检查'],
          ['监控优化Agent','自动化监控 · 自动化总结 · 优化建议 · 预警推送'],
          ['复盘归档Agent','完整复盘报告 · 有产客户/酒店清单 · 活动结论 · 经验入库'],
        ].map((labels, i) => `
          <div class="card card-body entry-card" onclick="App.navigate('agent${i + 1}')" style="text-align:center;padding:14px 10px">
            <div style="font-size:13px;font-weight:700;color:#1d4ed8;line-height:1.35">${labels[0]}</div>
            <div style="font-size:10px;color:#6b7280;margin-top:8px;line-height:1.45;text-align:left">${labels[1]}</div>
          </div>`).join('')}
      </div>
      ${this.lifecycleBarHtml('新加坡F1赛事酒店预订')}`;
  },

  lifecycleBarHtml(activityName) {
    const name = activityName || '样例活动';
    const steps = this.DEMO_LIFECYCLE.map((s, i) => {
      const active = s.phase <= 5;
      return `<div class="lifecycle-step ${active ? 'active' : ''}" onclick="App.navigate('${s.view}')" title="阶段${s.phase}">
        <div class="lifecycle-num">${s.phase}</div>
        <div class="lifecycle-lbl">${s.label}</div>
        <div class="lifecycle-st">${s.status}</div>
      </div>${i < this.DEMO_LIFECYCLE.length - 1 ? '<div class="lifecycle-arrow">→</div>' : ''}`;
    }).join('');
    return `<div class="card" style="margin-top:20px">
      <div class="card-head">样例活动全链路 · ${name} <span class="hint">（演示用状态条 · 点击查看各阶段）</span></div>
      <div class="card-body"><div class="lifecycle-bar">${steps}</div></div>
    </div>`;
  },

  phaseBannerHtml(agentKey) {
    if (agentKey === 'agent2') return '';
    const ph = this.SOP_PHASES.find(p => p.agent === agentKey);
    if (!ph) return '';
    return `<div class="callout" style="margin-bottom:14px;border-left:4px solid #2563eb">
      <strong>阶段${ph.n} · ${ph.name}</strong> → ${ph.agentLabel}
      <div style="font-size:12px;color:#6b7280;margin-top:6px">业务：${ph.biz}</div>
      <div style="font-size:12px;color:#6b7280">系统：${ph.sys}</div>
      <button class="btn btn-sm" style="margin-top:8px;margin-right:8px" onclick="App.navigate('sop-map')">返回 SOP 对照</button>
    </div>`;
  },

  async renderSopMap() {
    let modMap = { phases: [], summary: {} };
    try { modMap = await this.fetch('/api/v2/admin/modules'); } catch (_) {}

    const phaseCards = this.SOP_PHASES.map(ph => {
      const apiPh = (modMap.phases || []).find(p => p.agent === ph.agent);
      const modCount = apiPh?.modules?.length || '—';
      const steps = ph.steps.map(s => `<li>${s}</li>`).join('');
      return `<div class="card sop-phase-card" onclick="App.navigate('${ph.agent}')">
        <div class="card-head">阶段${ph.n} · ${ph.name}
          <span class="badge-sm info">${ph.agentLabel}</span></div>
        <div class="card-body">
          <p style="font-size:13px;margin:0 0 8px"><strong>业务：</strong>${ph.biz}</p>
          <p style="font-size:13px;margin:0 0 10px;color:#6b7280"><strong>系统：</strong>${ph.sys}</p>
          <ul style="font-size:12px;margin:0 0 10px 18px;color:#374151">${steps}</ul>
          <div style="font-size:11px;color:#9ca3af">本阶段 ${modCount} 个功能模块 · 点击进入工作台</div>
        </div>
      </div>`;
    }).join('');

    const sum = modMap.summary || {};
    return `
      <div class="callout">
        <strong>团队演示页</strong> — 左：业务六阶段；右：系统 Agent 与对象状态。
        完整文档见 <code>docs/SYSTEM_DESIGN_v2.md</code> ·
        <button class="btn btn-sm" onclick="App.navigate('system-config',{configTab:'modules'})">模块总览 ${sum.total || 26} 项</button>
        <button class="btn btn-sm btn-primary" onclick="App.navigate('agent1')">返回营销日历工作台</button>
      </div>
      <div class="grid grid-2" style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
        <div class="card card-body">
          <h3 style="margin:0 0 10px;font-size:15px">业务总流程</h3>
          <div style="font-size:13px;line-height:1.8">
            ① 策划评审 → ② 建档看板 → ③ 任务进展 → ④ T-1审核 → ⑤ 监控推送 → ⑥ 档案库 → 反哺①
          </div>
          <p style="font-size:12px;color:#6b7280;margin-top:10px">关键规则：只要AI池 · T-1审核 · T+1总结 · 催办创建不通知</p>
        </div>
        <div class="card card-body">
          <h3 style="margin:0 0 10px;font-size:15px">系统对象流转</h3>
          <div style="font-size:12px;font-family:monospace;line-height:1.7">
            proposal → adopted → archived → prep → ready_launch → live → closed → archive
          </div>
          <p style="font-size:12px;color:#6b7280;margin-top:10px">骨架 ${sum.skeleton ?? 18} · 待填 ${sum.placeholder ?? 7} · 可运行 ${sum.ready ?? 1}</p>
        </div>
      </div>
      ${this.lifecycleBarHtml('新加坡F1赛事酒店预订')}
      <div class="nav-section" style="color:#6b7280;margin:16px 0 10px">六阶段 · 点击进入对应 Agent</div>
      <div class="sop-phase-grid">${phaseCards}</div>`;
  },

  /* ── Agent1 · 标准活动规划 ── */
  pipelineStepHtml(step) {
    if (!step) return '';
    const st = step.status || '';
    const ok = ['simulate', 'ok', 'llm', 'skill_fallback', 'fallback_simulate'].includes(st);
    const icon = ok ? '✓' : (st === 'error' ? '✗' : '…');
    const detail = step.detail ? `<pre class="json" style="max-height:120px;margin-top:8px;font-size:11px">${JSON.stringify(step.detail, null, 2)}</pre>` : '';
    return `<div class="pipeline-step ${ok ? 'ok' : 'warn'}" style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin-bottom:10px">
      <div style="font-weight:600">${icon} 步骤${step.step} · ${step.name}
        <span class="hint" style="margin-left:8px">${st}</span></div>
      <div style="font-size:13px;margin-top:6px">${step.message || ''}</div>
      ${step.analyzer ? `<div style="font-size:12px;color:#6b7280;margin-top:4px">分析引擎：${step.analyzer}</div>` : ''}
      ${detail}
    </div>`;
  },

  draftCol(d, feishuKey, legacyKey) {
    const v = d[feishuKey] ?? d[legacyKey];
    return v == null || v === '' ? '—' : v;
  },

  p75TableHtml(table, months) {
    if (!table?.length) return '';
    const monthCols = months?.length ? months : Object.keys(table[0]).filter(k => /^\d{4}-\d{2}$/.test(k));
    const head = ['归属洲', '归属洲二', ...monthCols.slice(0, 6), '…', '全年P75'];
    const body = table.slice(0, 24).map(row => {
      const cells = [
        row['归属洲'] || '—',
        row['归属洲二'] || '—',
        ...monthCols.slice(0, 6).map(m => row[m] ?? '—'),
        '…',
        row['全年P75'] ?? '—',
      ];
      return `<tr class="${row['归属洲二'] === '总计' ? 'row-total' : ''}">${cells.map(c => `<td style="font-size:11px">${c}</td>`).join('')}</tr>`;
    }).join('');
    return `<div class="table-wrap" style="max-height:360px;overflow:auto">
      <table><thead><tr>${head.map(h => `<th style="font-size:11px">${h}</th>`).join('')}</tr></thead>
      <tbody>${body}</tbody></table></div>`;
  },

  checkoutDetailHtml(table) {
    if (!table?.length) return '';
    const rows = table.map(r => `<tr>
      <td style="font-size:11px">${r.checkout_month || '—'}</td>
      <td>${r['国家'] || '—'}</td>
      <td>${r['归属洲'] || '—'}</td>
      <td>${r['归属洲二'] || '—'}</td>
      <td style="text-align:right">${(r.total_ttv || 0).toLocaleString()}</td>
      <td style="text-align:right">${r.total_bks ?? '—'}</td>
      <td style="text-align:right">${r.bks_until_75_percent ?? '—'}</td>
      <td style="text-align:right">${r.leading_date_for_top75_percent ?? '—'}</td>
    </tr>`).join('');
    return `<div class="table-wrap" style="max-height:280px;overflow:auto">
      <table><thead><tr>
        <th>checkout_month</th><th>国家</th><th>归属洲</th><th>归属洲二</th>
        <th>total_ttv</th><th>total_bks</th><th>bks_until_75%</th><th>leading_date_P75</th>
      </tr></thead><tbody>${rows}</tbody></table>
      <p class="hint">展示 TOP ${table.length} 行 · MCP 路径含 total_bks；bks_until_75/P75 行级字段待官方指标或合并飞书底表</p>
    </div>`;
  },

  ttvShareTableHtml(table, months) {
    if (!table?.length) return '';
    const monthCols = months?.length ? months : Object.keys(table[0]).filter(k => /^\d{4}-\d{2}$/.test(k));
    const head = ['归属洲', '归属洲二', ...monthCols.slice(0, 6), '…', '总计(M)'];
    const body = table.slice(0, 20).map(row => {
      const cells = [
        row['归属洲'] || '—',
        row['归属洲二'] || '—',
        ...monthCols.slice(0, 6).map(m => row[m] || '—'),
        '…',
        row['总计_M'] ?? '—',
      ];
      const isTotal = row['归属洲二'] === '总计';
      return `<tr class="${isTotal ? 'row-total' : ''}">${cells.map(c => `<td style="font-size:11px">${c}</td>`).join('')}</tr>`;
    }).join('');
    return `<div class="table-wrap" style="max-height:320px;overflow:auto">
      <table><thead><tr>${head.map(h => `<th style="font-size:11px">${h}</th>`).join('')}</tr></thead>
      <tbody>${body}</tbody></table>
      ${table.length > 20 ? `<p class="hint">仅展示前 20 行，共 ${table.length} 行</p>` : ''}
    </div>`;
  },

  async renderAgent1ManualPlan() {
    const r = this.manualCalendarResult;
    const sum = r?.summary || {};
    const pipeline = r?.pipeline || [];
    const dw = r?.data_window || {};
    const months = r?.ttv_share_table?.[0]
      ? Object.keys(r.ttv_share_table[0]).filter(k => /^\d{4}-\d{2}$/.test(k))
      : (r?.p75_table?.[0]
        ? Object.keys(r.p75_table[0]).filter(k => /^\d{4}-\d{2}$/.test(k))
        : []);
    const staleHint = r && !r.ttv_share_table?.length ? `
      <div class="callout" style="border-color:#fbbf24;background:#fffbeb;margin-bottom:12px">
        <strong>数据不完整</strong>：当前结果是旧版缓存（仅有 Analysis A）。
        请 <strong>Ctrl+F5 强刷</strong> 后重新点击「正式运行」，应出现：离店数据明细 · 离店TTV占比 · 提前预订P75 三张过程表。
      </div>` : '';
    const contRows = r?.continent_totals
      ? Object.entries(r.continent_totals).map(([k, v]) => `<tr><td>${k}</td><td>${v}M</td></tr>`).join('')
      : '';
    const draftRows = (r?.draft_rows || []).map(d => `
      <tr>
        <td style="font-size:12px">${this.draftCol(d, '活动场次', 'session_group')}</td>
        <td><strong>${this.draftCol(d, '副活动主题(按目的地/区域)', 'sub_theme')}</strong>
          <div class="meta">${this.draftCol(d, 'analysis_unit', 'analysis_unit')} · ${this.draftCol(d, 'continent', 'continent')}</div></td>
        <td style="font-size:12px">${this.draftCol(d, '覆盖目的地/城市', 'destinations')}</td>
        <td>${this.draftCol(d, '对应出游/离店窗口(促销月份)', 'checkout_window')}</td>
        <td>${this.draftCol(d, '关键P75(目标离店月·天)', 'p75_days')}</td>
        <td style="font-size:12px">${this.draftCol(d, '选目的地数据依据·节庆/旺季(Top/峰值/淡旺季)', 'evidence')}</td>
      </tr>`).join('');
    const combined = (r?.combined_groups || []).map(c => `
      <tr><td>${c.sub_theme || c.analysis_unit}</td><td>${c.target_checkout_month}</td><td>${c.p75_days ?? '—'}</td>
      <td style="font-size:12px">${c.evidence}</td></tr>`).join('');

    return `
      ${pipeline.length ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">流水线执行记录</div>
        <div class="card-body">${pipeline.map(s => this.pipelineStepHtml(s)).join('')}</div>
      </div>` : ''}
      <details class="card config-collapsible" style="margin-bottom:16px" open>
        <summary class="card-head config-summary">参数与操作<span class="config-toggle">▾</span></summary>
        <div class="card-body">
          <div class="actions">
            <button class="btn btn-primary" onclick="App.generateManualCalendar('mcp')">正式运行（MCP 离店指标）</button>
            <button class="btn" onclick="App.generateManualCalendar('simulate')">虚拟数据模拟</button>
            <button class="btn" onclick="App.generateManualCalendar('auto')">自动（MCP 失败则模拟）</button>
            <button class="btn" onclick="App.submitManualCalendarPool()" ${r?.draft_rows?.length ? '' : 'disabled'}>
              送入初版评审池（${r?.draft_rows?.length || 0} 条）
            </button>
            <button class="btn" onclick="App.setAgent1GenSub('manual')">配置 Prompt</button>
          </div>
          ${r ? `<p style="font-size:12px;color:#6b7280;margin-top:10px">
            已生成：候选 ${sum.candidates ?? 0} 条 · 初版 ${sum.draft_rows ?? 0} 条 · 组合场 ${sum.combined_groups ?? 0} 个
          </p>` : ''}
        </div>
      </details>
      ${staleHint}
      ${contRows ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">大洲离店 TTV 汇总 · Analysis A（对齐飞书「离店TTV及占比」洲总计）</div>
        <div class="card-body table-wrap"><table><thead><tr><th>归属洲</th><th>全年离店 TTV(M)</th></tr></thead><tbody>${contRows}</tbody></table></div>
      </div>` : ''}
      ${r?.checkout_detail_table?.length ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">离店数据 · 明细样例（对齐飞书「离店数据」G/H/I 列）</div>
        <div class="card-body">${this.checkoutDetailHtml(r.checkout_detail_table)}</div>
      </div>` : ''}
      ${r?.ttv_share_table?.length ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">离店 TTV 及占比 · Analysis B（对齐飞书过程表，TOP5 单元 × 月占比%）</div>
        <div class="card-body">${this.ttvShareTableHtml(r.ttv_share_table, months)}</div>
      </div>` : ''}
      ${r?.p75_table?.length ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">提前预订 P75（对齐飞书「提前预订P75」· 取目标离店月列）</div>
        <div class="card-body">${this.p75TableHtml(r.p75_table, months)}</div>
      </div>` : ''}
      ${combined ? `<div class="card" style="margin-bottom:16px">
        <div class="card-head">组合场 · 加权 P75（对齐飞书组合规则 · 新马泰等）</div>
        <div class="card-body table-wrap"><table><thead><tr><th>组合副主题</th><th>高峰离店月</th><th>加权P75(天)</th><th>数据依据</th></tr></thead><tbody>${combined}</tbody></table></div>
      </div>` : ''}
      <details class="card config-collapsible" open>
        <summary class="card-head config-summary">营销日历初版 ${r ? `（${r.draft_rows?.length || 0} 条）` : ''}
          <span class="hint">列对齐飞书初版表 A–G　<span class="config-toggle">▾</span></span></summary>
        <div class="card-body table-wrap">
          <table><thead><tr>
            <th>活动场次</th><th>副活动主题</th><th>覆盖目的地/城市</th>
            <th>对应出游/离店窗口</th><th>关键P75</th><th>选目的地数据依据</th>
          </tr></thead>
          <tbody>${draftRows || '<tr><td colspan=6 class="empty">点击「正式运行」开始</td></tr>'}</tbody></table>
        </div>
      </details>`;
  },

  async generateManualCalendar(mode = 'simulate') {
    const box = document.getElementById('cfg-mcp-result');
    this.manualCalendarResult = null;
    try {
      this.render();
      const r = await this.fetch('/api/v2/agent1/manual-calendar/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (!r.ok) {
        alert(r.error || '生成失败');
        return;
      }
      this.manualCalendarResult = r;
      this.render();
    } catch (e) {
      alert(e.message || '生成失败');
    }
  },

  async submitManualCalendarPool() {
    const rows = this.manualCalendarResult?.draft_rows;
    if (!rows?.length) {
      alert('请先生成标准活动规划');
      return;
    }
    if (!confirm(`将 ${rows.length} 条标准活动规划送入初版评审池？`)) return;
    try {
      const r = await this.fetch('/api/v2/agent1/manual-calendar/submit-pool', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft_rows: rows, operator: 'marketer' }),
      });
      if (!r.ok) {
        alert(r.error || '提交失败');
        return;
      }
      alert(`已送入评审池：新增 ${r.inserted} 条，跳过重复 ${r.skipped} 条`);
      await this.refresh();
      this.setTab('work');
    } catch (e) {
      alert(e.message || '提交失败');
    }
  },

  /* ── Agent1 · 字段与评审池工具 ── */
  loadAgent1PendingIds() {
    try { return JSON.parse(localStorage.getItem('agent1_pending_ids') || '[]'); } catch (_) { return []; }
  },
  saveAgent1PendingIds(ids) { localStorage.setItem('agent1_pending_ids', JSON.stringify(ids)); },
  toggleAgent1Pending(key) {
    const ids = this.loadAgent1PendingIds();
    const i = ids.indexOf(key);
    if (i >= 0) ids.splice(i, 1); else ids.push(key);
    this.saveAgent1PendingIds(ids);
    this.render();
  },
  parseMonthNum(v) {
    if (v == null || v === '') return null;
    const s = String(v);
    const iso = s.match(/20\d{2}[-/年](\d{1,2})/);
    if (iso) {
      const n = parseInt(iso[1], 10);
      return n >= 1 && n <= 12 ? n : null;
    }
    const cn = s.match(/(\d{1,2})\s*月/);
    if (cn) {
      const n = parseInt(cn[1], 10);
      return n >= 1 && n <= 12 ? n : null;
    }
    const m = s.match(/(?:^|[^\d])(\d{1,2})(?:[^\d]|$)/);
    if (!m) return null;
    const n = parseInt(m[1], 10);
    return n >= 1 && n <= 12 ? n : null;
  },
  activityLaunchMonth(a) {
    const ld = a.launch_date || a.start_date || a.promotion_date || '';
    const dm = String(ld).match(/20\d{2}-(\d{2})/);
    if (dm) return parseInt(dm[1], 10);
    return this.parseMonthNum(a.promotion_month || a._monthKey);
  },
  agent1EntryLabel(item) {
    const src = item.plan_source || item.source?.plan_source || item.source || '';
    const map = window.AGENT1_ENTRY_LABEL || window.AGENT1_SOURCE_LABEL || {};
    return map[src] || '规划生成';
  },
  parseActivityType(item) {
    if (!item) return '人工标准';
    const direct = item.activity_type || item.basic?.activity_type;
    if (direct && window.AGENT1_ACTIVITY_TYPES?.includes(direct)) return direct;
    if (direct) {
      if (String(direct).includes('创意')) return 'AI创意';
      if (String(direct).includes('其他')) return '其他';
      return '人工标准';
    }
    let row = item;
    if (item.solution_analysis) {
      try { row = { ...item, ...JSON.parse(item.solution_analysis) }; } catch (_) {}
    } else if (item.raw?.solution_analysis) {
      try { row = { ...item, ...JSON.parse(item.raw.solution_analysis) }; } catch (_) {}
    }
    if (row.activity_type && window.AGENT1_ACTIVITY_TYPES?.includes(row.activity_type)) return row.activity_type;
    const src = item.plan_source || item.source?.plan_source || row.plan_source || '';
    if (['ai_suggestion', 'ai_creative', 'ai_intel'].includes(src)) return 'AI创意';
    return '人工标准';
  },
  resolveReviewSchema(item) {
    const t = this.parseActivityType(item);
    if (t === 'AI创意') return 'CREATIVE';
    if (t === '其他') return 'OTHER';
    return 'STANDARD';
  },
  agent1SourceLabel(item) {
    return this.parseActivityType(item);
  },
  isStandardProposal(a) {
    return this.resolveReviewSchema(a) === 'STANDARD';
  },
  normalizeReviewPoolItems(ws) {
    const lib = ws.proposal_library || {};
    const calProposals = lib.calendar_proposals || [];
    const aiPending = lib.ai_pending || ws.ai_suggestions?.pending_review || [];
    const pendingSet = new Set(this.loadAgent1PendingIds());
    const items = [];
    calProposals.forEach(a => items.push({
      key: `campaign:${a.campaign_id}`, id: a.campaign_id, type: 'campaign',
      name: a.campaign_name || '—', month: a.promotion_month || '—',
      monthNum: this.parseMonthNum(a.promotion_month),
      activityType: this.parseActivityType(a),
      entryLabel: this.agent1EntryLabel(a),
      dest: a.destination_region || a.regions || a.target_dest || '—',
      keyword: a.theme_keyword || a.sub_theme || '—',
      schemaType: this.resolveReviewSchema(a),
      pending: pendingSet.has(`campaign:${a.campaign_id}`), reviewed: !!(a.plan_review_confirmed || a.reviewed || a.status === 'adopted'), raw: a,
    }));
    aiPending.forEach(s => items.push({
      key: `suggestion:${s.suggestion_id}`, id: s.suggestion_id, type: 'suggestion',
      name: s.campaign_name || '—', month: s.promotion_month_hint || '—',
      monthNum: this.parseMonthNum(s.promotion_month_hint),
      activityType: this.parseActivityType(s),
      entryLabel: this.agent1EntryLabel(s),
      dest: s.target_dest || '—', keyword: s.theme_keyword || '—',
      schemaType: this.resolveReviewSchema(s),
      pending: pendingSet.has(`suggestion:${s.suggestion_id}`), reviewed: !!(s.reviewed || s.status === 'adopted'), raw: s,
    }));
    const existing = new Set(items.map(it => it.id));
    Object.values(ws.human_calendar?.by_month || {}).flat().forEach(a => {
      const id = a.campaign_id || a.activity_id;
      if (!id || existing.has(id)) return;
      items.push({key:`campaign:${id}`,id,type:'campaign',name:a.campaign_name||a.sub_theme||'—',month:a.promotion_month||a._monthKey||'—',monthNum:this.parseMonthNum(a.promotion_month||a._monthKey),activityType:this.parseActivityType(a),entryLabel:this.agent1EntryLabel(a),dest:a.destination_region||a.target_dest||a.regions||'—',keyword:a.theme_keyword||a.sub_theme||'—',schemaType:this.resolveReviewSchema(a),pending:false,reviewed:true,raw:a});
    });
    return items;
  },
  setAgent1ReviewMonth(m) {
    const current = Array.isArray(this.agent1ReviewMonths) ? this.agent1ReviewMonths : (this.agent1ReviewMonth ? [this.agent1ReviewMonth] : []);
    this.agent1ReviewMonths = current.includes(m) ? current.filter(x => x !== m) : [...current, m].sort((a,b)=>a-b);
    this.agent1ReviewMonth = this.agent1ReviewMonths.length === 1 ? this.agent1ReviewMonths[0] : null;
    this.render();
  },
  clearAgent1ReviewMonths() { this.agent1ReviewMonths = []; this.agent1ReviewMonth = null; this.render(); },
  setAgent1AnnualMonth(m) { this.agent1AnnualMonth = m; this.render(); },
  setAgent1PlanningYear(y) {
    this.agent1PlanningYear = Number(y) || 2027;
    this.render();
  },
  parseActivityYear(a, defaultYear) {
    const fields = [a.launch_date, a.start_date, a.promotion_date, a.promotion_month_hint, a.promotion_month, a._monthKey];
    for (const c of fields) {
      const m = String(c || '').match(/(20\d{2})/);
      if (m) return parseInt(m[1], 10);
    }
    return defaultYear ?? this.agent1PlanningYear ?? new Date().getFullYear();
  },
  activityInPlanningYear(a, year) {
    return this.parseActivityYear(a, year) === year;
  },
  getNested(obj, path) {
    if (!obj || !path) return '';
    return path.split('.').reduce((o, k) => (o && o[k] != null ? o[k] : ''), obj) ?? '';
  },
  setNested(obj, path, value) {
    const parts = path.split('.');
    let cur = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!cur[parts[i]] || typeof cur[parts[i]] !== 'object') cur[parts[i]] = {};
      cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
  },
  agent1CalendarReviewFormHtml(s, opts = {}) {
    const schemaType = opts.schemaType || 'STANDARD';
    const schema = (window.AGENT1_FIELDS || {})[schemaType] || [];
    const ro = !!opts.readonly;
    return schema.map((grp, gi) => {
      const mandatory = ['活动类型','月度主活动主题','活动名称','目的地归属（大洲）','国家/地区'];
      const fields = grp.fields.map(f => this.rvField(`a1rv-${f.key}`, f.label, this.getNested(s, f.path) || f.default || '', { placeholder: f.label, readonly: ro || f.readonly, required: f.required || mandatory.includes(f.label) })).join('');
      return this.sectionBlock(`a1g${gi}`, `【${grp.group}】`, '', '', fields);
    }).join('');
  },
  collectAgent1ReviewForm(schemaType, baseStructured) {
    const s = JSON.parse(JSON.stringify(baseStructured || {}));
    const schema = (window.AGENT1_FIELDS || {})[schemaType] || [];
    schema.forEach(grp => grp.fields.forEach(f => {
      this.setNested(s, f.path, document.getElementById(`a1rv-${f.key}`)?.value ?? '');
    }));
    return s;
  },

  /* ── Agent1 ── */
  async renderAgent1Generate() {
    const sub = this.agent1GenSub || 'manual';
    let body = '';
    if (sub === 'manual') body = (await this.renderAgent1ManualConfigInline()) + await this.renderAgent1ManualPlan();
    else if (sub === 'creative') body = await this.renderAgent1CreativeGeneratePanel();
    else body = await this.renderAgent1TempPanel();
    return `${this.agent1TabsHtml()}${body}`;
  },

  async renderAgent1ManualConfigInline() {
    const cfg = this.agentConfig.agent1 || {};
    const mc = cfg.manual_calendar || {};
    const calendarAiBlock = await this.renderPromptBlock('manual_calendar_ai', 'calendar-ai');
    return `<details class="card" style="margin-bottom:16px">
      <summary class="card-head config-summary" style="cursor:pointer;list-style:none">MCP取数与输出活动<span class="config-toggle">▾</span></summary>
      <div class="card-body">
        <div class="form-row agent1-date-row">
          <div class="form-group"><label>规划归属年 <span class="req">*</span></label><select id="a1-plan-year">${Array.from({length:276},(_,i)=>2025+i).map(y=>`<option value="${y}" ${Number(this.agent1PlanningYear || mc.planning_year || 2027)===y?'selected':''}>${y}</option>`).join('')}</select></div>
          <div class="form-group"><label>数据窗起点 <span class="req">*</span></label><input id="a1-win-start" type="date" value="${mc.data_window_start || '2026-08-01'}" onchange="document.getElementById('a1-win-end').min=this.value" /></div>
          <div class="form-group"><label>数据窗终点 <span class="req">*</span></label><input id="a1-win-end" type="date" value="${mc.data_window_end || '2027-07-31'}" min="${mc.data_window_start || '2026-08-01'}" /></div>
        </div>
        <div class="cfg-step prompt-title-row"><strong>① MCP 取数 AI 提示词</strong><div class="prompt-header-actions"><button class="btn btn-primary" onclick="App.useDefaultMcpPrompt()">默认提示词</button><button class="btn btn-primary" onclick="App.saveMcpPrompt()">保存更改后提示词</button></div></div><div class="form-group"><textarea id="a1-mcp-fetch" rows="8">${this.escAttr(mc.mcp_fetch_prompt || this._legacyFetchPrompt(mc))}</textarea></div>
        <div class="cfg-step"><strong>② 数据分析及输出活动 AI 提示词</strong></div>
        ${calendarAiBlock}
        <div class="actions config-save-actions"><button class="btn btn-primary" onclick="App.saveAgent1ManualConfig()">保存全部配置</button></div>
      </div></details>`;
  },

  useDefaultMcpPrompt(){const node=document.getElementById('a1-mcp-fetch');if(node)node.value=this._legacyFetchPrompt(this.agentConfig.agent1?.manual_calendar||{});},
  async saveMcpPrompt(){await this.saveAgent1ManualConfig();alert('MCP 取数提示词已保存');},
  executeMcpPrompt(){alert('已提交 MCP 取数提示词，正在执行取数。');},

  async renderAgent1CreativeGeneratePanel() {
    const cfg = this.agentConfig.agent1 || {};
    const cr = cfg.creative || {};
    const creativeBlock = await this.renderPromptBlock('ai_creative', 'creative');
    const intelBody = await this.renderAgent1IntelConfigPanel(cfg);
    return `<details class="card" style="margin-bottom:16px">
      <summary class="card-head config-summary" style="cursor:pointer;list-style:none">AI生成创意活动<span class="config-toggle">▾</span></summary>
      <div class="card-body">
        <div class="form-row"><div class="form-group"><label>模型选择</label>
          <select id="a1-creative-provider">
            <option value="inherit" ${(cr.llm_provider || 'inherit') === 'inherit' ? 'selected' : ''}>系统默认</option>
            <option value="qwen" ${cr.llm_provider === 'qwen' ? 'selected' : ''}>Dragon API</option>
            <option value="deepseek" ${cr.llm_provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
          </select></div></div>
        ${creativeBlock}
        <div class="actions config-save-actions"><button class="btn btn-primary" onclick="App.saveAgent1CreativeConfig()">保存全部配置</button></div>
      </div></details>${intelBody}`;
  },

  async renderAgent1TempPanel() {
    return `<div class="callout"><strong>中途录入入口</strong> — 「临时」不是活动类型。手动加活动时请先选标签（标准 / 创意 / 其他），系统会分流到对应类型：<strong>人工标准 · AI创意 · 其他</strong>。</div>
      <div class="card" style="margin-bottom:16px"><div class="card-head">中途活动录入</div><div class="card-body">
        <div class="form-row temp-entry-row">
          <div class="form-group"><label>活动名称 <span class="req">*</span></label><input id="tmp-name" /></div>
          <div class="form-group"><label>活动标签 <span class="req">*</span></label>
            <select id="tmp-label">
              <option value="标准">人工标准活动</option>
              <option value="创意">AI创意活动</option>
              <option value="其他">其他 → 活动类型：其他</option>
            </select>
          </div>
          <div class="form-group"><label>推广日期 <span class="req">*</span></label><input id="tmp-date" type="date" /></div>
        </div>
        <div class="form-row temp-entry-row">
          <div class="form-group"><label>国家/地区</label><input id="tmp-country" /></div>
          <div class="form-group"><label>城市</label><input id="tmp-city" /></div>
          <div class="form-group"><label>主题词</label><input id="tmp-keyword" /></div>
        </div>
        <div class="form-group"><label>机会论证</label><textarea id="tmp-bg" rows="5"></textarea></div>
        <div class="cfg-step"><strong>上传 / 链接一键分析</strong></div>
        <div class="form-group"><label>文章链接</label><input id="a1-intel-url" /></div>
        <div class="form-group"><label>上传文件</label><input type="file" id="a1-intel-file" accept=".txt,.md,.csv,.xlsx,.xls" /></div>
        <div class="form-group"><label>正文</label><textarea id="a1-intel-content" rows="4"></textarea></div>
        <p class="hint">AI 解析后将自动回填上方活动信息；如有偏差，可人工修改后再保存并送入评审。</p>
        <div class="actions temp-actions-right">
          <button class="btn btn-primary" onclick="App.oneClickAgent1Creative()">一键分析生成</button>
          <button class="btn btn-primary" onclick="App.uploadAgent1TempFile()">上传 Excel 日历</button>
          <button class="btn btn-primary" onclick="App.submitTempActivityManual()">保存并送入评审</button>
        </div>
      </div></div>`;
  },

  async submitTempActivityManual() {
    const name = document.getElementById('tmp-name')?.value?.trim();
    const month = document.getElementById('tmp-date')?.value;
    const label = document.getElementById('tmp-label')?.value || '标准';
    const labelMap = window.AGENT1_TEMP_LABEL_MAP || { 标准: '人工标准', 创意: 'AI创意', 其他: '其他' };
    if (!name || !month) { alert('请填写活动名称和推广日期'); return; }
    const row = {
      sub_theme: name, '副活动主题(按目的地/区域)': name,
      activity_type: labelMap[label] || '人工标准',
      activity_label: label,
      entry_channel: 'temp_manual',
      destinations: [document.getElementById('tmp-city')?.value, document.getElementById('tmp-country')?.value].filter(Boolean).join(' · '),
      checkout_window: month, '对应出游/离店窗口(促销月份)': month,
      evidence: document.getElementById('tmp-bg')?.value || '', plan_source: 'temp_entry',
      theme_keyword: document.getElementById('tmp-keyword')?.value || '',
    };
    const r = await this.fetch('/api/v2/agent1/manual-calendar/submit-pool', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_rows: [row], operator: 'marketer' }),
    });
    if (!r.ok) { alert(r.error || '提交失败'); return; }
    alert('已送入评审池'); await this.refresh(); this.setTab('work');
  },

  async uploadAgent1TempFile() {
    const file = document.getElementById('a1-intel-file')?.files?.[0];
    if (!file) { alert('请选择文件'); return; }
    const fd = new FormData(); fd.append('file', file); fd.append('operator', 'marketer');
    const r = await fetch(this.API + '/api/v2/agent1/manual-calendar/upload-pool', { method: 'POST', body: fd });
    const data = await r.json();
    if (!data.ok) { alert(data.error || '上传失败'); return; }
    alert(`已送入评审池 ${data.inserted || 0} 条`); await this.refresh(); this.setTab('work');
  },

  async renderAgent1ReviewPool() {
    const ws = await this.fetch('/api/v2/workspace');
    this.data.workspace = ws;
    const items = this.normalizeReviewPoolItems(ws);
    const selectedMonths = Array.isArray(this.agent1ReviewMonths) ? this.agent1ReviewMonths : [];
    const sel = selectedMonths.length === 1 ? selectedMonths[0] : null;
    const monthOrder = selectedMonths.length ? [...selectedMonths, ...Array.from({length:12},(_,i)=>i+1).filter(n=>!selectedMonths.includes(n))] : Array.from({ length: 12 }, (_, i) => i + 1);
    const monthStrip = monthOrder.map(n => {
      const cnt = items.filter(it => it.monthNum === n).length;
      const active = selectedMonths.includes(n);
      const selectedHeight = active && cnt > 0 ? ` style="min-height:${Math.max(84, cnt * 84 + Math.max(0, cnt - 1) * 10)}px"` : '';
      return `<button type="button" class="month-strip-btn ${active ? 'active' : ''}"${selectedHeight} onclick="App.setAgent1ReviewMonth(${n})">${n}月<span class="cnt">${cnt} 场</span></button>`;
    }).join('');
    const filtered = selectedMonths.length ? items.filter(it => selectedMonths.includes(it.monthNum)) : items;
    const cardHtml = it => `
        <div class="review-pool-card${it.reviewed ? ' reviewed' : ''}">
        <div><strong>${this.escHtml(it.name)}</strong>${it.pending && !it.reviewed ? ' <span class="tag tag-planned">待定</span>' : ''}
          <div class="review-pool-meta">${it.month} · 类型 <strong>${this.escHtml(it.activityType)}</strong> · 入口 ${this.escHtml(it.entryLabel)} · ${this.escHtml(it.dest)} · 主题词：${this.escHtml(it.keyword)}</div></div>
        <div class="review-pool-actions">
          <button type="button" class="btn btn-sm ${it.reviewed ? '' : 'btn-primary'}" data-action="${it.type === 'campaign' ? 'review-campaign' : 'review-suggestion'}" data-id="${this.escAttr(it.id)}" data-schema="${it.schemaType}">${it.reviewed ? '已评审' : '去评审'}</button>
          <button type="button" class="btn btn-sm" onclick="App.toggleAgent1Pending('${this.escAttr(it.key)}')">${it.pending ? '取消待定' : '待定'}</button>
          <button type="button" class="btn btn-sm" data-action="${it.type === 'campaign' ? 'reject-proposal' : 'reject-suggestion'}" data-id="${this.escAttr(it.id)}">删除</button>
        </div></div>`;
    const grouped = Array.from({length:12},(_,i)=>i+1).map(n => ({n, items: filtered.filter(it => it.monthNum === n)})).filter(g => g.items.length);
    const groupedHtml = grouped.map(g => `<section class="review-month-group"><div class="review-month-title"><strong>${g.n}月</strong><span>${g.items.length} 场活动</span></div><div class="review-month-grid">${g.items.map(cardHtml).join('')}</div></section>`).join('');
    const monthFilters = `<div class="review-month-filters"><button class="btn btn-sm ${selectedMonths.length===0?'btn-primary':''}" onclick="App.clearAgent1ReviewMonths()">全选</button>${Array.from({length:12},(_,i)=>i+1).map(n=>`<button class="btn btn-sm ${selectedMonths.includes(n)?'btn-primary':''}" onclick="App.setAgent1ReviewMonth(${n})">${n}月</button>`).join('')}</div>`;
    return `${this.agent1TabsHtml()}<div class="card"><div class="card-head">营销活动评审池 <span>${items.length} 项</span></div>
      <div class="card-body review-pool-groups">${monthFilters}${groupedHtml || '<div class="empty">暂无待审</div>'}</div></div>`;
  },

  async renderAgent1AnnualPlan() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    this.data.workspace = ws;
    const byMonth = ws.human_calendar?.by_month || {};
    const sel = this.agent1AnnualMonth || new Date().getMonth() + 1;
    const year = this.agent1PlanningYear || 2027;
    const yearOpts = [year - 1, year, year + 1, year + 2].map(y =>
      `<option value="${y}" ${y === year ? 'selected' : ''}>${y}年</option>`
    ).join('');
    const daysInMonth = new Date(year, sel, 0).getDate();
    const allActs = [];
    Object.entries(byMonth).forEach(([mk, list]) => list.forEach(a => allActs.push({ ...a, _monthKey: mk })));
    const yearActs = allActs.filter(a => this.activityInPlanningYear(a, year));
    const monthActs = yearActs.filter(a => this.activityLaunchMonth(a) === sel);
    const dayMap = {}; for (let d = 1; d <= daysInMonth; d++) dayMap[d] = [];
    monthActs.forEach(a => {
      const ld = a.launch_date || a.start_date || a.promotion_date || '';
      let day = 1;
      const dm = String(ld).match(/-(\d{2})/);
      if (dm) day = Math.min(daysInMonth, parseInt(dm[1], 10));
      dayMap[day].push(a);
    });
    const monthStrip = Array.from({ length: 12 }, (_, i) => {
      const n = i + 1;
      const cnt = yearActs.filter(a => this.activityLaunchMonth(a) === n).length;
      return `<button type="button" class="month-strip-btn ${sel === n ? 'active' : ''}" onclick="App.setAgent1AnnualMonth(${n})">${n}月<span class="cnt">${cnt} 场</span></button>`;
    }).join('');
    const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
    const firstDow = new Date(year, sel - 1, 1).getDay();
    const weekdayHead = WEEKDAYS.map(w => `<div class="day-weekhead">${w}</div>`).join('');
    const leadingPads = Array.from({ length: firstDow }, () => `<div class="day-cell day-cell-pad empty-day"></div>`).join('');
    const dayCells = Array.from({ length: daysInMonth }, (_, i) => {
      const d = i + 1;
      const dow = new Date(year, sel - 1, d).getDay();
      const acts = dayMap[d] || [];
      const actsHtml = acts.map(a => {
        const cid = this.escAttr(a.campaign_id);
        const meta = this.agent2ActMeta(a);
        const typeColor = this.agent2TypeColor(meta.type);
        return `<div class="day-act day-act-link" role="button" tabindex="0" onclick="App.openAnnualPlanDetail('${cid}')" title="点击查看活动详情" style="border-left:3px solid ${typeColor}">
          <div>${this.escHtml(meta.name)}</div>
          <div style="color:#6b7280">${this.escHtml(meta.dest)} · <span style="color:${typeColor}">${this.escHtml(meta.type)}</span></div>
        </div>`;
      }).join('');
      return `<div class="day-cell ${acts.length ? '' : 'empty-day'}"><div class="day-num">${d}<span class="day-w">周${WEEKDAYS[dow]}</span></div>${actsHtml}</div>`;
    }).join('');
    const tail = (firstDow + daysInMonth) % 7;
    const trailingPads = tail ? Array.from({ length: 7 - tail }, () => `<div class="day-cell day-cell-pad empty-day"></div>`).join('') : '';
    const emptyAnnual = yearActs.length === 0;
    return `${this.agent1TabsHtml()}
      <div class="card"><div class="card-head annual-plan-head">
        <label style="font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px">规划年
          <select class="year-select" onchange="App.setAgent1PlanningYear(this.value)">${yearOpts}</select>
        </label>
        <span>${sel}月 · ${monthActs.length} 场 · 全年 ${yearActs.length} 场</span>
        <button class="btn btn-sm" onclick="App.seedDemoCalendar2027()" title="加载 2027 演示活动">📋 加载演示数据</button>
        <button class="btn btn-sm btn-primary agent1-download-btn" onclick="App.downloadAnnualCalendar()" title="导出已采纳的全年营销日历（CSV 表格）">📥 下载营销日历</button>
      </div>
      ${emptyAnnual ? `<div class="callout" style="margin:0 0 12px;font-size:13px">暂无 ${year} 年活动。点击「加载演示数据」可快速填充 9 场样例（含标准/创意/其他），点击日历中的活动名称查看详情。</div>` : ''}
      <div class="card-body"><div class="month-strip">${monthStrip}</div><div class="day-grid">${weekdayHead}${leadingPads}${dayCells}${trailingPads}</div></div></div>`;
  },

  async renderAgent1() {
    if (this.tab === 'generate' || this.tab === 'manual-plan') return this.renderAgent1Generate();
    if (this.tab === 'annual') return this.renderAgent1AnnualPlan();
    return this.renderAgent1ReviewPool();
  },

  async sendToAgent2(id) {
    if (!confirm('确认送入活动建档Agent？')) return;
    const r = await this.fetch(`/api/v2/activities/${this.encId(id)}/send-to-agent2`, { method: 'POST' });
    if (r.require_plan_review) {
      alert(r.error || '请先完成方案评审');
      this.openCampaignReview(id);
      return;
    }
    alert(r.ok ? '已送入活动建档Agent' : (r.error || '失败'));
    if (r.ok) this.navigate('agent2');
  },

  monthOptions(selected) {
    return [1,2,3,4,5,6,7,8,9,10,11,12].map(m => {
      const label = `${m}月`;
      return `<option value="${label}" ${selected === label || selected === m ? 'selected' : ''}>${label}</option>`;
    }).join('');
  },

  esc(v) {
    return String(v || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  },

  escHtml(v) {
    return String(v || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  },

  gpFromTtv(ttv) {
    const text = String(ttv || '');
    const range = text.match(/(\d+(?:\.\d+)?)\s*[-~—至到]+\s*(\d+(?:\.\d+)?)\s*万/);
    const single = range ? null : text.match(/(\d+(?:\.\d+)?)\s*万/);
    if (!range && !single) return '';
    const lo = range ? parseFloat(range[1]) : parseFloat(single[1]);
    const hi = range ? parseFloat(range[2]) : lo;
    const fmt = n => (n < 10 ? String(Number(n.toFixed(1))) : String(Math.round(n)));
    return `${fmt(lo * 0.01)}-${fmt(hi * 0.02)}万`;
  },

  applyDidaGpToPlan(plan) {
    const ttv = plan?.forecast?.expected_ttv || plan?.objectives?.ttv_target || '';
    const gp = this.gpFromTtv(ttv);
    if (!gp) return plan;
    plan.forecast = plan.forecast || {};
    plan.objectives = plan.objectives || {};
    plan.forecast.expected_gp = gp;
    plan.forecast.expected_roi = '预订GP率约1%-2%';
    plan.objectives.gp_target = gp;
    plan.objectives.roi_expectation = '预订GP率约1%-2%';
    if (!plan.objectives.calc_method || (plan.objectives.calc_method.includes('15%') && !plan.objectives.calc_method.includes('转化'))) {
      plan.objectives.calc_method = '预订GP = TTV × 1%–2%';
    }
    const rewrite = s => String(s || '').replace(/(GP[：:]\s*)([0-9,.\-—~至到]+万)/g, `$1${gp}`);
    plan.objectives.target_metrics = rewrite(plan.objectives.target_metrics);
    plan.objectives.primary_goal = rewrite(plan.objectives.primary_goal);
    plan.forecast.value_proposition = rewrite(plan.forecast.value_proposition);
    return plan;
  },

  bindGpFromTtv() {
    const ttvEl = document.getElementById('rv-fc-ttv');
    const gpEl = document.getElementById('rv-fc-gp');
    const roiEl = document.getElementById('rv-fc-roi');
    const objRoi = document.getElementById('rv-obj-roi');
    const calcEl = document.getElementById('rv-obj-calc');
    if (!ttvEl || !gpEl) return;
    const sync = () => {
      const gp = this.gpFromTtv(ttvEl.value);
      if (!gp) return;
      gpEl.value = gp;
      if (roiEl) roiEl.value = '预订GP率约1%-2%';
      if (objRoi) objRoi.value = '预订GP率约1%-2%';
      if (calcEl && (!calcEl.value || (calcEl.value.includes('15%') && !calcEl.value.includes('转化')))) {
        calcEl.value = '预订GP = TTV × 1%–2%';
      }
    };
    ttvEl.addEventListener('input', sync);
    ttvEl.addEventListener('change', sync);
    sync();
  },

  rvField(id, label, value, opts = {}) {
    const ro = opts.readonly ? 'readonly' : '';
    const ph = opts.placeholder ? `placeholder="${opts.placeholder}"` : '';
    const dateLike = /日期|时间|推广月份|起止区间|窗口/.test(label);
    const type = opts.type || (dateLike ? 'date' : 'text');
    const required = opts.required ? 'required' : '';
    return `<div class="form-group"><label>${label}${required ? ' <span class="req">*</span>' : ''}</label>
      <input id="${id}" type="${type}" value="${this.esc(value)}" ${ro} ${required} ${ph} /></div>`;
  },

  rvTextarea(id, label, value, rows = 3) {
    return `<div class="form-group"><label>${label}</label>
      <textarea id="${id}" rows="${rows}">${this.escHtml(value)}</textarea></div>`;
  },

  laneTasksText(tasks) {
    return (tasks || []).map(t =>
      [t.name, t.owner, t.deadline || t.t_label, t.status || 'todo', t.deliverable_url || ''].join(' | ')
    ).join('\n');
  },

  parseLaneTasks(text, lane) {
    return String(text || '').split('\n').map(l => l.trim()).filter(Boolean).map(line => {
      const p = line.split('|').map(s => s.trim());
      return {
        name: p[0] || '',
        owner: p[1] || '',
        deadline: p[2] || '',
        status: p[3] || 'todo',
        deliverable_url: p[4] || '',
        lane,
        accept_criteria: '',
      };
    });
  },

  materialsText(items) {
    return (items || []).map(m => [m.type || m.name || '', m.preview_url || m.url || ''].join(' | ')).join('\n');
  },

  parseMaterials(text) {
    return String(text || '').split('\n').map(l => l.trim()).filter(Boolean).map(line => {
      const p = line.split('|').map(s => s.trim());
      return { type: p[0] || '', preview_url: p[1] || '', status: 'todo' };
    });
  },

  rvSelect(id, label, options, selected) {
    const opts = options.map(o => {
      const v = typeof o === 'string' ? o : o.v;
      const t = typeof o === 'string' ? o : o.t;
      return `<option value="${v}" ${selected === v ? 'selected' : ''}>${t}</option>`;
    }).join('');
    return `<div class="form-group"><label>${label}</label><select id="${id}">${opts}</select></div>`;
  },

  sectionBlock(id, title, hint, reviewFocus, inner, hidden = false) {
    const titleHtml = String(title).replace(/\(([^)]+)\)\s*$/, '<span class="field-en">($1)</span>');
    return `<div class="review-section" id="sec-${id}" ${hidden ? 'style="display:none"' : ''}>
      <h4>${titleHtml}</h4>
      ${hint ? `<p class="hint">${hint}</p>` : ''}
      ${reviewFocus ? `<p class="review-focus"><strong>评审要点：</strong>${reviewFocus}</p>` : ''}
      ${inner}
    </div>`;
  },

  reviewFormHtml(s, opts = {}) {
    const isAi = opts.isAi;
    const src = s.source || {};
    const basic = s.basic || {};
    const bg = s.background || {};
    const data = s.data_insights || {};
    const obj = s.objectives || {};
    const strat = s.strategy || {};
    const cs = s.customer_segment || {};
    const hs = s.hotel_solution || s.hotel_profile || {};
    const cqp = cs.query_profile || {};
    const hqp = hs.query_profile || {};
    const pd = s.product_delivery || s.delivery || {};
    const fc = s.forecast || {};
    const ex = s.execution || {};
    const ai = s.ai_provenance || {};
    const tb = s.task_board || {};
    const lp = s.launch_pack || {};
    const ar = s.archive || {};
    const lanes = tb.task_mode === 'custom' ? (tb.lanes || {}) : { resource: [], plan: [], material: [] };
    const laneText = (key) => this.laneTasksText(lanes[key] || []);

    const deliveryTypes = [
      { v: 'display_only', t: '纯展示推荐（无优惠券）' },
      { v: 'coupon', t: '优惠券驱动' },
      { v: 'mixed', t: '组合触达（展示+优惠券）' },
      { v: 'sms_push', t: '短信/定向推送' },
      { v: 'bundle', t: '打包套餐' },
    ];

    const decisionBanner = isAi ? `<div class="decision-card">
      <div class="decision-card-top">
        <span class="tag tag-ai">${this.escHtml(src.priority || 'P1')}</span>
        <span class="decision-card-conf">${this.escHtml(ai.confidence || '')}</span>
      </div>
      <h4>${this.escHtml(basic.campaign_name || s.campaign_name || 'AI 活动')}</h4>
      <p>${this.escHtml(ai.ai_rationale || '')}</p>
      <div class="decision-card-metrics">
        <span><b>上线</b> ${this.escHtml(basic.start_date || '—')}</span>
        <span><b>入住</b> ${this.escHtml(basic.promotion_time || '—')}</span>
        <span><b>TTV</b> ${this.escHtml(fc.expected_ttv || '—')}</span>
        <span><b>GP</b> ${this.escHtml(fc.expected_gp || '—')}</span>
      </div>
    </div>` : '';

    const sourceSec = this.sectionBlock('source', '① 活动来源与基本信息', '活动从哪来、何时做、优先级',
      '核对来源是否可信、推广窗口是否合理',
      `${this.rvSelect('rv-src', '活动来源', [
        { v: 'human_calendar', t: '飞书人工营销日历' },
        { v: 'ai_intel', t: 'AI 行业情报建议' },
        { v: 'merged', t: '合并 AI 建议到现有活动' },
        { v: 'archive_reference', t: '历史案例参考立项' },
      ], src.plan_source || 'human_calendar')}
      ${this.rvField('rv-src-detail', '来源说明', src.source_detail || '', { placeholder: '如：2026飞书日历11月条目 / 情报报告#123' })}
      <div class="form-row">
        ${this.rvField('rv-name', '活动标题', basic.campaign_name || s.campaign_name || '')}
        ${this.rvSelect('rv-month', '推广月份', [1,2,3,4,5,6,7,8,9,10,11,12].map(m => ({ v: `${m}月`, t: `${m}月` })), basic.promotion_month || s.promotion_month)}
      </div>
      <div class="form-row">
        ${this.rvField('rv-dest', '目的地', basic.target_dest || s.target_dest || '')}
        ${this.rvSelect('rv-type', '活动类型', ['Banner', 'Coupon', 'SMS', '专题页', '组合活动'], basic.campaign_type || s.campaign_type || 'Banner')}
      </div>
      <div class="form-row">
        ${this.rvField('rv-time', '推广时段', basic.promotion_time || s.promotion_time || '', { placeholder: '如：11.1-11.15' })}
        ${this.rvSelect('rv-priority', '优先级', ['P0', 'P1', 'P2'], src.priority || 'P1')}
      </div>
      <div class="form-row">
        ${this.rvField('rv-start', '上线日（AI 拆任务锚点）', basic.start_date || '', { placeholder: 'YYYY-MM-DD' })}
        ${this.rvField('rv-end', '下线日', basic.end_date || '', { placeholder: 'YYYY-MM-DD' })}
      </div>
      ${this.rvField('rv-owner', '负责人', src.owner || '营销师')}`);

    const bgSec = this.sectionBlock('background', '② 活动背景', '市场节点与业务契机',
      '背景是否充分、与目的地/季节是否匹配',
      `${this.rvTextarea('rv-bg-market', '市场/行业背景', bg.market_context || bg.summary || s.background || '', 4)}
      ${this.rvTextarea('rv-bg-trigger', '业务契机（为什么现在做）', bg.business_trigger || '', 3)}
      ${this.rvTextarea('rv-bg-opp', '机会判断', bg.opportunity || '', 3)}`);

    const dataSec = this.sectionBlock('data_insights', '③ 数据分析 · 为什么要做', '用数据证明需求真实存在',
      '数据依据是否充分、结论是否支撑立项',
      `${this.rvTextarea('rv-data-market', '市场/目的地数据', data.market_data || '', 4)}
      ${this.rvTextarea('rv-data-client', '客户行为数据', data.client_behavior_data || '', 4)}
      ${this.rvTextarea('rv-data-hist', '历史同类活动参考', data.historical_reference || '', 3)}
      ${this.rvTextarea('rv-data-comp', '竞争/供给环境', data.competitive_landscape || '', 3)}
      ${this.rvTextarea('rv-data-concl', '数据结论（立项依据）', data.data_conclusion || s.demand_analysis || '', 4)}`);

    const objSec = this.sectionBlock('objectives', '④ 活动目标', '量化目标与预算',
      '目标是否 SMART、预算与 ROI 预期是否合理',
      `${this.rvTextarea('rv-obj-primary', '主目标', obj.primary_goal || '')}
      <div class="form-row">
        ${this.rvField('rv-obj-metrics', '量化指标', obj.target_metrics || s.goals?.target_metrics || '')}
        ${this.rvField('rv-obj-budget', '预算（CNY）', obj.budget_cny || obj.budget_hint || '')}
      </div>
      ${this.rvTextarea('rv-obj-secondary', '次要目标', obj.secondary_goals || '')}
      ${this.rvField('rv-obj-success', '成功标准', obj.success_criteria || obj.primary_kpi || s.goals?.primary_kpi || '')}
      ${this.rvField('rv-obj-roi', 'ROI 预期', obj.roi_expectation || '预订GP率约1%-2%', { placeholder: '预订GP率约1%-2%，不要按15%估GP' })}
      ${this.rvField('rv-obj-process', '过程监控指标', obj.process_metrics || ex.monitoring_focus || '', { placeholder: '曝光 / 点击 / CTR / CVR / GMV / GP' })}
      ${this.rvField('rv-obj-calc', '目标计算方式', obj.calc_method || '预订GP = TTV × 1%–2%', { placeholder: '预订GP = TTV × 1%–2%' })}
      ${this.rvField('rv-obj-base', '对比基准', obj.baseline || '', { placeholder: '去年同期 / 活动前基线 / 对照组' })}`);

    const stratSec = this.sectionBlock('strategy', '⑤ 方案策划', '定位、主题、创意与打法',
      '方案是否清晰可执行、与目标是否对齐',
      `${this.rvField('rv-strat-pos', '活动定位', strat.positioning || '')}
      ${this.rvField('rv-strat-theme', '活动主题', strat.theme || '')}
      ${this.rvTextarea('rv-strat-msg', '核心卖点 / Message', strat.core_message || '')}
      ${this.rvTextarea('rv-strat-creative', '创意方向', strat.creative_direction || '')}
      ${this.rvTextarea('rv-strat-solution', '方案详述', strat.solution_summary || s.solution_analysis || '')}
      ${this.rvTextarea('rv-strat-diff', '差异化 / 竞争策略', strat.differentiation || '')}
      ${this.rvTextarea('rv-strat-mech', '关键机制（玩法）', strat.key_mechanics || '')}
      ${this.rvField('rv-strat-place', '上线位置', strat.placements || pd.display_strategy || '', { placeholder: '首页Banner, 专题页' })}
      ${this.rvField('rv-strat-mats', '素材需求清单', strat.material_needs || '', { placeholder: 'Banner,海报,文案,朋友圈物料' })}`);

    const csSec = this.sectionBlock('customer_segment', '⑥ 目标客户群体', '圈谁、群体特性、为什么选这群人',
      '客群是否精准、能否落地到 MCP 圈客条件',
      `${this.rvField('rv-cs-name', '客群名称', cs.segment_name || '')}
      ${this.rvTextarea('rv-cs-desc', '客群描述', cs.description || '', 4)}
      <div class="form-row">
        ${this.rvField('rv-cs-groups', '客户分组 ID', cs.client_groups || '', { placeholder: 'MCP 分组，如 2,6,11' })}
        ${this.rvField('rv-cs-size', '预估规模', cs.size_estimate || '', { placeholder: '如：约 500 家活跃客户' })}
      </div>
      ${this.rvTextarea('rv-cs-beh', '行为特征（给人看）', cs.behaviors || '')}
      ${this.rvTextarea('rv-cs-pain', '痛点 / 需求', cs.pain_points || '')}
      ${this.rvTextarea('rv-cs-why', '圈选理由（链到③数据结论）', cs.selection_rationale || '')}
      ${this.rvTextarea('rv-cs-ids', '锁定客户 ID（上线前必填，评审时可空）', (cs.locked_client_ids || []).join(', '))}
      <div class="callout" style="margin-top:12px;font-size:12px">Agent2 执行条件（Query Profile · 必填）</div>
      <div class="form-row">
        ${this.rvField('rv-cs-qp-days', '时间窗（天）', cqp.time_window_days ?? 90)}
        ${this.rvField('rv-cs-qp-limit', '客户上限', cqp.client_limit ?? 200)}
      </div>
      <div class="form-row">
        ${this.rvField('rv-cs-qp-source', '行为来源', cqp.behavior_source || 'funnel', { placeholder: 'funnel / events' })}
        ${this.rvField('rv-cs-qp-steps', '漏斗步骤', (cqp.step_codes || ['request','click']).join(','), { placeholder: 'request,click' })}
      </div>`);

    const hsSec = this.sectionBlock('hotel_solution', '⑦ 酒店产品解决方案', '用什么酒店供给满足客群',
      '选品策略是否与客群匹配、供给是否可得',
      `${this.rvTextarea('rv-hs-strat', '选品策略', hs.selection_strategy || hs.description || '', 4)}
      <div class="form-row">
        ${this.rvField('rv-hs-star', '最低星级', hs.star_min || '')}
        ${this.rvField('rv-hs-price', '价格带', hs.price_range || '')}
      </div>
      ${this.rvTextarea('rv-hs-criteria', '筛选条件', hs.hotel_criteria || '')}
      ${this.rvTextarea('rv-hs-types', '推荐酒店类型/清单', hs.recommended_types || '')}
      ${this.rvTextarea('rv-hs-inv', '库存/供给说明', hs.inventory_notes || '')}
      ${this.rvTextarea('rv-hs-price-cmp', '比价/竞争力策略', hs.price_competitiveness || '')}
      ${this.rvTextarea('rv-hs-risk', '供给风险', hs.supply_risk || '')}
      ${this.rvTextarea('rv-hs-ids', '锁定酒店 ID（上线前必填，评审时可空）', (hs.locked_hotel_ids || []).join(', '))}
      <div class="callout" style="margin-top:12px;font-size:12px">Agent2 选品条件（Query Profile · 必填）</div>
      <div class="form-row">
        ${this.rvField('rv-hs-qp-star', '最低星级（数字）', hqp.star_min ?? hs.star_min ?? 4)}
        ${this.rvField('rv-hs-qp-limit', '酒店上限', hqp.hotel_limit ?? 20)}
      </div>
      <div class="form-row">
        ${this.rvField('rv-hs-qp-scope', '选品范围', hqp.scope || 'destination_hot', { placeholder: 'destination_hot' })}
        ${this.rvField('rv-hs-qp-keywords', '关键词优先（逗号）', (hqp.keyword_boost || []).join(','), { placeholder: 'Marina,Bay' })}
      </div>`);

    const pdSec = this.sectionBlock('product_delivery', '⑧ 产品交付方式', '优惠券 vs 纯展示 vs 组合触达',
      '交付形式是否适合客群与目标、成本是否可控',
      `${this.rvSelect('rv-pd-type', '交付类型', deliveryTypes, pd.delivery_type || 'mixed')}
      ${this.rvTextarea('rv-pd-coupon', '优惠券策略（如适用）', pd.coupon_strategy || '', 2)}
      ${this.rvTextarea('rv-pd-display', '展示/推荐策略', pd.display_strategy || pd.mode || '')}
      ${this.rvField('rv-pd-channels', '触达渠道', pd.channels || '')}
      ${this.rvTextarea('rv-pd-landing', '落地页/专区体验', pd.landing_experience || '')}
      ${this.rvTextarea('rv-pd-steps', '执行步骤', pd.execution_steps || s.delivery?.execution_steps || '')}
      ${this.rvTextarea('rv-pd-cost', '成本控制说明', pd.cost_control || '')}
      ${this.rvField('rv-pd-url', '落地页链接', pd.landing_url || '', { placeholder: '上线前补齐，审核时可点击' })}
      ${this.rvField('rv-pd-track', '埋点/监控事件', pd.tracking_events || obj.process_metrics || '', { placeholder: 'Banner点击、专题页访问、领券' })}`);

    const fcSec = this.sectionBlock('forecast', '⑨ 效果预估与业务价值', '预期曝光、转化、TTV；GP 按 TTV × 1%–2%',
      '预估是否有数据依据、业务价值是否大于投入',
      `<div class="form-row">
        ${this.rvField('rv-fc-exp', '预估曝光', fc.expected_exposure || '')}
        ${this.rvField('rv-fc-clk', '预估点击', fc.expected_clicks || '')}
      </div>
      <div class="form-row">
        ${this.rvField('rv-fc-ord', '预估订单', fc.expected_orders || '')}
        ${this.rvField('rv-fc-ttv', '预估 TTV', fc.expected_ttv || '', { placeholder: '如：250-300万' })}
      </div>
      <div class="form-row">
        ${this.rvField('rv-fc-gp', '预估 GP（TTV×1%–2%）', fc.expected_gp || '', { placeholder: '随 TTV 自动计算' })}
        ${this.rvField('rv-fc-roi', '预订 GP 率', fc.expected_roi || '预订GP率约1%-2%')}
      </div>
      ${this.rvTextarea('rv-fc-value', '业务价值说明', fc.value_proposition || '')}
      ${this.rvTextarea('rv-fc-risk', '风险与应对', fc.risk_assessment || '')}`);

    const taskSec = this.sectionBlock('task_board', '⑩ 三线任务板', '资源 / 方案 / 素材 · 采纳后按上线日自动拆，一行一条：名称 | 负责人 | 截止 | 状态 | 交付链接',
      '素材独立一列。没有上线日则无法自动算截止时间。',
      `${this.rvField('rv-tb-launch', '任务锚点上线日', tb.launch_date || basic.start_date || '', { placeholder: 'YYYY-MM-DD，可与①上线日相同' })}
      ${this.rvTextarea('rv-tb-res', '资源线', laneText('resource'), 6)}
      ${this.rvTextarea('rv-tb-plan', '方案线', laneText('plan'), 5)}
      ${this.rvTextarea('rv-tb-mat', '素材线', laneText('material'), 4)}
      ${this.rvTextarea('rv-ex-mile', '里程碑备注', ex.timeline_milestones || '')}
      ${this.rvTextarea('rv-ex-a2', '方案策划交接说明', ex.agent2_handoff || '')}`);

    const launchSec = this.sectionBlock('launch_pack', '⑪ 上线审核包', '上线前大家对着这份核对：来源与做法见①⑤⑧，这里放锁定 ID、监控、素材预览、任务完成',
      '客户 ID、酒店 ID、监控字段、素材链接、任务验收。评审阶段可空。',
      `${this.rvTextarea('rv-lp-clients', '锁定客户 ID', (lp.client_ids || cs.locked_client_ids || []).join(', '))}
      ${this.rvTextarea('rv-lp-hotels', '锁定酒店 ID', (lp.hotel_ids || hs.locked_hotel_ids || []).join(', '))}
      ${this.rvField('rv-lp-url', '落地页链接', lp.landing_url || pd.landing_url || '')}
      ${this.rvTextarea('rv-lp-track', '监控字段', lp.tracking || pd.tracking_events || obj.process_metrics || '')}
      ${this.rvTextarea('rv-lp-mats', '素材预览（类型 | 链接）', this.materialsText(lp.materials || []), 4)}
      ${this.rvTextarea('rv-lp-tasks', '任务完成情况备注', lp.task_completion_note || '')}`);

    const dg = s.diagnosis || {};
    const causes = (dg.root_causes || []).map(c => `${c.label || c.type || ''}：${c.evidence || ''}`).join('\n');
    const optLines = (dg.optimizations || []).map(o => `${o.action || ''}（${o.owner_hint || ''}）`).join('\n');
    const diagSec = this.sectionBlock('diagnosis', '⑫ 效果诊断', 'AI 读主文档假设 + 监控过程/结果 + 任务是否做完，追总根源。在复盘归档Agent 点生成。',
      '过程指标空则诊断只能判定无法归因。',
      `${this.rvField('rv-dg-verdict', '一句话判定', dg.one_line_verdict || '')}
      ${this.rvField('rv-dg-break', '漏斗断裂点', dg.funnel_break || '', { placeholder: 'expose / click / convert / order' })}
      ${this.rvTextarea('rv-dg-causes', '根因', causes, 4)}
      ${this.rvTextarea('rv-dg-opts', '优化策略', optLines, 3)}`);

    const archSec = this.sectionBlock('archive', '⑬ 归档', '实绩与诊断已在文档里；补人工结论即可归档，不必重写前面模块',
      '归档闸门：人工结论非空即可。',
      `${this.rvTextarea('rv-ar-human', '人工结论（归档必填）', ar.human_conclusion || '', 4)}
      ${this.rvTextarea('rv-ar-exp', '可复用经验', ar.experience || '')}
      ${this.rvTextarea('rv-ar-pit', '避坑', ar.pitfalls || '')}`);

    const aiSec = this.sectionBlock('ai_provenance', '⑭ AI 建议依据', 'AI 为什么建议、情报来源',
      'AI 理由是否成立、是否合并到现有日历',
      `${this.rvTextarea('rv-ai-rationale', '为什么建议此活动', ai.ai_rationale || s.ai_rationale || '')}
      ${this.rvField('rv-ai-intel', '情报来源', ai.intel_source || s.intel_source || '', { readonly: true })}
      ${this.rvField('rv-ai-similar', '相似日历活动', ai.similar_calendar_name || s.similar_calendar_name || '', { readonly: true })}
      ${this.rvField('rv-ai-conf', '建议置信度', ai.confidence || '', { placeholder: '高/中/低 + 说明' })}`,
      !isAi);

    return decisionBanner + sourceSec + bgSec + dataSec + objSec + stratSec + csSec + hsSec + pdSec + fcSec + taskSec + launchSec + diagSec + archSec + aiSec;
  },

  collectReviewForm() {
    const gv = id => document.getElementById(id)?.value ?? '';
    const deliveryMap = {
      display_only: '纯展示推荐（无优惠券）',
      coupon: '优惠券驱动',
      mixed: '组合触达（展示+优惠券）',
      sms_push: '短信/定向推送',
      bundle: '打包套餐',
    };
    const pdType = gv('rv-pd-type') || 'mixed';
    const dest = gv('rv-dest');
    const clientGroups = gv('rv-cs-groups');
    const parseIds = s => s.split(/[,，\s]+/).map(x => x.trim()).filter(Boolean);
    const parseNums = s => parseIds(s).map(x => parseInt(x, 10)).filter(n => !Number.isNaN(n));
    const plan = {
      schema_version: 3,
      source: {
        plan_source: gv('rv-src'),
        source_detail: gv('rv-src-detail'),
        owner: gv('rv-owner'),
        priority: gv('rv-priority'),
      },
      basic: {
        campaign_name: gv('rv-name'),
        campaign_type: gv('rv-type'),
        promotion_month: gv('rv-month'),
        promotion_time: gv('rv-time'),
        start_date: gv('rv-start'),
        end_date: gv('rv-end'),
        target_dest: gv('rv-dest'),
      },
      background: {
        market_context: gv('rv-bg-market'),
        business_trigger: gv('rv-bg-trigger'),
        opportunity: gv('rv-bg-opp'),
        summary: gv('rv-bg-market'),
      },
      data_insights: {
        market_data: gv('rv-data-market'),
        client_behavior_data: gv('rv-data-client'),
        historical_reference: gv('rv-data-hist'),
        competitive_landscape: gv('rv-data-comp'),
        data_conclusion: gv('rv-data-concl'),
      },
      objectives: {
        primary_goal: gv('rv-obj-primary'),
        target_metrics: gv('rv-obj-metrics'),
        secondary_goals: gv('rv-obj-secondary'),
        success_criteria: gv('rv-obj-success'),
        budget_cny: gv('rv-obj-budget'),
        roi_expectation: gv('rv-obj-roi'),
        process_metrics: gv('rv-obj-process'),
        calc_method: gv('rv-obj-calc'),
        baseline: gv('rv-obj-base'),
      },
      strategy: {
        positioning: gv('rv-strat-pos'),
        theme: gv('rv-strat-theme'),
        core_message: gv('rv-strat-msg'),
        creative_direction: gv('rv-strat-creative'),
        solution_summary: gv('rv-strat-solution'),
        differentiation: gv('rv-strat-diff'),
        key_mechanics: gv('rv-strat-mech'),
        placements: gv('rv-strat-place'),
        material_needs: gv('rv-strat-mats'),
      },
      customer_segment: {
        segment_name: gv('rv-cs-name'),
        description: gv('rv-cs-desc'),
        client_groups: clientGroups,
        behaviors: gv('rv-cs-beh'),
        pain_points: gv('rv-cs-pain'),
        geo_focus: dest,
        size_estimate: gv('rv-cs-size'),
        selection_rationale: gv('rv-cs-why'),
        locked_client_ids: parseIds(gv('rv-cs-ids') || gv('rv-lp-clients')),
        query_profile: {
          destination: dest,
          time_window_days: parseInt(gv('rv-cs-qp-days') || '90', 10),
          client_group_ids: parseNums(clientGroups),
          behavior_source: gv('rv-cs-qp-source') || 'funnel',
          step_codes: parseIds(gv('rv-cs-qp-steps') || 'request,click'),
          min_funnel_events: 1,
          exclude_test_account: true,
          client_limit: parseInt(gv('rv-cs-qp-limit') || '200', 10),
          sort_by: 'rp_click_pv_desc',
        },
      },
      hotel_solution: {
        selection_strategy: gv('rv-hs-strat'),
        star_min: gv('rv-hs-star'),
        price_range: gv('rv-hs-price'),
        hotel_criteria: gv('rv-hs-criteria'),
        recommended_types: gv('rv-hs-types'),
        inventory_notes: gv('rv-hs-inv'),
        price_competitiveness: gv('rv-hs-price-cmp'),
        supply_risk: gv('rv-hs-risk'),
        locked_hotel_ids: parseIds(gv('rv-hs-ids') || gv('rv-lp-hotels')),
        query_profile: {
          destination: dest,
          time_window_days: parseInt(gv('rv-cs-qp-days') || '90', 10),
          star_min: parseInt(gv('rv-hs-qp-star') || gv('rv-hs-star') || '4', 10),
          sort_by: 'click_cnt_desc',
          hotel_limit: parseInt(gv('rv-hs-qp-limit') || '20', 10),
          scope: gv('rv-hs-qp-scope') || 'destination_hot',
          keyword_boost: parseIds(gv('rv-hs-qp-keywords')),
        },
      },
      product_delivery: {
        delivery_type: pdType,
        delivery_type_label: deliveryMap[pdType] || pdType,
        coupon_strategy: gv('rv-pd-coupon'),
        display_strategy: gv('rv-pd-display'),
        channels: gv('rv-pd-channels'),
        landing_experience: gv('rv-pd-landing'),
        execution_steps: gv('rv-pd-steps'),
        cost_control: gv('rv-pd-cost'),
        landing_url: gv('rv-pd-url') || gv('rv-lp-url'),
        tracking_events: gv('rv-pd-track') || gv('rv-lp-track'),
      },
      forecast: {
        expected_exposure: gv('rv-fc-exp'),
        expected_clicks: gv('rv-fc-clk'),
        expected_orders: gv('rv-fc-ord'),
        expected_ttv: gv('rv-fc-ttv'),
        expected_gp: gv('rv-fc-gp'),
        expected_roi: gv('rv-fc-roi'),
        value_proposition: gv('rv-fc-value'),
        risk_assessment: gv('rv-fc-risk'),
      },
      execution: {
        timeline_milestones: gv('rv-ex-mile'),
        agent2_handoff: gv('rv-ex-a2'),
        monitoring_focus: gv('rv-obj-process') || gv('rv-lp-track'),
      },
      task_board: {
        launch_date: gv('rv-tb-launch') || gv('rv-start'),
        lanes: {
          resource: this.parseLaneTasks(gv('rv-tb-res'), 'resource'),
          plan: this.parseLaneTasks(gv('rv-tb-plan'), 'plan'),
          material: this.parseLaneTasks(gv('rv-tb-mat'), 'material'),
        },
      },
      launch_pack: {
        client_ids: parseIds(gv('rv-lp-clients') || gv('rv-cs-ids')),
        hotel_ids: parseIds(gv('rv-lp-hotels') || gv('rv-hs-ids')),
        landing_url: gv('rv-lp-url') || gv('rv-pd-url'),
        tracking: gv('rv-lp-track') || gv('rv-pd-track') || gv('rv-obj-process'),
        materials: this.parseMaterials(gv('rv-lp-mats')),
        task_completion_note: gv('rv-lp-tasks'),
      },
      diagnosis: {
        one_line_verdict: gv('rv-dg-verdict'),
        funnel_break: gv('rv-dg-break'),
        root_causes: String(gv('rv-dg-causes') || '').split('\n').filter(Boolean).map(line => ({ evidence: line })),
        optimizations: String(gv('rv-dg-opts') || '').split('\n').filter(Boolean).map(line => ({ action: line })),
      },
      archive: {
        human_conclusion: gv('rv-ar-human'),
        experience: gv('rv-ar-exp'),
        pitfalls: gv('rv-ar-pit'),
      },
      ai_provenance: {
        ai_rationale: gv('rv-ai-rationale'),
        intel_source: gv('rv-ai-intel'),
        similar_calendar_name: gv('rv-ai-similar'),
        confidence: gv('rv-ai-conf'),
      },
    };
    return this.applyDidaGpToPlan(plan);
  },

  scrollReviewSection(id) {
    document.getElementById(`sec-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  async openCampaignReview(campaignId, schemaType) {
    try {
      const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/plan-structured`);
      if (!r.ok) { alert(r.error || '加载失败'); return; }
      const src = r.structured?.source?.plan_source || '';
      const st = schemaType || this.resolveReviewSchema({ plan_source: src, ...(r.structured?.basic || {}) });
      this.review = { type: 'campaign', id: campaignId, data: r, confirmed: r.plan_review_confirmed, schemaType: st, useAgent1Schema: true, mode: 'review' };
      this.renderReviewOverlay();
    } catch (e) {
      alert('打开评审失败：' + (e.message || e));
      console.error(e);
    }
  },

  async openAnnualPlanDetail(campaignId) {
    try {
      const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/plan-structured`);
      if (!r.ok) { alert(r.error || '加载失败'); return; }
      const src = r.structured?.source?.plan_source || '';
      const st = this.resolveReviewSchema({ plan_source: src, activity_type: r.structured?.basic?.activity_type });
      this.review = {
        type: 'campaign', id: campaignId, data: r, confirmed: true,
        schemaType: st, useAgent1Schema: true, mode: 'annual-detail', editing: false,
      };
      this.renderReviewOverlay();
    } catch (e) {
      alert('打开活动详情失败：' + (e.message || e));
    }
  },

  enableAnnualDetailEdit() {
    if (!this.review || this.review.mode !== 'annual-detail') return;
    this.review.editing = true;
    this.renderReviewOverlay();
  },

  cancelAnnualDetailEdit() {
    if (!this.review || this.review.mode !== 'annual-detail') return;
    this.review.editing = false;
    this.renderReviewOverlay();
  },

  async saveAnnualDetailReview() {
    await this.saveCampaignReview();
    if (this.review?.mode === 'annual-detail') {
      this.review.editing = false;
      this.renderReviewOverlay();
    }
    await this.refresh();
  },

  async deleteAnnualPlanActivity() {
    const id = this.review?.id;
    if (!id) return;
    if (!confirm('确认从全年计划池删除该活动？删除后不再显示在日历中。')) return;
    const r = await this.fetch(`/api/v2/activities/${this.encId(id)}/remove-from-annual-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator: 'marketer' }),
    });
    if (!r.ok) { alert(r.error || '删除失败'); return; }
    this.closeReview();
    await this.refresh();
    this.setTab('annual');
    alert('已从全年计划池移除');
  },

  async openSuggestionReview(suggestionId, schemaType) {
    try {
      const r = await this.fetch(`/api/v2/suggestions/${suggestionId}/plan-structured`);
      if (!r.ok) { alert(r.error || '加载失败'); return; }
      this.review = { type: 'suggestion', id: suggestionId, data: r, confirmed: false, schemaType: schemaType || 'CREATIVE', useAgent1Schema: true };
      this.renderReviewOverlay();
    } catch (e) {
      alert('打开评审失败：' + (e.message || e));
      console.error(e);
    }
  },

  closeReview() {
    this.review = null;
    const el = document.getElementById('review-overlay');
    if (el) el.innerHTML = '';
    el?.classList.add('hidden');
  },

  renderReviewOverlay() {
    const rv = this.review;
    if (!rv) return;
    let el = document.getElementById('review-overlay');
    if (!el) {
      el = document.createElement('div');
      el.id = 'review-overlay';
      document.body.appendChild(el);
    }
    const previousBody = el.querySelector('.review-body');
    const previousScrollTop = previousBody ? previousBody.scrollTop : 0;
    const previousScrollLeft = previousBody ? previousBody.scrollLeft : 0;
    el.classList.remove('hidden');
    const s = rv.data.structured || {};
    const isAnnualDetail = rv.mode === 'annual-detail';
    const isArchiveDetail = rv.mode === 'archive-detail';
    const isAi = rv.type === 'suggestion';
    const schemaType = rv.schemaType || (isAi ? 'CREATIVE' : 'STANDARD');
    const useA1 = !isArchiveDetail && rv.useAgent1Schema !== false;
    const readonly = isAnnualDetail && !rv.editing;
    const pct = isArchiveDetail ? this.archiveCompletionPct(s) : null;
    const activityTitle = s.basic?.campaign_name || s.campaign_name || rv.id;
    const title = (isArchiveDetail || isAnnualDetail || useA1)
      ? activityTitle
      : (isAi ? 'AI 建议方案评审' : '活动方案评审');
    const hint = isArchiveDetail
      ? ''
      : isAnnualDetail
        ? (readonly ? '查看已采纳活动完整字段 · 点击「编辑」后可修改并保存' : '编辑模式 · 修改后请点击「保存」')
        : (useA1 ? '人工标准 · 评审' : '先看决策摘要，再按模块核对后采纳。');
    const formHtml = isArchiveDetail
      ? this.agent2ArchiveFormHtml(s)
      : useA1
        ? this.agent1CalendarReviewFormHtml(s, { schemaType, isAi, readonly })
        : this.reviewFormHtml(s, { isAi });
    const navHtml = isArchiveDetail
      ? ((window.AGENT2_FIELDS || {}).groups || []).map(grp => {
          const sub = grp.appendTaskBoard
            ? `<button type="button" class="review-nav-item review-nav-sub" onclick="App.scrollReviewSection('task_board')">↳ 三线任务板</button>`
            : '';
          const navLabel = grp.group.replace(/^[①-⑤]\s*/, '');
          return `<button type="button" class="review-nav-item" onclick="App.scrollReviewSection('${grp.id}')">${navLabel}</button>${sub}`;
        }).join('')
      : useA1
        ? ((window.AGENT1_FIELDS || {})[schemaType] || []).map((grp, gi) =>
            `<button type="button" class="review-nav-item" onclick="App.scrollReviewSection('a1g${gi}')">${grp.group}</button>`
          ).join('')
        : (rv.data.sections || []).filter(sec => isAi || sec.id !== 'ai_provenance').map(sec =>
            `<button type="button" class="review-nav-item" onclick="App.scrollReviewSection('${sec.id}')">${sec.title.replace(/^[①-⑳]\s*/, '')}</button>`
          ).join('');
    let footer;
    if (isArchiveDetail) {
      footer = `<button class="btn" onclick="App.closeReview()">返回日历</button>
         <button class="btn" onclick="App.addArchiveTask()">创建任务</button>
         <button class="btn btn-primary" onclick="App.saveArchiveDetail()">保存档案</button>`;
    } else if (isAnnualDetail) {
      footer = `<button class="btn" onclick="App.closeReview()">返回</button>
         ${readonly
           ? `<button class="btn btn-primary" onclick="App.enableAnnualDetailEdit()">编辑</button>`
           : `<button class="btn" onclick="App.cancelAnnualDetailEdit()">取消编辑</button>
              <button class="btn btn-primary" onclick="App.saveAnnualDetailReview()">保存</button>`}
         <button class="btn" style="color:#dc2626;border-color:#fca5a5" onclick="App.deleteAnnualPlanActivity()">删除</button>`;
    } else if (isAi) {
      footer = `<button class="btn" onclick="App.closeReview()">返回列表</button>
         <button class="btn" onclick="App.saveSuggestionDraft()">保存修改</button>
         <button class="btn btn-success" onclick="App.adoptSuggestion()">确认采纳 · 进入全年计划池</button>`;
    } else {
      footer = `<button class="btn" onclick="App.closeReview()">返回列表</button>
         <button class="btn" onclick="App.saveCampaignReview()">保存修改</button>
         <button class="btn btn-primary" onclick="App.confirmCampaignReview()">确认采纳 · 进入全年计划池</button>`;
    }
    el.innerHTML = `<div class="review-backdrop" onclick="App.closeReview()"></div>
      <div class="review-panel review-panel-wide">
        <div class="review-head">
          <div><h3>${title}</h3><p class="hint">${hint}</p></div>
          <button class="btn btn-sm" onclick="App.closeReview()">✕</button>
        </div>
        <div class="review-layout">
          <nav class="review-nav">${navHtml}</nav>
          <div class="review-body">${formHtml}</div>
        </div>
        <div class="review-foot">${footer}</div>
      </div>`;
    const nextBody = el.querySelector('.review-body');
    if (nextBody) {
      nextBody.scrollTop = previousScrollTop;
      nextBody.scrollLeft = previousScrollLeft;
    }
    requestAnimationFrame(() => {
      if (isArchiveDetail && rv.scrollTask) {
        const el = document.getElementById(`archive-task-${rv.scrollTask}`);
        if (el) {
          el.classList.add('task-highlight');
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        rv.scrollTask = null;
      }
      if (!useA1 && !isArchiveDetail) {
        this.bindGpFromTtv();
        this.refreshGrowthWarn();
        const body = document.querySelector('#review-overlay .review-body');
        if (body) body.oninput = () => this.refreshGrowthWarn();
      }
    });
  },

  _collectReviewStructured() {
    const rv = this.review;
    if (!rv) return {};
    if (rv.mode === 'archive-detail') {
      return this.collectAgent2ArchiveForm(rv.data.structured);
    }
    if (rv.useAgent1Schema !== false) {
      return this.collectAgent1ReviewForm(rv.schemaType || 'STANDARD', rv.data.structured);
    }
    return this.collectReviewForm();
  },

  async saveCampaignReview() {
    const structured = this._collectReviewStructured();
    const r = await this.fetch(`/api/v2/activities/${this.encId(this.review.id)}/plan-structured`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ structured }),
    });
    alert(r.ok ? '方案已保存' : (r.error || '保存失败'));
  },

  async confirmCampaignReview() {
    await this.saveCampaignReview();
    const r = await this.fetch(`/api/v2/activities/${this.encId(this.review.id)}/confirm-plan-review`, { method: 'POST' });
    if (!r.ok) { alert(r.error || '确认失败'); return; }
    this.review.confirmed = true;
    const gaps = this.growthGapsFromForm();
    const extra = gaps.length ? `\n\n建议补充${gaps.join('、')}，否则无法评估活动是否达成。` : '';
    alert('已采纳进入全年计划池，可在「第三步 · 全年计划池」查看' + extra);
    this.closeReview();
    await this.refresh();
    this.render();
  },

  async saveSuggestionDraft() {
    const structured = this._collectReviewStructured();
    const r = await this.fetch(`/api/v2/suggestions/${this.review.id}/plan-structured`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ structured }),
    });
    alert(r.ok ? '草稿已保存' : (r.error || '保存失败'));
  },

  async adoptSuggestion() {
    const structured = this._collectReviewStructured();
    const month = structured.basic?.promotion_month || structured.promotion_month;
    if (!month) {
      alert('请选择推广月份');
      return;
    }
    const r = await this.fetch(`/api/v2/suggestions/${this.review.id}/review`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'approve',
        promotion_month: month,
        structured_plan: structured,
      }),
    });
    if (!r.ok) { alert(r.error || '采纳失败'); return; }
    const gaps = this.growthGapsFromForm();
    const extra = gaps.length ? `\n\n建议补充${gaps.join('、')}，否则无法评估活动是否达成。` : '';
    alert(`已采纳并入日历（${month}），活动 ID: ${r.campaign_id || ''}` + extra);
    this.closeReview();
    await this.refresh();
    this.render();
  },

  async rejectCalendarProposal(campaignId) {
    if (!confirm('确认拒绝该飞书规划？将移出方案库待审，不会进入全年计划池（记录仍保留）。')) return;
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/reject-proposal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator: 'marketer' }),
    });
    if (!r.ok) {
      alert(r.error || '拒绝失败');
      return;
    }
    await this.refresh();
    this.render();
  },

  async reviewSuggestion(id, action) {
    await this.fetch(`/api/v2/suggestions/${id}/review`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    await this.refresh();
    this.render();
  },

  /* ── Agent2 · 活动建档 ── */
  agent2Activities() {
    const ws = this.data.workspace || {};
    return (ws.human_calendar?.full_year || []).filter(a => this.activityInPlanningYear(a, this.agent2Year || 2027));
  },

  agent2ActMeta(a) {
    let s = {};
    try {
      if (a.plan_structured_json) s = typeof a.plan_structured_json === 'string'
        ? JSON.parse(a.plan_structured_json) : a.plan_structured_json;
    } catch (_) { /* ignore */ }
    const basic = s.basic || {};
    const strat = s.strategy || {};
    const sched = s.schedule || {};
    const launchRaw = sched.launch_date || basic.start_date || a.launch_date || a.start_date || '';
    const timeM = String(launchRaw).match(/T(\d{2}:\d{2})/);
    return {
      id: a.campaign_id,
      name: basic.campaign_name || a.campaign_name || a.activity_name || '—',
      type: this.normalizeActivityType(basic.activity_type || a.activity_type || a.campaign_type),
      theme: strat.main_theme || strat.theme || basic.campaign_name || '—',
      dest: basic.target_dest || a.target_dest || a.destination_region || '—',
      travelMonth: basic.promotion_window || basic.promotion_month || a.promotion_month || '—',
      launch: launchRaw,
      launchTime: timeM ? timeM[1] : (String(launchRaw).length >= 10 ? launchRaw.slice(5, 10) : ''),
    };
  },

  normalizeActivityType(t) {
    const s = String(t || '');
    if (s === 'AI创意' || s.includes('创意')) return 'AI创意';
    if (s === '其他') return '其他';
    if (s === '人工标准' || s.includes('标准')) return '人工标准';
    return '人工标准';
  },
  agent2TypeColor(type) {
    const t = this.normalizeActivityType(type);
    if (t === 'AI创意') return '#7c3aed';
    if (t === '其他') return '#6b7280';
    return '#2563eb';
  },

  async seedDemoCalendar2027(opts = {}) {
    const r = await this.fetch('/api/v2/demo/seed-agent2-case', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force: !!opts.force }),
    });
    if (r.ok === false) { alert(r.error || r.message || '加载失败'); return r; }
    this.agent1PlanningYear = 2027;
    this.agent2Year = 2027;
    if (opts.month) this.agent1AnnualMonth = opts.month;
    if (opts.month) this.agent2Month = opts.month;
    await this.refresh();
    alert(r.message || `已加载 ${r.inserted || 0} 场演示活动`);
    this.render();
    return r;
  },

  async seedAgent2DemoCase() {
    await this.seedDemoCalendar2027({ month: 9, force: true });
  },

  setAgent2CalView(v) { this.agent2CalView = v; this.render(); },
  setAgent2Search(v) {
    this.agent2Search = v;
    const pos = String(v || '').length;
    this.render().then(() => {
      const input = document.querySelector('.agent2-search input[type="search"]');
      if (input) { input.focus(); input.setSelectionRange(pos, pos); }
    });
  },

  agent2GoToday() {
    const t = new Date();
    this.agent2Year = this.agent1PlanningYear || t.getFullYear();
    this.agent2Month = t.getMonth() + 1;
    this.agent2Day = t.getDate();
    this.render();
  },

  agent2CalEventHtml(a, meta) {
    const cid = this.escAttr(a.campaign_id);
    const color = this.agent2TypeColor(meta.type);
    const tip = [meta.type, meta.theme, meta.dest, meta.travelMonth].join(' · ');
    return `<div class="cal-event" style="border-left-color:${color}" onclick="event.stopPropagation();App.openArchiveDetail('${cid}')" title="${this.escAttr(tip)}">
      <span class="dot" style="color:${color}">●</span>
      <div class="cal-event-body">
        <div class="cal-event-title">${meta.launchTime ? `<span class="cal-event-time">${this.escHtml(meta.launchTime)}</span>` : ''}${this.escHtml(meta.name)}</div>
        <div class="cal-event-tags">
          <span>${this.escHtml(meta.type)}</span>
          <span>${this.escHtml(meta.theme.length > 8 ? meta.theme.slice(0, 8) + '…' : meta.theme)}</span>
        </div>
        <div class="ev-meta">${this.escHtml(meta.dest)} · 出游 ${this.escHtml(meta.travelMonth)}</div>
      </div>
    </div>`;
  },

  setAgent2Year(y) { this.agent2Year = parseInt(y, 10); this.render(); },
  setAgent2Month(m) { this.agent2Month = m; this.agent2Day = null; this.render(); },
  setAgent2Day(d) { this.agent2Day = d === this.agent2Day ? null : d; this.render(); },
  setAgent2SidebarMode(mode) { this.agent2SidebarMode = mode; this.render(); },
  toggleAgent2Filter(kind, val) {
    const arr = kind === 'type' ? this.agent2FilterTypes : this.agent2FilterThemes;
    const i = arr.indexOf(val);
    if (i >= 0) arr.splice(i, 1); else arr.push(val);
    this.render();
  },

  agent2FilteredActs(acts, metaFn) {
    let list = acts;
    const q = String(this.agent2Search || '').trim().toLowerCase();
    if (q) {
      list = list.filter(a => {
        const m = metaFn(a);
        return [m.name, m.type, m.theme, m.dest, m.travelMonth, a.campaign_id].some(
          x => String(x || '').toLowerCase().includes(q)
        );
      });
    }
    if (this.agent2FilterTypes.length) {
      list = list.filter(a => this.agent2FilterTypes.includes(metaFn(a).type));
    }
    if (this.agent2FilterThemes.length) {
      list = list.filter(a => this.agent2FilterThemes.includes(metaFn(a).theme));
    }
    if (this.agent2Day != null && this.agent2CalView !== 'month') {
      list = list.filter(a => {
        const ld = metaFn(a).launch || a.launch_date || a.start_date || '';
        const dm = String(ld).match(/-(\d{2})-(\d{2})/);
        return dm && parseInt(dm[1], 10) === this.agent2Month && parseInt(dm[2], 10) === this.agent2Day;
      });
    }
    return list;
  },

  agent2ActDayInMonth(a, meta, year, month, daysInMonth) {
    const ld = meta.launch || a.launch_date || a.start_date || '';
    const dm = String(ld).match(/-(\d{2})-(\d{2})/);
    if (dm && parseInt(dm[1], 10) === month) return Math.min(daysInMonth, parseInt(dm[2], 10));
    const pm = this.parseMonthNum(meta.travelMonth || a.promotion_month);
    if (pm === month) return Math.min(daysInMonth, Math.max(1, parseInt(String(ld).slice(8, 10), 10) || 1));
    return 0;
  },

  agent2MiniCalHtml(year, month, dayMap) {
    const daysInMonth = new Date(year, month, 0).getDate();
    const firstDow = new Date(year, month - 1, 1).getDay();
    const today = new Date();
    const isThisMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
    const todayDay = today.getDate();
    const dows = ['日', '一', '二', '三', '四', '五', '六'];
    const head = `<div class="mc-head">
      <button class="btn btn-sm" onclick="App.setAgent2Month(${month > 1 ? month - 1 : 12});${month === 1 ? `App.setAgent2Year(${year - 1})` : ''}">‹</button>
      <strong>${year}年${month}月</strong>
      <button class="btn btn-sm" onclick="App.setAgent2Month(${month < 12 ? month + 1 : 1});${month === 12 ? `App.setAgent2Year(${year + 1})` : ''}">›</button>
    </div>`;
    const dowRow = dows.map(w => `<div class="mc-dow">${w}</div>`).join('');
    const pads = Array.from({ length: firstDow }, () => '<div></div>').join('');
    const days = Array.from({ length: daysInMonth }, (_, i) => {
      const d = i + 1;
      const cls = [
        'mc-day',
        isThisMonth && d === todayDay ? 'today' : '',
        this.agent2Day === d ? 'selected' : '',
        (dayMap[d] || []).length ? 'has-act' : '',
      ].filter(Boolean).join(' ');
      return `<div class="${cls}" onclick="App.setAgent2Day(${d})">${d}</div>`;
    }).join('');
    return `<div class="agent2-mini-cal">${head}<div class="mc-grid">${dowRow}${pads}${days}</div></div>`;
  },

  async openArchiveDetail(campaignId, opts = {}) {
    try {
      const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/plan-structured`);
      if (!r.ok) { alert(r.error || '加载失败'); return; }
      this.review = {
        type: 'campaign', id: campaignId, data: r, mode: 'archive-detail',
        scrollTask: opts.taskCode || null,
      };
      this.renderReviewOverlay();
    } catch (e) {
      alert('打开活动档案失败：' + (e.message || e));
    }
  },

  archiveReqBadge(field, isCreative) {
    const req = field.req || 'opt';
    if (req === 'all' || (req === 'creative' && isCreative) || req === 'launch') {
      return '<span class="archive-required-star" aria-label="必填">*</span>';
    }
    return '';
  },

  archiveFieldEmpty(val) {
    if (Array.isArray(val)) return !val.length;
    return !String(val ?? '').trim();
  },

  agent2FieldTitle(f) {
    const en = f.path || f.key || '';
    return en ? `${f.label} (${en})` : f.label;
  },

  agent2FieldTitleHtml(f) {
    const en = f.path || f.key || '';
    if (!en) return this.escHtml(f.label);
    return `${this.escHtml(f.label)} <span class="field-en">(${this.escHtml(en)})</span>`;
  },

  agent2SectionTitle(grp) {
    return grp.id ? `${grp.group} (${grp.id})` : grp.group;
  },

  archiveFieldLabelHtml(f, isCreative) {
    const badge = this.archiveReqBadge(f, isCreative);
    const helpBtn = f.help
      ? `<button type="button" class="field-help-btn" aria-label="为什么填" onclick="event.preventDefault();App.toggleFieldHelp(this)">?</button>`
      : '';
    return `<div class="field-label-row"><label>${this.agent2FieldTitleHtml(f)}${badge}</label><span class="field-last-editor">${this.escHtml(f.last_editor || '未记录')}</span>${helpBtn}</div>`;
  },

  archiveFieldHelpHtml(f) {
    if (!f.help) return '';
    return `<div class="field-help-pop hidden" role="tooltip">${this.escHtml(f.help)}</div>`;
  },

  toggleFieldHelp(btn) {
    const wrap = btn.closest('.form-group');
    const pop = wrap?.querySelector('.field-help-pop');
    if (!pop) return;
    const willOpen = pop.classList.contains('hidden');
    document.querySelectorAll('.field-help-pop').forEach(p => p.classList.add('hidden'));
    if (willOpen) pop.classList.remove('hidden');
  },

  agent2ArchiveFormHtml(s) {
    const isCreative = window.isCreativeArchive ? window.isCreativeArchive(s) : false;
    const groups = (window.AGENT2_FIELDS || {}).groups || [];
    const getP = window.getPlanPath || ((p, path) => '');
    const fid = (g, f) => `a2-${g.id}-${f.key}`;
    let html = '';
    groups.forEach(grp => {
      const fields = (grp.fields || []).map(f => {
        const val = getP(s, f.path);
        const displayVal = f.key === 'plan_source' && val === 'human_calendar' ? 'manual_standard' : (Array.isArray(val) ? val.join(', ') : (val ?? ''));
        const empty = this.archiveFieldEmpty(val);
        const reqCls = empty && (f.req === 'all' || (f.req === 'creative' && isCreative)) ? 'archive-field-empty' : '';
        const labelHtml = this.archiveFieldLabelHtml(f, isCreative);
        const helpHtml = this.archiveFieldHelpHtml(f);
        const ro = f.readonly ? 'readonly' : '';
        const id = fid(grp, f);
        if (f.type === 'select') {
          const opts = (f.options || []).map(o =>
            `<option value="${this.escAttr(o.v)}" ${String(displayVal) === String(o.v) ? 'selected' : ''}>${this.escHtml(o.t)}</option>`
          ).join('');
          return `<div class="form-group ${reqCls}">${labelHtml}${helpHtml}
            <select id="${id}" data-a2-path="${f.path}" ${ro}>${opts}</select></div>`;
        }
        if ((f.rows || 0) > 1 || f.type === 'ids') {
          return `<div class="form-group ${reqCls}">${labelHtml}${helpHtml}
            <textarea id="${id}" rows="${f.rows || 3}" data-a2-path="${f.path}" ${ro}
              placeholder="${this.escAttr(f.placeholder || (f.type === 'ids' ? '逗号分隔 ID' : ''))}">${this.escHtml(displayVal)}</textarea></div>`;
        }
        const monthType = f.key === 'promotion_month' || f.key === 'promotion_window';
        const dateType = /date|handoff|delivery|done|review/i.test(f.key) || /时间|日期/.test(f.label);
        return `<div class="form-group ${reqCls}">${labelHtml}${helpHtml}
          <input id="${id}" type="${f.type === 'number' ? 'number' : (monthType ? 'month' : (dateType ? 'date' : 'text'))}" value="${this.escAttr(displayVal)}"
            data-a2-path="${f.path}" ${ro} placeholder="${this.escAttr(f.placeholder || '')}" /></div>`;
      }).join('');
      html += this.sectionBlock(grp.id, this.agent2SectionTitle(grp), grp.hint || '', '', fields);
      if (grp.appendTaskBoard) html += this.agent2TaskBoardHtml(s);
    });
    return html;
  },

  agent2TaskBoardHtml(s) {
    const tb = s.task_board || {};
    const lanes = tb.task_mode === 'custom' ? (tb.lanes || {}) : { resource: [], plan: [], material: [] };
    const laneLabels = { resource: '资源线', plan: '方案线', material: '素材线' };
    const renderTask = (t, li) => {
      const code = t.code || `${t.lane}-${li}`;
      const att = (t.deliverable_attachments || []).map(a =>
        `<li>${this.escHtml(a.name || a.url || '')}${a.url ? ` · <a href="${this.escAttr(a.url)}" target="_blank">打开</a>` : ''}</li>`
      ).join('');
      return `<div class="task-card" id="archive-task-${this.escAttr(code)}">
        <div class="task-card-head">
          <strong>${this.escHtml(t.name || '未命名任务')}</strong>
          <button type="button" class="btn btn-sm task-remove-btn" onclick="App.removeArchiveTask('${this.escAttr(code)}')">删除任务</button>
        </div>
        <div class="task-edit-grid">
          <label>任务名称<input data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="name" value="${this.escAttr(t.name || '')}" placeholder="请输入任务名称" /></label>
          <label>任务负责人<input data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="owner" value="${this.escAttr(t.owner || '')}" placeholder="请输入负责人" /></label>
          <label>任务线<select data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="lane" onchange="App.changeArchiveTaskLane(this)"><option value="resource" ${t.lane === 'resource' ? 'selected' : ''}>资源</option><option value="plan" ${t.lane === 'plan' ? 'selected' : ''}>方案</option><option value="material" ${t.lane === 'material' ? 'selected' : ''}>素材</option></select></label>
          <label>任务截止时间<input type="date" data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="deadline" value="${this.escAttr(t.deadline || '')}" /></label>
        </div>
        <div class="task-deliverable">
          <label>交付结果</label>
          <textarea rows="3" data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="deliverable_text"
            placeholder="粘贴分析结论、表格摘要等">${this.escHtml(t.deliverable_text || '')}</textarea>
          <div class="form-row" style="margin-top:6px">
            <input style="flex:1" data-task-lane="${t.lane}" data-task-idx="${li}" data-task-field="deliverable_url"
              value="${this.escAttr(t.deliverable_url || '')}" placeholder="飞书文档 / 云盘 / 图片链接" />
            <input type="file" multiple data-task-lane="${t.lane}" data-task-idx="${li}"
              onchange="App.onArchiveTaskFiles(this)" title="选择本地文件（文件名记录，请上传飞书后补链接）" />
          </div>
          ${att ? `<ul class="task-file-list">${att}</ul>` : ''}
        </div>
      </div>`;
    };
    let body = '';
    ['resource', 'plan', 'material'].forEach(lk => {
      const tasks = lanes[lk] || [];
      if (!tasks.length) return;
      body += `<div class="task-lane-heading task-lane-heading-${lk}"><strong>${laneLabels[lk]}</strong><span>${tasks.length} 项任务</span></div>`;
      body += `<div class="task-lane task-lane-${lk}">`;
      tasks.forEach((t, i) => { body += renderTask(t, i); });
      body += `</div>`;
    });
    const taskCount = ['resource', 'plan', 'material'].reduce((n, lk) => n + (lanes[lk] || []).length, 0);
    if (!body) body = `<div class="task-empty-state">当前还没有任务，请点击“创建任务”开始添加。</div>`;
    return this.sectionBlock('task_board', '② 三线任务板 (task_board)', '任务可自由创建并归入资源、方案或素材线；每个活动最多创建 10 个任务。任务截止时间建议为上线日 T-7。',
      '', `<input type="hidden" id="task-board-custom-mode" value="custom" /><div class="task-board-toolbar"><span>已创建 ${taskCount}/10 个任务</span><button type="button" class="btn btn-primary" onclick="App.addArchiveTask()" ${taskCount >= 10 ? 'disabled' : ''}>+ 创建任务</button></div>
      ${this.rvField('a2-tb-launch', '活动上线日', tb.launch_date || s.basic?.start_date || '', { placeholder: 'YYYY-MM-DD' })}
      ${body}`);
  },

  addArchiveTask() {
    if (!this.review?.data?.structured) return;
    const s = this.collectAgent2ArchiveForm(this.review.data.structured);
    s.task_board = s.task_board || { lanes: {} };
    if (s.task_board.task_mode !== 'custom') s.task_board.lanes = { resource: [], plan: [], material: [] };
    s.task_board.task_mode = 'custom';
    s.task_board.lanes = s.task_board.lanes || {};
    const lanes = s.task_board.lanes;
    const count = ['resource', 'plan', 'material'].reduce((n, lk) => n + (lanes[lk] || []).length, 0);
    if (count >= 10) return alert('每个活动最多可以创建 10 个任务');
    const launch = s.task_board.launch_date || s.basic?.start_date || '';
    let deadline = '';
    if (launch) {
      const d = new Date(`${String(launch).slice(0, 10)}T00:00:00`);
      if (!Number.isNaN(d.getTime())) { d.setDate(d.getDate() - 7); deadline = d.toISOString().slice(0, 10); }
    }
    lanes.resource = lanes.resource || [];
    lanes.resource.push({ code: `custom-${Date.now()}`, lane: 'resource', name: '', owner: '', deadline, deliverable_text: '', deliverable_url: '', deliverable_attachments: [] });
    this.review.data.structured = s;
    this.renderReviewOverlay();
  },

  removeArchiveTask(code) {
    if (!this.review?.data?.structured) return;
    const s = this.collectAgent2ArchiveForm(this.review.data.structured);
    Object.keys(s.task_board?.lanes || {}).forEach(lane => {
      s.task_board.lanes[lane] = (s.task_board.lanes[lane] || []).filter(task => String(task.code || '') !== String(code));
    });
    this.review.data.structured = s;
    this.renderReviewOverlay();
  },

  changeArchiveTaskLane(select) {
    if (!this.review?.data?.structured) return;
    const s = this.collectAgent2ArchiveForm(this.review.data.structured);
    this.review.data.structured = s;
    this.renderReviewOverlay();
  },

  onArchiveTaskFiles(input) {
    const lane = input.dataset.taskLane;
    const idx = parseInt(input.dataset.taskIdx, 10);
    const files = Array.from(input.files || []);
    if (!files.length || !this.review?.data?.structured) return;
    const lanes = this.review.data.structured.task_board?.lanes || {};
    const task = (lanes[lane] || [])[idx];
    if (!task) return;
    task.deliverable_attachments = task.deliverable_attachments || [];
    files.forEach(f => {
      task.deliverable_attachments.push({ name: f.name, kind: f.type || 'file', url: '', note: '本地文件，请上传飞书/云盘后补充链接' });
    });
    const names = files.map(f => f.name).join('、');
    task.deliverable_text = (task.deliverable_text || '') + (task.deliverable_text ? '\n' : '') + `[附件] ${names}`;
    this.renderReviewOverlay();
  },

  collectAgent2ArchiveForm(base) {
    const s = JSON.parse(JSON.stringify(base || {}));
    const setP = window.setPlanPath || (() => {});
    document.querySelectorAll('#review-overlay [data-a2-path]').forEach(el => {
      setP(s, el.dataset.a2Path, el.type === 'number' ? (el.value === '' ? '' : Number(el.value)) : el.value);
    });
    const launchEl = document.getElementById('a2-tb-launch');
    if (launchEl) {
      s.task_board = s.task_board || {};
      s.task_board.launch_date = launchEl.value;
    }
    if (document.getElementById('task-board-custom-mode') && s.task_board?.task_mode !== 'custom') {
      s.task_board = s.task_board || {};
      s.task_board.task_mode = 'custom';
      s.task_board.lanes = { resource: [], plan: [], material: [] };
    }
    document.querySelectorAll('#review-overlay [data-task-field]').forEach(el => {
      const lane = el.dataset.taskLane;
      const idx = parseInt(el.dataset.taskIdx, 10);
      const field = el.dataset.taskField;
      s.task_board = s.task_board || { lanes: {} };
      s.task_board.lanes = s.task_board.lanes || {};
      s.task_board.lanes[lane] = s.task_board.lanes[lane] || [];
      if (s.task_board.lanes[lane][idx]) s.task_board.lanes[lane][idx][field] = el.value;
    });
    if (s.task_board?.lanes) {
      const normalized = { resource: [], plan: [], material: [] };
      Object.values(s.task_board.lanes).flat().forEach(task => {
        const lane = ['resource', 'plan', 'material'].includes(task.lane) ? task.lane : 'resource';
        normalized[lane].push(task);
      });
      s.task_board.lanes = normalized;
    }
    if (s.schedule?.launch_date && !s.basic?.start_date) {
      s.basic = s.basic || {};
      s.basic.start_date = String(s.schedule.launch_date).slice(0, 10);
    }
    return s;
  },

  async saveArchiveDetail() {
    const structured = this.collectAgent2ArchiveForm(this.review.data.structured);
    const r = await this.fetch(`/api/v2/activities/${this.encId(this.review.id)}/plan-structured`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ structured }),
    });
    if (r.ok && r.structured) this.review.data.structured = r.structured;
    alert(r.ok ? '活动档案已保存' : (r.error || '保存失败'));
    if (r.ok) await this.refresh();
  },

  async generateArchiveTaskBoard(force) {
    if (!this.review?.id) return;
    await this.saveArchiveDetail();
    const r = await this.fetch(`/api/v2/activities/${this.encId(this.review.id)}/generate-task-board`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force: !!force }),
    });
    if (r.ok && r.structured) {
      this.review.data.structured = r.structured;
      this.renderReviewOverlay();
      alert('三线任务已生成');
    } else alert(r.error || '拆任务失败');
  },

  archiveCompletionPct(s) {
    const isCreative = window.isCreativeArchive ? window.isCreativeArchive(s) : false;
    const getP = window.getPlanPath || (() => '');
    let need = 0; let ok = 0;
    ((window.AGENT2_FIELDS || {}).groups || []).forEach(grp => {
      (grp.fields || []).forEach(f => {
        if (f.req === 'opt' || f.req === 'launch') return;
        if (f.req === 'creative' && !isCreative) return;
        need += 1;
        if (!this.archiveFieldEmpty(getP(s, f.path))) ok += 1;
      });
    });
    return need ? Math.round((ok / need) * 100) : 0;
  },

  async renderAgent2() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    this.data.workspace = ws;
    if (!this.agent2Year) this.agent2Year = this.agent1PlanningYear || 2027;
    const year = this.agent2Year;
    const month = this.agent2Month || new Date().getMonth() + 1;
    const acts = this.agent2Activities();
    const metaFn = a => this.agent2ActMeta(a);
    const metaCache = {};
    acts.forEach(a => { metaCache[a.campaign_id] = metaFn(a); });
    const types = [...new Set(acts.map(a => metaCache[a.campaign_id].type))].sort();
    const themes = [...new Set(acts.map(a => metaCache[a.campaign_id].theme))].sort();
    const filtered = this.agent2FilteredActs(acts, metaFn);
    const daysInMonth = new Date(year, month, 0).getDate();
    const dayMap = {}; for (let d = 1; d <= daysInMonth; d++) dayMap[d] = [];
    filtered.forEach(a => {
      const m = metaCache[a.campaign_id];
      const day = this.agent2ActDayInMonth(a, m, year, month, daysInMonth);
      if (day > 0) dayMap[day].push(a);
    });
    const today = new Date();
    const isTodayMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
    const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
    const selDay = this.agent2Day || (isTodayMonth ? today.getDate() : 1);
    const view = this.agent2CalView || 'month';
    let mainBody;
    if (this.agent2SidebarMode === 'theme') {
      const byThemeMonth = {};
      themes.forEach(th => { byThemeMonth[th] = Array.from({ length: 12 }, () => []); });
      filtered.forEach(a => {
        const th = metaCache[a.campaign_id].theme;
        const mn = this.parseMonthNum(metaCache[a.campaign_id].travelMonth) || this.parseMonthNum(a.promotion_month) || 1;
        if (byThemeMonth[th]) byThemeMonth[th][mn - 1].push(a);
      });
      const activeThemes = this.agent2FilterThemes.length ? this.agent2FilterThemes : themes;
      mainBody = `<div class="theme-dist-head">按主题 · 1–12 月活动数量${this.agent2FilterThemes.length ? `（已选 ${this.agent2FilterThemes.length} 个主题）` : ''}</div>
        <div class="theme-dist-grid">${Array.from({ length: 12 }, (_, mi) => {
        const n = mi + 1;
        let cnt = 0;
        const names = [];
        activeThemes.forEach(th => {
          (byThemeMonth[th]?.[mi] || []).forEach(a => { cnt += 1; names.push(metaCache[a.campaign_id].name); });
        });
        return `<div class="theme-dist-col"><h5>${n}月</h5><div class="cnt">${cnt}</div>
          ${names.length ? `<ul>${names.slice(0, 4).map(nm => `<li>${this.escHtml(nm)}</li>`).join('')}${names.length > 4 ? `<li>…共 ${names.length} 场</li>` : ''}</ul>` : ''}</div>`;
      }).join('')}</div>`;
    } else if (view === 'list') {
      const listGroups = Array.from({length:12},(_,i)=>i+1).map(n=>({n,items:filtered.filter(a=>(this.parseMonthNum(metaCache[a.campaign_id].travelMonth)||this.parseMonthNum(a.promotion_month))===n)})).filter(g=>g.items.length);
      mainBody = `<div class="review-pool-groups agent2-list-view">${listGroups.map(g=>`<section class="review-month-group"><div class="review-month-title"><strong>${g.n}月</strong><span>${g.items.length} 场活动</span></div><div class="review-month-grid">${g.items.map(a=>{const m=metaCache[a.campaign_id];return `<div class="review-pool-card" onclick="App.openArchiveDetail('${this.escAttr(a.campaign_id)}')"><div><strong>${this.escHtml(m.name)}</strong><div class="review-pool-meta">${this.escHtml(m.launch||'—')} · 类型 ${this.escHtml(m.type)} · 入口 ${this.escHtml(m.dest)} · 主题：${this.escHtml(m.theme)}</div></div><div class="review-pool-actions"><button class="btn btn-sm btn-primary" type="button">查看详情</button></div></div>`}).join('')}</div></section>`).join('') || '<div class="empty">暂无活动</div>'}</div>`;
    } else if (view === 'day') {
      const list = dayMap[selDay] || [];
      mainBody = `<div class="agent2-day-view">
        <h3>${year}年${month}月${selDay}日 · ${WEEKDAYS[new Date(year, month - 1, selDay).getDay()]} · ${list.length} 场</h3>
        ${list.length ? list.map(a => {
          const m = metaCache[a.campaign_id];
          return `<div class="agent2-day-card" onclick="App.openArchiveDetail('${this.escAttr(a.campaign_id)}')">
            <div class="agent2-day-card-title">${this.escHtml(m.name)}</div>
            <div class="agent2-day-card-grid">
              <span><b>类型</b> ${this.escHtml(m.type)}</span>
              <span><b>主题</b> ${this.escHtml(m.theme)}</span>
              <span><b>目的地</b> ${this.escHtml(m.dest)}</span>
              <span><b>出游月</b> ${this.escHtml(m.travelMonth)}</span>
              <span><b>上线</b> ${this.escHtml(m.launch || '—')}</span>
            </div>
          </div>`;
        }).join('') : '<p class="hint">当日暂无活动，可在左侧小月历选其他日期</p>'}
      </div>`;
    } else if (view === 'week') {
      const anchor = selDay;
      const dow = new Date(year, month - 1, anchor).getDay();
      const weekStart = anchor - dow;
      const weekCells = Array.from({ length: 7 }, (_, i) => {
        const d = weekStart + i;
        if (d < 1 || d > daysInMonth) {
          return `<div class="day-cell day-cell-pad empty-day"></div>`;
        }
        const list = dayMap[d] || [];
        const todayCls = isTodayMonth && d === today.getDate() ? 'today' : '';
        const selCls = d === selDay ? 'selected-day' : '';
        const evHtml = list.map(a => this.agent2CalEventHtml(a, metaCache[a.campaign_id])).join('');
        return `<div class="day-cell ${todayCls} ${selCls}" onclick="App.setAgent2Day(${d})">
          <div class="day-num">${d}<span class="day-w">周${WEEKDAYS[(dow + i) % 7]}</span></div>${evHtml}</div>`;
      }).join('');
      mainBody = `<div class="day-grid">${WEEKDAYS.map(w => `<div class="day-weekhead">${w}</div>`).join('')}${weekCells}</div>`;
    } else {
      const firstDow = new Date(year, month - 1, 1).getDay();
      const weekdayHead = WEEKDAYS.map(w => `<div class="day-weekhead">${w}</div>`).join('');
      const leadingPads = Array.from({ length: firstDow }, () => `<div class="day-cell day-cell-pad empty-day"></div>`).join('');
      const dayCells = Array.from({ length: daysInMonth }, (_, i) => {
        const d = i + 1;
        const dow = new Date(year, month - 1, d).getDay();
        const list = dayMap[d] || [];
        const todayCls = isTodayMonth && d === today.getDate() ? 'today' : '';
        const selCls = this.agent2Day === d ? 'selected-day' : '';
        const evHtml = list.map(a => this.agent2CalEventHtml(a, metaCache[a.campaign_id])).join('');
        return `<div class="day-cell ${list.length ? '' : 'empty-day'} ${todayCls} ${selCls}" onclick="App.setAgent2Day(${d})">
          <div class="day-num">${d}<span class="day-w">周${WEEKDAYS[dow]}</span></div>${evHtml}</div>`;
      }).join('');
      const tail = (firstDow + daysInMonth) % 7;
      const trailingPads = tail ? Array.from({ length: 7 - tail }, () => `<div class="day-cell day-cell-pad empty-day"></div>`).join('') : '';
      mainBody = `<div class="day-grid agent2-month-grid">${weekdayHead}${leadingPads}${dayCells}${trailingPads}</div>`;
    }
    const typeChips = types.map(t =>
      `<span class="agent2-chip ${this.agent2FilterTypes.includes(t) ? 'active' : ''}" onclick="App.toggleAgent2Filter('type','${this.escAttr(t)}')">${this.escHtml(t)}</span>`
    ).join('');
    const themeChips = themes.slice(0, 30).map(t =>
      `<span class="agent2-chip ${this.agent2FilterThemes.includes(t) ? 'active' : ''}" onclick="App.toggleAgent2Filter('theme','${this.escAttr(t)}')">${this.escHtml(t.length > 14 ? t.slice(0, 14) + '…' : t)}</span>`
    ).join('');
    const yearOpts = [year - 1, year, year + 1, year + 2].map(y =>
      `<option value="${y}" ${y === year ? 'selected' : ''}>${y}年</option>`).join('');
    const monthOpts = Array.from({ length: 12 }, (_, i) => {
      const n = i + 1;
      return `<option value="${n}" ${n === month ? 'selected' : ''}>${n}月</option>`;
    }).join('');
    const emptyHint = acts.length === 0
      ? `<div class="agent2-empty"><p>暂无终版日历活动</p><p class="hint">请先在 <strong>活动生成Agent → 全年计划池</strong> 采纳活动，终版会同步到此日历。</p>
         <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px">
           <button class="btn btn-sm btn-primary" onclick="App.seedDemoCalendar2027({month:9,force:true})">加载演示数据</button>
           <button class="btn btn-sm" onclick="App.navigate('agent1',{tab:'annual'})">去全年计划池</button>
         </div></div>`
      : '';
    const viewBtns = ['day', 'week', 'month'].map(v => {
      const lbl = { day: '日', week: '周', month: '月' }[v];
      return `<button class="agent2-view-btn ${view === v ? 'active' : ''}" onclick="App.setAgent2CalView('${v}')">${lbl}</button>`;
    }).join('');
    return `${this.phaseBannerHtml('agent2')}
      <div class="agent2-layout">
        <aside class="agent2-sidebar">
          ${this.agent2MiniCalHtml(year, month, dayMap)}
          <div class="agent2-search">
            <input type="search" placeholder="搜索活动名称、目的地…" value="${this.escAttr(this.agent2Search)}"
              oninput="App.setAgent2Search(this.value)" />
          </div>
          <div>
            <h4>上线时间</h4>
            <div class="form-row" style="gap:6px">
              <select class="year-select" style="flex:1" onchange="App.setAgent2Year(this.value)">${yearOpts}</select>
              <select class="year-select" style="flex:1" onchange="App.setAgent2Month(parseInt(this.value,10))">${monthOpts}</select>
            </div>
          </div>
          <div>
            <h4>活动类型</h4>
            <div class="agent2-filter-chips">${typeChips || '<span class="hint">暂无</span>'}</div>
          </div>
          <div>
            <h4>活动主题</h4>
            <div class="agent2-filter-chips">${themeChips || '<span class="hint">暂无</span>'}</div>
          </div>
          <div>
            <h4>视图</h4>
            <button class="btn btn-sm ${view === 'month' ? 'btn-primary' : ''}" style="width:100%;margin-bottom:4px" onclick="App.setAgent2CalView('month')">1 日历视图</button>
            <button class="btn btn-sm ${view === 'list' ? 'btn-primary' : ''}" style="width:100%" onclick="App.setAgent2CalView('list')">2 列表视图</button>
          </div>
          <p class="agent2-sidebar-foot">全年 ${acts.length} 场 · 筛选 ${filtered.length} 场</p>
        </aside>
        <div class="agent2-main">
          <div class="agent2-toolbar">
            <button class="btn btn-sm agent2-today-btn" onclick="App.agent2GoToday()">今天</button>
            <button class="btn btn-sm" onclick="App.setAgent2Month(${month > 1 ? month - 1 : 12})${month === 1 ? `;App.setAgent2Year(${year - 1})` : ''}">‹</button>
            <button class="btn btn-sm" onclick="App.setAgent2Month(${month < 12 ? month + 1 : 1})${month === 12 ? `;App.setAgent2Year(${year + 1})` : ''}">›</button>
            <select class="agent2-date-select" onchange="var p=this.value.split('-');App.setAgent2Year(p[0]);App.setAgent2Month(parseInt(p[1],10))">
              ${Array.from({ length: 12 }, (_, i) => {
                const n = i + 1;
                return `<option value="${year}-${n}" ${n === month ? 'selected' : ''}>${year}年${n}月</option>`;
              }).join('')}
            </select>
            ${this.agent2Day ? `<span class="badge-sm">${month}月${this.agent2Day}日</span>` : ''}
            <span class="spacer"></span>
            <div class="agent2-view-switch">${viewBtns}</div>
          </div>
          <div class="agent2-cal-body">${emptyHint || mainBody}</div>
        </div>
      </div>`;
  },

  async renderLegacyResourceWorkbench() {
    const wh = await this.fetch('/api/v2/warehouse/status');
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    const queue = [...(ws.prep_queue?.urgent || []), ...(ws.prep_queue?.in_progress || [])];
    const cid = queue[0]?.campaign_id || 'CAMP_CAL_08_新加坡F1赛事酒店预订';
    let qp = {}, rpData = {}, todos = [];
    try {
      qp = await this.fetch(`/api/v2/activities/${this.encId(cid)}/query-profile`);
      rpData = await this.fetch(`/api/v2/activities/${this.encId(cid)}/resource-plan`);
      todos = await this.fetch(`/api/v2/activities/${this.encId(cid)}/todos`);
    } catch (_) {}

    const profile = qp.query_profile || {};
    const missing = qp.validation?.missing_fields || [];
    const rp = rpData.resource_plan || {};
    const confirmed = !!rp.resource_confirmed;
    const groups = (profile.client_group_ids || []).join(',');

    const hotels = (rp.hotel_list || []).slice(0, 8).map(h => `
      <tr><td>${h.hotel_id}</td><td>${h.hotel_name}</td><td>${h.star_rating || '—'}</td><td>¥${h.avg_price_cny || '—'}</td>
      <td>${h.price_compare?.has_advantage ? '✓ 有优势' : '需优惠券 ' + (h.price_compare?.suggested_coupon_pct||0) + '%'}</td></tr>`).join('');

    const clients = (rp.client_preview || []).slice(0, 5).map(c => `
      <tr><td>${c.client_id}</td><td>${c.client_group_cn || c.client_group_id || '—'}</td>
      <td>${c.funnel_pv ?? '—'}</td><td>${c.rp_click_pv ?? '—'}</td></tr>`).join('');

    const todoRows = (Array.isArray(todos) ? todos : []).map(t => `
      <tr><td>${t.title}</td><td>${t.owner || '—'}</td>
      <td>${t.is_done ? '✅' : `<button class="btn btn-sm" data-action="complete-todo" data-todo-id="${t.todo_id}">完成</button>`}</td></tr>`).join('');

    return `
      <div class="callout">数仓模式：<strong>${wh.mode}</strong> · 圈客选品是补名单；上方 QBI 七页签才是时机/P80/机构分析 · 活动 <code>${cid}</code></div>
      ${missing.length ? `<div class="callout" style="border-color:#f59e0b">方案 Query Profile 缺项：${missing.join('、')} — 请回 Agent1 补全或在下方手动填写后查询</div>` : ''}
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">Query Profile（来自 Agent1 ⑥⑦ · 运营师可改条件重查）</div>
        <div class="card-body">
          <div class="form-row">
            <div class="form-group"><label>目的地</label><input id="pf-dest" value="${this.escAttr(profile.destination || '')}" /></div>
            <div class="form-group"><label>客户分组 ID</label><input id="pf-groups" value="${this.escAttr(groups)}" placeholder="2,6,11" /></div>
            <div class="form-group"><label>时间窗（天）</label><input id="pf-days" type="number" value="${profile.time_window_days || 90}" /></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>最低星级</label><input id="pf-star" value="${profile.star_min || profile.star_rating || 4}" /></div>
            <div class="form-group"><label>客户上限</label><input id="pf-climit" type="number" value="${profile.client_limit || 200}" /></div>
            <div class="form-group"><label>酒店上限</label><input id="pf-hlimit" type="number" value="${profile.hotel_limit || 20}" /></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>关键词优先</label><input id="pf-keywords" value="${this.escAttr((profile.keyword_boost || []).join(','))}" placeholder="Marina,Bay" /></div>
            <div class="form-group"><label>漏斗步骤</label><input id="pf-steps" value="${this.escAttr((profile.step_codes || ['request','click']).join(','))}" /></div>
          </div>
          <div class="actions">
            <button class="btn" data-action="profile-query" data-campaign-id="${this.escAttr(cid)}">预览 MCP 查询</button>
            <button class="btn btn-primary" data-action="configure-resources" data-campaign-id="${this.escAttr(cid)}">执行圈客选品</button>
            <button class="btn btn-primary" data-action="confirm-resources" data-campaign-id="${this.escAttr(cid)}" ${confirmed ? 'disabled' : ''}>确认锁定资源配置</button>
          </div>
          <div id="profile-result" style="margin-top:12px"></div>
        </div>
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">人工兜底 · 上传/追加 client_id / hotel_id</div>
        <div class="card-body">
          <div class="form-group"><label>客户 ID（逗号或换行分隔）</label>
            <textarea id="ov-clients" rows="2" placeholder="c_5382,c_8821"></textarea></div>
          <div class="form-group"><label>酒店 ID（逗号或换行分隔）</label>
            <textarea id="ov-hotels" rows="2" placeholder="12345,67890"></textarea></div>
          <div class="form-group"><label>覆盖说明（必填）</label>
            <input id="ov-reason" placeholder="如：补入战略大客户 / AI漏选" /></div>
          <div class="actions">
            <button class="btn" data-action="resource-override" data-mode="mixed" data-campaign-id="${this.escAttr(cid)}">追加到 AI 结果</button>
            <button class="btn" data-action="resource-override" data-mode="manual_ids" data-campaign-id="${this.escAttr(cid)}">完全用手动 ID 替换</button>
          </div>
        </div>
      </div>
      <div class="grid grid-2">
        <div class="card">
          <div class="card-head">资源配置结果 · ${confirmed ? '✅ 已锁定' : '⏳ 待确认'}</div>
          <div class="card-body">
            <p style="font-size:13px;margin-bottom:8px">${rp.client_selection_reason || '尚未执行圈客选品'}</p>
            <p style="font-size:13px">圈客 <strong>${rp.client_count || 0}</strong> · 酒店 <strong>${(rp.hotel_list||[]).length}</strong> · ${rp.override_mode || 'auto'}</p>
            <h4 style="margin:14px 0 8px;font-size:13px">客户预览</h4>
            <div class="table-wrap"><table><thead><tr><th>client_id</th><th>分组</th><th>漏斗PV</th><th>RP点击</th></tr></thead>
            <tbody>${clients || '<tr><td colspan=4>暂无</td></tr>'}</tbody></table></div>
            <h4 style="margin:14px 0 8px;font-size:13px">选品列表</h4>
            <div class="table-wrap"><table><thead><tr><th>ID</th><th>酒店</th><th>星级</th><th>均价</th><th>比价</th></tr></thead>
            <tbody>${hotels || '<tr><td colspan=5>暂无</td></tr>'}</tbody></table></div>
          </div>
        </div>
        <div class="card">
          <div class="card-head">待办清单 ${confirmed ? '' : '（确认锁定后生成）'}</div>
          <div class="card-body table-wrap">
            <table><thead><tr><th>任务</th><th>负责</th><th>状态</th></tr></thead>
            <tbody>${todoRows || '<tr><td colspan=3>请先确认锁定资源配置</td></tr>'}</tbody></table>
            ${confirmed ? `<div class="actions" style="margin-top:12px"><button class="btn btn-primary" data-action="submit-test" data-campaign-id="${this.escAttr(cid)}">提交测试</button></div>` : ''}
          </div>
        </div>
      </div>`;
  },

  localISODate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  },

  qbiDefaultDates() {
    const to = new Date();
    const from = new Date();
    from.setFullYear(from.getFullYear() - 1);
    return { from: this.localISODate(from), to: this.localISODate(to) };
  },

  qbiFilterBody() {
    return {
      country: document.getElementById('qbi-country')?.value?.trim() || '',
      city: document.getElementById('qbi-city')?.value?.trim() || '',
      date_from: document.getElementById('qbi-from')?.value || '',
      date_to: document.getElementById('qbi-to')?.value || '',
      customer_type: document.getElementById('qbi-cust')?.value || '全部',
    };
  },

  setQbiTab(id) {
    this.qbiTab = id || 'timing';
    document.querySelectorAll('.qbi-tab').forEach(el => {
      el.classList.toggle('active', el.dataset.tab === this.qbiTab);
    });
    document.querySelectorAll('.qbi-panel').forEach(el => {
      el.classList.toggle('active', el.dataset.panel === this.qbiTab);
    });
  },

  qbiTable(headers, rows) {
    const th = headers.map(h => `<th>${h}</th>`).join('');
    const body = rows.length
      ? rows.join('')
      : `<tr><td colspan="${headers.length}" class="empty" style="padding:16px">暂无数据</td></tr>`;
    return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
  },

  renderPrepAnalysisCard(cid, pack, meta = {}) {
    const filters = pack.filters || {};
    const cal = pack.calendar_inputs || {};
    const dest = pack.destination || meta.destination || cal.destination || '';
    const defaults = this.qbiDefaultDates();
    const cityVal = filters.city || dest;
    const countryVal = filters.country || '';
    const fromVal = filters.date_from || defaults.from;
    const toVal = filters.date_to || defaults.to;
    const custVal = filters.customer_type || '全部';
    const mode = pack.mode || (pack.conclusion ? 'auto' : '');
    const modeLabel = mode === 'manual' ? '手动验证' : mode === 'auto' ? '自动抓取' : '尚未运行';
    const tab = this.qbiTab || 'timing';
    const tabs = [
      { id: 'timing', title: '1 活动时机' },
      { id: 'country', title: '2 国家需求' },
      { id: 'city', title: '3 城市需求' },
      { id: 'dest_segment', title: '4 目的地×客群' },
      { id: 'trend', title: '5 需求趋势' },
      { id: 'hotel_tier', title: '6 酒店分层' },
      { id: 'grain', title: '7 客群×国家×酒店' },
    ];
    const tabBtns = tabs.map(t =>
      `<button type="button" class="qbi-tab ${tab === t.id ? 'active' : ''}" data-action="qbi-tab" data-tab="${t.id}">${t.title}</button>`
    ).join('');
    const empty = !pack.conclusion && !pack.timing;
    const crumb = ['历史预订规律','判断营销时间','筛选目的地','判断客群','判断需求趋势','提取酒店','匹配活动主题','验证资源','上线','复盘沉淀']
      .map((s, i, arr) => `<span>${s}</span>${i < arr.length - 1 ? '<span class="sep">→</span>' : ''}`).join('');
    const custOpts = ['全部', 'TMC', '定制'].map(v =>
      `<option value="${v}" ${custVal === v ? 'selected' : ''}>${v}</option>`
    ).join('');
    return `
      <div class="card" style="margin-bottom:16px" id="qbi-board">
        <div class="card-head">
          <span>Shopping 营销活动决策分析</span>
          <span class="qbi-mode ${mode === 'manual' ? 'manual' : 'auto'}">${modeLabel}${pack.generated_at ? ' · ' + pack.generated_at : ''}</span>
        </div>
        <div class="card-body">
          <div class="qbi-dual">
            <div class="qbi-pane auto">
              <h4>自动抓取</h4>
              <p class="hint">读日历城市 / 月份 / 客群 / 主题，按线下七步拉订单与漏斗，输出结果。人仍确认 ID，上线闸门才锁定。</p>
              <p class="hint">日历城市 <strong>${this.escAttr(cal.destination || dest || '—')}</strong>
                · 月份 ${cal.promotion_month || '—'}
                · 客群 ${this.escAttr(cal.customer_segment || '—')}
                · 数据源 ${pack.data_source || '—'}</p>
              <div class="actions" style="margin-top:8px">
                <button class="btn btn-primary" data-action="prep-analysis" data-mode="auto" data-campaign-id="${this.escAttr(cid)}">读取活动城市并分析</button>
                <button class="btn" data-action="prep-analysis-apply" data-mode="auto" data-campaign-id="${this.escAttr(cid)}">写入主档（不锁 ID）</button>
              </div>
            </div>
            <div class="qbi-pane manual">
              <h4>看板筛选 · 手动验证</h4>
              <p class="hint">改时间、国家、城市、客群后重跑，核对自动结论是否站得住。筛选条件写入同一套七页签。</p>
              <div class="form-row-4">
                <div class="form-group"><label>时间从</label><input id="qbi-from" type="date" value="${this.escAttr(fromVal)}" /></div>
                <div class="form-group"><label>时间到</label><input id="qbi-to" type="date" value="${this.escAttr(toVal)}" /></div>
                <div class="form-group"><label>国家</label><input id="qbi-country" placeholder="如 Hong Kong" value="${this.escAttr(countryVal)}" /></div>
                <div class="form-group"><label>城市</label><input id="qbi-city" placeholder="如 香港 / 新加坡" value="${this.escAttr(cityVal)}" /></div>
              </div>
              <div class="form-row" style="margin-top:8px">
                <div class="form-group"><label>客群</label>
                  <select id="qbi-cust">${custOpts}</select>
                </div>
                <div class="form-group"><label>&nbsp;</label>
                  <div class="actions" style="margin-top:0">
                    <button class="btn btn-primary" data-action="prep-analysis" data-mode="manual" data-campaign-id="${this.escAttr(cid)}">按筛选重跑</button>
                    <button class="btn" data-action="prep-analysis-apply" data-mode="manual" data-campaign-id="${this.escAttr(cid)}">写入主档（不锁 ID）</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="qbi-crumb">${crumb}</div>
          <div class="qbi-tabs">${tabBtns}</div>
          ${empty
            ? '<p style="font-size:13px;color:#6b7280">尚未跑过。左侧自动读取活动城市，或右侧改筛选后重跑，结果都写在这七个页签里。</p>'
            : `<p style="font-size:13px;margin-bottom:12px">${this.escAttr(pack.conclusion || '')}</p>${this.renderQbiPanels(pack, tab)}`}
        </div>
      </div>`;
  },

  renderQbiPanels(pack, active) {
    const timing = pack.timing || {};
    const hotels = pack.hotels || {};
    const tags = hotels.tag_counts || {};
    const countryRows = ((pack.country || {}).rows || []).map(r =>
      `<tr><td>${this.escAttr(r.name)}</td><td>${r.orders || 0}</td><td>${r.rns || 0}</td><td>${r.ttv || 0}</td></tr>`
    );
    const cityRows = ((pack.city || {}).rows || []).map(r =>
      `<tr><td>${this.escAttr(r.name)}</td><td>${r.orders || 0}</td><td>${r.rns || 0}</td><td>${r.ttv || 0}</td></tr>`
    );
    const mix = ((pack.dest_segment || {}).biz_type_mix || []).map(x =>
      `<tr><td>${this.escAttr(x.type)}</td><td>${x.count || 0}</td><td>${x.share_pct || 0}%</td></tr>`
    );
    const clients = ((pack.dest_segment || {}).preview || []).map(c =>
      `<tr><td>${this.escAttr(c.client_id)}</td><td>${this.escAttr(c.client_name || '—')}</td><td>${this.escAttr(c.biz_type || '—')}</td><td>${c.orders || 0}</td><td>${c.rns || 0}</td></tr>`
    );
    const curve = ((pack.trend || {}).curve || []).map(c =>
      `<tr><td>${c.month}月</td><td>${c.orders || 0}</td><td>${c.rns || 0}</td><td>${c.ttv || 0}</td></tr>`
    );
    const tagRow = ['高需求高转化','高需求低转化','低需求高转化','低需求低转化','无产'].map(k => {
      const hl = k === '高需求低转化' ? ' class="hotel-tag-hl"' : '';
      return `<tr><td${hl}>${k}${k === '高需求低转化' ? '（投放主靶）' : ''}</td><td${hl}>${tags[k] || 0}</td></tr>`;
    });
    const hotelRows = ((hotels.top_hotels || [])).map(h => {
      const hl = h.hotel_tag === '高需求低转化' ? ' class="hotel-tag-hl"' : '';
      return `<tr>
        <td>${this.escAttr(h.dida_hotel_id)}</td>
        <td>${this.escAttr(h.dida_hotel_name || '—')}</td>
        <td${hl}>${this.escAttr(h.hotel_tag || '—')}</td>
        <td>${h.request_pv || 0}</td><td>${h.rns || 0}</td>
        <td>${h.star || '—'}</td><td>${this.escAttr(h.chain || '—')}</td>
        <td>${h.avg_price_cny ?? '—'}</td>
      </tr>`;
    });
    const grainRows = ((pack.grain || {}).rows || []).map(h => {
      const hl = h.hotel_tag === '高需求低转化' ? ' class="hotel-tag-hl"' : '';
      return `<tr>
        <td>${this.escAttr(h.dida_hotel_id)}</td>
        <td>${this.escAttr(h.dida_hotel_name || '—')}</td>
        <td>${this.escAttr(h.city_name || '—')}</td>
        <td${hl}>${this.escAttr(h.hotel_tag || '—')}</td>
        <td>${h.request_pv || 0}</td><td>${h.bks || 0}</td><td>${h.rns || 0}</td>
        <td>${h.ttv || 0}</td><td>${h.gp || 0}</td>
      </tr>`;
    });
    const panel = (id, html) =>
      `<div class="qbi-panel ${active === id ? 'active' : ''}" data-panel="${id}">${html}</div>`;
    return [
      panel('timing', `
        <div class="grid grid-4" style="margin-bottom:12px">
          <div><div style="font-size:11px;color:#6b7280">离店高峰月</div><strong>${timing.peak_checkout_month || '—'}月</strong></div>
          <div><div style="font-size:11px;color:#6b7280">建议上线 / 下线</div><strong>${timing.suggested_go_live || '—'} / ${timing.suggested_go_offline || '—'}</strong></div>
          <div><div style="font-size:11px;color:#6b7280">中位提前天数</div><strong>${timing.median_lead_days ?? '—'}</strong></div>
          <div><div style="font-size:11px;color:#6b7280">预订高峰月</div><strong>${timing.booking_peak_month || '—'}月</strong></div>
        </div>
        <p style="font-size:13px;margin-bottom:6px">${this.escAttr(timing.summary || '')}</p>
        <p style="font-size:12px;color:#6b7280">${this.escAttr(timing.go_live_summary || '')}</p>`),
      panel('country', `
        <p style="font-size:13px;margin-bottom:8px">${this.escAttr((pack.country || {}).summary || '')}</p>
        ${this.qbiTable(['国家','订单','间夜','TTV'], countryRows)}`),
      panel('city', `
        <p style="font-size:13px;margin-bottom:8px">${this.escAttr((pack.city || {}).summary || '')}</p>
        ${this.qbiTable(['城市','订单','间夜','TTV'], cityRows)}`),
      panel('dest_segment', `
        <p style="font-size:13px;margin-bottom:8px">${this.escAttr((pack.dest_segment || {}).summary || '')}</p>
        ${this.qbiTable(['客群','订单数','占比'], mix)}
        <h4 style="margin:14px 0 8px;font-size:13px">机构预览（候选，未锁定）</h4>
        ${this.qbiTable(['client_id','名称','类型','订单','间夜'], clients)}`),
      panel('trend', `
        <p style="font-size:13px;margin-bottom:8px">淡旺季 <strong>${this.escAttr((pack.trend || {}).season_label || '—')}</strong> · ${this.escAttr((pack.trend || {}).summary || '')}</p>
        ${this.qbiTable(['月份','订单','间夜','TTV'], curve)}`),
      panel('hotel_tier', `
        <div class="grid grid-4" style="margin-bottom:12px">
          <div><div style="font-size:11px;color:#6b7280">P80 Request PV</div><strong>${hotels.p80_request_pv ?? '—'}</strong></div>
          <div><div style="font-size:11px;color:#6b7280">P80 RNs</div><strong>${hotels.p80_rns ?? '—'}</strong></div>
          <div><div style="font-size:11px;color:#6b7280">有产酒店</div><strong>${hotels.producing_count || 0}</strong></div>
          <div><div style="font-size:11px;color:#6b7280">高需求低转化</div><strong class="hotel-tag-hl">${tags['高需求低转化'] || 0}</strong></div>
        </div>
        <p style="font-size:13px;margin-bottom:8px">${this.escAttr(hotels.summary || '')}</p>
        ${this.qbiTable(['分层','家数'], tagRow)}
        <h4 style="margin:14px 0 8px;font-size:13px">候选酒店（优先高需求低转化，未锁定）</h4>
        ${this.qbiTable(['酒店ID','名称','分层','PV','RNs','星级','集团','均价'], hotelRows)}`),
      panel('grain', `
        <p style="font-size:13px;margin-bottom:8px">${this.escAttr((pack.grain || {}).summary || '')}</p>
        ${this.qbiTable(['酒店ID','名称','城市','分层','PV','BKs','RNs','TTV','GP'], grainRows)}`),
    ].join('');
  },

  async runPrepAnalysis(campaignId, applyToPlan, mode) {
    const body = { apply_to_plan: !!applyToPlan, mode: mode || 'auto' };
    if (mode === 'manual') Object.assign(body, this.qbiFilterBody());
    const btns = document.querySelectorAll('#qbi-board [data-action^="prep-analysis"]');
    btns.forEach(b => { b.disabled = true; });
    try {
      const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/resource-prep-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (r && r.ok === false) { alert(r.error || '分析失败'); return; }
      alert(applyToPlan ? '已写入主档数据分析（未锁定客户/酒店 ID）' : (mode === 'manual' ? '已按筛选重跑' : '自动分析完成'));
      await this.render();
    } catch (e) {
      alert(e.message || '分析失败');
    } finally {
      btns.forEach(b => { b.disabled = false; });
    }
  },

  profileQueryBody() {
    const splitIds = raw => (raw || '').split(/[,，\s\n]+/).map(s => s.trim()).filter(Boolean);
    const groups = splitIds(document.getElementById('pf-groups')?.value).map(x => parseInt(x, 10)).filter(n => !Number.isNaN(n));
    return {
      destination: document.getElementById('pf-dest')?.value,
      client_group_ids: groups.length ? groups : document.getElementById('pf-groups')?.value,
      time_window_days: parseInt(document.getElementById('pf-days')?.value || '90', 10),
      star_min: parseInt(document.getElementById('pf-star')?.value || '4', 10),
      client_limit: parseInt(document.getElementById('pf-climit')?.value || '200', 10),
      hotel_limit: parseInt(document.getElementById('pf-hlimit')?.value || '20', 10),
      keyword_boost: splitIds(document.getElementById('pf-keywords')?.value),
      step_codes: splitIds(document.getElementById('pf-steps')?.value || 'request,click'),
      behavior_source: 'funnel',
    };
  },

  async runProfileQuery(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/profile-query`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.profileQueryBody()),
    });
    const box = document.getElementById('profile-result');
    if (box) box.innerHTML = `<pre class="json">${JSON.stringify(r, null, 2)}</pre>`;
  },

  async runConfigureResources(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/configure`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.profileQueryBody()),
    });
    if (!r.ok) { alert(r.error || '圈客选品失败'); return; }
    alert(`圈客 ${r.resource_plan?.client_count || 0} · 酒店 ${(r.resource_plan?.hotel_list||[]).length}${r.validation?.missing_fields?.length ? ' · 注意缺项: ' + r.validation.missing_fields.join(',') : ''}`);
    this.render();
  },

  async confirmResources(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/confirm-resources`, { method: 'POST' });
    if (!r.ok) { alert(r.error || '确认失败'); return; }
    alert('资源配置已锁定，待办已生成');
    this.render();
  },

  async applyResourceOverride(campaignId, mode) {
    const splitIds = raw => (raw || '').split(/[,，\s\n]+/).map(s => s.trim()).filter(Boolean);
    const clients = splitIds(document.getElementById('ov-clients')?.value);
    const hotels = splitIds(document.getElementById('ov-hotels')?.value);
    const reason = document.getElementById('ov-reason')?.value?.trim();
    if (!clients.length && !hotels.length) return alert('请填写客户 ID 或酒店 ID');
    if (!reason) return alert('请填写覆盖说明');
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/resource-override`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, target_client_ids: clients, target_hotel_ids: hotels, override_reason: reason }),
    });
    if (!r.ok) { alert(r.error || '覆盖失败'); return; }
    alert('已应用人工 ID');
    this.render();
  },

  async submitTest(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/submit-test`, { method: 'POST' });
    if (!r.ok) { alert(r.error || JSON.stringify(r)); return; }
    alert('已提交测试');
    this.render();
  },

  /* ── Agent3/4/5/6 ── */
  async renderAgent3() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    const all = [
      ...(ws.prep_queue?.urgent || []),
      ...(ws.prep_queue?.in_progress || []),
      ...(ws.prep_queue?.executing || []),
    ];
    const demoAct = all.find(a => this.isDemoCampaign(a.activity_name || a.campaign_id || a.campaign_name))
      || all[0]
      || { activity_name: '新加坡F1赛事酒店预订', destination: 'Singapore', launch_date: '样例' };
    const remind = await this.fetch('/api/v2/config/reminders/status').catch(() => ({}));
    const lanes = this.demoLaneTasks(demoAct.activity_name || demoAct.campaign_name || demoAct.campaign_id);
    const rows = all.map(a => `
      <tr class="${this.isDemoCampaign(a.activity_name || a.campaign_id) ? 'demo-row' : ''}">
        <td><strong>${a.activity_name || a.campaign_id}</strong>${this.isDemoCampaign(a.activity_name || a.campaign_id) ? ' <span class="tag tag-urgent">对谈样例</span>' : ''}</td>
        <td>${a.destination || '—'}</td>
        <td>${a.launch_date || '—'}</td>
        <td><span class="badge-sm warn">催办中</span></td>
        <td><span class="badge-sm">三线并行</span></td>
        <td><span class="badge-sm ok">正常</span></td>
      </tr>`).join('');
    const botOk = !!remind.webhook_configured;
    return `
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">飞书催办 <span class="tag ${botOk ? 'tag-prep' : 'tag-urgent'}">${botOk ? 'Webhook 已配置' : '未配置 Webhook'}</span></div>
        <div class="card-body">
          <p class="cfg-desc">${botOk ? `定时：${remind.schedule || '每天 09:00'} · 待催办任务 ${remind.pending_tasks ?? 0} 条` : '请先到「系统连接配置」填写飞书群机器人 Webhook。'}</p>
          <div class="actions">
            <button class="btn btn-primary" data-action="test-feishu-bot"${botOk ? '' : ' disabled'}>发一条测试催办到飞书群</button>
            <button class="btn" data-action="run-feishu-reminders"${botOk ? '' : ' disabled'}>立即检查到期催办</button>
            <button class="btn" onclick="App.navigate('system-config',{configTab:'infra'})">去配置 Webhook</button>
          </div>
          <div id="agent3-bot-result"></div>
        </div>
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">三线看板 · ${demoAct.activity_name || demoAct.campaign_id}</div>
        <div class="card-body">
          <div class="kanban-board">
            ${this.kanbanColHtml('资源', '🏨', lanes.resource)}
            ${this.kanbanColHtml('方案', '📋', lanes.plan)}
            ${this.kanbanColHtml('素材', '🎨', lanes.material)}
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-head">活动任务督办总览</div>
        <div class="card-body table-wrap">
          <table><thead><tr><th>活动</th><th>目的地</th><th>上线日</th><th>催办状态</th><th>看板</th><th>延期风险</th></tr></thead>
          <tbody>${rows || '<tr><td colspan=6 class="empty">暂无活动进入催办阶段 · 下方为新加坡 F1 样例看板</td></tr>'}</tbody></table>
        </div>
      </div>`;
  },

  async renderAgent4() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    let ready = [
      ...(ws.prep_queue?.in_progress || []),
      ...(ws.prep_queue?.ready || []),
    ].filter((a, i, arr) => arr.findIndex(x => x.campaign_id === a.campaign_id) === i);
    const archiveExamples = [
      { campaign_id: 'DEMO_HOKKAIDO_SKI_EARLY', activity_name: '北海道滑雪季·早鸟预售', promotion_month: '2027-01', launch_date: '2027-01-07', status: 'ready_to_launch' },
      { campaign_id: 'DEMO_SE_ASIA_NATIONAL_DAY', activity_name: '国庆出境·东南亚精选', promotion_month: '2027-10', launch_date: '2027-09-14', status: 'ready_to_launch' },
      { campaign_id: 'DEMO_NEW_YEAR_LAST_MINUTE', activity_name: '元旦跨年尾单', promotion_month: '2027-01', launch_date: '2026-12-20', status: 'ready_to_launch' },
      { campaign_id: 'DEMO_SPRING_ISLAND', activity_name: '春节暖冬海岛预售', promotion_month: '2027-02', launch_date: '2027-01-10', status: 'ready_to_launch' },
    ];
    if (!ready.length) ready = archiveExamples;
    const filters = this.agent4Filters || { month: '', activity: '', search: '' };
    const monthOf = a => String(a.promotion_month || a.promotion_date || a.launch_date || a.start_date || '').slice(0, 7);
    const nameOf = a => a.activity_name || a.campaign_name || a.campaign_id || '';
    const months = [...new Set(ready.map(monthOf).filter(Boolean))].sort();
    const monthItems = filters.month ? ready.filter(a => monthOf(a) === filters.month) : ready;
    const activityOptions = monthItems.map(a => `<option value="${this.escAttr(a.campaign_id)}" ${filters.activity === a.campaign_id ? 'selected' : ''}>${this.escHtml(nameOf(a))}</option>`).join('');
    const search = String(filters.search || '').trim().toLowerCase();
    const selected = ready.find(a => a.campaign_id === filters.activity)
      || monthItems.find(a => !search || nameOf(a).toLowerCase().includes(search))
      || ready.find(a => !search || nameOf(a).toLowerCase().includes(search));
    const cid = selected?.campaign_id || 'CAMP_CAL_08_新加坡F1赛事酒店预订';
    const checklist = [
      '预备上线池终极审核',
      '资源检查',
      '位置检查',
      '素材检查',
      '目标字段检查',
      '风险检查',
      '活动机制检查',
    ];
    const items = checklist.map((label, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${label}</td>
        <td><input type="checkbox" disabled /></td>
        <td><span class="badge-sm">待确认</span></td>
      </tr>`).join('');
    return `${this.tabsHtml('agent4')}
      <div class="callout">
        <strong>上线审核Agent</strong> — 预备上线池终极审核 · 资源/位置/素材/目标字段/风险/活动机制检查。
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">选择待审核活动</div>
        <div class="card-body agent4-activity-picker">
          <label>活动推广月<select class="form-control" onchange="App.setAgent4Filter('month',this.value)"><option value="">全部月份</option>${months.map(m => `<option value="${m}" ${filters.month === m ? 'selected' : ''}>${m}</option>`).join('')}</select></label>
          <label>活动名称<select class="form-control" onchange="App.setAgent4Filter('activity',this.value)"><option value="">请选择活动</option>${activityOptions}</select></label>
          <label>搜索活动<input class="form-control" value="${this.escAttr(filters.search)}" placeholder="输入活动名称搜索" oninput="App.setAgent4Filter('search',this.value)" /></label>
        </div>
        <div class="card-head">${this.escHtml(nameOf(selected || {}))}</div>
        <div class="card-body table-wrap">
          <table><thead><tr><th>#</th><th>确认项</th><th>通过</th><th>AI 审核</th></tr></thead>
          <tbody>${items}</tbody></table>
          <div class="actions agent4-review-actions" style="margin-top:16px">
            <button class="btn" disabled>AI审核</button>
            <button class="btn" disabled>暂不上线</button>
            <button class="btn btn-primary" disabled>批准上线</button>
          </div>
        </div>
      </div>`;
  },

  setAgent4Filter(key, value) {
    this.agent4Filters = this.agent4Filters || { month: '', activity: '', search: '' };
    this.agent4Filters[key] = value;
    if (key === 'month') this.agent4Filters.activity = '';
    this.render();
  },

  async renderAgent5() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    const executing = ws.prep_queue?.executing || [];
    const activities = executing.length ? executing : [{ campaign_id: 'CAMP_CAL_08_新加坡F1赛事酒店预订', activity_name: '新加坡F1赛事酒店预订', promotion_month: '2027-10' }];
    const sf = this.stageActivityFilters?.agent5 || {};
    const selected = activities.find(a => a.campaign_id === sf.activity) || activities.find(a => !sf.search || (a.activity_name || a.campaign_name || '').toLowerCase().includes(String(sf.search).toLowerCase())) || activities[0];
    const cid = selected.campaign_id;
    let preview = {};
    try { preview = await this.fetch(`/api/v2/activities/${this.encId(cid)}/monitor/preview`); } catch (_) {}
    const kpis = preview.kpi_cards || preview.metrics || {};
    const kpiHtml = Object.keys(kpis).length
      ? Object.entries(kpis).map(([k, v]) => `
          <div class="card card-body" style="text-align:center;padding:16px">
            <div style="font-size:22px;font-weight:700;color:#2563eb">${typeof v === 'object' ? (v.value ?? '—') : v}</div>
            <div style="font-size:12px;color:#6b7280;margin-top:4px">${k}</div>
          </div>`).join('')
      : '<div class="callout">暂无 KPI 数据，活动上线后监控优化Agent 接入数仓实时看板</div>';
    return `${this.tabsHtml('agent5')}
      ${this.stageActivityPicker(activities, 'agent5', '选择监控活动')}
      <div class="callout">
        <strong>监控优化Agent</strong> — 自动化监控 · 自动化总结 · 自动化优化建议 · 预警推送。
      </div>
      <div class="grid grid-4" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">
        ${['自动化监控','自动化总结','自动化优化建议','预警推送'].map(f => `
          <div class="card card-body" style="text-align:center;padding:14px">
            <div style="font-size:13px;font-weight:600">${f}</div>
            <div style="font-size:11px;color:#9ca3af;margin-top:6px">待接入</div>
          </div>`).join('')}
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">执行中活动 · ${cid}</div>
        <div class="card-body">
          <div class="grid grid-4" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">${kpiHtml}</div>
          <details>
            <summary style="cursor:pointer;font-size:13px;color:#6b7280">原始监控数据 JSON</summary>
            <pre class="json" style="margin-top:8px">${JSON.stringify(preview, null, 2)}</pre>
          </details>
        </div>
      </div>`;
  },

  async renderAgent6() {
    const ws = this.data.workspace || await this.fetch('/api/v2/workspace');
    const all = [
      ...(ws.prep_queue?.urgent || []),
      ...(ws.prep_queue?.in_progress || []),
      ...(ws.prep_queue?.executing || []),
    ];
    const demo = all.find(a => this.isDemoCampaign(a.activity_name || a.campaign_id || a.campaign_name))
      || all[0]
      || { campaign_id: 'CAMP_F1_SG_2026', activity_name: '新加坡F1赛事酒店预订' };
    const archiveActivities = all.length ? all : [demo];
    const sf = this.stageActivityFilters?.agent6 || {};
    const selectedArchive = archiveActivities.find(a => a.campaign_id === sf.activity) || archiveActivities.find(a => !sf.search || (a.activity_name || a.campaign_name || '').toLowerCase().includes(String(sf.search).toLowerCase())) || demo;
    const cid = selectedArchive.campaign_id || 'CAMP_F1_SG_2026';
    const pack = await this.fetch(`/api/v2/activities/${this.encId(cid)}/diagnosis`).catch(() => ({}));
    const dg = pack.diagnosis || {};
    const live = pack.live || pack.read_pack?.live || {};
    const hypo = pack.read_pack?.hypothesis || {};
    const causes = (dg.root_causes || []).map(c =>
      `<li><strong>${c.label || c.type || ''}</strong> — ${c.evidence || ''}</li>`
    ).join('');
    const opts = (dg.optimizations || []).map(o =>
      `<li>${o.action || ''} <span class="hint">${o.owner_hint || ''}</span></li>`
    ).join('');
    const archives = await this.fetch('/api/v2/archives?destination=');
    const rows = (Array.isArray(archives) ? archives : []).map(a => `
      <tr>
        <td><strong>${a.activity_name || '—'}</strong></td>
        <td>${a.destination || '—'}</td>
        <td>${a.success_label || '—'}</td>
        <td style="font-size:12px">${(a.conclusions || a.reusable_points || '—').toString().slice(0, 80)}</td>
      </tr>`).join('');
    return `${this.tabsHtml('agent6')}
      ${this.stageActivityPicker(archiveActivities, 'agent6', '选择归档活动')}
      <div class="callout">
        <strong>复盘归档Agent</strong> — AI 读取主文档假设 + 过程漏斗 + 结果，给出总根源与优化策略。你只补人工结论，即可归档成最终文档。
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">效果诊断 · ${hypo.name || demo.activity_name || cid}
          <span class="tag ${dg.one_line_verdict ? 'tag-prep' : 'tag-urgent'}">${dg.one_line_verdict ? '已生成' : '待生成'}</span>
        </div>
        <div class="card-body">
          <p class="cfg-desc">假设：${hypo.why || hypo.data_conclusion || '（主文档②③）'} · 客群 ${hypo.audience || '—'} · 酒店 ${hypo.hotel_strategy || '—'}</p>
          <div class="grid grid-3" style="margin:12px 0">
            <div class="stat-card"><div class="val">${live.banner_ctr ?? '—'}</div><div class="lbl">Banner CTR</div></div>
            <div class="stat-card"><div class="val">${live.order_count ?? live.orders ?? '—'}</div><div class="lbl">订单</div></div>
            <div class="stat-card"><div class="val">${live.total_ttv ?? '—'}</div><div class="lbl">TTV</div></div>
          </div>
          <p><strong>一句话：</strong>${dg.one_line_verdict || '尚未生成。点下方按钮，AI 会对照主文档与监控数据追根因。'}</p>
          <p class="hint">漏斗断裂点：${dg.funnel_break || '—'}</p>
          <ul style="margin:8px 0 0 18px;font-size:13px">${causes || '<li class="hint">暂无根因</li>'}</ul>
          <p style="margin-top:10px"><strong>优化策略</strong></p>
          <ul style="margin:4px 0 0 18px;font-size:13px">${opts || '<li class="hint">暂无</li>'}</ul>
          <div class="actions" style="margin-top:12px">
            <button class="btn btn-primary" data-action="run-diagnosis" data-id="${this.escAttr(cid)}">生成根因分析</button>
          </div>
          <div id="agent6-diag-result"></div>
        </div>
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">人工结论 · 归档最终文档</div>
        <div class="card-body">
          <div class="form-group"><label>人工结论（归档必填）</label>
            <textarea id="ar6-human" rows="4">${pack.archive?.human_conclusion || ''}</textarea></div>
          <div class="form-group"><label>可复用经验</label>
            <textarea id="ar6-exp" rows="2">${pack.archive?.experience || ''}</textarea></div>
          <div class="form-group"><label>避坑</label>
            <textarea id="ar6-pit" rows="2">${pack.archive?.pitfalls || ''}</textarea></div>
          <div class="actions">
            <button class="btn btn-primary" data-action="archive-campaign" data-id="${this.escAttr(cid)}">确认归档</button>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-head">活动案例库 · 反哺下次评审</div>
        <div class="card-body table-wrap">
          <table><thead><tr><th>活动</th><th>目的地</th><th>标签</th><th>结论</th></tr></thead>
          <tbody>${rows || '<tr><td colspan=4 class="empty">暂无归档</td></tr>'}</tbody></table>
        </div>
      </div>`;
  },

  stageActivityPicker(activities, stage, title) {
    const filters = this.stageActivityFilters?.[stage] || {};
    const monthOf = a => String(a.promotion_month || a.promotion_date || a.launch_date || a.start_date || '').slice(0, 7);
    const months = [...new Set(activities.map(monthOf).filter(Boolean))].sort();
    const monthActivities = filters.month ? activities.filter(a => monthOf(a) === filters.month) : activities;
    const options = monthActivities.map(a => `<option value="${this.escAttr(a.campaign_id)}" ${filters.activity === a.campaign_id ? 'selected' : ''}>${this.escHtml(a.activity_name || a.campaign_name || a.campaign_id)}</option>`).join('');
    return `<div class="card stage-activity-picker" style="margin-bottom:16px"><div class="card-head">${title}</div><div class="card-body"><div class="agent4-activity-picker"><label>活动推广月<select class="form-control" onchange="App.setStageActivityFilter('${stage}','month',this.value)"><option value="">全部月份</option>${months.map(m => `<option value="${m}" ${filters.month === m ? 'selected' : ''}>${m}</option>`).join('')}</select></label><label>活动名称<select class="form-control" onchange="App.setStageActivityFilter('${stage}','activity',this.value)"><option value="">请选择活动</option>${options}</select></label><label>搜索活动<input class="form-control" value="${this.escAttr(filters.search || '')}" placeholder="输入活动名称搜索" oninput="App.setStageActivityFilter('${stage}','search',this.value)" /></label></div></div></div>`;
  },

  setStageActivityFilter(stage, key, value) {
    this.stageActivityFilters = this.stageActivityFilters || {};
    this.stageActivityFilters[stage] = this.stageActivityFilters[stage] || {};
    this.stageActivityFilters[stage][key] = value;
    if (key === 'month') this.stageActivityFilters[stage].activity = '';
    this.render();
  },

  /* ── Config pages ── */
  configStatusCard(key, item) {
    const cls = item.ok ? 'cfg-ok' : 'cfg-warn';
    return `<div class="cfg-status-card ${cls}">
      <div class="cfg-status-title">${item.name}</div>
      <div class="cfg-status-val">${item.status}</div>
      <div class="cfg-status-hint">${item.hint || ''}</div>
    </div>`;
  },

  renderCheckResult(boxId, r) {
    const box = document.getElementById(boxId);
    if (!box) return;
    const cls = r.ok ? 'cfg-result-ok' : 'cfg-result-fail';
    const checks = (r.checks || []).map(c => {
      const icon = c['通过'] ? '✅' : (c.optional ? '⚠️' : '❌');
      const label = c.optional ? `${c['项']}（可选）` : c['项'];
      return `<tr><td>${label}</td><td>${icon}</td><td>${c['说明'] || ''}</td></tr>`;
    }).join('');
    const steps = (r.steps || []).map(s => `
      <tr><td>${s.step}. ${s.name}</td><td>${s.ok ? '✅' : '❌'}</td><td>${s.detail || ''}</td></tr>`).join('');
    const sample = r.sample_records ? `<pre class="json">${JSON.stringify(r.sample_records, null, 2)}</pre>`
      : r.sample ? `<pre class="json">${JSON.stringify(r.sample, null, 2)}</pre>` : '';
    const stepSample = (r.steps || []).find(s => s.sample);
    const stepSampleHtml = stepSample ? `<pre class="json">${JSON.stringify(stepSample.sample, null, 2)}</pre>` : '';
    box.innerHTML = `<div class="cfg-result ${cls}">
      <strong>${r.ok ? '✅' : '❌'} ${r.title || ''}${r.mode ? ` · ${r.mode}` : ''}</strong>
      <p style="margin:6px 0;font-size:13px">${r.message || r.error || ''}</p>
      ${r.note ? `<p style="font-size:12px;color:#6b7280;margin:4px 0">${r.note}</p>` : ''}
      ${r.record_count != null ? `<p style="font-size:13px">共读取 <strong>${r.record_count}</strong> 条记录</p>` : ''}
      ${steps ? `<div class="table-wrap" style="margin-top:8px"><table><thead><tr><th>步骤</th><th>结果</th><th>说明</th></tr></thead><tbody>${steps}</tbody></table></div>` : ''}
      ${checks ? `<div class="table-wrap" style="margin-top:8px"><table><thead><tr><th>检测项</th><th>结果</th><th>说明</th></tr></thead><tbody>${checks}</tbody></table></div>` : ''}
      ${sample || stepSampleHtml}
    </div>`;
  },

  async renderMcpConfig(_embedded = false) {
    const [cfg, status, localCal] = await Promise.all([
      this.fetch('/api/v2/config/integrations'),
      this.fetch('/api/v2/config/integrations/status'),
      this.fetch('/api/v2/config/calendar/local-status').catch(() => ({})),
    ]);
    const wh = cfg.warehouse_mcp || {};
    const fs = cfg.feishu || {};
    const llm = cfg.llm || {};
    const qwen = llm.qwen || {};
    const ds = llm.deepseek || {};
    const dsrc = status.data_sources || {};
    const fsType = fs.calendar_type || 'bitable';
    const isLocal = fsType === 'local';
    const isBitable = fsType === 'bitable';
    const isSheet = fsType === 'sheet';

    const img = cfg.image_gen || {};
    return `
      <div class="callout">
        <strong>通用底座（4 项）</strong>：MCP 数仓 · AI 大模型 · 飞书催办 Bot · 生图/海报工具。
        各 Agent 的 Prompt 配置在对应 Agent 工作台内（如 Agent1 → 活动生成各子模块）。
      </div>

      <div class="grid grid-4" style="margin-bottom:16px;display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
        ${this.configStatusCard('mcp', dsrc.mcp || {})}
        ${this.configStatusCard('llm', dsrc.llm || {})}
        ${this.configStatusCard('feishu-bot', { ok: fs.bot_webhook_url_set, label: '飞书 Bot' })}
        ${this.configStatusCard('image', { ok: img.api_key_set, label: '生图工具' })}
      </div>

      <div class="actions" style="margin-bottom:16px">
        <button class="btn btn-primary" data-action="test-all-config">一键检测全部连接</button>
        <button class="btn" onclick="App.saveIntegrations('all')">保存全部配置</button>
      </div>
      <div id="cfg-all-result" style="margin-bottom:16px"></div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-head">① 数仓 MCP <span class="tag ${wh.mode === 'warehouse_mcp' ? 'tag-prep' : 'tag-urgent'}">${wh.mode === 'warehouse_mcp' ? '已配置' : '演示模式'}</span></div>
        <div class="card-body">
          <p class="cfg-desc">全系统拉取数仓数据的共用配置。Agent1 标准活动 · Agent2 圈客 · Agent3/4 监控复盘均依赖此项。</p>
          <div class="form-row">
            <div class="form-group"><label>接口地址 <span class="req">必填</span></label>
              <input id="mcp-endpoint" value="${this.escAttr(wh.endpoint || 'https://data-api-mcp.didaadmin.com/mcp/v1/query')}" /></div>
            <div class="form-group"><label>鉴权 Key <span class="req">必填</span></label>
              <input id="mcp-key" type="password" placeholder="${wh.api_key_set ? '已配置（留空不修改）' : '粘贴 MCP Key'}" /></div>
          </div>
          <details style="margin:12px 0;font-size:13px">
            <summary style="cursor:pointer;color:#1d4ed8">高级选项（一般不用改）</summary>
            <div class="form-row" style="margin-top:10px"><div class="form-group"><label>环境</label><select id="mcp-environment"><option value="production">正式环境</option><option value="test">测试环境</option></select></div><div class="form-group"><label>请求超时（秒）</label><input id="mcp-timeout" type="number" value="${wh.timeout_seconds || 30}" /></div><div class="form-group"><label>失败重试次数</label><input id="mcp-retries" type="number" value="${wh.retry_count ?? 2}" /></div></div>
            <div class="form-row" style="margin-top:10px">
              <div class="form-group"><label>鉴权 Header</label><input id="mcp-auth-header" value="${wh.auth_header || 'agent_user_key'}" /></div>
              <div class="form-group"><label>行为事件表</label><input id="mcp-events" value="${wh.tables?.events || ''}" /></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>用户表</label><input id="mcp-users" value="${wh.tables?.users || ''}" /></div>
              <div class="form-group"><label>漏斗表</label><input id="mcp-funnel" value="${wh.tables?.funnel || ''}" /></div>
            </div>
            <label style="font-size:12px;display:flex;gap:8px;align-items:center;margin-top:8px;color:#6b7280">
              <input type="checkbox" id="mcp-fallback" ${wh.use_local_fallback !== false ? 'checked' : ''} />
              MCP 不可用时使用本地演示数据（仅开发用）
            </label>
          </details>
          <p class="cfg-desc" style="margin-top:8px;font-size:12px;color:#6b7280">
            Agent1 标准活动走 <strong>analyse_query 官方指标</strong>；下方「快速 Ping」只测 3 步打通。
            「完整检测」含 Agent2 圈客选品（execute_sql），无表权限时会 ⚠️，<strong>不影响 Agent1</strong>。
          </p>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.saveIntegrations('mcp')">保存</button>
            <button class="btn" data-action="test-mcp-ping">快速 Ping（Agent1）</button>
            <button class="btn" data-action="test-mcp-config">完整检测</button>
          </div>
          <div id="cfg-mcp-result"></div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-head">② AI 大模型 <span class="tag ${dsrc.llm?.ok ? 'tag-prep' : 'tag-urgent'}">${dsrc.llm?.ok ? '已配置' : '未配置'}</span></div>
        <div class="card-body">
          <p class="cfg-desc">全系统调用 AI 模型的共用密钥（Agent1 创意/分析、情报输入等）。</p>
          <div class="form-row">
            <div class="form-group"><label>默认使用</label>
              <select id="llm-provider">
                <option value="qwen" ${llm.default_provider === 'qwen' ? 'selected' : ''}>公司 Dragon API（Qwen）</option>
                <option value="deepseek" ${llm.default_provider === 'deepseek' ? 'selected' : ''}>DeepSeek（个人备用）</option>
              </select></div>
            <div class="form-group"><label>行业情报使用</label>
              <select id="llm-intel-provider">
                <option value="qwen" ${(llm.industry_intel?.provider || 'qwen') === 'qwen' ? 'selected' : ''}>公司 Dragon API</option>
                <option value="deepseek" ${llm.industry_intel?.provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
              </select></div>
          </div>
          <div class="grid grid-2" style="margin-top:8px">
            <div>
              <h4 class="cfg-subtitle">公司 Dragon API（内网）</h4>
              <div class="form-group"><label>API Key ${qwen.api_key_set ? '<span class="tag tag-prep">已保存</span>' : ''}</label><input id="qwen-key" type="password" placeholder="${qwen.api_key_set ? '已配置（留空不修改，不显示明文）' : 'LLM_API_KEY'}" /></div>
              <div class="form-group"><label>接口地址</label><input id="qwen-url" value="${this.escAttr(qwen.base_url || 'http://dragon-open-api.didainternal.com/v1')}" /></div>
              <div class="form-group"><label>模型名称</label><input id="qwen-model" value="${this.escAttr(qwen.model || 'qwen3.7-plus')}" /></div>
            </div>
            <div>
              <h4 class="cfg-subtitle">DeepSeek（备用）</h4>
              <div class="form-group"><label>API Key ${ds.api_key_set ? '<span class="tag tag-prep">已保存</span>' : ''}</label><input id="ds-key" type="password" placeholder="${ds.api_key_set ? '已配置（留空不修改，不显示明文）' : 'sk-...'}" /></div>
              <div class="form-group"><label>接口地址</label><input id="ds-url" value="${this.escAttr(ds.base_url || 'https://api.deepseek.com/v1')}" /></div>
              <div class="form-group"><label>模型名称</label><input id="ds-model" value="${this.escAttr(ds.model || 'deepseek-chat')}" /></div>
            </div>
          </div>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.saveIntegrations('llm')">保存</button>
            <button class="btn" data-action="test-llm-config">检测 AI 是否跑通</button>
          </div>
          <div id="cfg-llm-result"></div>
        </div>
      </div>

      <div class="card" style="margin-bottom:16px">
        <div class="card-head">③ 飞书催办机器人 <span class="tag ${fs.bot_webhook_url_set ? 'tag-prep' : 'tag-urgent'}">${fs.bot_webhook_url_set ? '已配置' : '未配置'}</span></div>
        <div class="card-body">
          <p class="cfg-desc">任务监督 Agent 催办通知。Webhook 消息须带安全关键词。</p>
          <div class="form-row">
            <div class="form-group"><label>Webhook URL <span class="req">必填</span></label>
              <input id="fs-bot-webhook" type="password" placeholder="${fs.bot_webhook_url_set ? '已配置（留空不修改）' : 'https://open.feishu.cn/open-apis/bot/v2/hook/...'}" /></div>
            <div class="form-group"><label>安全关键词</label>
              <input id="fs-bot-keyword" value="${this.escAttr(fs.bot_keyword || '任务通知')}" /></div>
          </div>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.saveIntegrations('feishu-bot')">保存</button>
            <button class="btn" data-action="test-feishu-bot">发一条测试到飞书群</button>
          </div>
          <div id="cfg-feishu-bot-result"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">④ 生图 / 海报 AI 工具 <span class="tag ${img.api_key_set ? 'tag-prep' : 'tag-urgent'}">${img.api_key_set ? '已配置' : '未配置'}</span></div>
        <div class="card-body">
          <p class="cfg-desc">营销物料海报生成工具的 API 密钥（后续 Agent2/素材线接入）。</p>
          <div class="form-row">
            <div class="form-group"><label>API Key ${img.api_key_set ? '<span class="tag tag-prep">已保存</span>' : ''}</label>
              <input id="img-key" type="password" placeholder="${img.api_key_set ? '已配置（留空不修改）' : '粘贴生图 API Key'}" /></div>
            <div class="form-group"><label>接口地址</label>
              <input id="img-url" value="${this.escAttr(img.base_url || '')}" placeholder="https://..." /></div>
            <div class="form-group"><label>模型</label>
              <input id="img-model" value="${this.escAttr(img.model || '')}" /></div>
          </div>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.saveIntegrations('image-gen')">保存</button>
          </div>
        </div>
      </div>`;
  },

  async saveIntegrations(section) {
    const body = {};
    if (section === 'mcp' || section === 'all') {
      body.warehouse_mcp = {
        endpoint: document.getElementById('mcp-endpoint')?.value,
        api_key: document.getElementById('mcp-key')?.value,
        auth_header: document.getElementById('mcp-auth-header')?.value || 'agent_user_key',
        protocol: 'streamable_http',
        environment: document.getElementById('mcp-environment')?.value || 'production',
        timeout_seconds: Number(document.getElementById('mcp-timeout')?.value || 30),
        retry_count: Number(document.getElementById('mcp-retries')?.value || 2),
        use_local_fallback: document.getElementById('mcp-fallback')?.checked,
        tables: {
          events: document.getElementById('mcp-events')?.value,
          users: document.getElementById('mcp-users')?.value,
          funnel: document.getElementById('mcp-funnel')?.value,
        },
      };
    }
    if (section === 'feishu' || section === 'all') {
      body.feishu = {
        calendar_type: document.getElementById('fs-type')?.value || 'bitable',
        app_id: document.getElementById('fs-app-id')?.value,
        app_secret: document.getElementById('fs-secret')?.value,
        app_token: document.getElementById('fs-app-token')?.value,
        marketing_calendar_table_id: document.getElementById('fs-table')?.value,
        marketing_calendar_view_id: document.getElementById('fs-view')?.value,
        spreadsheet_token: document.getElementById('fs-spreadsheet-token')?.value,
        sheet_id: document.getElementById('fs-sheet-id')?.value,
        sheet_range: document.getElementById('fs-sheet-range')?.value,
        bot_webhook_url: document.getElementById('fs-bot-webhook')?.value,
        bot_keyword: document.getElementById('fs-bot-keyword')?.value || '任务通知',
      };
    }
    if (section === 'feishu-bot') {
      body.feishu = {
        bot_webhook_url: document.getElementById('fs-bot-webhook')?.value,
        bot_keyword: document.getElementById('fs-bot-keyword')?.value || '任务通知',
      };
    }
    if (section === 'llm' || section === 'all') {
      body.llm = {
        default_provider: document.getElementById('llm-provider')?.value,
        industry_intel: { provider: document.getElementById('llm-intel-provider')?.value },
        qwen: {
          api_key: document.getElementById('qwen-key')?.value,
          base_url: document.getElementById('qwen-url')?.value,
          model: document.getElementById('qwen-model')?.value,
        },
        deepseek: {
          api_key: document.getElementById('ds-key')?.value,
          base_url: document.getElementById('ds-url')?.value,
          model: document.getElementById('ds-model')?.value,
        },
      };
    }
    if (section === 'image-gen' || section === 'all') {
      body.image_gen = {
        api_key: document.getElementById('img-key')?.value,
        base_url: document.getElementById('img-url')?.value,
        model: document.getElementById('img-model')?.value,
      };
    }
    const r = await this.fetch('/api/v2/config/integrations', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    alert(`已保存 · 数仓：${r.warehouse_mode === 'warehouse_mcp' ? 'MCP 已连通' : '演示模式'} · AI：${r.llm_configured ? '已配置' : '未配置'}`);
    await this.refresh();
    this.render();
  },

  async testMcpPing() {
    const box = document.getElementById('cfg-mcp-result');
    if (box) box.innerHTML = '<p style="font-size:13px;color:#6b7280">正在 Ping MCP（配置→握手→离店指标）…</p>';
    const r = await this.fetch('/api/v2/config/integrations/test-mcp-ping', { method: 'POST' });
    this.renderCheckResult('cfg-mcp-result', r);
  },

  async testMcpConfig() {
    const box = document.getElementById('cfg-mcp-result');
    if (box) box.innerHTML = '<p style="font-size:13px;color:#6b7280">正在完整检测 MCP…</p>';
    const r = await this.fetch('/api/v2/config/integrations/test-mcp', { method: 'POST' });
    this.renderCheckResult('cfg-mcp-result', r);
  },

  toggleFeishuCalendarType() {
    const t = document.getElementById('fs-type')?.value || 'bitable';
    const bitable = document.getElementById('fs-bitable-fields');
    const sheet = document.getElementById('fs-sheet-fields');
    if (bitable) bitable.style.display = t === 'bitable' ? 'block' : 'none';
    if (sheet) sheet.style.display = t === 'sheet' ? 'block' : 'none';
  },

  async testFeishuConfig() {
    const r = await this.fetch('/api/v2/config/integrations/test-feishu', { method: 'POST' });
    this.renderCheckResult('cfg-feishu-result', r);
  },

  async testLlmConfig() {
    const r = await this.fetch('/api/v2/config/integrations/test-llm', { method: 'POST' });
    this.renderCheckResult('cfg-llm-result', r);
  },

  async testFeishuBot() {
    const r = await this.fetch('/api/v2/config/integrations/test-feishu-bot', { method: 'POST' });
    this.renderCheckResult('cfg-feishu-bot-result', r);
    this.renderCheckResult('agent3-bot-result', r);
    alert(r.ok ? '已发到飞书群，请打开群看「任务通知」测试消息。' : (r.message || r.error || '发送失败'));
  },

  async runFeishuReminders() {
    const r = await this.fetch('/api/v2/config/reminders/run', { method: 'POST' });
    this.renderCheckResult('agent3-bot-result', {
      ok: r.ok,
      title: '到期催办',
      mode: r.today || '',
      message: r.message || r.error,
      checks: (r.items || []).map(it => ({ 项: it.title, 通过: true, 说明: `级别 ${it.level}` })),
    });
    alert(r.message || r.error || '已执行');
    this.render();
  },

  async testAllConfig() {
    const r = await this.fetch('/api/v2/config/integrations/test-all', { method: 'POST' });
    const box = document.getElementById('cfg-all-result');
    if (!box) return;
    const parts = ['mcp', 'feishu', 'llm'].map(k => {
      const item = r.results?.[k] || {};
      return `<div class="cfg-result ${item.ok ? 'cfg-result-ok' : 'cfg-result-fail'}" style="margin-bottom:8px">
        <strong>${item.ok ? '✅' : '❌'} ${item.title}</strong> — ${item.message || item.error || ''}
      </div>`;
    }).join('');
    box.innerHTML = `<div class="callout">${r.ok ? '✅ 全部检测通过' : '⚠️ 部分未通过，请查看各项明细'}</div>${parts}`;
    this.renderCheckResult('cfg-mcp-result', r.results?.mcp || {});
    this.renderCheckResult('cfg-feishu-result', r.results?.feishu || {});
    this.renderCheckResult('cfg-llm-result', r.results?.llm || {});
  },

  async testMcp() { return this.testMcpConfig(); },
  async testLlm() { return this.testLlmConfig(); },

  calendarDropzoneHtml(localStatus = {}, embedded = false) {
    const rows = localStatus.rows || 0;
    const fn = localStatus.filename || '';
    const ts = localStatus.uploaded_at || '';
    const isLocal = localStatus.source === 'local_upload';
    const statusText = isLocal
      ? `当前本地日历：<strong>${rows}</strong> 条${fn ? ` · ${this.escAttr(fn)}` : ''}${ts ? ` · ${this.escAttr(ts)}` : ''}`
      : (rows ? `当前 ${rows} 条演示数据，上传后可替换` : '拖拽上传飞书导出的 Excel（表头与飞书列名一致）');
    const intro = embedded
      ? `<p class="cfg-desc" style="margin-top:4px">从飞书多维表格 <strong>⋯ → 导出 Excel</strong>，拖到下方即可。支持 .xlsx / .xls / .csv / .json</p>`
      : `<hr class="cfg-divider" />
      <h4 class="cfg-subtitle">本地表格导入 <span class="tag tag-prep">无需飞书 API</span></h4>
      <p class="cfg-desc">在飞书多维表格点 <strong>⋯ → 导出 Excel</strong>，将文件拖到下方即可。支持 .xlsx / .xls / .csv / .json</p>`;
    return `
      ${intro}
      <div id="calendar-dropzone" class="calendar-dropzone">
        <input type="file" id="calendar-file-input" accept=".xlsx,.xls,.csv,.json" hidden />
        <div class="calendar-dropzone-inner">
          <div class="calendar-dropzone-icon">📄</div>
          <p><strong>拖拽文件到此处</strong>，或 <span class="calendar-dropzone-link">点击选择文件</span></p>
          <p class="calendar-dropzone-hint">表头需含：月度推荐主题、推广月份、推广时间、目的地归属、地区</p>
        </div>
      </div>
      <div id="calendar-upload-status" class="calendar-upload-status">${statusText}</div>
      <div id="cfg-calendar-upload-result"></div>`;
  },

  bindCalendarDropzone() {
    const zone = document.getElementById('calendar-dropzone');
    const input = document.getElementById('calendar-file-input');
    if (!zone || !input || zone.dataset.bound) return;
    zone.dataset.bound = '1';

    zone.addEventListener('click', (e) => {
      if (e.target.closest('a, button')) return;
      input.click();
    });
    input.addEventListener('change', () => {
      if (input.files?.[0]) this.uploadCalendarFile(input.files[0]);
      input.value = '';
    });
    ['dragenter', 'dragover'].forEach((ev) => {
      zone.addEventListener(ev, (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
      });
    });
    zone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
      const file = e.dataTransfer?.files?.[0];
      if (file) this.uploadCalendarFile(file);
    });
  },

  async uploadCalendarFile(file) {
    if (!file) return;
    const name = (file.name || '').toLowerCase();
    if (!/\.(xlsx|xls|csv|json)$/.test(name)) {
      alert('仅支持 .xlsx / .xls / .csv / .json');
      return;
    }
    const zone = document.getElementById('calendar-dropzone');
    zone?.classList.add('uploading');
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/api/v2/config/calendar/upload', { method: 'POST', body: fd });
      const j = await r.json();
      if (j.ok) {
        await this.fetch('/api/v2/config/integrations', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feishu: { calendar_type: 'local' } }),
        });
        const fsType = document.getElementById('fs-type');
        if (fsType) fsType.value = 'local';
        this.toggleCalendarSource();
        this.renderCheckResult('cfg-calendar-upload-result', {
          ok: true,
          title: '本地表格导入',
          mode: '已导入',
          message: j.message,
          record_count: j.rows,
        });
        const st = document.getElementById('calendar-upload-status');
        if (st) {
          st.innerHTML = `当前本地日历：<strong>${j.rows}</strong> 条 · ${this.escAttr(file.name)}`;
        }
        await this.refresh();
      } else {
        alert(j.error || '导入失败');
      }
    } catch (err) {
      alert(`上传失败：${err.message}`);
    } finally {
      zone?.classList.remove('uploading');
    }
  },

  async renderCalendarUpload() {
    const [fs, raw, test, localCal] = await Promise.all([
      this.fetch('/api/v2/feishu/calendar/status'),
      this.fetch('/api/v2/feishu/calendar/raw'),
      this.fetch('/api/v2/config/integrations/test-feishu', { method: 'POST' }).catch(() => ({})),
      this.fetch('/api/v2/config/calendar/local-status').catch(() => ({})),
    ]);
    return `
      <div class="callout">营销日历可来自飞书 API 或<strong>本地 Excel 导入</strong>。飞书凭证在 <a href="#" onclick="App.navigate('system-config',{configTab:'infra'});return false" style="color:#1d4ed8">系统通用配置 · 通用底座</a> 填写。</div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">本地表格导入</div>
        <div class="card-body">${this.calendarDropzoneHtml(localCal)}</div>
      </div>
      <div class="grid grid-2">
        <div class="card">
          <div class="card-head">同步状态</div>
          <div class="card-body">
            <p style="font-size:13px;margin-bottom:8px">模式：<strong>${localCal.source === 'local_upload' ? `本地表格（${localCal.rows} 条）` : (test.mode || fs.mode || '—')}</strong></p>
            <p style="font-size:13px;margin-bottom:8px">${localCal.message || test.message || (test.ok ? `已读取 ${test.record_count} 条` : '尚未连接飞书，可上传本地 Excel')}</p>
            <div class="actions">
              <button class="btn btn-primary" onclick="App.navigate('system-config',{configTab:'infra'})">去配置飞书</button>
              <button class="btn" data-action="test-feishu-config">重新检测</button>
              <a class="btn" href="https://didatravel.feishu.cn/base/GpYkbnH9ga8nMAs0GUQcCXoInXe" target="_blank">打开飞书日历</a>
            </div>
            <div id="cfg-feishu-result" style="margin-top:12px">${test.sample_records ? `<pre class="json">${JSON.stringify(test.sample_records, null, 2)}</pre>` : ''}</div>
          </div>
        </div>
        <div class="card">
          <div class="card-head">按月份预览（${raw.count} 条）</div>
          <div class="card-body"><pre class="json" style="max-height:360px;overflow:auto">${JSON.stringify(raw.by_month, null, 2)}</pre></div>
        </div>
      </div>`;
  },

  async uploadCalendar() {
    const input = document.getElementById('calendar-file-input') || document.getElementById('calendar-file');
    if (!input?.files?.[0]) return alert('请选择或拖拽文件');
    await this.uploadCalendarFile(input.files[0]);
    this.render();
  },

  async renderIntelHub() {
    const [tasks, reports] = await Promise.all([
      this.fetch('/api/v2/intel/tasks'),
      this.fetch('/api/v2/intel/reports?limit=20'),
    ]);
    const taskRows = (tasks.tasks || []).map((t, i) => `
      <tr>
        <td><input type="checkbox" id="task-en-${i}" ${t.enabled ? 'checked' : ''} /></td>
        <td><input id="task-title-${i}" value="${this.escAttr(t.title || '')}" style="width:100%" /></td>
        <td><select id="task-freq-${i}"><option ${t.frequency==='weekly'?'selected':''}>weekly</option><option ${t.frequency==='monthly'?'selected':''}>monthly</option><option ${t.frequency==='manual'?'selected':''}>manual</option></select></td>
        <td><input id="task-url-${i}" value="${this.escAttr(t.source_url || '')}" placeholder="https://..." style="width:100%" /></td>
        <td><input id="task-inst-${i}" value="${this.escAttr(t.scrape_instruction || '')}" style="width:100%" /></td>
        <td><input id="task-dest-${i}" value="${this.escAttr(t.destinations || '')}" /></td>
        <input type="hidden" id="task-id-${i}" value="${this.escAttr(t.task_id || '')}" />
        <input type="hidden" id="task-type-${i}" value="${this.escAttr(t.source_type || 'url')}" />
      </tr>`).join('');

    const reportRows = (reports.reports || []).map(r => `
      <tr>
        <td>${r.report_title || '—'}</td>
        <td>${r.report_date || '—'}</td>
        <td>${r.source_channel || '—'}</td>
        <td style="font-size:12px;max-width:280px">${(r.summary || '').slice(0, 100)}</td>
      </tr>`).join('');

    return `
      <div class="callout">OpenClaw 式工作流：配置采集任务 → 运行采集 / 上传报告 → LLM 汇总生成建议 → 活动生成Agent 评审采纳</div>
      <div class="grid grid-2" style="margin-bottom:16px">
        <div class="card">
          <div class="card-head">① 采集任务配置 <span>LLM ${tasks.llm_configured ? '已配置' : '未配置'}</span></div>
          <div class="card-body">
            <div class="form-group"><label>汇总 Prompt（也可在活动生成Agent 配置页编辑）</label>
              <textarea id="intel-collection-prompt" rows="5">${tasks.collection_prompt || ''}</textarea></div>
            <div class="table-wrap"><table><thead><tr><th>启</th><th>任务名</th><th>频率</th><th>URL</th><th>抓取说明</th><th>目的地</th></tr></thead>
            <tbody>${taskRows || '<tr><td colspan=6>暂无</td></tr>'}</tbody></table></div>
            <div class="actions">
              <button class="btn btn-primary" onclick="App.saveIntelTasks()">保存任务</button>
              <button class="btn" onclick="App.runIntelTasks()">立即运行采集</button>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-head">② 上传行业报告 / 竞对素材</div>
          <div class="card-body">
            <div class="form-group" style="margin-bottom:12px;padding:12px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px">
              <label>公众号 / 网页链接</label>
              <input id="upload-url" placeholder="mp.weixin.qq.com 或行业报道 URL" />
              <div class="actions" style="margin-top:8px;margin-bottom:0">
                <button class="btn btn-primary" onclick="App.uploadIntelFromUrl()">抓取链接并入库</button>
              </div>
            </div>
            <div class="form-group"><label>报告标题</label><input id="upload-title" placeholder="如：2026Q1 OTA出境趋势" /></div>
            <div class="form-group"><label>目的地标签</label><input id="upload-dest" placeholder="Singapore,Japan" /></div>
            <div class="form-group"><label>报告正文（粘贴）</label><textarea id="upload-content" rows="8" placeholder="粘贴行业分析、竞对活动描述…"></textarea></div>
            <div class="form-group"><label>或上传文本文件</label><input type="file" id="upload-file" accept=".txt,.md,.csv" /></div>
            <div class="actions">
              <button class="btn btn-primary" onclick="App.uploadIntelReport()">上传入库</button>
            </div>
          </div>
        </div>
      </div>
      <div class="card" style="margin-bottom:16px">
        <div class="card-head">③ LLM 生成 AI 活动建议</div>
        <div class="card-body">
          <p style="font-size:13px;margin-bottom:12px">读取最近情报报告，调用已配置的 Qwen/DeepSeek，生成待审建议（写入活动生成Agent 右侧「AI 建议待审」）</p>
          <button class="btn btn-success" onclick="App.generateIntelSuggestions()">LLM 生成建议</button>
          <button class="btn" onclick="App.navigate('agent1')">去活动生成Agent 评审</button>
        </div>
      </div>
      <div class="card">
        <div class="card-head">情报库（最近 ${reports.count || 0} 条）</div>
        <div class="card-body table-wrap">
          <table><thead><tr><th>标题</th><th>日期</th><th>来源</th><th>摘要</th></tr></thead>
          <tbody>${reportRows || '<tr><td colspan=4 class="empty">暂无，请先采集或上传</td></tr>'}</tbody></table>
        </div>
      </div>`;
  },

  collectIntelTasksFromDom() {
    const tasks = [];
    let i = 0;
    while (document.getElementById(`task-id-${i}`)) {
      tasks.push({
        task_id: document.getElementById(`task-id-${i}`)?.value || `task_${i}`,
        title: document.getElementById(`task-title-${i}`)?.value,
        enabled: document.getElementById(`task-en-${i}`)?.checked,
        frequency: document.getElementById(`task-freq-${i}`)?.value,
        source_type: document.getElementById(`task-type-${i}`)?.value || 'url',
        source_url: document.getElementById(`task-url-${i}`)?.value,
        scrape_instruction: document.getElementById(`task-inst-${i}`)?.value,
        destinations: document.getElementById(`task-dest-${i}`)?.value,
        output_fields: ['summary', 'activity_suggestions'],
      });
      i++;
    }
    return {
      collection_prompt: document.getElementById('intel-collection-prompt')?.value,
      tasks,
    };
  },

  async saveIntelTasks() {
    const body = this.collectIntelTasksFromDom();
    await this.fetch('/api/v2/intel/tasks', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    alert('采集任务已保存');
  },

  async runIntelTasks() {
    const r = await this.fetch('/api/v2/intel/tasks/run', { method: 'POST' });
    alert(`采集完成：写入 ${r.saved || 0} 条情报（URL 爬虫为占位，请配置真实 URL 或用手动上传）`);
    this.render();
  },

  async uploadIntelFromUrl() {
    const url = document.getElementById('upload-url')?.value?.trim();
    const title = document.getElementById('upload-title')?.value?.trim() || '';
    const dest = document.getElementById('upload-dest')?.value || '';
    if (!url) return alert('请粘贴链接');
    try {
      const r = await this.fetch('/api/v2/intel/reports/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title, destinations: dest }),
      });
      if (r.ok === false) throw new Error(r.error || '抓取失败');
      alert(`已抓取入库（${r.fetch?.char_count || '?'} 字）`);
      this.render();
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  async uploadIntelReport() {
    const title = document.getElementById('upload-title')?.value;
    const content = document.getElementById('upload-content')?.value;
    const dest = document.getElementById('upload-dest')?.value || '';
    const fileInput = document.getElementById('upload-file');
    if (fileInput?.files?.length) {
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      fd.append('title', title || fileInput.files[0].name);
      fd.append('destinations', dest);
      const r = await fetch('/api/v2/intel/reports/upload-file', { method: 'POST', body: fd });
      if (!r.ok) { alert(await r.text()); return; }
      alert('文件已上传入库');
    } else if (title && content) {
      await this.fetch('/api/v2/intel/reports/upload', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content, destinations: dest }),
      });
      alert('报告已上传入库');
    } else {
      alert('请填写标题和正文，或选择文件');
      return;
    }
    this.render();
  },

  async generateIntelSuggestions() {
    if (!confirm('调用 LLM 汇总最近情报并生成 AI 活动建议？')) return;
    try {
      const r = await this.fetch('/api/v2/intel/generate-suggestions', { method: 'POST' });
      if (!r.ok) { alert(r.error || '生成失败'); return; }
      alert(`已生成 ${r.generated || 0} 条建议（模型：${r.llm_provider || '—'}）\n请到活动生成Agent 评审`);
      await this.refresh();
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  moduleStatusBadge(st) {
    const map = {
      ready: '<span class="badge-sm ok">可运行</span>',
      placeholder: '<span class="badge-sm warn">待填内容</span>',
      skeleton: '<span class="badge-sm info">骨架入口</span>',
    };
    return map[st] || map.skeleton;
  },

  setConfigTab(tab, agent1Sub) {
    this.configTab = tab;
    if (agent1Sub !== undefined) this.agent1ConfigSub = agent1Sub;
    this.render();
  },

  systemConfigTabsHtml(active) {
    const tab = active || this.configTab || 'infra';
    const pending = this.feedbackSummary?.pending_total || 0;
    const agentTabs = Object.entries(this.AGENT_CONFIG_META)
      .filter(([key]) => key !== 'agent1')
      .map(([key, meta]) =>
      `<button class="tab ${tab === key ? 'active' : ''}" onclick="App.setConfigTab('${key}')">${meta.label}</button>`
    ).join('');
    return `<div class="callout" style="margin-bottom:12px">
      <strong>系统通用配置</strong> — 仅 4 项通用底座（MCP / AI模型 / 飞书Bot / 生图工具）。
      Agent1 提示词请在 <a href="#" onclick="App.navigate('agent1',{tab:'generate'});return false" style="color:#1d4ed8">活动生成Agent · 活动生成</a> 各子模块内配置。
    </div>
    <div class="tabs config-tabs" style="flex-wrap:wrap">
      <button class="tab ${tab === 'infra' ? 'active' : ''}" onclick="App.setConfigTab('infra')">通用底座</button>
      ${agentTabs}
      <button class="tab ${tab === 'tickets' ? 'active' : ''}" onclick="App.setConfigTab('tickets')">
        问题工单${pending ? ` <span class="tag tag-urgent">${pending}</span>` : ''}
      </button>
      <button class="tab ${tab === 'logs' ? 'active' : ''}" onclick="App.setConfigTab('logs')">运行日志</button>
      <button class="tab ${tab === 'modules' ? 'active' : ''}" onclick="App.setConfigTab('modules')">模块总览</button>
    </div>`;
  },

  async renderSystemConfig() {
    const tab = this.configTab || 'infra';
    const head = this.systemConfigTabsHtml(tab);
    if (tab === 'infra') return head + await this.renderMcpConfig(true);
    if (tab === 'modules') return head + await this.renderModulesPanel();
    if (tab === 'logs') return head + await this.renderLogsPanel();
    if (tab === 'tickets') return head + await this.renderTicketsPanel();
    if (tab.startsWith('agent')) {
      if (tab === 'agent1') {
        return head + `<div class="callout">Agent1 的 Prompt 与运行已迁移至 <button class="btn btn-sm btn-primary" onclick="App.navigate('agent1',{tab:'generate'})">活动生成Agent · 活动生成</button></div>`;
      }
      return head + await this.renderAgentConfigPanel(tab);
    }
    return head + await this.renderMcpConfig(true);
  },

  _ticketStatusLabel(st) {
    return { open: '待处理', investigating: '排查中', resolved: '已修复', wont_fix: '不处理' }[st] || st;
  },

  _ticketStatusClass(st) {
    return { open: 'status-open', investigating: 'status-investigating', resolved: 'status-resolved' }[st] || '';
  },

  openTicket(id) {
    this.selectedTicketId = id;
    this.setConfigTab('tickets');
  },

  async renderTicketsPanel() {
    const filter = this.ticketFilter || '';
    const data = await this.fetch(`/api/v2/feedback?limit=80${filter ? '&status=' + filter : ''}`);
    this.feedbackSummary = data.summary || this.feedbackSummary;
    const items = data.items || [];
    const rows = items.map(t => `
      <tr style="cursor:pointer" onclick="App.openTicket(${t.feedback_id})" class="${this.selectedTicketId === t.feedback_id ? 'row-active' : ''}">
        <td><strong>${t.ticket_no}</strong></td>
        <td><span class="${this._ticketStatusClass(t.status)}">${this._ticketStatusLabel(t.status)}</span></td>
        <td>${t.reporter}</td>
        <td style="font-size:13px">${t.title}</td>
        <td>${t.module || '—'}</td>
        <td style="font-size:12px;white-space:nowrap">${(t.created_at || '').slice(0, 16)}</td>
      </tr>`).join('');

    let detail = '';
    if (this.selectedTicketId) {
      const one = await this.fetch(`/api/v2/feedback/${this.selectedTicketId}`);
      const f = one.feedback || {};
      const logs = (f.related_logs || []).map(l => `
        <tr>
          <td style="font-size:11px">${l.created_at || ''}</td>
          <td>${l.level || ''}</td>
          <td>${l.action || ''}</td>
          <td style="font-size:12px">${l.message || ''}</td>
        </tr>`).join('');
      detail = `
        <div class="card" style="margin-top:16px;border:2px solid #2563eb">
          <div class="card-head">${f.ticket_no} · ${this._ticketStatusLabel(f.status)}
            <span class="hint">${f.reporter} · ${f.created_at || ''}</span></div>
          <div class="card-body">
            <div class="ticket-detail-grid">
              <div><div class="ticket-meta">环节</div><strong>${f.module || '—'}</strong> / ${f.page_view || ''} ${f.tab_name ? '· ' + f.tab_name : ''}</div>
              <div><div class="ticket-meta">紧急程度</div>${f.severity || 'normal'}</div>
            </div>
            <p><strong>问题：</strong>${f.title}</p>
            <p style="font-size:13px;margin:8px 0">${f.description || '—'}</p>
            <p style="font-size:13px;color:#6b7280"><strong>期望：</strong>${f.expected_behavior || '—'}</p>
            ${f.context?.last_api_error ? `<div class="callout warn" style="margin:12px 0;font-size:12px"><strong>最近 API 报错</strong><pre class="json">${JSON.stringify(f.context.last_api_error, null, 2)}</pre></div>` : ''}
            <hr style="margin:16px 0;border:none;border-top:1px solid #e5e7eb" />
            <p class="cfg-desc"><strong>后台处理</strong>（查因 → 修复 → 结案）</p>
            <div class="form-row">
              <div class="form-group"><label>状态</label>
                <select id="tk-status">
                  <option value="open" ${f.status === 'open' ? 'selected' : ''}>待处理</option>
                  <option value="investigating" ${f.status === 'investigating' ? 'selected' : ''}>排查中</option>
                  <option value="resolved" ${f.status === 'resolved' ? 'selected' : ''}>已修复</option>
                  <option value="wont_fix" ${f.status === 'wont_fix' ? 'selected' : ''}>不处理</option>
                </select></div>
            </div>
            <div class="form-group"><label>原因分析</label>
              <textarea id="tk-root-cause" rows="3" placeholder="根因是什么？">${f.root_cause || ''}</textarea></div>
            <div class="form-group"><label>修复说明 / 给用户的回复</label>
              <textarea id="tk-resolution" rows="3" placeholder="做了什么修复？用户侧如何验证？">${f.resolution || ''}</textarea></div>
            <div class="form-group"><label>内部备注</label>
              <textarea id="tk-admin-notes" rows="2">${f.admin_notes || ''}</textarea></div>
            <div class="actions">
              <button class="btn btn-primary" onclick="App.saveTicket(${f.feedback_id})">保存处理结果</button>
            </div>
            <div class="card" style="margin-top:16px">
              <div class="card-head">关联运行日志（反馈时间 ±30 分钟 · 共 ${f.log_count || 0} 条）</div>
              <div class="card-body table-wrap" style="max-height:240px;overflow:auto">
                <table><thead><tr><th>时间</th><th>级别</th><th>动作</th><th>消息</th></tr></thead>
                <tbody>${logs || '<tr><td colspan=4 class="empty">无关联日志</td></tr>'}</tbody></table>
              </div>
            </div>
          </div>
        </div>`;
    }

    const sum = data.summary || {};
    return `
      <div class="callout">使用者点顶部「反馈问题」提交 → 您在此接单、看关联日志、写原因和修复说明 → 标记已修复。</div>
      <div class="grid grid-4" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">
        <div class="card card-body stat-card"><div class="val status-open">${sum.open ?? 0}</div><div class="lbl">待处理</div></div>
        <div class="card card-body stat-card"><div class="val status-investigating">${sum.investigating ?? 0}</div><div class="lbl">排查中</div></div>
        <div class="card card-body stat-card"><div class="val status-resolved">${sum.resolved ?? 0}</div><div class="lbl">已修复</div></div>
        <div class="card card-body stat-card"><div class="val">${sum.total ?? 0}</div><div class="lbl">累计工单</div></div>
      </div>
      <div class="actions" style="margin-bottom:12px">
        <button class="btn btn-sm ${!filter ? 'btn-primary' : ''}" onclick="App.setTicketFilter('')">全部</button>
        <button class="btn btn-sm ${filter === 'open' ? 'btn-primary' : ''}" onclick="App.setTicketFilter('open')">待处理</button>
        <button class="btn btn-sm ${filter === 'investigating' ? 'btn-primary' : ''}" onclick="App.setTicketFilter('investigating')">排查中</button>
        <button class="btn btn-sm ${filter === 'resolved' ? 'btn-primary' : ''}" onclick="App.setTicketFilter('resolved')">已修复</button>
      </div>
      <div class="card"><div class="card-body table-wrap">
        <table><thead><tr><th>工单号</th><th>状态</th><th>反馈人</th><th>问题</th><th>环节</th><th>时间</th></tr></thead>
        <tbody>${rows || '<tr><td colspan=6 class="empty">暂无反馈，使用者可通过顶部「反馈问题」提交</td></tr>'}</tbody></table>
      </div></div>${detail}`;
  },

  setTicketFilter(f) {
    this.ticketFilter = f;
    this.render();
  },

  async saveTicket(id) {
    const body = {
      status: document.getElementById('tk-status')?.value,
      root_cause: document.getElementById('tk-root-cause')?.value,
      resolution: document.getElementById('tk-resolution')?.value,
      admin_notes: document.getElementById('tk-admin-notes')?.value,
      operator: 'admin',
    };
    await this.fetch(`/api/v2/feedback/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    alert('已保存处理结果');
    await this.refresh();
    this.selectedTicketId = id;
    this.setConfigTab('tickets');
  },

  async renderModulesPanel() {
    const map = await this.fetch('/api/v2/admin/modules');
    const summary = map.summary || {};
    const phaseHtml = (map.phases || []).map(ph => {
      const mods = (ph.modules || []).map(m => `
        <tr>
          <td>${m.name}</td>
          <td>${this.moduleStatusBadge(m.effective_status || m.status)}</td>
          <td>${m.owner || '—'}</td>
          <td style="font-size:12px;color:#6b7280">${m.note || ''}</td>
          <td><button class="btn btn-sm" onclick="App.goModuleEntry('${this.escAttr(m.entry || '')}')">进入</button></td>
        </tr>`).join('');
      return `
        <div class="card" style="margin-bottom:16px">
          <div class="card-head">${ph.name || ph.id}
            <span class="hint">${ph.agent_label || ''} · ${(ph.steps || []).join(' / ')}</span>
            <button class="btn btn-sm" style="margin-left:8px" onclick="App.setConfigTab('${ph.agent || 'agent1'}')">配置本 Agent</button>
          </div>
          <div class="card-body table-wrap">
            <table><thead><tr><th>功能模块</th><th>状态</th><th>负责人</th><th>说明</th><th></th></tr></thead>
            <tbody>${mods || '<tr><td colspan=5 class="empty">无</td></tr>'}</tbody></table>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="grid grid-4" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px">
        <div class="card card-body stat-card"><div class="val">${summary.total ?? '—'}</div><div class="lbl">功能模块</div></div>
        <div class="card card-body stat-card"><div class="val" style="color:#059669">${summary.ready ?? 0}</div><div class="lbl">可运行</div></div>
        <div class="card card-body stat-card"><div class="val" style="color:#d97706">${summary.placeholder ?? 0}</div><div class="lbl">待填内容</div></div>
        <div class="card card-body stat-card"><div class="val" style="color:#2563eb">${summary.skeleton ?? 0}</div><div class="lbl">骨架入口</div></div>
      </div>
      ${phaseHtml}`;
  },

  async renderLogsPanel() {
    const data = await this.fetch('/api/v2/admin/logs?limit=80');
    const rows = (data.logs || []).map(l => `
      <tr>
        <td style="white-space:nowrap;font-size:12px">${l.created_at || ''}</td>
        <td><span class="badge-sm ${l.level === 'error' ? 'warn' : 'info'}">${l.level || 'info'}</span></td>
        <td>${l.module || '—'}</td>
        <td>${l.action || '—'}</td>
        <td style="font-size:13px">${l.message || ''}</td>
        <td>${l.operator || '—'}</td>
      </tr>`).join('');
    return `
      <div class="callout" style="margin-bottom:12px">技术审计日志（API 启动、配置保存、Skill 执行等）。<strong>使用者反馈请查「问题工单」</strong>，工单会自动关联此处的相关记录。</div>
      <div class="actions" style="margin-bottom:12px">
        <button class="btn btn-sm" onclick="App.testAdminLog()">写入测试日志</button>
        <button class="btn btn-sm" onclick="App.setConfigTab('logs')">刷新</button>
      </div>
      <div class="card"><div class="card-body table-wrap">
        <table><thead><tr><th>时间</th><th>级别</th><th>模块</th><th>动作</th><th>消息</th><th>操作人</th></tr></thead>
        <tbody>${rows || '<tr><td colspan=6 class="empty">暂无日志</td></tr>'}</tbody></table>
      </div></div>`;
  },

  async renderPromptBlock(key, fieldPrefix) {
    const one = await this.fetch(`/api/v2/admin/prompts/${encodeURIComponent(key)}`).catch(() => ({}));
    const p = one.prompt || {};
    const pf = fieldPrefix || key.replace(/[^a-z0-9]/gi, '-');
    const displayTitle = key === 'ai_creative' ? 'AI创意活动提示词' : (p.title || key);
    const displayDescription = key === 'ai_creative' ? '' : (p.description || '');
    const defaultCreativePrompt = `你是营销活动创意策划助手。请根据用户上传的行业报告、OTA 趋势、竞对活动和目的地信息，生成可执行的酒店营销活动候选。每条活动必须包含：活动名称、目标国家/城市、推广日期、目标客群、核心机会点、活动机制、所需素材和数据依据。不得臆造未提供的酒店数据；不确定的信息标注“待确认”。输出结构化 JSON，便于人工修改后送入评审池。`;
    const promptContent = p.content || (key === 'ai_creative' ? defaultCreativePrompt : '');
    return `
      <div class="form-group">
        <div class="prompt-title-row"><label>${displayTitle} <span class="req">*</span> ${this.moduleStatusBadge(p.status === 'ready' ? 'ready' : 'placeholder')}
          ${key === 'ai_creative' ? '' : `<span class="hint" style="font-weight:normal;margin-left:8px">负责人：${p.owner || '—'}</span>`}</label>
        <div class="prompt-header-actions"><button class="btn btn-primary" onclick="App.useDefaultPrompt('${key}','${pf}')">默认提示词</button><button class="btn btn-primary" onclick="App.savePromptOnly('${key}','${pf}')">保存更改后提示词</button></div></div>
        <p class="cfg-desc">${displayDescription}</p>
        <textarea id="prompt-${pf}-content" rows="10" placeholder="待填入">${this.escAttr(promptContent)}</textarea>
      </div>
        <div class="form-group"><div class="notes-title-row"><label>备注</label><button class="btn btn-primary" onclick="App.savePromptNotes('${key}','${pf}')">保存备注</button></div>
        <textarea id="prompt-${pf}-notes" rows="2">${p.notes || ''}</textarea>
      </div>`;
  },

  async renderAgent1ConfigPanel() {
    const sub = this.agent1ConfigSub || 'manual';
    const cfg = this.agentConfig.agent1 || {};
    const mc = cfg.manual_calendar || {};
    const cr = cfg.creative || {};
    const mcpOk = this.data.mcp?.warehouse?.mode === 'warehouse_mcp';
    const llm = this.data.mcp?.llm || {};
    const llmOk = llm.qwen?.api_key_set || llm.deepseek?.api_key_set;

    const flowHtml = `
      <div class="agent1-flow card" style="margin-bottom:16px;border:1px solid #dbeafe;background:#f8fafc">
        <div class="card-body" style="padding:14px 18px">
          <div style="font-size:13px;font-weight:600;margin-bottom:10px">Agent1 · 营销活动日历初版 — 四条路径 → 同一评审池</div>
          <div class="agent1-flow-steps" style="display:flex;flex-wrap:wrap;gap:8px;font-size:12px">
            <span class="tag ${sub === 'manual' ? 'tag-prep' : ''}">① 人工标准活动 · MCP+AI</span>
            <span class="tag ${sub === 'upload' ? 'tag-prep' : ''}">② 人工上传日历 · 兜底</span>
            <span class="tag ${sub === 'creative' ? 'tag-prep' : ''}">③ AI创意 · Prompt</span>
            <span class="tag ${sub === 'intel' ? 'tag-prep' : ''}">④ 人工补充创意活动</span>
            <span style="color:#9ca3af">→</span>
            <strong style="color:#1d4ed8">初版评审池</strong>
          </div>
          <div style="margin-top:10px;font-size:12px;color:#6b7280">
            通用底座：MCP <span class="${mcpOk ? 'ok-text' : 'warn-text'}">${mcpOk ? '已连通' : '未连通'}</span>
            · AI模型 <span class="${llmOk ? 'ok-text' : 'warn-text'}">${llmOk ? '已配置' : '未配置'}</span>
            ${!mcpOk ? ' · <a href="#" onclick="App.setConfigTab(\'infra\');return false" style="color:#1d4ed8">去配置 MCP</a>' : ''}
            ${!llmOk ? ' · <a href="#" onclick="App.setConfigTab(\'infra\');return false" style="color:#1d4ed8">去配置 AI</a>' : ''}
          </div>
        </div>
      </div>`;

    const tabsHtml = `
      <div class="tabs agent1-config-tabs" style="margin-bottom:16px;flex-wrap:wrap">
        <button class="tab ${sub === 'manual' ? 'active' : ''}" onclick="App.setConfigTab('agent1','manual')">① 人工标准活动</button>
        <button class="tab ${sub === 'upload' ? 'active' : ''}" onclick="App.setConfigTab('agent1','upload')">② 人工上传日历</button>
        <button class="tab ${sub === 'creative' ? 'active' : ''}" onclick="App.setConfigTab('agent1','creative')">③ AI 创意活动</button>
        <button class="tab ${sub === 'intel' ? 'active' : ''}" onclick="App.setConfigTab('agent1','intel')">④ 人工补充创意活动</button>
      </div>`;

    if (sub === 'intel') {
      return flowHtml + tabsHtml + await this.renderAgent1IntelConfigPanel(cfg);
    }
    if (sub === 'upload') {
      return flowHtml + tabsHtml + this.renderAgent1UploadConfigPanel();
    }

    if (sub === 'creative') {
      const creativeBlock = await this.renderPromptBlock('ai_creative', 'creative');
      return flowHtml + tabsHtml + `
      <div class="card">
        <div class="card-head">AI 创意活动策划 · 配置
          <span class="hint">Prompt 配置 · 资讯补充在 Tab④ · 一键创作 → 评审池</span></div>
        <div class="card-body">
          <div class="callout" style="margin-bottom:14px;font-size:12px">
            <strong>一个独立 Prompt：</strong>定义 AI 如何阅读 Tab④ 上传的 OTA/竞对/公众号资讯，并输出创意活动方案。
            上传与一键创作在 <a href="#" onclick="App.setConfigTab('agent1','intel');return false" style="color:#1d4ed8">Tab④ 上传资讯补充</a>。
          </div>
          <div class="cfg-step"><span class="cfg-step-n">1</span><strong>运行参数</strong></div>
          <div class="form-row">
            <div class="form-group"><label>模型选择</label>
              <select id="a1-creative-provider">
                <option value="inherit" ${(cr.llm_provider || 'inherit') === 'inherit' ? 'selected' : ''}>系统默认</option>
                <option value="qwen" ${cr.llm_provider === 'qwen' ? 'selected' : ''}>公司 Dragon API（Qwen）</option>
                <option value="deepseek" ${cr.llm_provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
              </select></div>
            <div class="form-group"><label>提前准备月数</label>
              <input id="cfg-prep" type="number" value="${cfg.prep_lead_months || 3}" /></div>
          </div>

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">2</span><strong>AI 创意活动 Prompt</strong> — 唯一提示词：读资讯 + 生成创意 + 输出格式</div>
          ${creativeBlock}

          <div class="actions" style="margin-top:16px">
            <button class="btn btn-primary" onclick="App.saveAgent1CreativeConfig()">保存 AI 创意配置</button>
            <button class="btn" onclick="App.setConfigTab('agent1','intel')">去 Tab④ 一键创作</button>
            <button class="btn" onclick="App.navigate('agent1')">去评审池</button>
          </div>
        </div>
      </div>`;
    }

    const calendarAiBlock = await this.renderPromptBlock('manual_calendar_ai', 'calendar-ai');

    if (sub === 'manual') {
      return flowHtml + tabsHtml + `
      <div class="card">
        <div class="card-head">人工标准活动策划 · 配置
          <span class="hint">MCP 取数 → AI 分析并输出日历 → 初版评审池</span></div>
        <div class="card-body">
          <div class="callout" style="margin-bottom:14px;font-size:12px">
            <strong>两段 Prompt：</strong>① 上方 MCP 取数说明 — 告诉数仓拉什么；
            ② 下方 AI 分析输出 — 告诉 AI 拿到数据后怎么分析、输出哪些列。
          </div>
          <div class="cfg-step"><span class="cfg-step-n">1</span><strong>规划参数</strong> — 决定取数时间范围与归属规划年</div>
          <div class="form-row">
            <div class="form-group"><label>规划归属年</label>
              <input id="a1-plan-year" type="number" value="${mc.planning_year || 2027}" /></div>
            <div class="form-group"><label>数据窗起点</label>
              <input id="a1-win-start" value="${mc.data_window_start || '2026-08'}" placeholder="2026-08" />
              <span class="hint">离店/预订统计起始月</span></div>
            <div class="form-group"><label>数据窗终点</label>
              <input id="a1-win-end" value="${mc.data_window_end || '2027-07'}" placeholder="2027-07" />
              <span class="hint">滚动 12 个月窗口</span></div>
          </div>

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">2</span><strong>MCP 取数说明</strong> — 一个框写清 1/2/3 要什么数据，MCP 会解读并拉数</div>
          <div class="callout" style="margin-bottom:12px;font-size:12px">
            用自然语言或 SQL 均可；可用占位符 <code>{data_window_start}</code> <code>{data_window_end}</code> <code>{planning_year}</code>。
            参考飞书数据字段：<a href="https://didatravel.feishu.cn/wiki/JAulw5Ev7iCHNXkqlZ4cGT5znvh?sheet=1gjyEB" target="_blank" rel="noopener">27年营销日历数据表</a>
          </div>
          <div class="form-group"><label>取数需求（1 离店 · 2 预订 · 3 P75）</label>
            <textarea id="a1-mcp-fetch" rows="10" placeholder="1. 离店数据：…&#10;2. 预订数据：…&#10;3. P75：…">${this.escAttr(mc.mcp_fetch_prompt || this._legacyFetchPrompt(mc))}</textarea>
            <span class="hint">例：「我想要 2026-08 到 2027-07 每个国家每月离店订单和离店 TTV」— 与你在飞书/Data MCP 里提问一样</span>
          </div>

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">3</span><strong>AI 分析与日历输出 Prompt</strong> — 分析规则（A/B/C）+ 输出列格式 + 主题要求，合一填写</div>
          ${calendarAiBlock}

          <div class="actions" style="margin-top:16px">
            <button class="btn btn-primary" onclick="App.saveAgent1ManualConfig()">保存标准活动配置</button>
            <button class="btn" onclick="App.navigate('agent1',{tab:'manual-plan'})">去运行 · 生成标准活动规划</button>
            <button class="btn" onclick="App.navigate('agent1')">去评审池</button>
          </div>
        </div>
      </div>`;
    }

    return flowHtml + tabsHtml + `<div class="empty">请选择配置 Tab</div>`;
  },

  async renderAgent1IntelConfigPanel(cfg) {
    const reports = await this.fetch('/api/v2/intel/reports?limit=10');
    const llm = this.data.mcp?.llm || {};
    const llmOk = llm.qwen?.api_key_set || llm.deepseek?.api_key_set;
    const preview = this.agent1CreativePreview;
    const reportRows = (reports.reports || []).slice(0, 8).map(r => `
      <tr><td>${r.report_title || '—'}</td><td>${r.report_date || '—'}</td>
        <td style="font-size:12px;max-width:240px">${(r.summary || '').slice(0, 80)}</td></tr>`).join('');

    const previewRows = (preview?.suggestions || []).map((s, i) => `
      <tr>
        <td><input type="checkbox" class="a1-creative-pick" data-idx="${i}" checked /></td>
        <td>${this.escAttr(s.campaign_name || '—')}</td>
        <td>${this.escAttr(s.target_dest || '—')}</td>
        <td>${this.escAttr(s.promotion_month_hint || '—')}</td>
        <td style="font-size:12px;max-width:280px">${this.escAttr((s.rationale || '').slice(0, 120))}</td>
      </tr>`).join('');

    const previewBlock = preview?.suggestions?.length ? `
      <div class="card" style="margin-top:16px;border:2px solid #86efac;background:#f0fdf4">
        <div class="card-head">AI 创意活动预览（${preview.suggestions.length} 条）
          <span class="hint">来源：${this.escAttr(preview.intel_title || '—')}</span></div>
        <div class="card-body">
          <div class="table-wrap"><table>
            <thead><tr><th style="width:36px">选</th><th>活动名称</th><th>目的地</th><th>推广月</th><th>机会点 / 依据</th></tr></thead>
            <tbody>${previewRows}</tbody>
          </table></div>
          <div class="actions" style="margin-top:12px">
            <button class="btn btn-success" onclick="App.submitAgent1CreativePreview()">送入初版评审池</button>
            <button class="btn" onclick="App.clearAgent1CreativePreview()">清除预览</button>
            <button class="btn" onclick="App.navigate('agent1')">去评审池查看</button>
          </div>
        </div>
      </div>` : '';

    return `
      <details class="card" style="margin-bottom:16px">
        <summary class="card-head config-summary" style="cursor:pointer;list-style:none">人工补充创意活动<span class="config-toggle">▾</span></summary>
        <div class="card-body">
          <div class="cfg-step"><span class="cfg-step-n">1</span><strong>补充资讯</strong> — 粘贴链接、正文或上传文件</div>
          <div class="form-group" style="margin-bottom:12px;padding:12px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px">
            <label>公众号 / 网页链接</label>
            <input id="a1-intel-url" placeholder="粘贴 mp.weixin.qq.com 公众号文章链接，或 OTA/行业报道 URL" />
          </div>
          <div class="grid grid-2">
            <div class="form-group"><label>报告标题（可选）</label>
              <input id="a1-intel-title" placeholder="如：2026Q1 OTA 出境趋势" /></div>
            <div class="form-group"><label>目的地标签</label>
              <input id="a1-intel-dest" placeholder="Japan,Singapore" /></div>
          </div>
          <div class="form-group"><label>报告正文（粘贴）</label>
            <textarea id="a1-intel-content" rows="6" placeholder="粘贴行业分析、竞对活动描述、公众号文章…"></textarea></div>
          <div class="form-group"><label>或上传文本/Markdown 文件</label>
            <input type="file" id="a1-intel-file" accept=".txt,.md,.csv" /></div>

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">2</span><strong>一键创作</strong> — 自动入库 + AI 分析 → 预览创意活动列表</div>
          <p style="font-size:13px;margin-bottom:12px;color:#4b5563">
            点击后：若有链接/正文/文件则先入库，再按 Tab③ Prompt 分析活动机会点，生成 AI 创意活动列表（可勾选后送入初版评审池）。
          </p>
          <div class="actions intel-actions" style="margin-bottom:8px">
            <button class="btn btn-success btn-lg" onclick="App.oneClickAgent1Creative()" ${llmOk ? '' : 'disabled'}>
              一键创作 AI 创意活动
            </button>
            <button class="btn" onclick="App.uploadAgent1IntelUrl()">仅抓取链接入库</button>
            <button class="btn" onclick="App.uploadAgent1Intel()">仅上传入库</button>
          </div>

          ${previewBlock}

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">3</span><strong>最近情报（${reports.count || 0} 条）</strong></div>
          <div class="table-wrap"><table><thead><tr><th>标题</th><th>日期</th><th>摘要</th></tr></thead>
            <tbody>${reportRows || '<tr><td colspan=3 class="empty">暂无，请先上传或一键创作</td></tr>'}</tbody></table></div>
        </div>
      </details>`;
  },

  renderAgent1UploadConfigPanel() {
    return `
      <div class="card">
        <div class="card-head">人工上传 · 标准活动初版日历
          <span class="hint">线下 Excel 做好 → 解析 A–M 列 → 直接进初版评审池</span></div>
        <div class="card-body">
          <div class="callout" style="margin-bottom:14px;font-size:12px">
            适用于营销负责人线下用 Excel 完成全年规划后，直接上传进系统评审，无需再走 MCP 取数流程。
          </div>
          <div class="cfg-step"><span class="cfg-step-n">1</span><strong>准备 Excel</strong> — 列名对齐飞书「营销日历初版」</div>
          <div class="table-wrap" style="margin:12px 0;font-size:12px">
            <table><thead><tr><th>列</th><th>字段</th><th>说明</th></tr></thead><tbody>
              <tr><td>A</td><td>活动场次</td><td>1–12 月分组</td></tr>
              <tr><td>B</td><td>月度主活动主题</td><td>当月主主题</td></tr>
              <tr><td>C</td><td>副活动主题</td><td>必填之一</td></tr>
              <tr><td>D</td><td>覆盖目的地块/城市</td><td>必填之一</td></tr>
              <tr><td>E</td><td>对应离店/预订窗口期</td><td></td></tr>
              <tr><td>F</td><td>提前预定天数 P75</td><td></td></tr>
              <tr><td>G</td><td>选目的地的数据依据</td><td></td></tr>
              <tr><td>H–M</td><td>资源对接/交付/T-14/上线/离档/复盘</td><td>可留空，人工后续填</td></tr>
            </tbody></table>
          </div>

          <hr class="cfg-divider" />
          <div class="cfg-step"><span class="cfg-step-n">2</span><strong>上传并送入评审池</strong></div>
          <div class="form-group">
            <label>选择 Excel / CSV 文件</label>
            <input type="file" id="a1-upload-calendar" accept=".xlsx,.xls,.csv" />
          </div>
          <div id="a1-upload-result"></div>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.uploadAgent1ManualCalendar()">上传并送入初版评审池</button>
            <button class="btn" onclick="App.navigate('agent1')">去评审池查看</button>
          </div>
        </div>
      </div>`;
  },

  async renderAgentConfigPanel(key) {
    const meta = this.AGENT_CONFIG_META[key] || { label: key };
    if (key === 'agent1') return this.renderAgent1ConfigPanel();
    const cfg = this.agentConfig[key] || {};
    let promptBlock = '';
    if (meta.promptKey) {
      promptBlock = await this.renderPromptBlock(meta.promptKey, meta.promptKey);
    }
    return `
      <div class="card">
        <div class="card-head">${meta.label} · 提示词与功能配置
          <span class="hint">${meta.sub || ''}</span></div>
        <div class="card-body">
          <div class="form-row">
            <div class="form-group"><label>名称</label><input id="cfg-name" value="${cfg.name || ''}" /></div>
            <div class="form-group"><label>角色</label><input id="cfg-role" value="${cfg.role || ''}" /></div>
          </div>
          ${promptBlock}
          <div class="form-group"><label>System Prompt</label>
            <textarea id="cfg-prompt" rows="8">${cfg.system_prompt || ''}</textarea></div>
          <div class="form-row">
            <div class="form-group"><label>工具 / MCP</label>
              <input id="cfg-tools" value="${(cfg.tools || []).join(', ')}" /></div>
            <div class="form-group"><label>人工闸门</label>
              <input id="cfg-gates" value="${(cfg.human_gates || []).join(' | ')}" /></div>
          </div>
          <div class="actions">
            <button class="btn btn-primary" onclick="App.saveAgentConfig('${key}'${meta.promptKey ? `,'${meta.promptKey}'` : ''})">保存配置</button>
            <button class="btn" onclick="App.navigate('${key}')">去工作台</button>
          </div>
        </div>
      </div>`;
  },

  async savePromptFields(key, fieldPrefix) {
    const pf = fieldPrefix || key.replace(/[^a-z0-9]/gi, '-');
    const content = document.getElementById(`prompt-${pf}-content`)?.value || '';
    const notes = document.getElementById(`prompt-${pf}-notes`)?.value || '';
    await this.fetch(`/api/v2/admin/prompts/${encodeURIComponent(key)}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, notes, operator: 'admin-ui' }),
    });
  },
  async useDefaultPrompt(key,pf){const one=await this.fetch(`/api/v2/admin/prompts/${encodeURIComponent(key)}`).catch(()=>({}));const node=document.getElementById(`prompt-${pf}-content`);if(node&&one.prompt)node.value=one.prompt.content||'';},
  async savePromptOnly(key,pf){await this.savePromptFields(key,pf);alert('提示词已保存为下一次默认提示词');},
  executePrompt(key,pf){alert('已提交 AI 提示词执行任务');},
  async savePromptNotes(key,pf){await this.savePromptFields(key,pf);alert('备注已保存');},

  _legacyFetchPrompt(mc) {
    const parts = [mc.fetch_checkout, mc.fetch_booking, mc.fetch_p75, mc.mcp_query_profile].filter(Boolean);
    if (parts.length) return parts.join('\n\n');
    return `请从数仓拉取以下数据（时间范围：{data_window_start} 至 {data_window_end}）：\n\n1. 离店数据：每个国家、每月的离店订单数和离店 TTV\n2. 预订数据：每个国家、每月的预订订单数和预订 TTV\n3. 提前预订 P75：各分析单元在目标离店月的 P75 天数`;
  },

  async saveAgent1ManualConfig() {
    const winStart = document.getElementById('a1-win-start')?.value || '2026-08';
    const winEnd = document.getElementById('a1-win-end')?.value || '2027-07';
    const planYear = parseInt(document.getElementById('a1-plan-year')?.value || '2027');
    const subst = (s) => (s || '')
      .replace(/\{data_window_start\}/g, winStart)
      .replace(/\{data_window_end\}/g, winEnd)
      .replace(/\{planning_year\}/g, String(planYear));
    const mc = {
      planning_year: planYear,
      data_window_start: winStart,
      data_window_end: winEnd,
      mcp_fetch_prompt: subst(document.getElementById('a1-mcp-fetch')?.value),
    };
    await this.fetch('/api/v2/config/agents/agent1', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ manual_calendar: mc }),
    });
    await this.savePromptFields('manual_calendar_ai', 'calendar-ai');
    this.agentConfig.agent1 = { ...this.agentConfig.agent1, manual_calendar: mc };
    alert('人工标准活动配置已保存');
    this.setConfigTab('agent1', 'manual');
  },

  async saveAgent1CreativeConfig() {
    const body = {
      prep_lead_months: parseInt(document.getElementById('cfg-prep')?.value || '3'),
      creative: {
        llm_provider: document.getElementById('a1-creative-provider')?.value || 'inherit',
      },
    };
    await this.fetch('/api/v2/config/agents/agent1', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    await this.savePromptFields('ai_creative', 'creative');
    this.agentConfig.agent1 = { ...this.agentConfig.agent1, ...body };
    alert('AI 创意活动配置已保存');
    this.setConfigTab('agent1', 'creative');
  },

  async _uploadAgent1IntelPayload() {
    const title = document.getElementById('a1-intel-title')?.value?.trim() || '';
    const content = document.getElementById('a1-intel-content')?.value?.trim() || '';
    const dest = document.getElementById('a1-intel-dest')?.value || '';
    const url = document.getElementById('a1-intel-url')?.value?.trim() || '';
    const fileInput = document.getElementById('a1-intel-file');

    if (url) {
      const r = await this.fetch('/api/v2/intel/reports/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title, destinations: dest }),
      });
      if (r.ok === false) throw new Error(r.error || '链接抓取失败');
      return r.intel_id;
    }
    if (fileInput?.files?.length) {
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      fd.append('title', title || fileInput.files[0].name);
      fd.append('destinations', dest);
      const resp = await fetch('/api/v2/intel/reports/upload-file', { method: 'POST', body: fd });
      if (!resp.ok) throw new Error(await resp.text());
      const r = await resp.json();
      return r.intel_id;
    }
    if (content) {
      const r = await this.fetch('/api/v2/intel/reports/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title || `上传报告 (${new Date().toISOString().slice(0, 10)})`,
          content,
          destinations: dest,
        }),
      });
      return r.intel_id;
    }
    return null;
  },

  async oneClickAgent1Creative() {
    try {
      let intelId = await this._uploadAgent1IntelPayload();
      if (!intelId) {
        const reports = await this.fetch('/api/v2/intel/reports?limit=1');
        intelId = reports.reports?.[0]?.intel_id;
        if (!intelId) {
          alert('请先粘贴链接、正文或上传文件，或确保情报库中已有报告');
          return;
        }
      }
      if (!confirm('将基于最新资讯调用 AI 分析活动机会点并生成创意活动预览？')) return;
      const r = await this.fetch('/api/v2/intel/generate-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intel_id: intelId, intel_limit: 1, preview_only: true }),
      });
      if (r.ok === false) throw new Error(r.error || '生成失败');
      this.agent1CreativePreview = {
        suggestions: r.suggestions || [],
        intel_id: r.intel_id || intelId,
        intel_title: r.intel_title,
        llm_provider: r.llm_provider,
      };
      this.setConfigTab('agent1', 'intel');
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  async submitAgent1CreativePreview() {
    const preview = this.agent1CreativePreview;
    if (!preview?.suggestions?.length) return alert('暂无预览，请先一键创作');
    const picks = [];
    document.querySelectorAll('.a1-creative-pick').forEach(el => {
      const idx = parseInt(el.dataset.idx, 10);
      if (el.checked && preview.suggestions[idx]) picks.push(preview.suggestions[idx]);
    });
    if (!picks.length) return alert('请至少勾选一条活动');
    if (!confirm(`将 ${picks.length} 条 AI 创意活动送入初版评审池？`)) return;
    try {
      const r = await this.fetch('/api/v2/intel/submit-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          suggestions: picks,
          intel_id: preview.intel_id,
        }),
      });
      if (r.ok === false) throw new Error(r.error || '提交失败');
      alert(`已送入初版评审池：新增 ${r.inserted || 0} 条，跳过重复 ${r.skipped || 0} 条`);
      this.agent1CreativePreview = null;
      this.navigate('agent1');
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  clearAgent1CreativePreview() {
    this.agent1CreativePreview = null;
    this.setConfigTab('agent1', 'intel');
  },

  async uploadAgent1IntelUrl() {
    const url = document.getElementById('a1-intel-url')?.value?.trim();
    const title = document.getElementById('a1-intel-title')?.value?.trim() || '';
    const dest = document.getElementById('a1-intel-dest')?.value || '';
    if (!url) {
      alert('请粘贴公众号或网页链接');
      return;
    }
    try {
      const r = await this.fetch('/api/v2/intel/reports/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title, destinations: dest }),
      });
      if (r.ok === false) throw new Error(r.error || '抓取失败');
      const f = r.fetch || {};
      alert(`链接已抓取入库：${f.title || title || '—'}（${f.char_count || '?'} 字）\n可点击「LLM 生成创意活动」`);
      this.setConfigTab('agent1', 'intel');
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  async uploadAgent1Intel() {
    const title = document.getElementById('a1-intel-title')?.value;
    const content = document.getElementById('a1-intel-content')?.value;
    const dest = document.getElementById('a1-intel-dest')?.value || '';
    const fileInput = document.getElementById('a1-intel-file');
    try {
      if (fileInput?.files?.length) {
        const fd = new FormData();
        fd.append('file', fileInput.files[0]);
        fd.append('title', title || fileInput.files[0].name);
        fd.append('destinations', dest);
        const r = await fetch('/api/v2/intel/reports/upload-file', { method: 'POST', body: fd });
        if (!r.ok) throw new Error(await r.text());
      } else if (content) {
        await this.fetch('/api/v2/intel/reports/upload', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title || `上传报告 (${new Date().toISOString().slice(0, 10)})`,
            content,
            destinations: dest,
          }),
        });
      } else {
        alert('请填写正文，或选择文件，或使用链接抓取');
        return;
      }
      alert('资讯已上传入库');
      this.setConfigTab('agent1', 'intel');
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  async generateAgent1IntelSuggestions() {
    if (!confirm('调用 LLM 汇总最近情报并直接送入评审池？（如需先预览请用「一键创作」）')) return;
    try {
      const r = await this.fetch('/api/v2/intel/generate-suggestions', { method: 'POST' });
      if (r.ok === false) throw new Error(r.error || '生成失败');
      alert(`已生成 ${r.generated ?? r.raw_count ?? 0} 条 AI 创意建议，请到评审池查看`);
      this.navigate('agent1');
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  async uploadAgent1ManualCalendar() {
    const input = document.getElementById('a1-upload-calendar');
    if (!input?.files?.[0]) return alert('请选择 Excel 或 CSV 文件');
    const fd = new FormData();
    fd.append('file', input.files[0]);
    fd.append('operator', 'marketer');
    try {
      const r = await fetch('/api/v2/agent1/manual-calendar/upload-pool', { method: 'POST', body: fd });
      const data = await r.json();
      const box = document.getElementById('a1-upload-result');
      if (!data.ok) {
        if (box) box.innerHTML = `<div class="callout warn" style="margin-top:12px">${data.error || '上传失败'}</div>`;
        alert(data.error || '上传失败');
        return;
      }
      const preview = (data.preview || []).map(row => `
        <tr><td>${row.sub_theme || row.main_theme || '—'}</td><td>${row.destinations || '—'}</td>
          <td>${row.checkout_window || '—'}</td></tr>`).join('');
      if (box) box.innerHTML = `
        <div class="callout" style="margin-top:12px">
          已解析 ${data.parsed_rows} 条 · 新入池 ${data.inserted} 条 · 跳过重复 ${data.skipped} 条
        </div>
        ${preview ? `<div class="table-wrap" style="margin-top:8px"><table><thead><tr><th>副主题</th><th>目的地</th><th>离店窗</th></tr></thead><tbody>${preview}</tbody></table></div>` : ''}`;
      alert(`上传成功：${data.inserted} 条已送入初版评审池`);
    } catch (e) {
      alert(e.message || String(e));
    }
  },

  setAdminTab(tab, promptKey) {
    this.adminTab = tab;
    if (promptKey !== undefined) this.adminPromptKey = promptKey;
    this.render();
  },

  goModuleEntry(entry) {
    if (!entry) return;
    const path = String(entry).split('?')[0].replace(/^\//, '');
    const qs = entry.includes('?') ? entry.split('?')[1] : '';
    const params = new URLSearchParams(qs);
    const tab = params.get('tab');
    const key = params.get('key');
    if (path === 'system-admin' || path === 'system-config' || path === 'mcp-config') {
      let configTab = path === 'mcp-config' ? 'infra' : 'modules';
      if (tab === 'logs') configTab = 'logs';
      else if (tab === 'prompts' || tab === 'agent1') configTab = 'agent1';
      else if (tab && tab.startsWith('agent')) configTab = tab;
      else if (tab === 'infra') configTab = 'infra';
      else if (tab === 'modules') configTab = 'modules';
      this.navigate('system-config', {
        configTab: key === 'manual_plan_sop' || key === 'ai_creative' ? 'agent1' : configTab,
        agent1Sub: ['manual_plan_sop', 'manual_theme', 'manual_calendar_ai'].includes(key) ? 'manual' : key === 'ai_creative' ? 'creative' : undefined,
        promptKey: key || null,
      });
      return;
    }
    if (entry.includes('tab=config')) {
      const agent = path.match(/^agent(\d)/)?.[0] || 'agent1';
      this.navigate('system-config', { configTab: agent });
      return;
    }
    const view = path || 'home';
    this.navigate(view, { tab: tab || 'work' });
  },

  async testAdminLog() {
    await this.fetch('/api/v2/admin/logs/test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '手动测试日志 · ' + new Date().toLocaleString('zh-CN') }),
    });
    this.setConfigTab('logs');
  },

  async renderCaseLibrary(embedded = false) {
    const archives = await this.fetch('/api/v2/archives?destination=');
    const rows = (Array.isArray(archives) ? archives : []).map(a => `
      <tr>
        <td><strong>${a.activity_name || '—'}</strong></td>
        <td>${a.destination || '—'}</td>
        <td>${a.success_label || '—'}</td>
        <td style="font-size:12px">${(a.reusable_points || '—').slice(0, 80)}</td>
      </tr>`).join('');
    const html = `
      <div class="card">
        <div class="card-head">活动案例库 · 复盘归档Agent 知识库 · 营销策划 RAG 参考</div>
        <div class="card-body table-wrap">
          <table><thead><tr><th>活动</th><th>目的地</th><th>标签</th><th>可复用经验</th></tr></thead>
          <tbody>${rows || '<tr><td colspan=4 class="empty">暂无归档，活动完结后复盘归档Agent 写入</td></tr>'}</tbody></table>
        </div>
      </div>`;
    return embedded ? `${this.tabsHtml()}${html}` : html;
  },

  async saveAgentConfig(key, promptKey) {
    const body = {
      name: document.getElementById('cfg-name')?.value,
      role: document.getElementById('cfg-role')?.value,
      system_prompt: document.getElementById('cfg-prompt')?.value,
      tools: (document.getElementById('cfg-tools')?.value || '').split(',').map(s => s.trim()).filter(Boolean),
      human_gates: (document.getElementById('cfg-gates')?.value || '').split('|').map(s => s.trim()).filter(Boolean),
    };
    await this.fetch(`/api/v2/config/agents/${key}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (promptKey) await this.savePromptFields(promptKey, promptKey);
    alert('配置已保存');
    this.agentConfig[key] = { ...this.agentConfig[key], ...body };
    this.setConfigTab(key);
  },

  bindEvents() {
    const root = document.getElementById('main-content');
    if (!root || root._bound) return;
    root._bound = true;
    root.addEventListener('click', (e) => {
      const el = e.target.closest('[data-action]');
      if (!el) return;
      const action = el.dataset.action;
      const id = el.dataset.id;
      if (action === 'review-campaign') {
        e.stopPropagation();
        this.openCampaignReview(id, el.dataset.schema);
      } else if (action === 'send-a2') {
        e.stopPropagation();
        this.sendToAgent2(id);
      } else if (action === 'review-suggestion') {
        e.stopPropagation();
        this.openSuggestionReview(Number(id), el.dataset.schema);
      } else if (action === 'reject-suggestion') {
        e.stopPropagation();
        this.reviewSuggestion(Number(id), 'reject');
      } else if (action === 'reject-proposal') {
        e.stopPropagation();
        this.rejectCalendarProposal(id);
      } else if (action === 'complete-todo') {
        e.stopPropagation();
        this.completeTodo(Number(el.dataset.todoId));
      } else if (action === 'profile-query') {
        e.stopPropagation();
        this.runProfileQuery(el.dataset.campaignId);
      } else if (action === 'prep-analysis') {
        e.stopPropagation();
        this.runPrepAnalysis(el.dataset.campaignId, false, el.dataset.mode || 'auto');
      } else if (action === 'prep-analysis-apply') {
        e.stopPropagation();
        this.runPrepAnalysis(el.dataset.campaignId, true, el.dataset.mode || 'auto');
      } else if (action === 'qbi-tab') {
        e.stopPropagation();
        this.setQbiTab(el.dataset.tab);
      } else if (action === 'configure-resources') {
        e.stopPropagation();
        this.runConfigureResources(el.dataset.campaignId);
      } else if (action === 'confirm-resources') {
        e.stopPropagation();
        this.confirmResources(el.dataset.campaignId);
      } else if (action === 'resource-override') {
        e.stopPropagation();
        this.applyResourceOverride(el.dataset.campaignId, el.dataset.mode || 'manual_ids');
      } else if (action === 'submit-test') {
        e.stopPropagation();
        this.submitTest(el.dataset.campaignId);
      } else if (action === 'test-mcp-ping') {
        e.stopPropagation();
        this.testMcpPing();
      } else if (action === 'test-mcp-config') {
        e.stopPropagation();
        this.testMcpConfig();
      } else if (action === 'test-feishu-config') {
        e.stopPropagation();
        this.testFeishuConfig();
      } else if (action === 'test-llm-config') {
        e.stopPropagation();
        this.testLlmConfig();
      } else if (action === 'test-feishu-bot') {
        e.stopPropagation();
        this.testFeishuBot();
      } else if (action === 'run-feishu-reminders') {
        e.stopPropagation();
        this.runFeishuReminders();
      } else if (action === 'run-diagnosis') {
        e.stopPropagation();
        this.runDiagnosis(id);
      } else if (action === 'archive-campaign') {
        e.stopPropagation();
        this.archiveCampaign(id);
      } else if (action === 'test-all-config') {
        e.stopPropagation();
        this.testAllConfig();
      }
    });
  },

  async runDiagnosis(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/diagnosis`, { method: 'POST' });
    if (!r.ok) { alert(r.error || '诊断失败'); return; }
    alert(r.diagnosis?.one_line_verdict || '已生成根因分析');
    this.render();
  },

  async archiveCampaign(campaignId) {
    const r = await this.fetch(`/api/v2/activities/${this.encId(campaignId)}/archive`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        human_conclusion: document.getElementById('ar6-human')?.value || '',
        experience: document.getElementById('ar6-exp')?.value || '',
        pitfalls: document.getElementById('ar6-pit')?.value || '',
      }),
    });
    if (!r.ok) { alert(r.error || '归档失败（需填写人工结论）'); return; }
    alert('已归档。主文档（含诊断与结论）进入案例库，下次评审可参考。');
    this.render();
  },

  async completeTodo(id) {
    await this.fetch(`/api/v2/todos/${id}/complete`, { method: 'POST' });
    this.render();
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
