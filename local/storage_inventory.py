"""Read-only private storage accounting and archive planning."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .research import guarded
from .storage_references import ArchivePlan, RUN


SCHEMA = "private-storage-inventory-v1"
CATEGORIES = ("database", "raw", "bundle", "backup", "model", "unknown")
DIRECTORIES = {
    "backups": "backup", "backup": "backup", "runs": "bundle", "research-runs": "bundle",
    "raw": "raw", "official": "raw", "market-prices": "raw", "prices": "raw",
    "models": "model", "model-cache": "model", "huggingface": "model",
}
DB_FILE = re.compile(r".*\.(?:db|sqlite|sqlite3)(?:-wal|-shm|-journal)?$", re.I)
DIR_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
MAX_ENTRIES = 100_000
MAX_DEPTH = 128
MAX_REPORT_BYTES = 64 * 1024 * 1024


def category(path, classes, root):
    for prefix in (path, *path.parents):
        if prefix.as_posix() in classes:
            return classes[prefix.as_posix()]
    if RUN.fullmatch(root.name) and DIRECTORIES.get(root.parent.name) == "bundle":
        return "bundle"
    for part in (root.name, *path.parts[:-1]):
        if part in DIRECTORIES:
            return DIRECTORIES[part]
    if DB_FILE.fullmatch(path.name):
        return "database"
    return "unknown"


def settings(options, *, budgets=False):
    result = {}
    allowed = (*CATEGORIES, "total") if budgets else CATEGORIES
    for setting in options:
        name, sep, value = setting.partition("=")
        if not sep or name not in allowed:
            raise ValueError(f"invalid setting: {setting}")
        if budgets:
            if name in result or not value.isascii() or not value.isdigit():
                raise ValueError(f"invalid byte budget: {setting}")
            result[name] = int(value)
        else:
            prefix = Path(value)
            if not value or prefix.is_absolute() or ".." in prefix.parts or str(prefix) in result:
                raise ValueError(f"invalid or duplicated classification path: {setting}")
            result[str(prefix)] = name
    return result


def inventory(root, classes, budgets, content_budget):
    started = datetime.now(timezone.utc).isoformat()
    plan = ArchivePlan(content_budget, root.name)
    files, errors, inodes = [], [], {}
    counts = Counter(dict.fromkeys(CATEGORIES, 0))
    visited = 0

    def walk(fd, directory):
        nonlocal visited
        if len(directory.parts) > MAX_DEPTH:
            raise ValueError("scan depth limit exceeded")
        names = []
        with os.scandir(fd) as listing:
            for item in listing:
                visited += 1
                if visited > MAX_ENTRIES:
                    raise ValueError("scan entry limit exceeded")
                names.append(item.name)
        for name in sorted(names):
            path = directory / name
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, DIR_FLAGS, dir_fd=fd)
                    try:
                        walk(child, path)
                    finally:
                        os.close(child)
                    continue
                group = category(path, classes, root)
                row = {"path": str(path), "category": group, "counted_bytes": 0}
                files.append(row)
                if stat.S_ISREG(info.st_mode):
                    key = (info.st_dev, info.st_ino)
                    row.update(type="file", size_bytes=info.st_size)
                    if key in inodes:
                        row["same_file_as"] = inodes[key]
                    else:
                        inodes[key] = str(path)
                        row["counted_bytes"] = info.st_size
                        counts[group] += info.st_size
                    plan.inspect(fd, name, path, info)
                else:
                    row["type"] = "symlink" if stat.S_ISLNK(info.st_mode) else "special"
                    plan.skip(path, row["type"])
            except OSError as exc:
                errors.append({"path": str(path), "errno": exc.errno, "reason": exc.strerror})

    fd = os.open(root, DIR_FLAGS)
    try:
        root_stat = os.fstat(fd)
        walk(fd, Path("."))
    finally:
        os.close(fd)
    total = sum(counts.values())
    exceeded = []
    for group, limit in sorted(budgets.items()):
        amount = total if group == "total" else counts[group]
        if amount > limit:
            exceeded.append({"category": group, "limit_bytes": limit, "observed_bytes": amount,
                             "excess_bytes": amount - limit, "paths": [
                                 row["path"] for row in files if row["counted_bytes"] and
                                 (group == "total" or row["category"] == group)]})
    return {"schema_version": SCHEMA, "root": str(root), "root_id": [root_stat.st_dev, root_stat.st_ino],
            "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
            "class_overrides": classes, "budgets": budgets, "files": files,
            "bytes_by_category": dict(counts), "total_bytes": total, "budget_exceeded": exceeded,
            "archive_plan": plan.finish(), "content_budget": content_budget,
            "scan_errors": errors, "size_complete": not errors}


def growth(report, previous_path):
    with previous_path.open("rb") as stream:
        body = stream.read(MAX_REPORT_BYTES + 1)
    if len(body) > MAX_REPORT_BYTES:
        raise ValueError("previous inventory exceeds report budget")
    earlier = json.loads(body)
    keys = ("schema_version", "root", "root_id", "class_overrides")
    if not isinstance(earlier, dict) or any(earlier.get(key) != report[key] for key in keys):
        raise ValueError("previous inventory root, schema or classification differs")
    old = {row["path"]: row for row in earlier["files"]}
    new = {row["path"]: row for row in report["files"]}
    missed_before = {e["path"] for e in earlier["scan_errors"]}
    missed_after = {e["path"] for e in report["scan_errors"]}
    complete = earlier["size_complete"] and report["size_complete"]
    changes = []
    for path in sorted(old.keys() | new.keys()):
        a, b = old.get(path, {}), new.get(path, {})
        fields = ("type", "size_bytes", "counted_bytes", "same_file_as")
        if all(a.get(k) == b.get(k) for k in fields):
            continue
        missing = missed_before if not a else missed_after if not b else set()
        if missing and any(str(prefix) in missing for prefix in (Path(path), *Path(path).parents)):
            changes.append({"path": path, "change": "unobserved", "size_delta_bytes": None,
                            "counted_delta_bytes": None})
            continue
        changes.append({"path": path, "change": "added" if not a else "removed" if not b else "changed",
                        "size_delta_bytes": b.get("size_bytes", 0) - a.get("size_bytes", 0),
                        "counted_delta_bytes": b.get("counted_bytes", 0) - a.get("counted_bytes", 0)})
    return {"previous_finished_at": earlier["finished_at"], "sizes_complete": complete, "files": changes,
            "total_delta_bytes": report["total_bytes"] - earlier["total_bytes"] if complete else None,
            "delta_by_category": {k: report["bytes_by_category"][k] - earlier["bytes_by_category"][k]
                                  for k in CATEGORIES} if complete else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--class", dest="classes", metavar="CATEGORY=RELATIVE_PATH", action="append", default=[])
    parser.add_argument("--content-budget", type=int, default=256 * 1024 * 1024,
                        help="maximum total bytes read for hashes and JSON references")
    parser.add_argument("--previous", help="previous inventory of the same root and classes")
    parser.add_argument("--budget", metavar="CATEGORY=BYTES", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        root, output = guarded(args.root), guarded(args.output)
        if output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError("inventory output must be outside the scanned root")
        if args.content_budget < 0:
            raise ValueError("content budget must be nonnegative")
        report = inventory(root, settings(args.classes), settings(args.budget, budgets=True), args.content_budget)
        if args.previous:
            previous = guarded(args.previous)
            if not previous.is_file() or previous.is_relative_to(root):
                raise ValueError("previous inventory must be a file outside the scan")
            report["growth"] = growth(report, previous)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, mode="w", encoding="utf-8") as temp:
            written = 0
            encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, sort_keys=True)
            for part in encoder.iterencode(report):
                written += len(part)
                if written > MAX_REPORT_BYTES:
                    raise ValueError("inventory exceeds report budget")
                temp.write(part)
            temp.flush()
            os.fsync(temp.fileno())
            os.link(temp.name, output)
        return 0 if report["size_complete"] else 2
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        parser.exit(2, f"storage inventory: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
