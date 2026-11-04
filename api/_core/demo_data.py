"""Demo brand: Neem & Nila Skincare (fictional).

Every guest workspace is cloned from this template, so judges can start
checking content immediately. All names, prices and facts are invented.
"""

BRAND = {
    "name": "Neem & Nila Skincare",
    "description": "Indian D2C skincare brand: gentle, plant-powered, science-backed.",
    "tone_summary": "Warm, calm and expert, like a knowledgeable friend. Explains, never shouts.",
    "palette": [
        {"name": "Deep Teal", "hex": "#0F5257"},
        {"name": "Neem Green", "hex": "#6A994E"},
        {"name": "Sand", "hex": "#F2E8CF"},
        {"name": "Nila Blue", "hex": "#3D5A80"},
        {"name": "Coral (accent)", "hex": "#EE6C4D"},
        {"name": "White", "hex": "#FFFFFF"},
        {"name": "Ink", "hex": "#1D2B2E"},
    ],
}

# kind: exact = checked by code, judgement = checked by AI with citation.
# check: which rule handles an exact clause; params tune it.
CLAUSES = [
    # 1 Brand basics
    {"code": "1.1", "section": "Brand basics", "title": "Brand name",
     "text": "Always write the brand name as 'Neem & Nila', with an ampersand and both words capitalised. Never 'Neem and Nila', 'NeemNila', 'N&N' or 'Neem n Nila'.",
     "kind": "exact", "check": "terms"},
    {"code": "1.2", "section": "Brand basics", "title": "Product names",
     "text": "Use the full approved product names: 'Glow Ritual Vitamin C Serum', 'Calm Neem Face Wash', 'Nila Night Repair Cream', 'Sun Shield SPF 50 Gel'.",
     "kind": "exact", "check": "terms"},
    # 2 Voice and tone
    {"code": "2.1", "section": "Voice and tone", "title": "Our voice",
     "text": "Our voice is warm, calm and expert, like a knowledgeable friend. We explain, we don't shout. Avoid slang, hype and pressure tactics.",
     "kind": "judgement"},
    {"code": "2.2", "section": "Voice and tone", "title": "No shaming",
     "text": "No fear-based or shaming language about skin. Never call skin 'ugly', 'bad' or 'problem skin', and never imply people must fix how they look.",
     "kind": "judgement"},
    {"code": "2.3", "section": "Voice and tone", "title": "No false urgency",
     "text": "No false urgency. Avoid 'last chance', 'hurry', 'only today' or countdown pressure unless the offer is real and its end date is stated.",
     "kind": "judgement"},
    {"code": "2.4", "section": "Voice and tone", "title": "Emoji by channel",
     "text": "Instagram and WhatsApp may use up to 3 emoji. Email may use 1 emoji. Blogs, press notes and packaging use no emoji.",
     "kind": "exact", "check": "emoji",
     "params": {"social": 3, "whatsapp": 3, "email": 1, "blog": 0, "press": 0, "packaging": 0}},
    {"code": "2.5", "section": "Voice and tone", "title": "Inclusive language",
     "text": "Write for all skin tones and genders. Never describe fair or lighter skin as better; never use 'fairness', 'whitening' or 'skin lightening'.",
     "kind": "exact", "check": "terms"},
    # 3 Writing style
    {"code": "3.1", "section": "Writing style", "title": "Readability",
     "text": "Write so a 14-year-old can follow: short sentences and everyday words. Target a Flesch reading ease of 60+ for social, WhatsApp and email, and 50+ for blogs and press notes.",
     "kind": "exact", "check": "readability",
     "params": {"social": 60, "whatsapp": 60, "email": 60, "blog": 50, "press": 50, "packaging": 50}},
    {"code": "3.2", "section": "Writing style", "title": "Sentence case",
     "text": "Use sentence case. Do not write words in ALL CAPS except approved acronyms such as SPF, UV, PA and pH.",
     "kind": "exact", "check": "caps", "params": {"allow": ["SPF", "UV", "PA", "PH", "UVA", "UVB", "INR", "FAQ", "PETA", "OK"]}},
    {"code": "3.3", "section": "Writing style", "title": "Exclamation marks",
     "text": "Use at most one exclamation mark in a piece of content.",
     "kind": "exact", "check": "exclamation", "params": {"max": 1}},
    {"code": "3.4", "section": "Writing style", "title": "Indian English spelling",
     "text": "Use Indian (British) English spelling, such as colour, moisturise and favourite, and write prices with the ₹ symbol.",
     "kind": "exact", "check": "terms"},
    {"code": "3.5", "section": "Writing style", "title": "Hashtags",
     "text": "Social posts use at most 5 hashtags and always include #NeemAndNila.",
     "kind": "exact", "check": "hashtags", "params": {"max": 5, "required": "#NeemAndNila", "channels": ["social"]}},
    # 4 Claims and facts
    {"code": "4.1", "section": "Claims and facts", "title": "Claims need evidence",
     "text": "Every product claim must be backed by the approved fact sheet. If a claim is not on the fact sheet, do not make it.",
     "kind": "judgement"},
    {"code": "4.2", "section": "Claims and facts", "title": "No medical claims",
     "text": "No medical or cure claims. Never say a product treats, cures, heals or removes a skin condition such as acne, eczema, pigmentation or scars. Say 'helps reduce the look of' instead.",
     "kind": "exact", "check": "medical"},
    {"code": "4.3", "section": "Claims and facts", "title": "No absolute claims",
     "text": "Never use absolute or superlative claims such as 'guaranteed', '100% safe', '100% natural', 'No. 1', 'best in India', 'clinically proven' or 'chemical-free' unless that exact claim is on the fact sheet.",
     "kind": "exact", "check": "lexicon"},
    {"code": "4.4", "section": "Claims and facts", "title": "Current prices and offers",
     "text": "Prices, offers and ingredient percentages must match the current fact sheet. Never use expired prices or offers.",
     "kind": "judgement"},
    {"code": "4.5", "section": "Claims and facts", "title": "No competitor mentions",
     "text": "Do not name or criticise competitor brands.",
     "kind": "judgement"},
    # 5 Visual identity
    {"code": "5.1", "section": "Visual identity", "title": "Current logo only",
     "text": "Use only the current logo: the 2025 leaf mark in deep teal. The old 2022 orange sun logo is retired and must not appear.",
     "kind": "judgement", "visual": True},
    {"code": "5.2", "section": "Visual identity", "title": "Colour palette",
     "text": "Use the brand palette: Deep Teal #0F5257, Neem Green #6A994E, Sand #F2E8CF, Nila Blue #3D5A80, Coral #EE6C4D (accent only), plus white and ink. Avoid large areas of colours outside this palette.",
     "kind": "exact", "check": "palette", "params": {"min_share": 0.12, "max_distance": 25}},
    {"code": "5.3", "section": "Visual identity", "title": "Real skin",
     "text": "Show real skin with natural texture. Do not use heavily retouched or skin-lightened images.",
     "kind": "judgement", "visual": True},
    {"code": "5.4", "section": "Visual identity", "title": "Text on images",
     "text": "Text on images must have strong contrast (at least 4.5:1) and sit on a plain area.",
     "kind": "judgement", "visual": True},
    # 6 Accessibility
    {"code": "6.1", "section": "Accessibility", "title": "Alt text",
     "text": "Every image must have alt text that describes what it shows.",
     "kind": "exact", "check": "alt_text"},
    {"code": "6.2", "section": "Accessibility", "title": "Meaningful links",
     "text": "Links must say where they go. Never use 'click here'. Do not rely on colour or emoji alone to carry meaning.",
     "kind": "exact", "check": "terms"},
    # 7 Legal and disclosure
    {"code": "7.1", "section": "Legal and disclosure", "title": "Paid partnerships",
     "text": "Influencer, creator or paid posts must clearly include #ad or #sponsored, as required by ASCI influencer guidelines.",
     "kind": "judgement"},
    {"code": "7.2", "section": "Legal and disclosure", "title": "Offer terms",
     "text": "Every offer must state its end date and key terms, for example 'valid till 10 Nov' or 'on orders above ₹499'.",
     "kind": "judgement"},
]

FACTS = [
    {"code": "F1", "key": "Glow Ritual Vitamin C Serum price", "value": "₹649 for 30 ml (since 1 Oct 2026)", "valid_until": None, "source": "Price list Oct 2026"},
    {"code": "F2", "key": "Glow Ritual Vitamin C Serum old price", "value": "₹599 for 30 ml", "valid_until": "2026-09-30", "source": "Price list Apr 2026 (expired)"},
    {"code": "F3", "key": "Glow Ritual Vitamin C Serum ingredients", "value": "10% vitamin C (ascorbyl glucoside) and 1% niacinamide", "valid_until": None, "source": "Formulation sheet v3"},
    {"code": "F4", "key": "Glow Ritual testing", "value": "Dermatologist tested on an in-house panel (2025). Not clinically proven to treat any skin condition.", "valid_until": None, "source": "Test report DT-2025-07"},
    {"code": "F5", "key": "Calm Neem Face Wash price", "value": "₹299 for 100 ml", "valid_until": None, "source": "Price list Oct 2026"},
    {"code": "F6", "key": "Calm Neem Face Wash formula", "value": "Soap-free, pH 5.5, with neem and tulsi extracts. Suitable for oily and acne-prone skin.", "valid_until": None, "source": "Formulation sheet v2"},
    {"code": "F7", "key": "Nila Night Repair Cream", "value": "₹799 for 50 g; contains a 2% ceramide complex", "valid_until": None, "source": "Price list Oct 2026"},
    {"code": "F8", "key": "Sun Shield SPF 50 Gel", "value": "SPF 50, PA++++, ₹549 for 50 g. Water-resistant or waterproof claims are NOT approved.", "valid_until": None, "source": "SPF test report 2026"},
    {"code": "F9", "key": "Vegan and cruelty-free", "value": "All products are vegan and cruelty-free (PETA certificate 2024).", "valid_until": None, "source": "PETA certificate"},
    {"code": "F10", "key": "Made in India", "value": "All products are made in our Bengaluru facility.", "valid_until": None, "source": "Company profile"},
    {"code": "F11", "key": "Diwali offer", "value": "20% off sitewide on orders above ₹499, valid 20 Oct to 10 Nov 2026", "valid_until": "2026-11-10", "source": "Campaign brief Diwali 2026"},
    {"code": "F12", "key": "Free shipping", "value": "Free shipping on orders above ₹399", "valid_until": None, "source": "Website policy"},
    {"code": "F13", "key": "Natural content", "value": "Products are NOT chemical-free and NOT 100% natural. Glow Ritual Vitamin C Serum is 92% naturally derived.", "valid_until": None, "source": "Formulation sheet v3"},
]

# kind: brand_name | product_name | banned | spelling | link
TERMS = [
    {"term": "Neem and Nila", "kind": "brand_name", "replacement": "Neem & Nila", "clause": "1.1"},
    {"term": "NeemNila", "kind": "brand_name", "replacement": "Neem & Nila", "clause": "1.1"},
    {"term": "Neem n Nila", "kind": "brand_name", "replacement": "Neem & Nila", "clause": "1.1"},
    {"term": "N&N", "kind": "brand_name", "replacement": "Neem & Nila", "clause": "1.1"},
    {"term": "Glow Ritual Serum", "kind": "product_name", "replacement": "Glow Ritual Vitamin C Serum", "clause": "1.2"},
    {"term": "Glow Serum", "kind": "product_name", "replacement": "Glow Ritual Vitamin C Serum", "clause": "1.2"},
    {"term": "Neem Face Wash", "kind": "product_name", "replacement": "Calm Neem Face Wash", "clause": "1.2", "unless_preceded_by": "Calm "},
    {"term": "Night Repair Cream", "kind": "product_name", "replacement": "Nila Night Repair Cream", "clause": "1.2", "unless_preceded_by": "Nila "},
    {"term": "Sunshield", "kind": "product_name", "replacement": "Sun Shield SPF 50 Gel", "clause": "1.2"},
    {"term": "fairness", "kind": "banned", "replacement": "even-looking skin", "clause": "2.5"},
    {"term": "whitening", "kind": "banned", "replacement": "brightening", "clause": "2.5"},
    {"term": "skin lightening", "kind": "banned", "replacement": "radiance", "clause": "2.5"},
    {"term": "fair skin", "kind": "banned", "replacement": "healthy-looking skin", "clause": "2.5"},
    {"term": "ugly skin", "kind": "banned", "replacement": "your skin", "clause": "2.2"},
    {"term": "problem skin", "kind": "banned", "replacement": "oily or acne-prone skin", "clause": "2.2"},
    {"term": "bad skin", "kind": "banned", "replacement": "your skin", "clause": "2.2"},
    {"term": "color", "kind": "spelling", "replacement": "colour", "clause": "3.4"},
    {"term": "moisturize", "kind": "spelling", "replacement": "moisturise", "clause": "3.4"},
    {"term": "moisturizer", "kind": "spelling", "replacement": "moisturiser", "clause": "3.4"},
    {"term": "moisturizing", "kind": "spelling", "replacement": "moisturising", "clause": "3.4"},
    {"term": "favorite", "kind": "spelling", "replacement": "favourite", "clause": "3.4"},
    {"term": "Rs.", "kind": "spelling", "replacement": "₹", "clause": "3.4"},
    {"term": "INR ", "kind": "spelling", "replacement": "₹", "clause": "3.4"},
    {"term": "click here", "kind": "link", "replacement": "shop now on our website", "clause": "6.2"},
]

# Absolute / superlative claim words (clause 4.3)
LEXICON = [
    ("guaranteed", "4.3"), ("guarantee", "4.3"), ("100% safe", "4.3"), ("100% natural", "4.3"),
    ("chemical-free", "4.3"), ("chemical free", "4.3"), ("clinically proven", "4.3"),
    ("no. 1", "4.3"), ("no.1", "4.3"), ("number one", "4.3"), ("#1", "4.3"),
    ("best in india", "4.3"), ("miracle", "4.3"), ("instant results", "4.3"),
    ("dermatologist approved", "4.3"), ("100% protection", "4.3"), ("waterproof", "4.3"),
    ("zero side effects", "4.3"), ("no side effects", "4.3"),
]

CHANNELS = ["social", "whatsapp", "email", "blog", "press", "packaging"]
