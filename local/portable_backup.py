"""Create, verify and restore a private research archive in a new directory."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import ctypes
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile

from .backup import consistent_copy
from .portable_audit import audit, read_json
from .research import file_digest, guarded
from .research_history import canonical
from .safety import exclusive_lock


VERSION = "private-research-backup-1"
DATABASES = {"ledger.db", "prices.db"}
CLASSES = {"runs": "research_bundle", "raw": "raw", "prices": "price_snapshot",
           "inputs": "normalized_input", "config": "configuration", "events": "event_report"}


def file_class(relative):
    if str(relative) in DATABASES:
        return "database"
    if len(relative.parts) < 2 or relative.parts[0] not in CLASSES:
        raise ValueError("unexpected archive member")
    return CLASSES[relative.parts[0]]


def stat_key(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def scan(bindings):
    """Measure the entire selected source set, including directory membership."""
    entries = {}
    def visit(source, relative):
        info = source.lstat()
        if relative in entries:
            raise ValueError("duplicate portable path")
        entries[relative] = (source, stat_key(info))
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(source.iterdir()):
                visit(child, relative / child.name)
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("portable inputs must be ordinary files or directories without links")

    for source, relative in bindings:
        visit(guarded(source), relative)
    return entries


def journal_state(bindings):
    # SHM contains mutable reader coordination. Database and WAL/journal carry commits.
    state = {}
    for source, relative in bindings:
        if str(relative) not in DATABASES:
            continue
        for suffix in ("-wal", "-journal", "-shm"):
            path = guarded(str(source) + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("invalid SQLite sidecar")
            if suffix != "-shm":
                state[path] = stat_key(info)
    return state


def copy_entries(entries, target, *, online):
    for path, (source, identity) in entries.items():
        dest = target / path
        if stat.S_ISDIR(identity[2]):
            dest.mkdir(mode=0o700, parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if online and str(path) in DATABASES:
            consistent_copy(source, dest)
        else:
            guarded(source)
            with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as fp:
                if stat_key(os.fstat(fp.fileno())) != identity:
                    raise ValueError("source changed before copy")
                with dest.open("xb") as out:
                    shutil.copyfileobj(fp, out, length=1024 * 1024)
        dest.chmod(0o600)


def inventory(root):
    entries = scan([(root, Path("."))])
    directories = sorted(p.as_posix() for p, (_, key) in entries.items() if p.parts and stat.S_ISDIR(key[2]))
    if any(Path(d).parts[0] not in CLASSES for d in directories):
        raise ValueError("unexpected archive directory")
    files = [{"path": p.as_posix(), "class": file_class(p), "bytes": key[4], "sha256": file_digest(source)}
            for p, (source, key) in sorted(entries.items()) if stat.S_ISREG(key[2])]
    return {"files": files, "directories": directories}


def verify_payload(root, manifest):
    members = inventory(root)
    if (set(manifest) != {"schema_version", "files", "directories", "audit"} or manifest["schema_version"] != VERSION
            or any(manifest[key] != value for key, value in members.items())):
        raise ValueError("archive manifest or file checksum mismatch")
    if manifest.get("audit") != audit(root, members["files"]):
        raise ValueError("archive manifest or file checksum mismatch")


def verify(bundle):
    bundle = guarded(bundle)
    if not bundle.is_dir() or {p.name for p in bundle.iterdir()} != {"payload", "manifest.json"}:
        raise ValueError("invalid archive layout")
    manifest_path = guarded(bundle / "manifest.json")
    mode = manifest_path.lstat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
        raise ValueError("invalid archive manifest")
    manifest = read_json(manifest_path)
    verify_payload(guarded(bundle / "payload"), manifest)
    return manifest


def install_new(stage, target):
    """Native no-replace directory rename, even if another writer creates an empty target."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        result = libc.renamex_np(os.fsencode(stage), os.fsencode(target), 4)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        result = libc.renameat2(-100, os.fsencode(stage), -100, os.fsencode(target), 1)  # RENAME_NOREPLACE
    else:
        raise ValueError("exclusive directory rename unavailable")
    if result:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), target)


def new_target(output, sources):
    target = guarded(output)
    if target.exists() or any(target.is_relative_to(source) or source.is_relative_to(target) for source in sources):
        raise ValueError("destination must be new and separate from inputs")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return target


def create(args):
    bindings = [(guarded(args.ledger), Path("ledger.db")), (guarded(args.runs), Path("runs"))]
    if bool(args.prices_db) != bool(args.price_snapshots):
        raise ValueError("price database and original price snapshots must be supplied together")
    if args.prices_db:
        bindings += [(guarded(args.prices_db), Path("prices.db")), (guarded(args.price_snapshots), Path("prices"))]
    for folder, paths in (("raw", args.raw), ("inputs", args.input), ("events", args.event), ("config", args.config)):
        for path in paths:
            if not path.name or ".." in path.parts:
                raise ValueError("invalid source path")
            source = guarded(path)
            if folder in ("inputs", "events", "config") and not source.is_file():
                raise ValueError("input, event and configuration arguments must be files")
            bindings.append((source, Path(folder) / source.name))
    target = new_target(args.output, [source for source, _ in bindings])
    # These are the same resources locked by research, collectors and the price importer.
    resources = {target, *(source for source, _ in bindings if source.is_dir())}
    with ExitStack() as stack:
        for resource in sorted(resources):
            stack.enter_context(exclusive_lock(resource))
        tmp = stack.enter_context(tempfile.TemporaryDirectory(dir=target.parent, prefix=".portable-"))
        stage = Path(tmp) / "archive"
        payload = stage / "payload"
        stage.mkdir(mode=0o700)
        payload.mkdir(mode=0o700)
        initial = scan(bindings)
        journals = journal_state(bindings)
        copy_entries(initial, payload, online=True)
        members = inventory(payload)
        manifest = {"schema_version": VERSION, **members, "audit": audit(payload, members["files"])}
        index = stage / "manifest.json"
        index.write_bytes(canonical(manifest))
        index.chmod(0o600)
        verify(stage)
        if initial != scan(bindings) or journals != journal_state(bindings):
            raise ValueError("source changed during archive creation")
        install_new(stage, target)
    return manifest


def restore(bundle, destination):
    bundle = guarded(bundle)
    target = new_target(destination, [bundle])
    with exclusive_lock(target), tempfile.TemporaryDirectory(dir=target.parent, prefix=".restore-") as tmp:
        manifest = verify(bundle)
        stage = Path(tmp) / "restored"
        entries = scan([(bundle / "payload", Path("."))])
        copy_entries(entries, stage, online=False)
        verify_payload(stage, manifest)
        install_new(stage, target)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create_cmd = commands.add_parser("create")
    for option in ("ledger", "runs", "output"):
        create_cmd.add_argument("--" + option, required=True, type=Path)
    for option in ("prices-db", "price-snapshots"):
        create_cmd.add_argument("--" + option, type=Path)
    for option in ("raw", "input", "event", "config"):
        create_cmd.add_argument("--" + option, action="append", type=Path, default=[], required=option == "input")
    for command in ("verify", "restore"):
        sub = commands.add_parser(command)
        sub.add_argument("--bundle", type=Path, required=True)
        if command == "restore":
            sub.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            manifest = create(args)
        elif args.command == "verify":
            manifest = verify(args.bundle)
        else:
            manifest = restore(args.bundle, args.destination)
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(1, f"{args.command} failed: {exc}\n")
    print(json.dumps({"schema_version": VERSION, "files": len(manifest["files"]), "runs": manifest["audit"]["runs"],
                      "events": manifest["audit"]["events"], "references": len(manifest["audit"]["references"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
