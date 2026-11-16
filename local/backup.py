"""Manual, verified private SQLite backups. Never overwrite a restore target.

SQLite's online backup API captures a consistent database, including committed
WAL data. This does NOT back up raw CSV directories, model weights or credentials.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid

from .core import ROOT
from .collect_official import atomic_bytes
from .research import guarded, file_digest
from .research_history import canonical, strict_json, utc_now
from .safety import exclusive_lock

VERSION = "private-sqlite-backup-1"


def _consistent_copy(source, target):
    with closing(sqlite3.connect(Path(source).as_uri()+"?mode=ro", uri=True)) as src:
        src.execute("PRAGMA trusted_schema=OFF")
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            dst.commit()
            # Produce a standalone file even when the source uses WAL mode.
            # Otherwise a later readonly verification may create WAL/SHM sidecars.
            mode = dst.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            if mode.lower() != "delete":
                raise ValueError("backup could not switch to standalone journal mode")
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("backup SQLite integrity check failed")


def create(database, output_root):
    source, root = guarded(database), guarded(output_root)
    if not source.is_file() or source == root or source.is_relative_to(root):
        raise ValueError("backup input must be a separate existing SQLite file")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with exclusive_lock(root):
        name = uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix=".backup-stage-", dir=root) as temporary:
            stage = Path(temporary)
            target = stage/"database.sqlite"
            _consistent_copy(source, target)
            manifest = {"schema_version": VERSION, "created_at": utc_now(), "sha256": file_digest(target),
                        "bytes": target.stat().st_size, "scope": "SQLite only; raw snapshots require separate backup"}
            atomic_bytes(stage/"manifest.json", canonical(manifest))
            verify(stage)
            stage.rename(root/name)
        return root/name


def verify(bundle):
    root = guarded(bundle)
    if not root.is_dir() or {p.name for p in root.iterdir()} != {"manifest.json", "database.sqlite"}:
        raise ValueError("unexpected or incomplete backup bundle")
    manifest_path = guarded(root/"manifest.json")
    database = guarded(root/"database.sqlite")
    manifest = strict_json(manifest_path.read_bytes())
    if (manifest.get("schema_version") != VERSION or manifest.get("bytes") != database.stat().st_size
            or manifest.get("sha256") != file_digest(database)):
        raise ValueError("backup checksum/size mismatch")
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup SQLite integrity check failed")
    return manifest


def restore(bundle, database):
    root, target = guarded(bundle), guarded(database)
    verify(root)
    if target.exists() or target.is_relative_to(root):
        raise ValueError("restore target must not exist; never overwrite an active database")
    target.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(target):
        # Same-filesystem hard-link installation is atomic and cannot clobber a
        # concurrently created file. No unsafe overwrite fallback on NAS errors.
        with tempfile.TemporaryDirectory(prefix=".restore-stage-", dir=target.parent) as temporary:
            prepared = Path(temporary)/"restore.sqlite"
            _consistent_copy(root/"database.sqlite", prepared)
            os.chmod(prepared, 0o600)
            os.link(prepared, target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create_cmd = commands.add_parser("create")
    create_cmd.add_argument("--db", required=True, type=Path)
    create_cmd.add_argument("--output-root", type=Path, default=ROOT/"local/private/backups")
    verify_cmd = commands.add_parser("verify")
    verify_cmd.add_argument("--bundle", required=True, type=Path)
    restore_cmd = commands.add_parser("restore")
    restore_cmd.add_argument("--bundle", required=True, type=Path)
    restore_cmd.add_argument("--db", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "create":
        print("Private SQLite backup:", create(args.db, args.output_root))
    elif args.command == "verify":
        print("Verified SQLite backup:", verify(args.bundle)["sha256"])
    else:
        print("Restored to new private database:", restore(args.bundle, args.db))


if __name__ == "__main__":
    main()
