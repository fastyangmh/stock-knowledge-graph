/* Static-only viewer. No brokers, credentials or model calls in the browser. */
(() => {
  'use strict';
  const U = window.StockGraph;
  const $ = id => document.getElementById(id);
  const ui = Object.fromEntries(['universe','search','stock','relation','fit','reload','coverage','status','graph-layout','cy','details','sources'].map(id => [id, $(id)]));
  let manifest = null, cy = null, activePath = null, graph = null, requestID = 0, controller = null;
  const baseURL = new URL('./', document.baseURI);
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
  }
  function beginRequest() {
    if (controller) controller.abort();
    controller = new AbortController();
    return {id: ++requestID, signal: controller.signal};
  }
  async function fetchJSON(path, req, sha) {
    const response = await fetch(new URL(path, baseURL), {signal: req.signal, cache: 'no-store', credentials: 'same-origin'});
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
      source_url:'資料集來源',license_url:'授權條款'};
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
        {selector:'edge',style:{width:2,'line-color':'#6583aa','curve-style':'bezier','target-arrow-shape':'none',label:'data(relation)','font-size':9,color:'#9db0cc','text-rotation':'autorotate'}},
        {selector:'edge[relation="contains"]',style:{'target-arrow-shape':'triangle','target-arrow-color':'#6583aa'}},
        {selector:':selected',style:{'border-width':3,'border-color':'#fff','line-color':'#fff'}}
      ],layout:{name:'cose',animate:false,padding:40}});
      cy.on('tap','node,edge',evt => showDetails(original.get(evt.target.id())));
      ui.fit.disabled = false; updateRelation();
      const primary = data.nodes.find(n => n.id === 'stock:' + data.stock_id) || data.nodes.find(n => n.type === 'stock');
      if (primary) showDetails(primary);
      showSources();
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
  ui.reload.addEventListener('click', loadManifest);
  if (!U) message('介面程式未完整載入，請重新載入頁面。', true); else loadManifest();
})();
