"""Calendar and event CLIs share an audited catalog built from synthetic prices."""
from datetime import date, timedelta
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local.core import ROOT
from local.market_prices import ingest
from local.research import run
from local.research_history import canonical
from test_alert_integration import csv_data
from test_alerts import checks, payload, SID
from test_event_integration import research_run


class EventCalendarTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.runs = self.root / 'runs'
        self.as_of = '2019-01-09T20:00:00+08:00'
        self.start, self.end = '2019-01-04', '2019-01-08'
        self.data = payload()
        self.data['financial_metrics'] = []

    def anchor(self, prior='2019-01-03', friday='2019-01-04'):
        self.save(prior, '100')
        return self.save(friday, '110', alerts=True)

    def save(self, day, close, **options):
        return research_run(self.root, day, day, close, 1000, data=self.data, **options)

    def cli(self, module, *args):
        return subprocess.run([sys.executable, '-m', module, '--root', str(self.runs),
                               '--as-of', self.as_of, *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True)

    def study(self, name='event.json'):
        output = self.root / name
        result = self.cli('local.event_study', '--output', output)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(output.read_bytes())

    def coverage(self, event_id, explicit, *, weekdays=None, name='coverage.json', success=True, market='twse'):
        archive = self.root / 'synthetic-days.json'
        raw = canonical({'days': explicit, 'weekdays': weekdays})
        archive.write_bytes(raw)
        version = {'id': 'fixture', 'path': archive.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                   'start': self.start, 'end': self.end, 'days': explicit, 'market': 'twse',
                   'date_semantics': 'synthetic market sessions', 'source_url': 'https://example.org/days',
                   'retrieved_at': '2018-11-01T00:00:00Z', 'saved_at': '2018-11-01T00:01:00Z'}
        if weekdays is not None:
            version['open_weekdays'] = weekdays
        index = self.root / 'calendar.json'
        index.write_bytes(canonical({'schema_version': 'market-calendar-1', 'entries': [version]}))
        output = self.root / name
        result = self.cli('local.calendar_coverage', '--calendar', index, '--output', output,
                          '--market', market, '--symbols', '1000', '--start', self.start,
                          '--end', self.end, *(['--event-id', event_id] if event_id else []))
        if not success:
            return result
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_bytes())
        return report['event_sequence'] if event_id else report

    def test_open_monday_gap_preserves_tuesday_as_first_quote_and_second_session(self):
        first = self.anchor()
        self.save('2019-01-08', '121')
        study = self.study()
        event, = study['categories']['price_volume']['events']
        self.assertEqual(event['event_id'], 'b3eb4771d2003e42c9010f50358226dfecf20d01e788f9e7d20c31e8b1578f6f')
        seq = self.coverage(event['event_id'], {}, weekdays=[0, 1, 2, 3, 4])
        self.assertEqual(seq['anchor']['run'], first['run'])
        self.assertEqual(seq['anchor']['event_id'], event['event_id'])
        self.assertEqual(seq['anchor']['taipei_date'], '2019-01-04')
        self.assertEqual([d['date'] for d in seq['days']],
                         ['2019-01-05', '2019-01-06', '2019-01-07', '2019-01-08'])
        monday, tuesday = seq['days'][-2:]
        self.assertEqual((monday['session_ordinal'], monday['quote_ordinal'], monday['availability']),
                         (1, None, 'missing_observation'))
        self.assertEqual((tuesday['session_ordinal'], tuesday['quote_ordinal'], tuesday['continuity']),
                         (2, 1, 'incomplete'))

    def test_monday_closure_unknown_or_conflict_determines_tuesday_ordinal(self):
        self.anchor()
        self.save('2019-01-08', '121')
        event, = self.study()['categories']['price_volume']['events']
        for name, schedule, expected in (
                ('closure', {'2019-01-07': 'closed'}, (1, 'complete')),
                ('unknown', {}, (None, 'unknown')),
                ('conflict', {'2019-01-07': 'closed', '2019-01-08': 'closed'}, (None, 'unknown'))):
            with self.subTest(name=name):
                days = {'2019-01-04': 'open', '2019-01-05': 'closed', '2019-01-06': 'closed',
                        '2019-01-08': 'open', **schedule}
                seq = self.coverage(event['event_id'], days, name=name + '.json')
                tuesday = seq['days'][-1]
                self.assertEqual((tuesday['session_ordinal'], tuesday['continuity']), expected)
                self.assertEqual(tuesday['quote_ordinal'], 1)
                ordinary = self.coverage(None, days, name=name + '-range.json')['days'][-1]
                expected_from_friday = 2 if name == 'closure' else None
                self.assertEqual(ordinary['session_ordinal'], expected_from_friday)
                self.assertEqual(ordinary['stocks'][SID]['observation_continuity'], expected[1])

    def year_end_sequence(self, skip=None):
        self.anchor('2018-12-27', '2018-12-28')
        self.start, self.end = '2018-12-29', '2019-01-29'
        self.as_of = self.end + 'T21:00:00+08:00'
        day = date.fromisoformat(self.start)
        while day <= date.fromisoformat(self.end):
            key = day.isoformat()
            if day.weekday() < 5 and key not in ('2019-01-01', skip):
                self.save(key, '111')
            day += timedelta(days=1)
        event, = self.study()['categories']['price_volume']['events']
        return self.coverage(event['event_id'], {'2019-01-01': 'closed'}, weekdays=[0, 1, 2, 3, 4])

    def test_cross_year_session_and_quote_targets_1_5_20(self):
        report = self.year_end_sequence()
        for target, horizon, day in zip(report['horizons'], (1, 5, 20),
                                        ('2018-12-31', '2019-01-07', '2019-01-28'), strict=True):
            self.assertEqual((target['horizon'], target['session']['date'], target['quote']['date']),
                             (horizon, day, day))
            self.assertEqual(target['session']['continuity'], 'complete')
            self.assertEqual(target['session']['availability'], 'observed')

    def test_missing_fifth_session_does_not_displace_fifth_or_twentieth_target(self):
        report = self.year_end_sequence(skip='2019-01-07')
        first, fifth, last = report['horizons']
        self.assertEqual(first['session']['continuity'], 'complete')
        self.assertEqual(fifth['session'], {'date': '2019-01-07', 'availability': 'missing_observation',
                                            'continuity': 'incomplete'})
        self.assertEqual(fifth['quote']['date'], '2019-01-08')
        self.assertEqual((last['session']['date'], last['session']['continuity'], last['quote']['date']),
                         ('2019-01-28', 'incomplete', '2019-01-29'))

    def test_not_yet_due_sessions_are_pending_at_cutoff(self):
        self.anchor()
        self.as_of = '2019-01-05T01:00:00+08:00'
        event, = self.study()['categories']['price_volume']['events']
        report = self.coverage(event['event_id'], {}, weekdays=[0, 1, 2, 3, 4])
        first, fifth, _ = report['horizons']
        self.assertEqual(first['session'], {'date': '2019-01-07', 'availability': 'pending',
                                            'continuity': 'pending'})
        self.assertIsNone(first['quote']['date'])
        self.assertEqual(fifth['session']['availability'], 'outside_report_range')

    def capture(self, day, saved_at, *, alerts=False, known_at=None):
        path = self.root / 'normalized.json'
        self.data['metadata']['observed_at'] = day + 'T20:00:00+08:00'
        path.write_bytes(canonical(self.data))
        with patch('local.research.utc_now', return_value=saved_at), patch(
                'local.research_history.utc_now', return_value=saved_at):
            return run(path, ['1000'], history_db=self.root / 'ledger.db', output_root=self.runs,
                       prices_db=self.root / 'prices.db', price_snapshots=self.root / 'raw',
                       trade_date=day, known_at=known_at, alerts=alerts)

    def test_first_capture_taipei_midnight_and_missing_close_survive_revisions(self):
        self.save('2019-01-03', '100')
        self.save('2019-01-04', '110')
        first = self.capture('2019-01-04', '2019-01-06T16:05:00Z',
                             alerts=True, known_at='2019-01-04T20:00:00+08:00')
        self.capture('2019-01-04', '2019-01-07T02:00:00Z', alerts=True)
        self.save('2019-01-07', '120')
        missing_close = csv_data('2019-01-08').replace(b',100,1000,', b',--,1000,')
        ingest(missing_close, 'twse', ['1000'], '2019-01-08', db=self.root/'prices.db',
               output=self.root/'raw', observed_at='2019-01-08T18:00:00+08:00', acquisition='local_file_unverified')
        followup = self.capture('2019-01-08', '2019-01-08T12:00:00Z')
        ingest(csv_data('2019-01-08', '130'), 'twse', ['1000'], '2019-01-08', db=self.root/'prices.db',
               output=self.root/'raw', observed_at='2019-01-09T18:00:00+08:00', acquisition='local_file_unverified')
        self.save('2019-01-09', '130')
        self.end = '2019-01-09'
        study = self.study()
        event, = study['categories']['price_volume']['events']
        alerts_file = self.runs / first['run'] / 'alerts.json'
        alerts = json.loads(alerts_file.read_bytes())['stocks'][SID]
        self.assertEqual(alerts['config']['volume_window'], 20)
        self.assertEqual(checks(alerts)['price_change']['value'], '10.000000')
        self.assertEqual(checks(alerts)['volume_ratio']['status'], 'insufficient_data')
        seq = self.coverage(event['event_id'], {}, weekdays=[0, 1, 2, 3, 4])
        self.assertEqual(seq['event_study_version'], 'event-study-2.0')
        self.assertEqual((seq['anchor']['taipei_date'], seq['anchor']['run']), ('2019-01-07', first['run']))
        self.assertEqual([r['date'] for r in seq['days']], ['2019-01-08', '2019-01-09'])
        self.assertEqual(seq['days'][0]['availability'], 'missing_close')
        self.assertEqual((seq['days'][0]['quote_ordinal'], seq['days'][0]['continuity']), (1, 'complete'))
        self.assertEqual(seq['days'][0]['quote']['run'], followup['run'])
        self.assertIsNone(seq['days'][0]['quote']['close'])
        self.assertEqual(event['baseline']['market']['close'], '110')
        self.assertEqual(event['repeated_captures'], 1)
        change = next(row for row in event['outcomes'] if row['metric'] == 'close_change_pct' and row['horizon'] == 1)
        self.assertEqual((change['target_period'], change['horizon_unit'], change['reason']),
                         ('2019-01-08', 'quote_observations', 'missing_or_nonpositive_denominator_or_close'))
        self.assertEqual(change['followup']['fact_id'], seq['days'][0]['quote']['fact_id'])
        summary = next(row for row in study['categories']['price_volume']['summaries']
                       if row['metric'] == 'close_change_pct' and row['horizon'] == 1)
        self.assertEqual((summary['n_total'], summary['n_observed']), (1, 0))
        self.assertEqual(study, self.study('replayed-study.json'))
        self.assertEqual(alerts, json.loads(alerts_file.read_bytes())['stocks'][SID])

    def test_wrong_market_anchor_or_omitted_sequence_start_preserve_prior_output(self):
        self.anchor()
        event, = self.study()['categories']['price_volume']['events']
        key = event['event_id']
        self.coverage(key, {}, weekdays=list(range(7)))
        output = self.root / 'coverage.json'
        prior = output.read_bytes()
        for event_id, market, start, diagnostic in (
                ('unknown-id', 'twse', self.start, 'event ID'),
                (key, 'tpex', self.start, 'anchor market'),
                (key, 'twse', '2019-01-07', 'interval')):
            with self.subTest(diagnostic=diagnostic):
                self.start = start
                result = self.coverage(event_id, {}, weekdays=list(range(7)), success=False, market=market)
                self.assertEqual(result.returncode, 2)
                self.assertIn(diagnostic, result.stderr)
                self.assertEqual(output.read_bytes(), prior)
