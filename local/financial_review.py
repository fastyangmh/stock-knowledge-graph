"""Offline, side-by-side financial fact review against a separately prepared input.

Both files are normalized snapshots, not proof of an official audit. No provider
is automatically 'truth'. Different unit/scope/period definitions block numeric
comparison; no currency conversion, scale guessing, source selection or edits.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path

from .collect_official import atomic_bytes
from .research import guarded
from .research_history import canonical, strict_json, validate_payload, validate_symbols, MAX_INPUT_BYTES

VERSION = "financial-review-1.0"
MAX_ROWS = 20000
UNKNOWN_UNITS = {None, "", "source_reported", "unknown", "unspecified"}
KEYS = ("stock_id", "metric", "period_end", "period_type")


def tolerance(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)) or len(str(value)) > 128:
        raise ValueError("tolerance must be a bounded nonnegative decimal")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid tolerance") from exc
    if not result.is_finite() or result < 0 or result > Decimal('1000000'):
        raise ValueError("invalid tolerance")
    return result


def _reference(row, sources):
    if row is None:
        return None
    return {**{key: row.get(key) for key in (*KEYS, "value", "unit", "source_id", "available_at", "registered_at",
                                          "statement_scope", "report_basis", "currency")},
            "source_url": sources.get(row["source_id"], {}).get("url")}


def review(left, right, symbols, *, absolute_tolerance="0", relative_tolerance="0", max_rows=MAX_ROWS):
    selected = validate_symbols(symbols)
    validate_payload(left); validate_payload(right)
    atol, rtol = tolerance(absolute_tolerance), tolerance(relative_tolerance)
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError("invalid financial review row budget")
    sources = [{row["source_id"]: row for row in data.get("sources", [])} for data in (left, right)]
    indexes = [defaultdict(list), defaultdict(list)]
    for data, index in zip((left, right), indexes):
        for row in data.get("financial_metrics", []):
            if row["stock_id"] in selected:
                index[tuple(row[k] for k in KEYS)].append(row)
                if len(index) > max_rows:
                    raise ValueError("financial review row budget exceeded")
    keys = sorted(set(indexes[0]) | set(indexes[1]))
    if len(keys) > max_rows:
        raise ValueError("financial review row budget exceeded")
    output = []
    for key in keys:
        a, b = indexes[0].get(key, []), indexes[1].get(key, [])
        row = {**dict(zip(KEYS, key)), "status": "equal", "difference": None, "allowed_difference": None,
               "input": [_reference(r, sources[0]) for r in a], "reference": [_reference(r, sources[1]) for r in b]}
        if not a:
            row["status"] = "missing_input"
        elif not b:
            row["status"] = "missing_reference"
        elif len(a) != 1 or len(b) != 1:
            row["status"] = "ambiguous_sources"
        else:
            first, second = a[0], b[0]
            if any(value is not None and not isinstance(value, str) for value in (first.get("unit"), second.get("unit"))):
                raise ValueError("financial unit must be text or null")
            if first.get("unit") in UNKNOWN_UNITS or second.get("unit") in UNKNOWN_UNITS:
                row["status"] = "unit_unverified"
            elif first.get("unit") != second.get("unit") or first.get("currency") != second.get("currency"):
                row["status"] = "unit_or_currency_mismatch"
            elif key[3] not in ("month", "quarter", "year", "annual"):
                row["status"] = "statement_definition_unverified"
            elif key[3] in ("quarter", "year", "annual") and (
                    first.get("statement_scope") not in ("consolidated", "separate") or
                    second.get("statement_scope") not in ("consolidated", "separate") or
                    first.get("report_basis") not in ("single_period", "cumulative", "point_in_time") or
                    second.get("report_basis") not in ("single_period", "cumulative", "point_in_time")):
                row["status"] = "statement_definition_unverified"
            elif any(first.get(k) != second.get(k) for k in ("statement_scope", "report_basis")):
                row["status"] = "statement_definition_mismatch"
            else:
                x, y = Decimal(str(first["value"])), Decimal(str(second["value"]))
                with localcontext() as context:
                    context.prec = max(100, len(format(x, "f")) + len(format(y, "f")) + 64)
                    delta = x-y
                    allowed = max(atol, rtol*max(abs(x), abs(y)))
                row.update(difference=format(delta, "f"), allowed_difference=format(allowed, "f"),
                           status="equal" if delta == 0 else "within_tolerance" if abs(delta) <= allowed else "value_mismatch")
        output.append(row)
    covered = {key[0] for key in keys}
    missing = sorted(selected-covered)
    counts = dict(sorted(Counter(row["status"] for row in output).items()))
    result = {"schema_version": VERSION, "stock_ids": sorted(selected), "rows": output,
              "counts": counts, "stocks_without_financial_records": missing,
              "needs_review": bool(missing) or any(row["status"] not in ("equal", "within_tolerance") for row in output),
              "tolerances": {"absolute": format(atol, "f"), "relative_fraction": format(rtol, "f"),
                             "formula": "abs(input-reference) <= max(absolute, relative * max(abs(input), abs(reference)))"},
              "input_normalized_sha256": hashlib.sha256(canonical(left)).hexdigest(),
              "reference_normalized_sha256": hashlib.sha256(canonical(right)).hexdigest(),
              "scope": "offline_numeric_reconciliation_not_provider_authenticity_financial_audit_or_return_analysis",
              "notes": ["no_automatic_truth_source_or_overwrite", "unknown_unit_scale_is_not_comparable_even_when_numbers_equal",
                        "quarterly_cumulative_and_single_period_values_must_not_be_mixed",
                        "snapshot_comparison_does_not_reconstruct_unobserved_historical_revisions"]}
    result["review_id"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--symbols',nargs='+',required=True)
    p.add_argument('--absolute-tolerance',default='0')
    p.add_argument('--relative-tolerance',default='0')
    p.add_argument('--output',type=Path,required=True,help='Private report; never edits either compared source')
    args=p.parse_args(argv)
    source,reference,output=map(guarded,(args.input,args.reference,args.output))
    if output in (source,reference):
        p.error('output must not overwrite a source snapshot')
    validate_symbols(args.symbols);tolerance(args.absolute_tolerance);tolerance(args.relative_tolerance)
    bodies=[]
    for path in (source,reference):
        with path.open('rb') as f:bodies.append(f.read(MAX_INPUT_BYTES+1))
    result=review(*(strict_json(body) for body in bodies),args.symbols,
                  absolute_tolerance=args.absolute_tolerance,relative_tolerance=args.relative_tolerance)
    result['raw_file_sha256']={'input':hashlib.sha256(bodies[0]).hexdigest(),'reference':hashlib.sha256(bodies[1]).hexdigest()}
    atomic_bytes(output,canonical(result))
    print(json.dumps({'counts':result['counts'],'needs_review':result['needs_review'],
                     'stocks_without_financial_records':result['stocks_without_financial_records']},ensure_ascii=False))
    return 2 if result['needs_review'] else 0


if __name__=='__main__':
    raise SystemExit(main())
