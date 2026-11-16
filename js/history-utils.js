/* Pure validation/navigation for the read-only private research archive. */
(function(root,factory) {
  const api=factory(); if(typeof module==='object' && module.exports)module.exports=api; else root.ResearchHistory=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const RUN=/^[0-9a-f]{32}$/;
  const TRANSITIONS={activated:'本次新達門檻',no_longer_triggered:'本次未再達門檻（非風險解除）',
    still_triggered:'仍達門檻',still_not_triggered:'仍未達門檻',became_unavailable:'本次資料不足／不可比較',
    became_evaluable:'首次可評估（不是新訊號）',still_unavailable:'兩次均無法完整評估',
    definition_changed:'設定或來源改變，不直接比較',definition_unknown:'舊版缺少比較基準，無法判斷',not_computed:'至少一版尚未計算提醒',
    added_coverage:'新增研究股票（非新訊號）',removed_coverage:'移出研究股票（非風險解除）'};
  const require=(ok,message)=>{if(!ok)throw new Error(message);};
  function runID(value){require(typeof value==='string' && RUN.test(value),'版本識別碼錯誤');return value;}
  function viewLink(id){return 'index.html?run='+runID(id);}
  function comparePath(a,b){return 'api/compare?before='+runID(a)+'&after='+runID(b);}
  function validateCatalog(value){
    require(value && value.schema_version==='research-catalog-1.0' && Array.isArray(value.runs),'研究歷史索引格式錯誤');
    const seen=new Set();
    for(const row of value.runs){
      runID(row.run);require(!seen.has(row.run),'重複版本');seen.add(row.run);
      require(['valid','invalid'].includes(row.status),'版本狀態錯誤');
      if(row.status==='valid'){
        require(typeof row.known_at==='string' && Number.isFinite(Date.parse(row.known_at)),'版本時間錯誤');
        require(Array.isArray(row.stock_ids) && row.stock_ids.every(x=>/^TW:[0-9]{4}$/.test(x)),'股票清單錯誤');
        require(row.counts && Number.isInteger(row.counts.graphs) && row.counts.graphs===row.stock_ids.length,'版本數量錯誤');
        require(Array.isArray(row.warnings) && row.warnings.every(x=>typeof x==='string'),'品質警告錯誤');
      }
    }
    require(value.latest===null || seen.has(value.latest),'最新版本指標不在清單內');
    return value;
  }
  function validateComparison(value,a,b){
    require(value && value.schema_version==='research-comparison-1.0' && value.combined_score===false,'比較格式錯誤');
    require(value.before?.run===runID(a) && value.after?.run===runID(b),'回應與選取版本不符');
    require(Array.isArray(value.stocks),'缺少股票比較');
    const seen=new Set();
    for(const stock of value.stocks){
      require(/^TW:[0-9]{4}$/.test(stock.stock_id) && !seen.has(stock.stock_id),'股票識別錯誤');seen.add(stock.stock_id);
      for(const category of ['price_volume','monthly_revenue']){
        require(Array.isArray(stock.categories?.[category]),'缺少獨立研究類別');
        for(const row of stock.categories[category])require(Object.hasOwn(TRANSITIONS,row.transition) && row.category===category,'未知提醒轉變');
      }
    }
    return value;
  }
  return {runID,viewLink,comparePath,validateCatalog,validateComparison,TRANSITIONS};
});
