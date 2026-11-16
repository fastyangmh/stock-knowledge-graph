"""Real loopback HTTP tests; no remote network or private files served."""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from local.bundle_audit import AuditError
from local.research_archive import make_server, archive_snapshot
from history_fixtures import make_run


class ArchiveHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.a=make_run(cls.root,1,value=10);cls.b=make_run(cls.root,2,value=40)
        cls.runs=cls.root/'runs';cls.server=make_server(cls.runs,port=0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2);cls.tmp.cleanup()
    def request(self,path,method='GET',headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            c.request(method,path,headers=headers or {});res=c.getresponse();return res.status,dict(res.getheaders()),res.read()
        finally:c.close()
    def comparison_path(self):return f"/api/compare?before={self.a['run']}&after={self.b['run']}"
    def test_portal_and_catalog(self):
        code,headers,body=self.request('/')
        self.assertEqual(code,200);self.assertIn('研究歷史'.encode(),body)
        self.assertEqual(headers['Cache-Control'],'no-store');self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        data=json.loads(self.request('/research-history.json')[2]);self.assertEqual(data['counts']['valid'],2)
    def test_both_version_graphs_available(self):
        for r in (self.a,self.b):
            code,_,body=self.request(f"/versions/{r['run']}/data/stocks/1000/graph.json")
            self.assertEqual(code,200);self.assertEqual(json.loads(body)['stock_id'],'TW:1000')
    def test_comparison_true_http(self):
        code,_,body=self.request(self.comparison_path());self.assertEqual(code,200)
        report=json.loads(body);self.assertEqual(report['before']['run'],self.a['run'])
        self.assertEqual(report['stocks'][0]['categories']['monthly_revenue'][0]['transition'],'activated')
    def test_db_reports_raw_and_source_files_not_served(self):
        for suffix in ('graph.db','report.json','alerts.json','input.json','data/'):
            self.assertEqual(self.request(f"/versions/{self.a['run']}/{suffix}")[0],404)
        for path in ('/local/','/.git/config','/docs/','/latest.json','/input-1.json','/%2e%2e/input-1.json'):
            self.assertEqual(self.request(path)[0],404)
    def test_rebinding_bad_host_rejected_for_api(self):
        self.assertEqual(self.request(self.comparison_path(),headers={'Host':'attacker.example'})[0],403)
    def test_absolute_form_request_rejected(self):
        self.assertEqual(self.request('http://attacker.example/api/compare',headers={'Host':f'127.0.0.1:{self.server.server_port}'})[0],400)
    def test_invalid_comparison_requests(self):
        for q in ('', '?before=../private&after=x',f"?before={self.a['run']}",
                  f"?before={self.a['run']}&before={self.a['run']}&after={self.b['run']}",
                  f"?before={self.b['run']}&after={self.a['run']}", '?before='+'f'*32+'&after='+'e'*32):
            with self.subTest(q=q):self.assertEqual(self.request('/api/compare'+q)[0],400)
    def test_head_returns_no_bytes(self):
        code,headers,body=self.request(self.comparison_path(),method='HEAD')
        self.assertEqual(code,200);self.assertFalse(body);self.assertGreater(int(headers['Content-Length']),0)
    def test_post_is_not_an_operation(self):
        self.assertEqual(self.request('/api/compare',method='POST')[0],501)
    def test_long_query_rejected(self):self.assertEqual(self.request('/api/compare?'+'x'*8192)[0],414)
    def test_same_run_comparison_allowed(self):
        q=f"/api/compare?before={self.a['run']}&after={self.a['run']}"
        self.assertEqual(self.request(q)[0],200)
    def test_history_assets_not_missing(self):
        for path in ('/history.html','/js/history.js','/js/history-utils.js','/index.html','/js/app.js'):
            self.assertEqual(self.request(path)[0],200)


class ArchiveSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.a=make_run(self.root);self.runs=self.root/'runs'
    def test_snapshot_is_immutable_after_capture(self):
        files,bundles=archive_snapshot(self.runs);key=f"/versions/{self.a['run']}/data/manifest.json";old=files[key][0]
        (self.runs/self.a['run']/'data/manifest.json').write_text('bad')
        self.assertEqual(files[key][0],old);self.assertIn(self.a['run'],bundles)
    def test_preview_size_fails_closed(self):
        with self.assertRaisesRegex(AuditError,'size_budget'):archive_snapshot(self.runs,max_preview_bytes=1)
    def test_invalid_run_has_no_graph_routes(self):
        (self.runs/self.a['run']/'graph.db').write_bytes(b'bad')
        files,bundles=archive_snapshot(self.runs)
        self.assertFalse(bundles);self.assertFalse(any(k.startswith('/versions/') for k in files))
        self.assertNotIn('/data/manifest.json',files)
        summary=json.loads(files['/research-history.json'][0]);self.assertEqual(summary['counts']['invalid'],1)
    def test_budget_validation(self):
        for value in (0,-1,True,4097):
            with self.subTest(value=value),self.assertRaises(AuditError):archive_snapshot(self.runs,max_mib=value)

    def test_preview_budget_before_catalog_parses_json(self):
        with patch('local.research_archive.catalog',side_effect=AssertionError('do not allocate JSON')):
            with self.assertRaisesRegex(AuditError,'size_budget'):
                archive_snapshot(self.runs,max_preview_bytes=1)
