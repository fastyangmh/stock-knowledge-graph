"""Smoke tests: python -m unittest discover -s local/tests -v"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from local.core import init_db, import_payload
from local.similarity import compute, cosine
from local.export_json import export, validate_graph

ROOT=Path(__file__).resolve().parents[2]

class PipelineTests(unittest.TestCase):
    def test_end_to_end_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=sqlite3.connect(Path(tmp)/"test.db")
            db.row_factory=sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            init_db(db)
            sample=json.loads((ROOT/"local"/"sample_data.json").read_text(encoding="utf-8"))
            import_payload(db,sample)
            import_payload(db,sample)
            self.assertEqual(db.execute("SELECT count(*) FROM documents").fetchone()[0],3)
            result=compute(db,top_k=5,threshold=0.0)
            self.assertEqual(result["documents"],3)
            manifest=export(db,Path(tmp)/"out")
            self.assertEqual(len(manifest["stocks"]),3)
            for item in manifest["stocks"]:
                graph=json.loads((Path(tmp)/"out"/item["path"].removeprefix("data/")).read_text(encoding="utf-8"))
                validate_graph(graph)
                self.assertTrue(graph["nodes"])
                self.assertTrue(all(e["source"] in {n["id"] for n in graph["nodes"]} for e in graph["edges"]))
            # Re-export a smaller universe: stale stock graph files must disappear.
            manifest2=export(db,Path(tmp)/"out",universe={"TW:2330"},lifecycle=True)
            self.assertEqual(len(manifest2["stocks"]),1)
            self.assertFalse((Path(tmp)/"out/stocks/2454/graph.json").exists())
            self.assertFalse((Path(tmp)/"out/stocks/2317/graph.json").exists())
            with self.assertRaises(ValueError):
                export(db,Path(tmp)/"out",universe={"TW:9999"})
            self.assertTrue((Path(tmp)/"out/stocks/2330/graph.json").exists())
            db.close()

    def test_cosine(self):
        self.assertAlmostEqual(cosine([1,0],[1,0]),1.0)
        self.assertAlmostEqual(cosine([1,0],[0,1]),0.0)
        with self.assertRaises(ValueError):
            cosine([1],[1,0])

if __name__=="__main__":
    unittest.main()
