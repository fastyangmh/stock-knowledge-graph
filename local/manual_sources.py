"""Acquire or replay the two reviewed financial feeds and one market price feed."""
import hashlib
import json
import time
from pathlib import Path

from . import market_prices, official_import, research
from .collect_official import atomic_bytes, download, save_failure
from .core import ROOT
from .http_evidence import ResponseBytes, body_metadata
from .official_adapter import csv_rows, dataset_profile
from .research import guarded
from .research_history import MAX_INPUT_BYTES, canonical, strict_json, utc_now, validate_symbols
from .source_registry import load_approved


def read_json(path):
    with guarded(path).open('rb') as stream:
        return strict_json(stream.read(MAX_INPUT_BYTES + 1))


def optional_json(path):
    return read_json(path) if guarded(path).exists() else None


def checked_bytes(path, expected, limit):
    with guarded(path).open('rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit or hashlib.sha256(body).hexdigest() != expected:
        raise ValueError(f'input exceeds budget or checksum mismatch: {path}')
    return body


def registry_for(plan):
    registry = Path(plan.get('registry', ROOT/'local/official_datasets.json'))
    approved = load_approved(registry)
    expected = {plan['market'] + suffix for suffix in ('_companies', '_monthly_revenue')}
    if {s['dataset_id'] for s in approved} != expected:
        raise ValueError('financial registry must enable the two sources for the requested market')
    official = {s['dataset_id']: s for s in json.loads((ROOT/'local/official_datasets.json').read_bytes())}
    for source in approved:
        trusted = official[source['dataset_id']]
        for field in ('kind', 'format', 'resource_url', 'dataset_url', 'license_url', 'provider', 'attribution'):
            if trusted[field] != source[field]:
                raise ValueError('registry differs from approved dataset: ' + source['dataset_id'])
    return registry, approved


def verify_entry(plan, reviewed, entry, root, status):
    relative = Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts or entry['resource_url'] != reviewed['resource_url']:
        raise ValueError('snapshot path or source differs from reviewed source')
    body = checked_bytes(root/relative, entry['sha256'], 15_000_000)
    if len(body) != entry['bytes']:
        raise ValueError('snapshot byte length mismatch')
    profile = dataset_profile(reviewed, csv_rows(body), entry['retrieved_at'], validate_symbols(plan['symbols']))
    detail = {'dataset_id': entry['dataset_id'], 'retrieved_at': entry['retrieved_at'], 'sha256': entry['sha256'],
              'retrieval_day': profile['retrieval_day'], 'report_dates': list(profile['report_dates']),
              'revenue_months': list(profile['revenue_months'])}
    if profile['retrieval_day'] != plan['as_of']:
        status.update(kind='stale', actual=detail)
        raise ValueError('snapshot retrieval day differs from requested as_of')
    if reviewed['kind'] == 'monthly_revenue' and plan.get('expected_revenue_month') and (
            detail['revenue_months'] != [plan['expected_revenue_month']]):
        status.update(kind='stale', actual=detail)
        raise ValueError('financial period differs from expected ' + plan['expected_revenue_month'])
    return detail


def collect_sources(plan, job, approved, status):
    snapshots = guarded(job/'official')
    datasets = []
    downloaded = False
    for source in approved:
        ident = source['dataset_id']
        status['failed_source'] = ident
        dest = guarded(snapshots/ident)
        dest.mkdir(parents=True, exist_ok=True)
        manifest_path = guarded(dest/'retrieval_manifest.json')
        pin = guarded(dest/'verified-receipt.json')
        if not pin.exists():
            registry = guarded(dest/'registry.json')
            atomic_bytes(registry, canonical([source]))
            if downloaded:
                time.sleep(1)
            download(registry, dest)
            downloaded = True
        if pin.exists():
            manifest = strict_json(checked_bytes(manifest_path, read_json(pin)['sha256'], 4*1024**2))
        else:
            manifest = read_json(manifest_path)
        [entry] = manifest['datasets']
        if entry['dataset_id'] != ident or entry['resource_url'] != source['resource_url']:
            raise ValueError('cached receipt does not match the requested source')
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid cached source path')
        verify_entry(plan, source, entry, dest, status)
        if not pin.exists():
            atomic_bytes(pin, canonical({'sha256': research.file_digest(manifest_path)}))
        datasets.append({**entry, 'path': str(Path(ident)/relative)})
        status.setdefault('verified_sources', []).append(ident)
    combined = {'schema_version': '1.0', 'datasets': datasets}
    atomic_bytes(guarded(snapshots/'retrieval_manifest.json'), canonical(combined))
    return snapshots, combined


def financial_sources(plan, job, status):
    registry, approved = registry_for(plan)
    expected = {s['dataset_id'] for s in approved}
    if plan.get('download_financial') is True:
        snapshots, manifest = collect_sources(plan, job, approved, status)
    else:
        snapshots = guarded(plan['financial_dir'])
        manifest = strict_json(checked_bytes(snapshots/'retrieval_manifest.json',
                                             plan['financial_manifest_sha256'], 4*1024**2))
    if {s['dataset_id'] for s in manifest['datasets']} != expected or len(manifest['datasets']) != 2:
        raise ValueError('missing or unexpected financial source')
    reviewed = {s['dataset_id']: s for s in approved}
    sources = []
    status['sources'] = sources
    for source in manifest['datasets']:
        ident = source['dataset_id']
        status['failed_source'] = ident
        sources.append(verify_entry(plan, reviewed[ident], source, snapshots, status))
    status.pop('failed_source')
    return snapshots, registry


def normalize(plan, snapshots, registry, job, verified_sources):
    output = guarded(job/'input.json')
    args = ['--snapshot-dir', str(snapshots), '--registry', str(registry),
            '--symbols', *plan['symbols'], '--as-of', plan['as_of'], '--output', str(output)]
    if plan.get('unit_evidence'):
        checked_bytes(plan['unit_evidence'], plan['unit_evidence_sha256'], 4*1024**2)
        args += ['--unit-evidence', plan['unit_evidence']]
    official_import.main(args)
    payload = read_json(output)
    observed = {(r['dataset_id'], r['sha256'], r['retrieved_at']) for r in payload['metadata']['source_snapshots']}
    expected = {(r['dataset_id'], r['sha256'], r['retrieved_at']) for r in verified_sources}
    if observed != expected or payload['metadata'].get('unit_evidence_sha256') != plan.get('unit_evidence_sha256'):
        raise ValueError('normalized sources or unit evidence changed after verification')
    return {'revenue_months': sorted({m['period_end'][:7] for m in payload['financial_metrics']}),
            'revenue_report_dates': sorted({d['source_report_date'] for d in payload['documents']}),
            'retrieval_day': plan['as_of'], 'input_sha256': research.file_digest(output)}


def closed_day_evidence(plan, calendar):
    # A saved file explicitly supplied for a holiday can contradict the calendar.
    # Do not fetch quotes to check a holiday.
    raw = checked_bytes(plan['price_file'], plan['price_sha256'], market_prices.MAX_BYTES)
    try:
        market_prices.normalize(raw, plan['market'], plan['symbols'], plan['trade_date'], utc_now())
    except ValueError as exc:
        dates = getattr(exc, 'profile', {}).get('date_distribution', {})
        if len(dates) == 1 and plan['trade_date'] not in dates:
            calendar['other_price_date'] = next(iter(dates))
            return
        raise
    calendar.update(market_status='conflict', reason='verified_quote_on_closed_day',
                    price_sha256=plan['price_sha256'])


def ingest_prices(plan, market, job):
    source = market_prices.source_info(plan['market'])
    online = plan.get('download_prices') is True
    acquisition = 'https_download' if online else 'local_file_unverified'
    receipt = guarded(job/'price-observation.json')
    raw_path = guarded(job/'downloaded-price.csv' if online else plan['price_file'])
    saved = optional_json(receipt)
    body = None
    try:
        if online and saved is None:
            body = market_prices.fetch(plan['market'])
            observed = utc_now()
            # Persist only a matching, complete target day as reusable evidence.
            market_prices.normalize(body, plan['market'], plan['symbols'], plan['trade_date'], observed)
            atomic_bytes(raw_path, body)
        else:
            expected = saved['sha256'] if online else plan['price_sha256']
            body = checked_bytes(raw_path, expected, market_prices.MAX_BYTES)
            observed = saved['observed_at'] if saved else utc_now()
        if saved is None:
            saved = {'sha256': hashlib.sha256(body).hexdigest(), 'observed_at': observed,
                     'http': body_metadata(body, source['resource_url'])}
            atomic_bytes(receipt, canonical(saved))
        if hashlib.sha256(body).hexdigest() != saved['sha256']:
            raise ValueError('saved price observation checksum mismatch')
        payload = market_prices.ingest(ResponseBytes(body, saved['http']), plan['market'], plan['symbols'],
                      plan['trade_date'], db=guarded(market/'prices.db'), output=guarded(market/'prices'),
                      acquisition=acquisition, observed_at=observed)
    except Exception as exc:
        save_failure(guarded(job/'price-failures'), source, [], 'manual_prices', exc, body)
        raise
    return {'trade_date': payload['expected_date'], 'observed_at': payload['observed_at'],
            'acquisition': acquisition, 'raw_sha256': payload['raw_sha256'],
            'inserted': payload['inserted_observations']}
