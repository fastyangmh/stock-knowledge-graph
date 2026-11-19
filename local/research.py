"""Manual private research bundles: normalized financial facts + optional prices.

No downloads, index-membership assumptions, scheduling, orders or Git operations.
Each success is a new immutable bundle (SQLite + graph JSON + quality report).
The ledger preserves normalized observations; public data/ is never modified.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
import sqlite3
import tempfile
import uuid
from pathlib import Path

from .core import ROOT, connect, init_db, import_payload, upsert_node, upsert_edge, digest
from .collect_official import atomic_bytes
from .dates import iso_date, timestamp
from .export_json import export
from .market_graph import attach_prices, HistoryBudget, observation_report
from .research_history import (strict_json, canonical, record_snapshot, replay,
                               validate_symbols, utc_now, MAX_INPUT_BYTES)
from .safety import private_path, exclusive_lock
from .semantic import compute_semantic, DEFAULT_MODEL, INPUT_VERSION
from .similarity import compute
from .validate_release import validate_data_dir

ENGINE_VERSION = "private-research-1"


def file_digest(path):
    with Path(path).open("rb") as stream:
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
        return checksum.hexdigest()


def guarded(path) -> Path:
    original = Path(path).absolute()
    if original.is_symlink() or any(parent.is_symlink() for parent in original.parents):
        raise ValueError("symlink paths are not accepted for private research")
    return private_path(original)


def attach_metrics(conn, payload):
    sources = {source["source_id"]: source for source in payload["sources"]}
    count = 0
    evidence_by_key = {}
    for doc in payload["documents"]:
        for sid in doc.get("stock_ids", []):
            evidence_by_key.setdefault((doc.get("source_id"), doc.get("period_end"), sid), []).append(doc)
    for metric in payload["financial_metrics"]:
        source = sources[metric["source_id"]]
        key = (metric["stock_id"], metric["source_id"], metric["metric"], metric["period_end"], metric["period_type"])
        node_id = "metric:" + digest(json.dumps(key, ensure_ascii=False))
        props = {**metric, "source_url": source.get("url"), "license_type": source.get("license_type"),
                 "description": "來源報告數值；未知尺度不換算，非語意分數或投資建議。"}
        evidence = []
        for doc in evidence_by_key.get((metric["source_id"], metric["period_end"], metric["stock_id"]), []):
            evidence.append(doc["document_id"])
            for field in ("license_url", "attribution"):
                if field in doc:
                    props[field] = doc[field]
        upsert_node(conn, node_id, "financial_metric", metric["metric"] + " " + metric["period_end"],
                    stock_id=metric["stock_id"], props=props)
        upsert_edge(conn, "stock:" + metric["stock_id"], node_id, "has_financial_metric", "reported_financial_fact", evidence=evidence)
        count += 1
    return count


def _read_last(root):
    pointer = root/"latest.json"
    if not pointer.exists():
        return None
    if pointer.is_symlink():
        raise ValueError("latest pointer is a symlink")
    obj = strict_json(pointer.read_bytes())
    name = obj.get("run")
    if (obj.get("engine") != ENGINE_VERSION or not isinstance(name, str)
            or len(name) != 32 or any(c not in "0123456789abcdef" for c in name)):
        raise ValueError("unexpected latest pointer; do not overwrite unrelated files")
    bundle = root/name
    report = guarded(bundle/"report.json")
    database = guarded(bundle/"graph.db")
    body = report.read_bytes()
    if hashlib.sha256(body).hexdigest() != obj.get("report_sha256"):
        raise ValueError("prior bundle report checksum mismatch")
    info = strict_json(body)
    if info.get("engine") != ENGINE_VERSION or info.get("run") != name or info.get("status") != "complete":
        raise ValueError("prior bundle is incomplete")
    if file_digest(database) != info.get("graph_db_sha256"):
        raise ValueError("prior graph database changed; refusing unsafe cache reuse")
    # Validate all saved evidence, not only the database used for vector reuse.
    from .bundle_audit import audit_bundle
    audit_bundle(root, name, expected_report_sha=obj["report_sha256"])
    return database


def _reuse_cache(conn, prior, model_name, revision):
    if prior is None:
        return 0
    config = json.dumps({"name":model_name, "revision":revision, "input_version":INPUT_VERSION},
                        sort_keys=True, ensure_ascii=False)
    model_id = "st:" + digest(config)[:24]
    with closing(sqlite3.connect(prior.as_uri()+"?mode=ro", uri=True)) as old:
        old.execute("PRAGMA query_only=ON")
        old.execute("PRAGMA trusted_schema=OFF")
        model = old.execute("SELECT * FROM embedding_models WHERE model_id=?", (model_id,)).fetchone()
        if model is None:
            return 0
        if model[3] != config:
            raise ValueError("prior model identity differs from requested cache")
        conn.execute("INSERT INTO embedding_models VALUES(?,?,?,?)", model)
        nodes = {r[0] for r in conn.execute("SELECT node_id FROM graph_nodes")}
        docs = {r[0] for r in conn.execute("SELECT document_id FROM documents")}
        count = 0
        for row in old.execute("SELECT * FROM embeddings WHERE model_id=?", (model_id,)):
            if row[0] in nodes:
                conn.execute("INSERT INTO embeddings VALUES(?,?,?,?,?)", row)
                count += 1
        for edge in old.execute("SELECT * FROM graph_edges WHERE model_id=?", (model_id,)):
            if edge[1] in nodes and edge[2] in nodes:
                conn.execute("INSERT INTO graph_edges VALUES(?,?,?,?,?,?,?,?,?)", edge)
                for evidence in old.execute("SELECT edge_id,document_id FROM edge_evidence WHERE edge_id=?", (edge[0],)):
                    if evidence[1] in docs:
                        conn.execute("INSERT INTO edge_evidence VALUES(?,?)", evidence)
        state = old.execute("SELECT * FROM similarity_state WHERE model_id=?", (model_id,)).fetchone()
        if state:
            conn.execute("INSERT INTO similarity_state VALUES(?,?,?,?)", state)
    return count


def run(input_file, symbols, *, history_db, output_root, analysis="none", known_at=None,
        prices_db=None, trade_date=None, price_market="twse", price_snapshots=None, model=DEFAULT_MODEL, revision=None,
        top_k=10, threshold=0.65, max_pairs=2_000_000, lookback_days=None, encoder=None,
        alerts=False, alerts_config=None, max_information_nodes=100, enable_source_revisions=False):
    """Materialize an isolated research database from as-recorded observations."""
    stock_ids = validate_symbols(symbols)
    if type(max_information_nodes) is not int or not 0 <= max_information_nodes <= 100:
        raise ValueError("display information limit must be 0..100")
    from .alerts import evaluate, policy
    if type(alerts) is not bool or (alerts_config is not None and not alerts):
        raise ValueError("alerts configuration requires alerts=True")
    rules = policy(alerts_config) if alerts else None
    if analysis not in ("none", "lexical", "semantic"):
        raise ValueError("analysis must be none, lexical or semantic")
    if type(top_k) is not int or top_k < 1 or not isinstance(model, str) or not model.strip():
        raise ValueError("invalid top_k or model")
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("invalid threshold")
    if type(max_pairs) is not int or max_pairs < 0 or (lookback_days is not None and (type(lookback_days) is not int or lookback_days < 0)):
        raise ValueError("invalid comparison budget/window")
    root, ledger = guarded(output_root), guarded(history_db)
    source_path = guarded(input_file)
    if ledger == source_path or ledger == root or ledger.is_relative_to(root) or source_path.is_relative_to(root):
        raise ValueError("input, history DB and bundle directory must be separate")
    if known_at and timestamp(known_at) > timestamp(utc_now()):
        raise ValueError("known_at must not be in the future")
    if len({bool(prices_db), bool(trade_date), bool(price_snapshots)}) != 1:
        raise ValueError("--prices-db, --trade-date and --price-snapshots must be used together")
    if trade_date:
        iso_date(trade_date)
    with source_path.open("rb") as source:
        body = source.read(MAX_INPUT_BYTES+1)
    input_payload = strict_json(body)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(root), closing(sqlite3.connect(ledger)) as ledger_conn:
        prior = _read_last(root)
        # Closing an uncommitted connection rolls back every staged observation.
        ledger_conn.execute("BEGIN IMMEDIATE")
        snapshot = record_snapshot(ledger_conn, input_payload, enable_source_revisions=enable_source_revisions)
        cutoff = timestamp(known_at or utc_now()).isoformat(timespec="microseconds")
        payload, quality = replay(ledger_conn, stock_ids, cutoff)
        from .research_facts import build_facts, load_market_history
        notices = []
        market_history = load_market_history(guarded(prices_db), price_market, sorted(s[3:] for s in stock_ids),
            trade_date, cutoff, guarded(price_snapshots), HistoryBudget(), notice_history=notices) if prices_db else []
        prices = [item for item in market_history if item["record"]["trade_date"] == trade_date]
        covered = {"TW:"+item["record"]["symbol"] for item in prices}
        if notices:
            from .market_notices import withdrawn_stocks
            quality['market_notices'] = notices
            covered.update(withdrawn_stocks(notices, trade_date, timestamp(cutoff)))
        if prices_db and covered != stock_ids:
            raise ValueError("market coverage missing at known_at")
        revision_files = {}
        for item in quality['snapshots']:
            if 'revision_payload' in item:
                path = 'revisions/' + item['sha256'] + '.json'
                revision_files[path] = item.pop('revision_payload')
                item['revision_path'] = path
        facts = build_facts(payload, quality, stock_ids, cutoff, market_history,
                            price_market if prices_db else None, trade_date)
        alert_report = None
        if alerts:
            # Same reminder window, using already verified observations. This
            # avoids re-reading raw history outside the shared work budget.
            from datetime import timedelta
            history = {sid: [] for sid in stock_ids}
            if prices_db:
                count = max(rules["volume_window"], 1)+1
                lower = iso_date(trade_date)-timedelta(days=(count+1)*rules["max_observation_gap_days"])
                for item in market_history:
                    if iso_date(item["record"]["trade_date"]) >= lower:
                        history["TW:"+item["record"]["symbol"]].append(item)
                history = {sid: rows[-count:] for sid, rows in history.items()}
            alert_report = evaluate(payload, history, stock_ids, cutoff, trade_date=trade_date, config=rules)
        name = uuid.uuid4().hex
        final = root/name
        with tempfile.TemporaryDirectory(prefix=".research-stage-", dir=root) as temporary:
            stage = Path(temporary)/name
            stage.mkdir()
            conn = connect(stage/"graph.db")
            try:
                init_db(conn)
                conn.execute("BEGIN IMMEDIATE")
                import_payload(conn, payload)
                metric_count = attach_metrics(conn, payload)
                price_count = attach_prices(conn, prices)
                cached = _reuse_cache(conn, prior, model, revision) if analysis == "semantic" else 0
                stats = {"mode": analysis, "encoded": 0, "pairs_evaluated": 0}
                if analysis == "semantic":
                    stats.update(compute_semantic(conn, model_name=model, revision=revision, encoder=encoder,
                                 top_k=top_k, threshold=threshold, max_pairs=max_pairs,
                                 as_of=cutoff, lookback_days=lookback_days))
                elif analysis == "lexical":
                    stats.update(compute(conn, top_k=top_k, threshold=threshold))
                export_options = {"research_alerts": alert_report} if alerts else {}
                manifest = export(conn, stage/"data", universe=stock_ids, lifecycle=True, max_information_nodes=max_information_nodes, **export_options)
                graph_count = validate_data_dir(stage/"data")
                conn.commit()
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("research SQLite integrity check failed")
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
            missing_prices = sum(bool(p["record"]["missing_price_fields"]) for p in prices)
            warnings = list(quality["warnings"])
            if prices:
                warnings.append("unadjusted_prices: no returns, trading signals or cross-source unit comparisons")
            if any(p["acquisition"] == "local_file_unverified" for p in prices):
                warnings.append("market_input_is_unverified_local_file")
            if missing_prices:
                warnings.append("missing_OHLC_fields_in_selected_prices")
            if analysis == "semantic" and not revision:
                warnings.append("model_revision_not_pinned: mutable remote model names are not fully reproducible")
            if analysis == "lexical":
                warnings.append("lexical_baseline_is_not_an_AI_semantic_model")
            report = {"engine": ENGINE_VERSION, "status": "complete", "run": name,
                      "completed_at": utc_now(), "known_at": cutoff,
                      "selection": {"mode": "explicit_symbols", "stock_ids": sorted(stock_ids),
                                    "index_membership_inferred": False},
                      "input_sha256": hashlib.sha256(body).hexdigest(), "registered_snapshot": snapshot,
                      "quality": {**quality, "warnings": sorted(set(warnings))},
                      "analysis": {**stats, "cached_vectors_copied": cached},
                      "configuration": {"analysis": {"mode": analysis, "model": model if analysis == "semantic" else None,
                          "revision": revision if analysis == "semantic" else None, "top_k": top_k,
                          "threshold": threshold, "max_pairs": max_pairs, "lookback_days": lookback_days},
                          "lifecycle": "display-caps-v1", "max_information_nodes": max_information_nodes, "engine": ENGINE_VERSION},
                      "counts": {"graphs": graph_count, "financial_metric_nodes": metric_count,
                                 "market_nodes": price_count, "market_missing_OHLC": missing_prices},
                      "market_observations": [observation_report(p) for p in prices],
                      "graph_db_sha256": file_digest(stage/"graph.db"),
                      "manifest_sha256": hashlib.sha256((stage/"data/manifest.json").read_bytes()).hexdigest(),
                      "public_publish": False,
                      "scope": "private as-recorded research bundle; no historical-market backtest or license certification"}
            if alerts:
                alerts_body = canonical({"schema_version":"research-alerts-1.0", "stocks":alert_report})
                atomic_bytes(stage/"alerts.json", alerts_body)
                report["research_alerts"] = {"enabled":True, "sha256":hashlib.sha256(alerts_body).hexdigest(),
                    "config":rules, "path":"alerts.json", "combined_score":False,
                    "triggered_by_category":{category:sum(c["status"] == "triggered"
                        for r in alert_report.values() for c in r["categories"][category])
                        for category in ("price_volume", "monthly_revenue")}}
            if revision_files:
                (stage/'revisions').mkdir()
                for path, envelope in revision_files.items():
                    atomic_bytes(stage/path, canonical(envelope))
            facts_body = canonical(facts)
            atomic_bytes(stage/"research-facts.json", facts_body)
            report["research_facts"] = {"schema_version": facts["schema_version"], "path": "research-facts.json",
                "sha256": hashlib.sha256(facts_body).hexdigest(), "count": len(facts["facts"]),
                "size_bytes": len(facts_body), "market": facts["scope"]["market"]}
            report_body = canonical(report)
            atomic_bytes(stage/"report.json", report_body)
            from .bundle_audit import audit_bundle
            audit_bundle(Path(temporary), name)
            ledger_conn.commit()
            stage.rename(final)
            # A pointer failure leaves a complete but unreferenced bundle, never corrupts the old one.
            atomic_bytes(root/"latest.json", canonical({"engine": ENGINE_VERSION, "run": name,
                         "report_sha256": hashlib.sha256(report_body).hexdigest()}))
        return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="Normalized private JSON with metadata.observed_at and metric source_id")
    p.add_argument("--symbols", required=True, nargs="+")
    p.add_argument("--history-db", type=Path, default=ROOT/"local/private/research-history.db")
    p.add_argument("--output-root", type=Path, default=ROOT/"local/private/research-runs")
    p.add_argument("--enable-source-revisions", action="store_true", help="Verify and migrate the normalized ledger to accept explicit source notices")
    p.add_argument("--known-at", help="Timezone-aware local knowledge cutoff; default is now")
    p.add_argument("--prices-db", type=Path)
    p.add_argument("--price-snapshots", type=Path, help="Required raw snapshot directory when including market observations")
    p.add_argument("--trade-date", help="Explicit price date, never relabel stale data")
    p.add_argument("--price-market", choices=("twse", "tpex"), default="twse")
    p.add_argument("--analysis", choices=("none", "lexical", "semantic"), default="none")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--revision")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--threshold", type=float, default=0.65)
    p.add_argument("--max-pairs", type=int, default=2_000_000)
    p.add_argument("--lookback-days", type=int)
    p.add_argument("--max-information-nodes", type=int, default=100, help="Display cap 0..100; research facts are not pruned")
    p.add_argument("--alerts", action="store_true", help="Independent price/volume and revenue reminders; no trading instructions")
    p.add_argument("--alerts-config", type=Path, help="Optional private JSON threshold overrides; requires --alerts")
    args = p.parse_args(argv)
    options = vars(args).copy()
    options["input_file"] = options.pop("input")
    if args.alerts_config:
        if not args.alerts:
            p.error("--alerts-config requires --alerts")
        with guarded(args.alerts_config).open("rb") as f:
            options["alerts_config"] = strict_json(f.read(65537))
        if args.alerts_config.stat().st_size > 65536:
            p.error("alerts config exceeds 64 KiB")
    result = run(**options)
    print("Private research bundle:", args.output_root/result["run"])
    print("Graphs:", result["counts"]["graphs"], "Warnings:", len(result["quality"]["warnings"]), "No publication.")


if __name__ == "__main__":
    main()
