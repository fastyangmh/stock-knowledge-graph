"""History DOM smoke, with opt-in --live-http production server acceptance.

Default: local assets and in-memory synthetic responses, no browser networking.
Live: persisted synthetic bundles, native HTTP and original graph CDN.
Neither mode publishes data or contacts financial providers.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'local/tests'))
from history_fixtures import make_run
from local.research_archive import archive_snapshot
from local.research_compare import compare
from local.research_history import canonical
from local.safety import private_path


async def run(args):
    from playwright.async_api import async_playwright
    checks=[];errors=[]
    with tempfile.TemporaryDirectory(prefix='history-browser-') as directory:
        root=Path(directory);a=make_run(root,1,value=10);b=make_run(root,2,value=40);c=make_run(root,3,config={'revenue_yoy_pct':99})
        shutil.copytree(root/'runs'/a['run'],root/'runs'/('f'*32)) # invalid run identity; no automatic repair
        files,bundles=archive_snapshot(root/'runs')
        memory={path:body.decode('utf-8') for path,(body,_) in files.items()}
        statuses={}
        for before in (a,b,c):
            for after in (a,b,c):
                path=f"/api/compare?before={before['run']}&after={after['run']}"
                try:memory[path]=canonical(compare(bundles[before['run']],bundles[after['run']])).decode()
                except ValueError:statuses[path]=400
        # Untrusted provider/error text must be displayed literally, not as HTML.
        catalog=json.loads(memory['/research-history.json']);catalog['runs'][0].setdefault('warnings',[]).append('<img src=x onerror="window.injected=true">')
        memory['/research-history.json']=json.dumps(catalog)
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=str(args.chromium),headless=True,args=['--no-sandbox'])
            context=await browser.new_context(viewport={'width':1280,'height':900})
            await context.route('**/*',lambda route:route.abort())
            page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            html=re.sub(r'<script\b[^>]*>.*?</script>','',(ROOT/'history.html').read_text(),flags=re.S)
            html=re.sub(r'<link\b[^>]*>','',html)
            await page.set_content(html)
            await page.add_style_tag(content=(ROOT/'css/style.css').read_text())
            await page.evaluate('''([files,status])=>{
              window.__files=files;window.__statuses=status;window.__delay=0;window.__requests=[];
              window.fetch=async(raw,options={})=>{
                const url=new URL(String(raw),'https://fixture.invalid/');const path=url.pathname+url.search;
                __requests.push(path);if(path.startsWith('/api/'))await new Promise(resolve=>setTimeout(resolve,__delay));
                const code=__statuses[path]||(Object.hasOwn(__files,path)?200:404);
                return new Response(__files[path]||'{}',{status:code,headers:{'Content-Type':'application/json'}});
              };
            }''',[memory,statuses])
            await page.add_script_tag(content=(ROOT/'js/history-utils.js').read_text())
            await page.add_script_tag(content=(ROOT/'js/history.js').read_text())
            await page.wait_for_function("document.querySelector('#before-run').options.length===3")
            assert await page.locator('#run-list article').count()==4
            assert await page.locator('#run-list a').count()==3
            assert '未通過稽核' in await page.locator('#run-list').inner_text()
            checks.append('valid versions listed; corrupt version disabled, never linked')
            assert await page.locator('#run-list img').count()==0
            assert not await page.evaluate('Boolean(window.injected)')
            checks.append('untrusted warnings rendered with textContent, not HTML')
            await page.select_option('#before-run',a['run']);await page.select_option('#after-run',b['run']);await page.click('#compare-runs')
            await page.wait_for_selector('#comparison:not([hidden])')
            assert await page.locator('[data-comparison-category="price_volume"]').count()==1
            assert await page.locator('[data-comparison-category="monthly_revenue"]').count()==1
            assert await page.locator('[data-transition="activated"]').count()>0
            assert await page.locator('[data-transition="still_unavailable"]').count()==2
            checks.append('price/volume and revenue comparison independent; missing observations never called resolved')
            await page.locator('[data-comparison-category="monthly_revenue"] details summary').first.click()
            assert 'source_id' in await page.locator('#comparison').inner_text()
            checks.append('both versions retain inspectable rule thresholds and source evidence')
            await page.select_option('#before-run',b['run']);await page.select_option('#after-run',c['run']);await page.click('#compare-runs')
            await page.wait_for_selector('[data-transition="definition_changed"]')
            assert '不直接比較' in await page.locator('#comparison').inner_text()
            checks.append('changed threshold not interpreted as activation/resolution')
            await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(80)
            assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            await page.screenshot(path=str(args.report.with_suffix('.png')),full_page=True)
            checks.append('390px mobile layout without horizontal overflow')
            await page.evaluate('window.__delay=200')
            await page.select_option('#before-run',a['run']);await page.select_option('#after-run',b['run']);await page.click('#compare-runs')
            await page.select_option('#after-run',c['run'])
            await page.wait_for_timeout(250)
            assert await page.locator('#comparison').is_hidden()
            checks.append('selection change clears stale comparison and ignores late response')
            await page.evaluate('window.__delay=0')
            await page.select_option('#before-run',c['run']);await page.select_option('#after-run',a['run']);await page.click('#compare-runs')
            await page.wait_for_function("document.querySelector('#history-status').classList.contains('error')")
            assert await page.locator('#comparison').is_hidden()
            checks.append('backward knowledge cutoff rejected and prior results cleared')
            # Recover from invalid selection without restarting the page.
            await page.select_option('#before-run',a['run']);await page.select_option('#after-run',b['run']);await page.click('#compare-runs')
            await page.wait_for_selector('#comparison:not([hidden])');checks.append('valid comparison works after an error')
            await context.close();await browser.close()
    report={'passed':not errors,'checks':checks,'page_errors':errors,'scope':'synthetic saved bundles and in-memory browser fetch; no live network, return backtest or data licence approval',
            'python':sys.version,'finished_at':datetime.now(timezone.utc).isoformat(),
            'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('history.html','js/history.js','js/history-utils.js','css/style.css')}}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise AssertionError('Browser errors')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--chromium',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--live-http', action='store_true', help='Use production private HTTP servers and native browser fetch')
    args=p.parse_args();args.report=private_path(args.report)
    if args.live_http:
        from history_event_live_smoke import run_live
        asyncio.run(run_live(args, 'history'))
    else:
        asyncio.run(run(args))


if __name__=='__main__':main()
