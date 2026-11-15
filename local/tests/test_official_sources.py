import json
import tempfile
import unittest
from pathlib import Path
from local.source_registry import load_approved

class OfficialSourceTests(unittest.TestCase):
    def test_disabled_default(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"
            p.write_text(json.dumps([{"dataset_id":"demo","enabled":False}]))
            self.assertEqual(load_approved(p),[])
    def test_unreviewed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"
            p.write_text(json.dumps([{"dataset_id":"demo","enabled":True,"resource_url":"https://openapi.twse.com.tw/example"}]))
            with self.assertRaises(ValueError):load_approved(p)
    def test_unknown_host_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"
            p.write_text(json.dumps([{"dataset_id":"demo","enabled":True,"license_reviewed":True,"redistribution_reviewed":True,
                "provider":"TWSE","dataset_url":"https://data.gov.tw/example",
                "resource_url":"https://example.com/a","license_url":"https://data.gov.tw/license",
                "attribution":"TWSE"}]))
            with self.assertRaises(ValueError):load_approved(p)
