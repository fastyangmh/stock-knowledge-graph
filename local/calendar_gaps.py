"""Explain a missing audited quote using archived stock and collection records."""
from collections import Counter, defaultdict
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .calendar_archive import load_evidence
from .dates import iso_date, timestamp
from .market_prices import FEEDS
from .research_history import validate_symbols


def validate_entry(entry):
    for field in ('id', 'locator', 'source_id'):
        if not isinstance(entry.get(field), str) or not 0 < len(entry[field].strip()) <= 256:
            raise ValueError('missing or invalid gap evidence field: ' + field)
    day = iso_date(entry['date'])
    kind = entry['kind']
    taipei = ZoneInfo('Asia/Taipei')
    if kind in ('no_trade', 'fetch_failed') and timestamp(entry['saved_at']).astimezone(taipei).date() < day:
        raise ValueError('daily outcome predates the trading date')
    if entry['market'] not in FEEDS:
        raise ValueError('invalid gap evidence market')
    if kind in ('due', 'fetch_failed', 'missing_file'):
        if 'stock_id' in entry:
            raise ValueError('feed-wide evidence must apply to the whole feed')
        if kind == 'due':
            if timestamp(entry['due_at']).astimezone(taipei).date() < day:
                raise ValueError('daily quote due before the trading date')
        elif kind == 'fetch_failed':
            if any(not isinstance(entry.get(k), str) or not entry[k].strip() for k in ('run_id', 'failure')):
                raise ValueError('collection failure requires an execution record')
        else:
            if timestamp(entry['checked_at']) > timestamp(entry['saved_at']):
                raise ValueError('inventory checked after evidence was saved')
            target = entry['quote_file']
            for field in ('expected_files', 'missing_files'):
                files = entry[field]
                if (not isinstance(target, str) or not target.strip() or not isinstance(files, list)
                        or not all(isinstance(f, str) and f.strip() for f in files) or target not in files):
                    raise ValueError('inventory requires expected and missing quote file')
        return
    if kind not in ('suspended', 'no_trade'):
        raise ValueError('invalid gap evidence kind')
    sid = entry['stock_id']
    if not isinstance(sid, str) or sid not in validate_symbols([sid.removeprefix('TW:')]):
        raise ValueError('invalid gap evidence stock ID')
    url = urlsplit(entry['source_url'])
    domain = {'twse': 'twse.com.tw', 'tpex': 'tpex.org.tw'}[entry['market']]
    if url.scheme != 'https' or not (url.hostname == domain or (url.hostname or '').endswith('.' + domain)):
        raise ValueError('stock status requires official exchange evidence')


def load_gaps(path, cutoff, budget, market, start, end, stock_ids):
    index = defaultdict(list)
    if path is None:
        return [], index, budget
    entries, budget = load_evidence(path, cutoff, budget, 'market-gap-evidence-1', validate_entry)
    if len({e['id'] for e in entries}) != len(entries):
        raise ValueError('duplicate gap evidence ID')
    selected = []
    for entry in entries:
        if (entry['market'] == market and entry['source_id'] == FEEDS[market]['source_id']
                and start <= entry['date'] <= end and ('stock_id' not in entry or entry['stock_id'] in stock_ids)):
            selected.append(entry)
            index[entry['date'], entry.get('stock_id')].append(entry)
    return selected, index, budget


def diagnose(market_status, row, index, day, sid, cutoff):
    diagnosis = {'stock_state': 'unknown', 'stock_evidence_ids': [], 'acquisition': {},
                 'timing': 'not_applicable', 'timing_evidence_ids': [], 'gap': 'not_applicable'}
    beyond_trade_date = row['reason'] == 'after_market_trade_date'
    if market_status != 'open' or (row['status'] == 'insufficient_scope' and not beyond_trade_date):
        return diagnosis
    feed = index.get((day, None), [])
    deadlines = {timestamp(e['due_at']) for e in feed if e['kind'] == 'due'}
    if beyond_trade_date and not deadlines:
        return diagnosis
    deadline = next(iter(deadlines)) if len(deadlines) == 1 else None
    diagnosis['timing_evidence_ids'] = sorted(e['id'] for e in feed if e['kind'] == 'due')
    if deadline is None:
        timing = 'due_conflict' if deadlines else 'due_unknown'
    elif row['observation']:
        captured = timestamp(row['observation']['captured_at'])
        timing = 'late_first_bundle' if captured > deadline else 'saved_by_due'
    elif cutoff < deadline:
        timing = 'pending'
    else:
        timing = 'due_passed_outside_scope' if beyond_trade_date else 'overdue_unobserved'
    diagnosis['timing'] = timing
    if beyond_trade_date:
        if timing == 'pending':
            diagnosis['gap'] = 'pending'
        return diagnosis
    entries = index.get((day, sid), [])
    if entries:
        states = {e['kind'] for e in entries}
        observation = row['observation']
        contradicted = observation and (observation['trades'] > 0 or observation['volume_shares'] > 0)
        if contradicted:
            state = 'conflict'
        else:
            state = 'suspended' if 'suspended' in states else 'no_trade'
        diagnosis.update(stock_state=state, stock_evidence_ids=sorted(e['id'] for e in entries))
    acquisition = defaultdict(list)
    for entry in feed:
        kind = entry['kind']
        if kind == 'fetch_failed' or (kind == 'missing_file' and deadline and timestamp(entry['checked_at']) >= deadline):
            acquisition[kind].append(entry['id'])
    diagnosis['acquisition'] = {kind: sorted(ids) for kind, ids in acquisition.items()}
    if row['status'] == 'missing_observation':
        if timing == 'pending':
            diagnosis['gap'] = 'pending'
        elif acquisition or diagnosis['stock_state'] in ('suspended', 'no_trade'):
            diagnosis['gap'] = 'explained'
        else:
            diagnosis['gap'] = 'unresolved'
    return diagnosis


def diagnostic_counts(days, stock_ids):
    counts = {}
    for sid in sorted(stock_ids):
        rows = [day['stocks'][sid]['diagnosis'] for day in days]
        counts[sid] = {field: Counter(row[field] for row in rows) for field in ('stock_state', 'timing', 'gap')}
        counts[sid]['acquisition'] = Counter(kind for row in rows for kind in row['acquisition'])
    return counts
