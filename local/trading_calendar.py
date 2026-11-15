"""Explicit TW exchange calendar gate: never assume weekdays are trading days."""
import argparse
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")

def is_trading_day(calendar_csv,date):
    with Path(calendar_csv).open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows or not {"date","is_open"}.issubset(rows[0]):
        raise ValueError("calendar CSV requires date,is_open columns")
    matches=[r for r in rows if r["date"]==date]
    if len(matches)!=1:
        raise ValueError(f"calendar date {date} missing or duplicated; fail closed")
    value=matches[0]["is_open"].strip().lower()
    if value not in ("1","0","true","false"):
        raise ValueError("is_open must be 0/1/true/false")
    return value in ("1","true")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--calendar",type=Path,required=True)
    p.add_argument("--date",default=datetime.now(TZ).date().isoformat())
    args=p.parse_args()
    if not is_trading_day(args.calendar,args.date):
        print("Closed market; no update")
        return
    print("Trading day:",args.date)

if __name__=="__main__":
    main()
