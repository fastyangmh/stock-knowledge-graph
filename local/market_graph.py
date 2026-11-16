"""Read-only market observations -> numeric graph nodes, never text embeddings.

No network access. Selecting a historical trade date does not backdate when its
price was observed. No price adjustment, return forecast or buy/sell signal.
"""
from __future__ import annotations
import csv
import hashlib
from contextlib import closing
import io
import json
import re
import sqlite3
from pathlib import Path

from .core import upsert_node, upsert_edge
from .dates import iso_date, timestamp
from .market_prices import FEEDS, FIELDS, normalize, source_info, MAX_BYTES


def read_prices(database, feed: str, symbols, trade_date: str, known_at: str, snapshot_dir=None) -> list[dict]:
    info = source_info(feed)
    symbols = list(symbols)
    if not symbols or len(set(symbols)) != len(symbols) or any(not re.fullmatch(r"[0-9]{4}", s) for s in symbols):
        raise ValueError("explicit unique four-digit market symbols are required")
    target, cutoff = iso_date(trade_date), timestamp(known_at)
    path = Path(database).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
        raise ValueError("market database must be an existing nonsymlink file")
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.row_factory = sqlite3.Row
        kind = conn.execute("SELECT type FROM sqlite_master WHERE name='market_price_observations'").fetchone()
        if kind is None or kind[0] != "table":
            raise ValueError("market_price_observations table is missing")
        # Count and dates are deliberately bounded before loading data into memory.
        query = "SELECT * FROM market_price_observations WHERE source_id=? AND trade_date=? AND symbol IN (" + ",".join("?" for _ in symbols) + ")"
        rows = conn.execute(query + " ORDER BY observed_at LIMIT 10001", (info["source_id"], trade_date, *symbols)).fetchall()
    if len(rows) > 10000:
        raise ValueError("market revision budget exceeded")
    latest = {}
    for row in rows:
        observed = timestamp(row["observed_at"])
        if observed > cutoff:
            continue
        if row["market"] != info["market"] or row["acquisition"] not in ("https_download", "local_file_unverified"):
            raise ValueError("market observation identity/acquisition is inconsistent")
        if not re.fullmatch(r"[0-9a-f]{64}", row["raw_sha256"]):
            raise ValueError("market observation has invalid raw checksum")
        source = json.loads(row["source_json"])
        if source != info:
            raise ValueError("market source metadata changed; review the feed before integration")
        record = json.loads(row["record_json"])
        if not isinstance(record, dict) or record.get("symbol") != row["symbol"] or record.get("trade_date") != trade_date or record.get("market") != info["market"]:
            raise ValueError("market record differs from its observation key")
        for key in ("volume_shares", "trades"):
            if type(record.get(key)) is not int:
                raise ValueError("market counts must be integers")
        for key in ("open", "high", "low", "close", "turnover_raw"):
            if record.get(key) is not None and not isinstance(record[key], str):
                raise ValueError("market decimal fields must retain source precision as TEXT")
        # Reuse the existing financial validation rules, without treating these
        # reconstructed bytes as the raw snapshot or changing its checksum.
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(FEEDS[feed]["columns"])
        writer.writerow([record.get(key) if record.get(key) is not None else "--" for key in FIELDS])
        normalized = normalize(buffer.getvalue().encode(), feed, [row["symbol"]], trade_date, row["observed_at"])
        if normalized["records"][0] != record:
            raise ValueError("market record values/basis fail normalized contract")
        verified = False
        if snapshot_dir is not None:
            raw = Path(snapshot_dir).absolute()/info["source_id"]/(row["raw_sha256"] + ".csv")
            if raw.is_symlink() or any(p.is_symlink() for p in raw.parents):
                raise ValueError("symlink price snapshot is not permitted")
            with raw.open("rb") as source_file:
                body = source_file.read(MAX_BYTES+1)
            if len(body) > MAX_BYTES or hashlib.sha256(body).hexdigest() != row["raw_sha256"]:
                raise ValueError("market raw snapshot checksum mismatch")
            original = normalize(body, feed, [row["symbol"]], trade_date, row["observed_at"])
            if original["records"][0] != record:
                raise ValueError("market record does not match its raw source snapshot")
            verified = True
        item = {"record": record, "raw_snapshot_verified": verified, "source": source, "observed_at": row["observed_at"],
                "raw_sha256": row["raw_sha256"], "acquisition": row["acquisition"]}
        prior = latest.get(row["symbol"])
        if prior is not None and observed == timestamp(prior["observed_at"]) and item != prior:
            raise ValueError("conflicting market revisions at the same instant")
        if prior is None or observed > timestamp(prior["observed_at"]):
            latest[row["symbol"]] = item
    if set(latest) != set(symbols):
        raise ValueError("market coverage missing at known_at: " + ",".join(sorted(set(symbols)-set(latest))))
    return [latest[symbol] for symbol in sorted(latest)]


def attach_prices(conn, observations: list[dict]) -> int:
    """Attach facts to existing stock nodes. Caller owns the SQLite transaction."""
    for item in observations:
        record, source = item["record"], item["source"]
        sid = "TW:" + record["symbol"]
        if conn.execute("SELECT 1 FROM stocks WHERE stock_id=?", (sid,)).fetchone() is None:
            raise ValueError("market stock is absent from research input: " + sid)
        conn.execute("INSERT INTO sources VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET provider=excluded.provider,url=excluded.url,license_type=excluded.license_type",
                     (source["source_id"], source["provider"], source["dataset_url"], source["license"]))
        node_id = f"market:{source['source_id']}:{record['symbol']}:{record['trade_date']}"
        props = {**record, "source_id": source["source_id"], "source_url": source["dataset_url"],
                 "license_url": source["license_url"], "attribution": source["attribution"],
                 "available_at": item["observed_at"], "observed_at": item["observed_at"],
                 "raw_sha256": item["raw_sha256"], "acquisition": item["acquisition"],
                 "raw_snapshot_verified": item["raw_snapshot_verified"],
                 "description": "盤後數值觀察；未還原價格，非語意分數或投資訊號。"}
        upsert_node(conn, node_id, "market_price", f"{record['symbol']} {record['trade_date']} 盤後行情", stock_id=sid, props=props)
        upsert_edge(conn, "stock:" + sid, node_id, "has_market_price", "observed_official_daily_price")
    return len(observations)
