import json
import tempfile
import unittest
from pathlib import Path
from local.source_registry import load_approved

class OfficialSourceTests(unittest.TestCase):
    def test_quarterly_csv_resources_are_individually_registered_for_offline_review(self):
        from local.core import ROOT
        registry = ROOT/'local/official_datasets.json'
        entries = {r['dataset_id']: r for r in json.loads(registry.read_bytes())}
        enabled = {r['dataset_id'] for r in load_approved(registry)}
        for dataset, filename in (
            (91998, 't187ap06_L_ci.csv'), (94853, 't187ap06_O_ci.csv'),
            (91995, 't187ap06_L_basi.csv'), (92000, 't187ap06_L_ins.csv'),
            (94831, 't187ap07_L_ci.csv'), (91967, 't187ap07_O_ci.csv'),
            (94829, 't187ap07_L_basi.csv'), (94833, 't187ap07_L_ins.csv'),
        ):
            with self.subTest(dataset=dataset):
                sid = f'mops_{dataset}'
                self.assertIn(sid, entries)
                source = entries[sid]
                self.assertEqual(source['dataset_url'], f'https://data.gov.tw/dataset/{dataset}')
                self.assertEqual(source['resource_url'], 'https://mopsfin.twse.com.tw/opendata/' + filename)
                self.assertEqual(source['usage'], 'offline_saved_receipt_only')
                self.assertTrue(source['license_reviewed'])
                self.assertFalse(source['redistribution_reviewed'])
                self.assertNotIn(sid, enabled)

    def test_11633_is_registered_only_for_saved_capture_review(self):
        from local.core import ROOT
        from local.tpex_action_evidence import CATALOG, RESOURCE
        registry = ROOT / 'local/official_datasets.json'
        matches = [r for r in json.loads(registry.read_bytes()) if r['dataset_url'] == CATALOG]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['resource_url'], RESOURCE)
        self.assertFalse(matches[0]['enabled'])
        self.assertFalse(matches[0]['redistribution_reviewed'])
        self.assertNotIn(matches[0], load_approved(registry))

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
