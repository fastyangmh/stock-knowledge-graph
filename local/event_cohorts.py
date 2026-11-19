"""Descriptive follow-up windows in saved research time."""
from bisect import bisect_left, bisect_right
from collections import defaultdict

from .dates import timestamp
from .market_notices import activation


def attach_windows(events, analysis_at):
    """Count distinct same-stock windows intersecting each closed capture interval.

    UTC timestamps are normalized by analyze/saved_facts. Use sorted endpoints
    to count intersections without materializing a quadratic list of event pairs.
    """
    windows = defaultdict(list)
    for event in events:
        for row in event["outcomes"]:
            censored = (row["status"] == "pending" or
                        row["reason"] == "not_enough_saved_post_event_quotes_not_verified_sessions")
            if row["followup"] is not None:
                end = row.get("sequence_known_at", row["followup"]["captured_at"])
            elif censored or row["reason"] == "target_month_not_saved_no_nearest_month_fill":
                end = analysis_at
            else:
                # Missing/incompatible at baseline: no interpretable follow-up interval.
                end = None
            window = {"start_at": event["event_at"], "end_at": end, "right_censored": censored,
                      "same_stock_overlapping_events": None}
            row["followup_window"] = window
            if end is not None:
                windows[event["stock_id"], row["metric"], row["horizon"]].append(window)

    for rows in windows.values():
        intervals = [(timestamp(w["start_at"]), timestamp(w["end_at"])) for w in rows]
        starts = sorted(start for start, _ in intervals)
        ends = sorted(end for _, end in intervals)
        for window, (start, end) in zip(rows, intervals):
            window["same_stock_overlapping_events"] = bisect_right(starts, end) - bisect_left(ends, start) - 1


def input_coverage(bundle, stock_ids, facts_by_run):
    """Observed ranges in this saved selection, including runs without a trigger."""
    run = bundle.report["run"]
    markets, revenue = defaultdict(set), defaultdict(set)
    for stock_id in stock_ids:
        for fact in facts_by_run[run, stock_id]:
            if fact["metric"] == "market":
                markets[fact["market"] or "unknown"].add(fact["period"])
            else:
                revenue[fact["metric"]].add(fact["period"])

    def ranges(periods):
        return {key: {"first": min(days), "last": max(days), "distinct_dates": len(days)}
                for key, days in sorted(periods.items())}

    selection = bundle.report.get("selection", {})
    quality = bundle.report.get("quality", {})
    notices = []
    cutoff = timestamp(bundle.report["known_at"])
    for entry in quality.get("market_notices", []):
        notice = entry["notice"]
        notices.append({**{k: notice[k] for k in ("market", "symbol", "trade_date", "action", "effective_at")},
                        "notice_sha256": entry["notice_sha256"], "recorded_at": entry["recorded_at"],
                        "effective_by_run_cutoff": activation(entry) <= cutoff})
    return {"market_notices": notices,
            "selection": {"mode": selection.get("mode", "unknown"), "stock_ids": sorted(stock_ids),
                          "index_membership_inferred": selection.get("index_membership_inferred")},
            "saved_periods": {"market": ranges(markets), "monthly_revenue": ranges(revenue)}}
