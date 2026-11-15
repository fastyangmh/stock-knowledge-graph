/* Static viewer: all similarity calculations happen offline. */
(async () => {
  const stockSelect=document.querySelector('#stock'), relationSelect=document.querySelector('#relation');
  const details=document.querySelector('#details'), status=document.querySelector('#status');
  const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  try {
    const manifest=await (await fetch('./data/manifest.json')).json();
    manifest.stocks.forEach(s=>{const o=document.createElement('option');o.value=s.path;o.textContent=s.label;stockSelect.append(o)});
    let cy;
    async function load(){
      const graph=await (await fetch('./'+stockSelect.value)).json();
      const elements=[
        ...graph.nodes.map(n=>({data:{...n}})),
        ...graph.edges.map((e,i)=>({data:{id:e.id||'edge-'+i,...e}}))
      ];
      if(cy)cy.destroy();
      cy=cytoscape({container:document.querySelector('#cy'),elements,
        style:[
          {selector:'node',style:{'label':'data(label)','background-color':'#3986d8','color':'#e8eef7','font-size':11,'text-valign':'bottom','text-margin-y':7,'width':34,'height':34}},
          {selector:'node[type="stock"]',style:{'background-color':'#19b9a6','width':54,'height':54,'font-weight':'bold'}},
          {selector:'node[type="news"]',style:{'background-color':'#df9a4d'}},
          {selector:'node[type="financial"]',style:{'background-color':'#986de0'}},
          {selector:'edge',style:{'width':2,'line-color':'#6583aa','curve-style':'bezier','target-arrow-shape':'triangle','target-arrow-color':'#6583aa','label':'data(relation)','font-size':9,'color':'#9db0cc','text-rotation':'autorotate'}},
          {selector:':selected',style:{'border-width':3,'border-color':'#fff','line-color':'#fff'}}
        ],layout:{name:'cose',animate:false,padding:40}});
      cy.on('tap','node,edge',evt=>{const d=evt.target.data();details.innerHTML='<h2>'+escapeHtml(d.label||d.relation||d.id)+'</h2><dl>'+Object.entries(d).filter(([k])=>k!=='id').map(([k,v])=>'<dt>'+escapeHtml(k)+'</dt><dd>'+escapeHtml(typeof v==='object'?JSON.stringify(v):v)+'</dd>').join('')+'</dl>'});
      filter();
      status.textContent='資料版本：'+manifest.version+' · 更新：'+manifest.generated_at+' · 節點 '+graph.nodes.length+' · 關係 '+graph.edges.length;
    }
    function filter(){if(!cy)return;const type=relationSelect.value;cy.edges().forEach(e=>e.style('display',type==='all'||e.data('relation')===type?'element':'none'))}
    stockSelect.addEventListener('change',load);relationSelect.addEventListener('change',filter);
    document.querySelector('#fit').addEventListener('click',()=>cy&&cy.fit(undefined,35));
    await load();
  }catch(err){status.textContent='載入失敗：'+err.message;console.error(err)}
})();