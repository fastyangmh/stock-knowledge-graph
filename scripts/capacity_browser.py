"""Measure graph readiness for the saved hot bundles using native Chromium and the normal CDN."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from playwright.async_api import async_playwright

from browser_live_smoke import CDN, loaded
from history_event_live_smoke import native, serving
from local.preview import make_server
from local.research import guarded


async def measure(folder, executable):
    summary = json.loads(guarded(folder / 'summary.json').read_bytes())
    if not summary['passed']:
        raise ValueError('successful capacity benchmark required')
    rows = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path=executable)
        for phase in summary['phases']:
            if phase['mode'] != 'hot':
                continue
            size = phase['documents']
            graph = guarded(folder / str(size) / 'runs' / phase['run'] / 'data')
            context = await browser.new_context(viewport={'width': 1280, 'height': 900})
            async with serving(make_server(graph, port=0)) as origin:
                for attempt in range(1, 4):
                    page = await context.new_page()
                    start = perf_counter()
                    await page.goto(origin, wait_until='domcontentloaded')
                    await loaded(page, '1000')
                    elapsed = perf_counter() - start
                    await native(page)
                    resources = await page.evaluate("""cdn => performance.getEntriesByType('resource')
                        .filter(r => r.name === cdn || r.name.endsWith('/graph.json'))
                        .map(r => ({kind: r.name === cdn ? 'cdn' : 'graph', duration_ms: r.duration,
                                    transfer_bytes: r.transferSize}))""", CDN)
                    if {r['kind'] for r in resources} != {'cdn', 'graph'}:
                        raise ValueError('missing expected CDN or graph HTTP resource')
                    rows.append({'documents': size, 'run': phase['run'], 'attempt': attempt,
                                 'first_in_context': attempt == 1, 'ready_seconds': elapsed,
                                 'loads': resources, 'chromium': browser.version})
                    await page.close()
            await context.close()
        await browser.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--chromium', help='Optional existing Chromium executable')
    parser.add_argument('--output', type=Path, required=True, help='New private JSON report')
    args = parser.parse_args()
    output = guarded(args.output)
    if output.exists():
        raise FileExistsError(output)
    rows = asyncio.run(measure(guarded(args.benchmark), args.chromium))
    with output.open('x') as stream:
        json.dump(rows, stream, indent=2)
    print(output)


if __name__ == '__main__':
    main()
