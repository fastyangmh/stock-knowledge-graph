"""Compare two audited private research versions, without market return claims.

Compare rule states and evidence, NOT trades, alpha, accuracy or a combined score.
Changed thresholds/source definitions and missing observations are distinguished
from genuine transitions between two evaluable states under the same rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .alerts import RULES
from .bundle_audit import Bundle, audit_bundle, _require
from .dates import timestamp
from .market_units import DEFINITION_KEYS
from .research_history import canonical

VERSION = "research-comparison-1.0"
CATEGORIES = ("price_volume", "monthly_revenue")
CONFIG_KEYS = {
    "price_change": ("price_change_pct", "max_observation_gap_days"),
    "volume_ratio": ("volume_ratio", "volume_window", "max_observation_gap_days"),
    "revenue_yoy": ("revenue_yoy_pct",),
    "revenue_mom": ("revenue_mom_pct",),
    "revenue_yoy_change": ("revenue_yoy_change_pp",),
    "revenue_yoy_trend": ("revenue_trend_steps",),
}
EVALUATED = {"triggered", "not_triggered"}


def _checks(bundle, sid):
    if bundle.alerts is None or sid not in bundle.alerts["stocks"]:
        return None, {}
    report = bundle.alerts["stocks"][sid]
    return report, {row["rule_id"]: row for group in report["categories"].values() for row in group}


def _sources(check):
    return sorted({(row.get("source_id") or "", row.get("source_url") or "") for row in check["evidence"]})


def _rule_diff(rule, before_report, before, after_report, after):
    result = {"rule_id": rule, "title": RULES[rule][1], "category": RULES[rule][0],
              "before": before, "after": after, "comparable": False,
              "changed_fields": [], "transition": "not_computed", "reason": "alerts_not_computed_in_both_runs"}
    if before_report is None or after_report is None:
        return result
    config_keys = CONFIG_KEYS[rule]
    if (before_report["schema_version"] != after_report["schema_version"] or
            any(before_report["config"].get(k) != after_report["config"].get(k) for k in config_keys) or
            any(before.get(k) != after.get(k) for k in ("formula", "unit", "threshold"))):
        result.update(transition="definition_changed", reason="rule_version_or_relevant_settings_changed")
        return result
    if _sources(before) and _sources(after) and _sources(before) != _sources(after):
        result.update(transition="definition_changed", reason="evidence_source_changed")
        return result
    if RULES[rule][0] == "price_volume" and before["status"] in EVALUATED and after["status"] in EVALUATED:
        def identities(check):
            return {(row.get("market"), *(row.get(k) for k in DEFINITION_KEYS)) for row in check["evidence"]}
        a_id, b_id = identities(before), identities(after)
        if not a_id or not b_id or any(
                any(row.get(k) is None for k in ("market", "price_unit", "price_basis"))
                for check in (before, after) for row in check["evidence"]):
            result.update(transition="definition_unknown", reason="legacy_price_basis_not_recorded")
            return result
        if a_id != b_id or len(a_id) != 1:
            result.update(transition="definition_changed", reason="price_basis_or_scale_changed")
            return result
    result["changed_fields"] = [key for key in sorted(set(before) | set(after))
                                if key != "id" and before.get(key) != after.get(key)]
    a, b = before["status"], after["status"]
    if a in EVALUATED and b in EVALUATED:
        result["comparable"] = True
        transition = ("activated" if (a, b) == ("not_triggered", "triggered") else
                      "no_longer_triggered" if (a, b) == ("triggered", "not_triggered") else
                      "still_triggered" if b == "triggered" else "still_not_triggered")
        result.update(transition=transition, reason="two_evaluable_states_same_definition")
    elif a in EVALUATED:
        result.update(transition="became_unavailable", reason="missing_or_incomparable_data_is_not_resolved_risk")
    elif b in EVALUATED:
        result.update(transition="became_evaluable", reason="first_evaluable_result_is_not_a_new_signal_transition")
    else:
        result.update(transition="still_unavailable", reason="neither_run_evaluable")
    return result


def _element_diff(before, after, *, edge=False, limit=50):
    def facts(row):
        # Timestamp churn is not a changed relation definition. Data availability,
        # evidence and model identity are retained; only generated edge as_of is ignored.
        return {k: v for k, v in row.items() if not (edge and k == "as_of")}
    a, b = {r["id"]: facts(r) for r in before}, {r["id"]: facts(r) for r in after}
    added, removed = sorted(b.keys()-a.keys()), sorted(a.keys()-b.keys())
    changed = []
    for key in sorted(a.keys() & b.keys()):
        fields = [f for f in sorted(set(a[key]) | set(b[key])) if a[key].get(f) != b[key].get(f)]
        if fields:
            changed.append({"id": key, "fields": fields})
    return {"counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
            "added": added[:limit], "removed": removed[:limit], "changed": changed[:limit],
            "details_truncated": any(n > limit for n in (len(added), len(removed), len(changed)))}


def compare(before: Bundle, after: Bundle, *, detail_limit=50, price_review=False, action_manifests=()):
    _require(type(detail_limit) is int and 1 <= detail_limit <= 500, "invalid_detail_budget")
    _require(timestamp(before.report["known_at"]) <= timestamp(after.report["known_at"]), "before_cutoff_is_later_than_after")
    a, b = set(before.graphs), set(after.graphs)
    rows = []
    for sid in sorted(a | b):
        selection = "shared" if sid in a & b else "added" if sid in b else "removed"
        previous, old = _checks(before, sid)
        current, new = _checks(after, sid)
        categories = {c: [] for c in CATEGORIES}
        for rule, (category, _, _) in RULES.items():
            change = _rule_diff(rule, previous, old.get(rule), current, new.get(rule))
            if selection != "shared":
                change.update(transition="added_coverage" if selection == "added" else "removed_coverage",
                              comparable=False, reason="stock_selection_change_is_not_an_alert_transition")
            categories[category].append(change)
        g1, g2 = before.graphs.get(sid, {}), after.graphs.get(sid, {})
        rows.append({"stock_id": sid, "selection": selection, "categories": categories,
                     "graph": {"nodes": _element_diff(g1.get("nodes", []), g2.get("nodes", []), limit=detail_limit),
                               "edges": _element_diff(g1.get("edges", []), g2.get("edges", []), edge=True, limit=detail_limit)}})
    old_w, new_w = set(before.report["quality"]["warnings"]), set(after.report["quality"]["warnings"])
    parameters_a, parameters_b = before.report.get("configuration"), after.report.get("configuration")
    result = {"schema_version": VERSION, "combined_score": False,
              "before": {k: v for k, v in before.summary().items() if k in ("run", "known_at", "completed_at", "report_sha256")},
              "after": {k: v for k, v in after.summary().items() if k in ("run", "known_at", "completed_at", "report_sha256")},
              "selection": {"added": sorted(b-a), "removed": sorted(a-b), "shared": sorted(a & b)},
              "graph_configuration": "unknown" if parameters_a is None or parameters_b is None else
                                     "same" if parameters_a == parameters_b else "changed",
              "quality_warnings": {"added": sorted(new_w-old_w), "removed": sorted(old_w-new_w), "unchanged": sorted(old_w & new_w)},
              "stocks": rows, "scope": "exported_display_subgraphs_and_rule_states_only_not_full_history_or_returns",
              "caveats": ["no_combined_score_or_buy_sell_instructions", "missing_data_does_not_mean_alert_resolved",
                          "graph_pruning_and_settings_can_change_visible_nodes", "local_hashes_are_not_digital_signatures",
                          "not_an_event_study_backtest_or_forecast_validation"]}
    if price_review or action_manifests:
        from .price_action_review import review_prices
        result["price_review"] = review_prices(before, after, action_manifests)
    result["comparison_id"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--before", required=True, help="Saved run ID; no path or implicit latest")
    parser.add_argument("--after", required=True)
    parser.add_argument("--price-review", action="store_true", help="Review original prices and action evidence for the saved trade dates")
    parser.add_argument("--action-manifest", type=Path, action="append", default=[],
                        help="Private data.gov.tw 11633 capture manifest; repeat for saved versions (implies --price-review)")
    args = parser.parse_args(argv)
    result = compare(audit_bundle(args.root, args.before), audit_bundle(args.root, args.after),
                     price_review=args.price_review, action_manifests=args.action_manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
