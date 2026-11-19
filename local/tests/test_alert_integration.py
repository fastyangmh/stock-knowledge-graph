"""Real CSV/snapshot/SQLite/bundle tests; no API, model download or publication."""
import copy
import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local.alert_inputs import load_price_history
from local.alerts import evaluate
from local.core import ROOT
from local.market_prices import FEEDS, ingest
from local.research import run, main
from local.research_history import canonical
from local.validate_release import validate_data_dir
from test_alerts import payload, prices, TARGET, CUTOFF, SID, checks


def csv_data(day, close='100', volume=1000):
    output=io.StringIO(newline='');writer=csv.writer(output)
    writer.writerow(FEEDS['twse']['columns'])
    price = 100 if close == '--' else float(close)
    writer.writerow([day,'1000','Synthetic','100',max(100,price),min(100,price),close,volume,'200000',10])
    return output.getvalue().encode()


class AlertIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=self.root/'market.db';self.raw=self.root/'raw'
        self.input=self.root/'normalized.json';self.input.write_bytes(canonical(payload()))
        self.history=self.root/'history.db';self.output=self.root/'runs'
    def ingest(self,day,close='100',volume=1000,observed=None):
        return ingest(csv_data(day,close,volume),'twse',['1000'],day,db=self.db,output=self.raw,
                      observed_at=observed or day+'T18:00:00+08:00',acquisition='local_file_unverified')
    def market(self):
        for day in ('2020-08-12','2020-08-13','2020-08-14'):self.ingest(day)
        self.ingest(TARGET,'110',3000)
    def execute(self,**kw):
        return run(self.input,['1000'],history_db=self.history,output_root=self.output,**kw)
    def test_full_real_bundle_separate_alerts_and_export_checksum(self):
        self.market();before=(ROOT/'data/manifest.json').read_bytes()
        result=self.execute(alerts=True,alerts_config={'volume_window':3},prices_db=self.db,
                            trade_date=TARGET,price_snapshots=self.raw)
        bundle=self.output/result['run']
        self.assertEqual(validate_data_dir(bundle/'data'),1)
        report=json.loads((bundle/'alerts.json').read_text())
        graph=json.loads((bundle/'data/stocks/1000/graph.json').read_text())
        self.assertEqual(graph['research_alerts'],report['stocks'][SID])
        self.assertEqual(result['research_alerts']['sha256'],hashlib.sha256((bundle/'alerts.json').read_bytes()).hexdigest())
        self.assertEqual(result['research_alerts']['triggered_by_category'],{'price_volume':2,'monthly_revenue':4})
        self.assertFalse(result['research_alerts']['combined_score']);self.assertFalse(result['public_publish'])
        self.assertEqual((ROOT/'data/manifest.json').read_bytes(),before)
        with sqlite3.connect(bundle/'graph.db') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM documents').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM embeddings').fetchone()[0],0)
    def test_disabled_preserves_old_contract(self):
        result=self.execute()
        self.assertNotIn('research_alerts',result)
        self.assertFalse((self.output/result['run']/'alerts.json').exists())
    def test_revenue_only_has_explicit_price_insufficient_not_no_alert(self):
        result=self.execute(alerts=True)
        r=json.loads((self.output/result['run']/'alerts.json').read_text())['stocks'][SID]
        self.assertEqual(len(r['categories']['price_volume']),2)
        self.assertTrue(all(c['status']=='insufficient_data' for c in r['categories']['price_volume']))
        self.assertTrue(all(c['status']=='triggered' for c in r['categories']['monthly_revenue']))
    def test_no_revenue_percentages_does_not_block_price_group(self):
        data=payload();data['financial_metrics']=[];self.input.write_bytes(canonical(data));self.market()
        result=self.execute(alerts=True,alerts_config={'volume_window':3},prices_db=self.db,trade_date=TARGET,price_snapshots=self.raw)
        self.assertEqual(result['research_alerts']['triggered_by_category']['price_volume'],2)
        self.assertEqual(result['research_alerts']['triggered_by_category']['monthly_revenue'],0)
    def test_invalid_policy_fails_before_writes(self):
        for options in ({'alerts':True,'alerts_config':{'volume_window':0}}, {'alerts_config':{}}):
            with self.subTest(options=options),self.assertRaises(ValueError):self.execute(**options)
        self.assertFalse(self.output.exists());self.assertFalse(self.history.exists())
    def test_cli_config_private_and_no_network(self):
        config=self.root/'alerts.json';config.write_text('{"revenue_yoy_pct":999}')
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')),redirect_stdout(io.StringIO()):
            main(['--input',str(self.input),'--symbols','1000','--history-db',str(self.history),'--output-root',str(self.output),
                  '--alerts','--alerts-config',str(config)])
        latest=json.loads((self.output/'latest.json').read_text());report=json.loads((self.output/latest['run']/'alerts.json').read_text())
        self.assertEqual(checks(report['stocks'][SID])['revenue_yoy']['status'],'not_triggered')
        with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            main(['--input',str(self.input),'--symbols','1000','--alerts-config',str(config)])
    def test_revisions_at_cutoff_use_old_quote_and_verified_raw(self):
        self.market();self.ingest(TARGET,'120',6000,observed='2020-08-16T18:00:00+08:00')
        history=load_price_history(self.db,'twse',['1000'],TARGET,CUTOFF,self.raw,{'volume_window':3})
        self.assertEqual(history[SID][-1]['record']['close'],'110')
        self.assertTrue(all(p['raw_snapshot_verified'] for p in history[SID]))
        newer=load_price_history(self.db,'twse',['1000'],TARGET,'2020-08-17T00:00:00Z',self.raw,{'volume_window':3})
        self.assertEqual(newer[SID][-1]['record']['close'],'120')
    def test_missing_baseline_quotes_do_not_abort_report(self):
        self.ingest(TARGET,'110',3000)
        result=self.execute(alerts=True,prices_db=self.db,trade_date=TARGET,price_snapshots=self.raw)
        report=json.loads((self.output/result['run']/'alerts.json').read_text())['stocks'][SID]
        self.assertEqual(checks(report)['volume_ratio']['status'],'insufficient_data')
    def test_corrupted_baseline_snapshot_blocks_new_bundle(self):
        self.market();first=self.execute(alerts=True,prices_db=self.db,trade_date=TARGET,price_snapshots=self.raw)
        pointer=(self.output/'latest.json').read_bytes()
        with sqlite3.connect(self.db) as conn:
            sha,source=conn.execute('SELECT raw_sha256,source_id FROM market_price_observations ORDER BY trade_date LIMIT 1').fetchone()
        (self.raw/source/(sha+'.csv')).write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'):
            self.execute(alerts=True,prices_db=self.db,trade_date=TARGET,price_snapshots=self.raw)
        self.assertEqual((self.output/'latest.json').read_bytes(),pointer)
    def test_alert_failure_does_not_replace_latest(self):
        self.execute();pointer=(self.output/'latest.json').read_bytes()
        with patch('local.alerts.evaluate',side_effect=ValueError('bad evidence')),self.assertRaises(ValueError):
            self.execute(alerts=True)
        self.assertEqual((self.output/'latest.json').read_bytes(),pointer)
    def test_tampered_alerts_rejected_even_if_graph_checksum_updated(self):
        result=self.execute(alerts=True);bundle=self.output/result['run'];p=bundle/'data/stocks/1000/graph.json'
        graph=json.loads(p.read_text());graph['research_alerts']['categories']['monthly_revenue'][0]['value']='999'
        p.write_text(json.dumps(graph));m=bundle/'data/manifest.json';manifest=json.loads(m.read_text())
        manifest['stocks'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'alert content hash'):validate_data_dir(bundle/'data')
    def test_loader_bounds_and_read_only(self):
        self.market();before=self.db.read_bytes()
        result=load_price_history(self.db,'twse',['1000'],TARGET,CUTOFF,self.raw,{'volume_window':2})
        self.assertEqual(len(result[SID]),3);self.assertEqual(self.db.read_bytes(),before)
        link=self.root/'link.db';link.symlink_to(self.db)
        with self.assertRaises(ValueError):load_price_history(link,'twse',['1000'],TARGET,CUTOFF,self.raw)
