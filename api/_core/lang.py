"""Indian-language and code-mixed content (Round 3, improvement 2).

* detect(): tells English, Tamil, Hindi, Tanglish (Tamil in Latin letters mixed
  with English) and Hinglish apart, from the script and common romanised words.
* check_indic(): exact checks for Tamil and Hindi (native script and romanised):
  absolute claims, medical claims, fair-skin bias, skin shaming and the brand
  name written in another script. Each cites the same English guideline clause.
* prompt_note(): tells the AI which language it is reading, to quote in the
  original script, to fix in the same language, and to give an English meaning.
"""
import re

TAMIL = re.compile(r"[஀-௿]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN_WORD = re.compile(r"[A-Za-z]+")

# Common romanised words; two or more hits mark a code-mixed post.
TANGLISH = {"romba", "semma", "vaanga", "vanga", "machan", "machi", "enna", "illa", "illai", "irukku", "iruku",
            "panna", "pannunga", "aagum", "agum", "aaga", "ungal", "unga", "namma", "inniki", "indru", "kandippa",
            "sollunga", "paarunga", "vaangunga", "mattum", "thaan", "dhaan", "nalla", "azhaga", "azhagu",
            "poyidum", "kaanama", "seekiram", "sikiram", "kadaisi", "neenga", "da", "di", "pa", "la", "ku"}
HINGLISH = {"hai", "hain", "nahi", "nahin", "bahut", "yaar", "kya", "aur", "mein", "accha", "acha", "bilkul",
            "abhi", "jaldi", "karo", "karein", "kare", "sirf", "aaj", "apni", "apna", "aapki", "aapka", "wala",
            "wali", "hoga", "hogi", "ho", "se", "ke", "ki", "ka", "ko", "bhi", "toh", "gayab", "khatam", "chahiye"}
STRONG_TA = {"romba", "semma", "vaanga", "machan", "irukku", "pannunga", "aagum", "inniki", "kandippa", "poyidum",
             "vaangunga", "seekiram", "neenga", "azhagu", "kaanama"}
STRONG_HI = {"hai", "hain", "nahi", "bahut", "yaar", "kya", "bilkul", "jaldi", "karo", "sirf", "aapki", "gayab",
             "khatam", "chahiye", "hoga", "hogi"}

LABELS = {"en": "English", "ta": "Tamil", "hi": "Hindi", "ta-en": "Tamil + English (Tanglish)",
          "hi-en": "Hindi + English (Hinglish)", "mixed": "Mixed Indian languages"}


def detect(text):
    t = text or ""
    ta, hi = len(TAMIL.findall(t)), len(DEVANAGARI.findall(t))
    words = [w.lower() for w in LATIN_WORD.findall(t)]
    latin = len(words)
    ta_rom = sum(1 for w in words if w in TANGLISH)
    hi_rom = sum(1 for w in words if w in HINGLISH)
    ta_strong = sum(1 for w in words if w in STRONG_TA)
    hi_strong = sum(1 for w in words if w in STRONG_HI)
    latin_letters = sum(len(w) for w in words)
    if ta and hi:
        code = "mixed"
    elif ta:  # product names stay in English, so only call it mixed when English dominates
        code = "ta-en" if latin_letters > ta * 1.5 else "ta"
    elif hi:
        code = "hi-en" if latin_letters > hi * 1.5 else "hi"
    elif ta_strong >= 1 and ta_rom >= 2 and ta_rom >= hi_rom:
        code = "ta-en"
    elif hi_strong >= 1 and hi_rom >= 3 and hi_rom > ta_rom:
        code = "hi-en"
    else:
        code = "en"
    return {"code": code, "label": LABELS[code], "indic": code != "en",
            "script": "Tamil" if ta else "Devanagari" if hi else "Latin"}


# ---------------- exact checks ----------------
# Word boundary that also treats Tamil and Devanagari letters and vowel signs as part of a word.
_W = "A-Za-z0-9_\u0B80-\u0BFF\u0900-\u0963\u0966-\u097F"  # letters of Tamil and Devanagari, but not the danda (।)


def _pat(term):
    return re.compile(rf"(?<![{_W}]){re.escape(term)}(?![{_W}])", re.I)


def _stem(term):  # Tamil/Hindi words take suffixes: match the word start only
    return re.compile(rf"(?<![{_W}]){re.escape(term)}[{_W}]*", re.I)


# (terms, how to match, rule key, fix, why)
ABSOLUTE = [
    (["100% गारंटी", "गारंटी", "गारंटीड"], _pat, None,
     "'{q}' (guarantee) is an absolute claim; the brand can't guarantee results."),
    (["100% सुरक्षित"], _pat, "सौम्य", "'{q}' (100% safe) is an absolute claim."),
    (["100% प्राकृतिक", "100% नेचुरल"], _pat, "92% प्राकृतिक स्रोतों से बना",
     "'{q}' (100% natural) contradicts the fact sheet: the serum is 92% naturally derived."),
    (["केमिकल-फ्री", "केमिकल फ्री", "रसायन मुक्त"], _pat, "सौम्य सामग्री से बना",
     "'{q}' (chemical-free) is not true and not approved."),
    (["नंबर 1", "नंबर वन"], _pat, "सबका पसंदीदा", "'{q}' (number one) is an unproven superlative."),
    (["உத்தரவாதம்", "கியாரண்டி", "கேரண்டி"], _stem, None,
     "'{q}' (guarantee) is an absolute claim; the brand can't guarantee results."),
    (["100% பாதுகாப்பான"], _stem, "மென்மையான", "'{q}' (100% safe) is an absolute claim."),
    (["100% இயற்கை"], _stem, "92% இயற்கை மூலங்களிலிருந்து",
     "'{q}' (100% natural) contradicts the fact sheet: the serum is 92% naturally derived."),
    (["கெமிக்கல் இல்லாத", "ரசாயனம் இல்லாத"], _pat, "மென்மையான பொருட்களால் ஆன",
     "'{q}' (chemical-free) is not true and not approved."),
    (["நம்பர் 1", "நம்பர் ஒன்"], _pat, "பலருக்கும் பிடித்த", "'{q}' (number one) is an unproven superlative."),
    (["gaaranti", "guarantee pakka", "pakka guarantee", "100% pakka"], _pat, None,
     "'{q}' (guarantee) is an absolute claim; the brand can't guarantee results."),
]
MEDICAL = [
    re.compile(rf"(मुंहासे|मुँहासे|मुहांसे|पिंपल्स?|दाग-धब्बे|दाग|झाइयां|झाइयाँ|एक्ने)[{_W}]*\s+(?:[{_W}]+\s+){{0,3}}?"
               rf"(जड़ से खत्म|खत्म|ठीक|गायब|दूर)[{_W}]*"),
    re.compile(rf"(?<![{_W}])(इलाज)(?![{_W}])"),
    re.compile(rf"(பருக்கள்|பரு|முகப்பரு|கரும்புள்ளிகள்|கரும்புள்ளி|தழும்புகள்|தழும்பு)[{_W}]*\s+(?:[{_W}]+\s+){{0,3}}?"
               rf"(நீக்கும்|நீங்கும்|போக்கும்|போகும்|குணமாக்கும்|குணமாகும்|குணப்படுத்தும்|மறையும்|மறைந்துவிடும்|காணாமல்)[{_W}]*"),
    re.compile(rf"(?<![{_W}])(குணப்படுத்தும்|குணமாக்கும்)(?![{_W}])"),
    re.compile(r"\b(pimples?|acne|paru|daag|kumkum spots?|scars?)\s+(?:\w+\s+){0,3}?"
               r"(poyidum|pogum|poidum|kaanama|kaanaama|gayab|khatam|khatm|theek|clear aagum|cure aagum)\b", re.I),
]
FAIR = [
    (["गोरी त्वचा", "गोरा रंग"], _pat, "निखरी त्वचा"), (["गोरापन", "फेयरनेस"], _pat, "निखार"),
    (["गोरी", "गोरा"], _pat, "निखरी"),
    (["சிவப்பழகு"], _stem, "இயற்கை பொலிவு"), (["வெள்ளையாக", "சிவப்பாக"], _pat, "பொலிவாக"),
    (["ஃபேர்னஸ்", "வெண்மை"], _stem, "பொலிவு"),
    (["gori twacha", "gora rang", "goriya", "gori skin"], _pat, "glowing skin"),
    (["vellaiya", "vellai aagum", "sivappa aagum", "colour aagum", "fair aagum"], _pat, "glow aagum"),
]
SHAMING = [(["बदसूरत", "खराब त्वचा"], _pat), (["அசிங்கமான", "அசிங்கம்"], _pat), (["bekaar skin", "kharab skin"], _pat)]
BRAND = ["नीम एंड नीला", "नीम और नीला", "नीम & नीला", "नीम एन नीला", "நீம் அண்ட் நிலா", "நீம் & நிலா", "நீம் நிலா"]


def _medical_fix(m):
    """Same-language rewrite: 'helps reduce the look of <condition>'."""
    if m.lastindex is None or m.lastindex < 2:
        return None
    cond = m.group(1)
    if TAMIL.search(cond):
        return f"{cond} குறைவாகத் தெரிய உதவும்"
    if DEVANAGARI.search(cond):
        return f"{cond} कम दिखाने में मदद"  # the sentence usually continues with करता है
    return f"helps reduce the look of {cond.lower()}"


def check_indic(text, by_code, by_check, finding):
    """finding = rules._f. Returns exact findings for Tamil/Hindi/romanised text."""
    out = []
    absolute = by_check.get("lexicon")
    medical = by_check.get("medical")
    fair = by_code.get("2.5") if (by_code.get("2.5") or {}).get("title", "").lower().startswith("inclusive") else None
    shame = by_code.get("2.2") if (by_code.get("2.2") or {}).get("title", "").lower().startswith("no shaming") else None
    brand = by_code.get("1.1") if (by_code.get("1.1") or {}).get("title", "").lower().startswith("brand name") else None
    seen = set()

    def add(cat, sev, m, clause, why, fix, rule):
        key = (m.start(), m.end())
        if any(a <= m.start() and m.end() <= b for a, b in seen):
            return
        seen.add(key)
        out.append(finding(cat, sev, m.group(0), m.start(), m.end(), clause, why, fix, rule=rule))

    if medical:
        for pat in MEDICAL:
            for m in pat.finditer(text):
                add("claims", "high", m, medical, f"'{m.group(0)}' is a medical claim (treating or removing a skin "
                    "condition). Cosmetics can't make it in any language.", _medical_fix(m), "medical_indic")
    if absolute:
        for terms, mk, fix, why in ABSOLUTE:
            for t in terms:
                for m in mk(t).finditer(text):
                    add("claims", "high", m, absolute, why.format(q=m.group(0)), fix, "lexicon_indic")
    if fair:
        for terms, mk, fix in FAIR:
            for t in terms:
                for m in mk(t).finditer(text):
                    add("terminology", "high", m, fair, f"'{m.group(0)}' links beauty to fair or lighter skin, "
                        "which the brand never does in any language.", fix, "inclusive_indic")
    if shame:
        for terms, mk in SHAMING:
            for t in terms:
                for m in mk(t).finditer(text):
                    add("terminology", "high", m, shame, f"'{m.group(0)}' shames the reader's skin.", None,
                        "shaming_indic")
    if brand:
        for t in BRAND:
            for m in _pat(t).finditer(text):
                add("terminology", "medium", m, brand, "Write the brand name in English letters as 'Neem & Nila', "
                    "even in Tamil or Hindi posts.", "Neem & Nila", "brand_script")
    return out


def prompt_note(info):
    if not info or not info["indic"]:
        return ""
    return (f"LANGUAGE: the draft is in {info['label']}. The guidelines are in English but apply in every language: "
            "judge the meaning, not just English words (a Tamil or Hindi word for 'guarantee', 'cure' or 'fair skin' "
            "breaks the same clause). Quote the draft exactly in its original script. Write fix_text in the same "
            "language and script as the quoted words. Write the explanation in English and include the English "
            "meaning of the quoted words in brackets.\n\n")
