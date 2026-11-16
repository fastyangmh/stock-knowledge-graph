/* Static-only viewer. No brokers, credentials or model calls in the browser. */
(() => {
  'use strict';
  const U = window.StockGraph;
  const $ = id => document.getElementById(id);
  const ui = Object.fromEntries(['universe','search','stock','relation','fit','reload','coverage','status','graph-layout','cy','details','sources','alerts'].map(id => [id, $(id)]));
  let manifest = null, cy = null, activePath = null, graph = null, requestID = 0, controller = null;
  const baseURL = new URL('./', document.baseURI);
  const requestedRuns = new URLSearchParams(window.location.search).getAll('run');
  const savedRun = requestedRuns.length === 1 && /^[0-9a-f]{32}$/.test(requestedRuns[0]) ? requestedRuns[0] : null;
  const invalidRun = requestedRuns.length > 0 && savedRun === null;
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = String(text);
    if (parent) parent.append(node);
    return node;
  }
  function message(text, error = false) { ui.status.textContent = text; ui.status.classList.toggle('error', error); }
  function clearGraph() {
    if (cy) { cy.destroy(); cy = null; }
    graph = null; activePath = null; ui.fit.disabled = true; ui['graph-layout'].hidden = true;
    ui.details.replaceChildren(); element('h2', '詳細資訊', ui.details);
    ui.alerts.replaceChildren(); ui.alerts.hidden = true;
  }
  function beginRequest() {
    if (controller) controller.abort();
    controller = new AbortController();
    return {id: ++requestID, signal: controller.signal};
  }
  async function fetchJSON(path, req, sha) {
    const response = await fetch(new URL((savedRun ? `versions/${savedRun}/` : '') + path, baseURL), {signal: req.signal, cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`讀取失敗（HTTP ${response.status}）`);
    const bytes = await response.arrayBuffer();
    await U.verifyBytes(bytes, sha);
    return JSON.parse(new TextDecoder().decode(bytes));
  }
  function safeLink(parent, url, label) {
    const safe = U.externalURL(url);
    if (!safe) return;
    const anchor = element('a', label, parent);
    anchor.href = safe; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; anchor.referrerPolicy = 'no-referrer';
    parent.append(document.createTextNode(' '));
  }
  function showDetails(data) {
    ui.details.replaceChildren();
    element('h2', data.label || U.RELATIONS[data.relation] || data.relation || data.id, ui.details);
    if (data.type === 'stock') {
      const group = U.groupOf(data), badge = element('span', U.GROUPS[group], ui.details); badge.className = 'badge';
    }
    const labels = {type:'類型',relation:'關係',score:'相似度（非報酬預測）',method:'計算方法',model_id:'模型識別',
      as_of:'關聯計算時間',universe_as_of:'名單觀察日期',available_at:'資訊可得時間',published_at:'來源時間',
      description:'說明',evidence_ids:'證據文件 ID',universe_memberships:'股票池來源與生效日期',attribution:'來源署名',
      source_url:'資料集來源',license_url:'授權條款',trade_date:'行情交易日期',observed_at:'來源觀察時間',
      registered_at:'本地首次登錄時間',raw_sha256:'原始 CSV SHA256',input_snapshot_sha256:'正規化快照 SHA256',
      open:'開盤（來源尺度）',high:'最高（來源尺度）',low:'最低（來源尺度）',close:'收盤（來源尺度）',
      volume_shares:'成交股數',turnover_raw:'成交金額（來源尺度）',trades:'成交筆數',price_basis:'價格基準',
      price_unit:'價格單位',turnover_unit:'金額單位',value:'來源報告數值',unit:'數值單位',metric:'指標',
      period_end:'資料期末日',period_type:'期間類型',acquisition:'取得方式',raw_snapshot_verified:'已比對原始快照'};
    const dl = element('dl', undefined, ui.details);
    for (const [key,value] of Object.entries(data)) {
      if (['id','label'].includes(key) || value === null || value === undefined) continue;
      element('dt', labels[key] || key, dl);
      const dd = element('dd', undefined, dl);
      if (key === 'source_url' || key === 'license_url') {
        if (U.externalURL(value)) safeLink(dd, value, value); else dd.textContent = '無安全的 HTTPS 連結';
      } else dd.textContent = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
    }
  }
  function showSources() {
    ui.sources.replaceChildren();
    const items = [...(Array.isArray(manifest?.sources) ? manifest.sources : [])];
    if (graph) {
      for (const node of graph.nodes) {
        if (node.source_id || node.attribution || node.source_url) items.push(node);
        for (const membership of (Array.isArray(node.universe_memberships) ? node.universe_memberships : [])) {
          items.push({provider:membership.universe_id, source_url:membership.source_url,
            attribution:`名單日期：${membership.snapshot_date || node.universe_as_of || '未標示'}；網址是溯源，不代表公開使用權利已確認。`});
        }
      }
    }
    const seen = new Set();
    for (const item of items) {
      if (!item || typeof item !== 'object') continue;
      const url = item.source_url || item.url || item.dataset_url;
      const key = JSON.stringify([item.source_id || item.provider, url, item.license_url, item.attribution]);
      if (seen.has(key)) continue; seen.add(key);
      const block = element('article', undefined, ui.sources);
      element('p', item.provider || item.source_id || '資料來源', block);
      if (item.attribution) element('p', item.attribution, block);
      if (item.license_type) element('p', `授權標記：${item.license_type}`, block);
      safeLink(block, url, '來源資料集'); safeLink(block, item.license_url, '授權條款');
    }
    if (!seen.size) element('p', '這份資料未提供來源署名。舊版示範資料不視為正式金融資料。', ui.sources);
    element('p', '來源標示不取代授權審查；ETF 持股與指數成分股是不同觀察。', ui.sources);
  }
  function showAlerts() {
    ui.alerts.replaceChildren(); ui.alerts.hidden = false;
    element('h2', '研究提醒：價量與月營收分開判讀', ui.alerts);
    const report = graph?.research_alerts;
    if (!report) {
      element('p','此圖尚未計算研究提醒；不代表沒有異常。',ui.alerts); return;
    }
    element('p',`可得時間截止：${report.known_at}。門檻為可調研究設定，尚未經投資績效校準；不合併評分，不提供買賣指令。`,ui.alerts);
    const reasons = {missing_history:'歷史觀察不足',price_input_not_requested:'未提供行情資料',
      target_price_missing_at_cutoff:'截止時間前缺少指定日行情',
      mixed_source_basis_or_unverified_snapshot:'來源、價格基準不同或原始快照未驗證',
      observation_gap_exceeds_policy:'觀察日期間隔超過設定',missing_or_nonpositive_close:'收盤價缺漏或不為正數',
      zero_volume_baseline:'歷史平均成交量為零，無法計算倍數',
      missing_consecutive_months_or_latest_percentage:'最新期百分比或連續月份不足',
      percentage_unit_or_source_mismatch:'百分比單位或來源不一致',threshold_met:'達到設定門檻',
      threshold_not_met:'未達設定門檻',increasing:'年增率連續上升',decreasing:'年增率連續下降',mixed_or_flat:'非連續同方向變化'};
    for (const [category,label] of [['price_volume','價量提醒'],['monthly_revenue','月營收提醒']]) {
      const block = element('article',undefined,ui.alerts); block.dataset.alertCategory = category;
      element('h3',label,block);
      element('p',category==='price_volume' ? '比較同來源的已觀察報價，非確認連續交易日；未還原價格可能受除權息、分割等影響。' :
        '使用來源提供的年增／月增百分比；未知金額尺度不重算成長率。連續上升不等於營收為正成長。',block);
      for (const check of report.categories[category]) {
        const card=element('div',undefined,block); card.className='alert-check'; card.dataset.alertStatus=check.status;
        element('h4',`${check.title} — ${U.ALERT_STATUS[check.status]}`,card);
        element('p',`期別：${check.target_period || '未提供'}｜觀察值：${check.value ?? '無法計算'} ${{percent:'%',ratio:'倍',percentage_points:'百分點',steps:'次'}[check.unit] || check.unit}｜門檻：${check.threshold}`,card);
        element('p',reasons[check.reason] || check.reason,card);
        const details=element('details',undefined,card); element('summary','計算方法、設定與來源證據',details);
        element('p',check.formula,details);
        element('pre',JSON.stringify({baseline:check.baseline,config:report.config},null,2),details);
        for (const evidence of check.evidence) {
          const item=element('div',undefined,details); safeLink(item,evidence.source_url,'來源');
          element('pre',JSON.stringify(evidence,null,2),item);
        }
      }
    }
  }
  function updateRelation() {
    if (!cy || !graph) return;
    const value = ui.relation.value;
    cy.edges().forEach(edge => edge.style('display', value === 'all' || edge.data('relation') === value ? 'element' : 'none'));
  }
  async function loadGraph(entry) {
    const req = beginRequest(); clearGraph(); showSources(); message(`正在載入 ${entry.label}…`);
    try {
      const data = U.graph(await fetchJSON(U.graphPath(entry.path), req, entry.sha256), entry);
      if (req.id !== requestID) return;
      if (typeof window.cytoscape !== 'function') throw new Error('Cytoscape 圖譜程式未載入；請檢查網路或 CDN 存取');
      graph = data; activePath = entry.path; ui['graph-layout'].hidden = false;
      const relations = [...new Set(data.edges.map(e => e.relation))].sort();
      const oldRelation = ui.relation.value; ui.relation.replaceChildren();
      const all = element('option', '全部關聯', ui.relation); all.value = 'all';
      for (const relation of relations) { const option = element('option', U.RELATIONS[relation] || relation, ui.relation); option.value = relation; }
      ui.relation.value = relations.includes(oldRelation) ? oldRelation : 'all';
      const original = new Map([...data.nodes, ...data.edges].map(e => [e.id,e]));
      const elements = [
        ...data.nodes.map(n => ({data:{id:n.id,label:n.label || n.id,type:n.type || 'unknown'}})),
        ...data.edges.map(e => ({data:{id:e.id,source:e.source,target:e.target,relation:e.relation}}))
      ];
      cy = window.cytoscape({container:ui.cy,elements,style:[
        {selector:'node',style:{label:'data(label)','background-color':'#3986d8',color:'#e8eef7','font-size':11,'text-valign':'bottom','text-margin-y':7,width:34,height:34}},
        {selector:'node[type="stock"]',style:{'background-color':'#19b9a6',width:54,height:54,'font-weight':'bold'}},
        {selector:'node[type="news"]',style:{'background-color':'#df9a4d'}},
        {selector:'node[type="financial"]',style:{'background-color':'#986de0'}},
        {selector:'node[type="market_price"]',style:{shape:'roundrectangle','background-color':'#3986d8'}},
        {selector:'node[type="financial_metric"]',style:{shape:'diamond','background-color':'#986de0'}},
        {selector:'edge',style:{width:2,'line-color':'#6583aa','curve-style':'bezier','target-arrow-shape':'none',label:'data(relation)','font-size':9,color:'#9db0cc','text-rotation':'autorotate'}},
        {selector:'edge[relation="contains"]',style:{'target-arrow-shape':'triangle','target-arrow-color':'#6583aa'}},
        {selector:':selected',style:{'border-width':3,'border-color':'#fff','line-color':'#fff'}}
      ],layout:{name:'cose',animate:false,padding:40}});
      cy.on('tap','node,edge',evt => showDetails(original.get(evt.target.id())));
      ui.fit.disabled = false; updateRelation();
      const primary = data.nodes.find(n => n.id === 'stock:' + data.stock_id) || data.nodes.find(n => n.type === 'stock');
      if (primary) showDetails(primary);
      showSources(); showAlerts();
      const group = U.groupOf(entry), date = entry.universe_as_of || '未標示';
      message(`${entry.label}｜${U.GROUPS[group]}｜名單日期：${date}｜節點 ${data.nodes.length} · 關係 ${data.edges.length}｜產生時間：${data.generated_at || manifest.generated_at || '未標示'}`);
    } catch (error) {
      if (req.id !== requestID || error.name === 'AbortError') return;
      clearGraph(); showSources(); message(`載入失敗：${error.message}。可按「重新載入」。`, true);
    }
  }
  function renderList(force = false) {
    if (!manifest) return;
    const previous = ui.stock.value;
    const list = U.select(manifest.stocks, ui.universe.value, ui.search.value);
    ui.stock.replaceChildren();
    for (const stock of list) {
      const option = element('option', stock.label, ui.stock); option.value = stock.path;
    }
    ui.stock.disabled = !list.length;
    if (!list.length) { beginRequest(); clearGraph(); showSources(); message('沒有符合條件的股票；請調整股票池或搜尋文字。'); return; }
    if (list.some(s => s.path === previous)) ui.stock.value = previous;
    const entry = list.find(s => s.path === ui.stock.value) || list[0];
    if (force || activePath !== entry.path) loadGraph(entry);
  }
  async function loadManifest() {
    const req = beginRequest(); clearGraph(); manifest = null; ui.stock.replaceChildren(); ui.stock.disabled = true;
    ui.coverage.textContent = ''; ui.sources.replaceChildren(); message('正在載入股票索引…');
    try {
      const result = U.manifest(await fetchJSON('data/manifest.json', req));
      if (req.id !== requestID) return;
      manifest = result;
      const counts = U.counts(result.stocks), previous = ui.universe.value; ui.universe.replaceChildren();
      for (const [value,label] of Object.entries(U.MODES)) { const option = element('option', `${label}（${counts[value]}）`, ui.universe); option.value = value; }
      ui.universe.value = Object.hasOwn(U.MODES, previous) ? previous : 'all';
      const dates = [...new Set(result.stocks.map(s => s.universe_as_of).filter(Boolean))].sort();
      ui.coverage.textContent = `已匯出主圖 ${counts.all} 檔｜臺灣50 ${counts.tw50} · 009816 ${counts.etf_009816} · 重疊 ${counts.both} · 未標示 ${counts.unknown}｜觀察日期：${dates.join('、') || '未標示'}${dates.length > 1 ? '（混合日期，不視為單一當日名單）' : ''}`;
      showSources(); renderList(true);
    } catch (error) {
      if (req.id !== requestID || error.name === 'AbortError') return;
      message(`索引載入失敗：${error.message}。可按「重新載入」。`, true);
    }
  }
  ui.stock.addEventListener('change', () => { const entry = manifest?.stocks.find(s => s.path === ui.stock.value); if (entry) loadGraph(entry); });
  ui.universe.addEventListener('change', () => renderList());
  ui.search.addEventListener('input', () => renderList());
  ui.relation.addEventListener('change', updateRelation);
  function fitView() { if (cy && !ui['graph-layout'].hidden) { cy.resize(); cy.fit(undefined,35); } }
  ui.fit.addEventListener('click', fitView);
  let resizeFrame = null;
  function resized() {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { resizeFrame = null; fitView(); });
  }
  if (typeof ResizeObserver === 'function') new ResizeObserver(resized).observe(ui.cy);
  else window.addEventListener('resize', resized);
  ui.reload.addEventListener('click', () => { if (!invalidRun) loadManifest(); });
  if (savedRun) {
    const banner = element('p', `已儲存研究版本 ${savedRun.slice(0,8)}；不是即時資料。`, document.querySelector('header'));
    const link = element('a', '返回本機研究歷史', banner); link.href = 'history.html';
  }
  if (invalidRun) message('研究版本識別碼錯誤；沒有載入任何資料。', true);
  else if (!U) message('介面程式未完整載入，請重新載入頁面。', true); else loadManifest();
})();
