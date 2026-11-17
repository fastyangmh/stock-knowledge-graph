"""Private TWSE/TPEx daily-price ingestion, independent of index/ETF membership.

Uses only the two CSV URLs linked by data.gov.tw datasets 11549 and 11371.
No credentials, graph changes, price-to-text embeddings, scheduler or Git push.
Offline inputs are explicitly labelled unverified local copies, not live checks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import tempfile
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .core import ROOT
from .dates import iso_date, timestamp
from .market_units import apply_review
from .safety import exclusive_lock, private_path
from .http_evidence import body_metadata, capture_response
from .collect_official import save_failure

MAX_BYTES = 20_000_000
LICENSE_URL = "https://data.gov.tw/license"
FEEDS = {
    "twse": {
        "source_id": "twse_daily_11549", "market": "TWSE", "dataset_id": "11549",
        "dataset_url": "https://data.gov.tw/dataset/11549",
        "resource_url": "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data",
        "title": "盤後資訊 > 個股日成交資訊",
        "columns": ("日期", "證券代號", "證券名稱", "開盤價", "最高價", "最低價", "收盤價", "成交股數", "成交金額", "成交筆數"),
    },
    "tpex": {
        "source_id": "tpex_daily_11371", "market": "TPEX", "dataset_id": "11371",
        "dataset_url": "https://data.gov.tw/dataset/11371",
        "resource_url": "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=data&se=EW",
        "title": "上櫃股票收盤行情",
        "columns": ("資料日期", "代號", "名稱", "開盤", "最高", "最低", "收盤", "成交股數", "成交金額", "成交筆數"),
    },
}
FIELDS = ("trade_date", "symbol", "name", "open", "high", "low", "close", "volume_shares", "turnover_raw", "trades")
SCHEMA = """CREATE TABLE IF NOT EXISTS market_price_observations (
    source_id TEXT NOT NULL, market TEXT NOT NULL, symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL, observed_at TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
    record_json TEXT NOT NULL, source_json TEXT NOT NULL, acquisition TEXT NOT NULL,
    PRIMARY KEY (source_id, symbol, trade_date, observed_at)
);
"""
LATEST_VIEW = """CREATE VIEW IF NOT EXISTS market_prices_latest AS
SELECT p.* FROM market_price_observations p WHERE NOT EXISTS (
    SELECT 1 FROM market_price_observations n WHERE n.source_id=p.source_id
    AND n.symbol=p.symbol AND n.trade_date=p.trade_date AND n.observed_at>p.observed_at
)"""


def encode_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def source_info(feed: str) -> dict:
    if feed not in FEEDS:
        raise ValueError("unsupported market feed")
    info = {key: value for key, value in FEEDS[feed].items() if key != "columns"}
    info.update(provider="金融監督管理委員會證券期貨局", license="OGDL-1.0",
                license_url=LICENSE_URL, reviewed_at="2026-11-16",
                attribution=f"金融監督管理委員會證券期貨局 {FEEDS[feed]['title']}；政府資料開放授權條款第1版。來源與條款見 dataset_url / license_url；整理不代表提供機關認可。")
    return info


def _symbols(values) -> set[str]:
    items = list(values)
    if not items or any(not isinstance(s, str) or not re.fullmatch(r"[0-9]{4}", s) for s in items):
        raise ValueError("provide explicit four-digit symbols; no inferred index membership")
    if len(items) != len(set(items)):
        raise ValueError("duplicate requested symbols")
    return set(items)


def _date(value: str) -> str:
    if re.fullmatch(r"\d{7,8}", value):
        year_size = len(value) - 4
        year = int(value[:year_size]) + (1911 if year_size == 3 else 0)
        return date(year, int(value[-4:-2]), int(value[-2:])).isoformat()
    match = re.fullmatch(r"(\d{3,4})/(\d{1,2})/(\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        return date(int(year) + (1911 if len(year) == 3 else 0), int(month), int(day)).isoformat()
    return iso_date(value).isoformat()


def _number(value: str, *, integer=False, missing=False):
    if value in ("", "-", "--", "N/A"):
        if missing:
            return None
        raise ValueError("missing volume, turnover or trade count is not zero")
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", value) or len(value) > 48:
        raise ValueError("invalid nonnegative market number")
    number = Decimal(value.replace(",", ""))
    if integer:
        if number != number.to_integral_value() or number > 2**63-1:
            raise ValueError("count must be a nonnegative 64-bit integer")
        return int(number)
    # Keep source precision as decimal TEXT, not binary floats or guessed currency.
    return format(number, "f")


def normalize(body: bytes, feed: str, symbols, expected_date: str, observed_at: str, *, unit_review=None) -> dict:
    source = source_info(feed)
    requested = _symbols(symbols)
    target = iso_date(expected_date)
    observed = timestamp(observed_at)
    if target > observed.astimezone(ZoneInfo("Asia/Taipei")).date():
        raise ValueError("trade date is later than observation day")
    if not body or len(body) > MAX_BYTES:
        raise ValueError("empty or oversized market CSV")
    text = body.decode("utf-8-sig")
    if text.lstrip().startswith(("<", "{", "[")):
        raise ValueError("expected official CSV, not HTML/JSON")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    columns = FEEDS[feed]["columns"]
    if not headers or len(set(headers)) != len(headers) or not all(headers) or not set(columns).issubset(headers):
        raise ValueError("missing or duplicated official CSV columns")
    reader.fieldnames = headers
    rows = list(reader)
    profile = {"columns": headers, "row_count": len(rows), "date_distribution": {},
               "selected_symbol_rows": {symbol: 0 for symbol in sorted(requested)},
               "missing_symbols": [], "selected_value_validation": "not_run"}
    mapped_rows = []
    seen = set()
    try:
        for row in rows:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("CSV row length differs from header")
            mapped = {key: row[column].strip() for key, column in zip(FIELDS, columns)}
            day = _date(mapped["trade_date"])
            profile["date_distribution"][day] = profile["date_distribution"].get(day, 0) + 1
            symbol = mapped["symbol"]
            if symbol in seen:
                raise ValueError("duplicate symbol in full source file")
            seen.add(symbol)
            if symbol in requested:
                profile["selected_symbol_rows"][symbol] += 1
                mapped_rows.append(mapped)
        profile["missing_symbols"] = sorted(requested - seen)
        if set(profile["date_distribution"]) != {expected_date}:
            raise ValueError("stale/mixed source date; refuse to relabel data")
        if profile["missing_symbols"]:
            raise ValueError("requested symbol coverage incomplete: " + ",".join(profile["missing_symbols"]))
    except ValueError as exc:
        exc.profile = profile
        raise
    records = {}
    try:
        for mapped in mapped_rows:
            symbol = mapped["symbol"]
            if not mapped["name"]:
                raise ValueError("empty security name")
            record = {"market": source["market"], "symbol": symbol, "name": mapped["name"], "trade_date": expected_date}
            for key in ("open", "high", "low", "close"):
                record[key] = _number(mapped[key], missing=True)
            for key in ("volume_shares", "trades"):
                record[key] = _number(mapped[key], integer=True)
            record["turnover_raw"] = _number(mapped["turnover_raw"])
            low, high = record["low"], record["high"]
            for key in ("open", "high", "low", "close"):
                value = record[key]
                if value is not None and ((low is not None and Decimal(value) < Decimal(low))
                                          or (high is not None and Decimal(value) > Decimal(high))):
                    raise ValueError("inconsistent OHLC range")
            record.update(price_basis="source_unadjusted", price_unit="source_reported", turnover_unit="source_reported",
                          missing_price_fields=[key for key in ("open", "high", "low", "close") if record[key] is None])
            if unit_review is not None:
                record = apply_review(record, unit_review, source["source_id"], hashlib.sha256(body).hexdigest())
            records[symbol] = record
        if set(records) != requested:
            raise ValueError("requested symbol coverage incomplete: " + ",".join(sorted(requested-set(records))))
    except ValueError as exc:
        profile["selected_value_validation"] = "failed"
        exc.profile = profile
        raise
    profile["selected_value_validation"] = "passed"
    return {"schema_version": "market-prices-1.0", "source": source, "profile": profile,
            "bytes": len(body), **body_metadata(body, source["resource_url"]),
            "observed_at": observed.isoformat(timespec="microseconds"),
            "observation_basis": "retrieved_or_imported_at_not_original_publication",
            "expected_date": expected_date, "raw_sha256": hashlib.sha256(body).hexdigest(),
            "universe_scope": "explicit_symbols_not_index_membership",
            "records": [records[key] for key in sorted(records)]}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(feed: str) -> bytes:
    info = source_info(feed)
    opener = build_opener(NoRedirect())
    for attempt in range(3):
        try:
            request = Request(info["resource_url"], headers={"Accept": "text/csv", "User-Agent": "StockKnowledgeGraph/0.3 (official open-data research)"})
            with opener.open(request, timeout=20) as response:
                return capture_response(response, info["resource_url"], MAX_BYTES)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                try:
                    captured = capture_response(exc, info["resource_url"], MAX_BYTES)
                except ValueError as size_error:
                    captured = size_error.response_body
                exc.response_body = captured
                raise
            retry = (exc.headers or {}).get("Retry-After", "")
            time.sleep(min(int(retry), 30) if retry.isdigit() else 2**attempt)
    raise AssertionError("unreachable")


def _target(path) -> Path:
    original = Path(path).absolute()
    if original.is_symlink() or any(parent.is_symlink() for parent in original.parents):
        raise ValueError("symlink output is not allowed")
    return private_path(original)


def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def store(conn, payload, acquisition: str) -> int:
    """Append observations atomically; caller commits. Never replace older evidence."""
    if acquisition not in ("https_download", "local_file_unverified"):
        raise ValueError("unknown acquisition mode")
    source = payload["source"]
    added = 0
    conn.execute("SAVEPOINT prices")
    try:
        conn.execute(SCHEMA)
        conn.execute(LATEST_VIEW)
        for record in payload["records"]:
            key = (source["source_id"], record["symbol"], record["trade_date"], payload["observed_at"])
            facts = (payload["raw_sha256"], encode_json(record).decode(), encode_json(source).decode(), acquisition)
            prior = conn.execute("SELECT raw_sha256,record_json,source_json,acquisition FROM market_price_observations WHERE source_id=? AND symbol=? AND trade_date=? AND observed_at=?", key).fetchone()
            if prior:
                if tuple(prior) != facts:
                    raise ValueError("conflicting observation at the same timestamp")
                continue
            conn.execute("INSERT INTO market_price_observations VALUES(?,?,?,?,?,?,?,?,?)",
                         (source["source_id"], source["market"], record["symbol"], record["trade_date"], payload["observed_at"], *facts))
            added += 1
        conn.execute("RELEASE prices")
    except BaseException:
        conn.execute("ROLLBACK TO prices")
        conn.execute("RELEASE prices")
        raise
    return added


def ingest(body: bytes, feed: str, symbols, expected_date: str, *, db, output, observed_at: str, acquisition: str, unit_review=None) -> dict:
    # Validate every selected row before creating a DB, snapshot or successful report.
    payload = normalize(body, feed, symbols, expected_date, observed_at, unit_review=unit_review)
    destination, database = _target(output), _target(db)
    if database == destination or database.is_relative_to(destination):
        raise ValueError("database and snapshot directories must be separate")
    source_id, checksum = payload["source"]["source_id"], payload["raw_sha256"]
    raw = _target(destination / source_id / (checksum + ".csv"))
    report = _target(destination / ("latest-" + feed + ".json"))
    if report.exists() and not report.is_file():
        raise ValueError("report path is not a regular file")
    with exclusive_lock(destination):
        if raw.exists():
            if hashlib.sha256(raw.read_bytes()).hexdigest() != checksum:
                raise ValueError("immutable price snapshot was changed")
        else:
            _atomic(raw, body)
        database.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database)
        try:
            conn.execute("BEGIN IMMEDIATE")
            added = store(conn, payload, acquisition)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        payload.update(acquisition=acquisition, inserted_observations=added,
                       snapshot_path=raw.relative_to(destination).as_posix())
        _atomic(report, encode_json(payload))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=tuple(FEEDS), required=True)
    parser.add_argument("--symbols", nargs="+", required=True, help="Explicit four-digit codes; not a TW50 list")
    parser.add_argument("--expected-date", required=True, help="Actual trading date YYYY-MM-DD; reject stale responses")
    parser.add_argument("--input", type=Path, help="Offline CSV copy instead of any network request (unverified origin)")
    parser.add_argument("--db", type=Path, default=ROOT/"local/private/market-prices.db")
    parser.add_argument("--output", type=Path, default=ROOT/"local/private/market-prices")
    parser.add_argument("--unit-review", type=Path, help="Explicit snapshot-bound unit review; use a separate DB for a new definition")
    args = parser.parse_args(argv)
    # Fail before network or disk IO for invalid selection/date/output paths.
    _symbols(args.symbols)
    if iso_date(args.expected_date) > datetime.now(ZoneInfo("Asia/Taipei")).date():
        parser.error("--expected-date is in the future")
    _target(args.db)
    _target(args.output)
    unit_review = None
    if args.unit_review:
        from .research_history import strict_json, MAX_INPUT_BYTES
        with _target(args.unit_review).open("rb") as stream:
            unit_review = strict_json(stream.read(MAX_INPUT_BYTES+1))
    body = None
    stage = "fetch" if not args.input else "read_local_input"
    try:
        if args.input:
            with args.input.open("rb") as source:
                body = source.read(MAX_BYTES+1)
        else:
            body = fetch(args.market)
        observed = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        stage = "validation_and_persistence"
        result = ingest(body, args.market, args.symbols, args.expected_date, db=args.db, output=args.output,
                        observed_at=observed, acquisition="local_file_unverified" if args.input else "https_download", unit_review=unit_review)
    except Exception as exc:
        save_failure(_target(args.output), source_info(args.market), [], stage, exc, body)
        raise
    print(f"Private prices: {len(result['records'])} securities; {result['inserted_observations']} new observations; no publication")


if __name__ == "__main__":
    main()
