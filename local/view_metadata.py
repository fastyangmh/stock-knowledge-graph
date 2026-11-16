"""Small, validated display metadata. Membership is an observation, not permission.

Missing metadata stays unknown; never infer TW50 from ticker, name or ETF size.
This optional manifest extension keeps existing schema_version=1.0 files usable.
"""
from .combined_universe import TW50, ETF, _source_url
from .dates import iso_date

FIELDS = ("universe_ids", "universe_group", "universe_as_of")


def membership_summary(node):
    present = [key in node for key in (*FIELDS, "universe_memberships")]
    if not any(present):
        return {}
    if not all(present):
        raise ValueError("Incomplete universe metadata; do not infer missing membership")
    ids = node["universe_ids"]
    if (not isinstance(ids, list) or not ids or any(x not in (TW50, ETF) for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Invalid universe_ids")
    group = "both" if len(ids) == 2 else ("tw50_only" if ids[0] == TW50 else "etf_009816_only")
    if node["universe_group"] != group:
        raise ValueError("Universe group differs from source IDs")
    as_of = node["universe_as_of"]
    target = iso_date(as_of)
    rows = node["universe_memberships"]
    if not isinstance(rows, list) or len(rows) != len(ids):
        raise ValueError("Membership evidence is incomplete")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid membership evidence")
        kind = row.get("universe_id")
        if kind not in ids or kind in seen:
            raise ValueError("Membership evidence differs from IDs")
        seen.add(kind)
        _source_url(row.get("source_url"))
        start = iso_date(row.get("effective_from"))
        end = iso_date(row.get("effective_to") or "9999-12-31")
        if not start <= target <= end:
            raise ValueError("Membership outside its effective interval")
        if kind == ETF:
            if (row.get("membership_kind") != "etf_holding"
                    or row.get("snapshot_date") != as_of or start != target or end != target):
                raise ValueError("ETF membership must be the exact same-day snapshot")
        elif row.get("membership_kind") != "index_constituent":
            raise ValueError("TW50 evidence must be index_constituent")
    return {"universe_ids": sorted(ids), "universe_group": group, "universe_as_of": as_of}


def universe_counts(stocks):
    counts = dict(total=len(stocks), tw50=0, etf_009816=0, both=0,
                  tw50_only=0, etf_009816_only=0, unknown=0)
    for stock in stocks:
        group = stock.get("universe_group", "unknown")
        if group not in ("both", "tw50_only", "etf_009816_only", "unknown"):
            raise ValueError("Unknown universe group")
        counts[group] += 1
        counts["tw50"] += group in ("both", "tw50_only")
        counts["etf_009816"] += group in ("both", "etf_009816_only")
    return counts
