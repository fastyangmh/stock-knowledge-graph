"""Public market ingestion, readback and reconciliation behavior."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.market_prices import ingest
from local.market_graph import read_prices

CSV = '日期,證券代號,證券名稱,開盤價,最高價,最低價,收盤價,成交股數,成交金額,成交筆數\n20200102,1000,Synthetic,10.00,12.00,9.00,11.00,1000,11000,20\n'.encode()
DAY = '2020-01-02'
OBS = '2020-01-02T09:00:00Z'


def definition(body=CSV):
    return {'schema_version': 'market-unit-review-1.0', 'source_id': 'twse_daily_11549',
            'raw_sha256': hashlib.sha256(body).hexdigest(), 'trade_date': DAY, 'symbols':['1000'],
            'price_unit': 'currency_per_share', 'price_currency': 'TWD',
            'volume_unit': 'share', 'turnover_unit': 'currency', 'turnover_currency': 'TWD',
            'trades_unit': 'trade', 'price_basis': 'source_unadjusted',
            'trading_scope': 'regular_only',
            'evidence': [{'url': 'https://www.twse.com.tw/example', 'sha256': 'a'*64,
                          'locator': 'synthetic official notes', 'retrieved_at': OBS}]}


class MarketUnitReviewTests(unittest.TestCase):
    def test_reviewed_units_roundtrip_without_rewriting_legacy_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = ingest(CSV, 'twse', ['1000'], DAY, db=root/'old.db', output=root/'old',
                         observed_at=OBS, acquisition='local_file_unverified')
            new = ingest(CSV, 'twse', ['1000'], DAY, db=root/'new.db', output=root/'new',
                         observed_at=OBS, acquisition='local_file_unverified', unit_review=definition())
            self.assertEqual(old['records'][0]['price_unit'], 'source_reported')
            value = read_prices(root/'new.db', 'twse', ['1000'], DAY, OBS, root/'new')[0]
            self.assertTrue(value['raw_snapshot_verified'])
            self.assertEqual(value['record']['price_currency'], 'TWD')
            self.assertEqual(value['record']['raw_values']['open'], '10.00')
            self.assertEqual(value['record']['normalization_version'], 'market-units-2.0')
            self.assertEqual(read_prices(root/'old.db', 'twse', ['1000'], DAY, OBS, root/'old')[0]['record'], old['records'][0])

    def test_market_review_cli_reports_seven_fields_and_rejects_unknown_or_mismatched_units(self):
        from local.market_review import main
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference_bytes = b'Synthetic independently transcribed reference; not the input CSV'
            (root/'reference.txt').write_bytes(reference_bytes)
            record = {'market': 'TWSE', 'symbol': '1000', 'trade_date': DAY,
                      'open': '10', 'high': '12', 'low': '9', 'close': '11',
                      'volume_shares': 1000, 'turnover_raw': '11000', 'trades': 20,
                      **{k:v for k,v in definition().items() if k not in ('schema_version','source_id','raw_sha256','trade_date','evidence')},
                      'evidence_id': 'independent', 'locator': 'row 1000, seven column labels'}
            reference = {'schema_version':'market-reference-1.0', 'records':[record],
                         'evidence':[{'id':'independent', 'path':'reference.txt',
                                      'sha256':hashlib.sha256(reference_bytes).hexdigest(),
                                      'url':'https://www.twse.com.tw/independent', 'retrieved_at':OBS}]}
            ingest(CSV, 'twse', ['1000'], DAY, db=root/'prices.db', output=root/'raw',
                   observed_at=OBS, acquisition='local_file_unverified', unit_review=definition())
            args=['--db',str(root/'prices.db'),'--snapshots',str(root/'raw'),'--market','twse',
                  '--symbols','1000','--trade-date',DAY,'--known-at',OBS,
                  '--reference',str(root/'reference.json'),'--output',str(root/'report.json')]
            (root/'reference.json').write_text(json.dumps(reference))
            self.assertEqual(main(args),0)
            report=json.loads((root/'report.json').read_text())
            self.assertEqual(report['counts'],{'equal':7})
            self.assertEqual(report['compared_fields'],7)
            self.assertEqual(report['rows'][0]['allowed_difference'],'0')
            for key,value in [('volume_unit','lot'),('price_currency','USD'),('trading_scope','unknown')]:
                changed=copy.deepcopy(reference); changed['records'][0][key]=value
                (root/'reference.json').write_text(json.dumps(changed))
                self.assertEqual(main(args),2)
                self.assertTrue(json.loads((root/'report.json').read_text())['needs_review'])
            reference['records']=[]
            (root/'reference.json').write_text(json.dumps(reference))
            self.assertEqual(main(args),2)
            (root/'reference.txt').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'checksum'):
                main(args)

    def test_reminders_reject_same_numbers_with_changed_market_definition(self):
        from test_alerts import prices, compute, checks
        for key,value in [('price_currency','USD'),('volume_unit','lot'),
                          ('turnover_currency','USD'),('turnover_unit','thousand_currency'),
                          ('trading_scope','regular_only'),('normalization_version','other')]:
            with self.subTest(key=key):
                rows=prices(); rows[-1]['record'][key]=value
                result=checks(compute(history=rows))
                self.assertEqual(result['price_change']['status'],'not_comparable')
                self.assertEqual(result['volume_ratio']['status'],'not_comparable')

    def test_event_results_reject_changed_currency_scope_or_normalization(self):
        from event_fixtures import bundle, outcome
        from test_alerts import SID
        from local.event_study import analyze
        first=bundle(alerts=True)
        for key,value in [('price_currency','USD'),('volume_unit','lot'),
                          ('trading_scope','regular_only'),('normalization_version','other')]:
            with self.subTest(key=key):
                later=bundle(2,'2020-08-16',close='115.5',volume=1000)
                later.graphs[SID]['nodes'][-1][key]=value
                report=analyze([first,later],'2020-12-31T23:59:59+08:00',
                               {'quote_horizons':[1],'revenue_horizons':[1]})
                self.assertEqual(outcome(report)['status'],'not_comparable')

    def test_unit_attestation_is_bound_to_exact_raw_date_and_reviewed_symbols(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for key,value in [('raw_sha256','f'*64),('trade_date','2020-01-01'),('symbols',['9999'])]:
                with self.subTest(key=key):
                    changed=definition(); changed[key]=value
                    with self.assertRaisesRegex(ValueError,'review'):
                        ingest(CSV,'twse',['1000'],DAY,db=root/'p.db',output=root/'raw',
                               observed_at=OBS,acquisition='local_file_unverified',unit_review=changed)
            self.assertFalse((root/'p.db').exists())

    def test_research_audit_preserves_review_and_rejects_unversioned_injected_units(self):
        from unittest.mock import patch
        from local.research import run
        from local.bundle_audit import audit_bundle
        from local.research_history import canonical
        from test_research_history import payload
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'input.json').write_bytes(canonical(payload()))
            for label,units in [('legacy',None),('reviewed',definition())]:
                ingest(CSV,'twse',['1000'],DAY,db=root/(label+'.db'),output=root/label,
                       observed_at=OBS,acquisition='local_file_unverified',unit_review=units)
                with patch('local.research.utc_now',return_value=OBS), patch('local.research_history.utc_now',return_value=OBS):
                    report=run(root/'input.json',['1000'],history_db=root/'ledger.db',output_root=root/'runs',
                               prices_db=root/(label+'.db'),price_snapshots=root/label,trade_date=DAY)
                bundle=audit_bundle(root/'runs',report['run'])
                market=next(row for row in bundle.facts['facts'] if row['kind']=='market_price')
                if units:
                    self.assertEqual(market['unit_review'],units)
                    self.assertEqual(market['raw_values']['open'],'10.00')
                else:
                    legacy_bundle=bundle
            directory=root/'runs'/legacy_bundle.report['run']
            facts=copy.deepcopy(legacy_bundle.facts)
            next(row for row in facts['facts'] if row['kind']=='market_price')['price_currency']='USD'
            body=canonical(facts); (directory/'research-facts.json').write_bytes(body)
            report=copy.deepcopy(legacy_bundle.report)
            report['research_facts'].update(sha256=hashlib.sha256(body).hexdigest(),size_bytes=len(body))
            (directory/'report.json').write_bytes(canonical(report))
            with self.assertRaisesRegex(ValueError,'normalization|unversioned'):
                audit_bundle(root/'runs',legacy_bundle.report['run'])

    def test_review_differences_empty_input_and_same_raw_reference_never_pass(self):
        from local.market_prices import normalize
        from local.market_review import review
        from local.market_units import apply_review
        legacy=normalize(CSV,'twse',['1000'],DAY,OBS)['records'][0]
        row=apply_review(legacy,definition(),'twse_daily_11549',hashlib.sha256(CSV).hexdigest())
        item={'record':row,'raw_snapshot_verified':True,'raw_sha256':hashlib.sha256(CSV).hexdigest()}
        evidence={'id':'independent','url':'https://www.twse.com.tw/ref','sha256':'b'*64,'retrieved_at':OBS}
        ref={'schema_version':'market-reference-1.0','records':[{**row,'close':'10.5','evidence_id':'independent','locator':'seven source columns'}], 'evidence':[evidence]}
        report=review([item],ref,['1000'],DAY,'TWSE')
        self.assertEqual(report['counts'],{'equal':6,'value_mismatch':1})
        self.assertTrue(report['needs_review'])
        self.assertEqual(next(r for r in report['rows'] if r['field']=='close')['difference'],'0.50')
        self.assertTrue(review([],ref,['1000'],DAY,'TWSE')['needs_review'])
        ref['records'][0]['close']='11.00'; evidence['sha256']=item['raw_sha256']
        self.assertTrue(review([item],ref,['1000'],DAY,'TWSE')['needs_review'])
