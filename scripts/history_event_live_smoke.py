"""Opt-in native HTTP acceptance for private history and event pages.

Successful paths use production server factories and persisted synthetic bundles.
Fault cases change captured HTTP bytes, never fetch, browser policy or the CDN.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import version
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from browser_live_smoke import Evidence, FaultFiles, loaded, sha, verify_cdn
from local.core import ROOT
from local import event_study, research_archive
from local.preview import server_from_files
from local.research_compare import compare
from local.research_history import canonical

ATTACK = '<img src=x onerror=window.injected=true>'


@asynccontextmanager
async def serving(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join(timeout=2)


async def allowlist(context, origin, report, extra=()):
    rows = []
    for path in ('/graph.db', '/ledger.db', '/prices.db', '/raw', '/raw.csv',
                 '/research-facts.json', '/report.json', '/latest.json', '/runs/',
                 '/.git/config', '/local/private/', '/%2e%2e/ledger.db', *extra):
        response = await context.request.get(origin + path)
        rows.append({'path': path, 'status': response.status})
        assert response.status == 404, rows[-1]
    response = await context.request.get(origin + '/', headers={'Host': 'evil.example'})
    assert response.status == 403
    for method in ('POST', 'PUT', 'DELETE', 'OPTIONS'):
        response = await context.request.fetch(origin + '/', method=method)
        assert response.status == 501
        rows.append({'method': method, 'status': response.status})
    response = await context.request.head(origin + '/')
    assert response.status == 200 and await response.body() == b''
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert "connect-src 'self'" in response.headers['content-security-policy']
    report.setdefault('http_checks', []).append({'origin': origin, 'denied': rows, 'host_status': 403, 'head_status': 200})


async def native(page):
    assert page.url.startswith('http://127.0.0.1:')
    assert await page.evaluate("Function.prototype.toString.call(fetch).includes('[native code]')")


async def history_ready(page, count):
    await page.wait_for_function('count => document.querySelector("#before-run").options.length === count && !document.querySelector("#history-status").textContent.startsWith("讀取")', arg=count)
    await native(page)


async def comparison(page, before, after):
    await page.select_option('#before-run', before['run'])
    await page.select_option('#after-run', after['run'])
    await page.click('#compare-runs')
    await page.wait_for_selector('#comparison:not([hidden])')


async def history_checks(browser, root, report, screenshot):
    from history_fixtures import make_run
    a = make_run(root, 1, value=10)
    b = make_run(root, 2, value=40)
    c = make_run(root, 3, config={'revenue_yoy_pct': 99})
    invalid = 'f' * 32
    shutil.copytree(root/'runs'/a['run'], root/'runs'/invalid)
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()
    evidence = Evidence(page, report)
    report.update(checks=[], data_kind='persisted synthetic SQLite research bundles', passed=False)
    try:
        async with serving(research_archive.make_server(root/'runs', port=0)) as origin:
            await page.goto(origin)
            await history_ready(page, 3)
            assert await page.locator('#run-list article').count() == 4
            assert await page.locator('#run-list a').count() == 3
            assert '未通過稽核' in await page.locator('#run-list').inner_text()
            await comparison(page, a, b)
            assert await page.locator('[data-comparison-category="price_volume"]').count() == 1
            assert await page.locator('[data-comparison-category="monthly_revenue"]').count() == 1
            assert await page.locator('[data-transition="activated"]').count() > 0
            assert await page.locator('[data-transition="still_unavailable"]').count() == 2
            await page.locator('[data-comparison-category="monthly_revenue"] details summary').first.click()
            assert 'source_id' in await page.locator('#comparison').inner_text()
            await comparison(page, b, c)
            assert await page.locator('[data-transition="definition_changed"]').count() > 0
            report['checks'].append('desktop: audited versions; corrupt version disabled; independent categories, transitions, definitions and source evidence')
            for width in (1280, 390):
                await page.set_viewport_size({'width': width, 'height': 900})
                await comparison(page, a, b)
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                await page.locator(f'[data-run="{b["run"]}"] a').click()
                await loaded(page, '1000')
                await verify_cdn(page, evidence)
                assert await page.locator('#alerts .alert-check').count() == 6
                assert f'run={b["run"]}' in page.url
                await page.go_back()
                await history_ready(page, 3)
            await page.screenshot(path=str(screenshot), full_page=True)
            report['checks'].append('desktop/mobile comparisons and actual version graph navigation; original CDN 3.30.4, native WebCrypto, back navigation')
            await allowlist(context, origin, report, (f'/versions/{b["run"]}/graph.db', f'/versions/{b["run"]}/research-facts.json', f'/versions/{invalid}/data/manifest.json'))
            await page.select_option('#before-run', c['run'])
            await page.select_option('#after-run', a['run'])
            await page.click('#compare-runs')
            await page.wait_for_selector('#history-status.error')
            assert await page.locator('#comparison').is_hidden()
            await comparison(page, a, b)
            report['checks'].append('HTTP 400 reverse-cutoff rejection clears output; valid comparison recovers')
        # Captured synthetic fault server: same production HTTP handler and assets.
        files, bundles = research_archive.archive_snapshot(root/'runs')
        files = FaultFiles(files)
        path = f'/api/compare?before={a["run"]}&after={b["run"]}'
        started, finished = threading.Event(), threading.Event()
        def resolve(parsed):
            if parsed.path + '?' + parsed.query != path:
                return None
            started.set()
            import time
            time.sleep(.6)
            finished.set()
            return canonical(compare(bundles[a['run']], bundles[b['run']])), 'application/json'
        catalog = json.loads(files['/research-history.json'][0])
        next(row for row in catalog['runs'] if row['status'] == 'valid').setdefault('warnings', []).append(ATTACK)
        files['/research-history.json'] = (canonical(catalog), 'application/json')
        async with serving(server_from_files(files, port=0, resolver=resolve)) as origin:
            await page.goto(origin)
            await history_ready(page, 3)
            assert ATTACK in await page.locator('#run-list').text_content()
            assert await page.locator('#run-list img').count() == 0
            assert not await page.evaluate('Boolean(window.injected)')
            await page.select_option('#before-run', a['run'])
            await page.select_option('#after-run', b['run'])
            await page.click('#compare-runs')
            assert await asyncio.to_thread(started.wait, 5)
            await page.select_option('#after-run', c['run'])
            assert await asyncio.to_thread(finished.wait, 5)
            await page.wait_for_timeout(100)
            assert await page.locator('#comparison').is_hidden()
            await comparison(page, a, b)
            report['checks'].append('literal malicious warning; delayed real HTTP comparison cannot overwrite changed selection; recovery')
            for name, entry in [('404', None), ('invalid catalog', (b'{}', 'application/json'))]:
                files.overrides['/research-history.json'] = entry
                await page.reload()
                await page.wait_for_selector('#history-status.error')
                assert await page.locator('#comparison').is_hidden()
                files.overrides.clear()
                await page.reload()
                await history_ready(page, 3)
                report['checks'].append(name + ' rejected; reload recovers')
        (root/'runs/latest.json').write_text('{}')
        try:
            research_archive.make_server(root/'runs', port=0)
        except ValueError as error:
            assert 'invalid_latest_pointer' in str(error)
        else:
            raise AssertionError('malformed latest must prevent server startup')
        report['checks'].append('malformed on-disk latest prevents server startup')
        (root/'runs/latest.json').unlink()
        async with serving(research_archive.make_server(root/'runs', port=0)) as origin:
            await page.goto(origin)
            await history_ready(page, 3)
            assert '最新指標缺失或無效' in await page.locator('#history-overview').inner_text()
            assert (await context.request.get(origin+'/data/manifest.json')).status == 404
            await comparison(page, a, b)
            report['checks'].append('missing on-disk latest never falls back; individually audited versions remain comparable')
        empty = root/'empty'; empty.mkdir()
        try:
            research_archive.make_server(empty, port=0)
        except ValueError as error:
            assert 'no_research_runs' in str(error)
        else:
            raise AssertionError('empty catalog must prevent server startup')
        empty_catalog = {**catalog, 'runs': [], 'latest': None, 'latest_valid': False,
                         'counts': {'valid': 0, 'invalid': 0, 'staging_residues': 0}}
        files.overrides['/research-history.json'] = (canonical(empty_catalog), 'application/json')
        async with serving(server_from_files(files, port=0)) as origin:
            await page.goto(origin)
            await page.wait_for_function('document.querySelector("#history-overview").textContent.includes("有效版本 0")')
            assert await page.locator('#compare-runs').is_disabled()
            assert await page.locator('#before-run option').count() == 0
            report['checks'].append('empty on-disk catalog prevents startup; synthetic empty HTTP catalog disables comparison')
        await evidence.finish()
        assert not report['page_errors']
        report['native_fetch'] = True
        report['passed'] = True
    finally:
        await evidence.finish()
        await context.close()


async def event_ready(page):
    await page.wait_for_function('!document.querySelector("#event-status").textContent.startsWith("讀取")')
    await native(page)


async def event_checks(browser, root, report, screenshot):
    from test_event_integration import research_run
    from event_fixtures import revenue
    research_run(root, 0, '2020-08-14', '100', 1000)
    research_run(root, 1, '2020-08-15', '110', 3000, alerts=True)
    research_run(root, 2, '2020-08-16', '121', 1500)
    research_run(root, 3, '2020-09-10', '120', 1000, data=revenue())
    result = event_study.build(root/'runs', '2020-09-30T23:59:59+08:00')
    event_study.save_report(result, root/'event-report.json', root/'runs')
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()
    evidence = Evidence(page, report)
    report.update(checks=[], data_kind='report built from audited persisted synthetic CSV/SQLite bundles', passed=False,
                  study_id=result['study_id'], report_sha256=sha(canonical(result)))
    try:
        async with serving(event_study.make_server(result, port=0)) as origin:
            await page.goto(origin)
            await event_ready(page)
            assert await page.locator('[data-event-category]').count() == 2
            content = await page.locator('#event-results').inner_text()
            for label in ('價量提醒事件（2筆）', '月營收提醒事件（4筆）', '事件分母 1｜可計算 1｜尚無可比結果 0',
                          '已觀察', '月份尚未結束', '資料不足', '不可比較', '無可計算樣本', '後第5筆報價觀察', '後3個曆月'):
                assert label in content, label
            assert '10.000000' in content
            for width in (1280, 390):
                await page.set_viewport_size({'width': width, 'height': 900})
                section = page.locator('[data-event-category="monthly_revenue"]')
                for index in (1, 0, 1):
                    await section.locator('select').select_option(index=index)
                details = section.locator('details').filter(has=page.locator('summary', has_text='事件基準與原始提醒'))
                await details.locator('summary').click()
                assert 'report_sha256' in await details.inner_text()
                assert 'baseline' in await details.inner_text()
                assert result['categories']['monthly_revenue']['events'][1]['event_id'] in await details.inner_text()
                await details.locator('summary').click()
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path=str(screenshot), full_page=True)
            await allowlist(context, origin, report, ('/data/manifest.json', '/api/compare'))
            report['checks'].append('desktop/mobile: 2 price and 4 revenue events; four-state denominators, 10% observed result, no fake zero, exact horizons and frozen evidence')
        files = {'/event-study.json': (canonical(result), 'application/json')}
        for name, mime in event_study.ASSETS.items():
            files['/'+name] = ((ROOT/name).read_bytes(), mime)
        files['/'] = files['/event-study.html']
        files = FaultFiles(files)
        attack = json.loads(canonical(result)); attack['warnings'].append(ATTACK)
        bad = json.loads(canonical(result)); bad['categories']['price_volume']['summaries'][0]['n_total'] = 99
        empty_root = root/'no-events'; empty_root.mkdir()
        research_run(empty_root, 0, '2020-08-14', '100', 1000)
        empty = event_study.build(empty_root/'runs', '2020-09-30T23:59:59+08:00')
        async with serving(server_from_files(files, port=0)) as origin:
            for name, body, error in [('malicious text', canonical(attack), False), ('invalid denominator', canonical(bad), True),
                                       ('illegal schema', b'{"schema_version":"unknown"}', True),
                                       ('malformed JSON', b'{broken', True), ('HTTP 404', None, True),
                                       ('zero events', canonical(empty), False)]:
                files.overrides['/event-study.json'] = None if body is None else (body, 'application/json')
                await page.goto(origin)
                await event_ready(page)
                if error:
                    assert await page.locator('#event-results').is_hidden()
                    assert await page.locator('#event-status.error').count() == 1
                elif name == 'malicious text':
                    await page.get_by_text('分析設定與資料限制', exact=True).click()
                    assert ATTACK in await page.locator('#event-overview').inner_text()
                    assert await page.locator('#event-overview img').count() == 0
                    assert not await page.evaluate('Boolean(window.injected)')
                else:
                    assert await page.locator('[data-study-group]').count() == 0
                    assert '沒有符合定義的觸發事件' in await page.locator('#event-results').inner_text()
                files.overrides.clear()
                await page.reload()
                await event_ready(page)
                assert await page.locator('#event-results').is_visible()
                report['checks'].append(name + ': expected state and reload recovery')
        await evidence.finish()
        assert not report['page_errors']
        report['native_fetch'] = True
        report['passed'] = True
    finally:
        await evidence.finish()
        await context.close()


async def run_live(args, kind):
    from playwright.async_api import async_playwright
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {'mode': 'live-http', 'page': kind, 'started_at': datetime.now(timezone.utc).isoformat(),
              'command': sys.argv, 'python': sys.version, 'platform': platform.platform(), 'playwright': version('playwright'),
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
              'source_sha256': {name: sha((ROOT/name).read_bytes()) for name in (
                  'scripts/history_event_live_smoke.py', 'scripts/browser_live_smoke.py', 'scripts/history_browser_smoke.py',
                  'scripts/event_browser_smoke.py', 'history.html', 'event-study.html', 'index.html', 'css/style.css',
                  'js/history.js', 'js/history-utils.js', 'js/event-study.js', 'js/app.js', 'js/graph-utils.js',
                  'local/research_archive.py', 'local/event_study.py', 'local/preview.py',
                  'local/tests/history_fixtures.py', 'local/tests/event_fixtures.py',
                  'local/tests/test_event_integration.py', 'local/tests/test_alerts.py',
                  'local/tests/test_alert_integration.py')}, 'passed': False}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=str(args.chromium), headless=True)
            report['browser'] = browser.version
            try:
                with tempfile.TemporaryDirectory(prefix=kind+'-live-') as directory:
                    await (history_checks if kind == 'history' else event_checks)(browser, Path(directory), report, args.report.with_suffix('.png'))
            finally:
                await browser.close()
    except Exception as error:
        import traceback
        report['passed'] = False
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        report['exit_code'] = 0 if report['passed'] else 1
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        args.report.write_bytes(canonical(report))
        print(json.dumps({k:v for k,v in report.items() if k not in ('responses', 'source_sha256')}, ensure_ascii=False, indent=2))
    if not report['passed']:
        raise SystemExit(1)
