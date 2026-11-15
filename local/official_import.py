"""Normalize reviewed official snapshots into a private, TW50-scoped input."""
import argparse
import json
from pathlib import Path
from .core import ROOT
from .universe import load_universe
from .safety import private_path
from .collect_official import atomic_bytes
from .official_adapter import from_snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir",type=Path,default=ROOT/"local/private/official")
    parser.add_argument("--registry",type=Path,default=ROOT/"local/official_datasets.json")
    parser.add_argument("--universe",type=Path,required=True,help="Authorized date-effective TW50 constituent CSV")
    parser.add_argument("--as-of",required=True,help="Universe and snapshot day, YYYY-MM-DD")
    parser.add_argument("--output",type=Path,default=ROOT/"local/private/normalized.json")
    args = parser.parse_args(argv)
    output = private_path(args.output)
    universe = load_universe(args.universe,args.as_of,expected_count=50)
    payload = from_snapshots(args.snapshot_dir,args.registry,universe,as_of=args.as_of)
    atomic_bytes(output,(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode())
    print("Normalized",len(payload["stocks"]),"stocks; private only:",output)


if __name__ == "__main__":
    main()
