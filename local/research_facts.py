"""Versioned private numeric facts, independent of display graphs.

Null unit/currency/scope/basis means unknown, never a guessed conversion.
Only the bundle auditor exposes validated facts to downstream local readers.
"""
from __future__ import annotations

import copy
import hashlib

from .research_history import canonical
from .financial_definitions import financial_definition

SCHEMA = 'research-facts-1.0'
PRODUCER = 'private-research-1'
MAX_FACTS = 100000
TIME_SEMANTICS = {
    'available_at': 'max(source_available_at, observed_at, recorded_at) for normalized facts; observed_at for market facts',
    'recorded_at': 'first local normalized ledger registration; null means unknown for market facts',
    'completed_at': 'bundle save time only; never historical availability',
}


def fact_id(fact):
    key = [fact['kind'], fact['stock_id'], fact['source_id'], fact.get('metric'),
           fact.get('period_end', fact.get('trade_date')), fact.get('period_type')]
    return 'fact:' + hashlib.sha256(canonical(key)).hexdigest()


def coverage(facts, stock_ids):
    result = {sid: {'financial_metric': 0, 'chip_metric': 0, 'market_price': 0} for sid in sorted(stock_ids)}
    for fact in facts:
        result[fact['stock_id']][fact['kind']] += 1
    return result


def build_facts(payload, quality, stock_ids, known_at, prices=(), market=None, trade_date=None):
    if len(payload['financial_metrics']) + len(payload['chip_metrics']) + len(prices) > MAX_FACTS:
        raise ValueError('facts_entry_budget_exceeded')
    sources = {snapshot['sha256']: {source['source_id']: source for source in snapshot['sources']}
               for snapshot in quality['snapshots']}
    facts = []
    for group, kind in (('financial_metrics', 'financial_metric'), ('chip_metrics', 'chip_metric')):
        for record in payload[group]:
            fact = financial_definition(copy.deepcopy(record))
            fact.update(kind=kind, source=copy.deepcopy(sources[record['input_snapshot_sha256']][record['source_id']]),
                        recorded_at=record['registered_at'], recorded_at_status='known')
            for field in ('unit', 'currency', 'consolidation', 'value_basis'):
                fact.setdefault(field, None)
            fact['id'] = fact_id(fact)
            facts.append(fact)
    for item in prices:
        fact = {**copy.deepcopy(item['record']), 'kind': 'market_price',
                'stock_id': 'TW:'+item['record']['symbol'], 'source_id': item['source']['source_id'],
                'source': copy.deepcopy(item['source']), 'observed_at': item['observed_at'],
                'available_at': item['observed_at'], 'source_available_at': None,
                'recorded_at': None, 'recorded_at_status': 'unknown',
                'raw_sha256': item['raw_sha256'], 'raw_snapshot_verified': item['raw_snapshot_verified'],
                'acquisition': item['acquisition']}
        fact['id'] = fact_id(fact)
        facts.append(fact)
    return {'schema_version': SCHEMA, 'producer': PRODUCER,
            'scope': {'stock_ids': sorted(stock_ids), 'known_at': known_at,
                      'market': {'included': market is not None, 'market': market, 'trade_date': trade_date}},
            'time_semantics': TIME_SEMANTICS.copy(),
            'normalized_snapshots': copy.deepcopy(quality['snapshots']),
            'coverage': coverage(facts, stock_ids), 'facts': sorted(facts, key=lambda f: f['id'])}


def load_market_history(database, feed, symbols, trade_date, known_at, snapshot_dir, budget):
    """All locally saved eligible dates, with bounded work and no backfill IO."""
    from contextlib import closing
    from pathlib import Path
    import sqlite3
    from .dates import iso_date, timestamp
    from .market_prices import source_info
    from .market_graph import read_prices
    source = source_info(feed)
    target, cutoff = iso_date(trade_date), timestamp(known_at)
    by_day = {}
    with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA trusted_schema=OFF')
        conn.set_progress_handler(budget.progress, 1000)
        sql = ('SELECT symbol,trade_date,observed_at FROM market_price_observations '
               'WHERE source_id=? AND trade_date<=? AND symbol IN ('+','.join('?' for _ in symbols)+') LIMIT 100001')
        try:
            for symbol, day, observed in conn.execute(sql, (source['source_id'], trade_date, *symbols)):
                budget.consume('rows', 1)
                if iso_date(day) > target:
                    raise ValueError('future market date')
                if timestamp(observed) <= cutoff:
                    by_day.setdefault(day, set()).add(symbol)
                    if len(by_day) > 5000:
                        raise ValueError('market history date budget exceeded')
        except sqlite3.OperationalError as exc:
            if budget.exhausted:
                raise ValueError('market history SQL work budget exceeded') from exc
            raise
    result = []
    for day, members in sorted(by_day.items()):
        result.extend(read_prices(database, feed, sorted(members), day, known_at,
                                  snapshot_dir=snapshot_dir, budget=budget))
    return result


def validate_facts(document, report):
    if document.get('schema_version') != SCHEMA or report['research_facts'].get('schema_version') != SCHEMA:
        raise ValueError('facts_schema_unsupported')
    if document.get('producer') != PRODUCER:
        raise ValueError('facts_producer_unsupported')
    import math
    import re
    from zoneinfo import ZoneInfo
    from .dates import iso_date, timestamp

    def require(condition, code):
        if not condition:
            raise ValueError('facts_'+code)

    stock_ids = report['selection']['stock_ids']
    cutoff = timestamp(report['known_at'])
    scope = document.get('scope', {})
    require(isinstance(scope, dict), 'invalid_scope')
    require(scope.get('stock_ids') == stock_ids and scope.get('known_at') == report['known_at'], 'scope_mismatch')
    require(document.get('time_semantics') == TIME_SEMANTICS, 'time_semantics_mismatch')
    market = scope.get('market', {})
    require(isinstance(market, dict), 'invalid_market_scope')
    require(type(market.get('included')) is bool, 'invalid_market_scope')
    if market['included']:
        require(market.get('market') in ('twse', 'tpex'), 'invalid_market_scope')
        require(iso_date(market['trade_date']) <= cutoff.astimezone(ZoneInfo('Asia/Taipei')).date(), 'future_market_scope')
    else:
        require(market == {'included': False, 'market': None, 'trade_date': None}, 'invalid_market_scope')
    require(market == report['research_facts'].get('market'), 'market_scope_mismatch')
    snapshots = document.get('normalized_snapshots')
    require(isinstance(snapshots, list) and snapshots == report['quality']['snapshots'], 'snapshot_provenance_mismatch')
    by_hash = {}
    for snapshot in snapshots:
        require(isinstance(snapshot, dict), 'invalid_snapshot')
        checksum = snapshot.get('sha256')
        require(isinstance(checksum, str) and re.fullmatch(r'[0-9a-f]{64}', checksum) and checksum not in by_hash, 'invalid_snapshot_identity')
        observed, recorded = timestamp(snapshot['observed_at']), timestamp(snapshot['recorded_at'])
        require(observed <= recorded <= cutoff, 'future_snapshot_time')
        require(timestamp(snapshot['metadata']['observed_at']) == observed, 'snapshot_observation_mismatch')
        by_hash[checksum] = snapshot
    facts = document.get('facts')
    require(isinstance(facts, list), 'invalid_entries')
    require(len(facts) <= MAX_FACTS, 'entry_budget_exceeded')
    require(type(report['research_facts'].get('count')) is int and len(facts) == report['research_facts']['count'], 'count_mismatch')
    ids = set()
    for fact in facts:
        require(isinstance(fact, dict) and fact.get('stock_id') in stock_ids, 'foreign_stock')
        kind = fact.get('kind')
        require(kind in ('financial_metric', 'chip_metric', 'market_price'), 'unknown_kind')
        require(isinstance(fact.get('source_id'), str) and bool(fact['source_id']), 'invalid_source')
        require(isinstance(fact.get('source'), dict) and fact['source'].get('source_id') == fact['source_id']
                and isinstance(fact['source'].get('provider'), str) and bool(fact['source']['provider']), 'unresolved_source')
        require(fact.get('id') == fact_id(fact) and fact['id'] not in ids, 'invalid_identity')
        ids.add(fact['id'])
        available, observed = timestamp(fact['available_at']), timestamp(fact['observed_at'])
        require(observed <= available <= cutoff, 'future_fact_time')
        if kind != 'market_price':
            financial_definition(fact)
            require(fact.get('recorded_at_status') == 'known' and isinstance(fact.get('recorded_at'), str), 'unknown_registration')
            recorded, source_available = timestamp(fact['recorded_at']), timestamp(fact['source_available_at'])
            require(available == max(source_available, observed, recorded) and recorded <= cutoff, 'availability_mismatch')
            snapshot = by_hash.get(fact.get('input_snapshot_sha256'))
            require(snapshot is not None and fact['observed_at'] == snapshot['observed_at']
                    and fact['recorded_at'] == snapshot['recorded_at']
                    and fact.get('registered_at') == fact['recorded_at'], 'unresolved_snapshot')
            require(isinstance(snapshot.get('sources'), list) and
                    fact['source'] in snapshot['sources'], 'source_provenance_mismatch')
            require(type(fact.get('value')) in (int, float) and math.isfinite(fact['value']), 'invalid_value')
            require(isinstance(fact.get('metric'), str) and bool(fact['metric']), 'invalid_metric')
            day = iso_date(fact['period_end'] if kind == 'financial_metric' else fact['trade_date'])
            require(day <= source_available.astimezone(ZoneInfo('Asia/Taipei')).date(), 'future_period')
            if kind == 'financial_metric':
                require(isinstance(fact.get('period_type'), str) and bool(fact['period_type']), 'invalid_period_type')
            for field in ('unit', 'currency', 'consolidation', 'value_basis'):
                require(field in fact and (fact[field] is None or isinstance(fact[field], str)), 'invalid_definition')
        else:
            require(market['included'] and fact['stock_id'] == 'TW:'+fact['symbol'], 'market_coverage_mismatch')
            require(fact.get('recorded_at') is None and fact.get('recorded_at_status') == 'unknown'
                    and fact.get('source_available_at') is None and available == observed, 'invented_market_time')
            require(iso_date(fact['trade_date']) <= iso_date(market['trade_date']), 'future_market_date')
            require(fact.get('raw_snapshot_verified') is True and
                    isinstance(fact.get('raw_sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', fact['raw_sha256']), 'invalid_raw_evidence')
            require(fact.get('acquisition') in ('https_download', 'local_file_unverified'), 'invalid_acquisition')
            _validate_market_fact(fact, market['market'])
    from .source_revisions import audit_revisions
    audit_revisions(snapshots, report['quality'].get('source_revisions', []), facts, stock_ids, cutoff)
    require(document.get('coverage') == coverage(facts, stock_ids), 'coverage_mismatch')
    for group, kind in (('financial_metrics', 'financial_metric'), ('chip_metrics', 'chip_metric')):
        require(sum(f['kind'] == kind for f in facts) == report['quality']['counts'][group], 'replay_count_mismatch')


def _validate_market_fact(fact, feed):
    import csv
    import io
    from .market_prices import FEEDS, FIELDS, normalize, source_info
    if fact['source'] != source_info(feed):
        raise ValueError('facts_market_source_mismatch')
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(FEEDS[feed]['columns'])
    writer.writerow([fact.get(key) if fact.get(key) is not None else '--' for key in FIELDS])
    record = normalize(buffer.getvalue().encode(), feed, [fact['symbol']], fact['trade_date'], fact['observed_at'])['records'][0]
    from .market_units import reviewed_record
    record = reviewed_record(record, fact, fact["source_id"], fact["raw_sha256"])
    if any(key not in fact or fact[key] != value or type(fact[key]) != type(value) for key, value in record.items()):
        raise ValueError('facts_market_normalization_mismatch')
