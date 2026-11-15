"""Local multilingual sentence-transformers embeddings with SQLite cache.

No model download or heavy import occurs until compute_semantic() is called.
"""
import hashlib
import json
import math
import struct

from .core import digest, now, upsert_edge

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INPUT_VERSION = "title-content-v1"

def normalized(values):
    vec = [float(x) for x in values]
    if not vec or any(not math.isfinite(x) for x in vec):
        raise ValueError("embedding contains non-finite values or is empty")
    norm = math.sqrt(sum(x*x for x in vec))
    if norm == 0:
        raise ValueError("zero-length embedding")
    return [x/norm for x in vec]

def cosine(a,b):
    if len(a) != len(b):
        raise ValueError("vector dimensions differ")
    return sum(x*y for x,y in zip(a,b))

def pack(vec):
    return struct.pack("<"+str(len(vec))+"f",*vec)

def unpack(blob,dim):
    if len(blob) != dim*4:
        raise ValueError("cached embedding dimension mismatch")
    return list(struct.unpack("<"+str(dim)+"f",blob))

def compute_semantic(conn, model_name=DEFAULT_MODEL, top_k=10, threshold=0.65,
                     batch_size=32, encoder=None, revision=None):
    """Incrementally encode changed documents, then rebuild this model's graph edges.

    encoder is an optional injected object with encode(texts, batch_size=...).
    For production, supply a pinned model revision for reproducibility.
    """
    if top_k < 1 or batch_size < 1 or not -1 <= threshold <= 1:
        raise ValueError("invalid top_k, batch_size or threshold")
    if not model_name.strip():
        raise ValueError("model_name must be nonempty")
    if encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install local/requirements-embedding.txt to use semantic embeddings") from exc
        encoder = SentenceTransformer(model_name, revision=revision) if revision else SentenceTransformer(model_name)
    dimension = int(encoder.get_sentence_embedding_dimension())
    if dimension <= 0:
        raise ValueError("invalid model embedding dimension")
    # Revision is part of identity so cache cannot silently cross pinned revisions.
    config = json.dumps({"name":model_name,"revision":revision,"input_version":INPUT_VERSION},
                        sort_keys=True,ensure_ascii=False)
    model_id = "st:"+digest(config)[:24]
    previous = conn.execute("SELECT dimension,config_json FROM embedding_models WHERE model_id=?",(model_id,)).fetchone()
    if previous and (previous["dimension"] != dimension or previous["config_json"] != config):
        raise ValueError("model identity collision or dimension changed")
    conn.execute("INSERT OR IGNORE INTO embedding_models(model_id,model_name,dimension,config_json) VALUES(?,?,?,?)",
                 (model_id,model_name,dimension,config))
    docs = conn.execute("SELECT document_id,title,content FROM documents ORDER BY document_id").fetchall()
    entries = [("doc:"+r["document_id"],r["title"]+"\n"+r["content"]) for r in docs]
    existing = {r["node_id"]:r for r in conn.execute(
        "SELECT node_id,content_hash,vector FROM embeddings WHERE model_id=?",(model_id,))}
    vectors = {}
    changed = []
    for nid,text in entries:
        h = digest(INPUT_VERSION+"\n"+text)
        old = existing.get(nid)
        if old is not None and old["content_hash"] == h:
            vectors[nid] = normalized(unpack(old["vector"],dimension))
        else:
            changed.append((nid,text,h))
    for start in range(0,len(changed),batch_size):
        batch = changed[start:start+batch_size]
        encoded = encoder.encode([x[1] for x in batch],batch_size=batch_size)
        if len(encoded) != len(batch):
            raise ValueError("encoder returned wrong batch size")
        for (nid,text,h),raw in zip(batch,encoded):
            vec = normalized(raw)
            if len(vec) != dimension:
                raise ValueError("encoder returned wrong vector dimension")
            vectors[nid] = vec
            conn.execute("""INSERT INTO embeddings(node_id,model_id,content_hash,vector,computed_at)
                VALUES(?,?,?,?,?) ON CONFLICT(node_id,model_id) DO UPDATE SET
                content_hash=excluded.content_hash,vector=excluded.vector,computed_at=excluded.computed_at""",
                (nid,model_id,h,pack(vec),now()))
    # Remove cached entries for documents no longer present.
    stale = set(existing)-set(vectors)
    for nid in stale:
        conn.execute("DELETE FROM embeddings WHERE node_id=? AND model_id=?",(nid,model_id))
    # Exact candidate scan for MVP; not ANN. Symmetric Top-K union, deterministic ties.
    ids = sorted(vectors)
    neighbors = {}
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            score = max(-1.0,min(1.0,cosine(vectors[a],vectors[b])))
            if score >= threshold:
                neighbors.setdefault(a,[]).append((score,b))
                neighbors.setdefault(b,[]).append((score,a))
    selected = {}
    for a,vals in neighbors.items():
        for score,b in sorted(vals,key=lambda x:(-x[0],x[1]))[:top_k]:
            pair = tuple(sorted((a,b)))
            selected[pair] = score
    doc_stocks = {}
    for r in conn.execute("SELECT document_id,stock_id FROM document_stocks"):
        doc_stocks.setdefault("doc:"+r["document_id"],set()).add(r["stock_id"])
    stock_scores = {}
    for (a,b),score in selected.items():
        for sa in doc_stocks.get(a,set()):
            for sb in doc_stocks.get(b,set()):
                if sa != sb:
                    key = tuple(sorted((sa,sb)))
                    stock_scores[key] = max(stock_scores.get(key,-1.0),score)
    stock_neighbors = {}
    for (a,b),score in stock_scores.items():
        stock_neighbors.setdefault(a,[]).append((score,b))
        stock_neighbors.setdefault(b,[]).append((score,a))
    stock_selected = set()
    for a,vals in stock_neighbors.items():
        for score,b in sorted(vals,key=lambda x:(-x[0],x[1]))[:top_k]:
            stock_selected.add(tuple(sorted((a,b))))
    # Only replace graph edges after all embeddings and candidates succeed.
    conn.execute("DELETE FROM edge_evidence WHERE edge_id IN (SELECT edge_id FROM graph_edges WHERE model_id=?)",(model_id,))
    conn.execute("DELETE FROM graph_edges WHERE model_id=?",(model_id,))
    for (a,b),score in sorted(selected.items()):
        upsert_edge(conn,a,b,"semantic_similarity","sentence_transformers_cosine",round(score,6),model_id)
    for a,b in sorted(stock_selected):
        upsert_edge(conn,"stock:"+a,"stock:"+b,"semantic_similarity","document_max_cosine",round(stock_scores[(a,b)],6),model_id)
    conn.commit()
    return {"model_id":model_id,"documents":len(entries),"cache_hits":len(entries)-len(changed),
            "encoded":len(changed),"document_pairs":len(selected),"stock_pairs":len(stock_selected)}
