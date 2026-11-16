"""Atomic-ish JSON export with endpoint closure and validation."""
import json
import os
import tempfile
import shutil
import re
import math
import uuid
import hashlib
from .view_metadata import membership_summary, universe_counts
from .safety import exclusive_lock
from pathlib import Path
from .core import ROOT, now
from .lifecycle import prune

def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as tmp:
        json.dump(data,tmp,ensure_ascii=False,indent=2,allow_nan=False)
        tmp.write("\n")
        name=tmp.name
    os.replace(name,path)

def export(conn, output=None, universe=None, lifecycle=False, as_of=None):
    output=Path(output) if output else ROOT/"data"
    destination=output.resolve()
    if output.is_symlink() or destination==ROOT or ROOT.is_relative_to(destination):
        raise ValueError("Unsafe export directory")
    if destination.is_relative_to(ROOT) and not (destination==ROOT/"data" or destination.is_relative_to(ROOT/"local"/"private")):
        raise ValueError("Exports inside the project must use data/ or local/private/")
    with exclusive_lock(destination):
        if output.exists():
            if not output.is_dir():
                raise ValueError("Output must be a directory")
            for item in output.rglob("*"):
                if item.is_symlink():
                    raise ValueError("Symlinks are not allowed in exports")
                if item.is_file():
                    relative=item.relative_to(output).as_posix()
                    if relative!="manifest.json" and not re.fullmatch(r"stocks/[A-Za-z0-9_.-]+/graph\.json", relative):
                        raise ValueError("Refusing to replace unrelated file: "+relative)
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".stock-graph-stage-",dir=output.parent) as staging:
            return _export(conn, output, universe, lifecycle, Path(staging), as_of)

def _export(conn, output, universe, lifecycle, stage_root, as_of):
    output=Path(output) if output else ROOT/"data"
    if output.resolve()==ROOT.resolve() or output.resolve()==(ROOT/'local').resolve():
        raise ValueError('Unsafe export directory')
    stocks=conn.execute("SELECT stock_id,ticker,market,name FROM stocks ORDER BY market,ticker").fetchall()
    if universe is not None:
        stocks=[s for s in stocks if s["stock_id"] in universe]
    if not stocks:
        raise ValueError("No stocks selected for export")
    if universe is not None and {s["stock_id"] for s in stocks} != set(universe):
        raise ValueError("Universe contains stocks missing from SQLite; refuse partial export")
    node_rows={r["node_id"]:dict(r) for r in conn.execute("SELECT * FROM graph_nodes")}
    edges=[dict(r) for r in conn.execute("SELECT * FROM graph_edges ORDER BY edge_id")]
    evidence={}
    for row in conn.execute("SELECT edge_id,document_id FROM edge_evidence ORDER BY edge_id,document_id"):
        evidence.setdefault(row["edge_id"],[]).append(row["document_id"])
    source_rows={r["source_id"]:dict(r) for r in conn.execute("SELECT * FROM sources")}
    used_sources=set()
    stock_docs={}
    for r in conn.execute("SELECT stock_id,document_id FROM document_stocks"):
        stock_docs.setdefault(r["stock_id"],set()).add("doc:"+r["document_id"])
    # Generate a complete replacement in a temporary sibling directory first.
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=stage_root/"data"
    stage.mkdir()
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
                              "as_of":e["as_of"], "model_id":e["model_id"],
                              "evidence_ids":evidence.get(e["edge_id"],[])})
        graph={"schema_version":"1.0","stock_id":sid,"generated_at":now(),"nodes":nodes,"edges":out_edges}
        if lifecycle:
            graph=prune(graph,max_information_nodes=100,max_related_stocks=15,max_semantic_per_node=5,news_days=90,as_of=as_of)
        validate_graph(graph)
        for node in graph["nodes"]:
            if node.get("source_id") in source_rows:
                used_sources.add(node["source_id"])
        # Market-specific subfolders avoid collisions for equal tickers across exchanges.
        folder=s["ticker"] if s["market"]=="TW" else s["market"]+"-"+s["ticker"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",folder) or folder in (".",".."):
            raise ValueError("Unsafe stock output path")
        relative=f"stocks/{folder}/graph.json"
        write_json(stage/relative,graph)
        primary=next(n for n in graph["nodes"] if n["id"]=="stock:"+sid)
        summary=membership_summary(primary)
        manifest["stocks"].append({"stock_id":sid,"ticker":s["ticker"],
            "label":s["ticker"]+" "+s["name"],"path":"data/"+relative,
            "node_count":len(graph["nodes"]),"edge_count":len(graph["edges"]),
            "sha256":hashlib.sha256((stage/relative).read_bytes()).hexdigest(),**summary})
    manifest["research_universe"]={"counts":universe_counts(manifest["stocks"]),
        "as_of_dates":sorted({s["universe_as_of"] for s in manifest["stocks"] if "universe_as_of" in s}),
        "scope":"exported primary stock graphs only; not a certified index or current holdings list"}
    manifest["sources"]=[source_rows[sid] for sid in sorted(used_sources)]
    write_json(stage/"manifest.json",manifest)
    # Validate staged tree before touching current public data.
    from .validate_release import validate_release
    validate_release(stage_root)
    backup=output.with_name(".stock-graph-backup-"+uuid.uuid4().hex)
    try:
        if output.exists():
            output.rename(backup)
        stage.rename(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.rename(output)
        raise
    else:
        if backup.exists():shutil.rmtree(backup)
    return manifest

def validate_graph(graph):
    if not isinstance(graph,dict) or not isinstance(graph.get("nodes"),list) or not isinstance(graph.get("edges"),list):
        raise ValueError("graph requires nodes and edges arrays")
    if any(not isinstance(n,dict) or not isinstance(n.get("id"),str) or not n["id"] for n in graph["nodes"]):
        raise ValueError("node id must be a nonempty string")
    ids=[n["id"] for n in graph["nodes"]]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate node ids")
    idset=set(ids)
    edge_ids=set()
    for edge in graph["edges"]:
        if not isinstance(edge,dict) or not all(isinstance(edge.get(k),str) and edge[k] for k in ("id","source","target","relation")):
            raise ValueError("edge requires nonempty id,source,target,relation")
        if edge["source"]==edge["target"]:
            raise ValueError("self-loop is not allowed")
        if edge["source"] not in idset or edge["target"] not in idset:
            raise ValueError("edge endpoint missing: "+edge["id"])
        if edge["id"] in edge_ids or edge["id"] in idset:raise ValueError("duplicate graph element id")
        edge_ids.add(edge["id"])
        score=edge.get("score")
        if score is not None and (type(score) not in (int,float) or not math.isfinite(score) or not -1<=score<=1):
            raise ValueError("invalid cosine score")
