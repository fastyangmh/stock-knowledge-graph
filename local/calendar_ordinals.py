"""Compare the event study's saved quote positions with a market calendar."""
from zoneinfo import ZoneInfo

from .dates import iso_date, timestamp
from .event_outcomes import post_event_quotes, saved_facts
from .event_study import analyze


TAIPEI = ZoneInfo('Asia/Taipei')


def availability(day, stock, cutoff_day):
    if (day['market_status'] == 'open' and stock['observation'] is None
            and (stock['status'] == 'missing_observation' or stock['reason'] == 'after_market_trade_date')):
        if day['date'] > cutoff_day or stock.get('diagnosis', {}).get('timing') == 'pending':
            return 'pending'
    return stock['status']


# A known gap disproves continuity even when a different date is unresolved.
CONTINUITY_PRIORITY = {'no_sessions': 0, 'complete': 1, 'pending': 2, 'unknown': 3, 'incomplete': 4}


def daily_continuity(market, status):
    if market == 'closed':
        return 'no_sessions'
    if market != 'open' or status == 'insufficient_scope':
        return 'unknown'
    if status == 'missing_observation':
        return 'incomplete'
    if status == 'pending':
        return 'pending'
    return 'complete'


def range_positions(days, stock_ids, as_of):
    """Independent cumulative market ordinals and per-stock coverage, inclusive of start."""
    cutoff_day = timestamp(as_of).astimezone(TAIPEI).date().isoformat()
    sessions = 0
    calendar_known = True
    continuity = dict.fromkeys(stock_ids, 'no_sessions')
    closes = dict.fromkeys(stock_ids, 'no_sessions')
    for day in days:
        market = day['market_status']
        if market in ('unknown', 'conflict'):
            calendar_known = False
        if market == 'open':
            sessions += 1
        ordinal = sessions if calendar_known and market == 'open' else None
        for sid in stock_ids:
            stock = day['stocks'][sid]
            status = availability(day, stock, cutoff_day)
            current = daily_continuity(market, status)
            close = 'incomplete' if market == 'open' and status == 'missing_close' else current
            continuity[sid] = max(continuity[sid], current, key=CONTINUITY_PRIORITY.__getitem__)
            closes[sid] = max(closes[sid], close, key=CONTINUITY_PRIORITY.__getitem__)
            yield day, sid, ordinal, status, continuity[sid], closes[sid]


def set_range_positions(report):
    positions = range_positions(report['days'], report['stock_ids'], report['as_of'])
    for day, sid, ordinal, _, continuity, closes in positions:
        day['session_ordinal'] = ordinal
        day['stocks'][sid].update(observation_continuity=continuity, close_continuity=closes)


def event_sequence(report, bundles, event_id):
    study = analyze(bundles, report['as_of'], cohort='unpruned_facts')
    event = next((e for category in study['categories'].values() for e in category['events']
                  if e['event_id'] == event_id), None)
    if event is None:
        raise ValueError('event ID absent from first-saved unpruned events at cutoff')
    sid = event['stock_id']
    if sid not in report['stock_ids']:
        raise ValueError('anchor stock must be selected')
    baseline = event['baseline']['market']
    if baseline is not None and baseline['market'].lower() != report['market']:
        raise ValueError('anchor market does not match selected market')
    anchor_day = timestamp(event['event_at']).astimezone(TAIPEI).date()
    if (iso_date(report['start']) - anchor_day).days > 1 or iso_date(report['end']) < anchor_day:
        raise ValueError('calendar interval must cover the sequence from the day after event capture')
    facts = []
    cutoff = timestamp(report['as_of'])
    for bundle in bundles:
        if (bundle.facts is not None and sid in bundle.facts['scope']['stock_ids']
                and bundle.facts['scope']['market']['market'] == report['market']
                and timestamp(bundle.report['completed_at']) <= cutoff):
            facts.extend(saved_facts(bundle, sid))
    quotes = {quote['period']: (i, quote) for i, quote in
              enumerate(post_event_quotes(facts, event['event_at']), 1)}
    anchor = {k: event[k] for k in ('event_id', 'stock_id', 'rule_id', 'run', 'event_at', 'report_sha256')}
    anchor['taipei_date'] = anchor_day.isoformat()
    rows = []
    after = (day for day in report['days'] if day['date'] > anchor['taipei_date'])
    for day, _, session, available, continuity, closes in range_positions(after, [sid], report['as_of']):
        date = day['date']
        ordinal, quote = quotes.get(date, (None, None))
        rows.append({'date': date, 'session_ordinal': session,
                     'quote_ordinal': ordinal, 'availability': available, 'continuity': continuity, 'close_continuity': closes,
                     'quote': {k: quote[k] for k in ('run', 'captured_at', 'market', 'fact_id', 'close', 'volume_shares')}
                              if quote else None})
    horizons = []
    unresolved = any(day['market_status'] in ('unknown', 'conflict')
                     for day in report['days'] if day['date'] > anchor['taipei_date'])
    for outcome in event['outcomes']:
        if outcome['metric'] != 'close_change_pct':
            continue
        horizon = outcome['horizon']
        target = next((day for day in rows if day['session_ordinal'] == horizon), None)
        session = ({k: target[k] for k in ('date', 'availability', 'continuity', 'close_continuity')} if target else
                   {'date': None, 'availability': 'unknown_calendar' if unresolved else 'outside_report_range',
                    'continuity': None, 'close_continuity': None})
        target = next((day for day in rows if day['quote_ordinal'] == horizon), None)
        quote = ({'date': target['date'], **target['quote']} if target else
                 {'date': None, 'availability': 'no_saved_quote_in_range_by_cutoff'})
        original = {'date': outcome['target_period'], 'horizon_unit': outcome['horizon_unit'],
                    'market': outcome['followup']['market'] if outcome['followup'] else None,
                    'status': outcome['status'], 'reason': outcome['reason']}
        horizons.append({'horizon': horizon, 'session': session, 'quote': quote, 'event_study_close_target': original})
    return {'event_study_version': study['schema_version'], 'fact_scope': study['fact_scope'],
            'anchor': anchor, 'days': rows, 'horizons': horizons}
