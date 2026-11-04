"""Brandproof API (FastAPI). Deployed on Vercel as a Python function."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from typing import Optional  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from _core import auth, db, engine, evaluation, llm, rulebook, workflow, workspace  # noqa: E402
from _core.demo_data import CHANNELS  # noqa: E402
from _core.samples import SAMPLES  # noqa: E402

app = FastAPI(title="Brandproof API", version="0.2.0",
              description="Brand governance before publication: check content against approved guidelines, "
                          "facts and assets, with cited findings and human approval.",
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


def brand_of(user, brand_id=None):
    if brand_id:
        b = db.one("SELECT * FROM brands WHERE id = ? AND org_id = ?", (brand_id, user["org_id"]))
        if b:
            b["palette"] = db.jload(b["palette"], [])
            return b
    b = workspace.brand_for(user["org_id"])
    if not b:
        raise HTTPException(404, "No brand in this workspace")
    return b


# ---------------- session ----------------
class DemoIn(BaseModel):
    name: Optional[str] = "Guest"
    role: str = "creator"


@app.get("/api/health")
def health():
    return {"ok": True, "db": "postgres" if db.IS_PG else "sqlite", **llm.status()}


@app.post("/api/session/demo")
def demo_session(body: DemoIn):
    role = body.role if body.role in auth.ROLES else "creator"
    org_id, user_id = workspace.create_guest_workspace(body.name, role)
    return {"token": auth.sign(user_id, org_id), "role": role}


class RoleIn(BaseModel):
    role: str


@app.post("/api/session/role")
def switch_role(body: RoleIn, user=Depends(auth.current)):
    """Demo workspaces let one person try every role. Real orgs assign roles to members."""
    if body.role not in auth.ROLES:
        raise HTTPException(400, "Unknown role")
    org = db.one("SELECT kind FROM orgs WHERE id = ?", (user["org_id"],))
    if org["kind"] != "guest":
        raise HTTPException(403, "Ask an admin to change your role.")
    db.exec("UPDATE members SET role = ? WHERE user_id = ? AND org_id = ?", (body.role, user["user_id"], user["org_id"]))
    return {"role": body.role}


@app.get("/api/me")
def me(user=Depends(auth.current)):
    org = db.one("SELECT name, kind FROM orgs WHERE id = ?", (user["org_id"],))
    brands = db.all("SELECT id, name FROM brands WHERE org_id = ? ORDER BY created_at", (user["org_id"],))
    return {**user, "org": org, "brands": brands, "ai": llm.status(), "channels": CHANNELS}


# ---------------- samples & drafts ----------------
@app.get("/api/samples")
def samples(user=Depends(auth.current)):
    return [{"id": s["id"], "title": s["title"], "channel": s["channel"], "text": s["text"],
             "has_image": bool(s.get("image"))} for s in SAMPLES]


class DraftIn(BaseModel):
    title: str = ""
    channel: str = "social"
    text: str = Field("", max_length=20000)
    image_b64: Optional[str] = None
    alt_text: Optional[str] = None
    sample_id: Optional[str] = None
    pdf_b64: Optional[str] = None
    brand_id: Optional[str] = None


@app.post("/api/drafts")
def create_draft(body: DraftIn, user=Depends(auth.current)):
    b = brand_of(user, body.brand_id)
    text, image, alt, title, channel = body.text, body.image_b64, body.alt_text, body.title, body.channel
    if body.sample_id:
        s = next((x for x in SAMPLES if x["id"] == body.sample_id), None)
        if not s:
            raise HTTPException(404, "Sample not found")
        text, channel, title = s["text"], s["channel"], s["title"]
        image = workspace.asset_b64(s["image"]) if s.get("image") else None
        alt = s.get("alt_text")
    if body.pdf_b64:
        try:
            text = rulebook.extract_text(body.pdf_b64)[:20000]
        except Exception:
            raise HTTPException(400, "Could not read that PDF.")
    if image and len(image) > 3_000_000:
        raise HTTPException(413, "Image too large. Use an image under 2 MB.")
    if channel not in CHANNELS:
        raise HTTPException(400, f"channel must be one of {CHANNELS}")
    if not text.strip() and not image:
        raise HTTPException(400, "Add some text or an image to check.")
    d = workflow.create_draft(user["org_id"], b["id"], user, title or text.strip()[:60] or "Image post",
                              channel, text, image, alt, sample_id=body.sample_id)
    return d


@app.get("/api/drafts")
def list_drafts(status: Optional[str] = None, user=Depends(auth.current)):
    q = ("SELECT d.id, d.title, d.channel, d.status, d.created_by, d.updated_at, d.current_version, b.name AS brand "
         "FROM drafts d JOIN brands b ON b.id = d.brand_id WHERE d.org_id = ?")
    params = [user["org_id"]]
    if status:
        q += " AND d.status = ?"
        params.append(status)
    rows = db.all(q + " ORDER BY d.updated_at DESC", params)
    for r in rows:
        v = db.one("SELECT id FROM versions WHERE draft_id = ? AND n = ?", (r["id"], r["current_version"]))
        c = db.one("SELECT id FROM checks WHERE version_id = ? ORDER BY ran_at DESC LIMIT 1", (v["id"],)) if v else None
        r["open_issues"] = db.one("SELECT COUNT(*) AS n FROM findings WHERE check_id = ? AND decision IS NULL",
                                  (c["id"],))["n"] if c else None
        r["issues"] = db.one("SELECT COUNT(*) AS n FROM findings WHERE check_id = ?", (c["id"],))["n"] if c else None
    return rows


@app.get("/api/drafts/{draft_id}")
def draft_detail(draft_id: str, user=Depends(auth.current)):
    d = workflow.get_draft(user["org_id"], draft_id)
    versions = db.all("SELECT id, n, text, image_b64, alt_text, note, created_by, created_at FROM versions "
                      "WHERE draft_id = ? AND org_id = ? ORDER BY n", (draft_id, user["org_id"]))
    cur = versions[-1]
    check, findings = workflow.latest_check(user["org_id"], cur["id"])
    events = db.all("SELECT actor, role, action, comment, at FROM events WHERE draft_id = ? AND org_id = ? ORDER BY at",
                    (draft_id, user["org_id"]))
    brand = db.one("SELECT id, name FROM brands WHERE id = ?", (d["brand_id"],))
    return {"draft": d, "brand": brand, "versions": versions, "check": check, "findings": findings, "events": events}


@app.post("/api/drafts/{draft_id}/check")
def check_draft(draft_id: str, user=Depends(auth.current)):
    d = workflow.get_draft(user["org_id"], draft_id)
    if d["status"] in ("in_review", "approved"):
        raise HTTPException(400, "This draft is locked while in review or approved.")
    workflow.run_and_store(user["org_id"], brand_of(user, d["brand_id"]), d, user)
    return draft_detail(draft_id, user)


class EditIn(BaseModel):
    text: str = Field(..., max_length=20000)
    alt_text: Optional[str] = None
    image_b64: Optional[str] = None
    keep_image: bool = True


@app.post("/api/drafts/{draft_id}/versions")
def edit_draft(draft_id: str, body: EditIn, user=Depends(auth.current)):
    d = workflow.get_draft(user["org_id"], draft_id)
    if d["status"] in ("in_review", "approved"):
        raise HTTPException(400, "This draft is locked while in review or approved.")
    v = workflow.current_version(user["org_id"], d)
    image = body.image_b64 or (v["image_b64"] if body.keep_image else None)
    workflow.new_version(user["org_id"], d, user, body.text, image, body.alt_text, "Edited by creator")
    if d["status"] == "changes_requested":
        db.exec("UPDATE drafts SET status = 'draft' WHERE id = ?", (d["id"],))
    workflow.log(user["org_id"], d["id"], user, "edited")
    workflow.run_and_store(user["org_id"], brand_of(user, d["brand_id"]), workflow.get_draft(user["org_id"], draft_id), user)
    return draft_detail(draft_id, user)


class DecisionIn(BaseModel):
    decision: Optional[str]
    note: Optional[str] = None
    edited_fix: Optional[str] = None


@app.post("/api/findings/{finding_id}/decision")
def decide(finding_id: str, body: DecisionIn, user=Depends(auth.current)):
    f = db.one("SELECT v.draft_id FROM findings f JOIN versions v ON v.id = f.version_id WHERE f.id = ? AND f.org_id = ?",
               (finding_id, user["org_id"]))
    if not f:
        raise HTTPException(404, "Finding not found")
    d = workflow.get_draft(user["org_id"], f["draft_id"])
    if d["status"] in ("in_review", "approved"):
        raise HTTPException(400, "This draft is locked while in review or approved.")
    return workflow.decide(user["org_id"], finding_id, user, body.decision, body.note, body.edited_fix)


@app.post("/api/drafts/{draft_id}/submit")
def submit(draft_id: str, user=Depends(auth.current)):
    d = workflow.get_draft(user["org_id"], draft_id)
    workflow.submit(user["org_id"], brand_of(user, d["brand_id"]), d, user)
    return draft_detail(draft_id, user)


class ReviewIn(BaseModel):
    action: str
    comment: Optional[str] = None


@app.post("/api/drafts/{draft_id}/review")
def review(draft_id: str, body: ReviewIn, user=Depends(auth.current)):
    auth.require(user, "manager", "reviewer", "admin")
    workflow.review(user["org_id"], workflow.get_draft(user["org_id"], draft_id), user, body.action, body.comment)
    return draft_detail(draft_id, user)


class CommentIn(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2000)


@app.post("/api/drafts/{draft_id}/comment")
def comment(draft_id: str, body: CommentIn, user=Depends(auth.current)):
    workflow.get_draft(user["org_id"], draft_id)
    workflow.log(user["org_id"], draft_id, user, "commented", body.comment)
    return draft_detail(draft_id, user)


# ---------------- rulebook ----------------
@app.get("/api/rulebook")
def get_rulebook(brand_id: Optional[str] = None, user=Depends(auth.current)):
    b = brand_of(user, brand_id)
    clauses = db.all("SELECT id, code, section, title, text, kind, check_type, params, visual, status FROM clauses "
                     "WHERE org_id = ? AND brand_id = ? ORDER BY created_at, code", (user["org_id"], b["id"]))
    for c in clauses:
        c["params"] = db.jload(c["params"], {})
    facts = db.all("SELECT id, code, fkey, value, valid_until, source FROM facts WHERE org_id = ? AND brand_id = ? "
                   "ORDER BY code", (user["org_id"], b["id"]))
    facts.sort(key=lambda f: int("".join(ch for ch in (f["code"] or "") if ch.isdigit()) or 0))
    terms = db.all("SELECT id, term, kind, replacement, clause_code FROM terms WHERE org_id = ? AND brand_id = ? "
                   "ORDER BY kind, term", (user["org_id"], b["id"]))
    return {"brand": b, "clauses": clauses, "facts": facts, "terms": terms}


class ClauseIn(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None


@app.patch("/api/clauses/{clause_id}")
def edit_clause(clause_id: str, body: ClauseIn, user=Depends(auth.current)):
    auth.require(user, "admin", "manager")
    c = db.one("SELECT * FROM clauses WHERE id = ? AND org_id = ?", (clause_id, user["org_id"]))
    if not c:
        raise HTTPException(404, "Clause not found")
    for field in ("title", "text", "kind", "status"):
        val = getattr(body, field)
        if val is not None:
            db.exec(f"UPDATE clauses SET {field} = ?, embedding = NULL WHERE id = ?", (val, clause_id))
    db.exec("UPDATE brands SET rulebook_version = rulebook_version + 1 WHERE id = ?", (c["brand_id"],))
    return {"ok": True}


@app.post("/api/rulebook/confirm-all")
def confirm_all(brand_id: str, user=Depends(auth.current)):
    auth.require(user, "admin", "manager")
    db.exec("UPDATE clauses SET status = 'confirmed' WHERE org_id = ? AND brand_id = ?", (user["org_id"], brand_id))
    return {"ok": True}


class FactIn(BaseModel):
    fkey: str
    value: str
    valid_until: Optional[str] = None
    source: Optional[str] = None


@app.post("/api/facts")
def add_fact(body: FactIn, brand_id: Optional[str] = None, user=Depends(auth.current)):
    auth.require(user, "admin", "manager")
    b = brand_of(user, brand_id)
    n = db.one("SELECT COUNT(*) AS n FROM facts WHERE brand_id = ?", (b["id"],))["n"] + 1
    db.insert("facts", {"id": db.new_id(), "org_id": user["org_id"], "brand_id": b["id"], "code": f"F{n}",
                        "fkey": body.fkey, "value": body.value, "valid_until": body.valid_until or None,
                        "source": body.source})
    return {"ok": True}


class ImportIn(BaseModel):
    name: str = "Imported brand"
    pdf_b64: Optional[str] = None
    text: Optional[str] = None


@app.post("/api/rulebook/import")
def import_rulebook(body: ImportIn, user=Depends(auth.current)):
    auth.require(user, "admin", "manager")
    if not body.pdf_b64 and not (body.text or "").strip():
        raise HTTPException(400, "Upload a PDF or paste guideline text.")
    try:
        return rulebook.import_guideline(user["org_id"], body.name, body.pdf_b64, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------- insights & evaluation ----------------
@app.get("/api/insights")
def insights(user=Depends(auth.current)):
    return workflow.insights(user["org_id"])


@app.get("/api/eval/cases")
def eval_cases(user=Depends(auth.current)):
    return evaluation.case_list()


@app.post("/api/eval/cases/{case_id}")
def eval_case(case_id: str, user=Depends(auth.current)):
    b = db.one("SELECT * FROM brands WHERE org_id = ? AND name = ? ORDER BY created_at LIMIT 1",
               (user["org_id"], "Neem & Nila Skincare"))
    if not b:
        raise HTTPException(400, "Evaluation runs on the Neem & Nila demo brand.")
    b["palette"] = db.jload(b["palette"], [])
    r = evaluation.score_case(user["org_id"], b, case_id)
    if not r:
        raise HTTPException(404, "Unknown case")
    return r


class EvalSave(BaseModel):
    results: dict


@app.post("/api/eval/runs")
def eval_save(body: EvalSave, user=Depends(auth.current)):
    evaluation.save_run(user["org_id"], body.results)
    return {"ok": True}


@app.get("/api/eval/latest")
def eval_latest(user=Depends(auth.current)):
    return evaluation.latest(user["org_id"])


# ---------------- public check API ----------------
class CheckIn(BaseModel):
    text: str = Field(..., max_length=20000)
    channel: str = "social"
    image_b64: Optional[str] = None
    alt_text: Optional[str] = None
    brand_id: Optional[str] = None


@app.post("/api/v1/check")
def public_check(body: CheckIn, user=Depends(auth.current)):
    """Stateless check for integrations (CMS hooks, browser extensions): nothing is stored."""
    if body.channel not in CHANNELS:
        raise HTTPException(400, f"channel must be one of {CHANNELS}")
    b = brand_of(user, body.brand_id)
    res = engine.run_check(user["org_id"], b, {"text": body.text, "image_b64": body.image_b64,
                                                "alt_text": body.alt_text}, body.channel)
    res.pop("content_hash", None)
    return res


# Local development: serve the web app from /public (Vercel serves it statically in production).
if os.getenv("SERVE_STATIC"):
    from fastapi.staticfiles import StaticFiles  # noqa: E402
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "public"), html=True), name="web")
