"""Exact checks: rules that code can verify with certainty.

Each rule is driven by a rulebook clause (check_type + params) or by the
terms table, so editing the rulebook changes behaviour without new code.
Every finding cites the clause or term it comes from.
"""
import base64
import io
import re

from .demo_data import LEXICON

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF☀-➿⭐⭕←-⇿]️?")
EMOJI_RUN = re.compile("(?:[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF☀-➿⭐⭕]️?)+")

LEXICON_FIX = {
    "guaranteed": "visible", "guarantee": "promise", "100% safe": "gentle", "100% natural": "92% naturally derived",
    "chemical-free": "made with gentle, plant-powered ingredients", "chemical free": "made with gentle, plant-powered ingredients",
    "clinically proven": "dermatologist tested", "no. 1": "much-loved", "no.1": "much-loved", "number one": "much-loved",
    "#1": "much-loved", "best in india": "one of our best-loved products", "miracle": "everyday",
    "instant results": "visible results with regular use", "dermatologist approved": "dermatologist tested",
    "100% protection": "SPF 50, PA++++ protection", "waterproof": "lightweight", "zero side effects": "gentle",
    "no side effects": "gentle",
}

MEDICAL = re.compile(
    r"\b(cures?|cured|heals?|healed|treats?|treated|removes?|eliminates?|get rid of|clears?|"
    r"say goodbye to|no more)\b(?:\s+\w+){0,4}?\s+"
    r"(acne|pimples?|eczema|pigmentation|scars?|dark spots?|wrinkles?|damaged skin|breakouts?|rosacea|melasma)",
    re.I)


def _f(category, severity, quote, start, end, clause, explanation, fix=None, rule="", cite_type="clause",
       cite_code=None, cite_text=None):
    return {
        "category": category, "severity": severity, "confidence": 1.0, "source": "rule", "rule": rule,
        "quote": quote, "start": start, "end": end, "cite_type": cite_type,
        "cite_code": cite_code or (clause["code"] if clause else None),
        "cite_text": cite_text or (clause["text"] if clause else None),
        "explanation": explanation, "fix_text": fix, "claim_status": None,
    }


def _match_case(src, rep, text=None, start=None):
    """Capitalise the fix only where the original starts a sentence."""
    if not rep:
        return rep
    at_start = True
    if text is not None and start is not None:
        before = text[:start].rstrip()
        at_start = before == "" or before[-1] in ".!?\n:"
    if src[:1].isupper() and at_start:
        return rep[0].upper() + rep[1:]
    if not at_start and rep[:1].isupper() and not src[:1].isupper():
        return rep[0].lower() + rep[1:]
    return rep


def _bounded(term):
    t = re.escape(term.strip())
    return re.compile(rf"(?<![\w&]){t}(?![\w&])", re.I)


def check_terms(text, terms, clauses_by_code):
    out = []
    labels = {"brand_name": ("terminology", "medium", "The brand name must be written exactly as approved."),
              "product_name": ("terminology", "low", "Use the full approved product name."),
              "banned": ("terminology", "high", "This phrase is banned by the brand guidelines."),
              "spelling": ("terminology", "low", "Use Indian English spelling and the ₹ symbol."),
              "link": ("accessibility", "medium", "Link text must say where it goes.")}
    for t in terms:
        cat, sev, why = labels.get(t["kind"], ("terminology", "low", "Not the approved term."))
        for m in _bounded(t["term"]).finditer(text):
            pre = t.get("unless_preceded_by")
            if pre and text[max(0, m.start() - len(pre)):m.start()].lower() == pre.lower():
                continue
            q = m.group(0)
            clause = clauses_by_code.get(t["clause_code"])
            rep = t["replacement"]
            fix = rep if t["kind"] in ("brand_name", "product_name") else _match_case(q, rep, text, m.start())
            out.append(_f(cat, sev, q, m.start(), m.end(), clause,
                          f"{why} '{q}' should be '{fix}'.", fix, rule="terms"))
    return out


def check_lexicon(text, clause):
    out = []
    for word, _ in LEXICON:
        for m in _bounded(word).finditer(text):
            q = m.group(0)
            out.append(_f("claims", "high", q, m.start(), m.end(), clause,
                          f"'{q}' is an absolute claim that is not on the approved fact sheet.",
                          _match_case(q, LEXICON_FIX.get(word.lower()), text, m.start()), rule="lexicon"))
    return out


def check_medical(text, clause):
    out = []
    for m in MEDICAL.finditer(text):
        cond = m.group(2)
        verb = m.group(1).lower()
        helper = "helps" if verb.endswith("s") and verb not in ("no more",) else "help"
        out.append(_f("claims", "high", m.group(0), m.start(), m.end(), clause,
                      f"This is a medical claim about {cond}. Cosmetics cannot claim to treat or remove skin conditions.",
                      _match_case(m.group(0), f"{helper} reduce the look of {cond}", text, m.start()), rule="medical"))
    return out


def check_emoji(text, clause, channel):
    limit = (clause.get("params") or {}).get(channel)
    if limit is None:
        return []
    count = len(EMOJI.findall(text))
    if count <= limit:
        return []
    runs = list(EMOJI_RUN.finditer(text))
    m = max(runs, key=lambda r: len(r.group(0))) if runs else None
    where = f"{channel} posts allow {limit} emoji" if limit else f"{channel} content uses no emoji"
    fix = None
    if m:
        keep = EMOJI.findall(m.group(0))[:max(limit, 0)]
        fix = "".join(keep)
    return [_f("style", "low", m.group(0) if m else "*", m.start() if m else None, m.end() if m else None, clause,
               f"Found {count} emoji; {where}.", fix, rule="emoji")]


def _syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee")):
        n -= 1
    return max(1, n)


def flesch(text):
    body = re.sub(r"#\w+|https?://\S+|Subject:", " ", text)
    sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)|\n", body)))
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", body)
    if len(words) < 30:  # too short for a reliable score
        return None
    syl = sum(_syllables(w) for w in words)
    return round(206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syl / len(words)), 1)


def check_readability(text, clause, channel):
    target = (clause.get("params") or {}).get(channel)
    score = flesch(text)
    if target is None or score is None or score >= target:
        return []
    # point at the longest sentence
    sents = [(m.start(), m.end()) for m in re.finditer(r"[^.!?\n]+[.!?]?", text)]
    s, e = max(sents, key=lambda x: x[1] - x[0]) if sents else (None, None)
    return [_f("style", "medium", text[s:e].strip() if s is not None else "*", s, e, clause,
               f"Reading ease is {score}; the target for {channel} is {target}+. Use shorter sentences and everyday words.",
               None, rule="readability")]


def check_caps(text, clause):
    allow = {a.upper() for a in (clause.get("params") or {}).get("allow", [])}
    out = []
    for m in re.finditer(r"(?<![#@\w])[A-Z]{3,}(?![\w])", text):
        w = m.group(0)
        if w in allow:
            continue
        out.append(_f("style", "low", w, m.start(), m.end(), clause,
                      f"'{w}' is in ALL CAPS, which reads as shouting.", w.capitalize() if m.start() == 0 else w.lower(),
                      rule="caps"))
    return out


def check_exclamation(text, clause):
    limit = (clause.get("params") or {}).get("max", 1)
    marks = text.count("!")
    if marks <= limit:
        return []
    runs = list(re.finditer(r"!{2,}", text))
    if runs:
        m = runs[0]
        return [_f("style", "low", m.group(0), m.start(), m.end(), clause,
                   f"{marks} exclamation marks used; the limit is {limit}.", "!" if limit else ".", rule="exclamation")]
    i = [m.start() for m in re.finditer("!", text)][limit]
    return [_f("style", "low", "!", i, i + 1, clause,
               f"{marks} exclamation marks used; the limit is {limit}.", ".", rule="exclamation")]


def check_hashtags(text, clause, channel):
    p = clause.get("params") or {}
    if channel not in p.get("channels", ["social"]):
        return []
    tags = list(re.finditer(r"#\w+", text))
    out = []
    mx = p.get("max", 5)
    if len(tags) > mx:
        first_x, last_x = tags[mx], tags[-1]
        out.append(_f("style", "low", text[first_x.start():last_x.end()], first_x.start(), last_x.end(), clause,
                      f"{len(tags)} hashtags used; the limit is {mx}.", "", rule="hashtags"))
    req = p.get("required")
    if req and req.lower() not in text.lower():
        if tags:
            first = tags[0]
            out.append(_f("style", "low", first.group(0), first.start(), first.end(), clause,
                          f"Social posts must include {req}.",
                          req if len(tags) >= mx else f"{req} {first.group(0)}", rule="hashtags"))
        else:
            out.append(_f("style", "low", "*", None, None, clause, f"Social posts must include {req}.", None,
                          rule="hashtags"))
    return out


def check_alt_text(image, alt_text, clause):
    if image and not (alt_text or "").strip():
        return [_f("accessibility", "high", "[image]", None, None, clause,
                   "The image has no alt text, so screen-reader users cannot tell what it shows.",
                   None, rule="alt_text")]
    return []


# ---------- palette (image) ----------
def _lab(rgb):
    import numpy as np
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def dominant_colours(image_b64, k=5):
    import numpy as np
    from PIL import Image
    raw = base64.b64decode(image_b64.split(",", 1)[-1])
    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((64, 64))
    px = np.asarray(im, dtype=float).reshape(-1, 3)
    rng = np.random.default_rng(0)
    cent = px[rng.choice(len(px), k, replace=False)]
    for _ in range(12):
        lab_d = ((px[:, None, :] - cent[None]) ** 2).sum(-1)
        lbl = lab_d.argmin(1)
        cent = np.array([px[lbl == i].mean(0) if (lbl == i).any() else cent[i] for i in range(k)])
    shares = np.bincount(lbl, minlength=k) / len(px)
    return [(cent[i], float(shares[i])) for i in np.argsort(-shares)]


def check_palette(image_b64, clause, palette):
    import numpy as np
    if not image_b64 or not palette:
        return []
    p = clause.get("params") or {}
    pal = np.array([[int(c["hex"][i:i + 2], 16) for i in (1, 3, 5)] for c in palette], dtype=float)
    pal_lab = _lab(pal)
    off = []
    for rgb, share in dominant_colours(image_b64):
        if share < p.get("min_share", 0.12):
            continue
        d = np.sqrt(((pal_lab - _lab(rgb[None]))[...] ** 2).sum(-1)).min()
        if d > p.get("max_distance", 25):
            hexc = "#%02X%02X%02X" % tuple(int(x) for x in rgb)
            off.append(f"{hexc} ({round(share * 100)}% of the image)")
    if not off:
        return []
    return [_f("visual", "medium", "[image]", None, None, clause,
               "Large areas use colours outside the brand palette: " + ", ".join(off) + ".",
               None, rule="palette")]


def run_exact(text, channel, image_b64, alt_text, clauses, terms, palette):
    by_code = {c["code"]: c for c in clauses}
    by_check = {}
    for c in clauses:
        if c["kind"] == "exact" and c.get("check_type"):
            by_check.setdefault(c["check_type"], c)
    out = check_terms(text, terms, by_code)
    if "lexicon" in by_check:
        out += check_lexicon(text, by_check["lexicon"])
    if "medical" in by_check:
        out += check_medical(text, by_check["medical"])
    if "emoji" in by_check:
        out += check_emoji(text, by_check["emoji"], channel)
    if "readability" in by_check:
        out += check_readability(text, by_check["readability"], channel)
    if "caps" in by_check:
        out += check_caps(text, by_check["caps"])
    if "exclamation" in by_check:
        out += check_exclamation(text, by_check["exclamation"])
    if "hashtags" in by_check:
        out += check_hashtags(text, by_check["hashtags"], channel)
    if "alt_text" in by_check:
        out += check_alt_text(image_b64, alt_text, by_check["alt_text"])
    if "palette" in by_check and image_b64:
        out += check_palette(image_b64, by_check["palette"], palette)
    return _dedupe(out)


def _dedupe(findings):
    """Drop findings fully inside a longer finding of the same category."""
    keep = []
    for f in sorted(findings, key=lambda x: -((x["end"] or 0) - (x["start"] or 0))):
        if f["start"] is not None and any(
                k["category"] == f["category"] and k["start"] is not None and k["start"] <= f["start"]
                and f["end"] <= k["end"] and k is not f for k in keep):
            continue
        keep.append(f)
    return keep
