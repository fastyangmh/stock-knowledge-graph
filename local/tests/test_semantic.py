"""Offline tests with injected encoder: no model downloads required."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from local.core import init_db,import_payload
from local.semantic import compute_semantic,cosine
from local.export_json import export,validate_graph

ROOT=Path(__file__).resolve().parents[2]

class FakeEncoder:
    def __init__(self):
        self.calls=[]
    def get_sentence_embedding_dimension(self):
        return 3
    def encode(self,texts,batch_size=32):
        self.calls.append(list(texts))
        # Stable multilingual-independent synthetic vector for cache tests.
        return [[float("晶片" in t),float("電子" in t),1.0] for t in texts]

class SemanticTests(unittest.TestCase):
    def test_incremental_cache_and_model_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn=sqlite3.connect(Path(tmp)/"test.db")
            conn.row_factory=sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            init_db(conn)
            data=json.loads((ROOT/"local"/"sample_data.json").read_text(encoding="utf-8"))
            import_payload(conn,data)
            fake=FakeEncoder()
            first=compute_semantic(conn,encoder=fake,model_name="test/fake",revision="v1",threshold=0.0,batch_size=2)
            self.assertEqual(first["encoded"],3)
            self.assertEqual(first["cache_hits"],0)
            self.assertEqual([len(x) for x in fake.calls],[2,1])
            second=compute_semantic(conn,encoder=fake,model_name="test/fake",revision="v1",threshold=0.0)
            self.assertEqual(second["encoded"],0)
            self.assertEqual(second["cache_hits"],3)
            self.assertEqual(len(fake.calls),2)
            data["documents"][0]["content"]+=" 內容修訂"
            import_payload(conn,data)
            third=compute_semantic(conn,encoder=fake,model_name="test/fake",revision="v1",threshold=0.0)
            self.assertEqual(third["encoded"],1)
            self.assertEqual(third["cache_hits"],2)
            fourth=compute_semantic(conn,encoder=fake,model_name="test/fake",revision="v2",threshold=0.0)
            self.assertEqual(fourth["encoded"],3)
            self.assertNotEqual(first["model_id"],fourth["model_id"])
            manifest=export(conn,Path(tmp)/"out")
            for item in manifest["stocks"]:
                path=Path(tmp)/"out"/item["path"].removeprefix("data/")
                validate_graph(json.loads(path.read_text(encoding="utf-8")))
            conn.close()

    def test_invalid_vector_rejected(self):
        class Bad(FakeEncoder):
            def encode(self,texts,batch_size=32):
                return [[float("nan"),0,1] for _ in texts]
        with tempfile.TemporaryDirectory() as tmp:
            conn=sqlite3.connect(Path(tmp)/"test.db")
            conn.row_factory=sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            init_db(conn)
            data=json.loads((ROOT/"local"/"sample_data.json").read_text(encoding="utf-8"))
            import_payload(conn,data)
            with self.assertRaises(ValueError):
                compute_semantic(conn,encoder=Bad(),model_name="test/bad")
            conn.close()

if __name__=="__main__":
    unittest.main()
