"""Optional browser acceptance checks; requires Playwright and local Chromium.

No market downloads or Git operations. Uses a supplied Cytoscape UMD asset.
--in-memory runs DOM/render tests on about:blank with synthetic fetch responses,
without navigating to any host; HTTP server tests live in local/tests/test_preview.
In-memory mode omits optional manifest SHA fields because about:blank has no
secure-context WebCrypto. Real SHA verification is tested separately by Node.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import platform
from datetime import datetime, timezone
import re
import shutil
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local.core import ROOT, connect, init_db, import_payload, upsert_node, upsert_edge
from local.export_json import export
from local.preview import make_server, snapshot
from local.similarity import compute
from local.alerts import evaluate


def props(ids):
    return {"universe_ids":ids,"universe_as_of":"2026-11-16",
        "universe_group":"both" if len(ids)==2 else "tw50_only" if ids==["TW50"] else "etf_009816_only",
        "universe_memberships":[{"universe_id":u,"membership_kind":"index_constituent" if u=="TW50" else "etf_holding",
            "source_url":"https://example.org/synthetic-membership","effective_from":"2026-11-16","effective_to":"2026-11-16",
            **({"snapshot_date":"2026-11-16"} if u!="TW50" else {})} for u in ids]}


def fixture(root):
    stocks=[];documents=[]
    for i,ids in enumerate((["TW50"],["ETF:009816"],["ETF:009816","TW50"],[])):
        sid=f"TW:{1000+i}"
        stocks.append({"stock_id":sid,"ticker":str(1000+i),"market":"TW","name":f"Synthetic {i}",**(props(ids) if ids else {})})
        documents.append({"document_id":f"synthetic:{i}","doc_type":"news","title":f"Synthetic news {i}",
            "content":"synthetic common report <img src=x onerror=window.injected=1>","source_id":"fixture",
            "published_at":"2026-11-15T00:00:00+08:00","stock_ids":[sid],"attribution":"Synthetic attribution — test only",
            "source_url":"https://example.org/dataset","license_url":"https://example.org/terms"})
    with connect(root/'test.db') as conn:
        init_db(conn);import_payload(conn,{"stocks":stocks,"documents":documents,
            "sources":[{"source_id":"fixture","provider":"Synthetic provider","url":"https://example.org/dataset","license_type":"test only"}]})
        upsert_node(conn, "price:synthetic", "market_price", "Synthetic price 1002", stock_id="TW:1002",
                    props={"close":"11.00","volume_shares":1000,"trade_date":"2026-11-15",
                           "source_id":"fixture","price_unit":"source_reported","raw_snapshot_verified":False})
        upsert_edge(conn, "stock:TW:1002", "price:synthetic", "has_market_price", "synthetic_fixture")
        metrics=[{"stock_id":"TW:1002","source_id":"fixture","metric":"monthly_revenue_yoy_pct",
            "period_type":"month","period_end":"2026-10-31","value":40,"unit":"percent",
            "available_at":"2026-11-15T00:00:00Z"}]
        alerts=evaluate({"financial_metrics":metrics,"sources":[{"source_id":"fixture","url":"https://example.org/dataset"}]},
                        {}, {s['stock_id'] for s in stocks}, "2026-11-16T00:00:00+08:00")
        compute(conn,threshold=0);export(conn,root/'preview',lifecycle=True,research_alerts=alerts)


async def load_page(browser, data, js, in_memory, errors, saved_run=None):
    context=await browser.new_context(viewport={'width':1280,'height':900})
    page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
    server=thread=None
    if in_memory:
        if saved_run is not None:
            from urllib.parse import urlencode
            await page.goto('about:blank?'+urlencode({'run':saved_run}))
        files=snapshot(data)
        manifest=json.loads(files['/data/manifest.json'][0])
        for item in manifest['stocks']:item.pop('sha256',None)
        fixture_files={path:body.decode() for path,(body,mime) in files.items() if path.startswith('/data/')}
        fixture_files['/data/manifest.json']=json.dumps(manifest)
        if saved_run is not None:
            fixture_files={'/versions/'+saved_run+path:body for path,body in fixture_files.items()}
        html=re.sub(r'<script\b[^>]*>.*?</script>','',files['/index.html'][0].decode(),flags=re.S)
        html=re.sub(r'<link\b[^>]*>','',html)
        html=html.replace('<head>','<head><base href="https://example.invalid/stock-knowledge-graph/">')
        await context.route('**/*',lambda route:route.abort())
        await page.set_content(html)
        await page.add_style_tag(content=(ROOT/'css/style.css').read_text())
        await page.evaluate('''files => {
            window.__fixtureFiles=files; window.__fixtureDelay={}; window.__fixtureRequests=[];
            window.fetch=async url => {
              const path=new URL(url,document.baseURI).pathname.replace('/stock-knowledge-graph','');
              window.__fixtureRequests.push(path);
              const body=window.__fixtureFiles[path];
              await new Promise(resolve=>setTimeout(resolve,window.__fixtureDelay[path]||0));
              return new Response(body||'Not found',{status:body===undefined?404:200,headers:{'Content-Type':'application/json'}});
            };
        }''',fixture_files)
        await page.add_script_tag(content=js)
        await page.evaluate("""() => {
          const original=window.cytoscape;
          function capture(options) { const cy=original(options); window.__testCy=cy; return cy; }
          Object.assign(capture,original); window.cytoscape=capture;
        }""")
        await page.add_script_tag(content=(ROOT/'js/graph-utils.js').read_text())
        await page.add_script_tag(content=(ROOT/'js/app.js').read_text())
    else:
        server=make_server(data,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        async def routing(route):
            if route.request.url.startswith('https://unpkg.com/cytoscape@3.30.4/'):
                await route.fulfill(status=200,content_type='text/javascript',body=js)
            elif route.request.url.startswith(f'http://127.0.0.1:{server.server_port}/'):await route.continue_()
            else:await route.abort()
        await context.route('**/*',routing)
        await page.goto(f'http://127.0.0.1:{server.server_port}/')
    async def cleanup():
        await context.close()
        if server:server.shutdown();server.server_close();thread.join(timeout=2)
    return page,cleanup


async def run(args):
    from playwright.async_api import async_playwright, Error
    args.report.parent.mkdir(parents=True,exist_ok=True)
    report={"scope":"Synthetic DOM/render fixtures; no live models, official API or remote deployment", "checks":[],
            "transport":"in-memory fetch; no navigation" if args.in_memory else "loopback HTTP",
            "browser_checksum_verified":not args.in_memory}
    js=args.cytoscape_js.read_text(encoding='utf-8')
    report['cytoscape_asset_sha256']=hashlib.sha256(js.encode()).hexdigest()
    if args.esm_symbol:
        if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*',args.esm_symbol):raise ValueError('Invalid ESM symbol')
        js,n=re.subn(r'export\s*\{[^}]+\};?\s*$',f'globalThis.cytoscape={args.esm_symbol};',js)
        if n!=1:raise ValueError('Expected one terminal ESM export')
    report.update(python=sys.version,platform=platform.platform(),started_at=datetime.now(timezone.utc).isoformat(),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ("index.html","css/style.css","js/app.js","js/graph-utils.js","scripts/browser_smoke.py")})
    errors=[]
    with tempfile.TemporaryDirectory(prefix='stock-browser-') as d:
        root=Path(d);fixture(root);shutil.copytree(ROOT/'data',root/'legacy')
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=str(args.chromium),headless=True,args=['--no-sandbox'])
            page,cleanup=await load_page(browser,root/'preview',js,args.in_memory,errors)
            try:
                await page.wait_for_function("document.querySelector('#status').textContent.includes('節點')")
                report['cytoscape_version']=await page.evaluate('cytoscape.version')
                assert await page.locator('#cy canvas').count()>0
                assert await page.locator('#stock option').count()==4
                if args.in_memory:
                    assert await page.evaluate("__fixtureRequests.filter(x=>x.endsWith('/graph.json')).length") == 1
                report['checks'].append('real Cytoscape canvas; initial loading fetches one graph only')
                for mode,count in [('both',1),('tw50',2),('etf_009816',2),('tw50_only',1),('etf_009816_only',1),('unknown',1)]:
                    await page.select_option('#universe',mode)
                    assert await page.locator('#stock option').count()==count
                    await page.wait_for_function("document.querySelector('#status').textContent.includes('節點')")
                report['checks'].append('all six source filters')
                await page.fill('#search','does not exist')
                assert await page.locator('#graph-layout').is_hidden()
                assert await page.locator('#stock').is_disabled()
                report['checks'].append('empty state clears previous graph')
                await page.fill('#search','');await page.select_option('#universe','all')
                await page.fill('#search','1002')
                await page.wait_for_function("document.querySelector('#status').textContent.includes('1002') && document.querySelector('#status').textContent.includes('節點')")
                assert await page.locator('#stock option').count()==1
                assert '兩者皆有' in await page.locator('#details').inner_text()
                await page.locator('#source-panel summary').click()
                assert 'Synthetic attribution' in await page.locator('#sources').inner_text()
                assert await page.locator('#sources a[href="https://example.org/terms"]').count()>0
                assert await page.locator('#sources img').count()==0
                assert not await page.evaluate('Boolean(window.injected)')
                report['checks'].append('search, dates, provenance and text-safe rendering')
                assert await page.locator('[data-alert-category="price_volume"]').count()==1
                assert await page.locator('[data-alert-category="monthly_revenue"]').count()==1
                assert await page.locator('#alerts [data-alert-status="triggered"]').count()==1
                assert '資料不足，無法評估' in await page.locator('#alerts').inner_text()
                assert '不合併評分' in await page.locator('#alerts').inner_text()
                assert await page.locator('#alerts .alert-check').count()==6
                report['checks'].append('independent price/volume and revenue cards; trigger distinguished from insufficient data')
                await page.select_option('#relation','has_market_price')
                if args.in_memory:
                    await page.evaluate("() => { __testCy.getElementById('price:synthetic').emit('tap'); }")
                    assert '收盤（來源尺度）' in await page.locator('#details').inner_text()
                    assert '11.00' in await page.locator('#details').inner_text()
                report['checks'].append('numeric market relation and price detail labels')
                await page.select_option('#relation','contains');await page.click('#fit')
                report['checks'].append('relation filter and fit view')
                await page.fill('#search','')
                async def delay(route):
                    await asyncio.sleep(.25)
                    try:await route.continue_()
                    except Error:pass
                if args.in_memory:
                    await page.evaluate("__fixtureDelay['/data/stocks/1000/graph.json']=250")
                else:await page.route('**/data/stocks/1000/graph.json',delay)
                await page.select_option('#stock','data/stocks/1000/graph.json')
                await page.select_option('#stock','data/stocks/1001/graph.json')
                await page.wait_for_function("document.querySelector('#status').textContent.includes('1001') && document.querySelector('#status').textContent.includes('節點')")
                await page.wait_for_timeout(400)
                assert '1001' in await page.locator('#status').inner_text()
                report['checks'].append('late response cannot replace newest selection')
                await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(100)
                assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                await page.screenshot(path=str(args.report.with_suffix('.png')),full_page=True)
                report['checks'].append('390px mobile layout without horizontal overflow')
                if args.in_memory:
                    await page.evaluate("__fixtureFiles['/data/stocks/1000/graph.json']='{}'; __fixtureDelay={}")
                else:
                    await page.unroute('**/data/stocks/1000/graph.json',delay)
                    await page.route('**/data/stocks/1000/graph.json',lambda route:route.fulfill(status=200,content_type='application/json',body='{}'))
                await page.select_option('#stock','data/stocks/1000/graph.json')
                await page.wait_for_function("document.querySelector('#status').classList.contains('error')")
                assert await page.locator('#graph-layout').is_hidden()
                assert await page.locator('#alerts').is_hidden()
                report['checks'].append('invalid graph hides stale visualization and exposes reload')
            finally:await cleanup()
            page,cleanup=await load_page(browser,root/'legacy',js,args.in_memory,errors)
            try:
                await page.wait_for_function("document.querySelector('#status').textContent.includes('節點')")
                assert '未標示' in await page.locator('#status').inner_text()
                assert await page.locator('#cy canvas').count()>0
                assert '尚未計算研究提醒' in await page.locator('#alerts').inner_text()
                report['checks'].append('existing public demo renders without fabricated membership')
            finally:await cleanup()
            if args.in_memory:
                page,cleanup=await load_page(browser,root/'preview',js,True,errors,saved_run='a'*32)
                try:
                    await page.wait_for_function("document.querySelector('#status').textContent.includes('節點')")
                    assert await page.evaluate("__fixtureRequests.every(path=>path.startsWith('/versions/'+'a'.repeat(32)+'/data/'))")
                    assert '已儲存研究版本' in await page.locator('header').inner_text()
                    assert await page.locator('header a[href="history.html"]').count()==1
                    report['checks'].append('selected saved run routes all graph requests to its version prefix')
                finally:await cleanup()
                page,cleanup=await load_page(browser,root/'preview',js,True,errors,saved_run='../private')
                try:
                    await page.wait_for_function("document.querySelector('#status').classList.contains('error')")
                    assert await page.evaluate('__fixtureRequests.length')==0
                    await page.click('#reload');assert await page.evaluate('__fixtureRequests.length')==0
                    report['checks'].append('invalid saved-run ID fails before data requests, including reload')
                finally:await cleanup()
            await browser.close()
    report['page_errors']=errors;report['passed']=not errors
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise AssertionError('Browser page errors')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',type=Path,required=True)
    parser.add_argument('--cytoscape-js',type=Path,required=True)
    parser.add_argument('--esm-symbol')
    parser.add_argument('--in-memory',action='store_true')
    parser.add_argument('--report',type=Path,default=ROOT/'local/private/browser-check.json')
    args=parser.parse_args()
    from local.safety import private_path
    args.report=private_path(args.report)
    asyncio.run(run(args))

if __name__=='__main__':main()
