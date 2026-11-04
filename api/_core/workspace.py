"""Create organisations and clone the demo brand into them."""
import base64
import os

from . import db
from .demo_data import BRAND, CLAUSES, FACTS, TERMS
from .samples import SAMPLES

ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def asset_b64(name):
    with open(os.path.join(ASSETS, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def create_guest_workspace(name, role):
    org_id, user_id, brand_id = db.new_id(), db.new_id(), db.new_id()
    t = db.now()
    db.insert("orgs", {"id": org_id, "name": "Neem & Nila (demo workspace)", "kind": "guest", "created_at": t})
    db.insert("users", {"id": user_id, "name": name or "Guest", "created_at": t})
    db.insert("members", {"user_id": user_id, "org_id": org_id, "role": role})
    seed_brand(org_id, brand_id)
    seed_history(org_id, brand_id)
    return org_id, user_id


def seed_brand(org_id, brand_id):
    db.insert("brands", {"id": brand_id, "org_id": org_id, "name": BRAND["name"],
                         "description": BRAND["description"], "tone_summary": BRAND["tone_summary"],
                         "palette": db.jdump(BRAND["palette"]), "rulebook_version": 1, "created_at": db.now()})
    db.insert_many("clauses", [{
        "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "code": c["code"],
        "section": c["section"], "title": c["title"], "text": c["text"], "kind": c["kind"],
        "check_type": c.get("check"), "params": db.jdump(c.get("params") or {}),
        "visual": 1 if c.get("visual") else 0, "status": "confirmed", "embedding": None,
        "created_at": db.now()} for c in CLAUSES])
    db.insert_many("facts", [{
        "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "code": f["code"], "fkey": f["key"],
        "value": f["value"], "valid_until": f["valid_until"], "source": f["source"]} for f in FACTS])
    db.insert_many("terms", [{
        "id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "term": x["term"], "kind": x["kind"],
        "replacement": x["replacement"], "clause_code": x["clause"],
        "unless_preceded_by": x.get("unless_preceded_by")} for x in TERMS])


def seed_history(org_id, brand_id):
    """A little past activity so the manager queue and Insights are not empty."""
    from .workflow import create_draft
    for sid, status in (("s07", "approved"), ("s11", "approved")):
        s = next(x for x in SAMPLES if x["id"] == sid)
        d = create_draft(org_id, brand_id, {"user_id": "system", "role": "creator", "name": "Asha (content team)"},
                         s["title"], s["channel"], s["text"], None, None, sample_id=sid, log_event=False)
        db.exec("UPDATE drafts SET status = ? WHERE id = ?", (status, d["id"]))


def brand_for(org_id):
    b = db.one("SELECT * FROM brands WHERE org_id = ? ORDER BY created_at LIMIT 1", (org_id,))
    if b:
        b["palette"] = db.jload(b["palette"], [])
    return b
