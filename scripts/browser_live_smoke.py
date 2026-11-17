"""Opt-in real HTTP/CDN graph acceptance; called by browser_smoke --live-cdn.

The normal path uses the production preview allowlist and unmodified browser
networking. Only the synthetic server's captured bytes change for fault cases.
No certificate exceptions, request routing, fetch patches or CDN substitutions.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from local.core import ROOT
from local.preview import server_from_files, snapshot

CDN = 'https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js'
PAGES = 'https://fastyangmh.github.io/stock-knowledge-graph/'


def sha(body):
    return hashlib.sha256(body).hexdigest()


class FaultFiles(dict):
    """Captured allowlist with explicit synthetic HTTP faults, never disk serving."""

    def __init__(self, files):
        super().__init__(files)
        self.overrides = {}
        self.delay_path = None
        self.started = threading.Event()
        self.finished = threading.Event()
        self.requests = []

    def get(self, path, default=None):
        entry = self.overrides.get(path, super().get(path, default))
        self.requests.append(path)
        if path == self.delay_path:
            self.started.set()
            time.sleep(.6)
            self.finished.set()
        return entry


class Evidence:
    """Observe real browser responses without intercepting the transport."""

    def __init__(self, page, report):
        self.report = report
        self.tasks = []
        report.update(responses=[], request_failures=[], page_errors=[])
        page.on('response', lambda response: self.tasks.append(asyncio.create_task(self.capture(response))))
        page.on('requestfailed', lambda request: report['request_failures'].append(
            {'url': request.url, 'error': request.failure}))
        page.on('pageerror', lambda error: report['page_errors'].append(str(error)))

    async def capture(self, response):
        item = {'url': response.url, 'status': response.status,
                'content_type': response.headers.get('content-type')}
        self.report['responses'].append(item)
        try:
            body = await response.body()
            item.update(bytes=len(body), sha256=sha(body))
            if response.url.startswith('https:'):
                item['tls'] = await response.security_details()
        except Exception as error:
            item['body_error'] = str(error)

    async def finish(self):
        await asyncio.gather(*self.tasks)


async def loaded(page, ticker=None):
    await page.wait_for_function("ticker => { const s=document.querySelector('#status'); return s.textContent.includes('節點') && (!ticker || s.textContent.includes(ticker)); }", arg=ticker)
    assert await page.locator('#cy canvas').count() > 0
    assert await page.locator('#graph-layout').is_visible()


async def rejected(page, message):
    await page.wait_for_function("() => document.querySelector('#status').classList.contains('error')")
    assert message in await page.locator('#status').inner_text()
    assert await page.locator('#graph-layout').is_hidden()
    assert await page.locator('#cy canvas').count() == 0
    assert await page.locator('#alerts').is_hidden()
    assert await page.locator('#reload').is_enabled()


async def verify_cdn(page, evidence):
    assert await page.evaluate('cytoscape.version') == '3.30.4'
    assert await page.evaluate('isSecureContext && Boolean(crypto.subtle)')
    assert await page.evaluate("Function.prototype.toString.call(fetch).includes('[native code]')")
    await evidence.finish()
    assets = [r for r in evidence.report['responses'] if r['url'] == CDN]
    assert assets and assets[0]['status'] == 200 and assets[0].get('sha256')
    evidence.report.update(cytoscape_version='3.30.4', cdn=assets[0], native_fetch=True,
                           secure_context=True, webcrypto_available=True)


async def private_checks(browser, root, report, screenshot):
    from browser_smoke import fixture
    fixture(root)
    files = FaultFiles(snapshot(root / 'preview'))
    # Provenance attack strings are synthetic and transported as ordinary JSON.
    manifest = json.loads(files['/data/manifest.json'][0])
    manifest['sources'].append({'source_id': 'unsafe-synthetic',
        'provider': '<img src=x onerror=window.injected=1>',
        'attribution': '<script>window.injected=1</script>',
        'url': 'javascript:window.injected=1',
        'license_url': 'https://user:password@example.org/secret'})
    files['/data/manifest.json'] = (json.dumps(manifest).encode(), 'application/json')
    server = server_from_files(files, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()
    evidence = Evidence(page, report)
    report.update(checks=[], data_kind='synthetic SQLite export', transport='private preview HTTP + original HTTPS CDN')
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        await page.goto(origin + '/')
        await loaded(page, '1000')
        await verify_cdn(page, evidence)
        assert sum(path.endswith('/graph.json') for path in files.requests) == 1
        assert all(item.get('sha256') for item in manifest['stocks'])
        report['checks'].append('native fetch, real WebCrypto, original CDN 3.30.4; one initial graph')
        for mode, count in [('both', 1), ('tw50', 2), ('etf_009816', 2), ('tw50_only', 1), ('etf_009816_only', 1), ('unknown', 1)]:
            await page.select_option('#universe', mode)
            assert await page.locator('#stock option').count() == count
            await loaded(page)
        await page.fill('#search', 'not-a-stock')
        assert await page.locator('#graph-layout').is_hidden()
        assert await page.locator('#stock').is_disabled()
        await page.fill('#search', '')
        await page.select_option('#universe', 'all')
        await page.fill('#search', '1002')
        await loaded(page, '1002')
        assert await page.locator('#stock option').count() == 1
        report['checks'].append('six membership filters, search, empty state and recovery')
        await page.locator('#source-panel summary').click()
        assert '<img src=x onerror=window.injected=1>' in await page.locator('#sources').inner_text()
        assert '<script>window.injected=1</script>' in await page.locator('#sources').inner_text()
        assert await page.locator('#sources img, #sources script').count() == 0
        assert not await page.evaluate('Boolean(window.injected)')
        links = await page.locator('#sources a').evaluate_all("links => links.map(a => ({url:a.href,rel:a.rel,policy:a.referrerPolicy}))")
        assert any(link['url'] == 'https://example.org/terms' for link in links)
        assert all(link['url'].startswith('https:') and '@' not in link['url']
                   and link['rel'] == 'noopener noreferrer' and link['policy'] == 'no-referrer' for link in links)
        report['checks'].append('literal malicious source text, no execution, HTTPS links without credentials')
        assert await page.locator('#alerts [data-alert-status="triggered"]').count() == 1
        assert await page.locator('#alerts .alert-check').count() == 6
        await page.select_option('#relation', 'has_market_price')
        await page.click('#fit')
        report['checks'].append('independent alert cards, relation filter and fit')
        await page.fill('#search', '')
        path = '/data/stocks/1000/graph.json'
        files.delay_path = path
        await page.select_option('#stock', path.lstrip('/'))
        assert await asyncio.to_thread(files.started.wait, 5)
        await page.select_option('#stock', 'data/stocks/1001/graph.json')
        await loaded(page, '1001')
        assert await asyncio.to_thread(files.finished.wait, 5)
        await page.wait_for_timeout(100)
        assert '1001' in await page.locator('#status').inner_text()
        files.delay_path = None
        report['checks'].append('delayed HTTP response cannot replace newest selection')
        for name, entry, message in [
            ('wrong hash / valid other-stock bytes', files['/data/stocks/1002/graph.json'], '版本不一致'),
            ('HTTP 404', None, 'HTTP 404'),
            ('corrupt bytes', (b'{broken', 'application/json'), '版本不一致'),
        ]:
            files.overrides[path] = entry
            await page.select_option('#stock', path.lstrip('/'))
            await rejected(page, message)
            files.overrides.clear()
            await page.click('#reload')
            await loaded(page, '1000')
            report['checks'].append(name + ': stale canvas cleared; reload recovers')
            await page.select_option('#stock', 'data/stocks/1001/graph.json')
            await loaded(page, '1001')
        # Matching SHA proves integrity, not JSON validity or stock identity.
        for name, wrong, message in [
            ('wrong stock', files['/data/stocks/1002/graph.json'], '股票不一致'),
            ('malformed JSON', (b'{broken', 'application/json'), 'JSON'),
        ]:
            mismatched = json.loads(files['/data/manifest.json'][0])
            mismatched['stocks'][0]['sha256'] = sha(wrong[0])
            files.overrides.update({path: wrong, '/data/manifest.json': (json.dumps(mismatched).encode(), 'application/json')})
            await page.click('#reload')
            await rejected(page, message)
            files.overrides.clear()
            await page.click('#reload')
            await loaded(page, '1000')
            report['checks'].append(name + ' with matching hash rejected; reload recovers')
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.fill('#search', '1002')
        await loaded(page, '1002')
        await page.click('#fit')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(screenshot), full_page=True)
        report['checks'].append('390px mobile search, selection, fit and no overflow')
        for denied in ['/test.db', '/local/private/test.db', '/raw.csv', '/.git/config', '/docs/HANDOFF.md']:
            response = await context.request.get(origin + denied)
            assert response.status == 404
        report['checks'].append('private DB, raw and repository paths denied')
        await evidence.finish()
        assert not report['page_errors']
        report['passed'] = True
    finally:
        await evidence.finish()
        await context.close()
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join(timeout=2)


async def pages_checks(browser, report, screenshot):
    context = await browser.new_context(viewport={'width': 1280, 'height': 900})
    page = await context.new_page()
    evidence = Evidence(page, report)
    report.update(checks=[], data_kind='existing public demo; read only', url=PAGES)
    try:
        response = await page.goto(PAGES)
        assert response.status == 200
        await loaded(page)
        await verify_cdn(page, evidence)
        assert '未標示' in await page.locator('#status').inner_text()
        await page.fill('#search', 'not-a-stock')
        assert await page.locator('#graph-layout').is_hidden()
        await page.fill('#search', '')
        await loaded(page)
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.click('#fit')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(screenshot), full_page=True)
        await evidence.finish()
        assert not report['page_errors']
        report['checks'].append('HTTPS demo canvas, original CDN, search/empty recovery and 390px viewport')
        report['passed'] = True
    finally:
        await evidence.finish()
        await context.close()


async def run_live(args):
    from playwright.async_api import async_playwright
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {'mode': 'live-cdn', 'started_at': datetime.now(timezone.utc).isoformat(),
              'python': sys.version, 'platform': platform.platform(), 'command': sys.argv,
              'playwright': version('playwright'),
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
              'source_sha256': {name: sha((ROOT / name).read_bytes()) for name in (
                  'index.html', 'css/style.css', 'js/app.js', 'js/graph-utils.js',
                  'scripts/browser_smoke.py', 'scripts/browser_live_smoke.py', 'local/preview.py')},
              'private_preview': {'passed': False}, 'pages_demo': {'passed': False}, 'passed': False}
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=str(args.chromium), headless=True)
            report['browser'] = browser.version
            try:
                with tempfile.TemporaryDirectory(prefix='graph-live-') as directory:
                    try:
                        await private_checks(browser, Path(directory), report['private_preview'], args.report.with_suffix('.private.png'))
                    except Exception as error:
                        report['private_preview']['error'] = f'{type(error).__name__}: {error}'
                try:
                    await pages_checks(browser, report['pages_demo'], args.report.with_suffix('.pages.png'))
                except Exception as error:
                    report['pages_demo']['error'] = f'{type(error).__name__}: {error}'
            finally:
                await browser.close()
        report['passed'] = all(report[key]['passed'] for key in ('private_preview', 'pages_demo'))
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({key: value for key, value in report.items() if key not in ('source_sha256', 'command')}, ensure_ascii=False, indent=2))
    if not report['passed']:
        raise SystemExit(1)
