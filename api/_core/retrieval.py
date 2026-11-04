"""Find the guideline clauses and facts most relevant to a draft.

Hybrid: BM25 keyword scoring always; embedding similarity added when an
embeddings key is configured. Ranks are fused (reciprocal rank fusion).
"""
import math
import re

from . import db, llm

_STOP = set("a an the and or of to in on for with is are be it this that your our we you at by from as".split())


def _tok(s):
    return [w for w in re.findall(r"[a-z0-9₹%]+", s.lower()) if w not in _STOP]


def bm25_rank(query, docs, k1=1.4, b=0.75):
    toks = [_tok(d) for d in docs]
    avg = sum(len(t) for t in toks) / max(1, len(toks))
    df = {}
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    q = _tok(query)
    scores = []
    for t in toks:
        tf = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (len(docs) - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    return sorted(range(len(docs)), key=lambda i: -scores[i])


def _cos(a, b):
    num = sum(x * y for x, y in zip(a, b))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def ensure_embeddings(clauses):
    missing = [c for c in clauses if not c.get("embedding")]
    if not missing:
        return True
    vecs = llm.embed([f"{c['title']}: {c['text']}" for c in missing])
    if not vecs:
        return False
    for c, v in zip(missing, vecs):
        c["embedding"] = v
        db.exec("UPDATE clauses SET embedding = ? WHERE id = ?", (db.jdump(v), c["id"]))
    return True


def top_clauses(text, clauses, k=10):
    if len(clauses) <= k:
        return clauses
    docs = [f"{c['title']} {c['section']} {c['text']}" for c in clauses]
    ranks = {i: 1 / (60 + r) for r, i in enumerate(bm25_rank(text, docs))}
    for c in clauses:
        if isinstance(c.get("embedding"), str):
            c["embedding"] = db.jload(c["embedding"])
    if ensure_embeddings(clauses):
        qv = llm.embed([text])
        if qv:
            order = sorted(range(len(clauses)), key=lambda i: -_cos(qv[0], clauses[i]["embedding"]))
            for r, i in enumerate(order):
                ranks[i] += 1 / (60 + r)
    best = sorted(ranks, key=lambda i: -ranks[i])[:k]
    return [clauses[i] for i in sorted(best)]
