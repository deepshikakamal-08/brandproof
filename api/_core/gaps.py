"""Guideline-gap assistant (Round 3, improvement 3).

Finds guidelines that people struggle with (often disputed by reviewers, or
applied by the AI with low confidence), asks the AI for a clearer rewrite with
do / don't examples built from the real disputed and accepted cases, and lets
an admin approve, edit or reject it. Approving updates the clause, saves a new
rulebook version, and (optionally) resets that clause's learning history,
because the old disputes were about the old wording.
"""
from . import db, learning, llm, versions

MIN_DECISIONS = 2
DISPUTE_RATE = 0.4
LOW_CONFIDENCE = 0.7

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "rewrite": {"type": "string"},
        "do_examples": {"type": "array", "items": {"type": "string"}},
        "dont_examples": {"type": "array", "items": {"type": "string"}},
        "why": {"type": "string"},
    },
    "required": ["rewrite", "do_examples", "dont_examples", "why"],
}

SYSTEM = ("You edit brand guidelines so writers and reviewers apply them the same way. Keep the rule's intent and "
          "strictness; make it specific and testable; use plain words; one or two short sentences. Respond with "
          "JSON only.")


def candidates(org_id, brand_id):
    """Guidelines that look unclear, most urgent first."""
    pol = learning.policy(org_id, brand_id)
    clauses = {c["code"]: c for c in db.all(
        "SELECT code, title, text, kind FROM clauses WHERE org_id = ? AND brand_id = ? AND status = 'confirmed' "
        "AND kind = 'judgement'",  # exact rules are fixed in their settings, not by rewording
        (org_id, brand_id))}
    out = {}
    for code, h in pol["clauses"].items():
        if code in clauses and h["n"] >= MIN_DECISIONS and h["dispute_rate"] >= DISPUTE_RATE:
            out[code] = {"reason": f"Reviewers disputed {h['disputed']} of {h['n']} flags for this guideline.",
                         "score": h["dispute_rate"] + h["n"] / 100, "disputed": h["disputed"], "n": h["n"]}
    rows = db.all("SELECT f.cite_code AS code, AVG(f.confidence) AS conf, COUNT(*) AS n FROM findings f "
                  "JOIN versions v ON v.id = f.version_id JOIN drafts d ON d.id = v.draft_id "
                  "WHERE f.org_id = ? AND d.brand_id = ? AND f.source = 'ai' GROUP BY f.cite_code", (org_id, brand_id))
    for r in rows:
        if r["code"] in clauses and r["n"] >= 3 and (r["conf"] or 1) < LOW_CONFIDENCE and r["code"] not in out:
            out[r["code"]] = {"reason": f"The AI applies it with low confidence (average {round(r['conf'] * 100)}% "
                                        f"over {r['n']} flags).", "score": 1 - r["conf"], "disputed": 0, "n": r["n"]}
    pending = {s["code"]: s for s in db.all(
        "SELECT * FROM clause_suggestions WHERE org_id = ? AND brand_id = ? AND status = 'pending'", (org_id, brand_id))}
    res = []
    for code, g in sorted(out.items(), key=lambda kv: -kv[1]["score"]):
        c = clauses[code]
        res.append({"code": code, "title": c["title"], "text": c["text"], "kind": c["kind"], **g,
                    "examples": (pol["clauses"].get(code) or {}).get("examples", [])[:4],
                    "suggestion": _row(pending[code]) if code in pending else None})
    return res


def _row(s):
    if not s:
        return None
    s = dict(s)
    s["do_examples"] = db.jload(s["do_examples"], [])
    s["dont_examples"] = db.jload(s["dont_examples"], [])
    return s


def suggest(org_id, brand, code, reason=""):
    c = db.one("SELECT * FROM clauses WHERE org_id = ? AND brand_id = ? AND code = ?", (org_id, brand["id"], code))
    if not c:
        raise ValueError("Guideline not found")
    pol = learning.policy(org_id, brand["id"])
    ex = (pol["clauses"].get(code) or {}).get("examples", [])
    cases = "\n".join(f"- {'DISPUTED (reviewers said not a breach)' if e['decision'] == 'disputed' else 'ACCEPTED (a real breach)'}: "
                      f"\"{e['quote']}\"" + (f" — note: {e['note']}" if e.get("note") else "") for e in ex) or "- none yet"
    prompt = (f"Brand: {brand['name']}. Voice: {brand.get('tone_summary') or ''}\n\n"
              f"GUIDELINE {code} ({c['title']}): {c['text']}\n\n"
              f"WHY IT LOOKS UNCLEAR: {reason or 'Writers and reviewers apply it differently.'}\n\n"
              f"REAL CASES FROM REVIEWERS\n{cases}\n\n"
              "Rewrite the guideline so the disputed cases are clearly allowed or clearly not, and the accepted "
              "cases stay breaches. Give 2 short 'do' examples and 2 short 'don't' examples written for this brand, "
              "and one sentence on what you changed.")
    try:
        data, model = llm.chat_json(SYSTEM, prompt, SUGGEST_SCHEMA, "guideline_rewrite")
    except Exception as e:  # AI busy or down: draft one from the reviewers' own decisions instead
        print(f"[gaps] AI rewrite failed for {code}: {str(e)[:160]}", flush=True)
        data, model = _fallback(c, ex), "rules:reviewer-decisions"
    rewrite = (data.get("rewrite") or "").strip()
    if not rewrite:
        raise ValueError("The AI returned an empty suggestion. Please try again.")
    db.exec("UPDATE clause_suggestions SET status = 'superseded' WHERE org_id = ? AND brand_id = ? AND code = ? "
            "AND status = 'pending'", (org_id, brand["id"], code))
    sid = db.new_id()
    db.insert("clause_suggestions", {
        "id": sid, "org_id": org_id, "brand_id": brand["id"], "code": code, "reason": reason[:300],
        "old_text": c["text"], "new_text": rewrite[:1200],
        "do_examples": db.jdump([str(x)[:200] for x in (data.get("do_examples") or [])][:3]),
        "dont_examples": db.jdump([str(x)[:200] for x in (data.get("dont_examples") or [])][:3]),
        "why": (data.get("why") or "")[:400], "model": model, "status": "pending", "created_at": db.now()})
    return _row(db.one("SELECT * FROM clause_suggestions WHERE id = ?", (sid,)))


def _fallback(clause, examples):
    """Deterministic suggestion built from real decisions: disputed cases become allowed examples,
    accepted cases become examples of breaches. Used when the AI is unavailable."""
    allowed = [e["quote"] for e in examples if e["decision"] == "disputed"][:2]
    breaches = [e["quote"] for e in examples if e["decision"] == "accepted"][:2]
    text = clause["text"].strip()
    if allowed:
        text += " This does not apply to wording like " + " or ".join(f"'{q}'" for q in allowed) + \
            ", which reviewers have accepted."
    return {"rewrite": text, "do_examples": allowed, "dont_examples": breaches,
            "why": "Drafted from your reviewers' decisions because the AI was unavailable; edit before approving."}


def compose(text, do, dont):
    """Clause text with its examples, as the AI and writers will read it."""
    parts = [text.strip()]
    if do:
        parts.append("Do: " + "; ".join(f"'{x}'" for x in do) + ".")
    if dont:
        parts.append("Don't: " + "; ".join(f"'{x}'" for x in dont) + ".")
    return " ".join(parts)


def decide(org_id, brand_id, sid, user, approve, text=None, do=None, dont=None, reset_history=True):
    s = db.one("SELECT * FROM clause_suggestions WHERE id = ? AND org_id = ? AND brand_id = ?", (sid, org_id, brand_id))
    if not s:
        raise ValueError("Suggestion not found")
    if s["status"] != "pending":
        raise ValueError(f"This suggestion was already {s['status']}.")
    if not approve:
        db.exec("UPDATE clause_suggestions SET status = 'rejected', decided_by = ?, decided_at = ? WHERE id = ?",
                (user["name"], db.now(), sid))
        return {"status": "rejected"}
    do = do if do is not None else db.jload(s["do_examples"], [])
    dont = dont if dont is not None else db.jload(s["dont_examples"], [])
    versions.ensure_initial(org_id, brand_id)  # keep the "before" state for the diff
    new_text = compose(text or s["new_text"], [d for d in do if d.strip()], [d for d in dont if d.strip()])
    db.exec("UPDATE clauses SET text = ?, embedding = NULL WHERE org_id = ? AND brand_id = ? AND code = ?",
            (new_text, org_id, brand_id, s["code"]))
    if reset_history:
        learning.clear(org_id, brand_id, code=s["code"])
    v = versions.save(org_id, brand_id, user, f"Clarified guideline {s['code']} (guideline-gap assistant)")
    db.exec("UPDATE clause_suggestions SET status = 'approved', decided_by = ?, decided_at = ?, version = ?, "
            "new_text = ? WHERE id = ?", (user["name"], db.now(), v, text or s["new_text"], sid))
    return {"status": "approved", "version": v, "text": new_text}


def recent(org_id, brand_id, limit=10):
    return [_row(r) for r in db.all(
        "SELECT * FROM clause_suggestions WHERE org_id = ? AND brand_id = ? AND status IN ('approved', 'rejected') "
        "ORDER BY decided_at DESC LIMIT ?", (org_id, brand_id, limit))]
