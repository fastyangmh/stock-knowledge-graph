"""Append-only normalized-input ledger and as-recorded replay for private research.

A snapshot's collection time is NOT its publication time. Replay uses both the
provided observation time and the actual local registration time. Imported old
files do not magically become evidence that this system knew in the past.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .dates import iso_date, timestamp
from .financial_definitions import financial_definition

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_REPLAY_SNAPSHOTS = 5000
MAX_REPLAY_BYTES = 128 * 1024 * 1024
TABLE = """CREATE TABLE IF NOT EXISTS research_snapshots(
    sha256 TEXT PRIMARY KEY, observed_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    CHECK(length(sha256)=64)
)"""
GROUPS = ("stocks", "sources", "documents", "financial_metrics", "chip_metrics")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def strict_json_value(body: bytes):
    if not body or len(body) > MAX_INPUT_BYTES:
        raise ValueError("normalized input is empty or exceeds 32 MiB")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON value: " + value)
    return json.loads(body.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=invalid)


def strict_json(body: bytes) -> dict:
    value = strict_json_value(body)
    if not isinstance(value, dict):
        raise ValueError("normalized input must be a JSON object")
    return value


def validate_symbols(symbols) -> set[str]:
    items = list(symbols)
    if not items or len(items) > 500 or any(not isinstance(s, str) or not re.fullmatch(r"[0-9]{4}", s) for s in items):
        raise ValueError("provide 1..500 explicit four-digit symbols; not index membership")
    if len(items) != len(set(items)):
        raise ValueError("duplicate requested symbols")
    return {"TW:" + s for s in items}


def _ids(rows, key):
    ids = [row.get(key) for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("missing or duplicate " + key)
    return set(ids)


def validate_payload(payload: dict) -> dict:
    """Strict normalized contract. Validation is not proof of source permission."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    for group in GROUPS:
        rows = payload.get(group, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(group + " must be an array of objects")
    stocks = _ids(payload.get("stocks", []), "stock_id")
    if not stocks:
        raise ValueError("normalized input requires stocks")
    for stock in payload["stocks"]:
        sid = stock["stock_id"]
        if (not re.fullmatch(r"TW:[0-9]{4}", sid) or stock.get("ticker") != sid[3:]
                or stock.get("market") != "TW" or not isinstance(stock.get("name"), str) or not stock["name"].strip()):
            raise ValueError("invalid normalized stock identity")
    sources = _ids(payload.get("sources", []), "source_id")
    for source in payload.get("sources", []):
        if not isinstance(source.get("provider"), str) or not source["provider"].strip():
            raise ValueError("source provider is required")
    _ids(payload.get("documents", []), "document_id")
    for doc in payload.get("documents", []):
        if doc.get("source_id") not in sources:
            raise ValueError("document source_id must resolve within normalized sources")
        if not all(isinstance(doc.get(k), str) and doc[k] for k in ("title", "doc_type")):
            raise ValueError("document title and doc_type are required")
        if not isinstance(doc.get("content", ""), str):
            raise ValueError("document content must be text")
        timestamp(doc["published_at"])
        timestamp(doc.get("available_at", doc["published_at"]))
        links = doc.get("stock_ids", [])
        if not isinstance(links, list) or len(links) != len(set(links)) or not set(links).issubset(stocks):
            raise ValueError("document stock coverage is invalid")
    keys = set()
    for group in ("financial_metrics", "chip_metrics"):
        for row in payload.get(group, []):
            financial_definition(row)
            if row.get("stock_id") not in stocks or row.get("source_id") not in sources:
                raise ValueError("each metric needs a known stock_id and source_id")
            if not isinstance(row.get("metric"), str) or not row["metric"]:
                raise ValueError("metric name is required")
            if type(row.get("value")) not in (int, float) or not math.isfinite(row["value"]):
                raise ValueError("metric value must be finite, not boolean")
            day = iso_date(row["period_end"] if group == "financial_metrics" else row["trade_date"])
            available = timestamp(row["available_at"])
            if day > available.astimezone(ZoneInfo("Asia/Taipei")).date():
                raise ValueError("metric period is later than declared availability")
            if group == "financial_metrics" and (not isinstance(row.get("period_type"), str) or not row["period_type"]):
                raise ValueError("period_type is required")
            key = (group, row["source_id"], row["stock_id"], row["metric"], day.isoformat(), row.get("period_type"))
            if key in keys:
                raise ValueError("duplicate metric within one snapshot")
            keys.add(key)
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("observed_at"):
        raise ValueError("metadata.observed_at is required; do not invent a publication date")
    observed = timestamp(metadata["observed_at"])
    if len(canonical(payload)) > MAX_INPUT_BYTES:
        raise ValueError("normalized payload exceeds 32 MiB")
    warnings = []
    if any(row.get("unit") in (None, "", "source_reported") for row in payload.get("financial_metrics", [])):
        warnings.append("monetary_scale_unconfirmed: source_reported values are not comparable across sources")
    if not payload.get("documents"):
        warnings.append("no_documents: no textual similarity can be computed")
    return {"observed_at": observed.isoformat(timespec="microseconds"),
            "counts": {group: len(payload.get(group, [])) for group in GROUPS}, "warnings": warnings}


def record_snapshot(conn: sqlite3.Connection, payload: dict) -> dict:
    """Append one immutable snapshot under a savepoint; caller commits."""
    quality = validate_payload(payload)
    recorded = utc_now()
    if timestamp(quality["observed_at"]) > timestamp(recorded):
        raise ValueError("observation timestamp is in the future")
    body = canonical(payload)
    checksum = hashlib.sha256(body).hexdigest()
    conn.execute("SAVEPOINT research_observation")
    try:
        conn.execute(TABLE)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_recorded ON research_snapshots(recorded_at, observed_at)")
        # Unit migrations use a new ledger. Never rewrite observation times to
        # make revised definitions win the old ledger's same-time conflict rule.
        version = payload['metadata'].get('normalization_version')
        read_bytes = 0
        for count, (prior_body,) in enumerate(conn.execute("SELECT payload_json FROM research_snapshots"), 1):
            read_bytes += len(prior_body.encode('utf-8'))
            if count > MAX_REPLAY_SNAPSHOTS or read_bytes > MAX_REPLAY_BYTES:
                raise ValueError('normalization ledger inspection budget exceeded')
            prior = strict_json(prior_body.encode('utf-8'))
            if prior['metadata'].get('normalization_version') != version:
                raise ValueError('normalization version changed; use a separate ledger and output root')
        old = conn.execute("SELECT observed_at,recorded_at,payload_json FROM research_snapshots WHERE sha256=?", (checksum,)).fetchone()
        if old:
            if old[0] != quality["observed_at"] or old[2].encode("utf-8") != body:
                raise ValueError("immutable normalized snapshot has been changed")
            recorded = old[1]
        else:
            conn.execute("INSERT INTO research_snapshots VALUES(?,?,?,?)",
                         (checksum, quality["observed_at"], recorded, body.decode("utf-8")))
        conn.execute("RELEASE research_observation")
    except BaseException:
        conn.execute("ROLLBACK TO research_observation")
        conn.execute("RELEASE research_observation")
        raise
    return {"sha256": checksum, "recorded_at": recorded, "observed_at": quality["observed_at"],
            "inserted": old is None, "quality": quality}


def replay(conn: sqlite3.Connection, stock_ids: set[str], known_at: str) -> tuple[dict, dict]:
    """Rebuild facts known by cutoff, never infer index labels or deleted history.

Records are revision/upsert observations, not deletions. Ambiguous metric sources
and contradictory same-time revisions fail instead of choosing silently.
"""
    if not stock_ids:
        raise ValueError("empty research selection")
    cutoff = timestamp(known_at)
    if cutoff > timestamp(utc_now()):
        raise ValueError("known_at must not be in the future")
    if conn.execute("SELECT count(*) FROM research_snapshots").fetchone()[0] > MAX_REPLAY_SNAPSHOTS:
        raise ValueError("snapshot replay budget exceeded; archive or narrow the research database")
    rows = conn.execute("SELECT sha256,observed_at,recorded_at,payload_json FROM research_snapshots ORDER BY observed_at,recorded_at,sha256")
    read_bytes = 0
    selected = {group: {} for group in GROUPS}
    ranks, used, warnings = {}, [], set()
    def keep(group, key, item, rank, facts=None):
        prior = ranks.get((group, key))
        facts = canonical(item) if facts is None else canonical(facts)
        if prior and rank == prior[0] and facts != prior[1]:
            raise ValueError("conflicting same-time revision; reconcile source observations")
        if prior is None or rank > prior[0]:
            ranks[group, key] = (rank, facts)
            selected[group][key] = copy.deepcopy(item)
    for checksum, observed_at, recorded_at, text in rows:
        observed, recorded = timestamp(observed_at), timestamp(recorded_at)
        if max(observed, recorded) > cutoff:
            continue
        read_bytes += len(text.encode("utf-8"))
        if read_bytes > MAX_REPLAY_BYTES:
            raise ValueError("snapshot replay byte budget exceeded")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != checksum:
            raise ValueError("normalized snapshot checksum mismatch")
        payload = strict_json(text.encode("utf-8"))
        quality = validate_payload(payload)
        if quality["observed_at"] != observed_at:
            raise ValueError("snapshot timestamp differs from payload")
        relevant = {s["stock_id"] for s in payload["stocks"]} & stock_ids
        updates_selected_doc = any(d["document_id"] in selected["documents"] for d in payload.get("documents", []))
        if not relevant and not updates_selected_doc:
            continue
        used.append({"sha256": checksum, "observed_at": observed_at, "recorded_at": recorded_at,
                     "metadata": copy.deepcopy(payload["metadata"]),
                     "sources": copy.deepcopy(payload.get("sources", []))})
        warnings.update(quality["warnings"])
        for source in payload.get("sources", []):
            keep("sources", source["source_id"], source, observed)
        for stock in payload["stocks"]:
            if stock["stock_id"] in relevant:
                keep("stocks", stock["stock_id"], stock, observed)
        for doc in payload.get("documents", []):
            links = set(doc.get("stock_ids", [])) & stock_ids
            if not links and doc["document_id"] not in selected["documents"]:
                continue
            item = copy.deepcopy(doc)
            available = timestamp(doc.get("available_at", doc["published_at"]))
            if available > cutoff:
                continue
            item["stock_ids"] = sorted(links)
            item["available_at"] = max(available, observed, recorded).isoformat(timespec="microseconds")
            item["input_snapshot_sha256"] = checksum
            item["registered_at"] = recorded_at
            # Provenance differences between repeated observations are not fact conflicts.
            rank = (observed, available)
            keep("documents", doc["document_id"], item, rank, {**doc, "stock_ids": sorted(links)})
        for group in ("financial_metrics", "chip_metrics"):
            for metric in payload.get(group, []):
                if metric["stock_id"] not in relevant:
                    continue
                available = timestamp(metric["available_at"])
                if available > cutoff:
                    continue
                item = copy.deepcopy(metric)
                item["source_available_at"] = metric["available_at"]
                item["observed_at"] = observed_at
                item["available_at"] = max(available, observed, recorded).isoformat(timespec="microseconds")
                item["input_snapshot_sha256"] = checksum
                item["registered_at"] = recorded_at
                key = (metric["stock_id"], metric["metric"], metric.get("period_end", metric.get("trade_date")), metric.get("period_type"))
                old = selected[group].get(key)
                if old and old["source_id"] != metric["source_id"]:
                    raise ValueError("multiple sources for one metric require an explicit reconciliation policy")
                keep(group, key, item, (observed, available), metric)
    if set(selected["stocks"]) != stock_ids:
        raise ValueError("no as-recorded stock coverage for: " + ",".join(sorted(stock_ids-set(selected["stocks"]))))
    selected["documents"] = {key: doc for key, doc in selected["documents"].items() if doc["stock_ids"]}
    payload = {group: [values[k] for k in sorted(values)] for group, values in selected.items()}
    payload["metadata"] = {"observed_at": known_at, "selection_mode": "explicit_symbols_not_index_membership",
                           "known_at": known_at, "snapshot_ids": [s["sha256"] for s in used]}
    return payload, {"known_at": known_at, "snapshots": used, "warnings": sorted(warnings),
                     "counts": {g: len(payload[g]) for g in GROUPS},
                     "scope": "as-recorded local observations only; not reconstructed historical market knowledge"}
