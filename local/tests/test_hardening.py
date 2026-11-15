import copy
import json
import math
import random
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from local.core import connect, init_db, import_payload, ROOT
from local.neighbors import top_k_pairs
from local.semantic import compute_semantic, normalized
from local.lifecycle import prune
from local.universe import load_universe
from local.export_json import export, validate_graph
from local.validate_release import validate_data_dir
from local.pipeline import main

SAMPLE=json.loads((ROOT/"local/sample_data.json").read_text())
FIXED="2026-11-15T23:59:59+08:00"

class Encoder:
    def __init__(self): self.calls=[]
    def get_embedding_dimension(self): return 3
    def encode(self,texts,batch_size=32):
        self.calls.extend(texts)
        return [[float("晶片" in t),float("電子" in t),1.] for t in texts]

class DBCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.conn=connect(self.root/"test.db");init_db(self.conn)
        import_payload(self.conn,copy.deepcopy(SAMPLE));self.conn.commit()
    def tearDown(self):
        self.conn.close();self.tmp.cleanup()
    def compute(self,**kwargs):
        return compute_semantic(self.conn,model_name="fake",revision="v1",as_of=FIXED,threshold=0.,**kwargs)
    def test_all_cache_hit_skips_model_and_pair_scan(self):
        first=self.compute(encoder=Encoder())
        with patch("local.semantic.load_encoder",side_effect=AssertionError("must not load model")):
            second=self.compute()
        self.assertEqual(second["cache_hits"],3);self.assertEqual(second["encoded"],0)
        self.assertTrue(second["graph_reused"]);self.assertEqual(second["pairs_evaluated"],0)
        self.assertFalse(second["model_loaded"])
        self.assertEqual(first["model_id"],second["model_id"])
    def test_changed_document_only_reencodes_one(self):
        self.compute(encoder=Encoder())
        data=copy.deepcopy(SAMPLE);data["documents"][0]["content"]+=" revised"
        import_payload(self.conn,data)
        fake=Encoder(); result=self.compute(encoder=fake)
        self.assertEqual(result["encoded"],1);self.assertEqual(result["cache_hits"],2)
        self.assertFalse(result["graph_reused"]);self.assertEqual(len(fake.calls),1)
    def test_mapping_change_rebuilds_without_loading(self):
        self.compute(encoder=Encoder())
        doc=copy.deepcopy(SAMPLE["documents"][0]);doc["stock_ids"]=["TW:2317"]
        import_payload(self.conn,{"documents":[doc]})
        self.assertEqual([r[0] for r in self.conn.execute("SELECT stock_id FROM document_stocks WHERE document_id=?",(doc["document_id"],))],["TW:2317"])
        with patch("local.semantic.load_encoder",side_effect=AssertionError): result=self.compute()
        self.assertFalse(result["graph_reused"]);self.assertEqual(result["encoded"],0)
    def test_vector_failure_rolls_back_entire_refresh(self):
        self.compute(encoder=Encoder());self.conn.commit()
        prior=[tuple(r) for r in self.conn.execute("SELECT * FROM embeddings ORDER BY node_id")]
        edges=[tuple(r) for r in self.conn.execute("SELECT * FROM graph_edges WHERE model_id IS NOT NULL ORDER BY edge_id")]
        data=copy.deepcopy(SAMPLE)
        for doc in data["documents"]: doc["content"]+=" revision"
        import_payload(self.conn,data)
        class Bad(Encoder):
            def encode(self,texts,batch_size=32):return [[1.,0.,1.],[float('nan'),0,1],[1,0,1]]
        with self.assertRaises(ValueError):self.compute(encoder=Bad())
        self.assertEqual(prior,[tuple(r) for r in self.conn.execute("SELECT * FROM embeddings ORDER BY node_id")])
        self.assertEqual(edges,[tuple(r) for r in self.conn.execute("SELECT * FROM graph_edges WHERE model_id IS NOT NULL ORDER BY edge_id")])
    def test_encoder_count_mismatch(self):
        class Bad(Encoder):
            def encode(self,*a,**k):return []
        with self.assertRaises(ValueError):self.compute(encoder=Bad())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM embeddings").fetchone()[0],0)
    def test_corrupted_cache_fails_closed(self):
        self.compute(encoder=Encoder())
        self.conn.execute("UPDATE embeddings SET vector=x'00' WHERE node_id='doc:demo-001'")
        with self.assertRaises(ValueError): self.compute()
    def test_budget_before_model_load(self):
        with patch("local.semantic.load_encoder",side_effect=AssertionError):
            with self.assertRaises(ValueError):self.compute(max_pairs=1)
    def test_window_keeps_old_vectors_but_excludes_from_graph(self):
        self.compute(encoder=Encoder())
        result=compute_semantic(self.conn,model_name="fake",revision="v1",as_of="2027-12-01T00:00:00Z",lookback_days=1)
        self.assertEqual(result["documents"],0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM embeddings").fetchone()[0],3)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM graph_edges WHERE model_id IS NOT NULL").fetchone()[0],0)
    def test_first_observed_time_is_stable(self):
        before=self.conn.execute("SELECT available_at FROM documents WHERE document_id='demo-001'").fetchone()[0]
        doc=copy.deepcopy(SAMPLE["documents"][0]);doc["available_at"]="2026-11-15T18:00:00+08:00"
        import_payload(self.conn,{"documents":[doc]})
        self.assertEqual(self.conn.execute("SELECT available_at FROM documents WHERE document_id='demo-001'").fetchone()[0],before)
    def test_edge_evidence_and_model_exported(self):
        self.compute(encoder=Encoder());out=self.root/"out";export(self.conn,out)
        graph=json.loads((out/"stocks/2330/graph.json").read_text())
        edges=[e for e in graph["edges"] if e["relation"]=="semantic_similarity"]
        self.assertTrue(edges);self.assertTrue(all(e["model_id"] and e["evidence_ids"] for e in edges))
    def test_export_cleans_stale_graphs_without_losing_history(self):
        out=self.root/"out";export(self.conn,out)
        export(self.conn,out,universe={"TW:2330"})
        self.assertEqual(validate_data_dir(out),1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM stocks").fetchone()[0],3)
    def test_export_refuses_unrelated_files(self):
        out=self.root/"out";out.mkdir();(out/"private.db").write_text("keep")
        with self.assertRaises(ValueError):export(self.conn,out)
        self.assertEqual((out/"private.db").read_text(),"keep")
    def test_failed_install_restores_previous_output(self):
        out=self.root/"out";export(self.conn,out)
        before=(out/"manifest.json").read_bytes()
        original=Path.rename
        def fail(source,target):
            if source.name=="data" and source.parent.name.startswith(".stock-graph-stage-"):
                raise OSError("injected replacement failure")
            return original(source,target)
        with patch.object(Path,"rename",fail):
            with self.assertRaises(OSError):export(self.conn,out,universe={"TW:2330"})
        self.assertEqual((out/"manifest.json").read_bytes(),before)
        self.assertFalse(list(self.root.glob(".stock-graph-stage-*")))
    def test_preexisting_backup_is_never_deleted(self):
        out=self.root/"out";backup=self.root/"out.previous";backup.mkdir();(backup/"keep").write_text("keep")
        export(self.conn,out);self.assertTrue((backup/"keep").exists())
    def test_path_traversal_stock_rejected_before_replacing(self):
        self.conn.execute("UPDATE stocks SET ticker='../../private' WHERE stock_id='TW:2330'")
        with self.assertRaises(ValueError): export(self.conn,self.root/"out")
        self.assertFalse(list(self.root.glob(".stock-graph-stage-*")))
    def test_explicit_threshold_not_rewritten(self):
        with patch("local.pipeline.compute_semantic",return_value={}) as compute:
            main(["semantic","--db",str(self.root/"other.db"),"--threshold","0.15"])
        self.assertEqual(compute.call_args.args[3],0.15)
    def test_nonfinite_financial_value_rejected(self):
        record=copy.deepcopy(SAMPLE["financial_metrics"][0]);record["value"]=float('nan')
        with self.assertRaises(ValueError):import_payload(self.conn,{"financial_metrics":[record]})

class NeighborTests(unittest.TestCase):
    def test_matches_full_reference_with_ties(self):
        for seed in range(5):
            rng=random.Random(seed)
            vectors={f"d{i:02}":normalized([rng.randint(-2,2),rng.randint(-2,2),1]) for i in range(30)}
            actual,stats=top_k_pairs(vectors,3,-1)
            expected={}
            for a in sorted(vectors):
                scores=[(max(-1,min(1,math.fsum(x*y for x,y in zip(vectors[a],vectors[b])))),b) for b in vectors if b!=a]
                for score,b in sorted(scores,key=lambda x:(-x[0],x[1]))[:3]:expected[tuple(sorted((a,b)))]=score
            self.assertEqual(actual,expected);self.assertLessEqual(stats['retained_candidates'],90)
    def test_rejects_non_unit_vectors(self):
        with self.assertRaises(ValueError):top_k_pairs({'a':[2,0],'b':[1,0]},1,0)
    def test_zero_and_one_document(self):
        for vectors in ({},{'a':[1,0]}):self.assertEqual(top_k_pairs(vectors,5,0)[0],{})
    def test_threshold_negative_scores(self):
        self.assertEqual(top_k_pairs({'a':[1,0],'b':[-1,0]},1,0)[0],{})
        self.assertEqual(len(top_k_pairs({'a':[1,0],'b':[-1,0]},1,-1)[0]),1)

class DatePolicyTests(unittest.TestCase):
    def test_invalid_dates_and_overlapping_intervals(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'universe.csv'
            for rows in ('TW:2330,2026-99-99,\n','TW:2330,2026-01-01,2025-01-01\n',
                         'TW:2330,2026-01-01,2026-06-01\nTW:2330,2026-06-01,\n'):
                path.write_text('stock_id,effective_from,effective_to\n'+rows)
                with self.assertRaises(ValueError):load_universe(path,'2026-11-15')
    def test_expected_universe_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'universe.csv';path.write_text('stock_id,effective_from,effective_to\nTW:2330,2026-01-01,\n')
            with self.assertRaises(ValueError):load_universe(path,'2026-11-15',expected_count=50)
    def test_future_availability_overrides_old_publication(self):
        graph={'stock_id':'TW:2330','nodes':[{'id':'stock:TW:2330','type':'stock'},{'id':'future','type':'financial',
               'published_at':'2026-01-01T00:00:00Z','available_at':'2099-01-01T00:00:00Z'}],
               'edges':[{'id':'e','source':'stock:TW:2330','target':'future','relation':'contains'}]}
        self.assertEqual(len(prune(graph,as_of=FIXED)['nodes']),1)
    def test_related_stock_cap_is_not_semantic_information_cap(self):
        graph={'stock_id':'TW:2330','nodes':[{'id':'stock:TW:2330','type':'stock'}]+
            [{'id':f's{i}','type':'stock'} for i in range(20)],'edges':[
            {'id':f'e{i}','source':'stock:TW:2330','target':f's{i}','relation':'semantic_similarity','score':.8} for i in range(20)]}
        result=prune(graph,max_related_stocks=15,max_semantic_per_node=5,as_of=FIXED)
        self.assertEqual(len(result['nodes']),16)
    def test_bool_score_rejected(self):
        graph={'nodes':[{'id':'a'},{'id':'b'}],'edges':[{'id':'e','source':'a','target':'b','relation':'semantic_similarity','score':True}]}
        with self.assertRaises(ValueError):validate_graph(graph)

class AdditionalSafetyTests(unittest.TestCase):
    def test_export_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'real';target.mkdir();link=root/'link';link.symlink_to(target,target_is_directory=True)
            conn=connect(root/'test.db');init_db(conn);import_payload(conn,copy.deepcopy(SAMPLE))
            try:
                with self.assertRaises(ValueError):export(conn,link)
                self.assertTrue(target.exists())
            finally:conn.close()
    def test_release_symlink_not_dereferenced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'data';data.mkdir();outside=root/'secret.json';outside.write_text('{}')
            (data/'manifest.json').symlink_to(outside)
            with self.assertRaises(ValueError):validate_data_dir(data)
    def test_financial_availability_unchanged_for_same_value(self):
        with tempfile.TemporaryDirectory() as d:
            conn=connect(Path(d)/'test.db');init_db(conn);import_payload(conn,copy.deepcopy(SAMPLE))
            original=conn.execute('SELECT available_at FROM financial_metrics').fetchone()[0]
            item=copy.deepcopy(SAMPLE['financial_metrics'][0]);item['available_at']='2026-11-15T19:00:00+08:00'
            import_payload(conn,{'financial_metrics':[item]})
            self.assertEqual(conn.execute('SELECT available_at FROM financial_metrics').fetchone()[0],original)
            conn.close()
    def test_pipeline_export_failure_rolls_back_import(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);db=root/'test.db'
            with patch('local.pipeline.export',side_effect=ValueError('injected failure')):
                with self.assertRaises(ValueError):main(['all','--db',str(db),'--output',str(root/'out')])
            conn=connect(db)
            try:
                self.assertEqual(conn.execute('SELECT count(*) FROM stocks').fetchone()[0],0)
                self.assertEqual(conn.execute('SELECT status FROM pipeline_runs').fetchone()[0],'failed')
            finally:conn.close()
