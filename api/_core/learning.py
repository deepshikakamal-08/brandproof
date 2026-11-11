"""Learning from reviewer decisions (Round 3, improvement 1).

Every accept / edit / dispute is stored as feedback. From that history we derive
a policy for each brand:

* per guideline clause: how often reviewers accept or dispute its findings, and a
  mode (trusted / normal / softened / muted);
* a learned confidence threshold for AI findings (the cut-off that kept the most
  accepted findings while dropping the most disputed ones);
* a short list of real accepted and disputed examples per clause that is added
  to the AI prompt, so the model copies the reviewers' judgement;
* disputed quotes: a finding identical to one reviewers already disputed (and
  never accepted) for the same clause is not raised again.

Exact (code) rules are never hidden by learning, only softened, so a
deterministic check can't silently disappear. Admins can switch learning off
for one clause or for the whole brand, and reset a clause's history.
"""
import hashlib

from . import db

MIN_SOFTEN = 2        # decisions before a clause can be softened
MIN_MUTE = 3          # decisions before an AI clause can be muted
MIN_THRESHOLD = 6     # AI decisions before a confidence threshold is learned
SOFTEN_RATE = 0.5
MUTE_RATE = 0.75
TRUST_RATE = 0.2
ACCEPTED = ("accepted", "edited")


def _norm(q):
    return " ".join((q or "").lower().split())


# ---------------- recording ----------------
def record(org_id, brand_id, finding, decision, note, origin="reviewer"):
    """Store (or replace) the decision for one finding. decision None removes it."""
    fid = finding.get("id")
    if fid:
        db.exec("DELETE FROM feedback WHERE org_id = ? AND finding_id = ?", (org_id, fid))
    if decision not in ("accepted", "edited", "disputed"):
        return
    if finding.get("cite_code") is None:
        return
    db.insert("feedback", {
        "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "finding_id": fid,
        "cite_code": finding.get("cite_code"), "source": finding.get("source"), "rule": finding.get("rule"),
        "category": finding.get("category"), "confidence": finding.get("confidence"),
        "quote": (finding.get("quote") or "")[:300], "decision": decision, "note": (note or "")[:300],
        "origin": origin, "created_at": db.now()})


def clear(org_id, brand_id, code=None, origin=None):
    q, p = "DELETE FROM feedback WHERE org_id = ? AND brand_id = ?", [org_id, brand_id]
    if code:
        q += " AND cite_code = ?"
        p.append(code)
    if origin:
        q += " AND origin = ?"
        p.append(origin)
    db.exec(q, tuple(p))


def set_enabled(org_id, brand_id, code, enabled):
    db.exec("DELETE FROM learning_settings WHERE org_id = ? AND brand_id = ? AND code = ?", (org_id, brand_id, code))
    db.insert("learning_settings", {"org_id": org_id, "brand_id": brand_id, "code": code,
                                    "enabled": 1 if enabled else 0, "updated_at": db.now()})


# ---------------- policy ----------------
def _threshold(ai_rows):
    """Pick the confidence cut-off that keeps the most accepted AI findings
    and drops the most disputed ones. None if there is too little history
    or no cut-off beats keeping everything."""
    rows = [r for r in ai_rows if r["confidence"] is not None]
    if len(rows) < MIN_THRESHOLD or not any(r["decision"] == "disputed" for r in rows):
        return None
    best_t, best = None, None
    for t in [x / 100 for x in range(50, 96, 5)]:
        kept = [r for r in rows if r["confidence"] >= t]
        acc = sum(1 for r in kept if r["decision"] in ACCEPTED)
        dis = sum(1 for r in kept if r["decision"] == "disputed")
        lost = sum(1 for r in rows if r["decision"] in ACCEPTED) - acc
        score = acc - dis - lost * 0.5  # losing a real issue costs; keeping a false alarm costs more
        if best is None or score > best:
            best_t, best = t, score
    base = sum(1 for r in rows if r["decision"] in ACCEPTED) - sum(1 for r in rows if r["decision"] == "disputed")
    return best_t if best is not None and best > base and best_t > 0.5 else None


def policy(org_id, brand_id, enabled=True):
    settings = {r["code"]: bool(r["enabled"]) for r in db.all(
        "SELECT code, enabled FROM learning_settings WHERE org_id = ? AND brand_id = ?", (org_id, brand_id))}
    on = enabled and settings.get("*", True)
    rows = db.all("SELECT * FROM feedback WHERE org_id = ? AND brand_id = ? ORDER BY created_at DESC",
                  (org_id, brand_id))
    clauses = {}
    for r in rows:
        c = clauses.setdefault(r["cite_code"], {
            "code": r["cite_code"], "accepted": 0, "disputed": 0, "ai": 0, "rule": 0,
            "examples": [], "disputed_quotes": set(), "accepted_quotes": set(),
            "enabled": settings.get(r["cite_code"], True)})
        if r["decision"] in ACCEPTED:
            c["accepted"] += 1
            c["accepted_quotes"].add(_norm(r["quote"]))
        else:
            c["disputed"] += 1
            c["disputed_quotes"].add(_norm(r["quote"]))
        c["ai" if r["source"] == "ai" else "rule"] += 1
        if len(c["examples"]) < 4 and r["quote"] and r["quote"] != "[image]":
            c["examples"].append({"quote": r["quote"], "decision": "disputed" if r["decision"] == "disputed" else "accepted",
                                  "note": r["note"]})
    for c in clauses.values():
        n = c["accepted"] + c["disputed"]
        rate = c["disputed"] / n if n else 0
        c["n"], c["dispute_rate"] = n, round(rate, 2)
        if not c["enabled"]:
            c["mode"] = "off"
        elif c["ai"] >= MIN_MUTE and c["rule"] == 0 and rate >= MUTE_RATE:
            c["mode"] = "muted"
        elif n >= MIN_SOFTEN and rate >= SOFTEN_RATE:
            c["mode"] = "softened"
        elif n >= 3 and rate <= TRUST_RATE:
            c["mode"] = "trusted"
        else:
            c["mode"] = "normal"
        c["repeat_quotes"] = sorted(c["disputed_quotes"] - c["accepted_quotes"]) if c["enabled"] else []
    ai_rows = [r for r in rows if r["source"] == "ai" and clauses.get(r["cite_code"], {}).get("enabled", True)]
    thr = _threshold(ai_rows)
    pol = {
        "enabled": on, "decisions": len(rows),
        "reviewer_decisions": sum(1 for r in rows if r["origin"] == "reviewer"),
        "calibration_decisions": sum(1 for r in rows if r["origin"] == "calibration"),
        "ai_threshold": thr, "clauses": clauses,
    }
    pol["prompt_key"] = prompt_fingerprint(pol)
    return pol


def prompt_fingerprint(pol):
    """Changes only when the examples given to the AI change (keeps the cache useful)."""
    if not pol or not pol["enabled"]:
        return "off"
    h = hashlib.sha256()
    for code in sorted(k for k in pol["clauses"] if k):
        c = pol["clauses"][code]
        if c["mode"] == "off":
            continue
        for e in c["examples"]:
            h.update(f"{code}|{e['decision']}|{e['quote']}".encode())
    return h.hexdigest()[:16]


def prompt_block(pol, picked):
    """Reviewer history for the clauses given to the model, keyed by their prompt ids."""
    if not pol or not pol["enabled"]:
        return ""
    lines = []
    for c in picked:
        h = pol["clauses"].get(c["code"])
        if not h or h["mode"] == "off" or not h["examples"]:
            continue
        for e in h["examples"][:3]:
            if e["decision"] == "disputed":
                why = f" (reviewer: {e['note']})" if e["note"] else ""
                lines.append(f"{c['_id']}: reviewers said this was NOT a breach: \"{e['quote']}\"{why}")
            else:
                lines.append(f"{c['_id']}: reviewers confirmed this WAS a breach: \"{e['quote']}\"")
    if not lines:
        return ""
    return ("REVIEWER HISTORY (past decisions by this brand's reviewers; follow their judgement on similar text)\n"
            + "\n".join(lines[:24]) + "\n\n")


def apply(findings, pol):
    """Adjust findings using the policy. Returns (kept, hidden); each hidden item says why."""
    if not pol or not pol["enabled"]:
        return findings, []
    kept, hidden = [], []
    thr = pol["ai_threshold"]
    for f in findings:
        h = pol["clauses"].get(f.get("cite_code"))
        mode = h["mode"] if h else "normal"
        reason = None
        if h and mode != "off":
            if f.get("source") == "ai" and _norm(f.get("quote")) in h["repeat_quotes"]:
                reason = "Reviewers already disputed this exact text for this guideline."
            elif f.get("source") == "ai" and mode == "muted":
                reason = (f"Reviewers disputed {h['disputed']} of {h['n']} AI flags for this guideline; "
                          "it is muted until an admin reviews it.")
        if not reason and thr and f.get("source") == "ai" and mode not in ("off", "trusted") \
                and (f.get("confidence") or 0) < thr:
            reason = f"AI confidence {f.get('confidence'):.2f} is below the learned threshold {thr:.2f}."
        if reason:
            hidden.append({**f, "hidden_reason": reason})
            continue
        if h and mode == "softened":
            f = {**f, "severity": "low", "learning": f"Often disputed ({h['disputed']} of {h['n']}): softened to low."}
        elif h and mode == "trusted":
            f = {**f, "learning": f"Reviewers accepted {h['accepted']} of {h['n']} flags for this guideline."}
        kept.append(f)
    return kept, hidden


def summary(org_id, brand_id, clause_text=None):
    """Learning page data."""
    pol = policy(org_id, brand_id)
    texts = clause_text or {}
    rows = []
    for code, c in pol["clauses"].items():
        rows.append({"code": code, "text": texts.get(code, ""), "accepted": c["accepted"], "disputed": c["disputed"],
                     "n": c["n"], "dispute_rate": c["dispute_rate"], "mode": c["mode"], "enabled": c["enabled"],
                     "examples": c["examples"][:3], "repeat_quotes": len(c["repeat_quotes"])})
    rows.sort(key=lambda r: (-r["n"], r["code"] or ""))
    return {"enabled": pol["enabled"], "decisions": pol["decisions"],
            "reviewer_decisions": pol["reviewer_decisions"], "calibration_decisions": pol["calibration_decisions"],
            "ai_threshold": pol["ai_threshold"], "clauses": rows}
