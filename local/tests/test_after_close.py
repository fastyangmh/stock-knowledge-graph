import tempfile
import unittest
from unittest.mock import patch
from local.run_after_close import main
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

    def test_publish_flag_fails_closed_before_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            calendar=p/"calendar.csv"
            calendar.write_text("date,is_open\n2026-11-16,1\n")
            normalized=p/"normalized.json"
            normalized.write_text("{}")
            universe=p/"tw50.csv"
            universe.write_text("stock_id,effective_from,effective_to\nTW:2330,2026-01-01,\n")
            class Clock:
                def date(self):return type("Date",(),{"isoformat":lambda self:"2026-11-16"})()
                def time(self):return time(19,0)
            class FakeDateTime:
                @staticmethod
                def now(tz):return Clock()
            with patch("local.run_after_close.datetime",FakeDateTime):
                with self.assertRaisesRegex(RuntimeError,"not enabled"):
                    main_args=["--calendar",str(calendar),"--input",str(normalized),
                               "--universe",str(universe),"--publish"]
                    with patch("sys.argv",["after-close"]+main_args):
                        main()
