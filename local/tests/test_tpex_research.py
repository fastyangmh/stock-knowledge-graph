"""TPEx public ingestion boundaries, synthetic HTTP and real private bundles."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from local.bundle_audit import catalog
from local.collect_official import main as collect_main
from local.core import ROOT
from local.market_graph import read_prices
from local.market_prices import FEEDS, ingest, main as prices_main
from local.official_import import main as import_main
from local.research import run
from test_official_collection import Response

DAY = '2020-01-02'
WHEN = '2020-01-02T10:00:00+00:00'
LATER = '2020-01-03T10:00:00+00:00'
# Literal source column order, including unused fields: not built from FEEDS.
PRICES = ('資料日期,代號,名稱,收盤,漲跌,開盤,最高,最低,成交股數,成交金額,成交筆數,最後買價,最後賣價,發行股數,次日漲停價,次日跌停價\n'
          '1090102,1000,Synthetic A,11.50,+,10.10,12.00,9.00,1000,11500,4,11.50,11.60,100000,12.65,10.35\n'
          '1090102,1001,Synthetic B,21.00,+,20.00,22.00,19.00,2000,42000,8,21.00,21.10,200000,23.10,18.90\n').encode()
COMPANY = ('出表日期,公司代號,公司名稱,公司簡稱,上櫃日期\n'
           '1090102,1000,Synthetic A,A,1000101\n1090102,1001,Synthetic B,B,1000101\n').encode()
REVENUE = ('出表日期,資料年月,公司代號,公司名稱,營業收入-當月營收\n'
           '1090102,10812,1000,Synthetic A,1000\n1090102,10812,1001,Synthetic B,2000\n').encode()


class TPExResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = [s for s in json.loads((ROOT/'local/official_datasets.json').read_text())
                        if s['dataset_id'] in ('tpex_companies', 'tpex_monthly_revenue')]
        for source in self.sources:
            source['enabled'] = True
        self.registry = self.root/'registry.json'
        self.registry.write_text(json.dumps(self.sources))
        self.price_args = ['--market', 'tpex', '--symbols', '1000', '1001', '--expected-date', DAY,
                           '--db', str(self.root/'prices.db'), '--output', str(self.root/'prices')]
        self.options = dict(history_db=self.root/'history.db', output_root=self.root/'runs',
                            prices_db=self.root/'prices.db', price_snapshots=self.root/'prices',
                            price_market='tpex', trade_date=DAY, analysis='none', alerts=True)

    def collect(self, responses=None):
        responses = responses or [Response(body, source['resource_url'])
                                  for body, source in zip((COMPANY, REVENUE), self.sources)]
        with patch('local.collect_official.build_opener') as opener, \
             patch('local.collect_official.now', return_value=WHEN), \
             patch('local.collect_official.time.sleep'), redirect_stdout(io.StringIO()):
            opener.return_value.open.side_effect = responses
            collect_main(['--registry', str(self.registry), '--output-dir', str(self.root/'official'),
                          '--symbols', '1000', '1001'])

    def prepare(self):
        self.collect()
        with redirect_stdout(io.StringIO()):
            import_main(['--registry', str(self.registry), '--snapshot-dir', str(self.root/'official'),
                         '--symbols', '1000', '1001', '--as-of', DAY, '--output', str(self.root/'input.json')])
        with patch('local.market_prices.build_opener') as opener, redirect_stdout(io.StringIO()):
            opener.return_value.open.return_value = Response(PRICES, FEEDS['tpex']['resource_url'], 'application/csv')
            prices_main(self.price_args)
        return run(self.root/'input.json', ['1000', '1001'], **self.options)

    def preserved(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in (
            self.root/'official/retrieval_manifest.json', self.root/'prices/latest-tpex.json',
            self.root/'prices.db', self.root/'runs/latest.json')}

    def test_tpex_http_to_independent_financial_and_price_bundle(self):
        result = self.prepare()
        normalized = json.loads((self.root/'input.json').read_text())
        self.assertEqual({s['source_id'] for s in normalized['sources']},
                         {'tpex_companies', 'tpex_monthly_revenue'})
        self.assertEqual(result['counts']['market_nodes'], 2)
        self.assertEqual(result['counts']['financial_metric_nodes'], 2)
        report = json.loads((self.root/'prices/latest-tpex.json').read_text())
        self.assertEqual(report['http_status'], 200)
        self.assertEqual(report['profile']['date_distribution'], {DAY: 2})
        self.assertEqual(report['profile']['selected_symbol_rows'], {'1000': 1, '1001': 1})
        self.assertEqual((self.root/'prices'/report['snapshot_path']).read_bytes(), PRICES)
        graph = json.loads((self.root/'runs'/result['run']/'data/stocks/1000/graph.json').read_text())
        price = next(n for n in graph['nodes'] if n['type'] == 'market_price')
        self.assertEqual(price['close'], '11.50')
        self.assertEqual(price['source_id'], 'tpex_daily_11371')
        audit, _ = catalog(self.root/'runs')
        self.assertTrue(audit['latest_valid'])
        self.assertEqual(audit['counts']['invalid'], 0)

    def test_bad_tpex_batches_keep_market_and_research_success(self):
        self.prepare()
        before = self.preserved()
        wrong_market = PRICES.replace('資料日期,代號,名稱'.encode(), '日期,證券代號,證券名稱'.encode())
        cases = [PRICES.replace('成交股數'.encode(), 'missing'.encode()),
                 PRICES.replace(b'1090102', b'1090101'),
                 PRICES.replace(b'1090102,1001', b'1090101,1001'),
                 PRICES.replace(b'1001,', b'1002,'), b'<html>denied</html>', wrong_market]
        for body in cases:
            with self.subTest(body=body[:90]):
                previous = set((self.root/'prices').glob('retrieval-failure-*.json'))
                source = self.root/'bad.csv'
                source.write_bytes(body)
                with self.assertRaises(ValueError):
                    prices_main([*self.price_args, '--input', str(source)])
                failures = set((self.root/'prices').glob('retrieval-failure-*.json')) - previous
                self.assertEqual(len(failures), 1)
                failure = json.loads(failures.pop().read_text())['failure']
                self.assertEqual(failure['dataset_id'], '11371')
                self.assertEqual((self.root/'prices'/failure['path']).read_bytes(), body)
                self.assertEqual(self.preserved(), before)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            run(self.root/'input.json', ['1000', '1001'], **{**self.options, 'price_market': 'twse'})
        self.assertEqual(self.preserved(), before)

    def test_tpex_403_and_partial_financial_failure_keep_success(self):
        self.prepare()
        before = self.preserved()
        denied = b'<html>forbidden</html>'
        def error(url):
            return HTTPError(url, 403, 'Forbidden', {'Content-Type': 'text/html'}, io.BytesIO(denied))
        with patch('local.market_prices.build_opener') as opener:
            opener.return_value.open.side_effect = error(FEEDS['tpex']['resource_url'])
            with self.assertRaises(HTTPError):
                prices_main(self.price_args)
        with self.assertRaises(HTTPError):
            self.collect([Response(COMPANY, self.sources[0]['resource_url']), error(self.sources[1]['resource_url'])])
        for directory, dataset in [('prices', '11371'), ('official', 'tpex_monthly_revenue')]:
            failure = json.loads(next((self.root/directory).glob('retrieval-failure-*.json')).read_text())['failure']
            self.assertEqual(failure['dataset_id'], dataset)
            self.assertEqual(failure['http_status'], 403)
            self.assertEqual(failure['content_type'], 'text/html')
            self.assertEqual((self.root/directory/failure['path']).read_bytes(), denied)
        self.assertEqual(self.preserved(), before)

    def test_tpex_replay_revision_and_raw_checksum(self):
        arguments = dict(db=self.root/'prices.db', output=self.root/'prices', acquisition='local_file_unverified')
        first = ingest(PRICES, 'tpex', ['1000', '1001'], DAY, observed_at=WHEN, **arguments)
        again = ingest(PRICES, 'tpex', ['1000', '1001'], DAY, observed_at=WHEN, **arguments)
        self.assertEqual(again['inserted_observations'], 0)
        revised = PRICES.replace(b'Synthetic A,11.50', b'Synthetic A,11.60')
        ingest(revised, 'tpex', ['1000', '1001'], DAY, observed_at=LATER, **arguments)
        def read(known):
            return read_prices(self.root/'prices.db', 'tpex', ['1000', '1001'], DAY, known,
                               snapshot_dir=self.root/'prices')
        self.assertEqual(read(WHEN)[0]['record']['close'], '11.50')
        self.assertEqual(read(LATER)[0]['record']['close'], '11.60')
        (self.root/'prices'/first['snapshot_path']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            read(WHEN)
