"""Turn any brand guideline (PDF or pasted text) into rule cards."""
import base64
import re

from . import db, llm

CHECK_TYPES = ["terms", "emoji", "readability", "caps", "exclamation", "hashtags", "alt_text", "palette",
               "lexicon", "medical", "none"]

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {"clauses": {"type": "array", "items": {"type": "object", "properties": {
        "index": {"type": "integer"},
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": ["exact", "judgement"]},
        "check_type": {"type": "string", "enum": CHECK_TYPES},
        "visual": {"type": "boolean"},
        "terms": {"type": "array", "items": {"type": "object", "properties": {
            "term": {"type": "string"},
            "kind": {"type": "string", "enum": ["banned", "brand_name", "product_name", "spelling"]},
            "replacement": {"type": "string"}}, "required": ["term", "kind", "replacement"]}}},
        "required": ["index", "title", "kind", "check_type", "visual", "terms"]}}},
    "required": ["clauses"],
}


def extract_text(file_b64=None, text=None):
    if text:
        return text
    raw = base64.b64decode(file_b64.split(",", 1)[-1])
    import fitz  # PyMuPDF
    doc = fitz.open(stream=raw, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


HEAD = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})[.)]?\s+(.{3,})$")


def split_clauses(text):
    lines = [l.rstrip() for l in text.splitlines()]
    out, cur, section = [], None, "General"
    for line in lines:
        m = HEAD.match(line)
        if m:
            code, rest = m.group(1), m.group(2).strip()
            if "." not in code:  # top-level heading = section
                section = rest
                if cur:
                    out.append(cur)
                cur = None
                continue
            if cur:
                out.append(cur)
            cur = {"code": code, "section": section, "text": rest}
        elif line.strip() and cur:
            cur["text"] += " " + line.strip()
    if cur:
        out.append(cur)
    if len(out) < 3:  # no numbering: one clause per paragraph or bullet
        paras = [p.strip() for p in re.split(r"\n\s*\n|\n\s*[-•*]\s+", text) if len(p.strip()) > 25]
        out = [{"code": f"{i}", "section": "General", "text": re.sub(r"\s+", " ", p)} for i, p in enumerate(paras, 1)]
    return out[:80]


def _heuristic(c):
    t = c["text"].lower()
    rules = [("emoji", "emoji"), ("hashtag", "hashtags"), ("all caps", "caps"), ("capital", "caps"),
             ("exclamation", "exclamation"), ("alt text", "alt_text"), ("reading", "readability"),
             ("#", "palette"), ("palette", "palette")]
    for kw, ct in rules:
        if kw in t:
            return {"kind": "exact", "check_type": ct}
    visual = any(w in t for w in ("logo", "image", "photo", "visual", "colour", "color"))
    return {"kind": "judgement", "check_type": "none", "visual": visual}


def classify(clauses):
    try:
        listing = "\n".join(f"{i}. [{c['code']}] {c['text']}" for i, c in enumerate(clauses))
        data, _ = llm.chat_json(
            "You turn brand guideline clauses into machine-checkable rule cards. Reply with JSON only.",
            "For each clause decide: a short title; kind = exact if code can check it with certainty "
            "(specific words, counts, colours, alt text), otherwise judgement; check_type for exact clauses "
            f"(one of {', '.join(CHECK_TYPES)}); visual = true if it is about images or logos; and any specific "
            "terms the clause names as banned or required, with their approved replacement.\n\n" + listing,
            CLASSIFY_SCHEMA, "rule_cards")
        by_i = {x["index"]: x for x in data.get("clauses", [])}
        return [by_i.get(i) for i in range(len(clauses))], True
    except Exception:
        return [None] * len(clauses), False


def import_guideline(org_id, name, file_b64=None, text=None):
    raw = extract_text(file_b64, text)
    parts = split_clauses(raw)
    if not parts:
        raise ValueError("No guideline text found in this file.")
    labels, used_ai = classify(parts)
    brand_id = db.new_id()
    db.insert("brands", {"id": brand_id, "org_id": org_id, "name": name or "Imported brand",
                         "description": "Imported from an uploaded guideline", "tone_summary": "See clauses",
                         "palette": db.jdump(_palette_from(raw)), "rulebook_version": 1, "created_at": db.now()})
    clause_rows, term_rows = [], []
    for c, lab in zip(parts, labels):
        h = _heuristic(c)
        lab = lab or {}
        kind = lab.get("kind") or h["kind"]
        ct = lab.get("check_type") or h.get("check_type")
        if ct == "none":
            ct = None
        if kind == "exact" and not ct:
            kind = "judgement"
        clause_rows.append({"id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "code": c["code"],
                            "section": c["section"], "title": lab.get("title") or c["text"][:48],
                            "text": c["text"], "kind": kind, "check_type": ct, "params": db.jdump(_default_params(ct)),
                            "visual": 1 if (lab.get("visual") if lab else h.get("visual")) else 0,
                            "status": "draft", "embedding": None, "created_at": db.now()})
        for t in lab.get("terms") or []:
            if t.get("term"):
                term_rows.append({"id": db.new_id(), "org_id": org_id, "brand_id": brand_id, "term": t["term"],
                                  "kind": t.get("kind", "banned"), "replacement": t.get("replacement", ""),
                                  "clause_code": c["code"], "unless_preceded_by": None})
    db.insert_many("clauses", clause_rows)
    db.insert_many("terms", term_rows)
    return {"brand_id": brand_id, "clauses": len(clause_rows), "terms": len(term_rows), "used_ai": used_ai}


def _palette_from(text):
    hexes = list(dict.fromkeys(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", text)))
    return [{"name": h, "hex": h} for h in hexes] + [{"name": "White", "hex": "#FFFFFF"}] if hexes else []


def _default_params(ct):
    return {
        "emoji": {"social": 3, "whatsapp": 3, "email": 1, "blog": 0, "press": 0, "packaging": 0},
        "readability": {"social": 60, "whatsapp": 60, "email": 60, "blog": 50, "press": 50, "packaging": 50},
        "caps": {"allow": ["SPF", "UV", "PA", "OK", "FAQ"]},
        "exclamation": {"max": 1},
        "hashtags": {"max": 5, "channels": ["social"]},
        "palette": {"min_share": 0.12, "max_distance": 25},
    }.get(ct, {})
