"""Validate date-effective stock universes; no inferred or hard-coded TW50 list."""
import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .dates import iso_date


def load_universe(path, as_of=None, *, expected_count=None):
    target = iso_date(as_of) if as_of else datetime.now(ZoneInfo("Asia/Taipei")).date()
    intervals, result = {}, set()
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"stock_id", "effective_from", "effective_to"}.issubset(reader.fieldnames or []):
            raise ValueError("universe requires stock_id,effective_from,effective_to")
        for row in reader:
            sid = row.get("stock_id", "").strip()
            if not re.fullmatch(r"TW:[0-9]{4}", sid):
                raise ValueError("invalid TW stock id")
            start = iso_date(row["effective_from"].strip())
            end = iso_date(row["effective_to"].strip() or "9999-12-31")
            if end < start:
                raise ValueError("universe interval ends before it starts")
            for a, b in intervals.setdefault(sid, []):
                if start <= b and a <= end:
                    raise ValueError("duplicate or overlapping constituent interval")
            intervals[sid].append((start, end))
            if start <= target <= end:  # Both bounds inclusive; consecutive rows must not share a day.
                result.add(sid)
    if not result:
        raise ValueError("No active constituents for selected date; fail closed")
    if expected_count is not None and len(result) != expected_count:
        raise ValueError(f"Expected {expected_count} active constituents, found {len(result)}")
    return result
