"""Real local CSV/SQLite/bundle audits, CLI and HTTP; no provider/model/Git IO."""
import copy
import http.client
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from local.bundle_audit import audit_bundle
from local.core import ROOT
from local.event_study import build, main, save_report, make_server
from local.market_prices import ingest
from local.research import run
from local.research_history import canonical
from test_alert_integration import csv_data
from test_alerts import payload, SID
from event_fixtures import outcome

ASOF='2020-09-30T23:59:59+08:00'
CONFIG={'quote_horizons':[1,2], 'revenue_horizons':[1]}


def research_run(root,n,day,close,volume,*,alerts=False,data=None):
    """Backdated synthetic clocks are test-only; product CLI never backdates runs."""
    root=Path(root);known=day+'T20:00:00+08:00'
    body=csv_data(day,close,volume)
    ingest(body,'twse',['1000'],day,db=root/'prices.db',output=root/'raw',
           observed_at=day+'T18:00:00+08:00',acquisition='local_file_unverified')
    data=copy.deepcopy(data or payload());data['metadata']['observed_at']=known
    p=root/f'input-{n}.json';p.write_bytes(canonical(data))
    with patch('local.research.utc_now',return_value=known),patch('local.research_history.utc_now',return_value=known):
        return run(p,['1000'],history_db=root/'ledger.db',output_root=root/'runs',
                   alerts=alerts,alerts_config={'volume_window':1} if alerts else None,
                   prices_db=root/'prices.db',price_snapshots=root/'raw',trade_date=day)


class EventIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.pre=research_run(self.root,0,'2020-08-14','100',1000)
        self.first=research_run(self.root,1,'2020-08-15','110',3000,alerts=True)
        self.second=research_run(self.root,2,'2020-08-16','121',1500)
        self.third=research_run(self.root,3,'2020-08-17','99',0)
    def study(self):return build(self.root/'runs',ASOF,config=CONFIG)
    def test_true_bundle_audit_and_descriptive_integration(self):
        result=self.study();self.assertEqual(result['counts']['events'],6)
        self.assertEqual(outcome(result)['value'],'10.000000')
        self.assertEqual(outcome(result,horizon=2)['value'],'-10.000000')
        self.assertEqual(outcome(result,metric='volume_ratio')['value'],'0.500000')
        self.assertEqual(outcome(result)['baseline']['raw_snapshot_verified'],True)
        self.assertEqual(len(result['inputs']),4)
    def test_full_report_reproducible_read_only_no_network(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('forbidden network')):
            a=self.study();b=self.study()
        self.assertEqual(a,b)
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_cli_subprocess_writes_only_new_report(self):
        output=self.root/'event-report.json';config=self.root/'config.json';config.write_bytes(canonical(CONFIG))
        result=subprocess.run([sys.executable,'-m','local.event_study','--root',str(self.root/'runs'),
            '--as-of',ASOF,'--config',str(config),'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('No trading/publication',result.stdout)
        self.assertEqual(json.loads(output.read_text()),self.study())
    def test_idempotent_report_and_no_overwrite(self):
        output=self.root/'report.json';report=self.study()
        save_report(report,output,self.root/'runs');before=output.read_bytes()
        save_report(report,output,self.root/'runs');self.assertEqual(before,output.read_bytes())
        with self.assertRaises(FileExistsError):save_report({'different':True},output,self.root/'runs')
        self.assertEqual(before,output.read_bytes())
    def test_report_symlink_parent_and_bundle_paths_rejected(self):
        report=self.study();target=self.root/'other';target.mkdir();link=self.root/'link';link.symlink_to(target,target_is_directory=True)
        for path in (link/'report.json',self.root/'runs/report.json',ROOT/'data/events.json'):
            with self.subTest(path=path),self.assertRaises(ValueError):save_report(report,path,self.root/'runs')
    def test_output_does_not_clobber_config(self):
        config=self.root/'config.json';config.write_bytes(canonical(CONFIG))
        with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            main(['--root',str(self.root/'runs'),'--as-of',ASOF,'--config',str(config),'--output',str(config)])
        self.assertEqual(json.loads(config.read_text()),CONFIG)
    def test_invalid_bundle_not_silently_removed_from_sample(self):
        p=self.root/'runs'/self.second['run']/'graph.db';p.write_bytes(p.read_bytes()+b'bad')
        with self.assertRaisesRegex(ValueError,'invalid catalog'):self.study()
    def test_missing_latest_not_implicitly_reselected(self):
        (self.root/'runs/latest.json').unlink()
        with self.assertRaisesRegex(ValueError,'latest'):self.study()
    def test_graph_tamper_fails_before_report_write(self):
        p=self.root/'runs'/self.first['run']/'data/stocks/1000/graph.json';p.write_text('{}')
        output=self.root/'report.json'
        with self.assertRaises(ValueError):main(['--root',str(self.root/'runs'),'--as-of',ASOF,'--output',str(output)])
        self.assertFalse(output.exists())
    def test_analysis_cutoff_ignores_later_capture(self):
        r=build(self.root/'runs','2020-08-16T23:00:00+08:00',config=CONFIG)
        self.assertEqual(outcome(r,horizon=2)['status'],'insufficient_data')
        self.assertEqual(r['counts']['runs_after_cutoff'],1)
    def test_latest_snapshot_holds_baseline_even_after_later_restatement(self):
        data=payload()
        for m in data['financial_metrics']:
            if m['metric']=='monthly_revenue_yoy_pct':m['value']=99
        research_run(self.root,4,'2020-08-18','99',0,data=data)
        e=next(e for e in self.study()['categories']['monthly_revenue']['events'] if e['rule_id']=='revenue_yoy')
        self.assertEqual(e['baseline']['monthly_revenue_yoy_pct']['value'],30)
    def test_monetary_unknown_scale_is_explicit_while_yoy_works(self):
        data=payload();data['financial_metrics']=[]
        for kind,value,unit in [('monthly_revenue',1200,'source_reported'),('monthly_revenue_yoy_pct',45,'percent')]:
            data['financial_metrics'].append({'stock_id':SID,'source_id':'fixture','metric':kind,'period_end':'2020-08-31',
                'period_type':'month','value':value,'unit':unit,'available_at':'2020-09-10T08:00:00Z'})
        research_run(self.root,4,'2020-09-10','120',1000,data=data)
        r=self.study()
        self.assertEqual(outcome(r,metric='revenue_yoy_change_pp')['value'],'15.000000')
        self.assertEqual(outcome(r,metric='revenue_change_pct')['status'],'not_comparable')
    def test_invalid_config_budgets_fail(self):
        for values in ({'max_mib':0},{'max_runs':0},{'max_mib':True},{'config':{'quote_horizons':[0]}}):
            with self.subTest(values=values),self.assertRaises(ValueError):build(self.root/'runs',ASOF,**values)
    def test_duplicate_run_budget_refused(self):
        with self.assertRaises(ValueError):build(self.root/'runs',ASOF,max_runs=1)
    def test_no_usable_outcomes_not_fake_successful_average(self):
        result=build(self.root/'runs','2020-08-15T21:00:00+08:00',config=CONFIG)
        self.assertEqual(result['counts']['events'],6)
        for category in result['categories'].values():
            self.assertTrue(all(s['n_observed']==0 and s['statistics'] is None for s in category['summaries']))
    def test_private_http_allowlist_and_immutable_response(self):
        report=self.study();server=make_server(report,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3);self.addCleanup(conn.close)
        conn.request('GET','/event-study.json');response=conn.getresponse();body=response.read()
        self.assertEqual(response.status,200);self.assertEqual(json.loads(body),report)
        report['counts']['events']=999
        conn.request('GET','/event-study.json');response=conn.getresponse();self.assertEqual(response.read(),body)
        for path in ('/../ledger.db','/data/manifest.json','/raw','/report.json','/.env','/api/compare','/runs'):
            conn.request('GET',path);response=conn.getresponse();response.read();self.assertEqual(response.status,404,path)
        conn.request('GET','/',headers={'Host':'evil.example'});response=conn.getresponse();response.read();self.assertEqual(response.status,403)
        conn.request('HEAD','/');response=conn.getresponse();self.assertEqual(response.status,200);self.assertEqual(response.read(),b'')
        conn.request('POST','/');response=conn.getresponse();response.read();self.assertEqual(response.status,501)
    def test_public_data_unchanged(self):
        files={p:p.read_bytes() for p in (ROOT/'data').rglob('*.json')}
        self.study();self.assertEqual(files,{p:p.read_bytes() for p in files})
