"""Real loopback research→audit→event UI checks with synthetic private bundles.

Requires Playwright and Chromium; never replaces fetch or contacts providers.
"""
import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'local/tests'))
from local.event_study import build, make_server
from local.research_history import canonical
from local.safety import private_path
from test_event_integration import research_run, ASOF, CONFIG


async def run(args):
    from playwright.async_api import async_playwright
    checks, errors = [], []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        research_run(root, 0, '2020-08-14', '100', 1000, cap=0)
        first = research_run(root, 1, '2020-08-15', '110', 3000, alerts=True, cap=0)
        research_run(root, 2, '2020-08-16', '121', 1500, cap=0)
        complete = build(root/'runs', ASOF, config=CONFIG)
        # Produce an authentic legacy file layout, then let catalog audit it.
        path = root/'runs'/first['run']
        report = json.loads((path/'report.json').read_bytes())
        report.pop('research_facts')
        (path/'report.json').write_bytes(canonical(report))
        (path/'research-facts.json').unlink()
        mixed = build(root/'runs', ASOF, config=CONFIG, cohort='unpruned_facts')
        legacy = build(root/'runs', ASOF, config=CONFIG, cohort='display_graph_only')
        isolated = root/'legacy'
        shutil.copytree(path, isolated/first['run'])
        (isolated/'latest.json').write_bytes(canonical({'engine':report['engine'], 'run':first['run'],
            'report_sha256':hashlib.sha256(canonical(report)).hexdigest()}))
        pure_legacy = build(isolated, ASOF, config=CONFIG)
        reports = {'complete':complete, 'mixed':mixed, 'legacy':legacy, 'pure-legacy':pure_legacy}
        urls = {}
        for name, report in reports.items():
            (args.report.parent/(name+'-study.json')).write_bytes(canonical(report))
            server = make_server(report, port=0, root=ROOT)
            stack.callback(server.server_close)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            stack.callback(server.shutdown)
            urls[name] = f'http://127.0.0.1:{server.server_port}/'
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=str(args.chromium), headless=True)
            context = await browser.new_context(viewport={'width':1280, 'height':900})
            page = await context.new_page()
            page.on('pageerror', lambda error:errors.append(str(error)))
            for name, url in urls.items():
                await page.goto(url)
                await page.wait_for_function("document.querySelector('#event-status').textContent.startsWith('已載入')")
                text = await page.locator('#event-overview').inner_text()
                version, scope = (('event-study-1.0','display_graph_only') if 'legacy' in name
                                  else ('event-study-2.0','unpruned_facts'))
                assert version in text and scope in text
                assert '未納入' in text and '不合併分母' in text
                await page.get_by_text('納入／未納入版本與理由', exact=True).click()
                assert 'inputs' in await page.locator('#event-overview').inner_text()
                if name == 'mixed':
                    assert 'different_fact_scope' in await page.locator('#event-overview').inner_text()
                if name == 'complete':
                    assert '10.000000' in await page.locator('#event-results').inner_text()
                    await page.locator('[data-event-category="price_volume"] details').filter(has=page.get_by_text('事件基準與原始提醒', exact=True)).locator('summary').click()
                    assert 'fact_id' in await page.locator('#event-results').inner_text()
                checks.append(name+': real HTTP version, scope, cohort disclosure and event results')
                await page.set_viewport_size({'width':390, 'height':844})
                assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                await page.screenshot(path=str(args.report.parent/(name+'-mobile.png')), full_page=True)
                checks.append(name+': 390px mobile disclosure visible without horizontal overflow')
                await page.set_viewport_size({'width':1280, 'height':900})
            for path in ('research-facts.json','report.json','graph.db','raw','runs','../ledger.db'):
                response = await context.request.get(urls['complete']+path)
                assert response.status == 404
            checks.append('real HTTP allowlist refuses complete facts, report, DB and raw files')
            await context.close()
            await browser.close()
    result = {'passed':not errors, 'checks':checks, 'page_errors':errors,
        'scope':'Synthetic CSV/SQLite/research/audit reports; real loopback HTTP, native browser fetch. No official financial data or Linux validation.',
        'python':sys.version, 'finished_at':datetime.now(timezone.utc).isoformat(),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('event-study.html','js/event-study.js','css/style.css','local/event_study.py','local/event_outcomes.py','scripts/event_facts_browser_smoke.py')}}
    args.report.write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise AssertionError('Browser page errors')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    args.report = private_path(args.report)
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
