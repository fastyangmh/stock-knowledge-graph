"""Bounded, read-only historical price loader for independent research reminders."""
from contextlib import closing
from datetime import timedelta
from pathlib import Path
import sqlite3

from .alerts import policy
from .dates import iso_date, timestamp
from .market_graph import HistoryBudget, read_prices
from .market_prices import source_info
from .research_history import validate_symbols


def load_price_history(database, feed, symbols, trade_date, known_at, snapshot_dir, config=None):
    config = policy(config)
    ids = validate_symbols(symbols)
    symbols = sorted(sid[3:] for sid in ids)
    target, cutoff = iso_date(trade_date), timestamp(known_at)
    count = max(config["volume_window"], 1)+1
    lower = target-timedelta(days=(count+1)*config["max_observation_gap_days"])
    path = Path(database).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
        raise ValueError("alert price DB must be an existing nonsymlink file")
    info = source_info(feed)
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        sql = "SELECT symbol,trade_date,observed_at FROM market_price_observations WHERE source_id=? AND trade_date>=? AND trade_date<=? AND symbol IN ("+",".join("?" for _ in symbols)+") LIMIT 100001"
        rows = conn.execute(sql, (info["source_id"], lower.isoformat(), trade_date, *symbols)).fetchall()
    if len(rows) > 100000:
        raise ValueError("alert price history exceeds revision budget")
    by_day = {}
    for symbol, day, observed in rows:
        iso_date(day)
        if timestamp(observed) <= cutoff:
            by_day.setdefault(day, set()).add(symbol)
    result = {sid:[] for sid in ids}
    budget = HistoryBudget()
    for day, candidates in sorted(by_day.items(), reverse=True):
        members = sorted(symbol for symbol in candidates if len(result["TW:"+symbol]) < count)
        if not members:
            continue
        # Reuses source, revision, OHLC, and original CSV checksum verification.
        for item in read_prices(database, feed, members, day, known_at, snapshot_dir=snapshot_dir, budget=budget):
            result["TW:"+item["record"]["symbol"]].append(item)
    return {sid: list(reversed(items)) for sid, items in result.items()}
