"""Resolve portable archive references using the restored research readers."""
from collections import defaultdict
from contextlib import closing
from pathlib import Path
import hashlib
import sqlite3

from .bundle_audit import catalog
from .event_study import analyze
from .market_graph import HistoryBudget, read_prices
from .market_prices import FEEDS, source_info
from .research_facts import build_facts, load_market_history
from .research_history import MAX_INPUT_BYTES, MAX_REPLAY_BYTES, MAX_REPLAY_SNAPSHOTS, canonical, replay, strict_json
from .storage_references import bundle_requirements, objects, references


def read_json(path):
    with path.open("rb") as stream:
        return strict_json(stream.read(MAX_INPUT_BYTES + 1))


def relative_target(owner, value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or not path.parts:
        raise ValueError("unsafe recorded evidence path")
    return (Path(owner).parent / path).as_posix()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def read_database(path):
    conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    conn.execute("PRAGMA trusted_schema=OFF")
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA journal_mode").fetchone()[0] != "delete" or conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        conn.close()
        raise ValueError("archived SQLite integrity check failed")
    return conn


class References:
    def __init__(self, files):
        self.by_digest = defaultdict(list)
        self.rows = set()
        for entry in files:
            self.by_digest[entry["sha256"]].append(entry)

    def record(self, owner, field, sha, target):
        self.rows.add((owner, field, sha, target))

    def require_file(self, owner, field, sha, classes, *, size=None, path=None):
        for entry in self.by_digest.get(sha, []):
            if (entry["class"] in classes and (size is None or size == entry["bytes"])
                    and (path is None or path == entry["path"])):
                self.record(owner, field, sha, entry["path"])
                return entry["path"]
        raise ValueError(f"missing original bytes for {field} in {owner}")

    def report(self):
        return [dict(owner=o, field=f, sha256=s, target=t) for o, f, s, t in sorted(self.rows)]


def ledger_sources(root, conn, refs):
    sizes = conn.execute("SELECT length(CAST(payload_json AS BLOB)) FROM research_snapshots LIMIT ?",
                         (MAX_REPLAY_SNAPSHOTS + 1,))
    total = 0
    for count, (size,) in enumerate(sizes, 1):
        total += size
        if size > MAX_INPUT_BYTES or count > MAX_REPLAY_SNAPSHOTS or total > MAX_REPLAY_BYTES:
            raise ValueError("ledger exceeds supported replay budget")
    snapshots = {}
    for sha, observed, recorded, text in conn.execute(
            "SELECT sha256, observed_at, recorded_at, payload_json FROM research_snapshots"):
        body = text.encode("utf-8")
        if digest(body) != sha:
            raise ValueError("ledger snapshot checksum mismatch")
        payload = strict_json(body)
        owner = f"ledger.db#{sha}"
        meta = payload["metadata"]
        for entry in meta.get("source_snapshots", []):
            refs.require_file(owner, "source_snapshot", entry["sha256"], {"raw"}, size=entry.get("bytes"))
        for field in ("review_sha256", "note_sha256"):
            if field in meta:
                refs.require_file(owner, field, meta[field], {"raw"})
        if "unit_evidence_sha256" in meta:
            receipt = refs.require_file(owner, "unit_evidence_sha256", meta["unit_evidence_sha256"], {"raw"})
            evidence = read_json(root / receipt)
            if evidence.get("schema_version") != "financial-unit-evidence-1.0":
                raise ValueError("unknown financial unit evidence")
            for decision in evidence["decisions"]:
                refs.require_file(receipt, "raw_snapshot_sha256", decision["raw_snapshot_sha256"], {"raw"})
                for document in decision["references"]:
                    target = relative_target(receipt, document["path"])
                    refs.require_file(receipt, "reference_sha256", document["sha256"], {"raw"}, path=target)
        snapshots[sha] = (observed, recorded)
    return snapshots


def check_receipts(root, files, refs):
    for member in files:
        owner = member["path"]
        kind, name = member["class"], Path(owner).name
        if kind not in ("raw", "price_snapshot"):
            continue
        if name == "retrieval_manifest.json" or (name.startswith("retrieval-") and name.endswith(".json")):
            document = read_json(root / owner)
            entries = list(document["datasets"])
            failure = document.get("failure")
            if failure and (failure.get("path") is not None or failure.get("sha256") is not None):
                entries.append(failure)
            for entry in entries:
                path = relative_target(owner, entry["path"])
                refs.require_file(owner, "receipt_sha256", entry["sha256"], {kind}, path=path, size=entry["bytes"])
        elif kind == "price_snapshot" and name.startswith("latest-") and name.endswith(".json"):
            document = read_json(root / owner)
            path = relative_target(owner, document["snapshot_path"])
            refs.require_file(owner, "raw_sha256", document["raw_sha256"], {kind}, path=path, size=document["bytes"])


def price_sources(root, refs):
    with closing(read_database(root / "prices.db")) as conn:
        for source, sha in conn.execute("SELECT DISTINCT source_id, raw_sha256 FROM market_price_observations"):
            refs.require_file("prices.db", "raw_sha256", sha, {"price_snapshot"}, path=f"prices/{source}/{sha}.csv")
        for (text,) in conn.execute("SELECT record_json FROM market_price_observations"):
            record = strict_json(text.encode())
            for proof in record.get("unit_review", {}).get("evidence", []):
                refs.require_file("prices.db", "unit_evidence_sha256", proof["sha256"], {"raw", "price_snapshot"})
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='market_price_notices'").fetchone():
            for source, text in conn.execute("SELECT source_id, entry_json FROM market_price_notices"):
                entry = strict_json(text.encode())
                notice = entry["notice"]
                for field in ("evidence_sha256", "replacement_raw_sha256", "target_raw_sha256"):
                    sha = notice[field]
                    if sha:
                        suffix = f"notices/{sha}.bin" if field == "evidence_sha256" else f"{sha}.csv"
                        refs.require_file("prices.db", field, sha, {"price_snapshot"}, path=f"prices/{source}/{suffix}")


def check_bundle(root, bundle, conn, snapshots, refs):
    report = bundle.report
    owner = f"runs/{report['run']}/report.json"
    for document, name in ((report, Path(owner)), (bundle.manifest, Path(owner).parent / "data/manifest.json")):
        for field, sha, expected, _, _ in references(document, name):
            if expected is not None:
                refs.require_file(name.as_posix(), field, sha, {"research_bundle"}, path=expected)
    registered = report["registered_snapshot"]
    input_path = refs.require_file(owner, "input_sha256", report["input_sha256"], {"normalized_input"})
    if (digest(canonical(read_json(root / input_path))) != registered["sha256"]
            or snapshots.get(registered["sha256"]) != (registered["observed_at"], registered["recorded_at"])):
        raise ValueError("registered snapshot differs from original input or ledger")
    stock_ids = set(report["selection"]["stock_ids"])
    payload, quality = replay(conn, stock_ids, report["known_at"])
    indices = {s["sha256"]: s for s in report["quality"]["snapshots"]}
    for snapshot in quality["snapshots"]:
        sha = snapshot["sha256"]
        refs.record(owner, "snapshot_sha256", sha, f"ledger.db#{sha}")
        if "revision_payload" in snapshot and "revision_path" in indices.get(sha, {}):
            del snapshot["revision_payload"]
            snapshot["revision_path"] = f"revisions/{sha}.json"
    if quality["snapshots"] != report["quality"]["snapshots"]:
        raise ValueError("historical ledger replay differs from saved research snapshots")
    if bundle.facts is None:
        feeds = {source_info(feed)["source_id"]: feed for feed in FEEDS}
        for row in report.get("market_observations", []):
            prices = read_prices(root / "prices.db", feeds[row["source_id"]], [row["symbol"]],
                                 row["trade_date"], report["known_at"], root / "prices")
            if len(prices) != 1 or prices[0]["raw_sha256"] != row["raw_sha256"]:
                raise ValueError("legacy saved price differs from original")
        return
    scope = bundle.facts["scope"]["market"]
    prices, notices = [], []
    if scope["included"]:
        prices = load_market_history(root / "prices.db", scope["market"], sorted(s[3:] for s in stock_ids),
                                     scope["trade_date"], report["known_at"], root / "prices", HistoryBudget(),
                                     notice_history=notices)
    if notices != bundle.facts.get("market_notices", []):
        raise ValueError("market notice history differs from saved research")
    rebuilt = build_facts(payload, quality, stock_ids, report["known_at"], prices, scope["market"], scope["trade_date"])
    current = {record["id"]: record for record in rebuilt["facts"]}
    if current.keys() != {f["id"] for f in bundle.facts["facts"]}:
        raise ValueError("historical fact coverage mismatch")
    for fact in bundle.facts["facts"]:
        if any(current[fact["id"]].get(key) != value for key, value in fact.items()):
            raise ValueError("historical fact differs from restored sources")


def check_event(root, path, bundles, refs):
    event = read_json(root / path)
    # Reports written before later runs were created only name the catalog at their cutoff.
    selected = {}
    for row in event["inputs"] + event.get("excluded_inputs", []):
        bundle = bundles[row["run"]]
        if row["report_sha256"] != bundle.report_sha256 or row["run"] in selected:
            raise ValueError("event input differs from saved catalog")
        selected[row["run"]] = bundle
    for obj in objects(event):
        if "report_sha256" in obj:
            run = obj["run"]
            if selected[run].report_sha256 != obj["report_sha256"]:
                raise ValueError("event reference checksum mismatch")
            refs.record(path, "report_sha256", obj["report_sha256"], f"runs/{run}/report.json")
    rebuilt = analyze(list(selected.values()), event["analysis_at"], event["configuration"],
                      cohort=event["fact_scope"] if event.get("cohort_selection") == "explicit" else None)
    if rebuilt != event:
        raise ValueError("event report differs from restored event replay")


def audit(root, files):
    summary, bundles = catalog(root / "runs")
    if not summary["latest_valid"] or summary["counts"]["invalid"] or summary["counts"]["staging_residues"]:
        raise ValueError("incomplete or invalid research catalog")
    refs = References(files)
    check_receipts(root, files, refs)
    latest = summary["latest"]
    refs.record("runs/latest.json", "report_sha256", bundles[latest].report_sha256, f"runs/{latest}/report.json")
    if (root / "prices.db").exists():
        price_sources(root, refs)
    with closing(read_database(root / "ledger.db")) as conn:
        snapshots = ledger_sources(root, conn, refs)
        for bundle in bundles.values():
            check_bundle(root, bundle, conn, snapshots, refs)
    events = [entry["path"] for entry in files if entry["class"] == "event_report"]
    for path in events:
        check_event(root, path, bundles, refs)
    return {"runs": len(bundles), "latest": summary["latest"], "events": len(events),
            "requirements": {run: bundle_requirements(b.report) for run, b in sorted(bundles.items())},
            "references": refs.report()}
