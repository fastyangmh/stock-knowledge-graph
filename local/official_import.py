"""Normalize reviewed official snapshots into a private, source-labelled research input."""
import argparse
import json
from pathlib import Path
from .core import ROOT
from .universe import load_universe
from .research_history import validate_symbols
from .combined_universe import load_combined_universe
from .safety import private_path
from .collect_official import atomic_bytes
from .official_adapter import from_snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir",type=Path,default=ROOT/"local/private/official")
    parser.add_argument("--registry",type=Path,default=ROOT/"local/official_datasets.json")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--universe",type=Path,help="Authorized date-effective TW50 constituent CSV")
    selection.add_argument("--symbols",nargs="+",help="Explicit stock codes; do not imply index membership")
    parser.add_argument("--etf-holdings",type=Path,help="Optional same-day 009816 holdings CSV; union with TW50")
    parser.add_argument("--universe-source",help="HTTPS provenance URL for the TW50 membership file")
    parser.add_argument("--as-of",required=True,help="Universe and snapshot day, YYYY-MM-DD")
    parser.add_argument("--output",type=Path,default=ROOT/"local/private/normalized.json")
    parser.add_argument("--unit-evidence",type=Path,help="Private, hash-bound monthly unit review; requires a separate versioned research ledger")
    args = parser.parse_args(argv)
    output = private_path(args.output)
    inputs = (args.registry, args.universe, args.etf_holdings, args.unit_evidence)
    if (output.is_relative_to(args.snapshot_dir.resolve()) or
            any(output == path.resolve() for path in inputs if path is not None)):
        raise ValueError('output must not overwrite an input or unit evidence')
    if args.etf_holdings and not (args.universe and args.universe_source):
        parser.error("--etf-holdings requires --universe and --universe-source")
    combined = (load_combined_universe(args.universe,args.etf_holdings,args.as_of,args.universe_source)
                if args.etf_holdings else None)
    universe = (validate_symbols(args.symbols) if args.symbols else
                (combined.stock_ids if combined else load_universe(args.universe,args.as_of,expected_count=50)))
    payload = from_snapshots(args.snapshot_dir,args.registry,universe,as_of=args.as_of,unit_evidence=args.unit_evidence)
    if args.unit_evidence:
        # Use only references already validated and bound to the raw snapshots.
        references = (reference for row in payload['financial_metrics']
                      for reference in row.get('normalization', {}).get('references', []))
        if any(output == (args.unit_evidence.resolve().parent/reference['path']).resolve()
               for reference in references):
            raise ValueError('output must not overwrite unit evidence references')
    if combined:
        payload = combined.annotate_payload(payload)
    elif args.symbols:
        payload["metadata"]["research_selection"] = {"mode":"explicit_symbols_not_index_membership",
                                                     "stock_ids":sorted(universe)}
    atomic_bytes(output,(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode())
    print("Normalized",len(payload["stocks"]),"stocks; private only:",output)


if __name__ == "__main__":
    main()
