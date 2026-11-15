import tempfile
import unittest
from pathlib import Path
from local.universe import load_universe

class UniverseTests(unittest.TestCase):
    def test_effective_membership(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"tw50.csv"
            p.write_text("stock_id,effective_from,effective_to\nTW:2330,2026-01-01,\nTW:2454,2025-01-01,2025-12-31\n")
            self.assertEqual(load_universe(p,"2026-11-15"),{"TW:2330"})
            with self.assertRaises(ValueError):load_universe(p,"2024-01-01")
