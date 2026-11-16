"""True local end-to-end tests with synthetic observations and a fake encoder."""
import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local.core import ROOT
from local.collect_official import download
from local.official_import import main as official_main
from local.research import run, main
from local.research_history import canonical
from local.market_prices import ingest
from local.validate_release import validate_data_dir
from test_research_history import payload, T0, T1, T2, T3
from test_market_graph import CSV, DAY, OBS

class Encoder:
    def __init__(self):self.calls=[]
    def get_embedding_dimension(self):return 3
    def encode(self,texts,batch_size=32):
        self.calls.extend(texts);return [[1.,2.,3.] for _ in texts]

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.input=self.root/'normalized.json'
        self.ledger=self.root/'history.db';self.output=self.root/'runs';self.write(payload())
    def write(self,p):self.input.write_bytes(canonical(p))
    def execute(self,**kwargs):
        return run(self.input,['1000','1001'],history_db=self.ledger,output_root=self.output,**kwargs)
    def test_private_financial_bundle_and_provenance(self):
        before=(ROOT/'data/manifest.json').read_bytes()
        result=self.execute()
        bundle=self.output/result['run']
        self.assertEqual(validate_data_dir(bundle/'data'),2)
        self.assertEqual(result['counts']['financial_metric_nodes'],1)
        self.assertFalse(result['public_publish'])
        graph=json.loads((bundle/'data/stocks/1000/graph.json').read_text())
        metric=next(n for n in graph['nodes'] if n['type']=='financial_metric')
        self.assertEqual(metric['value'],1000);self.assertEqual(metric['source_id'],'synthetic')
        self.assertIn('input_snapshot_sha256',metric)
        self.assertFalse(any('universe_ids' in n for n in graph['nodes']))
        self.assertEqual((ROOT/'data/manifest.json').read_bytes(),before)
    def test_semantic_cache_and_graph_reused_between_immutable_bundles(self):
        encoder=Encoder();first=self.execute(analysis='semantic',model='test/model',revision='v1',encoder=encoder)
        first_data=(self.output/first['run']/'graph.db').read_bytes()
        with patch('local.semantic.load_encoder',side_effect=AssertionError('must not load model')):
            second=self.execute(analysis='semantic',model='test/model',revision='v1')
        self.assertEqual(first['analysis']['encoded'],1)
        self.assertEqual(second['analysis']['encoded'],0);self.assertTrue(second['analysis']['graph_reused'])
        self.assertEqual(second['analysis']['cached_vectors_copied'],1)
        self.assertEqual(first_data,(self.output/first['run']/'graph.db').read_bytes())
        self.assertNotEqual(first['run'],second['run'])
    def test_revision_reencodes_only_changed_text_and_preserves_history(self):
        first=self.execute(analysis='semantic',model='test/model',encoder=Encoder())
        self.write(payload(T2,1500))
        second=self.execute(analysis='semantic',model='test/model',encoder=Encoder())
        self.assertEqual(second['analysis']['encoded'],1)
        with sqlite3.connect(self.ledger) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM research_snapshots').fetchone()[0],2)
        for result,value in ((first,1000),(second,1500)):
            graph=json.loads((self.output/result['run']/'data/stocks/1000/graph.json').read_text())
            self.assertEqual(next(n for n in graph['nodes'] if n['type']=='financial_metric')['value'],value)
    def test_corrupt_previous_db_blocks_cache_reuse(self):
        first=self.execute();db=self.output/first['run']/'graph.db'
        with db.open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'database changed'):self.execute()
    def test_corrupt_latest_pointer_rejected(self):
        self.output.mkdir();(self.output/'latest.json').write_text('{"run":"../private"}')
        with self.assertRaisesRegex(ValueError,'unexpected latest'):self.execute()
    def test_failed_export_preserves_latest_and_old_files(self):
        first=self.execute();pointer=(self.output/'latest.json').read_bytes()
        with patch('local.research.export',side_effect=ValueError('injected failure')):
            with self.assertRaises(ValueError):self.execute()
        self.assertEqual((self.output/'latest.json').read_bytes(),pointer)
        self.assertEqual(len(list(self.output.glob('*/report.json'))),1)
        self.assertEqual(list(self.output.glob('.research-stage-*')),[])
        self.assertEqual(validate_data_dir(self.output/first['run']/'data'),2)
    def test_public_data_destination_and_symlinks_rejected(self):
        with self.assertRaises(ValueError):run(self.input,['1000'],history_db=self.ledger,output_root=ROOT/'data')
        link=self.root/'linked';link.symlink_to(self.output,target_is_directory=True)
        with self.assertRaises(ValueError):run(self.input,['1000'],history_db=self.ledger,output_root=link)
    def test_input_cannot_be_overwritten_by_db(self):
        with self.assertRaises(ValueError):run(self.input,['1000'],history_db=self.input,output_root=self.output)
    def test_prices_require_date_and_complete_stock_coverage(self):
        with self.assertRaisesRegex(ValueError,'together'):self.execute(prices_db=self.root/'no.db')
        db=self.root/'market.db';ingest(CSV,'twse',['1000'],DAY,db=db,output=self.root/'prices',observed_at=OBS,acquisition='local_file_unverified')
        with self.assertRaisesRegex(ValueError,'coverage'):self.execute(prices_db=db,trade_date=DAY,price_snapshots=self.root/'prices')
        self.assertFalse((self.output/'latest.json').exists())
    def test_actual_prices_and_financial_metrics_join_in_same_graph(self):
        db=self.root/'market.db';ingest(CSV,'twse',['1000'],DAY,db=db,output=self.root/'prices',observed_at=OBS,acquisition='local_file_unverified')
        result=run(self.input,['1000'],history_db=self.ledger,output_root=self.output,prices_db=db,trade_date=DAY,price_snapshots=self.root/'prices')
        self.assertEqual(result['counts']['market_nodes'],1)
        graph=json.loads((self.output/result['run']/'data/stocks/1000/graph.json').read_text())
        self.assertEqual({n['type'] for n in graph['nodes']},{'stock','financial','financial_metric','market_price'})
        self.assertTrue(all(e['score'] is None for e in graph['edges']))
        self.assertIn('market_input_is_unverified_local_file',result['quality']['warnings'])
        with sqlite3.connect(self.output/result['run']/'graph.db') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM documents').fetchone()[0],1)
    def test_cli_no_download_no_publish(self):
        with redirect_stdout(io.StringIO()),patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('no HTTP')):
            main(['--input',str(self.input),'--symbols','1000','--history-db',str(self.ledger),'--output-root',str(self.output)])
        self.assertTrue((self.output/'latest.json').is_file())
        with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            main(['--input',str(self.input),'--symbols','1000','--publish'])
    def test_explicit_subset_does_not_import_unselected_neighbors(self):
        result=run(self.input,['1000'],history_db=self.ledger,output_root=self.output)
        with sqlite3.connect(self.output/result['run']/'graph.db') as conn:
            self.assertEqual(conn.execute('SELECT stock_id FROM stocks').fetchall(),[('TW:1000',)])
    def test_budget_failure_leaves_old_bundle(self):
        data=payload();doc=copy.deepcopy(data['documents'][0]);doc['document_id']='d2';data['documents'].append(doc);self.write(data)
        first=self.execute();pointer=(self.output/'latest.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'budget'):self.execute(analysis='semantic',max_pairs=0,encoder=Encoder())
        self.assertEqual((self.output/'latest.json').read_bytes(),pointer)
    def test_semantic_price_record_does_not_enter_encoder(self):
        db=self.root/'market.db';ingest(CSV,'twse',['1000'],DAY,db=db,output=self.root/'prices',observed_at=OBS,acquisition='local_file_unverified')
        encoder=Encoder()
        result=run(self.input,['1000'],history_db=self.ledger,output_root=self.output,prices_db=db,trade_date=DAY,price_snapshots=self.root/'prices',
                   analysis='semantic',model='test/model',encoder=encoder)
        self.assertEqual(len(encoder.calls),1)
        self.assertNotIn('11.00',encoder.calls[0]);self.assertEqual(result['analysis']['documents'],1)
    def test_raw_price_snapshot_tamper_blocks_bundle(self):
        db=self.root/'market.db'
        info=ingest(CSV,'twse',['1000'],DAY,db=db,output=self.root/'prices',observed_at=OBS,acquisition='local_file_unverified')
        raw=self.root/'prices'/info['snapshot_path'];raw.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):
            run(self.input,['1000'],history_db=self.ledger,output_root=self.output,prices_db=db,trade_date=DAY,price_snapshots=self.root/'prices')
        self.assertFalse((self.output/'latest.json').exists())
    def test_future_cutoff_rejected_before_any_output(self):
        with self.assertRaisesRegex(ValueError,'future'):self.execute(known_at='2099-01-01T00:00:00Z')
        self.assertFalse(self.output.exists());self.assertFalse(self.ledger.exists())
    def test_invalid_budget_rejected_before_any_output(self):
        with self.assertRaisesRegex(ValueError,'budget'):self.execute(max_pairs=-1)
        self.assertFalse(self.output.exists());self.assertFalse(self.ledger.exists())
    def test_invalid_analysis_rejected(self):
        with self.assertRaises(ValueError):self.execute(analysis='predict')
    def test_lexical_mode_labeled_correctly(self):
        result=self.execute(analysis='lexical',threshold=0.15)
        self.assertIn('lexical_baseline_is_not_an_AI_semantic_model',result['quality']['warnings'])


class ExplicitOfficialImportTests(unittest.TestCase):
    def test_official_snapshot_to_explicit_research_without_index_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            company='出表日期,公司代號,公司名稱\n1090102,1000,Synthetic\n'.encode()
            revenue='出表日期,資料年月,公司代號,公司名稱,營業收入-當月營收\n1090102,10812,1000,Synthetic,1000\n'.encode()
            with patch('local.collect_official.fetch_csv',side_effect=[company,revenue]),patch('local.collect_official.now',return_value=T0),patch('local.collect_official.time.sleep'):
                download(ROOT/'local/official_datasets.json',root/'snapshots')
            with redirect_stdout(io.StringIO()):
                official_main(['--snapshot-dir',str(root/'snapshots'),'--symbols','1000','--as-of','2020-01-02','--output',str(root/'input.json')])
            data=json.loads((root/'input.json').read_text())
            self.assertEqual(data['metadata']['research_selection']['mode'],'explicit_symbols_not_index_membership')
            self.assertEqual(len(data['metadata']['source_snapshots']),2)
            self.assertEqual(data['financial_metrics'][0]['source_id'],'twse_monthly_revenue')
            self.assertNotIn('universe_ids',data['stocks'][0])
            result=run(root/'input.json',['1000'],history_db=root/'history.db',output_root=root/'runs')
            self.assertEqual(result['counts']['graphs'],1)
    def test_symbols_and_index_are_mutually_exclusive(self):
        with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            official_main(['--symbols','1000','--universe','index.csv','--as-of','2020-01-02'])
    def test_etf_requires_index_even_if_symbols_given(self):
        with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            official_main(['--symbols','1000','--etf-holdings','etf.csv','--universe-source','https://example.org','--as-of','2020-01-02'])

class StructuredLifecycleTests(unittest.TestCase):
    def test_market_and_metrics_keep_reserved_slots_without_exceeding_cap(self):
        from local.lifecycle import prune
        primary='stock:TW:1000'
        nodes=[{'id':primary,'type':'stock'}]+[{'id':f'doc:{i}','type':'financial'} for i in range(120)]
        nodes += [{'id':'quote','type':'market_price','trade_date':'2020-01-02'},
                  {'id':'metric','type':'financial_metric','period_end':'2019-12-31'}]
        edges=[{'id':f'e{i}','source':primary,'target':n['id'],'relation':'semantic_similarity','score':0.99}
               for i,n in enumerate(nodes[1:121])]
        edges += [{'id':'price-e','source':primary,'target':'quote','relation':'has_market_price'},
                  {'id':'metric-e','source':primary,'target':'metric','relation':'has_financial_metric'}]
        result=prune({'stock_id':'TW:1000','nodes':nodes,'edges':edges},max_information_nodes=100)
        self.assertEqual(len(result['nodes']),101)
        self.assertIn('quote',{n['id'] for n in result['nodes']})
        self.assertIn('metric',{n['id'] for n in result['nodes']})
        small=prune({'stock_id':'TW:1000','nodes':nodes,'edges':edges},max_information_nodes=1)
        self.assertEqual({n['id'] for n in small['nodes']},{primary,'quote'})
