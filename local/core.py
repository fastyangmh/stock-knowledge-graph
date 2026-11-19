"""SQLite initialization, import and graph materialization. Python 3.10+; no external dependencies."""
import hashlib
import json
import math
from .dates import iso_date, timestamp
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "local" / "stock_graph.db"
SCHEMA = Path(__file__).with_name("schema.sql")

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db(conn):
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def upsert_node(conn, node_id, kind, label, stock_id=None, document_id=None, props=None):
    conn.execute("""INSERT INTO graph_nodes(node_id,node_type,label,stock_id,document_id,properties_json,updated_at)
    VALUES(?,?,?,?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET
    node_type=excluded.node_type,label=excluded.label,stock_id=excluded.stock_id,
    document_id=excluded.document_id,properties_json=excluded.properties_json,updated_at=excluded.updated_at""",
    (node_id,kind,label,stock_id,document_id,json.dumps(props or {},ensure_ascii=False),now()))

def upsert_edge(conn, source, target, relation, method="explicit", score=None, model_id=None, evidence=None):
    if source == target:
        return
    edge_id = digest("|".join((source,target,relation,method,model_id or "")))[:32]
    conn.execute("""INSERT INTO graph_edges(edge_id,source_id,target_id,relation_type,method,score,model_id,as_of)
    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(edge_id) DO UPDATE SET
    score=excluded.score,as_of=excluded.as_of""",
    (edge_id,source,target,relation,method,score,model_id,now()))
    for doc in evidence or []:
        conn.execute("INSERT OR IGNORE INTO edge_evidence(edge_id,document_id) VALUES(?,?)",(edge_id,doc))

def import_payload(conn, payload):
    """Import explicit, normalized JSON records; idempotent by primary keys."""
    for d in payload.get("documents",[]):
        timestamp(d["published_at"])
        timestamp(d.get("available_at",d["published_at"]))
    for group in ("financial_metrics","chip_metrics"):
        for record in payload.get(group,[]):
            value=record["value"]
            if type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError("Financial values must be finite numbers, not booleans")
            iso_date(record["period_end"] if group=="financial_metrics" else record["trade_date"])
            if group=="financial_metrics":
                timestamp(record["available_at"])
    for s in payload.get("stocks",[]):
        sid=s["stock_id"]
        conn.execute("""INSERT INTO stocks(stock_id,ticker,market,name,industry,updated_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(stock_id) DO UPDATE SET name=excluded.name,industry=excluded.industry,updated_at=excluded.updated_at""",
        (sid,s["ticker"],s["market"],s["name"],s.get("industry"),now()))
        upsert_node(conn,"stock:"+sid,"stock",s["name"],sid,props={"ticker":s["ticker"],"industry":s.get("industry"),**{k:s[k] for k in ("source_id","source_url","license_url","attribution","provider","raw_sha256","row_number","source_column","universe_ids","universe_memberships","universe_group","universe_as_of") if k in s}})
    for s in payload.get("sources",[]):
        conn.execute("""INSERT INTO sources(source_id,provider,url,license_type) VALUES(?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET provider=excluded.provider,url=excluded.url,license_type=excluded.license_type""",
        (s["source_id"],s["provider"],s.get("url"),s.get("license_type")))
    for d in payload.get("documents",[]):
        content=d.get("content","")
        conn.execute("""INSERT INTO documents(document_id,source_id,external_id,doc_type,title,content,published_at,available_at,ingested_at,content_hash)
        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET
        title=excluded.title,content=excluded.content,published_at=excluded.published_at,
        available_at=CASE WHEN documents.content_hash=excluded.content_hash THEN documents.available_at ELSE excluded.available_at END,
        source_id=excluded.source_id,external_id=excluded.external_id,doc_type=excluded.doc_type,
        content_hash=excluded.content_hash""",
        (d["document_id"],d.get("source_id"),d.get("external_id"),d["doc_type"],d["title"],content,
         d["published_at"],d.get("available_at",d["published_at"]),now(),digest(d["title"]+"\n"+content)))
        did=d["document_id"]
        available=conn.execute("SELECT available_at FROM documents WHERE document_id=?",(did,)).fetchone()[0]
        props={"published_at":d["published_at"],"available_at":available,"description":content[:240],"source_id":d.get("source_id")}
        for key in ("source_url","license_url","attribution","period_end","unit","availability_basis","source_report_date","registered_at","input_snapshot_sha256"):
            if key in d:
                props[key]=d[key]
        if d["doc_type"] == "industry_report":
            for key in ("industry", "relation_basis", "raw_sha256", "source_column", "row_number"):
                if key in d:
                    props[key] = d[key]
        upsert_node(conn,"doc:"+did,d["doc_type"],d["title"],document_id=did,props=props)
        # A provided stock_ids list replaces that document's links; an absent field preserves them.
        if "stock_ids" in d:
            conn.execute("DELETE FROM document_stocks WHERE document_id=?",(did,))
            conn.execute("DELETE FROM edge_evidence WHERE edge_id IN (SELECT edge_id FROM graph_edges WHERE target_id=? AND relation_type='contains' AND method='explicit')",("doc:"+did,))
            conn.execute("DELETE FROM graph_edges WHERE target_id=? AND relation_type='contains' AND method='explicit'",("doc:"+did,))
        for sid in d.get("stock_ids",[]):
            conn.execute("INSERT OR IGNORE INTO document_stocks(document_id,stock_id) VALUES(?,?)",(did,sid))
            upsert_edge(conn,"stock:"+sid,"doc:"+did,"contains",evidence=[did])
    for m in payload.get("financial_metrics",[]):
        conn.execute("""INSERT INTO financial_metrics(stock_id,metric,period_end,period_type,value,unit,available_at)
        VALUES(?,?,?,?,?,?,?) ON CONFLICT(stock_id,metric,period_end,period_type) DO UPDATE SET
        available_at=CASE WHEN financial_metrics.value=excluded.value AND financial_metrics.unit IS excluded.unit
        THEN financial_metrics.available_at ELSE excluded.available_at END,
        value=excluded.value,unit=excluded.unit""",
        (m["stock_id"],m["metric"],m["period_end"],m["period_type"],m["value"],m.get("unit"),m["available_at"]))
    for m in payload.get("chip_metrics",[]):
        conn.execute("""INSERT INTO chip_metrics(stock_id,trade_date,metric,value,unit) VALUES(?,?,?,?,?)
        ON CONFLICT(stock_id,trade_date,metric) DO UPDATE SET value=excluded.value,unit=excluded.unit""",
        (m["stock_id"],m["trade_date"],m["metric"],m["value"],m.get("unit")))
    # The caller owns the transaction: keep imports atomic with later pipeline steps.
