"""Offline similarity. Default lexical vectors are a reproducible demo baseline, NOT semantic embeddings."""
import hashlib
import math
import re
import sqlite3
import struct
from .core import digest, now, upsert_edge
from .neighbors import top_k_pairs

MODEL_ID = "lexical-hash-v1"
DIM = 256

def vectorize(text, dim=DIM):
    # Character bigrams work with Chinese and English without tokenization.
    text = re.sub(r"\s+","",text.lower())
    grams = [text[i:i+2] for i in range(max(0,len(text)-1))]
    vec=[0.0]*dim
    for gram in grams:
        idx=int.from_bytes(hashlib.sha256(gram.encode()).digest()[:4],"big")%dim
        vec[idx]+=1.0
    norm=math.sqrt(sum(v*v for v in vec))
    return [v/norm for v in vec] if norm else vec

def cosine(a,b):
    if len(a)!=len(b):
        raise ValueError("vector dimensions differ")
    return sum(x*y for x,y in zip(a,b))

def compute(conn, top_k=10, threshold=0.15):
    """Build similarity between document nodes and aggregate cross-stock relationships."""
    if top_k<1 or not -1<=threshold<=1:
        raise ValueError("invalid top_k or threshold")
    conn.execute("""INSERT OR IGNORE INTO embedding_models(model_id,model_name,dimension,config_json)
    VALUES(?,?,?,?)""",(MODEL_ID,"Character bigram hashed baseline (not semantic)",DIM,'{}'))
    docs=conn.execute("""SELECT d.document_id,d.title,d.content,d.content_hash
    FROM documents d ORDER BY d.document_id""").fetchall()
    vectors={}
    for d in docs:
        nid="doc:"+d["document_id"]
        vec=vectorize(d["title"]+" "+d["content"])
        vectors[nid]=vec
        blob=struct.pack("<"+str(DIM)+"f",*vec)
        conn.execute("""INSERT INTO embeddings(node_id,model_id,content_hash,vector,computed_at)
        VALUES(?,?,?,?,?) ON CONFLICT(node_id,model_id) DO UPDATE SET
        content_hash=excluded.content_hash,vector=excluded.vector,computed_at=excluded.computed_at""",
        (nid,MODEL_ID,d["content_hash"],blob,now()))
    # Rebuild only this model's similarity edges, keeping explicit relationships intact.
    conn.execute("DELETE FROM edge_evidence WHERE edge_id IN (SELECT edge_id FROM graph_edges WHERE model_id=?)",(MODEL_ID,))
    conn.execute("DELETE FROM graph_edges WHERE model_id=?",(MODEL_ID,))
    # Symmetric exact Top-K union; keep at most N*K candidates in memory.
    usable={nid:v for nid,v in vectors.items() if any(v)}
    selected,_=top_k_pairs(usable,top_k,threshold)
    pairs=[(a,b,score) for (a,b),score in selected.items()]
    for a,b,score in pairs:
        upsert_edge(conn,a,b,"lexical_similarity","hashed_bigram_cosine",round(score,6),MODEL_ID)
    # Stock-level score: maximum document pair similarity between two distinct stocks.
    doc_stocks={}
    for r in conn.execute("SELECT document_id,stock_id FROM document_stocks"):
        doc_stocks.setdefault("doc:"+r["document_id"],set()).add(r["stock_id"])
    stock_pairs={}
    for a,b,score in pairs:
        for sa in doc_stocks.get(a,set()):
            for sb in doc_stocks.get(b,set()):
                if sa==sb:continue
                x,y=sorted((sa,sb))
                stock_pairs[(x,y)]=max(score,stock_pairs.get((x,y),-1))
    neighbors={}
    for (a,b),score in stock_pairs.items():
        neighbors.setdefault(a,[]).append((score,b))
        neighbors.setdefault(b,[]).append((score,a))
    chosen=set()
    for a,vals in neighbors.items():
        for score,b in sorted(vals,reverse=True)[:top_k]:
            chosen.add(tuple(sorted((a,b))))
    for a,b in sorted(chosen):
        upsert_edge(conn,"stock:"+a,"stock:"+b,"lexical_similarity","document_max_cosine",round(stock_pairs[(a,b)],6),MODEL_ID)
    # The pipeline/caller owns the transaction.
    return {"documents":len(docs),"document_pairs":len(pairs),"stock_pairs":len(chosen)}
