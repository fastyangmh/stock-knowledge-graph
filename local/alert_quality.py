"""Describe the six saved alert rules in one audited private research catalog."""
import argparse
from collections import Counter, defaultdict
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

from .alerts import CAVEATS, RULES, STATUSES, definition_number, number
from .calendar_archive import MIB
from .calendar_coverage import audited_bundles, calendar_day, load_calendar
from .dates import analysis_cutoff, iso_date, timestamp
from .event_study import save_report
from .financial_definitions import DEFINITION_KEYS as FINANCIAL_KEYS
from .market_units import DEFINITION_KEYS as PRICE_KEYS, UNKNOWN
from .price_action_review import ACTION_TYPES
from .tpex_action_evidence import read_capture
from .research_compare import CONFIG_KEYS, EVALUATED
from .research_history import canonical


def counts():
    return {**dict.fromkeys(sorted(STATUSES | {"total", "evaluable", "unavailable"}), 0), "reasons": Counter()}


def count(group, check):
    status = check["status"]
    group["reasons"][check["reason"]] += 1
    group["total"] += 1
    group[status] += 1
    group["evaluable" if status in EVALUATED else "unavailable"] += 1


def definition(alert, check):
    rule = check["rule_id"]
    fields = ("market", *PRICE_KEYS) if check["category"] == "price_volume" else ("metric", "unit", *FINANCIAL_KEYS)
    sources = {}
    for row in check["evidence"]:
        source = {field: row.get(field) for field in ("source_id", "source_url", *fields)}
        sources[canonical(source)] = source
    return {"version": alert["schema_version"], "settings": {k: definition_number(k, alert["config"][k]) for k in CONFIG_KEYS[rule]},
            "formula": check["formula"], "threshold": definition_number(CONFIG_KEYS[rule][0], check["threshold"]), "unit": check["unit"],
            "sources": [sources[key] for key in sorted(sources)]}


def evidence_values(check):
    field = {"price_change": "close", "volume_ratio": "volume_shares"}.get(check["rule_id"], "value")
    return {(row.get("period", row.get("period_end")), row.get("source_id"), row.get("metric")):
            number(row[field]) if row.get(field) is not None else None for row in check["evidence"]}


def change_since(previous, current):
    before, after = evidence_values(previous), evidence_values(current)
    if any(before[k] != after[k] for k in before.keys() & after.keys()):
        return "value_revised"
    if before.keys() != after.keys():
        return "observation_set_changed"
    if any(previous.get(k) != current.get(k) for k in ("value", "status", "reason", "baseline", "direction")):
        return "evaluation_changed"
    if previous["evidence"] != current["evidence"]:
        return "provenance_changed"
    return "repeat"


def record(cases, run, stock, alert, check, inputs):
    labels = {"stock_id": stock, "category": check["category"], "rule_id": check["rule_id"],
              "target_period": check["target_period"], "definition": definition(alert, check)}
    # A missing period or absent source cannot identify a repeat across runs.
    if not labels["target_period"] or not labels["definition"]["sources"]:
        labels["unidentified_in_run"] = run
    key = sha256(canonical(labels)).hexdigest()
    case = cases.setdefault(key, {**labels, "case_id": key, "captures": []})
    captures = case["captures"]
    change = "first_saved"
    if captures:
        previous = captures[-1]
        change = change_since(previous["check"], check)
        if (change not in ("repeat", "provenance_changed") and
                timestamp(inputs[previous["run"]]["completed_at"]) == timestamp(inputs[run]["completed_at"])):
            raise ValueError("conflicting same-time saved alert evaluations")
    capture = {"run": run, "change": change, "check": check}
    captures.append(capture)
    return capture


def price_context(check, sid, calendar, actions, budget):
    evidence = check["evidence"]
    dates = sorted({row["period"] for row in evidence})
    markets = {row.get("market") for row in evidence}
    warnings = ["action_coverage_unknown", "observation_window_not_verified_exchange_sessions"]
    if not evidence or any(row.get(k) in UNKNOWN for row in evidence for k in PRICE_KEYS):
        warnings.append("price_definition_unknown")
    context = {"warnings": warnings, "actions": [], "unknown_interval_coverage": list(ACTION_TYPES),
               "open_without_window_observation": [], "calendar_status_counts": {},
               "calendar_conflicts": [], "calendar_evidence_ids": []}
    if not dates or len(markets) != 1 or None in markets:
        warnings.append("price_window_or_market_unavailable")
        return context
    start, end = dates[0], dates[-1]
    market = next(iter(markets))
    if market == "TPEX":
        context["actions"] = [row for row in actions.get(sid, ()) if start < row["effective_date"] <= end]
        if context["actions"]:
            warnings.append("action_in_price_interval")
    if not calendar:
        warnings.append("calendar_evidence_unavailable_at_cutoff")
        return context
    first, last = iso_date(start), iso_date(end)
    day_count = (last - first).days + 1
    budget["days"] -= day_count
    budget["calendar_visits"] -= day_count * len(calendar)
    if min(budget.values()) < 0:
        raise ValueError("quality calendar window budget exceeded")
    present, statuses, ids = set(dates), Counter(), set()
    for offset in range(day_count):
        day = first + timedelta(days=offset)
        entry = calendar_day(calendar, market.lower(), day)
        status, date = entry["market_status"], day.isoformat()
        ids.update(entry["evidence_ids"])
        if status == "closed" and date in present:
            status = "conflict"
        statuses[status] += 1
        if status == "open" and date not in present:
            context["open_without_window_observation"].append(date)
        if status == "conflict":
            context["calendar_conflicts"].append(date)
    context.update(calendar_status_counts=dict(statuses), calendar_evidence_ids=sorted(ids))
    return context


def archived_provenance(report):
    quality = report["quality"]
    sources = {}
    for snapshot in quality.get("snapshots", []):
        receipts = snapshot.get("metadata", {}).get("source_snapshots", [])
        if isinstance(receipts, list):
            sources[snapshot["sha256"]] = [
                {k: row[k] for k in ("dataset_id", "resource_url", "retrieved_at", "sha256", "bytes") if k in row}
                for row in receipts if isinstance(row, dict) and "sha256" in row]
    notices = []
    for entry in quality.get("source_revisions", []):
        notice = entry["notice"]
        if notice["group"] == "financial_metrics" and notice["key"].get("metric") in (
            "monthly_revenue", "monthly_revenue_yoy_pct", "monthly_revenue_mom_pct"
        ):
            notices.append({k: notice[k] for k in ("action", "key", "source_id", "target_snapshot_sha256",
                            "effective_at", "published_at", "source_reference")} |
                           {k: entry[k] for k in ("snapshot_sha256", "recorded_at")})
    for entry in quality.get("market_notices", []):
        notice = entry["notice"]
        notices.append({k: notice[k] for k in ("action", "symbol", "trade_date", "source_id",
                        "effective_at", "published_at", "target_raw_sha256", "replacement_raw_sha256",
                        "evidence_sha256", "evidence_url", "locator")} |
                       {k: entry[k] for k in ("notice_sha256", "recorded_at")})
    return {"raw_sources": sources, "revision_notices": notices}


def summarize(cases):
    rules = {rule: {"category": category, "first_saved": counts(), "saved": counts()}
             for rule, (category, _, _) in RULES.items()}
    definitions = {}
    for case in cases:
        rule = case["rule_id"]
        labels = {"category": case["category"], "rule_id": rule, "definition": case["definition"]}
        identity = sha256(canonical(labels)).hexdigest()
        case["definition_id"] = identity
        group = definitions.setdefault(identity, {**labels, "definition_id": identity,
                                                  "first_saved": counts(), "saved": counts()})
        case["saved"] = counts()
        for bucket in (group, rules[rule]):
            count(bucket["first_saved"], case["captures"][0]["check"])
        for capture in case["captures"]:
            for bucket in (group["saved"], rules[rule]["saved"], case["saved"]):
                count(bucket, capture["check"])
    return rules, list(definitions.values())


def build(root, as_of, *, calendar=None, manifests=()):
    cutoff = analysis_cutoff(as_of)
    bundles = audited_bundles(root, 50, 256 * 1024 * 1024)
    if len(manifests) > 32:
        raise ValueError("action receipt count exceeds budget")
    calendar_entries = load_calendar(calendar, cutoff, 32 * MIB)[0] if calendar else []
    selection = {stock for bundle in bundles if timestamp(bundle.report["completed_at"]) <= cutoff
                 for stock in bundle.report["selection"]["stock_ids"]}
    sources, all_actions = [], []
    for manifest in manifests:
        source, actions = read_capture(manifest, cutoff, selection)
        if source and source not in sources:
            sources.append(source)
            all_actions.extend(actions)
    budget = {"days": 50000, "calendar_visits": 1000000}
    inputs, cases = {}, {}
    for bundle in sorted(bundles, key=lambda b: (timestamp(b.report["completed_at"]), b.report["run"])):
        report = bundle.report
        run = report["run"]
        info = inputs[run] = {k: report[k] for k in ("known_at", "completed_at", "selection")}
        info["report_sha256"] = bundle.report_sha256
        info["fact_scope"] = "unpruned_facts" if bundle.facts is not None else "display_graph_only"
        if timestamp(report["completed_at"]) > cutoff:
            info["status"] = "after_analysis_cutoff"
            continue
        if bundle.alerts is None:
            info["status"] = "alerts_not_computed"
            continue
        info["status"] = "included"
        known = timestamp(report["known_at"])
        eligible_calendar = [row for row in calendar_entries if timestamp(row["saved_at"]) <= known]
        actions = defaultdict(list)
        for action in all_actions:
            if timestamp(action["observed_at"]) <= known:
                actions[action["stock_id"]].append(action)
        info.update(archived_provenance(report))
        info["config"] = report["research_alerts"]["config"]
        for stock, alert in bundle.alerts["stocks"].items():
            for checks in alert["categories"].values():
                for check in checks:
                    capture = record(cases, run, stock, alert, check, inputs)
                    if check["category"] == "price_volume":
                        capture["price_context"] = price_context(check, stock, eligible_calendar, actions, budget)
    rules, definitions = summarize(cases.values())
    scope = "saved_alerts" if cases else "no_alerts_computed"
    if all(info["status"] == "after_analysis_cutoff" for info in inputs.values()):
        scope = "no_saved_run_by_cutoff"
    return {"schema_version": "alert-quality-2", "definition_groups": definitions, "scope_status": scope, "as_of": cutoff.isoformat(),
            "calendar_evidence": [{k: row[k] for k in ("id", "market", "start", "end", "sha256", "saved_at", "source_url")}
                                  for row in calendar_entries], "action_sources": sources,
            "rules": rules, "cases": list(cases.values()), "inputs": inputs, "warnings": CAVEATS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Include bundles saved by this timestamp with timezone")
    parser.add_argument("--output", type=Path, required=True, help="Private JSON report outside the runs directory")
    parser.add_argument("--calendar", type=Path, help="Private market-calendar-1 manifest")
    parser.add_argument("--action-manifest", type=Path, action="append", default=[], help="Saved 11633 receipt")
    args = parser.parse_args(argv)
    try:
        report = build(args.root, args.as_of, calendar=args.calendar, manifests=args.action_manifest)
        save_report(report, args.output, args.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print("Saved rule results:", sum(rule["saved"]["total"] for rule in report["rules"].values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
