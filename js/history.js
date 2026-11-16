/* No model/API queries. Only bounded, verified local archive JSON. */
(async()=>{
  'use strict';
  const U=window.ResearchHistory, $=id=>document.getElementById(id);
  const status=$('history-status'), list=$('run-list'), output=$('comparison'), before=$('before-run'), after=$('after-run'), button=$('compare-runs');
  let request=0, controller;
  function el(tag,text,parent){const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(parent)parent.append(node);return node;}
  function message(text,error=false){status.textContent=text;status.className=error?'status error':'status';}
  function reset(){request++;controller?.abort();output.replaceChildren();output.hidden=true;}
  async function json(path,signal){const response=await fetch(path,{cache:'no-store',signal});if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}
  function renderComparison(result){
    output.replaceChildren();output.hidden=false;
    el('h2','版本差異：價量與月營收分開判讀',output);
    el('p',`可得截止：${result.before.known_at} → ${result.after.known_at}`,output);
    el('p',`新增股票 ${result.selection.added.length}；移出股票 ${result.selection.removed.length}；共同股票 ${result.selection.shared.length}。`,output);
    el('p',`圖譜計算設定：${{same:'相同',changed:'已改變，畫面差異不一定是資料變動',unknown:'舊版未記錄，無法認定一致'}[result.graph_configuration] || '未確認'}。比較的是展示子圖，不是完整資料庫。`,output);
    for(const stock of result.stocks){
      const section=el('article',undefined,output);section.className='history-stock';el('h3',stock.stock_id,section);
      for(const [category,label] of [['price_volume','價量提醒變化'],['monthly_revenue','月營收提醒變化']]){
        const panel=el('section',undefined,section);panel.dataset.comparisonCategory=category;el('h4',label,panel);
        for(const row of stock.categories[category]){
          const card=el('div',undefined,panel);card.className='alert-check';card.dataset.transition=row.transition;
          el('p',`${row.title}：${U.TRANSITIONS[row.transition]}`,card);
          el('p',`觀察值 ${row.before?.value ?? '無法評估'} → ${row.after?.value ?? '無法評估'}；期別 ${row.before?.target_period || '未提供'} → ${row.after?.target_period || '未提供'}`,card);
          const details=el('details',undefined,card);el('summary','兩個版本的規則與來源證據',details);
          el('pre',JSON.stringify({reason:row.reason,changed_fields:row.changed_fields,before:row.before,after:row.after},null,2),details);
        }
      }
      const graph=el('details',undefined,section);el('summary','展示圖譜的節點／連線變化',graph);el('pre',JSON.stringify(stock.graph,null,2),graph);
    }
    const quality=el('details',undefined,output);el('summary','資料品質警告變化',quality);el('pre',JSON.stringify(result.quality_warnings,null,2),quality);
    el('p','未達門檻不代表風險消失；缺漏、移出股票、設定變更不算提醒解除。此頁不計算績效或合併評分。',output);
  }
  async function compare(){
    reset();const id=request;controller=new AbortController();
    const a=before.value,b=after.value;message('正在比較已驗證的本機版本…');
    try{const result=U.validateComparison(await json(U.comparePath(a,b),controller.signal),a,b);
      if(id!==request)return;renderComparison(result);message('比較完成；這是觀察狀態變化，不是投資績效。');
    }catch(error){if(id!==request || error.name==='AbortError')return;output.hidden=true;message(`無法比較：${error.message}。請確認前版可得截止不晚於後版，且兩版都通過驗證。`,true);}
  }
  before.addEventListener('change',reset);after.addEventListener('change',reset);button.addEventListener('click',compare);
  try{
    const catalog=U.validateCatalog(await json('research-history.json'));
    const valid=catalog.runs.filter(r=>r.status==='valid').sort((a,b)=>Date.parse(a.known_at)-Date.parse(b.known_at)||a.run.localeCompare(b.run));
    el('p',`有效版本 ${valid.length}，未通過 ${catalog.runs.length-valid.length}；暫存殘留 ${catalog.counts.staging_residues}。未自動刪除任何檔案。`,$('history-overview'));
    if(!catalog.latest_valid)el('p','最新指標缺失或無效；不要將其他版本誤認為最新。',$('history-overview'));
    for(const row of [...catalog.runs].reverse()){
      const item=el('article',undefined,list);item.className='history-run';item.dataset.run=row.run;el('h2',row.run.slice(0,8),item);
      if(row.status!=='valid'){el('p',`未通過稽核：${row.error}。不可查看或比較。`,item);continue;}
      el('p',`可得截止 ${row.known_at}｜產生 ${row.completed_at}｜${row.counts.graphs} 個股票圖譜`,item);
      const link=el('a','查看此版本圖譜',item);link.href=U.viewLink(row.run);
      el('p',`提醒：${row.alerts_enabled?'已計算，兩類各自呈現':'尚未計算'}；內部雜湊核對通過（非簽章）。`,item);
      const detail=el('details',undefined,item);el('summary',`資料品質警告（${row.warnings.length}）`,detail);el('pre',row.warnings.join('\n')||'未記錄警告；不代表官方資料已認證。',detail);
    }
    for(const select of [before,after]){for(const row of valid){const option=el('option',`${row.known_at} · ${row.run.slice(0,8)}`,select);option.value=row.run;}select.disabled=!valid.length;}
    if(valid.length){before.value=valid[Math.max(0,valid.length-2)].run;after.value=valid[valid.length-1].run;}
    button.disabled=valid.length<2;message(valid.length<2?'至少需要兩個完整版本才能比較；現有版本仍可查看。':'選擇兩個已儲存的版本，比較資料與提醒的變化。');
  }catch(error){reset();message(`未能載入本地研究歷史：${error.message}。請使用 local.research_archive 啟動；公開網站不會提供你的私有版本。`,true);}
})();
