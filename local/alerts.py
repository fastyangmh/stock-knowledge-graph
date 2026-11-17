"""Deterministic research reminders, not forecasts or trading instructions.

Two independent categories; no combined score. Defaults are engineering review
thresholds, not calibrated investment rules. All values use Decimal arithmetic.
Only same-source observations known by cutoff are used; no missing-value fills.
"""
from __future__ import annotations
import calendar
import hashlib
import math
from decimal import Decimal, InvalidOperation, localcontext
from zoneinfo import ZoneInfo

from .market_units import DEFINITION_KEYS
from .dates import iso_date, timestamp
from .financial_definitions import DEFINITION_KEYS as FINANCIAL_DEFINITION_KEYS, financial_definition
from .research_history import canonical

VERSION = "research-alerts-1.0"
DEFAULTS = dict(price_change_pct=5.0, volume_window=20, volume_ratio=2.0,
                max_observation_gap_days=10, revenue_yoy_pct=30.0,
                revenue_mom_pct=20.0, revenue_yoy_change_pp=10.0,
                revenue_trend_steps=3)
RULES = {
    "price_change": ("price_volume", "收盤價觀察變動", "percent"),
    "volume_ratio": ("price_volume", "成交股數相對基準", "ratio"),
    "revenue_yoy": ("monthly_revenue", "月營收年增率", "percent"),
    "revenue_mom": ("monthly_revenue", "月營收月增率", "percent"),
    "revenue_yoy_change": ("monthly_revenue", "年增率較前月變化", "percentage_points"),
    "revenue_yoy_trend": ("monthly_revenue", "年增率連續變化", "steps"),
}
STATUSES = {"triggered", "not_triggered", "insufficient_data", "not_comparable"}
CAVEATS = ["research_only_not_buy_sell_or_return_forecast", "thresholds_not_calibrated",
           "price_observations_not_verified_exchange_sessions",
           "unadjusted_prices_corporate_actions_not_removed",
           "reported_revenue_percentages_only_no_unknown_scale_recalculation",
           "as_recorded_revisions_not_original_historical_market_knowledge",
           "verified_raw_bytes_do_not_certify_provider_authenticity_or_reuse_rights"]


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("alert numeric value must be a finite number")
    if len(str(value)) > 128:
        raise ValueError("alert numeric value too large")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid alert number") from exc
    if not result.is_finite() or abs(result) > Decimal("1e60"):
        raise ValueError("invalid or unbounded alert number")
    return result


def text_number(value):
    with localcontext() as ctx:
        ctx.prec = 100
        return format(value.quantize(Decimal("0.000001")), "f")


def policy(overrides=None):
    if overrides is not None and (not isinstance(overrides, dict) or set(overrides)-set(DEFAULTS)):
        raise ValueError("unknown alert configuration keys")
    result = {**DEFAULTS, **(overrides or {})}
    for key, value in result.items():
        if key in ("volume_window", "max_observation_gap_days", "revenue_trend_steps"):
            cap = {"volume_window":252, "max_observation_gap_days":31, "revenue_trend_steps":12}[key]
            if type(value) is not int or not 1 <= value <= cap:
                raise ValueError("invalid integer alert configuration: " + key)
        elif type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1_000_000:
            raise ValueError("invalid numeric alert configuration: " + key)
    return result


def _check(rule, threshold, formula, period=None):
    category, title, unit = RULES[rule]
    return dict(rule_id=rule, category=category, title=title, status="insufficient_data",
                reason="missing_history", target_period=period, value=None, unit=unit,
                threshold=threshold, formula=formula, baseline={}, evidence=[])


def _result(check, value, threshold, *, absolute=True):
    check.update(value=text_number(value), status="triggered" if
                 (abs(value) if absolute else value) >= number(threshold) else "not_triggered",
                 reason="threshold_met" if (abs(value) if absolute else value) >= number(threshold)
                 else "threshold_not_met")
    return check


def _market_ref(item):
    record, source = item["record"], item["source"]
    return {"source_id":source["source_id"], "source_url":source.get("dataset_url"),
            "period":record["trade_date"], "observed_at":item["observed_at"],
            "raw_sha256":item["raw_sha256"], "acquisition":item["acquisition"],
            "raw_snapshot_verified":item["raw_snapshot_verified"],
            "close":record["close"], "volume_shares":record["volume_shares"],
            "market":record.get("market"), "price_unit":record.get("price_unit"),
            "price_basis":record.get("price_basis"),
            **{key:record.get(key) for key in DEFINITION_KEYS}}


def _price_checks(items, sid, target, cutoff, config):
    price = _check("price_change", config["price_change_pct"], "abs(100 * (close / previous_observed_close - 1)) >= threshold; value keeps sign", target)
    volume = _check("volume_ratio", config["volume_ratio"], "volume_shares / mean(previous_N_observed_volumes)", target)
    if not target:
        price["reason"] = volume["reason"] = "price_input_not_requested"
        return [price, volume]
    known = {}
    for item in items:
        row = item["record"]
        day = iso_date(row["trade_date"])
        if timestamp(item["observed_at"]) > cutoff or day > iso_date(target):
            continue
        if row["symbol"] != sid[3:] or row["trade_date"] in known:
            raise ValueError("wrong stock or duplicate price date in alert history")
        if type(row.get("volume_shares")) is not int or row["volume_shares"] < 0:
            raise ValueError("invalid volume count")
        if row.get("close") is not None:
            number(row["close"])
        known[row["trade_date"]] = item
    ordered = [known[day] for day in sorted(known)]
    if target not in known:
        price["reason"] = volume["reason"] = "target_price_missing_at_cutoff"
        return [price, volume]
    current, prior = ordered[-1], ordered[:-1]
    for check, count in ((price, 1), (volume, config["volume_window"])):
        history = prior[-count:]
        used = history + [current]
        check["evidence"] = [_market_ref(row) for row in used]
        check["baseline"] = {"required_observations":count, "available_observations":len(history),
                             "dates":[row["record"]["trade_date"] for row in history],
                             "target_excluded":True, "exchange_sessions_verified":False}
        if len(history) < count:
            continue
        identities = {(r["source"]["source_id"], r["source"].get("dataset_url"), r["record"].get("market"),
                       *(r["record"].get(key) for key in DEFINITION_KEYS)) for r in used}
        if len(identities) != 1 or any(r.get("raw_snapshot_verified") is not True for r in used):
            check.update(status="not_comparable", reason="mixed_source_basis_or_unverified_snapshot")
            continue
        dates = [iso_date(r["record"]["trade_date"]) for r in used]
        if any((b-a).days > config["max_observation_gap_days"] for a,b in zip(dates, dates[1:])):
            check.update(status="not_comparable", reason="observation_gap_exceeds_policy")
            continue
        if check is price:
            a, b = history[-1]["record"]["close"], current["record"]["close"]
            if a is None or b is None or number(a) <= 0 or number(b) <= 0:
                check.update(status="not_comparable", reason="missing_or_nonpositive_close")
            else:
                _result(check, (number(b)/number(a)-1)*100, config["price_change_pct"])
        else:
            baseline = sum((number(r["record"]["volume_shares"]) for r in history), Decimal(0))/count
            check["baseline"]["mean_volume_shares"] = text_number(baseline)
            if baseline <= 0:
                check.update(status="not_comparable", reason="zero_volume_baseline")
            else:
                _result(check, number(current["record"]["volume_shares"])/baseline, config["volume_ratio"], absolute=False)
    return [price, volume]


def _month_key(day):
    parsed = iso_date(day)
    if parsed.day != calendar.monthrange(parsed.year, parsed.month)[1]:
        raise ValueError("monthly revenue period must be calendar month end")
    return parsed.year*12+parsed.month


def _revenue_checks(payload, sid, cutoff, config):
    selected = {}
    wanted = ("monthly_revenue", "monthly_revenue_yoy_pct", "monthly_revenue_mom_pct")
    sources = {s["source_id"]:s for s in payload.get("sources", [])}
    for metric in payload.get("financial_metrics", []):
        if metric["stock_id"] != sid or metric["metric"] not in wanted or metric.get("period_type") != "month":
            continue
        if max(timestamp(metric["available_at"]), timestamp(metric.get("registered_at", metric["available_at"]))) > cutoff:
            continue
        _month_key(metric["period_end"])
        if iso_date(metric["period_end"]) > cutoff.astimezone(ZoneInfo("Asia/Taipei")).date():
            raise ValueError("revenue period later than knowledge cutoff")
        number(metric["value"])
        key = (metric["metric"], metric["period_end"])
        if key in selected:
            raise ValueError("ambiguous revenue metric; replay revisions first")
        selected[key] = financial_definition(metric)
    latest = max((period for _, period in selected), default=None)
    def find(metric, month):
        return next((row for (kind,day),row in selected.items() if kind == metric and _month_key(day) == month), None)
    def ref(row):
        return {k:row.get(k) for k in ("source_id", "period_end", "metric", "value", "unit",
                "available_at", "registered_at", "input_snapshot_sha256", "normalization_version",
                "statement_scope", "report_basis", "currency")} | {
                    "source_url":sources.get(row["source_id"], {}).get("url")}
    yoy = _check("revenue_yoy", config["revenue_yoy_pct"], "abs(source_reported_yoy_percent) >= threshold", latest)
    mom = _check("revenue_mom", config["revenue_mom_pct"], "abs(source_reported_mom_percent) >= threshold", latest)
    delta = _check("revenue_yoy_change", config["revenue_yoy_change_pp"], "current_yoy_percent - previous_month_yoy_percent", latest)
    trend = _check("revenue_yoy_trend", config["revenue_trend_steps"], "N consecutive monthly changes in yoy, all > 0 or all < 0", latest)
    for check, kind, count in ((yoy, "monthly_revenue_yoy_pct", 1), (mom, "monthly_revenue_mom_pct", 1),
                              (delta, "monthly_revenue_yoy_pct", 2),
                              (trend, "monthly_revenue_yoy_pct", config["revenue_trend_steps"]+1)):
        key = _month_key(latest) if latest else 0
        rows = [find(kind, month) for month in range(key-count+1, key+1)] if latest else []
        check["evidence"] = [ref(r) for r in rows if r]
        check["baseline"] = {"required_months":count, "available_months":sum(r is not None for r in rows),
                             "consecutive_calendar_months_required":True}
        if len(rows) != count or any(r is None for r in rows):
            check["reason"] = "missing_consecutive_months_or_latest_percentage"
            continue
        source_ids = {r["source_id"] for r in rows}
        if len(source_ids) != 1 or any(r.get("unit") != "percent" or r["source_id"] not in sources for r in rows):
            check.update(status="not_comparable", reason="percentage_unit_or_source_mismatch")
            continue
        definitions = {tuple(r.get(k) for k in FINANCIAL_DEFINITION_KEYS) for r in rows}
        if len(definitions) != 1:
            check.update(status="not_comparable", reason="financial_definition_mismatch")
            continue
        values = [number(r["value"]) for r in rows]
        if check is trend:
            changes = [b-a for a,b in zip(values, values[1:])]
            direction = "increasing" if all(x > 0 for x in changes) else ("decreasing" if all(x < 0 for x in changes) else "mixed_or_flat")
            check.update(status="triggered" if direction != "mixed_or_flat" else "not_triggered",
                         reason=direction, value=str(count-1), direction=direction)
            check["baseline"]["changes_percentage_points"] = [text_number(x) for x in changes]
        else:
            _result(check, values[-1]-values[0] if check is delta else values[-1], check["threshold"])
    return [yoy, mom, delta, trend]


def evaluate(payload, price_history, stock_ids, known_at, *, trade_date=None, config=None):
    """Pure as-known report; price_history contains validated, dated raw observations."""
    config, cutoff = policy(config), timestamp(known_at)
    if trade_date and iso_date(trade_date) > cutoff.astimezone(ZoneInfo("Asia/Taipei")).date():
        raise ValueError("alert target trade date is after cutoff")
    result = {}
    for sid in sorted(stock_ids):
        checks = _price_checks(price_history.get(sid, []), sid, trade_date, cutoff, config)
        checks += _revenue_checks(payload, sid, cutoff, config)
        for check in checks:
            check["id"] = hashlib.sha256(canonical([VERSION, sid, known_at, config, check])).hexdigest()
        result[sid] = {"schema_version":VERSION, "stock_id":sid, "known_at":known_at,
            "config":config.copy(), "warnings":CAVEATS.copy(),
            "categories":{group:[c for c in checks if c["category"] == group]
                          for group in ("price_volume", "monthly_revenue")}}
        validate(result[sid], sid)
    return result


def validate(report, sid):
    """Reject malformed optional JSON extension before installing an export."""
    if not isinstance(report, dict) or report.get("schema_version") != VERSION or report.get("stock_id") != sid:
        raise ValueError("invalid research alert identity/version")
    cutoff = timestamp(report["known_at"])
    policy(report["config"])
    if report.get("warnings") != CAVEATS or set(report.get("categories", {})) != {"price_volume", "monthly_revenue"}:
        raise ValueError("invalid research alert categories/disclosure")
    seen = set()
    for group, checks in report["categories"].items():
        if not isinstance(checks, list):
            raise ValueError("alert checks must be a list")
        for check in checks:
            rule = check.get("rule_id")
            if rule not in RULES or rule in seen or RULES[rule][0] != group or check.get("category") != group:
                raise ValueError("invalid or duplicate alert rule")
            seen.add(rule)
            if check.get("status") not in STATUSES or not isinstance(check.get("reason"), str):
                raise ValueError("invalid alert status/reason")
            if check.get("status") in ("triggered", "not_triggered") and check.get("value") is None:
                raise ValueError("evaluated alert needs value")
            if check.get("value") is not None:
                number(check["value"])
            if check.get("target_period"):
                if iso_date(check["target_period"]) > cutoff.astimezone(ZoneInfo("Asia/Taipei")).date():
                    raise ValueError("future alert period")
            evidence = check.get("evidence")
            if not isinstance(evidence, list) or len(evidence) > 253:
                raise ValueError("invalid alert evidence")
            for row in evidence:
                for key in ("observed_at", "available_at", "registered_at"):
                    if row.get(key) and timestamp(row[key]) > cutoff:
                        raise ValueError("future alert evidence")
            facts = {k:v for k,v in check.items() if k != "id"}
            expected = hashlib.sha256(canonical([VERSION, sid, report["known_at"], report["config"], facts])).hexdigest()
            if check.get("id") != expected:
                raise ValueError("alert content hash mismatch")
    if seen != set(RULES):
        raise ValueError("missing research alert rules")
