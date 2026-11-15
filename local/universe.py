"""Explicit, date-stamped TW50 membership; never guess current constituents."""
import csv
from datetime import date
from pathlib import Path

def load_universe(path,as_of=None):
    as_of=as_of or date.today().isoformat()
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not {"stock_id","effective_from","effective_to"}.issubset(reader.fieldnames or []):
            raise ValueError("universe requires stock_id,effective_from,effective_to")
        result=set()
        for row in reader:
            start=row["effective_from"]
            end=row["effective_to"] or "9999-12-31"
            if not row["stock_id"].startswith("TW:"):
                raise ValueError("invalid TW stock id")
            if start<=as_of<=end:
                if row["stock_id"] in result:
                    raise ValueError("duplicate active constituent")
                result.add(row["stock_id"])
    if not result:
        raise ValueError("No active constituents for selected date; fail closed")
    return result
