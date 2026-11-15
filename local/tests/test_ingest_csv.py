import tempfile
import unittest
from pathlib import Path
from local.ingest_csv import normalize

class CSVTests(unittest.TestCase):
    def test_local_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/"stocks.csv").write_text("stock_id,ticker,market,name\nTW:2330,2330,TW,Demo\n",encoding="utf-8")
            (p/"documents.csv").write_text("document_id,doc_type,title,published_at,stock_ids\nd1,news,Test,2026-11-15T10:00:00+08:00,TW:2330\n",encoding="utf-8")
            result=normalize(p)
            self.assertEqual(result["documents"][0]["stock_ids"],["TW:2330"])
            (p/"documents.csv").write_text("document_id,doc_type,title,published_at,stock_ids\nd1,news,Test,2026-11-15T10:00:00+08:00,TW:9999\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                normalize(p)
    def test_missing_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                normalize(tmp)
