"""TW50 index constituents UNION ETF 009816 common-stock holdings.

Local files only; this does not scrape or approve any source's usage rights.
ETF observations apply ONLY to their snapshot_date, never to an inferred period.
The two source lists have independent semantics and counts; shares/weights are
not combined. Existing single-universe CSVs remain supported by universe.py.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .dates import iso_date
from .universe import load_universe

TW50 = "TW50"
ETF = "ETF:009816"


def _source_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("source_url must be HTTPS without credentials")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or any(c.isspace() for c in value)):
        raise ValueError("source_url must be HTTPS without credentials")
    return value


def _rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        names = reader.fieldnames or []
        if len(names) != len(set(names)) or not required.issubset(names):
            raise ValueError("missing or duplicate CSV headers: " + ",".join(sorted(required)))
        result = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("CSV row length differs from header")
            result.append({k: v.strip() for k, v in row.items()})
        return result


@dataclass(frozen=True)
class CombinedUniverse:
    as_of: str
    memberships: dict[str, list[dict[str, str]]]
    input_sha256: dict[str, str]

    @property
    def stock_ids(self) -> set[str]:
        return set(self.memberships)

    def metadata(self) -> dict:
        sets = {kind: {sid for sid, rows in self.memberships.items()
                       if any(r["universe_id"] == kind for r in rows)} for kind in (TW50, ETF)}
        return {"mode": "TW50_PLUS_009816", "as_of": self.as_of,
                "counts": {"tw50": len(sets[TW50]), "etf_009816": len(sets[ETF]),
                           "overlap": len(sets[TW50] & sets[ETF]), "union": len(self.stock_ids)},
                "input_sha256": dict(self.input_sha256),
                "scope": "common stocks only; not a new index or a historical backtest"}

    def properties(self, stock_id: str) -> dict:
        rows = copy.deepcopy(self.memberships[stock_id])
        ids = sorted({r["universe_id"] for r in rows})
        group = "both" if len(ids) == 2 else ("tw50_only" if ids == [TW50] else "etf_009816_only")
        return {"universe_ids": ids, "universe_memberships": rows,
                "universe_group": group, "universe_as_of": self.as_of}

    def annotate_payload(self, payload: dict) -> dict:
        records = payload.get("stocks", [])
        ids = [s["stock_id"] for s in records]
        if len(ids) != len(set(ids)) or set(ids) != self.stock_ids:
            raise ValueError("normalized stock coverage must exactly match the combined universe")
        result = copy.deepcopy(payload)
        for stock in result["stocks"]:
            stock.update(self.properties(stock["stock_id"]))
        result.setdefault("metadata", {})["research_universe"] = self.metadata()
        return result

    def annotate_nodes(self, conn) -> None:
        """Caller owns transaction. Annotate selected stock nodes; never create fake ones."""
        updates = []
        for sid in sorted(self.stock_ids):
            row = conn.execute("SELECT properties_json FROM graph_nodes WHERE node_id=?",
                               ("stock:" + sid,)).fetchone()
            if row is None:
                raise ValueError("combined universe stock missing from SQLite: " + sid)
            props = json.loads(row[0])
            props.update(self.properties(sid))
            updates.append((json.dumps(props, ensure_ascii=False, allow_nan=False), "stock:" + sid))
        conn.executemany("UPDATE graph_nodes SET properties_json=? WHERE node_id=?", updates)


def load_combined_universe(tw50_path, holdings_path, as_of: str, tw50_source_url: str) -> CombinedUniverse:
    """Require 50 index members and a nonempty same-day ETF holdings snapshot.

    Holdings columns: stock_id,snapshot_date,source_url. Historical snapshots
    may coexist, but missing target day is an error: no forward/backward fill.
    Input rights must be checked outside this parser; URL is provenance only.
    """
    target = iso_date(as_of)
    tw50_path, holdings_path = Path(tw50_path), Path(holdings_path)
    tw50_source_url = _source_url(tw50_source_url)
    # Refuse concurrent source changes; metadata records the validated input bytes.
    tw50_bytes, holdings_bytes = tw50_path.read_bytes(), holdings_path.read_bytes()
    index_ids = load_universe(tw50_path, as_of, expected_count=50)
    index_rows = _rows(tw50_path, {"stock_id", "effective_from", "effective_to"})
    holdings_rows = _rows(holdings_path, {"stock_id", "snapshot_date", "source_url"})
    if tw50_path.read_bytes() != tw50_bytes or holdings_path.read_bytes() != holdings_bytes:
        raise ValueError("universe source changed while reading; retry from a stable snapshot")
    memberships = {sid: [] for sid in sorted(index_ids)}
    for row in index_rows:
        start = iso_date(row["effective_from"])
        end = iso_date(row["effective_to"] or "9999-12-31")
        if start <= target <= end:
            memberships[row["stock_id"]].append({"universe_id": TW50,
                "membership_kind": "index_constituent", "source_url": tw50_source_url,
                "effective_from": row["effective_from"], "effective_to": row["effective_to"]})
    seen, active_urls, active = set(), set(), set()
    for row in holdings_rows:
        sid = row["stock_id"]
        if not re.fullmatch(r"TW:[0-9]{4}", sid):
            raise ValueError("ETF research input supports four-digit TW common-stock IDs only")
        day = iso_date(row["snapshot_date"])
        url = _source_url(row["source_url"])
        key = (day, sid)
        if key in seen:
            raise ValueError("duplicate ETF stock within one snapshot date")
        seen.add(key)
        if day == target:
            active.add(sid)
            active_urls.add(url)
            memberships.setdefault(sid, []).append({"universe_id": ETF,
                "membership_kind": "etf_holding", "source_url": url,
                "snapshot_date": as_of, "effective_from": as_of, "effective_to": as_of})
    if not active:
        raise ValueError("009816 holdings have no target-day snapshot; no implicit carry-forward")
    if len(active_urls) != 1:
        raise ValueError("one ETF snapshot date must use one source URL; reconcile sources first")
    return CombinedUniverse(as_of=as_of,
        memberships={sid: memberships[sid] for sid in sorted(memberships)},
        input_sha256={TW50: hashlib.sha256(tw50_bytes).hexdigest(),
                      ETF: hashlib.sha256(holdings_bytes).hexdigest()})
