"""Append and replay private, manually reviewed exchange notices for one daily quote."""
from contextlib import closing
import hashlib
import re
import sqlite3
from urllib.parse import urlsplit

from .dates import iso_date, timestamp
from .market_prices import MAX_BYTES, _atomic, _target, normalize, source_info
from .market_units import DEFINITION_KEYS
from .research_history import canonical, strict_json, utc_now
from .safety import exclusive_lock

TABLE = """CREATE TABLE IF NOT EXISTS market_price_notices (
    source_id TEXT NOT NULL, symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
    sequence INTEGER NOT NULL, entry_json TEXT NOT NULL,
    PRIMARY KEY(source_id, symbol, trade_date, sequence))"""
MAX_NOTICE_BYTES = 64 * 1024
MAX_ENTRIES = 256
FIELDS = {'schema_version', 'action', 'market', 'source_id', 'symbol', 'trade_date',
          'published_at', 'observed_at', 'effective_at', 'target_raw_sha256', 'target_record_sha256',
          'parent_notice_sha256', 'replacement_raw_sha256', 'evidence_url', 'evidence_sha256', 'locator'}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def read_bytes(path, limit, budget=None):
    with _target(path).open('rb') as stream:
        body = stream.read(limit + 1)
    if not body or len(body) > limit:
        raise ValueError('market notice file empty or over byte budget')
    if budget:
        budget.consume('raw_bytes', len(body))
    return body


def validate_notice(notice, feed, symbol, day):
    source = source_info(feed)
    if (not isinstance(notice, dict) or set(notice) - {'replacement_unit_review'} != FIELDS
            or notice['schema_version'] != 'market-notice-1.0'
            or (notice['source_id'], notice['market'], notice['symbol'], notice['trade_date'])
            != (source['source_id'], feed, symbol, day)):
        raise ValueError('market notice differs from requested source, market, symbol or day')
    iso_date(day)
    if notice['action'] not in ('correct', 'withdraw', 'republish'):
        raise ValueError('unsupported market notice action')
    for key in ('evidence_sha256', 'target_raw_sha256', 'target_record_sha256', 'parent_notice_sha256', 'replacement_raw_sha256'):
        value = notice[key]
        if key == 'parent_notice_sha256' and value is None:
            continue
        if key == 'replacement_raw_sha256' and notice['action'] == 'withdraw':
            if value is not None or 'replacement_unit_review' in notice:
                raise ValueError('withdrawal cannot include a replacement')
            continue
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('invalid market notice checksum')
    if notice['evidence_sha256'] in (notice['target_raw_sha256'], notice['replacement_raw_sha256']):
        raise ValueError('market notice evidence must identify a distinct source notice')
    url = urlsplit(notice['evidence_url'])
    if (url.scheme != 'https' or url.netloc != urlsplit(source['resource_url']).netloc
            or not url.path.strip('/') or not isinstance(notice['locator'], str)
            or not 1 <= len(notice['locator'].strip()) <= 2000):
        raise ValueError('notice requires reviewed exchange origin and evidence locator')
    if timestamp(notice['published_at']) > timestamp(notice['observed_at']):
        raise ValueError('market notice observed before publication')
    timestamp(notice['effective_at'])


def entries_for(conn, source_id, symbol, day, budget=None):
    kind = conn.execute("SELECT type FROM sqlite_master WHERE name='market_price_notices'").fetchone()
    if kind is None:
        return []
    if kind[0] != 'table':
        raise ValueError('invalid market notice table')
    sql = """SELECT length(CAST(entry_json AS BLOB)), substr(CAST(entry_json AS BLOB),1,?)
             FROM market_price_notices WHERE source_id=? AND symbol=? AND trade_date=?
             ORDER BY sequence LIMIT ?"""
    entries = []
    for size, body in conn.execute(sql, (MAX_NOTICE_BYTES, source_id, symbol, day, MAX_ENTRIES+1)):
        if size > MAX_NOTICE_BYTES or len(entries) >= MAX_ENTRIES:
            raise ValueError('market notice history exceeds budget')
        if budget:
            budget.consume('record_bytes', size)
            budget.consume('rows', 1)
        entries.append(strict_json(body))
    return entries


def activation(entry):
    notice = entry['notice']
    return max(timestamp(entry['recorded_at']), timestamp(notice['effective_at']),
               timestamp(notice['observed_at']))


def check_transition(entry, prior):
    notice = entry['notice']
    if digest(canonical(notice)) != entry['notice_sha256']:
        raise ValueError('market notice manifest checksum mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}', entry['base_record_sha256']):
        raise ValueError('invalid market notice original record checksum')
    if notice['action'] == 'withdraw':
        if entry['replacement_record_sha256'] is not None:
            raise ValueError('withdrawn notice has a replacement record')
    elif not re.fullmatch(r'[0-9a-f]{64}', entry['replacement_record_sha256']):
        raise ValueError('invalid market notice replacement record checksum')
    if timestamp(notice['observed_at']) > timestamp(entry['recorded_at']):
        raise ValueError('market notice observation is later than registration')
    if (set(entry['definition']) != set(DEFINITION_KEYS)
            or timestamp(entry['base_observed_at']) > timestamp(notice['observed_at'])):
        raise ValueError('invalid market notice target definition or time')
    expected_parent = prior['notice_sha256'] if prior else None
    if notice['parent_notice_sha256'] != expected_parent:
        raise ValueError('market notice parent mismatch')
    if bool(prior and prior['notice']['action'] == 'withdraw') != (notice['action'] == 'republish'):
        raise ValueError('market notice incompatible with withdrawn state')
    if not prior and entry['base_record_sha256'] != notice['target_record_sha256']:
        raise ValueError('market notice target record mismatch')
    if prior:
        previous = prior['notice']
        if ((previous['replacement_raw_sha256'] or previous['target_raw_sha256']) != notice['target_raw_sha256']
                or entry['definition'] != prior['definition'] or entry['base_observed_at'] != prior['base_observed_at']
                or entry['base_record_sha256'] != prior['base_record_sha256']
                or notice['target_record_sha256'] != (prior['replacement_record_sha256'] or previous['target_record_sha256'])):
            raise ValueError('market notice target or definition mismatch')
        if (timestamp(previous['published_at']) >= timestamp(notice['published_at'])
                or timestamp(previous['observed_at']) > timestamp(notice['observed_at'])
                or timestamp(prior['recorded_at']) > timestamp(entry['recorded_at'])
                or activation(prior) > activation(entry)):
            raise ValueError('conflicting market notice chronology')


def replacement_record(body, notice, definition):
    if digest(body) != notice['replacement_raw_sha256']:
        raise ValueError('market notice replacement checksum mismatch')
    record = normalize(body, notice['market'], [notice['symbol']], notice['trade_date'],
                       notice['observed_at'], unit_review=notice.get('replacement_unit_review'))['records'][0]
    if {k: record.get(k) for k in DEFINITION_KEYS} != definition:
        raise ValueError('market notice replacement definition mismatch')
    return record


def register(args):
    from .market_graph import HistoryBudget, read_prices
    if len(args.symbols) != 1 or not args.notice_evidence or args.unit_review:
        raise ValueError('a notice needs one symbol, an evidence file and any unit review in its manifest')
    symbol, day = args.symbols[0], args.expected_date
    notice = strict_json(read_bytes(args.notice, MAX_NOTICE_BYTES))
    validate_notice(notice, args.market, symbol, day)
    evidence = read_bytes(args.notice_evidence, MAX_BYTES)
    if digest(evidence) != notice['evidence_sha256']:
        raise ValueError('market notice evidence checksum mismatch')
    if bool(args.input) != (notice['action'] != 'withdraw'):
        raise ValueError('market notice replacement file required only for correct and republish')
    replacement = read_bytes(args.input, MAX_BYTES) if args.input else None
    db, root = _target(args.db), _target(args.output)
    origin = root / notice['source_id']
    checksum = digest(canonical(notice))
    with exclusive_lock(root), closing(sqlite3.connect(db.as_uri()+'?mode=rw', uri=True)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(TABLE)
        entries = entries_for(conn, notice['source_id'], symbol, day)
        recorded_at = utc_now()
        current = read_prices(db, args.market, [symbol], day, recorded_at, root, budget=HistoryBudget())
        existing = next((e for e in entries if e['notice_sha256'] == checksum), None)
        if existing:
            if replacement is not None:
                replacement_record(replacement, notice, existing['definition'])
            return existing
        if len(entries) >= MAX_ENTRIES:
            raise ValueError('market notice history exceeds budget')
        prior = entries[-1] if entries else None
        if prior:
            definition, base_observed = prior['definition'], prior['base_observed_at']
            base_sha = prior['base_record_sha256']
        else:
            base = current[0]
            if base['raw_sha256'] != notice['target_raw_sha256']:
                raise ValueError('market notice target is stale or unknown')
            definition = {k: base['record'].get(k) for k in DEFINITION_KEYS}
            base_observed = base['observed_at']
            base_sha = digest(canonical(base['record']))
        new_record = replacement_record(replacement, notice, definition) if replacement is not None else None
        entry = dict(notice=notice, notice_sha256=checksum, recorded_at=recorded_at,
                     definition=definition, base_observed_at=base_observed, base_record_sha256=base_sha,
                     replacement_record_sha256=digest(canonical(new_record)) if new_record is not None else None)
        check_transition(entry, prior)
        encoded = canonical(entry)
        if len(encoded) > MAX_NOTICE_BYTES:
            raise ValueError('market notice exceeds byte budget')
        files = [(origin/'notices'/(notice['evidence_sha256']+'.bin'), evidence)]
        if replacement is not None:
            files.append((origin/(notice['replacement_raw_sha256']+'.csv'), replacement))
        for path, body in files:
            path = _target(path)
            if path.exists():
                if read_bytes(path, MAX_BYTES) != body:
                    raise ValueError('immutable market notice file changed')
            else:
                _atomic(path, body)
        conn.execute('INSERT INTO market_price_notices VALUES(?,?,?,?,?)',
                     (notice['source_id'], symbol, day, len(entries)+1, encoded.decode()))
        return entry


def resolve(entries, bases, latest, feed, symbol, day, cutoff, snapshot_dir, budget, history):
    prior = None
    for entry in entries:
        if timestamp(entry['recorded_at']) > cutoff:
            continue
        notice = entry['notice']
        validate_notice(notice, feed, symbol, day)
        check_transition(entry, prior)
        if snapshot_dir is None:
            raise ValueError('market notice replay requires original snapshots')
        origin = _target(snapshot_dir)/notice['source_id']
        evidence = read_bytes(origin/'notices'/(notice['evidence_sha256']+'.bin'), MAX_BYTES, budget)
        if digest(evidence) != notice['evidence_sha256']:
            raise ValueError('market notice evidence checksum mismatch')
        if prior is None:
            latest = bases.get((notice['target_raw_sha256'], entry['base_observed_at']))
            if (not latest or {k: latest['record'].get(k) for k in DEFINITION_KEYS} != entry['definition']
                    or digest(canonical(latest['record'])) != entry['base_record_sha256']):
                raise ValueError('market notice original observation or definition missing')
        record = None
        if notice['replacement_raw_sha256']:
            raw = read_bytes(origin/(notice['replacement_raw_sha256']+'.csv'), MAX_BYTES, budget)
            record = replacement_record(raw, notice, entry['definition'])
            if digest(canonical(record)) != entry['replacement_record_sha256']:
                raise ValueError('market notice replacement record mismatch')
        if history is not None:
            history.append(entry)
        if activation(entry) <= cutoff:
            latest = None if record is None else {
                'record': record, 'raw_snapshot_verified': True, 'source': source_info(feed),
                'observed_at': notice['observed_at'], 'recorded_at': entry['recorded_at'],
                'available_at': activation(entry).isoformat(timespec='microseconds'),
                'notice_sha256': entry['notice_sha256'], 'source_available_at': notice['published_at'],
                'raw_sha256': notice['replacement_raw_sha256'], 'acquisition': 'local_file_unverified'}
        prior = entry
    return latest


def active_heads(entries, cutoff):
    heads = {}
    for entry in entries:
        n = entry['notice']
        if activation(entry) <= cutoff:
            heads[n['symbol'], n['trade_date']] = entry
    return heads


def audit_entries(entries, facts, scope, cutoff, record_digests):
    feed = scope['market']['market']
    market_facts = {(f['symbol'], f['trade_date']): f for f in facts if f['kind'] == 'market_price'}
    previous, originals = {}, {}
    for entry in entries:
        notice = entry['notice']
        key = symbol, day = notice['symbol'], notice['trade_date']
        if ('TW:'+symbol not in scope['stock_ids'] or day > scope['market']['trade_date']
                or timestamp(entry['recorded_at']) > cutoff):
            raise ValueError('market notice outside archived scope')
        validate_notice(notice, feed, symbol, day)
        check_transition(entry, previous.get(key))
        previous[key] = entry
        originals.setdefault(key, entry)
    active = active_heads(entries, cutoff)
    for key, first in originals.items():
        head = active.get(key)
        fact = market_facts.get(key)
        if head is None:
            if (not fact or fact['raw_sha256'] != first['notice']['target_raw_sha256']
                    or fact['observed_at'] != first['base_observed_at']
                    or record_digests[key] != first['base_record_sha256']):
                raise ValueError('pending market notice target differs from fact')
        elif head['notice']['action'] == 'withdraw':
            if fact:
                raise ValueError('withdrawn market fact still present')
            continue
        else:
            notice = head['notice']
            if (not fact or fact.get('notice_sha256') != head['notice_sha256']
                    or record_digests[key] != head['replacement_record_sha256']
                    or fact['raw_sha256'] != notice['replacement_raw_sha256']
                    or fact['observed_at'] != notice['observed_at'] or fact['recorded_at'] != head['recorded_at']
                    or fact['source_available_at'] != notice['published_at']
                    or timestamp(fact['available_at']) != activation(head)):
                raise ValueError('active market notice differs from archived fact')
        if {k: fact.get(k) for k in DEFINITION_KEYS} != first['definition']:
            raise ValueError('market notice definition differs from archived fact')
    for key, fact in market_facts.items():
        if 'notice_sha256' in fact and key not in active:
            raise ValueError('unresolved archived market notice')


def inspect_prices(args):
    from .dates import analysis_cutoff
    from .market_graph import HistoryBudget, read_prices
    cutoff = analysis_cutoff(args.known_at)
    history = []
    observations = read_prices(args.db, args.market, args.symbols, args.expected_date, args.known_at,
                               args.output, budget=HistoryBudget(), notice_history=history)
    for item in observations:
        item['record_sha256'] = digest(canonical(item['record']))
    heads = active_heads(history, cutoff)
    for entry in history:
        n = entry['notice']
        if activation(entry) > cutoff:
            entry['status'] = 'pending_effective'
        elif heads[n['symbol'], n['trade_date']] is not entry:
            entry['status'] = 'superseded'
        else:
            entry['status'] = 'withdrawn' if n['action'] == 'withdraw' else 'active'
    return {'known_at': args.known_at, 'notices': history, 'observations': observations}


def audit_bundle_prices(document, report, graphs, alerts):
    """Match the report, displayed quote and reminder evidence to audited daily facts."""
    trade_date = document['scope']['market']['trade_date']
    facts = {(f['symbol'], f['trade_date']): f for f in document['facts'] if f['kind'] == 'market_price'}
    selected = {key: f for key, f in facts.items() if key[1] == trade_date}
    report_fields = ('source_id', 'symbol', 'trade_date', 'observed_at', 'raw_sha256', 'acquisition', 'raw_snapshot_verified')
    optional = ('notice_sha256', 'recorded_at', 'available_at', 'source_available_at')
    expected = [{**{k: f[k] for k in report_fields}, **({k: f[k] for k in optional} if 'notice_sha256' in f else {})}
                for _, f in sorted(selected.items())]
    if report.get('market_observations') != expected or report['counts']['market_nodes'] != len(expected):
        raise ValueError('market notice selected observation report mismatch')
    for sid, graph in graphs.items():
        for node in graph['nodes']:
            if node['type'] == 'market_price':
                fact = selected.get((node['symbol'], node['trade_date']))
                if not fact or any(node.get(k) != fact.get(k) for k in (*report_fields, 'close', 'volume_shares', 'notice_sha256')):
                    raise ValueError('market notice graph observation mismatch')
        if not alerts:
            continue
        for check in alerts['stocks'][sid]['categories']['price_volume']:
            if ((sid[3:], trade_date) not in selected
                    and (check['reason'] != 'target_price_missing_at_cutoff' or check['evidence'])):
                raise ValueError('market notice withdrawal differs from reminder')
            for ref in check['evidence']:
                fact = facts.get((sid[3:], ref['period']))
                if not fact or any(ref.get(k) != fact.get(k) for k in (
                        'source_id', 'observed_at', 'raw_sha256', 'close', 'volume_shares', 'notice_sha256')):
                    raise ValueError('market notice reminder evidence mismatch')
