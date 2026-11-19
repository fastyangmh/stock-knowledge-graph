"""Descriptive post-event measurements from already audited saved research facts.

No providers, SQL, price adjustment, transactions, causal inference or imputation.
The event baseline is frozen; future periods use their first saved observation.
Observed quote steps are NOT verified exchange sessions. Input units are never
silently converted. A missing/invalid endpoint is not replaced by a later one.
"""
from __future__ import annotations

import calendar
import copy
from datetime import date
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

from .alerts import number, text_number
from .market_units import DEFINITION_KEYS
from .research_facts import SCHEMA, NOTICE_SCHEMA
from .dates import iso_date, timestamp
from .financial_definitions import financial_definition, unverified_definition

METRICS = {
    "close_change_pct": ("收盤價觀察變化", "percent", "quote_observations"),
    "volume_ratio": ("成交股數相對事件日倍數", "ratio", "quote_observations"),
    "revenue_change_pct": ("月營收數值變化", "percent", "calendar_months"),
    "revenue_yoy_change_pp": ("月營收年增率變化", "percentage_points", "calendar_months"),
}
REVENUE_KEYS = ("monthly_revenue", "monthly_revenue_yoy_pct", "monthly_revenue_mom_pct")
STATES = ("observed", "pending", "insufficient_data", "not_comparable")


def month_end_offset(value, steps):
    day = iso_date(value)
    if day.day != calendar.monthrange(day.year, day.month)[1]:
        raise ValueError("revenue period is not month end")
    key = day.year * 12 + day.month - 1 + steps
    year, month = divmod(key, 12)
    return date(year, month + 1, calendar.monthrange(year, month + 1)[1]).isoformat()


def saved_facts(bundle, sid):
    """Prefer the audited complete contract; legacy uses primary-stock nodes.

Audit proves bytes/structure, not market truth. Preserve report and original
snapshot references, and validate numeric/time contracts before calculation.
"""
    cutoff = timestamp(bundle.report["known_at"])
    capture = timestamp(bundle.report["completed_at"])
    if capture < cutoff:
        raise ValueError("capture is earlier than source knowledge cutoff")
    items, seen = [], set()
    complete = bundle.facts is not None
    if complete and bundle.facts.get("schema_version") not in (SCHEMA, NOTICE_SCHEMA):
        raise ValueError("unsupported research facts schema")
    rows = bundle.facts["facts"] if complete else bundle.graphs[sid]["nodes"]
    for node in rows:
        if complete and node.get("stock_id") != sid:
            continue
        kind = node.get("kind") if complete else node.get("type")
        if kind == "market_price" and "TW:" + str(node.get("symbol")) == sid:
            metric, period = "market", node["trade_date"]
            if type(node.get("volume_shares")) is not int or node["volume_shares"] < 0:
                raise ValueError("invalid saved volume")
            if node.get("close") is not None:
                number(node["close"])
            available = node.get("available_at") if complete else node.get("observed_at")
            body = {key: node.get(key) for key in (
                "close", "volume_shares", "market", "price_unit", "price_basis",
                "raw_sha256", "raw_snapshot_verified", "acquisition", *DEFINITION_KEYS)}
        elif (kind == "financial_metric" and node.get("stock_id") == sid
              and node.get("metric") in REVENUE_KEYS and node.get("period_type") == "month"):
            metric, period = node["metric"], node["period_end"]
            node = financial_definition(node)
            month_end_offset(period, 0)
            number(node["value"])
            available = node.get("available_at")
            body = {key: node.get(key) for key in (
                "value", "unit", "input_snapshot_sha256", "registered_at",
                "currency", "consolidation", "value_basis", "period_type")}
        else:
            continue
        if not isinstance(node.get("source_id"), str) or not node["source_id"]:
            raise ValueError("numeric fact missing source identity")
        if timestamp(available) > cutoff or iso_date(period) > cutoff.astimezone(ZoneInfo("Asia/Taipei")).date():
            raise ValueError("saved numeric fact was not available by its bundle cutoff")
        if body.get("registered_at") and timestamp(body["registered_at"]) > cutoff:
            raise ValueError("saved numeric fact was registered after bundle cutoff")
        key = (metric, period)
        if key in seen:
            raise ValueError("ambiguous same-period numeric facts; reconcile sources first")
        seen.add(key)
        if complete:
            body.update({key: copy.deepcopy(node.get(key)) for key in (
                "source", "source_available_at", "observed_at", "recorded_at", "recorded_at_status",
                "normalization_version", "normalization", "raw_value", "raw_unit", "statement_scope", "report_basis")})
        if complete and "notice_sha256" in node:
            body["notice_sha256"] = node["notice_sha256"]
        identity = {"fact_id": node["id"]} if complete else {"node_id": node["id"]}
        source_url = (node["source"].get("dataset_url") or node["source"].get("url")) if complete else node.get("source_url")
        items.append({"metric": metric, "period": period, "stock_id": sid,
                      "source_id": node["source_id"], "source_url": source_url,
                      "available_at": available, "captured_at": capture.isoformat(),
                      "run": bundle.report["run"], "report_sha256": bundle.report_sha256,
                      **identity, **body})
    return items


def basis(fact):
    if fact is None:
        return {"source_id": None, "status": "missing_baseline"}
    keys = (("source_id", "source_url", "market", *DEFINITION_KEYS)
            if fact["metric"] == "market" else
            ("source_id", "source_url", "unit", "currency", "consolidation", "value_basis", "period_type"))
    if "fact_id" in fact:
        keys += ("normalization_version", "statement_scope", "report_basis")
    return {key: fact.get(key) for key in keys}


def baseline_facts(facts):
    market = max((f for f in facts if f["metric"] == "market"), key=lambda f: f["period"], default=None)
    period = max((f["period"] for f in facts if f["metric"] in REVENUE_KEYS), default=None)
    return {"market": market, "revenue_period": period,
            **{key: next((f for f in facts if f["metric"] == key and f["period"] == period), None)
               for key in REVENUE_KEYS}}


def _first_saved(facts, metric, event_at):
    """First captured eligible value per period, not final revised history."""
    found = {}
    for fact in sorted(facts, key=lambda f: (timestamp(f["captured_at"]), f["run"], f.get("fact_id", f.get("node_id")))):
        if fact["metric"] != metric or timestamp(fact["captured_at"]) <= timestamp(event_at):
            continue
        day = fact["period"]
        if day in found:
            prior = found[day]
            # Equal capture times with conflicting facts have no principled order.
            ignored = {"run", "report_sha256", "node_id", "fact_id"}
            if (timestamp(prior["captured_at"]) == timestamp(fact["captured_at"])
                    and {k:v for k,v in prior.items() if k not in ignored} !=
                        {k:v for k,v in fact.items() if k not in ignored}):
                raise ValueError("conflicting same-time outcome capture")
            continue
        found[day] = fact
    return found


def _result(metric, horizon, base, target=None):
    title, unit, horizon_unit = METRICS[metric]
    return {"metric": metric, "title": title, "horizon": horizon, "horizon_unit": horizon_unit,
            "target_period": target, "unit": unit, "status": "insufficient_data", "value": None,
            "reason": "missing_event_baseline", "baseline": copy.deepcopy(base), "followup": None,
            "basis": basis(base), "observations_available": 0}


def post_event_quotes(facts, event_at):
    """One first-saved market fact per Taipei date strictly after event capture."""
    day = timestamp(event_at).astimezone(ZoneInfo("Asia/Taipei")).date()
    periods = _first_saved([f for f in facts if iso_date(f["period"]) > day], "market", event_at)
    return [periods[p] for p in sorted(periods)]


def _market(event, facts, config):
    base = event["baseline"]["market"]
    day = timestamp(event["event_at"]).astimezone(ZoneInfo("Asia/Taipei")).date()
    ordered = post_event_quotes(facts, event["event_at"])
    result = []
    for horizon in config["quote_horizons"]:
        for metric in ("close_change_pct", "volume_ratio"):
            row = _result(metric, horizon, base)
            row["observations_available"] = len(ordered)
            result.append(row)
            if base is None:
                continue
            if (day - iso_date(base["period"])).days > config["max_quote_gap_days"]:
                row.update(status="not_comparable", reason="stale_event_baseline")
                continue
            if event["category"] == "price_volume" and base["period"] != event["target_period"]:
                row.update(status="not_comparable", reason="alert_and_baseline_period_differ")
                continue
            if len(ordered) < horizon:
                row["reason"] = "not_enough_saved_post_event_quotes_not_verified_sessions"
                continue
            future = ordered[horizon-1]
            row.update(target_period=future["period"], followup=copy.deepcopy(future))
            path = [base] + ordered[:horizon]
            if any(basis(p) != basis(base) for p in path):
                row.update(status="not_comparable", reason="quote_source_or_basis_changed")
                continue
            if (any(p.get("raw_snapshot_verified") is not True for p in path)
                    or any(base.get(k) in (None, "") for k in ("market", "price_unit", "price_basis"))):
                row.update(status="not_comparable", reason="missing_price_basis_or_prior_raw_verification")
                continue
            days = [iso_date(p["period"]) for p in path]
            if any((b-a).days > config["max_quote_gap_days"] for a,b in zip(days, days[1:])):
                row.update(status="not_comparable", reason="observed_quote_gap_exceeds_policy")
                continue
            field = "close" if metric == "close_change_pct" else "volume_shares"
            a, b = base.get(field), future.get(field)
            if a is None or b is None or number(a) <= 0 or (field == "close" and number(b) <= 0):
                row.update(status="not_comparable", reason="missing_or_nonpositive_denominator_or_close")
                continue
            with localcontext() as ctx:
                ctx.prec = 100
                value = ((number(b)/number(a)-1)*100 if metric == "close_change_pct" else number(b)/number(a))
                if abs(value) > Decimal("1e60"):
                    row.update(status="not_comparable", reason="numeric_ratio_out_of_bounds")
                else:
                    row.update(status="observed", reason="first_saved_post_event_quote", value=text_number(value))
    return result


def _revenue(event, facts, config, analysis_at):
    base_period = event["baseline"]["revenue_period"]
    event_day = timestamp(event["event_at"]).astimezone(ZoneInfo("Asia/Taipei")).date()
    analysis_day = timestamp(analysis_at).astimezone(ZoneInfo("Asia/Taipei")).date()
    result = []
    for metric, key in (("revenue_change_pct", "monthly_revenue"),
                        ("revenue_yoy_change_pp", "monthly_revenue_yoy_pct")):
        base = event["baseline"][key]
        periods = _first_saved(facts, key, event["event_at"])
        for horizon in config["revenue_horizons"]:
            target = month_end_offset(base_period, horizon) if base_period else None
            row = _result(metric, horizon, base, target)
            result.append(row)
            if base is None:
                continue
            if metric == "revenue_change_pct" and (unverified_definition(base.get("unit")) or unverified_definition(base.get("currency"))):
                row.update(status="not_comparable", reason="monetary_scale_or_currency_unconfirmed")
                continue
            if metric == "revenue_yoy_change_pp" and base.get("unit") != "percent":
                row.update(status="not_comparable", reason="growth_rate_unit_not_percent")
                continue
            if iso_date(target) <= event_day:
                row.update(status="not_comparable", reason="target_month_not_after_actual_event_capture")
                continue
            if iso_date(target) > analysis_day:
                row.update(status="pending", reason="target_calendar_month_not_ended")
                continue
            future = periods.get(target)
            if future is None:
                row["reason"] = "target_month_not_saved_no_nearest_month_fill"
                continue
            row.update(followup=copy.deepcopy(future), observations_available=1)
            if basis(base) != basis(future):
                row.update(status="not_comparable", reason="revenue_source_unit_or_reporting_scope_changed")
                continue
            a, b = number(base["value"]), number(future["value"])
            if metric == "revenue_change_pct" and a <= 0:
                row.update(status="not_comparable", reason="nonpositive_revenue_baseline")
                continue
            with localcontext() as ctx:
                ctx.prec = 100
                value = (b/a-1)*100 if metric == "revenue_change_pct" else b-a
                if abs(value) > Decimal("1e60"):
                    row.update(status="not_comparable", reason="numeric_ratio_out_of_bounds")
                else:
                    row.update(status="observed", reason="first_saved_exact_future_month", value=text_number(value))
    return result


def measure(event, facts, config, analysis_at):
    cutoff = timestamp(analysis_at)
    eligible = [f for f in facts if timestamp(f["captured_at"]) <= cutoff and timestamp(f["available_at"]) <= cutoff]
    return _market(event, eligible, config) + _revenue(event, eligible, config, analysis_at)
