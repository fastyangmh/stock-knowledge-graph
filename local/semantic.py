"""Lazy local multilingual encoder, SQLite vector cache and exact bounded Top-K.

Unchanged input reuses graph edges. Cached vectors use canonical float32 bytes
on both the first and subsequent runs. Model identity is backwards compatible;
pin a model commit revision for reproducible production use.
"""
from __future__ import annotations
import json
import math
import struct
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from .core import digest, now, upsert_edge
from .dates import timestamp
from .neighbors import top_k_pairs

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INPUT_VERSION = "title-content-v1"
ALGORITHM_VERSION = "bounded-topk-evidence-v2"


def normalized(values):
    vec = [float(x) for x in values]
    if not vec or any(not math.isfinite(x) for x in vec):
        raise ValueError("embedding contains non-finite values or is empty")
    norm = math.hypot(*vec)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("zero-length or invalid embedding")
    return [x/norm for x in vec]


def cosine(a, b):
    if len(a) != len(b):
        raise ValueError("vector dimensions differ")
    return math.fsum(x*y for x, y in zip(a, b))


def pack(vec):
    return struct.pack("<"+str(len(vec))+"f", *vec)


def unpack(blob, dim):
    if len(blob) != dim*4:
        raise ValueError("cached embedding dimension mismatch")
    return list(struct.unpack("<"+str(dim)+"f", blob))


def load_encoder(name, revision):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install the locked environment with uv sync --locked --extra dev") from exc
    return SentenceTransformer(name, revision=revision) if revision else SentenceTransformer(name)


@contextmanager
def _transaction(conn):
    conn.execute("SAVEPOINT semantic_refresh")
    try:
        yield
        conn.execute("RELEASE semantic_refresh")
    except BaseException:
        conn.execute("ROLLBACK TO semantic_refresh")
        conn.execute("RELEASE semantic_refresh")
        raise


def _edge_hash(conn, model_id):
    edges = [tuple(r) for r in conn.execute(
        "SELECT edge_id,source_id,target_id,relation_type,method,score,as_of "
        "FROM graph_edges WHERE model_id=? ORDER BY edge_id", (model_id,))]
    evidence = [tuple(r) for r in conn.execute(
        "SELECT e.edge_id,e.document_id FROM edge_evidence e JOIN graph_edges g "
        "ON g.edge_id=e.edge_id WHERE g.model_id=? ORDER BY e.edge_id,e.document_id", (model_id,))]
    return digest(json.dumps([edges, evidence], ensure_ascii=False, allow_nan=False))


def compute_semantic(conn, model_name=DEFAULT_MODEL, top_k=10, threshold=0.65,
                     batch_size=32, encoder=None, revision=None, *,
                     as_of=None, lookback_days=None, max_pairs=2_000_000):
    if type(top_k) is not int or top_k < 1 or type(batch_size) is not int or batch_size < 1:
        raise ValueError("top_k and batch_size must be positive integers")
    if not math.isfinite(threshold) or not -1 <= threshold <= 1 or not model_name.strip():
        raise ValueError("invalid threshold or model name")
    if lookback_days is not None and (type(lookback_days) is not int or lookback_days < 0):
        raise ValueError("lookback_days must be nonnegative")
    anchor = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    lower = anchor-timedelta(days=lookback_days) if lookback_days is not None else None
    config = json.dumps({"name":model_name,"revision":revision,"input_version":INPUT_VERSION},
                        sort_keys=True, ensure_ascii=False)
    model_id = "st:"+digest(config)[:24]
    previous = conn.execute("SELECT dimension,config_json FROM embedding_models WHERE model_id=?", (model_id,)).fetchone()
    if previous and previous["config_json"] != config:
        raise ValueError("model identity collision")
    docs = conn.execute("SELECT document_id,title,content,available_at FROM documents ORDER BY document_id").fetchall()
    all_ids = {"doc:"+r["document_id"] for r in docs}
    entries = []
    for row in docs:
        available = timestamp(row["available_at"])
        if available > anchor or (lower and available < lower):
            continue
        text = row["title"]+"\n"+row["content"]
        entries.append(("doc:"+row["document_id"], text, digest(INPUT_VERSION+"\n"+text)))
    pair_count = len(entries)*(len(entries)-1)//2
    if type(max_pairs) is not int or max_pairs < 0 or pair_count > max_pairs:
        raise ValueError(f"{pair_count} candidate pairs exceed budget {max_pairs}; use --lookback-days")
    existing = {r["node_id"]:r for r in conn.execute(
        "SELECT node_id,content_hash,vector FROM embeddings WHERE model_id=?", (model_id,))}
    dimension = int(previous["dimension"]) if previous else None
    vectors, changed = {}, []
    for nid, text, content_hash in entries:
        old = existing.get(nid)
        if old is not None and dimension and old["content_hash"] == content_hash:
            vectors[nid] = normalized(unpack(old["vector"], dimension))
        else:
            changed.append((nid, text, content_hash))
    # No model construction, import or download when all active vectors are cached.
    model_loaded = False
    if changed or (entries and dimension is None):
        if encoder is None:
            encoder = load_encoder(model_name, revision)
            model_loaded = True
        get_dimension = getattr(encoder, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = encoder.get_sentence_embedding_dimension
        actual = int(get_dimension())
        if actual <= 0 or (dimension is not None and dimension != actual):
            raise ValueError("model embedding dimension changed")
        dimension = actual
    active_ids = {entry[0] for entry in entries}
    links = [tuple(r) for r in conn.execute(
        "SELECT document_id,stock_id FROM document_stocks ORDER BY document_id,stock_id")
        if "doc:"+r["document_id"] in active_ids]
    fingerprint = digest(json.dumps({"algorithm":ALGORITHM_VERSION,"model":model_id,
        "entries":[(nid,h) for nid,_,h in entries],"links":links,"top_k":top_k,"threshold":threshold},
        sort_keys=True, ensure_ascii=False, allow_nan=False))
    conn.execute("""CREATE TABLE IF NOT EXISTS similarity_state(
        model_id TEXT PRIMARY KEY REFERENCES embedding_models(model_id),
        input_hash TEXT NOT NULL,edge_hash TEXT NOT NULL,stats_json TEXT NOT NULL)""")
    state = conn.execute("SELECT * FROM similarity_state WHERE model_id=?", (model_id,)).fetchone()
    if not changed and state and state["input_hash"] == fingerprint and state["edge_hash"] == _edge_hash(conn,model_id):
        stats = json.loads(state["stats_json"])
        return {**stats, "encoded":0, "cache_hits":len(entries), "model_loaded":False,
                "graph_reused":True, "pairs_evaluated":0, "retained_candidates":0}
    if dimension is None:
        return {"model_id":model_id,"documents":0,"cache_hits":0,"encoded":0,
                "document_pairs":0,"stock_pairs":0,"model_loaded":False,"graph_reused":False,
                "pairs_evaluated":0,"retained_candidates":0}
    with _transaction(conn):
        conn.execute("INSERT OR IGNORE INTO embedding_models(model_id,model_name,dimension,config_json) VALUES(?,?,?,?)",
                     (model_id,model_name,dimension,config))
        for start in range(0,len(changed),batch_size):
            batch = changed[start:start+batch_size]
            encoded = encoder.encode([x[1] for x in batch],batch_size=batch_size)
            if len(encoded) != len(batch):
                raise ValueError("encoder returned wrong batch size")
            for (nid,_,content_hash),raw in zip(batch,encoded):
                vec = normalized(raw)
                if len(vec) != dimension:
                    raise ValueError("encoder returned wrong vector dimension")
                blob = pack(vec)
                vectors[nid] = normalized(unpack(blob,dimension))
                conn.execute("""INSERT INTO embeddings(node_id,model_id,content_hash,vector,computed_at)
                    VALUES(?,?,?,?,?) ON CONFLICT(node_id,model_id) DO UPDATE SET
                    content_hash=excluded.content_hash,vector=excluded.vector,computed_at=excluded.computed_at""",
                    (nid,model_id,content_hash,blob,now()))
        # Old-window embeddings remain cached; only truly removed document entries are stale.
        for nid in set(existing)-all_ids:
            conn.execute("DELETE FROM embeddings WHERE node_id=? AND model_id=?", (nid,model_id))
        selected, counts = top_k_pairs(vectors,top_k,threshold,max_pairs=max_pairs)
        doc_stocks = {}
        for did,sid in links:
            doc_stocks.setdefault("doc:"+did,set()).add(sid)
        stock_scores, support = {}, {}
        for (a,b),score in selected.items():
            for sa in sorted(doc_stocks.get(a,())):
                for sb in sorted(doc_stocks.get(b,())):
                    if sa == sb:
                        continue
                    pair = tuple(sorted((sa,sb)))
                    if pair not in stock_scores or score > stock_scores[pair]:
                        stock_scores[pair] = score
                        support[pair] = [a.removeprefix("doc:"),b.removeprefix("doc:")]
        neighbors = {}
        for (a,b),score in stock_scores.items():
            neighbors.setdefault(a,[]).append((score,b))
            neighbors.setdefault(b,[]).append((score,a))
        stock_selected = set()
        for a,items in neighbors.items():
            for _,b in sorted(items,key=lambda item:(-item[0],item[1]))[:top_k]:
                stock_selected.add(tuple(sorted((a,b))))
        conn.execute("DELETE FROM edge_evidence WHERE edge_id IN (SELECT edge_id FROM graph_edges WHERE model_id=?)",(model_id,))
        conn.execute("DELETE FROM graph_edges WHERE model_id=?",(model_id,))
        for (a,b),score in selected.items():
            upsert_edge(conn,a,b,"semantic_similarity","sentence_transformers_cosine",round(score,6),model_id,
                        evidence=[a.removeprefix("doc:"),b.removeprefix("doc:")])
        for a,b in sorted(stock_selected):
            upsert_edge(conn,"stock:"+a,"stock:"+b,"semantic_similarity","selected_document_max_cosine",
                        round(stock_scores[(a,b)],6),model_id,evidence=support[(a,b)])
        stats = {"model_id":model_id,"documents":len(entries),"cache_hits":len(entries)-len(changed),
                 "encoded":len(changed),"document_pairs":len(selected),"stock_pairs":len(stock_selected),
                 "model_loaded":model_loaded,"graph_reused":False,**counts}
        conn.execute("""INSERT INTO similarity_state VALUES(?,?,?,?) ON CONFLICT(model_id) DO UPDATE SET
            input_hash=excluded.input_hash,edge_hash=excluded.edge_hash,stats_json=excluded.stats_json""",
            (model_id,fingerprint,_edge_hash(conn,model_id),json.dumps(stats,allow_nan=False)))
    return stats
