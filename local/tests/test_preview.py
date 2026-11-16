"""Read-only preview tests use actual loopback HTTP; no external connections."""
import http.client
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from local.preview import make_server, snapshot, ASSETS


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.site=self.root/"site";self.data=self.root/"private"
        for name in ASSETS:
            p=self.site/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("synthetic "+name)
        graph=self.data/"stocks/1000/graph.json";graph.parent.mkdir(parents=True)
        graph.write_text(json.dumps({"stock_id":"TW:1000","nodes":[{"id":"stock:TW:1000"}],"edges":[]}))
        (self.data/"manifest.json").write_text(json.dumps({"stocks":[{"label":"Synthetic","path":"data/stocks/1000/graph.json"}]}))
        (self.site/"private-token.txt").write_text("DO NOT SERVE")
        self.server=make_server(self.data,port=0,root=self.site)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def request(self,path,method="GET",headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            conn.request(method,path,headers=headers or {});res=conn.getresponse()
            return res.status,dict(res.getheaders()),res.read()
        finally:conn.close()
    def test_assets_and_graphs(self):
        for path in ("/","/index.html","/js/graph-utils.js","/data/manifest.json","/data/stocks/1000/graph.json"):
            status,headers,body=self.request(path)
            self.assertEqual(status,200);self.assertTrue(body)
            self.assertEqual(headers["Cache-Control"],"no-store")
    def test_no_directory_or_private_file_access(self):
        for path in ("/local/","/private-token.txt","/data/../private-token.txt","/%2e%2e/private-token.txt","/docs/","/data/stocks/"):
            self.assertEqual(self.request(path)[0],404)
    def test_host_rebinding_rejected(self):
        self.assertEqual(self.request("/data/manifest.json",headers={"Host":"attacker.example"})[0],403)
    def test_head(self):
        status,headers,body=self.request("/data/manifest.json",method="HEAD")
        self.assertEqual(status,200);self.assertEqual(body,b"")
        self.assertGreater(int(headers["Content-Length"]),0)
    def test_immutable_loaded_snapshot(self):
        prior=self.request("/data/manifest.json")[2]
        (self.data/"manifest.json").write_text("now invalid")
        self.assertEqual(self.request("/data/manifest.json")[2],prior)
    def test_size_budget(self):
        with self.assertRaises(ValueError): snapshot(self.data,root=self.site,max_bytes=1)
    def test_symlink_rejected(self):
        link=self.data/"secret";link.symlink_to(self.site/"private-token.txt")
        with self.assertRaises(ValueError): snapshot(self.data,root=self.site)

    def test_size_guard_runs_before_json_validation(self):
        with patch("local.preview.validate_data_dir",side_effect=AssertionError("must not parse")):
            with self.assertRaisesRegex(ValueError,"budget"):
                snapshot(self.data,root=self.site,max_bytes=1)
    def test_invalid_budget_rejected(self):
        for budget in (0,-1,True,1.5):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                snapshot(self.data,root=self.site,max_bytes=budget)
