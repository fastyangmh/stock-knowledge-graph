"""Local after-close release: validate generated JSON, commit only data/, push.

Run only after a successful local ingestion and embedding pipeline.
Does not fetch real market data and never commits the SQLite database.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path
from .core import ROOT
from .validate_release import validate_release

def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,text=True,capture_output=True).stdout.strip()

def publish(dry_run=False):
    validate_release(ROOT)
    if git("branch","--show-current")!="main":
        raise RuntimeError("Publishing requires local main branch")
    if git("status","--porcelain","--untracked-files=normal").strip():
        # Allow only generated data/ changes; do not auto-commit unrelated work.
        status=git("status","--porcelain","--untracked-files=normal").splitlines()
        if any(not line[3:].strip('"').startswith("data/") for line in status):
            raise RuntimeError("Unrelated local changes detected; aborting publication")
    git("fetch","origin","main")
    if git("rev-parse","HEAD")!=git("rev-parse","origin/main"):
        raise RuntimeError("Local main differs from origin/main; sync before publishing")
    git("add","-A","--","data/")
    staged=git("diff","--cached","--name-only")
    if not staged:
        return "No changed JSON to publish"
    if any(not line.startswith("data/") for line in staged.splitlines()):
        raise RuntimeError("Unexpected staged files; abort")
    if dry_run:
        return "Dry run: validated; staged files:\n"+staged
    git("commit","-m","data: publish validated stock graphs")
    git("push","origin","main")
    return "Published validated data to main"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    print(publish(args.dry_run))

if __name__=="__main__":
    main()
