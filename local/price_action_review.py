"""Read-only interval review of closing prices in two audited private bundles."""
from collections import defaultdict

from .dates import timestamp
from .market_units import UNKNOWN
from .tpex_action_evidence import read_capture

ACTION_TYPES = ('ex_rights_dividend', 'split_reverse_split', 'capital_reduction')
DEFINITION = ('market', 'source_id', 'price_basis', 'price_unit', 'price_currency',
              'trading_scope', 'normalization_version')


def _endpoints(bundle):
    if bundle.facts is None:
        return {}
    target = bundle.facts['scope']['market']['trade_date']
    endpoints = {}
    for fact in bundle.facts['facts']:
        if fact['kind'] == 'market_price' and fact['trade_date'] == target:
            stock = fact['stock_id']
            endpoints[stock] = {key: fact.get(key) for key in (
                'id', 'trade_date', 'close', 'observed_at', 'raw_sha256', 'acquisition',
                *DEFINITION)}
            endpoints[stock].update(run=bundle.report['run'], dataset_url=fact['source']['dataset_url'])
    return endpoints


def review_prices(before, after, manifests=()):
    if len(manifests) > 32:
        raise ValueError('action receipt count exceeds budget')
    sources = []
    by_stock = defaultdict(list)
    cutoff = timestamp(after.report['known_at'])
    selection = set(before.graphs) | set(after.graphs)
    for manifest in manifests:
        source, actions = read_capture(manifest, cutoff, selection)
        if source and source not in sources:
            sources.append(source)
            for action in actions:
                by_stock[action['stock_id']].append(action)
    previous, current = _endpoints(before), _endpoints(after)
    rows = []
    for sid in sorted(selection):
        a, b = previous.get(sid), current.get(sid)
        same_day = bool(a and b and a['trade_date'] == b['trade_date'])
        unknown_coverage = [] if same_day else list(ACTION_TYPES)
        warnings = ['action_coverage_unknown'] if unknown_coverage else []
        differences = []
        actions = []
        status = 'same_trade_date' if same_day else 'coverage_unknown'
        if not a or not b:
            status = 'unavailable'
            warnings.append('missing_price_endpoint')
        else:
            if a['market'] == b['market'] == 'TPEX':
                actions = [event for event in by_stock[sid]
                           if a['trade_date'] < event['effective_date'] <= b['trade_date']]
            if actions:
                status = 'incomparable'
                warnings.append('action_in_price_interval')
            differences = [key for key in DEFINITION if a[key] != b[key]]
            if differences:
                status = 'incomparable'
                warnings.append('price_definition_changed')
            if any(a[key] in UNKNOWN or b[key] in UNKNOWN for key in DEFINITION):
                warnings.append('price_definition_unknown')
            if a['close'] is None or b['close'] is None:
                status = 'unavailable'
                warnings.append('missing_close')
            if a['trade_date'] > b['trade_date']:
                status = 'incomparable'
                warnings.append('reversed_trade_date_interval')
        rows.append({'stock_id': sid, 'before': a, 'after': b, 'warnings': warnings,
                     'actions': sorted(actions, key=lambda e: (e['effective_date'], e['observed_at'], e['raw_sha256'], e['row_number'])),
                     'status': status, 'definition_differences': differences,
                     'unknown_interval_coverage': unknown_coverage})
    return {'schema_version': 'price-action-review-1.0', 'known_at': after.report['known_at'],
            'sources': sorted(sources, key=lambda s: (s['observed_at'], s['raw_sha256'])), 'stocks': rows}
