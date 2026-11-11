"""Drafts, versions, checks, decisions and approvals, plus the audit log."""
from fastapi import HTTPException

from . import db, engine, learning

STATUSES = ["draft", "in_review", "changes_requested", "approved"]


def log(org_id, draft_id, user, action, comment=None):
    db.insert("events", {"id": db.new_id(), "org_id": org_id, "draft_id": draft_id, "actor": user.get("name"),
                         "role": user.get("role"), "action": action, "comment": comment, "at": db.now()})


def create_draft(org_id, brand_id, user, title, channel, text, image_b64, alt_text, sample_id=None, log_event=True):
    did, t = db.new_id(), db.now()
    db.insert("drafts", {"id": did, "org_id": org_id, "brand_id": brand_id, "title": title or "Untitled draft",
                         "channel": channel, "status": "draft", "created_by": user.get("name"), "current_version": 1,
                         "sample_id": sample_id, "created_at": t, "updated_at": t})
    db.insert("versions", {"id": db.new_id(), "org_id": org_id, "draft_id": did, "n": 1, "text": text,
                           "image_b64": image_b64, "alt_text": alt_text, "note": "First version",
                           "created_by": user.get("name"), "created_at": t})
    if log_event:
        log(org_id, did, user, "created")
    return {"id": did}


def get_draft(org_id, draft_id):
    d = db.one("SELECT * FROM drafts WHERE id = ? AND org_id = ?", (draft_id, org_id))
    if not d:
        raise HTTPException(404, "Draft not found")
    return d


def current_version(org_id, d):
    return db.one("SELECT * FROM versions WHERE draft_id = ? AND org_id = ? AND n = ?",
                  (d["id"], org_id, d["current_version"]))


def latest_check(org_id, version_id):
    c = db.one("SELECT * FROM checks WHERE version_id = ? AND org_id = ? ORDER BY ran_at DESC LIMIT 1",
               (version_id, org_id))
    if not c:
        return None, []
    c["summary"] = db.jload(c["summary"], {})
    fs = db.all("SELECT * FROM findings WHERE check_id = ? AND org_id = ? ORDER BY ord", (c["id"], org_id))
    return c, fs


def run_and_store(org_id, brand, d, user):
    v = current_version(org_id, d)
    payload = engine.run_check(org_id, brand, v, d["channel"])
    cid = db.new_id()
    db.insert("checks", {"id": cid, "org_id": org_id, "version_id": v["id"], "content_hash": payload["content_hash"],
                         "model": payload["model"], "ai_status": payload["ai_status"],
                         "dropped_uncited": payload["dropped_uncited"], "duration_ms": payload["duration_ms"],
                         "summary": db.jdump({"verified_claims": payload["verified_claims"],
                                              "cached": payload.get("cached", False),
                                              "retrieved": payload.get("retrieved", []),
                                              "learning": payload.get("learning"),
                                              "learning_notes": {str(i): f["learning"] for i, f in
                                                                 enumerate(payload["findings"]) if f.get("learning")},
                                              "hidden": [{k: h.get(k) for k in ("category", "quote", "cite_code",
                                                                                 "explanation", "hidden_reason",
                                                                                 "confidence", "source")}
                                                         for h in payload.get("hidden", [])]}),
                         "ran_at": db.now()})
    rows = []
    for i, f in enumerate(payload["findings"]):
        rows.append({"id": db.new_id(), "org_id": org_id, "check_id": cid, "version_id": v["id"],
                     "category": f["category"], "severity": f["severity"], "confidence": f["confidence"],
                     "source": f["source"], "rule": f.get("rule"), "quote": f["quote"], "start_idx": f["start"],
                     "end_idx": f["end"], "cite_type": f["cite_type"], "cite_code": f["cite_code"],
                     "cite_text": f["cite_text"], "explanation": f["explanation"], "fix_text": f["fix_text"],
                     "claim_status": f.get("claim_status"), "decision": None, "decision_note": None,
                     "edited_fix": None, "decided_by": None, "decided_at": None, "ord": i})
    db.insert_many("findings", rows)
    log(org_id, d["id"], user, "checked", f"{len(rows)} issues found" + (" (AI unavailable)" if payload["ai_status"] == "failed" else ""))
    db.exec("UPDATE drafts SET updated_at = ? WHERE id = ?", (db.now(), d["id"]))
    return cid


def decide(org_id, finding_id, user, decision, note, edited_fix):
    if decision not in ("accepted", "edited", "disputed", None):
        raise HTTPException(400, "decision must be accepted, edited or disputed")
    f = db.one("SELECT * FROM findings WHERE id = ? AND org_id = ?", (finding_id, org_id))
    if not f:
        raise HTTPException(404, "Finding not found")
    if decision == "disputed" and not (note or "").strip():
        raise HTTPException(400, "Add a short note explaining the dispute.")
    if decision == "edited" and edited_fix is None:
        raise HTTPException(400, "Provide your edited text.")
    db.exec("UPDATE findings SET decision = ?, decision_note = ?, edited_fix = ?, decided_by = ?, decided_at = ? "
            "WHERE id = ?", (decision, note, edited_fix, user["name"], db.now(), finding_id))
    d = db.one("SELECT d.brand_id FROM versions v JOIN drafts d ON d.id = v.draft_id WHERE v.id = ? AND v.org_id = ?",
               (f["version_id"], org_id))
    if d:  # every decision teaches the checker (improvement 1)
        learning.record(org_id, d["brand_id"], f, decision, note)
    return db.one("SELECT * FROM findings WHERE id = ?", (finding_id,))


def new_version(org_id, d, user, text, image_b64, alt_text, note):
    n = d["current_version"] + 1
    db.insert("versions", {"id": db.new_id(), "org_id": org_id, "draft_id": d["id"], "n": n, "text": text,
                           "image_b64": image_b64, "alt_text": alt_text, "note": note, "created_by": user["name"],
                           "created_at": db.now()})
    db.exec("UPDATE drafts SET current_version = ?, updated_at = ? WHERE id = ?", (n, db.now(), d["id"]))
    d["current_version"] = n
    return n


def submit(org_id, brand, d, user):
    if d["status"] not in ("draft", "changes_requested"):
        raise HTTPException(400, "This draft is already in review or approved.")
    v = current_version(org_id, d)
    c, fs = latest_check(org_id, v["id"])
    if not c:
        raise HTTPException(400, "Run a check before submitting.")
    open_items = [f for f in fs if not f["decision"]]
    if open_items:
        raise HTTPException(400, f"Decide on every issue first ({len(open_items)} still open).")
    applied = [f for f in fs if f["decision"] in ("accepted", "edited")]
    if applied:
        text = engine.apply_fixes(v["text"], fs)
        n = new_version(org_id, d, user, text, v["image_b64"], v["alt_text"],
                        f"Applied {len(applied)} fixes from check")
        # carry decisions forward so reviewers see what happened
        nv = current_version(org_id, d)
        db.insert("checks", {"id": (cid := db.new_id()), "org_id": org_id, "version_id": nv["id"],
                             "content_hash": None, "model": c["model"], "ai_status": c["ai_status"],
                             "dropped_uncited": c["dropped_uncited"], "duration_ms": c["duration_ms"],
                             "summary": db.jdump({**c["summary"], "carried_from_version": n - 1}), "ran_at": db.now()})
        db.insert_many("findings", [{**{k: f[k] for k in f}, "id": db.new_id(), "check_id": cid,
                                     "version_id": nv["id"]} for f in fs])
    db.exec("UPDATE drafts SET status = 'in_review', updated_at = ? WHERE id = ?", (db.now(), d["id"]))
    disputed = sum(1 for f in fs if f["decision"] == "disputed")
    needs_reviewer = any(f["category"] in ("claims", "legal") and f["severity"] == "high" and f["decision"] == "disputed"
                         for f in fs)
    log(org_id, d["id"], user, "submitted",
        f"{len(applied)} fixes applied, {disputed} disputed" + ("; routed to reviewer for claims" if needs_reviewer else ""))


def review(org_id, d, user, action, comment):
    if d["status"] != "in_review":
        raise HTTPException(400, "Only drafts in review can be approved or sent back.")
    if action == "approve":
        v = current_version(org_id, d)
        _, fs = latest_check(org_id, v["id"])
        blocked = [f for f in fs if f["category"] in ("claims", "legal") and f["severity"] == "high"
                   and f["decision"] == "disputed"]
        if blocked and user["role"] == "manager" and not (comment or "").strip():
            raise HTTPException(400, "A high-severity claim was disputed. Add a comment explaining why it is OK to approve, "
                                     "or switch to Reviewer.")
        db.exec("UPDATE drafts SET status = 'approved', updated_at = ? WHERE id = ?", (db.now(), d["id"]))
        log(org_id, d["id"], user, "approved", comment)
    elif action == "request_changes":
        if not (comment or "").strip():
            raise HTTPException(400, "Tell the creator what to change.")
        db.exec("UPDATE drafts SET status = 'changes_requested', updated_at = ? WHERE id = ?", (db.now(), d["id"]))
        log(org_id, d["id"], user, "changes_requested", comment)
    else:
        raise HTTPException(400, "Unknown action")


def insights(org_id):
    rows = db.all("SELECT f.category, f.severity, f.source, f.cite_code, f.cite_text, f.decision, f.claim_status "
                  "FROM findings f JOIN checks c ON c.id = f.check_id "
                  "WHERE f.org_id = ? AND (c.summary NOT LIKE '%carried_from_version%' OR c.summary IS NULL)", (org_id,))
    by_cat, by_clause, disputes, ai_rule = {}, {}, {}, {"ai": 0, "rule": 0}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
        k = r["cite_code"]
        by_clause.setdefault(k, {"code": k, "text": r["cite_text"], "count": 0, "disputed": 0, "accepted": 0})
        by_clause[k]["count"] += 1
        if r["decision"] == "disputed":
            by_clause[k]["disputed"] += 1
        if r["decision"] in ("accepted", "edited"):
            by_clause[k]["accepted"] += 1
        ai_rule[r["source"]] = ai_rule.get(r["source"], 0) + 1
    unclear = [c for c in by_clause.values() if c["disputed"] >= 1 and c["disputed"] / max(1, c["count"]) >= 0.3]
    drafts = db.all("SELECT status, COUNT(*) AS n FROM drafts WHERE org_id = ? GROUP BY status", (org_id,))
    checks = db.one("SELECT COUNT(*) AS n, AVG(duration_ms) AS ms, SUM(dropped_uncited) AS dropped FROM checks "
                    "WHERE org_id = ? AND content_hash IS NOT NULL", (org_id,))
    return {
        "total_findings": len(rows),
        "by_category": sorted([{"category": k, "count": v} for k, v in by_cat.items()], key=lambda x: -x["count"]),
        "top_clauses": sorted(by_clause.values(), key=lambda x: -x["count"])[:8],
        "unclear_clauses": sorted(unclear, key=lambda x: -x["disputed"]),
        "by_source": ai_rule,
        "drafts_by_status": {r["status"]: r["n"] for r in drafts},
        "checks": {"count": checks["n"] or 0, "avg_ms": int(checks["ms"] or 0), "dropped_uncited": int(checks["dropped"] or 0)},
    }
