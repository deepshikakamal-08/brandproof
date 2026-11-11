"""AI gateway: one place for every model call.

- Providers are settings: LLM_PROVIDER = sarvam | gemini | openai_compat
- Every call: personal-data redaction, timeout, one retry, structured JSON.
- Vision and embeddings use Gemini's OpenAI-compatible endpoint if a key is set.
"""
import json
import os
import re
import time

TIMEOUT = float(os.getenv("LLM_TIMEOUT", "45"))           # primary provider
FALLBACK_TIMEOUT = float(os.getenv("LLM_FALLBACK_TIMEOUT", "30"))
BUDGET = float(os.getenv("LLM_BUDGET", "90"))             # whole call, all providers
FALLBACK_ORDER = ["sarvam", "sarvam_flash", "gemini", "openai_compat"]
VISION_ORDER = ["gemini", "sarvam_flash", "openai_compat"]

PROVIDERS = {
    "sarvam": {
        "url": "https://api.sarvam.ai/v1/chat/completions",
        "key": "SARVAM_API_KEY",
        "model": os.getenv("SARVAM_MODEL", "sarvam-105b"),
    },
    "sarvam_flash": {
        "url": "https://api.sarvam.ai/v2/chat/completions",
        "key": "SARVAM_API_KEY",
        "model": os.getenv("SARVAM_FLASH_MODEL", "glm5.3-flash"),
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": "GEMINI_API_KEY",
        "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    },
    "openai_compat": {
        "url": os.getenv("OPENAI_COMPAT_URL", ""),
        "key": "OPENAI_COMPAT_KEY",
        "model": os.getenv("OPENAI_COMPAT_MODEL", ""),
    },
}


def text_provider():
    name = os.getenv("LLM_PROVIDER", "sarvam")
    p = PROVIDERS.get(name)
    if p and os.getenv(p["key"]):
        return name, p
    for alt, q in PROVIDERS.items():  # fall back to any configured provider
        if q["url"] and os.getenv(q["key"]):
            return alt, q
    return None, None


def vision_provider():
    name = os.getenv("VISION_PROVIDER", "gemini")
    p = PROVIDERS.get(name)
    if p and os.getenv(p["key"]):
        model = os.getenv("VISION_MODEL", "").strip()
        if not model or model.upper() == "VISION_MODEL":  # guard against a mis-pasted setting
            model = p["model"]
        return name, {**p, "model": model}
    return None, None


MOCK = os.getenv("LLM_PROVIDER") == "mock"  # offline tests only


def status():
    if MOCK:
        return {"text_model": "mock:offline-test", "vision_model": "mock:offline-test", "embeddings": False}
    t, tp = text_provider()
    v, vp = vision_provider()
    return {
        "text_model": f"{t}:{tp['model']}" if t else None,
        "vision_model": f"{v}:{vp['model']}" if v else None,
        "embeddings": bool(os.getenv("GEMINI_API_KEY")),
    }


# ---------- personal data redaction (before anything leaves our server) ----------
_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone]"),
]


def redact(text):
    for pat, rep in _PII:
        text = pat.sub(rep, text)
    return text


class AIError(Exception):
    pass


def _headers(name, key):
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if name == "sarvam":
        h["api-subscription-key"] = key
    return h


def _extract_json(s):
    s = (s or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _candidates(vision):
    """Primary provider first, then the other configured providers as fallbacks."""
    first = vision_provider() if vision else text_provider()
    out = [first] if first[0] else []
    for name in (VISION_ORDER if vision else FALLBACK_ORDER):
        p = PROVIDERS[name]
        if p["url"] and os.getenv(p["key"]) and name != first[0]:
            out.append((name, p))
    return out


def _call(name, p, system, user, schema, schema_name, vision_image, timeout):
    import httpx
    content = redact(user)
    if vision_image:
        content = [{"type": "text", "text": content},
                   {"type": "image_url", "image_url": {"url": vision_image}}]
    body = {
        "model": p["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": 3000,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": schema_name, "schema": schema, "strict": False}},
    }
    if name in ("sarvam", "sarvam_flash"):
        effort = os.getenv("SARVAM_REASONING", "low").strip().lower()
        body["reasoning_effort"] = effort if effort in ("low", "medium", "high") else "low"
    key = os.getenv(p["key"], "").strip()
    # Some providers reject JSON-schema output: fall back to JSON mode, then to plain prompting.
    formats = [body["response_format"], {"type": "json_object"}, None]
    last = ""
    for fmt in formats:
        if fmt is None:
            body.pop("response_format", None)
        else:
            body["response_format"] = fmt
        r = httpx.post(p["url"], headers=_headers(name, key), json=body, timeout=timeout)
        if r.status_code in (429, 503):  # busy or rate-limited: one short retry
            time.sleep(2)
            r = httpx.post(p["url"], headers=_headers(name, key), json=body, timeout=timeout)
        if r.status_code in (400, 422):
            last = f"{r.status_code} {r.text[:300]}"
            continue
        if r.status_code >= 400:
            raise AIError(f"{r.status_code} {r.text[:300]}")
        msg = r.json()["choices"][0]["message"]
        return _extract_json(msg.get("content") or msg.get("reasoning_content"))
    raise AIError(last or "request rejected")


def chat_json(system, user, schema, schema_name="result", vision_image=None):
    """Returns (parsed_json, model_label). Tries providers in order within one time budget."""
    if MOCK:
        return _mock(user, schema_name, vision_image), "mock:offline-test"
    cands = _candidates(bool(vision_image))
    if not cands:
        raise AIError("No AI provider is configured")
    deadline = time.time() + BUDGET
    errors = []
    for i, (name, p) in enumerate(cands[:3]):
        left = deadline - time.time()
        if left < 8:
            break
        t0 = time.time()
        try:
            data = _call(name, p, system, user, schema, schema_name, vision_image,
                         min(TIMEOUT if i == 0 else FALLBACK_TIMEOUT, left - 2))
            print(f"[ai] {schema_name} {name}:{p['model']} ok in {time.time() - t0:.1f}s", flush=True)
            return data, f"{name}:{p['model']}"
        except Exception as e:  # timeout, busy, bad JSON: try the next provider
            print(f"[ai] {schema_name} {name}:{p['model']} failed after {time.time() - t0:.1f}s: {str(e)[:160]}", flush=True)
            errors.append(f"{name}: {str(e)[:120]}")
    raise AIError("; ".join(errors) or "out of time")


def embed(texts):
    """Gemini embeddings via OpenAI-compatible API. Returns list of vectors or None."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or not texts:
        return None
    try:
        import httpx
        r = httpx.post("https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
                       headers={"Authorization": f"Bearer {key}"},
                       json={"model": os.getenv("EMBED_MODEL", "gemini-embedding-001"),
                             "input": [redact(t) for t in texts]}, timeout=30)
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    except Exception:
        return None


def _mock(user, schema_name, image):
    """Deterministic stand-in used by offline tests. It returns one real
    finding and one uncited finding so the citation gate is exercised."""
    if schema_name == "visual_review":
        return {"issues": [{"cited_id": "V1", "severity": "high", "confidence": 0.8,
                            "explanation": "Mock: the retired orange logo appears.", "fix_text": ""}]}
    if schema_name == "rule_cards":
        return {"clauses": []}
    if schema_name == "guideline_rewrite":
        return {"rewrite": "Don't pressure readers with 'hurry' or 'last chance' unless the offer has a stated end date.",
                "do_examples": ["Offer ends 10 Nov.", "Available while stocks last."],
                "dont_examples": ["Hurry, last chance!", "Only today!"], "why": "Mock: named the allowed case."}
    draft = user.split("<<<", 1)[-1].split(">>>", 1)[0].strip()
    issues, claims = [], []
    m = re.search(r"(?i)hurry[^.!]*", draft)
    if m:
        issues.append({"category": "tone", "quote": m.group(0), "cited_id": "C3", "severity": "medium",
                       "confidence": 0.8, "explanation": "Mock: false urgency.", "fix_text": "Available while stocks last"})
    issues.append({"category": "tone", "quote": "this sentence is not in the draft", "cited_id": "C99",
                   "severity": "low", "confidence": 0.3, "explanation": "Mock: uncited", "fix_text": ""})
    m = re.search(r"₹\s?599", draft)
    if m:
        claims.append({"quote": m.group(0), "status": "outdated", "cited_id": "F2",
                       "explanation": "Mock: expired price.", "fix_text": "₹649"})
    return {"issues": issues, "claims": claims}


def probe():
    """Send one tiny request to every configured provider and report the result (no secrets)."""
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    out = {}
    for name, p in PROVIDERS.items():
        if not (p["url"] and os.getenv(p["key"])):
            continue
        t0 = time.time()
        try:
            data = _call(name, p, "Reply with JSON only.", 'Return {"ok": true}.', schema, "probe", None, 30)
            out[name] = {"model": p["model"], "ok": True, "seconds": round(time.time() - t0, 1), "reply": data}
        except Exception as e:
            out[name] = {"model": p["model"], "ok": False, "seconds": round(time.time() - t0, 1),
                         "error": f"{type(e).__name__}: {str(e)[:400]}"}
    key = os.getenv("GEMINI_API_KEY", "")
    out["key_check"] = {k: ("set" if os.getenv(k) else "missing") + (" (has spaces/newline!)" if os.getenv(k, "").strip() != os.getenv(k, "") else "")
                        for k in ("SARVAM_API_KEY", "GEMINI_API_KEY")}
    if key:
        t0 = time.time()
        v = embed(["test"])
        out["embeddings"] = {"ok": bool(v), "seconds": round(time.time() - t0, 1)}
    return out
