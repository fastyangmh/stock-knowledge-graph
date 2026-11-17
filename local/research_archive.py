"""Bounded, read-only localhost history viewer for audited research bundles.

Serves graphs/safe summaries only. No SQLite, source files, report internals,
filesystem listing, cleanup, publish, execution or remote binding is available.
All comparisons use captured and validated bytes; restart to see new versions.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import parse_qs

from .bundle_audit import catalog, _require, RUN, MAX_FILES
from .core import ROOT
from .research import guarded
from .preview import ASSETS, server_from_files
from .research_compare import compare
from .research_history import canonical

MAX_PREVIEW_BYTES = 64 * 1024 * 1024
HISTORY_ASSETS = {"history.html": "text/html; charset=utf-8",
                  "js/history-utils.js": "text/javascript; charset=utf-8",
                  "js/history.js": "text/javascript; charset=utf-8"}


def archive_snapshot(directory, *, root=ROOT, max_runs=50, max_mib=256, max_preview_bytes=MAX_PREVIEW_BYTES):
    _require(type(max_mib) is int and 1 <= max_mib <= 4096, "invalid_disk_budget")
    _require(type(max_preview_bytes) is int and max_preview_bytes > 0, "invalid_preview_budget")
    # Bound the served graph corpus before parsing. Unserved facts/reports remain
    # subject to the catalog total budget and per-JSON parser limit; they are not
    # part of the HTTP preview budget. Neither limit guarantees peak Python heap.
    directory = guarded(directory)
    _require(type(max_runs) is int and 1 <= max_runs <= 500, "invalid_run_budget")
    json_bytes, entries = 0, 0
    for run in directory.iterdir():
        entries += 1
        _require(entries <= max_runs + 100, "too_many_root_entries")
        if not RUN.fullmatch(run.name) or run.is_symlink() or not run.is_dir():
            continue
        count = 0
        for path in run.rglob("*"):
            count += 1
            _require(count <= MAX_FILES, "too_many_bundle_entries")
            if not path.is_symlink() and path.is_file() and path.suffix == ".json" and path.is_relative_to(run/"data"):
                json_bytes += path.stat().st_size
                _require(json_bytes <= max_preview_bytes, "history_preview_size_budget_exceeded")
    summary, bundles = catalog(directory, max_runs=max_runs, max_bytes=max_mib*1024*1024)
    files, used = {}, 0
    def add(name, body, mime):
        nonlocal used
        used += len(body)
        _require(used <= max_preview_bytes, "history_preview_size_budget_exceeded")
        files[name] = (body, mime)
    for name, bundle in bundles.items():
        for relative, body in bundle.data_files.items():
            add("/versions/"+name+"/"+relative, body, "application/json; charset=utf-8")
    root = Path(root).resolve()
    for name, mime in (ASSETS | HISTORY_ASSETS).items():
        path = root/name
        _require(not path.is_symlink() and path.resolve().is_relative_to(root), "unsafe_history_asset")
        _require(path.stat().st_size <= max_preview_bytes-used, "history_preview_size_budget_exceeded")
        add("/"+name, path.read_bytes(), mime)
    add("/research-history.json", canonical(summary), "application/json; charset=utf-8")
    files["/"] = files["/history.html"]
    # The default graph viewer is available only when an intact latest pointer exists.
    if summary["latest_valid"]:
        for relative, body in bundles[summary["latest"]].data_files.items():
            files["/"+relative] = (body, "application/json; charset=utf-8")
    return files, bundles


def make_server(directory, *, port=8766, root=ROOT, max_runs=50, max_mib=256):
    files, bundles = archive_snapshot(directory, root=root, max_runs=max_runs, max_mib=max_mib)
    def resolve(parsed):
        if parsed.path != "/api/compare":
            return None
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
        if set(query) != {"before", "after"} or any(len(values) != 1 for values in query.values()):
            raise ValueError("exactly before and after are required")
        before, after = query["before"][0], query["after"][0]
        if before not in bundles or after not in bundles:
            raise ValueError("only captured valid run IDs are allowed")
        return canonical(compare(bundles[before], bundles[after])), "application/json; charset=utf-8"
    return server_from_files(files, port=port, resolver=resolve)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT/"local/private/research-runs")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--max-runs", type=int, default=50)
    parser.add_argument("--max-mib", type=int, default=256)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be 1..65535")
    with make_server(args.root, port=args.port, max_runs=args.max_runs, max_mib=args.max_mib) as server:
        print(f"Read-only research history: http://127.0.0.1:{server.server_port}/", flush=True)
        print("Only local users can access; no authentication. No cleanup/publish. Restart to refresh.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
