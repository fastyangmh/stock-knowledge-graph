/* Pure display logic shared by the browser and Node's built-in test runner. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StockGraph = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const GROUPS = Object.freeze({both: '兩者皆有', tw50_only: '僅臺灣50',
    etf_009816_only: '僅009816', unknown: '未標示'});
  const MODES = Object.freeze({all: '全部股票', tw50: '臺灣50（含重疊）',
    etf_009816: '009816（含重疊）', both: '兩者皆有',
    tw50_only: '僅臺灣50', etf_009816_only: '僅009816', unknown: '未標示'});
  const RELATIONS = Object.freeze({semantic_similarity: '語意相似', lexical_similarity: '字元相似（測試基準）',
    industry: '產業關聯', contains: '資訊關聯', has_market_price: '盤後行情', has_financial_metric: '財務數值'});
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function day(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(value + 'T00:00:00Z');
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  }
  function groupOf(item) {
    if (!['universe_ids','universe_group','universe_as_of'].some(k => Object.hasOwn(item, k))) return 'unknown';
    const ids = item.universe_ids;
    if (!Array.isArray(ids) || ids.length < 1 || ids.length > 2 || new Set(ids).size !== ids.length ||
        ids.some(x => x !== 'TW50' && x !== 'ETF:009816') || !day(item.universe_as_of)) {
      throw new Error('股票池歸屬資料不完整');
    }
    const group = ids.length === 2 ? 'both' : (ids[0] === 'TW50' ? 'tw50_only' : 'etf_009816_only');
    if (item.universe_group !== group) throw new Error('股票池歸屬與來源不一致');
    return group;
  }
  function graphPath(value) {
    if (typeof value !== 'string' || !/^data\/stocks\/[A-Za-z0-9][A-Za-z0-9_.-]*\/graph\.json$/.test(value)) {
      throw new Error('圖譜路徑無效');
    }
    return value;
  }
  function externalURL(value) {
    if (typeof value !== 'string' || /\s/.test(value) || !/^https:\/\//i.test(value)) return null;
    try { const url = new URL(value); return url.username || url.password ? null : url.href; }
    catch (_) { return null; }
  }
  function manifest(value) {
    if (!object(value) || !Array.isArray(value.stocks)) throw new Error('股票索引格式錯誤');
    const paths = new Set(), ids = new Set();
    for (const stock of value.stocks) {
      if (!object(stock) || typeof stock.label !== 'string' || !stock.label.trim()) throw new Error('股票名稱缺漏');
      const path = graphPath(stock.path);
      if (paths.has(path)) throw new Error('股票索引路徑重複'); paths.add(path);
      if (stock.stock_id !== undefined) {
        if (typeof stock.stock_id !== 'string' || !stock.stock_id || ids.has(stock.stock_id)) throw new Error('股票代碼無效或重複');
        ids.add(stock.stock_id);
      }
      groupOf(stock);
      if (stock.sha256 !== undefined && !/^[0-9a-f]{64}$/.test(stock.sha256)) throw new Error('圖譜校驗碼格式錯誤');
    }
    return value;
  }
  function counts(stocks) {
    const result = {all: stocks.length, tw50: 0, etf_009816: 0, both: 0, tw50_only: 0, etf_009816_only: 0, unknown: 0};
    for (const stock of stocks) {
      const group = groupOf(stock); result[group] += 1;
      if (group === 'both' || group === 'tw50_only') result.tw50 += 1;
      if (group === 'both' || group === 'etf_009816_only') result.etf_009816 += 1;
    }
    return result;
  }
  function select(stocks, mode, query = '') {
    if (!Object.hasOwn(MODES, mode)) throw new Error('未知的股票池篩選');
    const text = String(query).trim().toLocaleLowerCase();
    return stocks.filter(stock => {
      const group = groupOf(stock);
      const matches = mode === 'all' || mode === group ||
        (mode === 'tw50' && ['tw50_only','both'].includes(group)) ||
        (mode === 'etf_009816' && ['etf_009816_only','both'].includes(group));
      return matches && [stock.label, stock.stock_id || '', stock.ticker || ''].join(' ').toLocaleLowerCase().includes(text);
    });
  }
  function graph(value, entry) {
    if (!object(value) || !Array.isArray(value.nodes) || !Array.isArray(value.edges)) throw new Error('圖譜格式錯誤');
    const ids = new Set();
    for (const node of value.nodes) {
      if (!object(node) || typeof node.id !== 'string' || !node.id || ids.has(node.id)) throw new Error('節點識別碼無效或重複');
      if (node.type === 'stock') groupOf(node);
      ids.add(node.id);
    }
    const nodeIDs = new Set(ids);
    for (const edge of value.edges) {
      if (!object(edge) || !['id','source','target','relation'].every(k => typeof edge[k] === 'string' && edge[k]) ||
          ids.has(edge.id) || edge.source === edge.target || !nodeIDs.has(edge.source) || !nodeIDs.has(edge.target)) {
        throw new Error('關聯識別碼或端點無效');
      }
      if (edge.score != null && (typeof edge.score !== 'number' || !Number.isFinite(edge.score) || edge.score < -1 || edge.score > 1)) {
        throw new Error('關聯分數必須介於 -1 與 1');
      }
      ids.add(edge.id);
    }
    if (entry) {
      if (entry.stock_id !== undefined && entry.stock_id !== value.stock_id) throw new Error('索引與圖譜股票不一致');
      if (groupOf(entry) !== 'unknown') {
        const primary = value.nodes.find(n => n.id === 'stock:' + value.stock_id);
        if (!primary || groupOf(primary) !== groupOf(entry) || primary.universe_as_of !== entry.universe_as_of) {
          throw new Error('索引與圖譜歸屬不一致');
        }
      }
    }
    if (value.research_alerts !== undefined) alerts(value.research_alerts, value.stock_id);
    return value;
  }
  const ALERT_RULES = Object.freeze({price_change:'price_volume', volume_ratio:'price_volume',
    revenue_yoy:'monthly_revenue', revenue_mom:'monthly_revenue',
    revenue_yoy_change:'monthly_revenue', revenue_yoy_trend:'monthly_revenue'});
  const ALERT_STATUS = Object.freeze({triggered:'達到研究門檻',not_triggered:'已評估，未達門檻',
    insufficient_data:'資料不足，無法評估',not_comparable:'資料不可比較'});
  function alerts(value, stockID) {
    if (!object(value) || value.schema_version !== 'research-alerts-1.0' || value.stock_id !== stockID ||
        !object(value.config) || !object(value.categories) || !Array.isArray(value.warnings) ||
        typeof value.known_at !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value.known_at) ||
        !Number.isFinite(Date.parse(value.known_at))) throw new Error('研究提醒格式或股票不一致');
    const categories = Object.keys(value.categories).sort();
    if (categories.join(',') !== 'monthly_revenue,price_volume') throw new Error('研究提醒類別不完整');
    const seen = new Set();
    for (const category of categories) {
      const list = value.categories[category];
      if (!Array.isArray(list) || list.length > 6) throw new Error('研究規則數量錯誤');
      for (const check of list) {
        if (!object(check) || !Object.hasOwn(ALERT_RULES,check.rule_id) || seen.has(check.rule_id) ||
            ALERT_RULES[check.rule_id] !== category || check.category !== category ||
            !Object.hasOwn(ALERT_STATUS,check.status) || !/^[0-9a-f]{64}$/.test(check.id) ||
            !['title','reason','formula','unit'].every(k=>typeof check[k]==='string') ||
            !object(check.baseline) || !Array.isArray(check.evidence) || check.evidence.length > 253 ||
            typeof check.threshold !== 'number' || !Number.isFinite(check.threshold) || check.threshold <= 0) {
          throw new Error('研究規則欄位錯誤');
        }
        seen.add(check.rule_id);
        if (check.value !== null && (typeof check.value !== 'string' || !/^-?\d+(?:\.\d+)?$/.test(check.value) ||
            !Number.isFinite(Number(check.value)))) throw new Error('研究觀察值無效');
        if (['triggered','not_triggered'].includes(check.status) && check.value === null) throw new Error('已評估規則缺數值');
        if (check.target_period !== null && !day(check.target_period)) throw new Error('研究期別無效');
        for (const evidence of check.evidence) {
          if (!object(evidence)) throw new Error('研究證據無效');
          for (const key of ['observed_at','available_at','registered_at']) {
            if (evidence[key] != null && (typeof evidence[key] !== 'string' ||
                !Number.isFinite(Date.parse(evidence[key])) || Date.parse(evidence[key]) > Date.parse(value.known_at))) {
              throw new Error('研究證據超過可得時間');
            }
          }
        }
      }
    }
    if (seen.size !== 6) throw new Error('研究提醒規則不完整');
    return value;
  }
  async function verifyBytes(bytes, expected) {
    if (!expected) return;
    if (!globalThis.crypto || !globalThis.crypto.subtle) throw new Error('請使用 HTTPS 或 localhost 以驗證圖譜完整性');
    const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
    const actual = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
    if (actual !== expected) throw new Error('圖譜與索引版本不一致，請重新載入');
  }
  return Object.freeze({GROUPS, MODES, RELATIONS, groupOf, graphPath, externalURL, manifest, counts, select, graph, verifyBytes, alerts, ALERT_STATUS});
});
