"""Atomic-ish JSON export with endpoint closure and validation."""
import json
import os
import tempfile
from pathlib import Path
from .core import ROOT, now

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as tmp:
        json.dump(data,tmp,ensure_ascii=False,indent=2,allow_nan=False)
        tmp.write("\n")
        name=tmp.name
    os.replace(name,path)

def export(conn, output=None):
    output=Path(output) if output else ROOT/"data"
    stocks=conn.execute("SELECT stock_id,ticker,market,name FROM stocks ORDER BY market,ticker").fetchall()
    node_rows={r["node_id"]:dict(r) for r in conn.execute("SELECT * FROM graph_nodes")}
    edges=[dict(r) for r in conn.execute("SELECT * FROM graph_edges ORDER BY edge_id")]
    stock_docs={}
    for r in conn.execute("SELECT stock_id,document_id FROM document_stocks"):
        stock_docs.setdefault(r["stock_id"],set()).add("doc:"+r["document_id"])
    manifest={"schema_version":"1.0","version":now(),"generated_at":now(),"stocks":[]}
    for s in stocks:
        sid=s["stock_id"]
        own={"stock:"+sid}|stock_docs.get(sid,set())
        # Also include neighbors of owned nodes, and their endpoint nodes.
        selected=[e for e in edges if e["source_id"] in own or e["target_id"] in own]
        ids=set(own)
        for e in selected:
            ids.add(e["source_id"]);ids.add(e["target_id"])
        nodes=[]
        for nid in sorted(ids):
            if nid not in node_rows:raise ValueError("missing node "+nid)
            n=node_rows[nid]
            props=json.loads(n["properties_json"])
            # Prevent arbitrary properties from overwriting required identifiers.
            props={k:v for k,v in props.items() if k not in ("id","label","type")}
            nodes.append({"id":nid,"label":n["label"],"type":n["node_type"],**props})
        out_edges=[]
        for e in selected:
            out_edges.append({"id":e["edge_id"],"source":e["source_id"],"target":e["target_id"],
                              "relation":e["relation_type"],"score":e["score"],"method":e["method"],
                              "as_of":e["as_of"]})
        graph={"schema_version":"1.0","stock_id":sid,"generated_at":now(),"nodes":nodes,"edges":out_edges}
        validate_graph(graph)
        # Market-specific subfolders avoid collisions for equal tickers across exchanges.
        folder=s["ticker"] if s["market"]=="TW" else s["market"]+"-"+s["ticker"]
        relative=f"stocks/{folder}/graph.json"
        write_json(output/relative,graph)
        manifest["stocks"].append({"label":s["ticker"]+" "+s["name"],"path":"data/"+relative})
    write_json(output/"manifest.json",manifest)
    return manifest

def validate_graph(graph):
    ids=[n["id"] for n in graph["nodes"]]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate node ids")
    idset=set(ids)
    edge_ids=set()
    for edge in graph["edges"]:
        if edge["source"] not in idset or edge["target"] not in idset:
            raise ValueError("edge endpoint missing: "+edge["id"])
        if edge["id"] in edge_ids:raise ValueError("duplicate edge id")
        edge_ids.add(edge["id"])
        score=edge.get("score")
        if score is not None and not -1<=score<=1:raise ValueError("invalid cosine score")
