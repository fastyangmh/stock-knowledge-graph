import tempfile
import unittest
from pathlib import Path
from local.trading_calendar import is_trading_day

class CalendarTests(unittest.TestCase):
    def test_explicit_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"calendar.csv"
            p.write_text("date,is_open\n2026-11-16,1\n2026-11-17,0\n",encoding="utf-8")
            self.assertTrue(is_trading_day(p,"2026-11-16"))
            self.assertFalse(is_trading_day(p,"2026-11-17"))
            with self.assertRaises(ValueError):
                is_trading_day(p,"2026-11-18")
