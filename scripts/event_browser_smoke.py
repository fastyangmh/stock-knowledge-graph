"""Offline DOM verification of the actual event UI; synthetic report, no network."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'local/tests'))
from event_fixtures import bundle,revenue
from local.event_study import analyze
from local.research_history import canonical
from local.safety import private_path


async def run(args):
    from playwright.async_api import async_playwright
    result=analyze([bundle(alerts=True),bundle(2,'2020-08-16',close='115.5'),
        bundle(3,'2020-09-10',data=revenue())], '2020-12-31T23:59:59+08:00')
    # Content is untrusted even in a locally-produced report; render it literally.
    result['warnings'].append('<img src=x onerror="window.injected=true">')
    args.report.parent.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];requests=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=str(args.chromium),headless=True,args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':1280,'height':900})
        await context.route('**/*',lambda route:route.abort())
        async def page_for(report,status=200):
            page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            html=re.sub(r'<script\b[^>]*>.*?</script>','',(ROOT/'event-study.html').read_text(),flags=re.S)
            html=re.sub(r'<link\b[^>]*>','',html)
            await page.set_content(html);await page.add_style_tag(content=(ROOT/'css/style.css').read_text())
            await page.evaluate('''([body,status])=>{window.__calls=[];window.fetch=async(path)=>{
              __calls.push(String(path));return new Response(body,{status,headers:{'Content-Type':'application/json'}});};}''',
              [canonical(report).decode(),status])
            await page.add_script_tag(content=(ROOT/'js/event-study.js').read_text())
            await page.wait_for_function("!document.querySelector('#event-status').textContent.startsWith('讀取')")
            return page
        page=await page_for(result)
        assert await page.locator('[data-event-category]').count()==2
        assert '價量提醒事件（2筆）' in await page.locator('#event-results').inner_text()
        assert '月營收提醒事件（4筆）' in await page.locator('#event-results').inner_text()
        checks.append('two independent event categories and explicit event counts')
        content=await page.locator('#event-results').inner_text()
        assert '可計算' in content and '資料不足' in content and '無可計算樣本' in content
        checks.append('usable/unavailable denominators visible, no zero average for missing samples')
        assert '後第5筆報價觀察' in content and '後3個曆月' in content
        checks.append('observation horizons not mislabeled as trading sessions')
        await page.locator('#event-overview details summary').click()
        assert '<img src=x' in await page.locator('#event-overview').inner_text()
        assert await page.locator('#event-overview img').count()==0 and not await page.evaluate('Boolean(window.injected)')
        checks.append('untrusted strings rendered as text; no HTML execution')
        section=page.locator('[data-event-category="monthly_revenue"]')
        await section.locator('select').select_option(index=1)
        await section.locator('details').last.locator('summary').click()
        assert 'source_id' in await section.inner_text() or 'baseline' in await section.inner_text()
        checks.append('select individual event and inspect frozen baseline/follow-up evidence')
        button=section.locator('button')
        if await button.is_visible():
            count=await section.locator('[data-study-group]').count();await button.click()
            assert await section.locator('[data-study-group]').count()>count
        checks.append('bounded group rendering exposes additional groups on request')
        await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(50)
        assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        await page.screenshot(path=str(args.report.with_suffix('.png')),full_page=True)
        checks.append('390px mobile viewport has no horizontal overflow')
        bad=json.loads(canonical(result));bad['categories']['price_volume']['summaries'][0]['n_total']=99
        error_page=await page_for(bad)
        assert await error_page.locator('#event-results').is_hidden()
        assert '分母' in await error_page.locator('#event-status').inner_text()
        checks.append('inconsistent sample denominator clears results rather than showing estimates')
        not_found=await page_for({},404)
        assert await not_found.locator('#event-results').is_hidden()
        assert 'local.event_study' in await not_found.locator('#event-status').inner_text()
        checks.append('public Pages/no local report shows instruction not fake statistics')
        empty=analyze([], '2020-12-31T00:00:00Z')
        empty_page=await page_for(empty)
        assert await empty_page.locator('[data-study-group]').count()==0
        assert '沒有符合定義的觸發事件' in await empty_page.locator('#event-results').inner_text()
        checks.append('zero-event catalog shown distinctly from zero numeric change')
        requests=await page.evaluate('window.__calls')
        assert requests==['./event-study.json']
        checks.append('only captured report requested; no providers, SQLite or raw files')
        await context.close();await browser.close()
    report={'passed':not errors,'checks':checks,'page_errors':errors,'requests':requests,
      'scope':'Actual local HTML/CSS/JS; about:blank plus in-memory synthetic report. No live network/CDN/market verification.',
      'python':sys.version,'finished_at':datetime.now(timezone.utc).isoformat(),
      'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('event-study.html','js/event-study.js','css/style.css')}}
    args.report.write_bytes(canonical(report));print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise AssertionError('Browser page errors')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--chromium',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();args.report=private_path(args.report);asyncio.run(run(args))


if __name__=='__main__':main()
