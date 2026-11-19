"""Identify private research dependencies without opening SQLite or following recorded paths."""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .research import ENGINE_VERSION


SHA = re.compile(r"[0-9a-f]{64}")
RUN = re.compile(r"[0-9a-f]{32}")
MAX_JSON = 8 * 1024 * 1024
MAX_REFS = 100_000


def objects(document):
    pending = [document]
    while pending:
        obj = pending.pop()
        if isinstance(obj, list):
            pending.extend(obj)
        elif isinstance(obj, dict):
            yield obj
            pending.extend(value for value in obj.values() if isinstance(value, (list, dict)))


def bundle_requirements(document):
    ids = {"source_id": set(), "dataset_id": set()}
    for obj in objects(document):
        for key in ids:
            if isinstance(obj.get(key), str):
                ids[key].add(obj[key])
    requirements = {k + "s": sorted(v) for k, v in ids.items()}
    config = document.get("configuration")
    analysis = config.get("analysis") if isinstance(config, dict) else None
    if isinstance(analysis, dict) and analysis.get("mode") == "semantic":
        requirements["model"] = {"id": analysis.get("model"), "revision": analysis.get("revision")}
    return requirements


def references(document, owner):
    """Keep distinct hash assertions, with local expected names for known contracts."""
    seen = set()
    for obj in objects(document):
        for field, value in obj.items():
            if field == "path" and isinstance(value, str) and "sha256" not in obj:
                key = (field, None, None, None, value)
                if key not in seen:
                    seen.add(key)
                    yield key
            if field != "sha256" and not field.endswith("_sha256"):
                continue
            expected = declared = None
            run = None
            if field == "report_sha256" and isinstance(obj.get("run"), str):
                run = obj["run"]
                if owner.name == "latest.json" and RUN.fullmatch(run):
                    expected = str(owner.parent / run / "report.json")
            if owner.name == "report.json":
                fixed = {"graph_db_sha256": "graph.db", "manifest_sha256": "data/manifest.json"}
                if field in fixed:
                    expected = str(owner.parent / fixed[field])
            if field == "sha256" and isinstance(obj.get("path"), str):
                if owner.name == "manifest.json" and owner.parent.name == "data":
                    expected = str(owner.parent.parent / obj["path"])
                elif owner.name == "report.json" and obj["path"] in ("research-facts.json", "alerts.json"):
                    expected = str(owner.parent / obj["path"])
                else:
                    declared = obj["path"]
            digest = value if isinstance(value, str) and SHA.fullmatch(value) else None
            key = (field, digest, expected, run, declared)
            if key not in seen:
                seen.add(key)
                yield key


class ArchivePlan:
    def __init__(self, byte_budget):
        self.remaining = byte_budget
        self.hashes = {}
        self.refs = {}
        self.bundles = {}
        self.requirements = {}
        self.uninspected = []
        self.ref_count = 0

    def skip(self, path, reason):
        self.uninspected.append({"path": str(path), "reason": reason})

    def inspect(self, parent_fd, name, path, info):
        if info.st_size > self.remaining:
            self.skip(path, "content_budget")
            return
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(name, flags, dir_fd=parent_fd), "rb") as source:
            def unchanged():
                now = os.fstat(source.fileno())
                return (stat.S_ISREG(now.st_mode) and os.path.samestat(now, info)
                        and now.st_mtime_ns == info.st_mtime_ns and now.st_size == info.st_size)

            if not unchanged():
                self.skip(path, "changed_during_scan")
                return
            digest = hashlib.sha256()
            data = bytearray() if path.suffix.lower() == ".json" and info.st_size <= MAX_JSON else None
            left = info.st_size
            while left:
                chunk = source.read(min(left, 1024 * 1024))
                if not chunk:
                    break
                self.remaining -= len(chunk)
                left -= len(chunk)
                digest.update(chunk)
                if data is not None:
                    data.extend(chunk)
            if left or not unchanged():
                self.skip(path, "changed_during_scan")
                return
        self.hashes[str(path)] = digest.hexdigest()
        if data is None:
            if path.suffix.lower() == ".json":
                self.skip(path, "json_size_budget")
            return
        try:
            document = json.loads(data)
        except (ValueError, RecursionError):
            self.skip(path, "invalid_json")
            return
        if path.name == "report.json" and isinstance(document, dict) and document.get("engine") == ENGINE_VERSION:
            if document.get("run") == path.parent.name and document.get("status") == "complete":
                self.bundles[str(path)] = document["run"]
                self.requirements[str(path)] = bundle_requirements(document)
            else:
                self.skip(path, "unknown_bundle")
        for ref in references(document, path):
            self.ref_count += 1
            if self.ref_count > MAX_REFS:
                raise ValueError("archive reference limit exceeded")
            self.refs.setdefault(str(path), []).append(ref)

    def finish(self):
        wanted = {digest for refs in self.refs.values() for _, digest, _, _, _ in refs if digest}
        content = defaultdict(list)
        reports = defaultdict(list)
        for path, digest in self.hashes.items():
            if digest in wanted:
                content[digest].append(path)
            if path in self.bundles:
                reports[(self.bundles[path], digest)].append(path)
        references_by_owner, incoming = {}, defaultdict(set)
        matched_report_links = 0
        for owner, refs in self.refs.items():
            resolved = []
            for field, digest, expected, run, declared in refs:
                record = {"field": field, "sha256": digest}
                matched = digest in content
                if declared is not None:
                    record["declared_path"] = declared
                if expected is not None:
                    record["expected_path"] = expected
                    matched = digest is not None and self.hashes.get(expected) == digest
                if field == "report_sha256":
                    record["run"] = run
                    targets = reports.get((run, digest), [])
                    if expected is not None:
                        targets = [expected] if expected in targets else []
                    matched = bool(targets)
                    matched_report_links += len(targets)
                    if matched_report_links > MAX_REFS:
                        raise ValueError("archive link limit exceeded")
                    for target in targets:
                        incoming[target].add(owner)
                record["status"] = "matched_bytes" if matched else "unresolved"
                resolved.append(record)
            references_by_owner[owner] = resolved
        return {"mode": "dry_run", "originals": "retain_all",
                "bundle_copies": [{"directory": str(Path(p).parent), "report": p,
                                   "referenced_by": sorted(incoming[p])} for p in sorted(self.bundles)],
                "bundle_requirements": self.requirements,
                "references": references_by_owner, "content_paths": dict(content),
                "uninspected": self.uninspected}
