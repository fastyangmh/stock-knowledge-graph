"""Verify private TPEx chip contributions against their registered source representation."""
import base64
import hashlib
from functools import lru_cache

from .dates import timestamp
from .source_receipts import raw_receipt, registry

CHIP_SOURCES = {'tpex_institutional_11856', 'tpex_margin_11387'}
CHIP_VERSIONS = {f'tpex-{family}-{version}' for family in ('margin', 'institutional') for version in (1, 2)}


@lru_cache(maxsize=2)
def columns_for(source):
    from . import institutional_import, margin_import
    if source == institutional_import.SOURCE:
        return {column: ('tpex_institutional_'+key, 'shares') for key, column in institutional_import.METRICS.items()}
    return {column: ('tpex_margin_'+key, 'percent' if column.endswith('使用率') else 'source_reported')
            for column, key in margin_import.METRICS.items()}


def validate_cell(row, source, receipt, meta, available):
    definition = columns_for(source).get(row['source_column'])
    if (row['source_id'] != source or row['raw_sha256'] != receipt
            or (row['metric'], row['unit']) != definition or row['trade_date'] != meta['trade_date'] or available != meta['observed_at']
            or type(row['row_number']) is not int or not 2 <= row['row_number'] <= meta['raw_row_count'] + 1):
        raise ValueError('chip cell differs from receipt or column contract')


def validate_chip(payload):
    from . import institutional_import, margin_import
    from .research_history import canonical

    meta = payload['metadata']
    version = meta.get('adapter_version')
    if version not in CHIP_VERSIONS:
        if ('source_csv_b64' in payload or ('source_revision' not in payload and
                any(r['source_id'] in CHIP_SOURCES for r in payload.get('chip_metrics', [])))):
            raise ValueError('chip source requires a reviewed adapter')
        return
    identity, sha = raw_receipt(payload)
    source = identity[0]
    adapter = institutional_import if source == institutional_import.SOURCE else margin_import
    receipt, = meta['source_snapshots']
    if version.endswith('-2'):
        body = base64.b64decode(payload['source_csv_b64'], validate=True)
        if len(body) != receipt['bytes'] or hashlib.sha256(body).hexdigest() != sha:
            raise ValueError('chip original CSV checksum mismatch')
        expected = adapter.project(registry()[source], dict(sha256=sha, bytes=len(body), received_at=meta['observed_at']),
                                   body, meta['trade_date'], {s['stock_id'] for s in payload['stocks']})
        if canonical(expected) != canonical(payload):
            raise ValueError('chip projection differs from original CSV')
        return
    if 'source_csv_b64' in payload or 'source_revision' in payload or payload.get('financial_metrics'):
        raise ValueError('unexpected legacy chip payload')
    rows = {}
    for metric in payload['chip_metrics']:
        validate_cell(metric, source, sha, meta, metric['available_at'])
        cells = rows.setdefault((metric['stock_id'], metric['row_number']), {})
        cells[metric['source_column']] = metric['value']
    stocks = {stock['stock_id'] for stock in payload['stocks']}
    if (len(rows) != len(stocks) or len({i for _, i in rows}) != len(rows) or {s for s, _ in rows} != stocks):
        raise ValueError('legacy chip row coverage differs from selection')
    columns = adapter.COLUMNS[3:3+len(adapter.METRICS)]
    for (_, index), cells in rows.items():
        if set(cells) != set(columns):
            raise ValueError('incomplete legacy chip row')
        adapter.row_values(['', '', '', *(str(cells[column]) for column in columns), ''], index)


def audit_chip_facts(snapshots, facts, stock_ids, revisions):
    """Validate each surviving fact against its immutable contributing projection."""
    by_sha, latest = {}, {}
    superseded = {(r['notice']['source_id'], r['notice']['key']['stock_id'], r['notice']['key']['metric'],
                   r['notice']['key']['trade_date']) for r in revisions if r['notice']['group'] == 'chip_metrics'}
    for snapshot in sorted(snapshots, key=lambda s: (s['observed_at'], s['recorded_at'], s['sha256'])):
        version = snapshot['metadata'].get('adapter_version')
        if version not in CHIP_VERSIONS:
            continue
        identity, raw_sha = raw_receipt(snapshot)
        payload = snapshot.get('chip_payload')
        cells = None
        if payload is not None:
            if payload['metadata'] != snapshot['metadata'] or payload['sources'] != snapshot['sources']:
                raise ValueError('chip archived receipt differs from snapshot')
            validate_chip(payload)
            cells = {}
            for row in payload['chip_metrics']:
                cells[row['stock_id'], row['metric']] = row
                key = (identity[0], row['stock_id'], row['metric'], row['trade_date'])
                if row['stock_id'] in stock_ids and key not in superseded:
                    prior = latest.get(key)
                    if prior is None or timestamp(prior['observed_at']) < identity[1]:
                        latest[key] = snapshot
        elif version.endswith('-2'):
            raise ValueError('missing immutable chip contribution')
        by_sha[snapshot['sha256']] = identity[0], raw_sha, snapshot['metadata'], cells
    seen = set()
    for fact in facts:
        info = by_sha.get(fact.get('input_snapshot_sha256'))
        if info is None:
            continue
        source, raw_sha, meta, cells = info
        if fact['kind'] != 'chip_metric':
            raise ValueError('invalid chip contribution kind')
        validate_cell(fact, source, raw_sha, meta, fact['source_available_at'])
        if cells is not None:
            key = (source, fact['stock_id'], fact['metric'], fact['trade_date'])
            if latest.get(key, {}).get('sha256') != fact['input_snapshot_sha256']:
                raise ValueError('chip fact uses a stale or superseded contribution')
            seen.add(key)
            if any(fact.get(field) is not None for field in ('currency', 'consolidation', 'value_basis',
                                                              'report_basis', 'statement_scope')):
                raise ValueError('unsupported chip cell definition')
            row = cells.get((fact['stock_id'], fact['metric']))
            if (row is None or any(row[key] != fact.get(key) for key in row if key != 'available_at')
                    or type(row['value']) != type(fact['value'])):
                raise ValueError('chip fact differs from immutable contribution')
    if seen != set(latest):
        raise ValueError('chip facts differ from selected contribution coverage')
