'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const U = require('../graph-utils.js');
const DAY = '2026-11-16';
function item(group, suffix='1000') {
  const ids = {both:['ETF:009816','TW50'],tw50_only:['TW50'],etf_009816_only:['ETF:009816']}[group];
  return {label:suffix+' 示例',stock_id:'TW:'+suffix,ticker:suffix,path:'data/stocks/'+suffix+'/graph.json',
    ...(ids ? {universe_ids:ids,universe_group:group,universe_as_of:DAY} : {})};
}
const stocks=[item('tw50_only','1000'),item('etf_009816_only','1001'),item('both','1002'),item('unknown','1003')];

test('legacy remains unknown, not inferred from stock ticker',()=>assert.equal(U.groupOf({stock_id:'TW:2330'}),'unknown'));
test('membership types remain distinct',()=>assert.deepEqual(stocks.map(U.groupOf),['tw50_only','etf_009816_only','both','unknown']));
test('partial metadata rejected',()=>assert.throws(()=>U.groupOf({universe_group:'both'})));
test('contradictory group rejected',()=>assert.throws(()=>U.groupOf({...item('both'),universe_group:'tw50_only'})));
test('duplicate source IDs rejected',()=>assert.throws(()=>U.groupOf({...item('both'),universe_ids:['TW50','TW50']})));
test('invalid calendar day rejected',()=>assert.throws(()=>U.groupOf({...item('both'),universe_as_of:'2026-02-30'})));
test('inclusive filters count overlap once',()=>{
  assert.equal(U.select(stocks,'tw50').length,2);assert.equal(U.select(stocks,'etf_009816').length,2);
  assert.equal(U.select(stocks,'both').length,1);assert.equal(U.select(stocks,'all').length,4);
  assert.equal(U.select(stocks,'unknown').length,1);
});
test('search combines with group filter',()=>{
  assert.equal(U.select(stocks,'tw50',' 1002 ').length,1);
  assert.equal(U.select(stocks,'tw50','1001').length,0);
  assert.equal(U.select(stocks,'all','示例').length,4);
});
test('unknown mode rejected',()=>assert.throws(()=>U.select(stocks,'other')));
test('counts distinguish union and unknown',()=>assert.deepEqual(U.counts(stocks),{
  all:4,tw50:2,etf_009816:2,both:1,tw50_only:1,etf_009816_only:1,unknown:1
}));
test('safe paths only',()=>{
  assert.equal(U.graphPath(stocks[0].path),stocks[0].path);
  for(const p of ['../private.json','https://example.org/a','/data/stocks/1/graph.json','data/stocks/../graph.json','data/stocks/%2e%2e/graph.json','data/stocks/1/graph.json?x=1']) assert.throws(()=>U.graphPath(p));
});
test('source links reject credentials and executable schemes',()=>{
  assert.equal(U.externalURL('https://example.org/source'),'https://example.org/source');
  for(const value of ['javascript:alert(1)','data:text/html,hi','https://u:p@example.org','//example.org','https://a.example/b c',{},null]) assert.equal(U.externalURL(value),null);
});
test('empty manifest is valid UI empty state',()=>assert.deepEqual(U.manifest({stocks:[]}),{stocks:[]}));
test('duplicate manifest path rejected',()=>assert.throws(()=>U.manifest({stocks:[stocks[0],stocks[0]]})));
test('unsafe manifest checksum rejected',()=>assert.throws(()=>U.manifest({stocks:[{...stocks[0],sha256:'invalid'}]})));
test('graph rejects node-edge ID collision and bad scores',()=>{
  const graph={nodes:[{id:'a'},{id:'b'}],edges:[{id:'e',source:'a',target:'b',relation:'contains',score:.8}]};
  assert.equal(U.graph(graph),graph);
  for(const delta of [{id:'a'},{target:'missing'},{score:NaN},{score:true},{score:1.1},{target:'a'}]) assert.throws(()=>U.graph({...graph,edges:[{...graph.edges[0],...delta}]}));
});
test('manifest/graph membership must agree',()=>{
  const stock=item('both');
  const graph={stock_id:stock.stock_id,nodes:[{id:'stock:'+stock.stock_id,...stock}],edges:[]};
  assert.equal(U.graph(graph,stock),graph);
  assert.throws(()=>U.graph({...graph,stock_id:'TW:9999'},stock));
  assert.throws(()=>U.graph({...graph,nodes:[{id:'stock:'+stock.stock_id,...stock,universe_as_of:'2026-11-15'}]},stock));
});
test('SHA256 verifies exact bytes, rejects mixed release',async()=>{
  const bytes=new TextEncoder().encode('{"test":1}');
  const sha=createHash('sha256').update(bytes).digest('hex');
  await U.verifyBytes(bytes,sha);
  await assert.rejects(()=>U.verifyBytes(new TextEncoder().encode('{"test":2}'),sha));
});

test('related stock membership must also be valid before rendering', () => {
  const malformed = {nodes:[{id:'a',type:'stock',universe_group:'both'}],edges:[]};
  assert.throws(() => U.graph(malformed), /歸屬資料不完整/);
});
