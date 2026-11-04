"""The check engine: exact rules -> retrieval -> AI judgement + claim check
-> citation gate -> fixes. Returns findings that each cite a real source.
"""
import difflib
import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import db, llm, retrieval

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - local fallback without the C extension
    fuzz = None
from .rules import run_exact

SEV = {"high": 0, "medium": 1, "low": 2}

_AI_FULL = {
    "type": "object",
    "properties": {
        "issues": {"type": "array", "items": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["tone", "claims", "legal", "accessibility", "terminology"]},
            "quote": {"type": "string"},
            "cited_id": {"type": "string"},
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "confidence": {"type": "number"},
            "explanation": {"type": "string"},
            "fix_text": {"type": "string"}},
            "required": ["category", "quote", "cited_id", "severity", "confidence", "explanation", "fix_text"]}},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "quote": {"type": "string"},
            "status": {"type": "string", "enum": ["supported", "outdated", "contradicted", "unsupported"]},
            "cited_id": {"type": "string"},
            "explanation": {"type": "string"},
            "fix_text": {"type": "string"}},
            "required": ["quote", "status", "cited_id", "explanation", "fix_text"]}},
    },
    "required": ["issues", "claims"],
}

ISSUES_SCHEMA = {"type": "object", "properties": {"issues": _AI_FULL["properties"]["issues"]}, "required": ["issues"]}
CLAIMS_SCHEMA = {"type": "object", "properties": {"claims": _AI_FULL["properties"]["claims"]}, "required": ["claims"]}

VISION_SCHEMA = {
    "type": "object",
    "properties": {"issues": {"type": "array", "items": {"type": "object", "properties": {
        "cited_id": {"type": "string"},
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence": {"type": "number"},
        "explanation": {"type": "string"},
        "fix_text": {"type": "string"}},
        "required": ["cited_id", "severity", "confidence", "explanation", "fix_text"]}}},
    "required": ["issues"],
}

SYSTEM = (
    "You are a meticulous brand-compliance reviewer. You only flag problems that break one of the numbered "
    "guideline clauses (C#) or contradict one of the numbered approved facts (F#) you are given. Never invent "
    "rules. Every issue must quote the exact words from the draft (copy them character for character) and cite "
    "exactly one id. If something required is missing (for example #ad or an offer end date), quote the sentence "
    "it belongs to. Suggested fixes must be the smallest rewrite of the quoted words that keeps the writer's "
    "meaning and voice. Do not flag spelling, emoji counts, hashtags, capital letters or exclamation marks: other "
    "checks handle those. If the draft is compliant, return empty lists. Respond with JSON only."
)


def _context(text, channel, brand, clauses, facts, today):
    cl = "\n".join(f"{c['_id']} [{c['code']} {c['title']}] {c['text']}" for c in clauses)
    fa = "\n".join(f"{f['_id']} {f['fkey']}: {f['value']}"
                   + (f" (valid until {f['valid_until']})" if f.get("valid_until") else "") for f in facts)
    return (f"Brand: {brand['name']}. Voice: {brand['tone_summary']}\nToday's date: {today}\nChannel: {channel}\n\n"
            f"GUIDELINE CLAUSES\n{cl}\n\n" + (f"APPROVED FACTS\n{fa}\n\n" if facts else "") +
            f"DRAFT\n<<<\n{text}\n>>>\n\n")


def _issues_prompt(text, channel, brand, clauses, today):
    return _context(text, channel, brand, clauses, [], today) + (
        "Return issues: tone, messaging, pressure tactics, competitor mentions, legal/disclosure (#ad, offer terms) "
        "and other breaches of the clauses above, each citing one C id. Ignore factual accuracy: another check does "
        "that. Keep explanations to one sentence. confidence is 0-1.")


def _claims_prompt(text, channel, brand, clauses, facts, today):
    return _context(text, channel, brand, clauses, facts, today) + (
        "Return claims: every factual or promotional claim in the draft (price, ingredient, percentage, result, "
        "certification, offer). status = supported if a fact backs it (cite that F id); outdated if it matches an "
        "expired fact (cite that F id); contradicted if a fact says otherwise (cite that F id); unsupported if no "
        "fact backs it (cite the C id of the claims rule). Keep explanations to one sentence.")


def _locate(text, quote):
    if not quote or quote.strip() in ("", "*", "[image]"):
        return None
    q = quote.strip().strip('"').strip("'")
    i = text.lower().find(q.lower())
    if i >= 0:
        return i, i + len(q)
    if fuzz:
        al = fuzz.partial_ratio_alignment(q.lower(), text.lower())
        if al and al.score >= 90:
            return al.dest_start, al.dest_end
        return None
    m = difflib.SequenceMatcher(None, text.lower(), q.lower()).find_longest_match(0, len(text), 0, len(q))
    return (m.a, m.a + m.size) if m.size >= 0.9 * len(q) else None


def _fix_ok(text, start, end, fix):
    """Intent check: the fixed sentence must stay close to the original."""
    if fix is None:
        return None
    s = text.rfind(".", 0, start) + 1
    e = text.find(".", end)
    e = len(text) if e < 0 else e
    before = text[s:e]
    after = text[s:start] + fix + text[end:e]
    if len(before) > 25 and difflib.SequenceMatcher(None, before, after).ratio() < 0.45:
        return None
    return fix


def _overlaps(a, b):
    return a["start"] is not None and b["start"] is not None and a["start"] < b["end"] and b["start"] < a["end"]


def rulebook_fingerprint(clauses, facts, terms, brand):
    h = hashlib.sha256()
    for c in sorted(clauses, key=lambda c: c["code"] or ""):
        h.update(f"{c['code']}|{c['text']}|{c['kind']}|{c.get('check_type')}|{c.get('params')}|{c.get('status')}".encode())
    for f in sorted(facts, key=lambda f: f["code"] or ""):
        h.update(f"{f['code']}|{f['value']}|{f.get('valid_until')}".encode())
    for t in sorted(terms, key=lambda t: t["term"]):
        h.update(f"{t['term']}|{t['kind']}|{t['replacement']}".encode())
    h.update(db.jdump(brand["palette"]).encode())
    return h.hexdigest()


def load_rulebook(org_id, brand):
    clauses = db.all("SELECT * FROM clauses WHERE org_id = ? AND brand_id = ? AND status = 'confirmed' ORDER BY code",
                     (org_id, brand["id"]))
    for c in clauses:
        c["params"] = db.jload(c["params"], {})
    facts = db.all("SELECT * FROM facts WHERE org_id = ? AND brand_id = ?", (org_id, brand["id"]))
    facts.sort(key=lambda f: int(re.sub(r"\D", "", f["code"] or "") or 0))
    terms = db.all("SELECT * FROM terms WHERE org_id = ? AND brand_id = ?", (org_id, brand["id"]))
    return clauses, facts, terms


def run_check(org_id, brand, version, channel, use_cache=True):
    t0 = time.time()
    text, image, alt = version["text"] or "", version.get("image_b64"), version.get("alt_text")
    clauses, facts, terms = load_rulebook(org_id, brand)
    status = llm.status()
    key = hashlib.sha256("|".join([text, channel, image or "", alt or "", str(date.today()),
                                   rulebook_fingerprint(clauses, facts, terms, brand),
                                   str(status["text_model"]), str(status["vision_model"])]).encode()).hexdigest()
    if use_cache:
        hit = db.one("SELECT payload FROM check_cache WHERE content_hash = ?", (key,))
        if hit:
            payload = db.jload(hit["payload"])
            payload["cached"] = True
            return payload

    findings = run_exact(text, channel, image, alt, clauses, terms, brand["palette"])

    judgement = [c for c in clauses if c["kind"] == "judgement" and not c.get("visual")]
    visual = [c for c in clauses if c.get("visual")]
    picked = retrieval.top_clauses(text, judgement, k=12)
    for i, c in enumerate(picked, 1):
        c["_id"] = f"C{i}"
    fact_list = facts if len(facts) <= 25 else [facts[i] for i in retrieval.bm25_rank(text, [f"{f['fkey']} {f['value']}" for f in facts])[:15]]
    for i, f in enumerate(fact_list, 1):
        f["_id"] = f["code"] if re.fullmatch(r"F\d+", f["code"] or "") else f"F{i}"
    ids = {c["_id"]: ("clause", c) for c in picked}
    ids.update({f["_id"]: ("fact", f) for f in fact_list})

    ai_status, model, dropped, verified = "ok", None, 0, []
    jobs = {}
    today = date.today().isoformat()
    claim_clauses = [c for c in picked if (c["code"] or "").startswith("4.")] or picked
    with ThreadPoolExecutor(max_workers=3) as pool:
        if text.strip() and status["text_model"]:
            # two smaller calls in parallel answer much faster than one large one
            jobs["issues"] = pool.submit(llm.chat_json, SYSTEM, _issues_prompt(text, channel, brand, picked, today),
                                         ISSUES_SCHEMA, "brand_issues")
            jobs["claims"] = pool.submit(llm.chat_json, SYSTEM,
                                         _claims_prompt(text, channel, brand, claim_clauses, fact_list, today),
                                         CLAIMS_SCHEMA, "brand_claims")
        if image and visual and status["vision_model"]:
            for i, c in enumerate(visual, 1):
                c["_id"] = f"V{i}"
            vprompt = ("Review this marketing image against these visual guideline clauses. Flag only clear breaches, "
                       "each citing one V id. Return empty issues if compliant.\n" +
                       "\n".join(f"{c['_id']} [{c['code']} {c['title']}] {c['text']}" for c in visual))
            jobs["vision"] = pool.submit(llm.chat_json, SYSTEM, vprompt, VISION_SCHEMA, "visual_review", image)
        results = {}
        for name, fut in jobs.items():
            try:
                results[name] = fut.result()
            except Exception as e:  # never crash the page: rule findings still return
                results[name] = e
    if not status["text_model"]:
        ai_status = "not_configured"

    text_parts = [k for k in ("issues", "claims") if k in results]
    failed = [k for k in text_parts if isinstance(results[k], Exception)]
    if text_parts and len(failed) == len(text_parts):
        ai_status = "failed"
    elif failed:
        ai_status = "partial"
    models = []
    if "issues" in results and not isinstance(results["issues"], Exception):
        data, m = results["issues"]
        models.append(m)
        for it in data.get("issues", []):
            f = _gate(text, it, ids, findings, kind="issue")
            if f:
                findings.append(f)
            else:
                dropped += 1
    if "claims" in results and not isinstance(results["claims"], Exception):
        data, m = results["claims"]
        models.append(m)
        for it in data.get("claims", []):
            if it.get("status") == "supported":
                ref = ids.get(str(it.get("cited_id", "")).strip())
                if ref and _locate(text, it.get("quote")):
                    verified.append({"quote": it["quote"], "cite_code": ref[1]["code"]})
                continue
            f = _gate(text, it, ids, findings, kind="claim")
            if f:
                findings.append(f)
            else:
                dropped += 1
    model = ", ".join(dict.fromkeys(models)) or None
    if "vision" in results:
        r = results["vision"]
        if isinstance(r, Exception):
            ai_status = "partial" if ai_status == "ok" else ai_status
        else:
            vdata, vmodel = r
            vids = {c["_id"]: c for c in visual}
            for it in vdata.get("issues", []):
                c = vids.get(str(it.get("cited_id", "")).strip())
                if not c:
                    dropped += 1
                    continue
                findings.append({
                    "category": "visual", "severity": it.get("severity", "medium"),
                    "confidence": float(it.get("confidence", 0.7)), "source": "ai", "rule": "vision",
                    "quote": "[image]", "start": None, "end": None, "cite_type": "clause", "cite_code": c["code"],
                    "cite_text": c["text"], "explanation": it.get("explanation", ""), "fix_text": None,
                    "claim_status": None, "model": vmodel})

    findings.sort(key=lambda f: (SEV.get(f["severity"], 3), f["start"] if f["start"] is not None else 10 ** 6))
    payload = {
        "findings": findings, "model": model if ai_status in ("ok", "partial") else None,
        "ai_status": ai_status, "dropped_uncited": dropped, "verified_claims": verified,
        "duration_ms": int((time.time() - t0) * 1000), "content_hash": key, "cached": False,
        "retrieved": [c["code"] for c in picked],
    }
    if ai_status == "ok":
        db.exec("DELETE FROM check_cache WHERE content_hash = ?", (key,))
        db.insert("check_cache", {"content_hash": key, "payload": db.jdump(payload), "created_at": db.now()})
    return payload


def _gate(text, it, ids, existing, kind):
    """Citation gate: keep an AI finding only if it cites a real source we gave it
    and quotes text that really is in the draft."""
    cid = str(it.get("cited_id", "")).strip().upper()
    ref = ids.get(cid)
    if not ref:
        return None
    rtype, src = ref
    if kind == "claim" and it.get("status") in ("outdated", "contradicted") and rtype != "fact":
        return None
    loc = _locate(text, it.get("quote"))
    if not loc:
        return None
    s, e = loc
    category = "claims" if kind == "claim" else it.get("category", "tone")
    if category not in ("tone", "claims", "legal", "accessibility", "terminology"):
        category = "tone"
    cand = {"start": s, "end": e}
    for ex in existing:
        if ex["category"] == category and _overlaps(ex, cand):
            return None  # an exact rule already covers this
    fix = it.get("fix_text") or None
    fix = _fix_ok(text, s, e, fix) if fix else None
    sev = it.get("severity") or ("high" if kind == "claim" else "medium")
    if kind == "claim":
        sev = "high" if it["status"] in ("contradicted", "outdated") else "medium"
    if rtype == "clause":
        code, ctext = src["code"], src["text"]
    else:
        code = src["code"]
        ctext = f"{src['fkey']}: {src['value']}" + (f" (valid until {src['valid_until']})" if src.get("valid_until") else "")
    return {
        "category": category, "severity": sev, "confidence": round(float(it.get("confidence", 0.75)), 2),
        "source": "ai", "rule": "claim" if kind == "claim" else "judgement",
        "quote": text[s:e], "start": s, "end": e, "cite_type": rtype, "cite_code": code, "cite_text": ctext,
        "explanation": it.get("explanation", ""), "fix_text": fix,
        "claim_status": it.get("status") if kind == "claim" else None,
    }


def apply_fixes(text, findings):
    """Apply accepted/edited fixes from the end of the text backwards."""
    edits = []
    for f in findings:
        s = f.get("start_idx", f.get("start"))
        e = f.get("end_idx", f.get("end"))
        if s is None or e is None or f.get("decision") not in ("accepted", "edited"):
            continue
        rep = f.get("edited_fix") if f.get("decision") == "edited" else f.get("fix_text")
        if rep is None:
            continue
        edits.append((s, e, rep))
    edits.sort(key=lambda x: -x[0])
    last = len(text) + 1
    for s, e, rep in edits:
        if e > last:  # overlapping edit: skip the inner one
            continue
        text = text[:s] + rep + text[e:]
        last = s
    return re.sub(r"[ \t]{2,}", " ", text)
