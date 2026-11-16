"""Display-only bounded subgraphs. Never deletes SQLite history.

Information-node caps apply separately from related-stock caps. Missing dates
are excluded when applying a dated news window. This is not a historical DB.
"""
from datetime import datetime, timedelta, timezone
from .dates import timestamp


def prune(graph, max_information_nodes=100, max_related_stocks=15,
          max_semantic_per_node=5, news_days=None, as_of=None):
    limits = (max_information_nodes, max_related_stocks, max_semantic_per_node)
    if any(type(n) is not int or n < 0 for n in limits):
        raise ValueError("limits must be nonnegative integers")
    if news_days is not None and (type(news_days) is not int or news_days < 0):
        raise ValueError("news_days must be nonnegative")
    anchor = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    primary = "stock:"+graph["stock_id"]
    nodes = {n["id"]:n for n in graph["nodes"]}
    if primary not in nodes:
        raise ValueError("primary stock node missing")
    information, stocks, scores = [], [], {}
    for edge in graph["edges"]:
        score = edge.get("score") if edge.get("score") is not None else 0
        for nid in (edge["source"], edge["target"]):
            scores[nid] = max(scores.get(nid, -1), score)
    for node in graph["nodes"]:
        if node["id"] == primary:
            continue
        # A source's report period/date is not its publication availability.
        available = node.get("available_at") or node.get("published_at")
        observed = timestamp(available) if available else None
        if observed and observed > anchor:
            continue
        if node["type"] == "stock":
            stocks.append(node)
        else:
            if news_days is not None and node["type"] == "news":
                if observed is None or observed < anchor-timedelta(days=news_days):
                    continue
            information.append(node)
    def order(node):
        return (-scores.get(node["id"], 0), node["id"])
    information.sort(key=order)
    # Reserve up to ten slots WITHIN the existing information cap for the
    # primary stock's latest structured observations. Pure fact edges have no
    # cosine score and would otherwise always lose against scored documents.
    direct = {e["target"] for e in graph["edges"] if e["source"] == primary}
    structured = [n for n in information if n["id"] in direct and n["type"] in ("market_price", "financial_metric")]
    structured.sort(key=lambda n:(n.get("trade_date", n.get("period_end", "")),
                                  n.get("available_at", ""), n["id"]), reverse=True)
    # Only the most recent market node needs a reserved slot; older ones can
    # still compete under the normal cap. This is display policy, not a signal.
    quotes = [n for n in structured if n["type"] == "market_price"][:1]
    metrics = [n for n in structured if n["type"] == "financial_metric"][:9]
    reserved = (quotes + metrics)[:min(10, max_information_nodes)]
    reserved_ids = {n["id"] for n in reserved}
    information = reserved + [n for n in information if n["id"] not in reserved_ids]
    stocks.sort(key=order)
    keep = {primary} | {n["id"] for n in information[:max_information_nodes]} | {n["id"] for n in stocks[:max_related_stocks]}
    edges, degree = [], {}
    for edge in sorted(graph["edges"], key=lambda e:(-(e.get("score") or 0),e.get("id",""))):
        a, b = edge["source"], edge["target"]
        if a not in keep or b not in keep:
            continue
        if edge.get("as_of") and timestamp(edge["as_of"]) > anchor:
            continue
        if edge["relation"] in ("semantic_similarity", "lexical_similarity"):
            endpoints = [nid for nid in (a,b) if nodes[nid]["type"] != "stock"]
            if any(degree.get(nid,0) >= max_semantic_per_node for nid in endpoints):
                continue
            for nid in endpoints:
                degree[nid] = degree.get(nid,0)+1
        edges.append(edge)
    # Do not fill the quota with isolated nodes after a connecting edge is pruned.
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["source"],set()).add(edge["target"])
        adjacency.setdefault(edge["target"],set()).add(edge["source"])
    reachable, pending = {primary}, [primary]
    while pending:
        for other in adjacency.get(pending.pop(), ()):
            if other not in reachable:
                reachable.add(other)
                pending.append(other)
    return {**graph,"nodes":[n for n in graph["nodes"] if n["id"] in reachable],
            "edges":sorted([e for e in edges if e["source"] in reachable and e["target"] in reachable], key=lambda e:e.get("id",""))}
