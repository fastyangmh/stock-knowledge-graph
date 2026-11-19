"""Read-only validation of private research bundles and bounded catalog discovery.

Hashes establish internal consistency, not authenticity, source rights or market
truth. Only the latest report has a pointer hash anchor; older reports are not
signed. No source download, database SQL execution, repair, deletion or Git IO.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import tempfile

from .alerts import validate as validate_alert, policy
from .dates import timestamp
from .research_history import canonical, strict_json, MAX_INPUT_BYTES
from .research import ENGINE_VERSION, guarded
from .validate_release import validate_data_dir

VERSION = "research-catalog-1.0"
MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_FILES = 2000
RUN = re.compile(r"[0-9a-f]{32}")
SHA = re.compile(r"[0-9a-f]{64}")


class AuditError(ValueError):
    """A stable, safe error code (no private file contents/paths in HTTP output)."""


@dataclass
class Bundle:
    report: dict
    report_sha256: str
    manifest: dict
    graphs: dict[str, dict]
    data_files: dict[str, bytes]
    alerts: dict | None
    size_bytes: int
    anchored: bool
    facts: dict | None = None

    def summary(self):
        return {"run": self.report["run"], "status": "valid",
                "known_at": self.report["known_at"], "completed_at": self.report["completed_at"],
                "stock_ids": self.report["selection"]["stock_ids"],
                "counts": self.report["counts"], "size_bytes": self.size_bytes,
                "report_sha256": self.report_sha256, "latest_pointer_anchored": self.anchored,
                "warnings": self.report["quality"]["warnings"],
                "analysis_mode": self.report.get("configuration", {}).get("analysis", {}).get("mode", self.report["analysis"].get("mode", "unknown")),
                "alerts_enabled": self.alerts is not None,
                "fact_scope": "unpruned_facts" if self.facts is not None else "display_graph_only",
                "triggered_by_category": self.report.get("research_alerts", {}).get("triggered_by_category", {})}


def _require(condition, code):
    if not condition:
        raise AuditError(code)


def _hash(body):
    return hashlib.sha256(body).hexdigest()


def audit_bundle(root, run_id, *, expected_report_sha=None, max_bytes=MAX_BUNDLE_BYTES):
    """Validate a captured bundle. SQLite is hashed as bytes, never opened as SQL."""
    _require(isinstance(run_id, str) and RUN.fullmatch(run_id), "invalid_run_id")
    _require(type(max_bytes) is int and max_bytes > 0, "invalid_size_budget")
    root = guarded(root)
    bundle = guarded(root/run_id)
    _require(bundle.is_dir(), "bundle_not_found")
    expected = {"report.json", "graph.db", "data/manifest.json"}
    count, total, found = 0, 0, set()
    for path in bundle.rglob("*"):
        count += 1
        _require(count <= MAX_FILES, "too_many_bundle_entries")
        _require(not path.is_symlink(), "bundle_symlink")
        if path.is_file():
            relative = path.relative_to(bundle).as_posix()
            _require(relative in expected or relative in ("alerts.json", "research-facts.json") or
                     re.fullmatch(r"revisions/[a-f0-9]{64}\.json", relative) or
                     re.fullmatch(r"data/stocks/[A-Za-z0-9_.-]+/graph\.json", relative), "unexpected_bundle_file")
            if relative != "graph.db":
                _require(path.stat().st_size <= MAX_INPUT_BYTES, "json_size_budget_exceeded")
            total += path.stat().st_size
            _require(total <= max_bytes, "bundle_size_budget_exceeded")
            found.add(relative)
        else:
            _require(path.is_dir(), "non_regular_bundle_entry")
    _require(expected.issubset(found), "incomplete_bundle")
    captured, digests, read_bytes = {}, {}, 0
    for relative in sorted(found):
        path = bundle/relative
        _require(not path.is_symlink(), "bundle_symlink")
        before = path.stat()
        digest, parts, file_bytes = hashlib.sha256(), [], 0
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024*1024), b""):
                read_bytes += len(part)
                file_bytes += len(part)
                _require(read_bytes <= max_bytes, "bundle_size_budget_exceeded")
                digest.update(part)
                if relative != "graph.db":
                    _require(file_bytes <= MAX_INPUT_BYTES, "json_size_budget_exceeded")
                    parts.append(part)
        after = path.stat()
        _require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                 (after.st_ino, after.st_size, after.st_mtime_ns), "file_changed_during_audit")
        digests[relative] = digest.hexdigest()
        if relative != "graph.db":
            captured[relative] = b"".join(parts)
    report = strict_json(captured["report.json"])
    _require(report.get("engine") == ENGINE_VERSION and report.get("status") == "complete" and
             report.get("run") == run_id and report.get("public_publish") is False, "invalid_bundle_report")
    cutoff = timestamp(report["known_at"])
    _require(cutoff <= timestamp(report["completed_at"]), "future_knowledge_cutoff")
    _require(report.get("graph_db_sha256") == digests["graph.db"], "database_checksum_mismatch")
    _require(report.get("manifest_sha256") == digests["data/manifest.json"], "manifest_checksum_mismatch")
    if expected_report_sha is not None:
        _require(isinstance(expected_report_sha, str) and SHA.fullmatch(expected_report_sha) and
                 expected_report_sha == digests["report.json"], "report_pointer_checksum_mismatch")
    selection = report.get("selection", {})
    stock_ids = selection.get("stock_ids")
    _require(isinstance(stock_ids, list) and stock_ids and len(stock_ids) <= 500 and
             all(isinstance(s, str) and re.fullmatch(r"TW:[0-9]{4}", s) for s in stock_ids) and
             stock_ids == sorted(set(stock_ids)), "invalid_bundle_selection")
    warnings = report.get("quality", {}).get("warnings")
    _require(isinstance(warnings, list) and all(isinstance(s, str) for s in warnings), "invalid_quality_warnings")
    _require(isinstance(report.get("analysis"), dict), "invalid_analysis_metadata")
    data_files = {name: body for name, body in captured.items() if name.startswith("data/")}
    # Reuse the exact release validator on the captured bytes, not a second read
    # of files that an uncooperative writer may have replaced in the meantime.
    with tempfile.TemporaryDirectory(prefix="stock-bundle-audit-") as temporary:
        base = Path(temporary)
        for relative, body in data_files.items():
            target = base/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        validate_data_dir(base/"data")
    manifest = strict_json(captured["data/manifest.json"])
    graphs = {}
    for entry in manifest["stocks"]:
        _require(isinstance(entry.get("sha256"), str) and SHA.fullmatch(entry["sha256"]), "missing_graph_checksum")
        graph = strict_json(captured[entry["path"]])
        sid = graph["stock_id"]
        _require(sid not in graphs and entry.get("stock_id") == sid, "duplicate_or_mismatched_stock")
        graphs[sid] = graph
    _require(set(graphs) == set(stock_ids) and report.get("counts", {}).get("graphs") == len(graphs), "bundle_coverage_mismatch")
    _require(set(data_files) ==
             {"data/manifest.json"} | {s["path"] for s in manifest["stocks"]}, "unlisted_bundle_graph")
    alert_index = report.get("research_alerts")
    alerts = None
    if alert_index is not None:
        _require(isinstance(alert_index, dict) and alert_index.get("enabled") is True and
                 alert_index.get("combined_score") is False and alert_index.get("path") == "alerts.json", "invalid_alert_report")
        _require("alerts.json" in captured and digests["alerts.json"] == alert_index.get("sha256"), "alert_checksum_mismatch")
        alerts = strict_json(captured["alerts.json"])
        _require(alerts.get("schema_version") == "research-alerts-1.0" and
                 isinstance(alerts.get("stocks"), dict) and set(alerts["stocks"]) == set(stock_ids), "alert_coverage_mismatch")
        config = policy(alert_index["config"])
        triggered = {"price_volume": 0, "monthly_revenue": 0}
        for sid, alert in alerts["stocks"].items():
            validate_alert(alert, sid)
            _require(timestamp(alert["known_at"]) == cutoff and policy(alert["config"]) == config, "alert_context_mismatch")
            _require(graphs[sid].get("research_alerts") == alert, "graph_alert_mismatch")
            for category, checks in alert["categories"].items():
                triggered[category] += sum(c["status"] == "triggered" for c in checks)
        _require(triggered == alert_index.get("triggered_by_category"), "alert_summary_mismatch")
    else:
        _require("alerts.json" not in captured and all("research_alerts" not in g for g in graphs.values()), "unlisted_alerts")
    facts = None
    if "research_facts" in report:
        index = report["research_facts"]
        _require(isinstance(index, dict), "invalid_facts_index")
        _require("research-facts.json" in captured and index.get("path") == "research-facts.json" and
                 digests.get("research-facts.json") == index.get("sha256"), "facts_checksum_mismatch")
        _require(type(index.get("size_bytes")) is int and index["size_bytes"] == len(captured["research-facts.json"]), "facts_size_mismatch")
        facts = strict_json(captured["research-facts.json"])
        from .research_facts import validate_facts
        snapshots = report['quality']['snapshots']
        paths = {s['revision_path'] for s in snapshots if 'revision_path' in s}
        _require(paths == {p for p in captured if p.startswith('revisions/')}, 'revision_file_set_mismatch')
        archived = []
        for snapshot in snapshots:
            if 'revision_path' in snapshot:
                path = snapshot['revision_path']
                sha = snapshot['sha256']
                _require('revision_payload' not in snapshot and path == f'revisions/{sha}.json'
                         and digests[path] == sha, 'revision_file_mismatch')
                snapshot = {**snapshot, 'revision_payload': strict_json(captured[path])}
            archived.append(snapshot)
        validate_facts(facts, report, archived_snapshots=archived, graphs=graphs)
    else:
        _require("research-facts.json" not in captured, "unlisted_facts")
        _require(not any(p.startswith('revisions/') for p in captured) and
                 not report.get('quality', {}).get('source_revisions') and
                 not any('revision_payload' in s or 'revision_path' in s
                         for s in report['quality'].get('snapshots', [])), 'revision_facts_missing')
    return Bundle(report, digests["report.json"], manifest, graphs, data_files,
                  alerts, read_bytes, expected_report_sha is not None, facts)


def catalog(root, *, max_runs=50, max_bytes=MAX_BUNDLE_BYTES):
    """Return summaries and the validated in-memory bundles; corrupt runs stay disabled."""
    _require(type(max_runs) is int and 1 <= max_runs <= 500, "invalid_run_budget")
    _require(type(max_bytes) is int and max_bytes > 0, "invalid_size_budget")
    root = guarded(root)
    _require(root.is_dir(), "research_root_not_found")
    entries = []
    leftovers = 0
    root_entries = 0
    for path in root.iterdir():
        root_entries += 1
        _require(root_entries <= max_runs + 100, "too_many_root_entries")
        if RUN.fullmatch(path.name):
            entries.append(path.name)
            _require(len(entries) <= max_runs, "run_budget_exceeded")
        elif path.name.startswith(".research-stage-"):
            leftovers += 1
        elif path.name != "latest.json":
            raise AuditError("unexpected_research_root_entry")
    _require(bool(entries), "no_research_runs")
    # Count invalid bundles too: repeated bad files may not evade the total budget.
    disk_budget = 0
    for name in entries:
        directory = root/name
        if directory.is_symlink() or not directory.is_dir():
            continue
        visited = 0
        for path in directory.rglob("*"):
            visited += 1
            _require(visited <= MAX_FILES, "too_many_bundle_entries")
            if not path.is_symlink() and path.is_file():
                disk_budget += path.stat().st_size
                _require(disk_budget <= max_bytes, "catalog_size_budget_exceeded")
    pointer = None
    if (root/"latest.json").exists() or (root/"latest.json").is_symlink():
        path = root/"latest.json"
        _require(not path.is_symlink() and path.stat().st_size <= 65536, "invalid_latest_pointer")
        pointer = strict_json(path.read_bytes())
        _require(pointer.get("engine") == ENGINE_VERSION and pointer.get("run") in entries and
                 isinstance(pointer.get("report_sha256"), str) and SHA.fullmatch(pointer["report_sha256"]), "invalid_latest_pointer")
    valid, rows, used = {}, [], 0
    # max_bytes applies to the WHOLE catalog, not separately to every run.
    for name in sorted(entries):
        try:
            bundle = audit_bundle(root, name, expected_report_sha=pointer["report_sha256"]
                                  if pointer and pointer["run"] == name else None, max_bytes=max_bytes-used)
            used += bundle.size_bytes
            valid[name] = bundle
            rows.append(bundle.summary())
        except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
            code = str(exc) if isinstance(exc, AuditError) else "invalid_bundle_content"
            if code in ("invalid_size_budget", "bundle_size_budget_exceeded"):
                raise AuditError("catalog_size_budget_exceeded") from exc
            rows.append({"run": name, "status": "invalid", "error": code})
    rows.sort(key=lambda row: (timestamp(row["known_at"]).isoformat() if row.get("known_at") else "",
                               timestamp(row["completed_at"]).isoformat() if row.get("completed_at") else "", row["run"]))
    return {"schema_version": VERSION, "latest": pointer["run"] if pointer else None,
            "latest_valid": bool(pointer and pointer["run"] in valid), "runs": rows,
            "counts": {"valid": len(valid), "invalid": len(rows)-len(valid), "staging_residues": leftovers},
            "validated_bytes": used, "no_automatic_cleanup": True,
            "scope": "local saved research versions, not signed evidence or a complete market history"}, valid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--max-runs", type=int, default=50)
    parser.add_argument("--max-mib", type=int, default=256)
    args = parser.parse_args(argv)
    _require(1 <= args.max_mib <= 4096, "invalid_size_budget")
    summary, _ = catalog(args.root, max_runs=args.max_runs, max_bytes=args.max_mib*1024*1024)
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if summary["counts"]["invalid"] or not summary["latest_valid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
