"""Produce a private daily market-calendar coverage report from archived evidence and audited runs."""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from datetime import timedelta
from graphlib import TopologicalSorter
from pathlib import Path
from urllib.parse import urlsplit

from .bundle_audit import catalog
from .dates import iso_date, timestamp
from .event_study import save_report
from .research import guarded
from .research_history import strict_json, validate_symbols


MIB = 1024 * 1024
MAX_ROWS = 50_000
MAX_ENTRIES = 512


def bounded_bytes(path, limit):
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError('calendar source missing, empty or exceeds size budget')
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('calendar source exceeds size budget')
    return body


def validate_calendar_entry(entry):
    for field in ('id', 'source_url', 'date_semantics', 'path', 'sha256'):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError('missing calendar evidence field: ' + field)
    url = urlsplit(entry['source_url'])
    if url.scheme not in ('http', 'https') or not url.netloc:
        raise ValueError('invalid calendar source URL')
    if entry['market'] not in ('twse', 'tpex') or iso_date(entry['start']) > iso_date(entry['end']):
        raise ValueError('invalid calendar market or coverage')
    retrieved = timestamp(entry['retrieved_at'])
    if retrieved > timestamp(entry['saved_at']):
        raise ValueError('calendar retrieval after local save time')
    if entry.get('published_at') is not None and timestamp(entry['published_at']) > retrieved:
        raise ValueError('calendar publication after retrieval')
    days = entry.get('days', {})
    if not isinstance(days, dict) or any(
        not iso_date(entry['start']) <= iso_date(day) <= iso_date(entry['end']) or status not in ('open', 'closed')
        for day, status in days.items()
    ):
        raise ValueError('invalid explicit calendar date or status')
    weekdays = entry.get('open_weekdays', [])
    if (not isinstance(weekdays, list) or any(type(n) is not int or not 0 <= n <= 6 for n in weekdays)
            or len(weekdays) != len(set(weekdays))):
        raise ValueError('invalid calendar weekday rule')
    targets = entry.get('supersedes', [])
    if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
        raise ValueError('invalid calendar supersession')


def load_calendar(path, cutoff, budget):
    path = guarded(path)
    body = bounded_bytes(path, min(budget, 4 * MIB))
    budget -= len(body)
    document = strict_json(body)
    if document.get('schema_version') != 'market-calendar-1' or not isinstance(document.get('entries'), list):
        raise ValueError('invalid calendar schema')
    if len(document['entries']) > MAX_ENTRIES:
        raise ValueError('calendar version count exceeds budget')
    eligible, archived_hashes = [], {}
    for entry in document['entries']:
        if timestamp(entry['saved_at']) > cutoff:
            continue
        validate_calendar_entry(entry)
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('calendar archive path must be relative to the calendar')
        archive = guarded(path.parent / relative)
        if archive not in archived_hashes:
            raw = bounded_bytes(archive, min(budget, 32 * MIB))
            budget -= len(raw)
            archived_hashes[archive] = hashlib.sha256(raw).hexdigest()
        if archived_hashes[archive] != entry['sha256']:
            raise ValueError('calendar source checksum mismatch: ' + entry['id'])
        eligible.append(entry)
    by_id = {entry['id']: entry for entry in eligible}
    if len(by_id) != len(eligible):
        raise ValueError('duplicate calendar evidence ID')
    graph = TopologicalSorter()
    for entry in eligible:
        targets = entry.get('supersedes', [])
        if any(t not in by_id or by_id[t]['market'] != entry['market']
               or timestamp(by_id[t]['saved_at']) > timestamp(entry['saved_at']) for t in targets):
            raise ValueError('calendar supersession requires a known version of the same market')
        graph.add(entry['id'], *targets)
    graph.prepare()  # Reject cycles before any market decision.
    return eligible, budget


def calendar_day(entries, market, day):
    key = day.isoformat()
    active, other_market = {}, False
    superseded = set()
    for entry in entries:
        if not entry['start'] <= key <= entry['end']:
            continue
        status = entry.get('days', {}).get(key)
        if status is None and 'open_weekdays' in entry:
            status = 'open' if day.weekday() in entry['open_weekdays'] else 'closed'
        if status is None:
            continue
        if entry['market'] == market:
            active[entry['id']] = status
            superseded.update(entry.get('supersedes', []))
        else:
            other_market = True
    if not active:
        return {'market_status': 'unknown', 'reason': 'other_market_only' if other_market else 'no_calendar_entry',
                'evidence_ids': []}
    surviving = sorted(active.keys() - superseded)
    states = {active[version] for version in surviving}
    if len(states) != 1:
        return {'market_status': 'conflict', 'reason': 'contradictory_calendar_entries',
                'evidence_ids': surviving or sorted(active)}
    return {'market_status': states.pop(), 'reason': 'calendar_entry', 'evidence_ids': surviving}


def research_inputs(root, market, stock_ids, start, end, cutoff, max_runs, byte_budget):
    summary, bundles = catalog(root, max_runs=max_runs, max_bytes=byte_budget)
    if summary['counts']['invalid'] or not summary['latest_valid']:
        raise ValueError('invalid research catalog or latest pointer')
    inputs, observations, covered_until, market_witnesses = [], {}, {}, {}
    for bundle in sorted(bundles.values(), key=lambda b: (timestamp(b.report['completed_at']), b.report['run'])):
        report = bundle.report
        if timestamp(report['completed_at']) > cutoff:
            continue
        summary = bundle.summary()
        item = {key: summary[key] for key in ('run', 'known_at', 'completed_at', 'report_sha256', 'stock_ids', 'fact_scope')}
        inputs.append(item)
        if bundle.facts is None:
            continue
        scope = bundle.facts['scope']['market']
        item['market_scope'] = scope
        if scope['market'] != market:
            continue
        for sid in stock_ids.intersection(item['stock_ids']):
            covered_until[sid] = max(covered_until.get(sid, ''), scope['trade_date'])
        for fact in bundle.facts['facts']:
            if fact['kind'] != 'market_price':
                continue
            day = fact['trade_date']
            if start <= day <= end:
                market_witnesses.setdefault(day, {'id': fact['id'], 'stock_id': fact['stock_id'], 'run': report['run']})
                if fact['stock_id'] not in stock_ids:
                    continue
                observation = {key: fact[key] for key in ('id', 'source_id', 'observed_at', 'recorded_at',
                                                          'recorded_at_status', 'raw_sha256', 'close', 'volume_shares')}
                observation.update(run=report['run'], captured_at=report['completed_at'])
                observations.setdefault((fact['stock_id'], day), observation)
    return inputs, observations, covered_until, market_witnesses


def scope_reason(inputs, sid):
    if not inputs:
        return 'no_saved_run_by_cutoff'
    selected = [item for item in inputs if sid in item['stock_ids']]
    if not selected:
        return 'stock_not_selected'
    if all(item['fact_scope'] == 'display_graph_only' for item in selected):
        return 'display_graph_only'
    return 'market_not_in_scope'


def stock_day(status, observation, insufficient_scope):
    if insufficient_scope:
        return {'status': 'insufficient_scope', 'reason': insufficient_scope, 'observation': None}
    if status == 'conflict':
        return {'status': 'calendar_conflict', 'reason': 'calendar_unresolved', 'observation': observation}
    if observation is not None:
        if observation['close'] is None:
            state, reason = 'missing_close', 'saved_row_without_close'
        else:
            state, reason = 'observed', 'saved_market_fact'
    else:
        state, reason = {'open': ('missing_observation', 'cause_unknown'),
                         'closed': ('closed', 'market_closed'),
                         'unknown': ('unknown_calendar', 'calendar_unresolved')}[status]
    return {'status': state, 'reason': reason, 'observation': observation}


def build(root, calendar, market, symbols, start, end, as_of, *, max_runs=50, max_mib=256, max_rows=MAX_ROWS):
    stock_ids = validate_symbols(symbols)
    first, last, cutoff = iso_date(start), iso_date(end), timestamp(as_of)
    day_count = (last - first).days + 1
    if not 1 <= max_mib <= 4096 or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError('invalid coverage budget')
    if day_count < 1 or day_count * len(stock_ids) > max_rows:
        raise ValueError('invalid date range or row budget exceeded')
    eligible, remaining = load_calendar(calendar, cutoff, max_mib * MIB)
    if day_count * len(eligible) > 1_000_000:
        raise ValueError('calendar evaluation budget exceeded')
    inputs, observations, covered_until, market_witnesses = research_inputs(
        root, market, stock_ids, start, end, cutoff, max_runs, remaining)
    outside = {sid: 'after_market_trade_date' if sid in covered_until else scope_reason(inputs, sid)
               for sid in stock_ids}
    days, market_counts = [], Counter()
    stock_counts = {sid: Counter() for sid in sorted(stock_ids)}
    for offset in range(day_count):
        day = first + timedelta(days=offset)
        key = day.isoformat()
        row = {'date': key, **calendar_day(eligible, market, day), 'stocks': {}}
        if row['market_status'] == 'closed' and key in market_witnesses:
            row.update(market_status='conflict', reason='closed_with_saved_observation', conflicting_observation=market_witnesses[key])
        market_counts[row['market_status']] += 1
        for sid in sorted(stock_ids):
            limitation = outside[sid] if key > covered_until.get(sid, '') else None
            result = stock_day(row['market_status'], observations.get((sid, key)), limitation)
            row['stocks'][sid] = result
            stock_counts[sid][result['status']] += 1
        days.append(row)
    return {'schema_version': 'calendar-coverage-1', 'market': market, 'stock_ids': sorted(stock_ids),
            'start': start, 'end': end, 'as_of': as_of, 'calendar': {'versions': eligible},
            'inputs': inputs, 'days': days, 'market_counts': market_counts, 'stock_counts': stock_counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--calendar', type=Path, required=True)
    parser.add_argument('--market', choices=('twse', 'tpex'), required=True)
    parser.add_argument('--symbols', nargs='+', required=True)
    for option in ('start', 'end', 'as-of'):
        parser.add_argument('--' + option, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-runs', type=int, default=50)
    parser.add_argument('--max-mib', type=int, default=256)
    parser.add_argument('--max-rows', type=int, default=MAX_ROWS)
    args = parser.parse_args(argv)
    try:
        report = build(args.root, args.calendar, args.market, args.symbols, args.start, args.end, args.as_of,
                       max_runs=args.max_runs, max_mib=args.max_mib, max_rows=args.max_rows)
        save_report(report, args.output, args.root)
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(2, f'{parser.prog}: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
