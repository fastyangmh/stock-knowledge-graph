"""Manually publish validated data only. Never runs from the after-close runner."""
import argparse
import re
import subprocess
from pathlib import Path
from .core import ROOT
from .safety import exclusive_lock
from .validate_release import validate_release


def git(*args, root=ROOT):
    # Do not strip porcelain output: its leading status column is significant.
    return subprocess.run(["git",*args],cwd=root,check=True,text=True,capture_output=True).stdout


def _allowed(path):
    return path=="data/manifest.json" or re.fullmatch(r"data/stocks/[A-Za-z0-9_.-]+/graph\.json",path) is not None


def publish(dry_run=False, *, root=ROOT):
    root = Path(root).resolve()
    with exclusive_lock(root/"data"):
        validate_release(root)
        if git("branch","--show-current",root=root).strip() != "main":
            raise RuntimeError("Publishing requires local main branch")
        if git("diff","--cached","--name-only","-z",root=root):
            raise RuntimeError("Pre-staged changes detected; leave your index untouched and review them first")
        candidates = []
        for entry in git("status","--porcelain=v1","-z","--untracked-files=all",root=root).split("\0"):
            if not entry:
                continue
            if len(entry)<4 or "R" in entry[:2] or "C" in entry[:2] or not _allowed(entry[3:]):
                raise RuntimeError("Unrelated/renamed local changes detected; publication aborted")
            candidates.append(entry[3:])
        git("fetch","origin","main",root=root)
        if git("rev-parse","HEAD",root=root).strip()!=git("rev-parse","origin/main",root=root).strip():
            raise RuntimeError("Local main differs from origin/main; reconcile without force-pushing")
        if not candidates:
            return "No changed JSON to publish"
        if dry_run:
            return "Dry run; index and working files unchanged:\n"+"\n".join(sorted(candidates))
        git("add","-A","--","data/",root=root)
        staged = [p for p in git("diff","--cached","--name-only","-z",root=root).split("\0") if p]
        if not staged or any(not _allowed(p) for p in staged):
            raise RuntimeError("Unexpected index contents; inspect manually before committing")
        git("commit","-m","data: publish validated stock graphs",root=root)
        try:
            git("push","origin","main",root=root)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Push failed. Local data commit retained; inspect it before a manual retry") from exc
        return "Published validated data to main"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    print(publish(args.dry_run))


if __name__=="__main__":
    main()
