"""Measure accuracy on labelled drafts: precision and recall per category."""
from . import db, engine
from .samples import EVAL_EXTRA, SAMPLES
from .workspace import asset_b64

CASES = [dict(s) for s in SAMPLES] + [dict(e, title=(e["text"].split("\n")[-1][:46] + "…")) for e in EVAL_EXTRA]


def case_list():
    return [{"id": c["id"], "title": c.get("title", c["id"]), "channel": c["channel"],
             "expected": len(c["expected"])} for c in CASES]


def _spans(text, quote):
    """All places the labelled quote occurs (a repeated mistake is one label)."""
    if quote == "*":
        return None
    out, low, q, i = [], text.lower(), quote.lower(), 0
    while (i := low.find(q, i)) >= 0:
        out.append((i, i + len(q)))
        i += 1
    return out or None


def score_case(org_id, brand, case_id):
    c = next((x for x in CASES if x["id"] == case_id), None)
    if not c:
        return None
    image = asset_b64(c["image"]) if c.get("image") else None
    version = {"text": c["text"], "image_b64": image, "alt_text": c.get("alt_text")}
    res = engine.run_check(org_id, brand, version, c["channel"])
    preds = res["findings"]
    exp = [{"category": cat, "quote": q, "spans": _spans(c["text"], q), "hit": False} for cat, q in c["expected"]]
    pred_rows = []
    for p in preds:
        matched = False
        for e in exp:
            if e["category"] != p["category"]:
                continue
            if e["quote"] == "*" or e["spans"] is None or p["start"] is None or \
                    any(p["start"] < b and a < p["end"] for a, b in e["spans"]):
                e["hit"] = True
                matched = True
        pred_rows.append({"category": p["category"], "quote": p["quote"], "source": p["source"],
                          "cite_code": p["cite_code"], "correct": matched})
    return {
        "id": c["id"], "title": c.get("title", c["id"]), "ai_status": res["ai_status"],
        "tp": sum(1 for e in exp if e["hit"]), "fn": sum(1 for e in exp if not e["hit"]),
        "fp": sum(1 for p in pred_rows if not p["correct"]),
        "missed": [{"category": e["category"], "quote": e["quote"]} for e in exp if not e["hit"]],
        "predicted": pred_rows, "dropped_uncited": res["dropped_uncited"],
        "by_cat": _by_cat(exp, pred_rows),
    }


def _by_cat(exp, preds):
    out = {}
    for e in exp:
        d = out.setdefault(e["category"], {"tp": 0, "fn": 0, "fp": 0})
        d["tp" if e["hit"] else "fn"] += 1
    for p in preds:
        if not p["correct"]:
            out.setdefault(p["category"], {"tp": 0, "fn": 0, "fp": 0})["fp"] += 1
    return out


def save_run(org_id, results):
    db.insert("eval_runs", {"id": db.new_id(), "org_id": org_id, "ran_at": db.now(), "results": db.jdump(results)})


def latest(org_id):
    r = db.one("SELECT * FROM eval_runs WHERE org_id = ? ORDER BY ran_at DESC LIMIT 1", (org_id,))
    if not r:
        r = db.one("SELECT * FROM eval_runs WHERE org_id = 'published' ORDER BY ran_at DESC LIMIT 1")
    if r:
        r["results"] = db.jload(r["results"])
    return r
