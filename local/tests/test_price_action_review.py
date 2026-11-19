"""Price review through the private comparison CLI; all generated rows are synthetic."""
import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local.market_prices import FEEDS, ingest
from local.research import run
from local.research_compare import main
from local.research_history import canonical
from test_research_history import payload, T1


class PriceActionReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / 'input.json'
        self.input.write_bytes(canonical(payload()))

    def ingest_day(self, day, close, feed, review, database, snapshots):
        body = io.StringIO(newline='')
        writer = csv.writer(body)
        writer.writerow(FEEDS[feed]['columns'])
        writer.writerow([day.replace('-', ''), '1000', 'Example', close, close, close, close, 1000, 20000, 10])
        raw = body.getvalue().encode()
        from hashlib import sha256
        if review:
            review = {**review, 'source_id': FEEDS[feed]['source_id'], 'trade_date': day,
                      'raw_sha256': sha256(raw).hexdigest()}
        ingest(raw, feed, ['1000'], day, db=database, output=snapshots,
               observed_at=T1, acquisition='local_file_unverified', unit_review=review)
    def bundle(self, day, close, *, feed='tpex', review=None, prior_day=None):
        database, snapshots = self.root / (feed+day+'.db'), self.root/'raw'
        self.ingest_day(day, close, feed, review, database, snapshots)
        if prior_day:
            self.ingest_day(prior_day, '19', feed, review, database, snapshots)
        with patch('local.research.utc_now', return_value=T1), patch('local.research_history.utc_now', return_value=T1):
            result = run(self.input, ['1000'], history_db=self.root/'ledger.db', output_root=self.root/'runs',
                         known_at=T1, prices_db=database, price_snapshots=snapshots,
                         trade_date=day, price_market=feed, max_information_nodes=0, alerts=bool(prior_day))
        return result['run']

    def compare(self, before, after, *options):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(['--root', str(self.root/'runs'), '--before', before, '--after', after, '--price-review', *options])
        return json.loads(output.getvalue())['price_review']

    def test_original_closes_from_each_bundle_and_unproven_range(self):
        a = self.bundle('2019-12-30', '20.00')
        b = self.bundle('2019-12-31', '21.00')
        row = self.compare(a, b)['stocks'][0]
        self.assertEqual(row['before']['close'], '20.00')
        self.assertEqual(row['after']['trade_date'], '2019-12-31')
        self.assertEqual(row['after']['price_basis'], 'source_unadjusted')
        self.assertEqual(row['after']['run'], b)
        self.assertIn('price_definition_unknown', row['warnings'])
        self.assertEqual(set(row['unknown_interval_coverage']), {'ex_rights_dividend','split_reverse_split','capital_reduction'})

    def test_http_compare_rejects_evaluable_alerts_in_different_currencies(self):
        from http.client import HTTPConnection
        from threading import Thread
        from local.research_archive import make_server
        from test_market_unit_review import definition
        first = self.bundle('2019-12-29', '20', review=definition(), prior_day='2019-12-28')
        second = self.bundle('2019-12-31', '22', prior_day='2019-12-30',
                             review={**definition(), 'price_currency': 'USD', 'turnover_currency': 'USD'})
        with make_server(self.root/'runs', port=0) as server:
            worker = Thread(target=server.handle_request)
            worker.start()
            client = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                client.request('GET', f'/api/compare?before={first}&after={second}')
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                result = json.loads(response.read())
            finally:
                client.close()
                worker.join(5)
        change = next(row for row in result['stocks'][0]['categories']['price_volume'] if row['rule_id'] == 'price_change')
        self.assertEqual(change['before']['status'], 'triggered')
        self.assertEqual(change['after']['status'], 'triggered')
        self.assertFalse(change['comparable'])
        self.assertEqual(change['transition'], 'definition_changed')

    def test_same_stock_with_different_market_or_currency_is_incomparable(self):
        from test_market_unit_review import definition
        a = self.bundle('2019-12-30', '20.00', review=definition())
        other_currency = self.bundle('2019-12-31', '40.00', review={
            **definition(), 'price_currency':'USD', 'turnover_currency':'USD'})
        other_market = self.bundle('2019-12-31', '40.00', feed='twse', review=definition())
        for end, field in ((other_currency, 'price_currency'), (other_market, 'source_id')):
            with self.subTest(field=field):
                row = self.compare(a, end)['stocks'][0]
                self.assertEqual(row['status'], 'incomparable')
                self.assertIn(field, row['definition_differences'])

    def capture(self, day, entries, received=T1):
        from hashlib import sha256
        columns = ['除權息日期','代號','名稱','除權息前收盤價','除權息參考價','權值','息值','權值加息值',
                   '權或息','漲停價','跌停價','開始交易基準價','減除股利參考價','現金股利','每仟股無償配股',
                   '現金增資股數','現金增資認購價','公開承銷股數','員工認購股數','原股東認購股數','按持股比例仟股認購']
        directory = self.root / (day + received.replace(':',''))
        directory.mkdir()
        body = io.StringIO(newline='')
        writer = csv.DictWriter(body, fieldnames=columns)
        writer.writeheader()
        for stock, marker in entries:
            writer.writerow({'除權息日期':day.replace('-',''), '代號':stock, '權或息':marker})
        raw = body.getvalue().encode('utf-8-sig')
        (directory / '11633.response').write_bytes(raw)
        path = directory/'manifest.json'
        path.write_text(json.dumps([{'id':11633, 'catalog':'https://data.gov.tw/dataset/11633',
            'url':'https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php?l=zh-tw&o=data',
            'started_at':received,'received_at':received,'status':'200','exit':0,'bytes':len(raw),
            'sha256':sha256(raw).hexdigest()}]))
        return str(path)

    def test_effective_day_excludes_old_close_and_includes_new_close(self):
        a = self.bundle('2019-12-30', '22')
        b = self.bundle('2019-12-31', '18')
        options = []
        for day in ('2019-12-30','2019-12-31','2020-01-01'):
            options.extend(['--action-manifest',self.capture(day, [('1000','除息'),('1001','除權')])])
        result = self.compare(a, b, *options)
        row = result['stocks'][0]
        self.assertEqual(row['status'], 'incomparable')
        self.assertEqual([(e['stock_id'],e['effective_date'],e['marker']) for e in row['actions']],
                         [('TW:1000','2019-12-31','除息')])
        self.assertEqual(row['actions'][0]['row_number'], 2)
        self.assertEqual(len(result['sources']),3)
        self.assertIn('action_in_price_interval', row['warnings'])

    def test_date_only_capture_and_later_acquisition_do_not_imply_no_actions(self):
        a = self.bundle('2019-12-30', '20')
        b = self.bundle('2019-12-31', '22')
        blank = self.capture('2019-12-31', [('', '')])
        late = self.capture('2019-12-31', [('1000','權息')], received='2020-01-03T09:00:00Z')
        result = self.compare(a, b, '--action-manifest', late, '--action-manifest', blank)
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['sources'][0]['date_only_rows'], 1)
        self.assertEqual(result['sources'][0]['identified_event_rows'], 0)
        self.assertEqual(result['stocks'][0]['actions'], [])
        self.assertEqual(result['stocks'][0]['status'], 'coverage_unknown')

    def test_other_market_never_receives_tpex_action_for_same_code(self):
        a = self.bundle('2019-12-30', '20', feed='twse')
        b = self.bundle('2019-12-31', '22', feed='twse')
        capture = self.capture('2019-12-31', [('1000', '除權')])
        row = self.compare(a, b, '--action-manifest', capture)['stocks'][0]
        self.assertEqual(row['actions'], [])
        self.assertIn('ex_rights_dividend', row['unknown_interval_coverage'])

    def test_changed_original_bytes_or_resource_url_reject_evidence(self):
        a = self.bundle('2019-12-30', '20')
        path = Path(self.capture('2019-12-30', [('1000','息')]))
        original = path.read_bytes()
        receipt = json.loads(original)
        receipt[0]['url'] = 'https://example.org/other'
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.compare(a, a, '--action-manifest', str(path))
        path.write_bytes(original)
        (path.parent/'11633.response').write_bytes(b'different bytes')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.compare(a, a, '--action-manifest', str(path))

    def test_same_stock_different_price_basis_blocks_comparison(self):
        from local.bundle_audit import audit_bundle
        from local.research_compare import compare
        a = audit_bundle(self.root/'runs', self.bundle('2019-12-30', '20'))
        b = audit_bundle(self.root/'runs', self.bundle('2019-12-31', '22'))
        # A future reader may provide another basis. Today's audit accepts raw only.
        next(f for f in b.facts['facts'] if f['kind']=='market_price')['price_basis'] = 'split_adjusted'
        row = compare(a, b, price_review=True)['price_review']['stocks'][0]
        self.assertEqual(row['status'], 'incomparable')
        self.assertEqual(row['definition_differences'], ['price_basis'])

    def test_older_bundle_without_facts_does_not_substitute_display_price(self):
        from local.bundle_audit import audit_bundle
        from local.research_compare import compare
        a = audit_bundle(self.root/'runs', self.bundle('2019-12-30', '20'))
        b = audit_bundle(self.root/'runs', self.bundle('2019-12-31', '22'))
        a.facts = None
        row = compare(a, b, price_review=True)['price_review']['stocks'][0]
        self.assertIsNone(row['before'])
        self.assertEqual(row['status'], 'unavailable')

    def test_same_saved_trade_date_has_no_intervening_action_interval(self):
        a = self.bundle('2019-12-30', '20')
        row = self.compare(a, a)['stocks'][0]
        self.assertEqual(row['status'], 'same_trade_date')
        self.assertEqual(row['unknown_interval_coverage'], [])
        self.assertNotIn('action_coverage_unknown', row['warnings'])
