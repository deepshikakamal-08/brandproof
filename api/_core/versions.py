"""Rulebook versions (Round 3, improvement 3).

Every change to a brand's rulebook (clause edit, new fact, confirmed import, an
approved guideline rewrite) saves a numbered snapshot. Each check records the
version it ran against, so a manager can see exactly which rules a past
approval used, and admins can compare any version with the one before it.
"""
from . import db


def _state(org_id, brand_id):
    clauses = db.all("SELECT code, title, text, kind, status FROM clauses WHERE org_id = ? AND brand_id = ? "
                     "ORDER BY code", (org_id, brand_id))
    facts = db.all("SELECT code, fkey, value, valid_until FROM facts WHERE org_id = ? AND brand_id = ? ORDER BY code",
                   (org_id, brand_id))
    terms = db.all("SELECT term, kind, replacement, clause_code FROM terms WHERE org_id = ? AND brand_id = ? "
                   "ORDER BY term", (org_id, brand_id))
    return {"clauses": clauses, "facts": facts, "terms": terms}


def current(org_id, brand_id):
    b = db.one("SELECT rulebook_version FROM brands WHERE id = ? AND org_id = ?", (brand_id, org_id))
    return (b or {}).get("rulebook_version") or 1


def ensure_initial(org_id, brand_id):
    """Brands created before versioning get their current rulebook saved as the first snapshot."""
    if not db.one("SELECT id FROM rulebook_versions WHERE org_id = ? AND brand_id = ? LIMIT 1", (org_id, brand_id)):
        db.insert("rulebook_versions", {
            "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "version": current(org_id, brand_id),
            "note": "Starting rulebook", "actor": "system", "created_at": db.now(),
            "snapshot": db.jdump(_state(org_id, brand_id))})


def save(org_id, brand_id, user, note):
    """Call after a rulebook change: bumps the version number and stores a snapshot."""
    ensure_initial(org_id, brand_id)
    db.exec("UPDATE brands SET rulebook_version = COALESCE(rulebook_version, 1) + 1 WHERE id = ? AND org_id = ?",
            (brand_id, org_id))
    v = current(org_id, brand_id)
    db.insert("rulebook_versions", {
        "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "version": v, "note": (note or "")[:300],
        "actor": (user or {}).get("name", "system"), "created_at": db.now(),
        "snapshot": db.jdump(_state(org_id, brand_id))})
    return v


def history(org_id, brand_id):
    ensure_initial(org_id, brand_id)
    rows = db.all("SELECT version, note, actor, created_at FROM rulebook_versions WHERE org_id = ? AND brand_id = ? "
                  "ORDER BY version DESC", (org_id, brand_id))
    return {"current": current(org_id, brand_id), "versions": rows}


def diff(org_id, brand_id, version):
    """What changed in `version` compared with the version before it."""
    rows = db.all("SELECT version, snapshot, note, actor, created_at FROM rulebook_versions "
                  "WHERE org_id = ? AND brand_id = ? AND version <= ? ORDER BY version DESC LIMIT 2",
                  (org_id, brand_id, version))
    if not rows or rows[0]["version"] != version:
        return None
    new = db.jload(rows[0]["snapshot"], {})
    old = db.jload(rows[1]["snapshot"], {}) if len(rows) > 1 else {"clauses": [], "facts": [], "terms": []}
    changes = []

    def compare(kind, key, fields, label):
        a = {x[key]: x for x in old.get(kind, [])}
        b = {x[key]: x for x in new.get(kind, [])}
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                changes.append({"type": "added", "what": label, "code": k, "new": " · ".join(str(b[k].get(f) or "") for f in fields)})
            elif k not in b:
                changes.append({"type": "removed", "what": label, "code": k, "old": " · ".join(str(a[k].get(f) or "") for f in fields)})
            elif any(a[k].get(f) != b[k].get(f) for f in fields):
                changes.append({"type": "changed", "what": label, "code": k,
                                "old": " · ".join(str(a[k].get(f) or "") for f in fields),
                                "new": " · ".join(str(b[k].get(f) or "") for f in fields)})

    compare("clauses", "code", ("text", "kind", "status"), "Guideline")
    compare("facts", "code", ("fkey", "value", "valid_until"), "Fact")
    compare("terms", "term", ("kind", "replacement"), "Term")
    r = rows[0]
    return {"version": version, "note": r["note"], "actor": r["actor"], "created_at": r["created_at"],
            "previous": rows[1]["version"] if len(rows) > 1 else None, "changes": changes}
