import json
import tempfile
import unittest
from pathlib import Path
from local.validate_release import validate_release

class ReleaseTests(unittest.TestCase):
    def test_valid_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            path=root/"data/stocks/2330/graph.json"
            path.parent.mkdir(parents=True)
            graph={"stock_id":"TW:2330","nodes":[{"id":"stock:TW:2330"}],"edges":[]}
            path.write_text(json.dumps(graph),encoding="utf-8")
            manifest={"stocks":[{"path":"data/stocks/2330/graph.json","label":"2330"}]}
            (root/"data/manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
            self.assertEqual(validate_release(root),1)
            (root/"data/stocks/2454").mkdir()
            (root/"data/stocks/2454/graph.json").write_text(json.dumps(graph))
            with self.assertRaises(ValueError):
                validate_release(root)
            (root/"data/stocks/2454/graph.json").unlink()
            manifest["stocks"][0]["path"]="data/../secret/graph.json"
            (root/"data/manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate_release(root)
