import unittest
from local.lifecycle import prune

class LifecycleTests(unittest.TestCase):
    def test_limits_and_endpoint_closure(self):
        graph={"stock_id":"TW:2330","nodes":[{"id":"stock:TW:2330","type":"stock"}]+
            [{"id":f"doc:{i}","type":"news","published_at":"2026-11-14T10:00:00+08:00"} for i in range(6)]+
            [{"id":"stock:TW:2454","type":"stock"}],
            "edges":[{"id":str(i),"source":"stock:TW:2330","target":f"doc:{i}","relation":"contains"} for i in range(6)]}
        result=prune(graph,max_information_nodes=2,max_related_stocks=0,as_of="2026-11-15T00:00:00+08:00")
        self.assertEqual(len(result["nodes"]),3)
        ids={n["id"] for n in result["nodes"]}
        self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in result["edges"]))
        self.assertEqual(len(graph["nodes"]),8)
    def test_expired_news(self):
        graph={"stock_id":"TW:2330","nodes":[{"id":"stock:TW:2330","type":"stock"},
            {"id":"doc:old","type":"news","published_at":"2020-01-01T00:00:00+08:00"}],"edges":[]}
        result=prune(graph,news_days=90,as_of="2026-11-15T00:00:00+08:00")
        self.assertEqual(len(result["nodes"]),1)
