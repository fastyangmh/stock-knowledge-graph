import tempfile
import unittest
from pathlib import Path
from datetime import time
from local.run_after_close import ready

class AfterCloseTests(unittest.TestCase):
    def test_cutoff_and_holiday(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"calendar.csv"
            p.write_text("date,is_open\n2026-11-16,1\n2026-11-17,0\n")
            with self.assertRaises(RuntimeError):ready(p,"2026-11-16",time(16,0))
            self.assertTrue(ready(p,"2026-11-16",time(18,30)))
            self.assertFalse(ready(p,"2026-11-17",time(18,30)))
