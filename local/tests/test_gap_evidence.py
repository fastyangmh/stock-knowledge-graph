"""Replay archived gap evidence against synthetic research runs through the private CLI."""
import hashlib
import unittest

from local.market_prices import ingest
from local.research_history import canonical
from test_alert_integration import csv_data
from test_calendar_coverage import CalendarCoverageFixture


class GapEvidenceTests(CalendarCoverageFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.start = '2019-01-07'
        self.entry('daily', days={self.start: 'open', self.end: 'open'})
        self.gaps = []

    def evidence(self, name, kind, **extra):
        raw = self.root / (name + '.txt')
        raw.write_text('Archived synthetic evidence for ' + name)
        self.gaps.append(dict(
            id=name, market='twse', date=self.start, source_id='twse_daily_11549',
            kind=kind, saved_at='2019-01-07T19:00:00+08:00', locator='synthetic record 1',
            path=raw.name, sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        ) | extra)

    def cli(self, *extra):
        index = self.root / 'gaps.json'
        index.write_bytes(canonical({'schema_version': 'market-gap-evidence-1', 'entries': self.gaps}))
        return super().cli('--gap-evidence', str(index), *extra)

    def test_suspension_and_traded_peer_on_same_open_session(self):
        ingest(csv_data(self.start), 'twse', ['1000'], self.start, db=self.root/'prices.db',
               output=self.root/'raw', observed_at=self.start+'T18:00:00+08:00',
               acquisition='local_file_unverified')
        self.save_run('2019-01-09')
        self.evidence('halt', 'suspended', stock_id='TW:1001',
                      source_url='https://www.twse.com.tw/synthetic/notice')
        report = self.report()
        monday = report['days'][0]
        self.assertEqual(report['market_counts'], {'open': 2})
        self.assertEqual(monday['stocks']['TW:1000']['status'], 'observed')
        halted = monday['stocks']['TW:1001']
        self.assertIsNone(halted['observation'])
        self.assertEqual(halted['diagnosis']['stock_state'], 'suspended')
        self.assertEqual(halted['diagnosis']['stock_evidence_ids'], ['halt'])
        self.assertEqual(report['diagnosis_counts']['TW:1001']['gap']['explained'], 1)

    def test_no_trade_missing_close_and_absent_row_keep_separate_denominators(self):
        self.evidence('no-trades', 'no_trade', stock_id='TW:1001',
                      source_url='https://www.twse.com.tw/synthetic/status')
        report = self.report()
        monday, tuesday = report['days']
        no_trade = monday['stocks']['TW:1001']
        self.assertIsNone(no_trade['observation'])
        self.assertEqual(no_trade['diagnosis']['stock_state'], 'no_trade')
        missing = monday['stocks']['TW:1000']
        self.assertIsNone(missing['observation'])
        self.assertEqual(missing['diagnosis']['gap'], 'unresolved')
        self.assertEqual(report['diagnosis_counts']['TW:1000']['gap']['unresolved'], 1)
        saved = tuesday['stocks']['TW:1001']
        self.assertEqual(saved['status'], 'missing_close')
        self.assertEqual(saved['diagnosis']['stock_state'], 'unknown')
        obs = saved['observation']
        self.assertEqual((obs['close'], obs['volume_shares'], obs['turnover_raw'], obs['trades']),
                         (None, 1000, '200000', 10))
        self.assertEqual(report['stock_counts']['TW:1001'], {'missing_close': 1, 'missing_observation': 1})

    def test_failed_collection_and_inventory_match_exact_feed_date_market_and_can_coexist(self):
        self.evidence('halt', 'suspended', stock_id='TW:1001',
                      source_url='https://www.twse.com.tw/synthetic/notice')
        self.evidence('batch-1', 'fetch_failed', run_id='attempt-1', failure='download failed')
        self.evidence('inventory', 'missing_file', checked_at=self.start+'T18:45:00+08:00',
                      quote_file='daily.csv', expected_files=['daily.csv', 'notes.txt'], missing_files=['daily.csv'])
        self.evidence('deadline', 'due', due_at=self.start+'T18:30:00+08:00')
        self.evidence('other-feed', 'fetch_failed', run_id='other', failure='parse', source_id='other')
        self.evidence('other-market', 'fetch_failed', run_id='other', failure='parse', market='tpex')
        self.evidence('other-day', 'fetch_failed', run_id='other', failure='parse', date='2019-01-06')
        report = self.report()
        diagnosis = report['days'][0]['stocks']['TW:1001']['diagnosis']
        self.assertEqual(diagnosis['stock_state'], 'suspended')
        self.assertEqual(diagnosis['acquisition'], {'fetch_failed': ['batch-1'], 'missing_file': ['inventory']})
        peer = report['days'][0]['stocks']['TW:1000']['diagnosis']
        self.assertEqual(peer['gap'], 'explained')
        self.assertEqual(report['diagnosis_counts']['TW:1001']['acquisition'], {'fetch_failed': 1, 'missing_file': 1})
        self.assertFalse(report['days'][1]['stocks']['TW:1000']['diagnosis']['acquisition'])

    def test_replay_before_and_after_late_first_saved_bundle_without_backdating_registration(self):
        self.as_of = '2019-01-08T20:00:00+08:00'
        self.evidence('deadline', 'due', due_at=self.start+'T18:30:00+08:00')
        early = self.report()
        missing = early['days'][0]['stocks']['TW:1000']
        self.assertEqual(missing['diagnosis']['timing'], 'overdue_unobserved')
        self.assertEqual(missing['diagnosis']['timing_evidence_ids'], ['deadline'])
        ingest(csv_data(self.start), 'twse', ['1000'], self.start, db=self.root/'prices.db',
               output=self.root/'raw', observed_at=self.start+'T18:00:00+08:00',
               acquisition='local_file_unverified')
        self.save_run('2019-01-09')
        self.evidence('future-failure', 'fetch_failed', saved_at='2019-01-09T10:00:00+08:00',
                      run_id='later', failure='download failed')
        self.assertEqual(self.report(), early)
        self.as_of = '2019-01-09T20:00:00+08:00'
        self.output = self.root/'after.json'
        late = self.report()['days'][0]['stocks']['TW:1000']
        self.assertEqual(late['diagnosis']['timing'], 'late_first_bundle')
        self.assertEqual(late['observation']['captured_at'], self.as_of)
        self.assertEqual(late['observation']['recorded_at_status'], 'unknown')
        self.assertIsNone(late['observation']['recorded_at'])
        self.assertEqual(late['diagnosis']['gap'], 'not_applicable')

    def test_pending_unknown_and_conflicting_deadlines_cannot_prove_missing_file(self):
        self.as_of = '2019-01-08T20:00:00+08:00'
        self.evidence('inventory', 'missing_file', checked_at=self.start+'T18:45:00+08:00',
                      quote_file='daily.csv', expected_files=['daily.csv'], missing_files=['daily.csv'])
        for remaining, timing, gap in [(None, 'due_unknown', 'unresolved'),
                                       ('2019-01-09T06:00:00Z', 'pending', 'pending'),
                                       ('2019-01-07T06:00:00Z', 'due_conflict', 'unresolved')]:
            with self.subTest(timing=timing):
                if remaining:
                    self.evidence(timing, 'due', due_at=remaining)
                self.output = self.root/(timing+'.json')
                diag = self.report()['days'][0]['stocks']['TW:1000']['diagnosis']
                self.assertEqual((diag['timing'], diag['gap'], diag['acquisition']), (timing, gap, {}))

    def test_known_deadline_after_latest_bundle_preserves_scope_and_pending_continuity(self):
        self.start = self.end = '2019-01-09'
        self.symbols = ['1000', '1009']
        self.entry('today', days={self.start: 'open'})
        deadline = self.start + 'T18:00:00+08:00'
        self.evidence('today-due', 'due', due_at=deadline)
        self.evidence('other-market', 'due', market='tpex', source_id='tpex_daily_11371',
                      due_at=self.start + 'T08:00:00+08:00')
        for cutoff, due_at, timing, gap, continuity in (
                ('2019-01-09T09:00:00+08:00', deadline, 'pending', 'pending', 'pending'),
                ('2019-01-10T01:00:00+08:00', '2019-01-10T02:00:00+08:00', 'pending', 'pending', 'pending'),
                (deadline, deadline, 'due_passed_outside_scope', 'not_applicable', 'unknown')):
            with self.subTest(cutoff=cutoff):
                self.as_of = cutoff
                self.gaps[0]['due_at'] = due_at
                self.output = self.root / (cutoff.replace(':', '') + '.json')
                report = self.report()
                stocks = report['days'][0]['stocks']
                row = stocks['TW:1000']
                self.assertEqual((row['status'], row['reason']), ('insufficient_scope', 'after_market_trade_date'))
                self.assertEqual(row['diagnosis']['timing_evidence_ids'], ['today-due'])
                self.assertEqual((row['diagnosis']['timing'], row['diagnosis']['gap']), (timing, gap))
                self.assertEqual((row['observation_continuity'], row['close_continuity']), (continuity, continuity))
                self.assertEqual(report['diagnosis_counts']['TW:1000']['gap'], {gap: 1})
                self.assertEqual(stocks['TW:1009']['reason'], 'stock_not_selected')
                self.assertEqual(stocks['TW:1009']['diagnosis']['timing'], 'not_applicable')
                self.assertEqual(stocks['TW:1009']['observation_continuity'], 'unknown')

    def test_invalid_reason_evidence_cannot_replace_report_or_guess_a_cause(self):
        self.evidence('attempt', 'fetch_failed', run_id='attempt-1', failure='synthetic error')
        valid = self.report()['days'][0]['stocks']['TW:1000']
        self.assertEqual(valid['reason'], 'documented_gap')
        original = self.output.read_bytes()
        entry = self.gaps[0]
        for changes in (
            {'sha256': '0' * 64}, {'path': '../other-file'}, {'run_id': ''},
            {'kind': 'missing_file', 'quote_file': 'q.csv', 'expected_files': [], 'missing_files': ['q.csv'],
             'checked_at': entry['saved_at']},
            {'kind': 'no_trade', 'stock_id': 'TW:1001', 'source_url': 'https://example.org/test'},
            {'kind': 'no_trade', 'stock_id': 'TW:1001', 'source_url': 'https://www.tpex.org.tw/test'},
        ):
            with self.subTest(changes=changes):
                self.gaps = [entry | changes]
                result = self.cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(self.output.read_bytes(), original)

    def test_traded_volume_contradicting_official_stock_status_keeps_both_records(self):
        self.evidence('halt', 'suspended', date=self.end, stock_id='TW:1000',
                      source_url='https://www.twse.com.tw/synthetic/notice')
        stock = self.report()['days'][1]['stocks']['TW:1000']
        self.assertEqual(stock['status'], 'observed')
        self.assertEqual(stock['observation']['trades'], 10)
        self.assertEqual(stock['diagnosis']['stock_state'], 'conflict')
        self.assertEqual(stock['diagnosis']['stock_evidence_ids'], ['halt'])

    def test_official_no_trade_with_saved_zero_preserves_original_values_and_halt_notice(self):
        day = self.start
        csv = csv_data(day).decode().splitlines()
        record = csv[1].split(',')
        record[3:] = ['--', '--', '--', '--', '0', '0', '0']
        raw = (csv[0]+'\r\n'+','.join(record)+'\r\n').encode()
        ingest(raw, 'twse', ['1000'], day, db=self.root/'prices.db', output=self.root/'raw',
               observed_at=day+'T18:00:00+08:00', acquisition='local_file_unverified')
        self.save_run('2019-01-09')
        self.evidence('zero', 'no_trade', stock_id='TW:1000',
                      source_url='https://www.twse.com.tw/synthetic/status')
        stock = self.report()['days'][0]['stocks']['TW:1000']
        self.assertEqual(stock['diagnosis']['stock_state'], 'no_trade')
        self.assertEqual(stock['observation']['turnover_raw'], '0')
        self.assertEqual(stock['observation']['volume_shares'], 0)
        self.assertIsNone(stock['observation']['close'])
        self.evidence('halt', 'suspended', stock_id='TW:1000',
                      source_url='https://www.twse.com.tw/synthetic/notice')
        self.output = self.root/'also-halted.json'
        again = self.report()['days'][0]['stocks']['TW:1000']
        self.assertEqual(again['diagnosis']['stock_state'], 'suspended')
        self.assertEqual(again['diagnosis']['stock_evidence_ids'], ['halt', 'zero'])

    def test_completed_market_observation_or_batch_cannot_predate_trading_date(self):
        self.evidence('too-soon', 'no_trade', stock_id='TW:1000', date=self.end,
                      source_url='https://www.twse.com.tw/synthetic/status')
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
