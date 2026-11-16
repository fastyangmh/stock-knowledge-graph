"""Private descriptive post-event statistics on saved, audited research bundles.

A: describe subsequent observations; NOT a strategy backtest, trade instruction,
causal effect or return forecast. No live market requests, model, SQL or Git IO.
Events use their first saved trigger per stock/rule/period/direction/definition;
subsequent values use first saved facts after the actual event capture time.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path

from .alerts import RULES, number, text_number, validate as validate_alert
from .bundle_audit import catalog, _require
from .core import ROOT
from .dates import iso_date, timestamp
from .event_outcomes import STATES, METRICS, baseline_facts, basis, measure, saved_facts
from .preview import server_from_files
from .research import guarded
from .research_compare import CONFIG_KEYS
from .research_history import canonical, strict_json
from .safety import exclusive_lock

VERSION = "event-study-1.0"
DEFAULTS = {"quote_horizons": [1, 5, 20], "revenue_horizons": [1, 3, 6], "max_quote_gap_days": 10}
MAX_EVENTS = 2000
MAX_FACTS = 100000
MAX_FACT_VISITS = 5_000_000
MAX_REPORT_BYTES = 32 * 1024 * 1024
CAVEATS = ["descriptive_only_not_strategy_return_causality_or_prediction",
           "price_changes_are_unadjusted_not_total_investment_returns",
           "observed_quotes_are_not_verified_exchange_sessions",
           "first_trigger_in_supplied_saved_catalog_not_true_market_onset",
           "first_saved_followup_policy_not_final_revised_history",
           "missing_pruned_or_unsaved_facts_never_imputed",
           "small_dependent_overlapping_samples_no_significance_claims",
           "selection_and_survivorship_bias_not_removed",
           "no_combined_score_win_rate_buy_sell_or_publication",
           "bundle_hashes_are_not_authenticity_or_data_license_proof",
           "raw_checks_are_from_saved_run_not_revalidated_against_raw_csv"]


def policy(overrides=None):
    if overrides is not None and (not isinstance(overrides, dict) or set(overrides)-set(DEFAULTS)):
        raise ValueError("unknown event study configuration")
    result = copy.deepcopy(DEFAULTS)
    result.update(copy.deepcopy(overrides or {}))
    for key, cap in (("quote_horizons", 252), ("revenue_horizons", 24)):
        values = result[key]
        if (not isinstance(values, list) or not 1 <= len(values) <= 6
                or any(type(n) is not int or not 1 <= n <= cap for n in values)
                or values != sorted(set(values))):
            raise ValueError("horizons must be sorted unique positive integers within budget")
    gap = result["max_quote_gap_days"]
    if type(gap) is not int or not 1 <= gap <= 31:
        raise ValueError("max_quote_gap_days must be 1..31")
    return result


def _id(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _definition(report, check):
    rule = check["rule_id"]
    sources = sorted({(row.get("source_id") or "", row.get("source_url") or "") for row in check["evidence"]})
    source_basis = sorted({canonical({k:r.get(k) for k in ("market", "price_unit", "price_basis")}).decode()
                           for r in check["evidence"]}) if check["category"] == "price_volume" else []
    return {"version": report["schema_version"], "rule_id": rule,
            "config": {k: report["config"][k] for k in CONFIG_KEYS[rule]},
            "formula": check["formula"], "threshold": check["threshold"], "unit": check["unit"],
            "sources": [list(pair) for pair in sources], "price_bases": source_basis}


def summarize(events):
    """Per-definition/direction/source/unit/metric/horizon strata. No pooled score."""
    groups = {}
    for event in events:
        for row in event["outcomes"]:
            labels = {k:event[k] for k in ("category", "rule_id", "direction", "definition_id")}
            labels.update({k:row[k] for k in ("metric", "horizon", "horizon_unit", "unit", "basis")})
            key = _id(labels)
            group = groups.setdefault(key, {**labels, "group_id":key, "events": [], "values":[], "statuses":Counter()})
            group["events"].append(event["event_id"])
            group["statuses"][row["status"]] += 1
            if row["status"] == "observed":
                group["values"].append(number(row["value"]))
    output = []
    for key in sorted(groups):
        group = groups[key]
        values = sorted(group.pop("values"))
        n = len(values)
        group["n_total"] = len(group["events"])
        group["n_observed"] = n
        group["n_unavailable"] = group["n_total"] - n
        group["status_counts"] = dict(group.pop("statuses"))
        group["status_counts"] = {state:group["status_counts"].get(state, 0) for state in STATES}
        group["statistics"] = None
        if n:
            with localcontext() as ctx:
                ctx.prec = 100
                group["statistics"] = {"mean": text_number(sum(values, Decimal(0))/n),
                    "median": text_number(values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2),
                    "min": text_number(values[0]), "max": text_number(values[-1])}
        group["sample_warning"] = "descriptive_dependent_sample_no_significance_or_population_claim"
        output.append(group)
    return output


def analyze(bundles, analysis_at, config=None):
    """Caller provides audited Bundle objects; no file access. Deterministic output."""
    settings = policy(config)
    cutoff = timestamp(analysis_at)
    analysis_at = cutoff.isoformat()
    if cutoff > datetime.now(timezone.utc):
        raise ValueError("analysis cutoff cannot be in the future")
    ordered = sorted(bundles, key=lambda b:(timestamp(b.report["completed_at"]), b.report["run"]))
    if len({b.report["run"] for b in ordered}) != len(ordered):
        raise ValueError("duplicate research bundle")
    eligible = [b for b in ordered if timestamp(b.report["completed_at"]) <= cutoff]
    facts_by_run, timeline, events = {}, {}, {}
    counters = Counter()
    for bundle in eligible:
        for sid in bundle.graphs:
            facts = saved_facts(bundle, sid)
            facts_by_run[bundle.report["run"],sid] = facts
            timeline.setdefault(sid, []).extend(facts)
            counters["saved_numeric_facts"] += len(facts)
            if counters["saved_numeric_facts"] > MAX_FACTS:
                raise ValueError("saved-fact budget exceeded")
        if bundle.alerts is None:
            counters["runs_without_alerts"] += 1
            continue
        for sid, report in sorted(bundle.alerts["stocks"].items()):
            validate_alert(report, sid)
            for category, checks in report["categories"].items():
                for check in checks:
                    if check["status"] != "triggered":
                        continue
                    counters["triggered_checks_seen"] += 1
                    if not check.get("target_period"):
                        raise ValueError("triggered event lacks target period")
                    iso_date(check["target_period"])
                    if not check["evidence"]:
                        raise ValueError("triggered event lacks evidence")
                    definition = _definition(report, check)
                    value = number(check["value"])
                    direction = "positive" if value > 0 else "negative" if value < 0 else "zero"
                    key = _id([VERSION,sid,check["rule_id"],check["target_period"],direction,definition])
                    if key in events:
                        prior = events[key]
                        if timestamp(prior["event_at"]) == timestamp(bundle.report["completed_at"]):
                            a = {k:v for k,v in prior["trigger"].items() if k != "id"}
                            b = {k:v for k,v in check.items() if k != "id"}
                            if a != b:
                                raise ValueError("conflicting same-time event trigger")
                        prior["repeated_captures"] += 1
                        counters["duplicate_period_events_suppressed"] += 1
                        continue
                    if len(events) >= MAX_EVENTS:
                        raise ValueError("event budget exceeded; choose a smaller research catalog")
                    events[key] = {"event_id":key,"stock_id":sid,"rule_id":check["rule_id"],
                        "category":category,"title":check["title"],"target_period":check["target_period"],
                        "direction":direction,"definition":definition,"definition_id":_id(definition),
                        "event_at":timestamp(bundle.report["completed_at"]).isoformat(),
                        "known_at":report["known_at"],"run":bundle.report["run"],"report_sha256":bundle.report_sha256,
                        "trigger":copy.deepcopy(check), "baseline":baseline_facts(facts_by_run[bundle.report["run"],sid]),
                        "repeated_captures":0}
    rows = sorted(events.values(),key=lambda e:(timestamp(e["event_at"]),e["stock_id"],e["rule_id"],e["event_id"]))
    if sum(len(timeline.get(e["stock_id"], [])) for e in rows) > MAX_FACT_VISITS:
        raise ValueError("event/fact work budget exceeded; narrow the saved catalog")
    for event in rows:
        event["outcomes"] = measure(event, timeline.get(event["stock_id"],[]), settings, analysis_at)
    result = {"schema_version":VERSION,"analysis_at":analysis_at,"configuration":settings,
        "combined_score":False,"trade_assumptions":False,"warnings":CAVEATS,
        "event_policy":"first_saved_trigger_per_stock_rule_period_direction_definition_not_crossing_episodes",
        "followup_policy":"first_saved_post_event_fact_per_period_no_restatement_or_missing_fill",
        "counts":{"included_runs":len(eligible),"runs_after_cutoff":len(ordered)-len(eligible),
                  "events":len(rows), **{k:counters[k] for k in ("saved_numeric_facts","runs_without_alerts",
                    "triggered_checks_seen","duplicate_period_events_suppressed")}},
        "inputs":[{"run":b.report["run"],"report_sha256":b.report_sha256,
                   "known_at":b.report["known_at"],"completed_at":b.report["completed_at"]} for b in eligible],
        "categories":{category:{"events":[e for e in rows if e["category"]==category],
                   "summaries":summarize([e for e in rows if e["category"]==category])}
                   for category in ("price_volume","monthly_revenue")},
        "scope":"saved_display_numeric_facts_only_not_complete_market_history_or_total_returns"}
    result["study_id"] = _id(result)
    if len(canonical(result)) > MAX_REPORT_BYTES:
        raise ValueError("event study exceeds 32 MiB report budget")
    return result


def build(root, analysis_at, *, config=None, max_runs=50, max_mib=256):
    if type(max_mib) is not int or not 1 <= max_mib <= 4096:
        raise ValueError("invalid catalog size budget")
    policy(config)
    cutoff = timestamp(analysis_at)
    if cutoff > datetime.now(timezone.utc):
        raise ValueError("analysis cutoff cannot be in the future")
    summary, bundles = catalog(root, max_runs=max_runs, max_bytes=max_mib*1024*1024)
    if summary["counts"]["invalid"] or not summary["latest_valid"]:
        raise ValueError("invalid catalog/latest; do not silently omit invalid events")
    return analyze(list(bundles.values()), analysis_at, config)


def save_report(report, output, root):
    """Exclusive creation; never overwrite another report or any research bundle."""
    path, source = guarded(output), guarded(root)
    if path == source or path.is_relative_to(source) or source.is_relative_to(path):
        raise ValueError("event report must be outside the research input directory")
    body = canonical(report)
    if len(body)>MAX_REPORT_BYTES:
        raise ValueError("event report exceeds size budget")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with exclusive_lock(path):
        if path.exists():
            if not path.is_file() or path.stat().st_size != len(body) or path.read_bytes() != body:
                raise FileExistsError("refusing to overwrite a different event report")
            return
        # Exclusive open avoids clobbering a concurrently-created destination.
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(dir=path.parent) as temp:
            temp.write(body); temp.flush(); os.fsync(temp.fileno())
            os.link(temp.name, path)


ASSETS = {"event-study.html":"text/html; charset=utf-8", "css/style.css":"text/css; charset=utf-8",
          "js/event-study.js":"text/javascript; charset=utf-8"}


def make_server(report, *, port=8767, root=ROOT):
    body = canonical(report)
    if len(body)>MAX_REPORT_BYTES:
        raise ValueError("event report exceeds preview budget")
    files = {"/event-study.json":(body,"application/json; charset=utf-8")}
    for name, mime in ASSETS.items():
        path = Path(root)/name
        if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()) or path.stat().st_size>1024*1024:
            raise ValueError("unsafe event preview asset")
        files["/"+name] = (path.read_bytes(),mime)
    files["/"] = files["/event-study.html"]
    return server_from_files(files,port=port)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT/"local/private/research-runs")
    p.add_argument("--as-of",required=True,help="Analysis cutoff with time and timezone, not event or trading date")
    p.add_argument("--config",type=Path,help="Private JSON horizon overrides")
    p.add_argument("--output",type=Path,help="Optional NEW private JSON report outside research-runs")
    p.add_argument("--serve",action="store_true",help="Read-only localhost report UI; no account authentication")
    p.add_argument("--port",type=int,default=8767)
    p.add_argument("--max-runs",type=int,default=50)
    p.add_argument("--max-mib",type=int,default=256)
    args=p.parse_args(argv)
    if not 1<=args.port<=65535:p.error("port must be 1..65535")
    config=None
    if args.config:
        with guarded(args.config).open("rb") as f:body=f.read(65537)
        if len(body)>65536:p.error("config exceeds 64 KiB")
        config=strict_json(body)
    if args.output:
        out=guarded(args.output)
        if args.config and out==guarded(args.config):p.error("output must not replace config")
    report=build(args.root,args.as_of,config=config,max_runs=args.max_runs,max_mib=args.max_mib)
    if args.output:save_report(report,args.output,args.root)
    print("Descriptive study:",report["study_id"],"Events:",report["counts"]["events"],"No trading/publication.")
    if args.serve:
        with make_server(report,port=args.port) as server:
            print(f"Private event observations: http://127.0.0.1:{server.server_port}/",flush=True)
            print("Read-only capture, local users can access; restart to refresh. Ctrl-C to stop.",flush=True)
            try:server.serve_forever()
            except KeyboardInterrupt:pass
    return 0


if __name__=="__main__":raise SystemExit(main())
