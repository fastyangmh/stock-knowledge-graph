"""Deterministic display-only graph pruning. Never deletes SQLite history."""
from datetime import datetime,timedelta,timezone

def prune(graph,max_information_nodes=100,max_related_stocks=15,max_semantic_per_node=5,news_days=None,as_of=None):
    if min(max_information_nodes,max_related_stocks,max_semantic_per_node)<0:
        raise ValueError("limits must be nonnegative")
    if news_days is not None and news_days<0:
        raise ValueError("news_days must be nonnegative")
    anchor=datetime.fromisoformat(as_of.replace("Z","+00:00")) if as_of else datetime.now(timezone.utc)
    if anchor.tzinfo is None:raise ValueError("as_of must include timezone")
    primary="stock:"+graph["stock_id"]
    nodes={n["id"]:n for n in graph["nodes"]}
    if primary not in nodes:raise ValueError("primary stock node missing")
    stock_neighbors=[]
    info=[]
    for n in graph["nodes"]:
        if n["id"]==primary:continue
        if n["type"]=="stock":
            stock_neighbors.append(n)
        else:
            if news_days is not None and n["type"]=="news":
                published=n.get("published_at")
                if published:
                    dt=datetime.fromisoformat(published.replace("Z","+00:00"))
                    if dt.tzinfo is None:raise ValueError("published_at requires timezone")
                    if dt>anchor or dt<anchor-timedelta(days=news_days):continue
            info.append(n)
    def score(n):
        edges=[e for e in graph["edges"] if e["source"]==n["id"] or e["target"]==n["id"]]
        return max((e.get("score") or 0 for e in edges),default=0)
    info.sort(key=lambda n:(-score(n),n["id"]))
    stock_neighbors.sort(key=lambda n:(-score(n),n["id"]))
    keep={primary}|{n["id"] for n in info[:max_information_nodes]}|{n["id"] for n in stock_neighbors[:max_related_stocks]}
    edges=[]
    degree={}
    for e in sorted(graph["edges"],key=lambda e:(-(e.get("score") or 0),e.get("id",""))):
        a,b=e["source"],e["target"]
        if a not in keep or b not in keep:continue
        if e["relation"] in ("semantic_similarity","lexical_similarity"):
            if degree.get(a,0)>=max_semantic_per_node or degree.get(b,0)>=max_semantic_per_node:
                continue
            degree[a]=degree.get(a,0)+1
            degree[b]=degree.get(b,0)+1
        edges.append(e)
    return {**graph,"nodes":[n for n in graph["nodes"] if n["id"] in keep],
            "edges":sorted(edges,key=lambda e:e.get("id",""))}
