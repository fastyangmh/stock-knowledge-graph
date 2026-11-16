/* Private descriptive report only. No dynamic HTML, trading, score or network provider. */
(function (root) {
  'use strict';
  const categories = ['price_volume','monthly_revenue'];
  const states = ['observed','pending','insufficient_data','not_comparable'];
  const statusLabels = {observed:'已觀察',pending:'月份尚未結束',insufficient_data:'資料不足',not_comparable:'不可比較'};
  const labels = {price_volume:'價量提醒事件',monthly_revenue:'月營收提醒事件'};
  const directions = {positive:'提醒值為正',negative:'提醒值為負',zero:'提醒值為零'};
  const titles = {price_change:'收盤價變動',volume_ratio:'成交量放大',revenue_yoy:'營收年增率',
    revenue_mom:'營收月增率',revenue_yoy_change:'年增率月間變化',revenue_yoy_trend:'年增率連續變化'};
  const metrics = {close_change_pct:'收盤價變化（%）',volume_ratio:'成交股數倍數',
    revenue_change_pct:'月營收數值變化（%）',revenue_yoy_change_pp:'年增率變化（百分點）'};
  function validNumber(x) {return typeof x==='string' && x.trim()!=='' && Number.isFinite(Number(x));}
  function validate(report) {
    if (!report || report.schema_version!=='event-study-1.0' || !/^[a-f0-9]{64}$/.test(report.study_id) ||
        report.combined_score!==false || report.trade_assumptions!==false || !report.counts ||
        !Number.isInteger(report.counts.events) || report.counts.events<0 || report.counts.events>2000 ||
        !report.categories || Object.keys(report.categories).sort().join(',')!==categories.slice().sort().join(','))
      throw new Error('報告格式或研究界線不符');
    let total=0;
    const eventIds=new Set();
    for (const category of categories) {
      const group=report.categories[category];
      if (!Array.isArray(group?.events) || !Array.isArray(group?.summaries) || group.summaries.length>48000)
        throw new Error('缺少事件或分組統計');
      const localIds=new Set();
      for (const event of group.events) {
        if (event.category!==category || !Object.hasOwn(titles,event.rule_id) || !directions[event.direction] ||
            !/^[a-f0-9]{64}$/.test(event.event_id) || eventIds.has(event.event_id) || !Array.isArray(event.outcomes) ||
            event.outcomes.length>24) throw new Error('事件資料無效');
        eventIds.add(event.event_id);localIds.add(event.event_id);
        for (const row of event.outcomes) {
          if (!Object.hasOwn(metrics,row.metric) || !states.includes(row.status) ||
              (row.status==='observed' ? !validNumber(row.value) : row.value!==null) ||
              !Number.isInteger(row.horizon) || row.horizon<1) throw new Error('後續觀察狀態無效');
        }
      }
      const groupIds=new Set();
      for (const s of group.summaries) {
        if (s.category!==category || !Object.hasOwn(metrics,s.metric) || !Object.hasOwn(titles,s.rule_id) ||
            !directions[s.direction] || !/^[a-f0-9]{64}$/.test(s.group_id) || groupIds.has(s.group_id) ||
            !Number.isInteger(s.horizon) || s.horizon<1 ||
            !['quote_observations','calendar_months'].includes(s.horizon_unit) ||
            !Number.isInteger(s.n_total) || s.n_total<1 || !Number.isInteger(s.n_observed) || s.n_observed<0 ||
            !Number.isInteger(s.n_unavailable) || s.n_unavailable<0 || s.n_total!==s.n_observed+s.n_unavailable ||
            !s.status_counts || states.some(k=>!Number.isInteger(s.status_counts[k]) || s.status_counts[k]<0) ||
            states.reduce((n,k)=>n+s.status_counts[k],0)!==s.n_total || s.status_counts.observed!==s.n_observed ||
            !Array.isArray(s.events) || s.events.length!==s.n_total || new Set(s.events).size!==s.events.length ||
            s.events.some(id=>!localIds.has(id))) throw new Error('分組分母或樣本狀態不一致');
        if (s.n_observed===0 ? s.statistics!==null : !s.statistics ||
            ['mean','median','min','max'].some(k=>!validNumber(s.statistics[k])))
          throw new Error('缺少或不合法的統計數值');
        groupIds.add(s.group_id);
      }
      total+=group.events.length;
    }
    if (total!==report.counts.events) throw new Error('事件總數不一致');
    return report;
  }
  function horizonLabel(row) {return row.horizon_unit==='calendar_months' ? `後${row.horizon}個曆月` : `後第${row.horizon}筆報價觀察`;}
  const api={validate,horizonLabel,statusLabels};
  if (typeof module!=='undefined' && module.exports) {module.exports=api;return;}
  root.EventStudyUtils=api;
  const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e;};
  function details(title,value) {const d=el('details');d.append(el('summary',title),el('pre',JSON.stringify(value,null,2)));return d;}
  function render(report) {
    validate(report);
    const overview=document.querySelector('#event-overview'), results=document.querySelector('#event-results');
    overview.replaceChildren();results.replaceChildren();
    overview.append(el('p',`分析截止：${report.analysis_at} · 已保存版本 ${report.counts.included_runs} · 去重事件 ${report.counts.events} · 重複提醒未重計 ${report.counts.duplicate_period_events_suppressed}`));
    overview.append(el('p','每列依提醒定義、方向、資料來源、單位與期間分組；沒有整體績效或綜合分數。樣本可能相關，不代表市場普遍行為。','notice'));
    overview.append(details('分析設定與資料限制',{study_id:report.study_id,configuration:report.configuration,
      event_policy:report.event_policy,followup_policy:report.followup_policy,warnings:report.warnings}));
    for (const category of categories) {
      const group=report.categories[category], section=el('section');section.dataset.eventCategory=category;
      section.append(el('h2',`${labels[category]}（${group.events.length}筆）`));
      if (!group.events.length) {section.append(el('p','這些已保存版本沒有符合定義的觸發事件；不代表市場沒有異常。'));results.append(section);continue;}
      const list=el('div'), more=el('button','顯示下一批分組');more.type='button';let shown=0;
      function appendGroups() {
        for (const s of group.summaries.slice(shown,shown+25)) {
          const card=el('article');card.dataset.studyGroup=s.group_id;
          card.append(el('h3',`${titles[s.rule_id]} · ${directions[s.direction]} · ${metrics[s.metric]} · ${horizonLabel(s)}`));
          card.append(el('p',`事件分母 ${s.n_total}｜可計算 ${s.n_observed}｜尚無可比結果 ${s.n_unavailable}`));
          card.append(el('p',states.map(k=>`${statusLabels[k]} ${s.status_counts[k]}`).join(' · ')));
          card.append(el('p',s.statistics ? `平均 ${s.statistics.mean} · 中位數 ${s.statistics.median} · 最小 ${s.statistics.min} · 最大 ${s.statistics.max}` : '無可計算樣本；不顯示零平均。'));
          card.append(details('分組定義與樣本證據',{definition_id:s.definition_id,basis:s.basis,event_ids:s.events,sample_warning:s.sample_warning}));list.append(card);
        }
        shown+=25;more.hidden=shown>=group.summaries.length;
      }
      more.addEventListener('click',appendGroups);appendGroups();section.append(list,more);
      const label=el('label','查看單一事件及後續證據 '), select=el('select'), evidence=el('div');
      select.setAttribute('aria-label',`${labels[category]}單一事件`);
      for (const event of group.events) {const option=el('option',`${event.stock_id} · ${titles[event.rule_id]} · ${event.target_period}`);option.value=event.event_id;select.append(option);}
      function showEvent() {
        evidence.replaceChildren();const event=group.events.find(e=>e.event_id===select.value);if(!event)return;
        evidence.append(el('p',`事件首次保存：${event.event_at}；資料截止：${event.known_at}。這不是來源最初公告時間。`));
        evidence.append(details('事件基準與原始提醒', {event_id:event.event_id,trigger:event.trigger,baseline:event.baseline,run:event.run,report_sha256:event.report_sha256}));
        for (const row of event.outcomes) evidence.append(details(`${metrics[row.metric]} · ${horizonLabel(row)} · ${statusLabels[row.status]}${row.value===null?'':' · '+row.value}`,row));
      }
      select.addEventListener('change',showEvent);label.append(select);section.append(label,evidence);showEvent();results.append(section);
    }
    results.hidden=false;
  }
  async function load() {
    const status=document.querySelector('#event-status');
    try {
      const response=await fetch('./event-study.json',{cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}；請使用 local.event_study --serve 開啟本機報告`);
      const body=await response.text();if(body.length>32*1024*1024)throw new Error('報告超過大小限制');
      const report=JSON.parse(body);render(report);status.textContent='已載入描述性研究報告；沒有買賣假設。';status.classList.remove('error');
    } catch(error) {
      document.querySelector('#event-results').replaceChildren();document.querySelector('#event-results').hidden=true;
      document.querySelector('#event-overview').replaceChildren();status.textContent='無法載入：'+error.message;status.classList.add('error');
    }
  }
  load();
})(typeof window!=='undefined'?window:globalThis);
