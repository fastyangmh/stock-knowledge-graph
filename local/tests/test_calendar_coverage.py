"""Private CLI with real synthetic SQLite price history and audited research runs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from local.core import ROOT
from local.market_prices import ingest
from local.research import run
from local.research_history import canonical
from test_alert_integration import csv_data
from test_alerts import payload


class CalendarCoverageFixture:
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.calendar = self.root / 'calendar.json'
        self.output = self.root / 'coverage.json'
        self.as_of = '2019-01-09T20:00:00+08:00'
        self.start, self.end = '2019-01-05', '2019-01-08'
        self.symbols = ['1000', '1001']
        self.entries = []
        self.data = payload()
        self.data['financial_metrics'] = []
        self.data['stocks'].append(dict(self.data['stocks'][0], stock_id='TW:1001', ticker='1001'))
        self.bundle = self.save_run(self.end)

    def save_run(self, day):
        known = day + 'T20:00:00+08:00'
        observed = day + 'T18:00:00+08:00'
        csv = csv_data(day).decode()
        second = csv.splitlines()[-1].split(',')
        second[1], second[6] = '1001', '--'
        body = csv.encode() + (','.join(second) + '\r\n').encode()
        ingest(body, 'twse', ['1000', '1001'], day, db=self.root/'prices.db',
               output=self.root/'raw', observed_at=observed, acquisition='local_file_unverified')
        self.data['metadata']['observed_at'] = known
        path = self.root/'normalized.json'
        path.write_bytes(canonical(self.data))
        with patch('local.research.utc_now', return_value=known), patch('local.research_history.utc_now', return_value=known):
            return run(path, ['1000', '1001'], history_db=self.root/'history.db',
                       output_root=self.root/'runs', prices_db=self.root/'prices.db',
                       price_snapshots=self.root/'raw', trade_date=day)

    def entry(self, name, **changes):
        body = ('synthetic calendar ' + name).encode()
        path = self.root/(name + '.txt')
        path.write_bytes(body)
        entry = dict(id=name, market='twse', start=self.start, end=self.end,
                     retrieved_at='2018-12-01T01:00:00Z', saved_at='2018-12-01T02:00:00Z',
                     source_url='https://example.org/calendar/' + name, date_semantics='market trading date',
                     path=path.name, sha256=hashlib.sha256(body).hexdigest())
        self.entries.append(dict(entry, **changes))

    def cli(self, *extra):
        self.calendar.write_bytes(canonical({'schema_version': 'market-calendar-1', 'entries': self.entries}))
        return subprocess.run([sys.executable, '-m', 'local.calendar_coverage', '--root', str(self.root/'runs'),
                               '--calendar', str(self.calendar), '--market', 'twse', '--symbols', *self.symbols,
                               '--start', self.start, '--end', self.end, '--as-of', self.as_of,
                               '--output', str(self.output), *extra], cwd=ROOT, text=True, capture_output=True)

    def report(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.read_bytes())


class CalendarCoverageTests(CalendarCoverageFixture, unittest.TestCase):
    def test_explicit_calendar_separates_closed_missing_unknown_and_saved_prices(self):
        self.entry('daily', days={'2019-01-05':'closed', '2019-01-07':'open', '2019-01-08':'open'})
        report = self.report()
        self.assertEqual(report['market'], 'twse')
        self.assertEqual(report['as_of'], self.as_of)
        self.assertEqual(report['inputs'][0]['run'], self.bundle['run'])
        self.assertEqual(report['calendar']['versions'][0]['id'], 'daily')
        self.assertEqual(report['market_counts'], {'closed':1, 'open':2, 'unknown':1})
        days = report['days']
        self.assertEqual([day['date'] for day in days], ['2019-01-05','2019-01-06','2019-01-07','2019-01-08'])
        self.assertEqual([day['market_status'] for day in days], ['closed','unknown','open','open'])
        self.assertEqual([day['stocks']['TW:1000']['status'] for day in days],
                         ['closed','unknown_calendar','missing_observation','observed'])
        self.assertEqual(days[2]['stocks']['TW:1000']['reason'], 'cause_unknown')
        self.assertEqual(days[3]['stocks']['TW:1001']['status'], 'missing_close')
        self.assertIsNone(days[3]['stocks']['TW:1001']['observation']['close'])
        self.assertEqual(report['stock_counts']['TW:1001'],
                         {'closed':1, 'unknown_calendar':1, 'missing_observation':1, 'missing_close':1})
        self.assertEqual(self.report(), report)

    def test_annual_schedule_holiday_weekend_and_missing_next_market_year(self):
        self.start, self.end = '2018-12-28', '2019-01-02'
        self.entry('year', end='2018-12-31', open_weekdays=[0,1,2,3,4],
                   days={'2018-12-29':'open', '2018-12-31':'closed'})
        self.entry('other-market', market='tpex', start='2019-01-01', days={'2019-01-01':'closed'})
        days = self.report()['days']
        self.assertEqual([d['market_status'] for d in days], ['open','open','closed','closed','unknown','unknown'])
        self.assertEqual(days[4]['reason'], 'other_market_only')
        self.assertEqual(days[5]['reason'], 'no_calendar_entry')

    def test_monday_unknown_scheduled_open_and_superseding_emergency_closure_at_cutoff(self):
        self.entry('weekend', days={'2019-01-05':'closed','2019-01-06':'closed','2019-01-08':'open'})
        self.assertEqual(self.report()['days'][2]['market_status'], 'unknown')
        self.output = self.root/'scheduled.json'
        self.entry('scheduled', days={'2019-01-07':'open'})
        schedule = self.report()
        self.assertEqual(schedule['days'][2]['stocks']['TW:1001']['status'], 'missing_observation')
        self.entry('emergency', days={'2019-01-07':'closed'}, saved_at='2019-01-10T00:00:00Z',
                   supersedes=['scheduled'])
        self.assertEqual(self.report(), schedule)
        self.as_of = '2019-01-11T00:00:00Z'
        self.output = self.root/'emergency.json'
        closed = self.report()['days'][2]
        self.assertEqual((closed['market_status'], closed['evidence_ids']), ('closed',['emergency']))
        self.entry('reopen', days={'2019-01-07':'open'}, saved_at='2019-01-10T01:00:00Z')
        self.output = self.root/'conflict.json'
        conflict = self.report()['days'][2]
        self.assertEqual((conflict['market_status'], conflict['evidence_ids']), ('conflict',['emergency','reopen']))
        self.assertEqual(conflict['reason'], 'contradictory_calendar_entries')

    def test_closed_day_with_a_saved_quote_retains_both_sources_as_a_conflict(self):
        self.entry('closed', days={self.end:'closed'})
        self.symbols = ['1000', '1009']
        report = self.report()
        day = report['days'][-1]
        self.assertEqual(day['market_status'], 'conflict')
        self.assertEqual(day['reason'], 'closed_with_saved_observation')
        self.assertEqual(day['evidence_ids'], ['closed'])
        self.assertEqual(day['stocks']['TW:1000']['observation']['run'], self.bundle['run'])
        self.assertEqual(day['stocks']['TW:1000']['status'], 'calendar_conflict')
        self.assertEqual(report['market_counts'], {'unknown':3, 'conflict':1})

    def test_reports_legacy_unselected_market_and_trade_date_scope_separately(self):
        self.symbols = ['1000', '1009']
        self.start, self.end = '2019-01-08', '2019-01-09'
        self.entry('open', open_weekdays=list(range(7)))
        first, second = self.report()['days']
        self.assertEqual(first['stocks']['TW:1009']['reason'], 'stock_not_selected')
        self.assertEqual(second['stocks']['TW:1000']['reason'], 'after_market_trade_date')
        self.output = self.root/'other.json'
        result = self.cli('--market', 'tpex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_bytes())['days'][0]['stocks']['TW:1000']['reason'], 'market_not_in_scope')
        path = self.root/'runs'/self.bundle['run']
        report = json.loads((path/'report.json').read_bytes())
        del report['research_facts']
        (path/'research-facts.json').unlink()
        body = canonical(report)
        (path/'report.json').write_bytes(body)
        pointer_path = self.root/'runs/latest.json'
        pointer = json.loads(pointer_path.read_bytes())
        pointer['report_sha256'] = hashlib.sha256(body).hexdigest()
        pointer_path.write_bytes(canonical(pointer))
        self.output = self.root/'legacy.json'
        legacy = self.report()
        self.assertEqual(legacy['inputs'][0]['fact_scope'], 'display_graph_only')
        self.assertEqual(legacy['days'][0]['stocks']['TW:1000']['reason'], 'display_graph_only')
        self.as_of = '2019-01-07T23:59:59Z'
        self.output = self.root/'before.json'
        early = self.report()
        self.assertEqual(early['inputs'], [])
        self.assertEqual(early['days'][0]['stocks']['TW:1000']['reason'], 'no_saved_run_by_cutoff')

    def test_source_checksum_and_corrupt_bundle_fail_without_replacing_old_output(self):
        self.entry('official', days={self.end:'open'})
        self.report()
        before = self.output.read_bytes()
        (self.root/'official.txt').write_text('different snapshot')
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum', result.stderr)
        self.assertEqual(self.output.read_bytes(), before)
        (self.root/'official.txt').write_text('synthetic calendar official')
        (self.root/'runs'/self.bundle['run']/'graph.db').write_bytes(b'different')
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_range_evidence_and_catalog_budgets_reject_success(self):
        self.entry('version', days={self.end:'open'})
        for options in (['--max-rows','7'], ['--start','2019-01-09'], ['--max-mib','0'], ['--max-runs','0']):
            with self.subTest(options=options):
                result = self.cli(*options)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
        source = self.root/'version.txt'
        source.write_bytes(b'a' * (1024 * 1024))
        self.entries[0]['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        result = self.cli('--max-mib','1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('budget', result.stderr)
        self.assertFalse(self.output.exists())

    def test_invalid_calendars_cannot_issue_decisions(self):
        self.entry('annual', days={self.end:'open'})
        original = self.entries[0]
        for changes in ({'days':{self.end:'holiday'}}, {'days':{'2019-02-01':'closed'}},
                        {'open_weekdays':[7]}, {'saved_at':'2018-01-01T00:00:00Z'},
                        {'date_semantics':''}, {'supersedes':['missing']}, {'supersedes':['annual']},
                        {'source_url':''}, {'market':'futures'}, {'path':'../unrelated.txt'}):
            with self.subTest(changes=changes):
                self.entries = [dict(original, **changes)]
                result = self.cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(self.output.exists())
        self.entries = [original, original]
        self.assertNotEqual(self.cli().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_later_bundle_and_latest_pointer_do_not_change_earlier_cutoff_replay(self):
        self.entry('annual', open_weekdays=[0,1,2,3,4])
        initial = self.report()
        self.save_run('2019-01-11')
        self.assertEqual(self.report(), initial)

    def test_market_conflict_from_audited_stock_outside_display_selection(self):
        self.entry('closed', days={self.end:'closed'})
        self.symbols = ['1009']
        day = self.report()['days'][-1]
        self.assertEqual(day['market_status'], 'conflict')
        self.assertEqual(day['conflicting_observation']['run'], self.bundle['run'])
        self.assertIn(day['conflicting_observation']['stock_id'], ('TW:1000','TW:1001'))
        self.assertEqual(day['stocks']['TW:1009']['status'], 'insufficient_scope')
