"""Frozen official headers with synthetic data rows for quarterly adapter tests."""
import csv
import hashlib
import json
from pathlib import Path

from local.bundle_audit import audit_bundle
from local.research import run
from local.quarterly_import import main


HEADERS = json.loads((Path(__file__).parent/'fixtures/quarterly_headers.json').read_text())


def save_csv(root, dataset, resource, row, *, columns=None, observed='2020-11-10T06:00:00Z'):
    raw = root / f'{dataset}.response'
    with raw.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or HEADERS[str(dataset)], extrasaction='ignore')
        writer.writeheader()
        writer.writerow(row)
    body = raw.read_bytes()
    entry = dict(id=dataset, catalog=f'https://data.gov.tw/dataset/{dataset}',
                 url='https://mopsfin.twse.com.tw/opendata/' + resource, received_at=observed,
                 sha256=hashlib.sha256(body).hexdigest(), bytes=len(body), exit=0, status='200')
    (root/'manifest.json').write_text(json.dumps([entry]))
    return entry


def normalize_csv(manifest, dataset, symbol, output, *options):
    main(['--manifest', str(manifest), '--dataset', str(dataset), '--symbols', symbol,
          '--output', str(output), *options])
    return json.loads(output.read_bytes())


def research(root, path, symbol, **options):
    runs = root/'runs'
    report = run(path, [symbol], history_db=root/'ledger.db', output_root=runs,
                 max_information_nodes=0, **options)
    return audit_bundle(runs, report['run'])
