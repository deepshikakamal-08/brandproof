"""Sample drafts (shown in the 'Try a sample' picker) and the labelled
evaluation set. Each draft lists the issues a careful human reviewer would
flag, as (category, quote). quote '*' means "anywhere in the draft".

Categories: terminology, style, claims, tone, accessibility, visual, legal
"""

SAMPLES = [
    {
        "id": "s01", "title": "Diwali glow serum — Instagram", "channel": "social",
        "text": "Diwali is HERE!!! ✨🪔🎉🔥 Get the Glow Ritual Serum from Neem and Nila at just ₹599 — clinically proven to remove acne and pigmentation in 7 days. Guaranteed glow or your money back! Hurry, last chance! #diwali #glow #skincare #festive #sale #offer",
        "expected": [
            ("style", "HERE"), ("style", "!!!"), ("style", "✨🪔🎉🔥"),
            ("terminology", "Glow Ritual Serum"), ("terminology", "Neem and Nila"), ("style", "#offer"),
            ("claims", "₹599"), ("claims", "clinically proven"), ("claims", "remove acne and pigmentation"),
            ("claims", "Guaranteed"), ("tone", "Hurry, last chance"), ("style", "#diwali"),
            ("legal", "*"),
        ],
    },
    {
        "id": "s02", "title": "Face wash launch — email", "channel": "email",
        "text": "Subject: Say bye to problem skin 😍🧼\n\nHi there,\nOur new Neem Face Wash is 100% natural and chemical-free, so it's perfect for anyone fed up with oily, ugly skin. It keeps your skin color even and helps you moisturize less. Click here to shop now for just ₹299.",
        "expected": [
            ("terminology", "problem skin"), ("style", "😍🧼"), ("terminology", "Neem Face Wash"),
            ("claims", "100% natural"), ("claims", "chemical-free"), ("terminology", "ugly skin"),
            ("terminology", "color"), ("terminology", "moisturize"), ("accessibility", "Click here"),
        ],
    },
    {
        "id": "s03", "title": "Night cream — blog intro", "channel": "blog",
        "text": "In the contemporary landscape of dermatological self-care, the Nila Night Repair Cream represents a paradigmatic evolution, synthesising multifunctional ceramide technologies with botanically derived constituents in order to systematically reconstitute compromised epidermal barrier architecture overnight. It is the best in India and it heals damaged skin and scars, unlike the Mamaearth night cream that many customers complain about.",
        "expected": [
            ("style", "*"), ("claims", "best in India"), ("claims", "heals damaged skin and scars"),
            ("claims", "heals"), ("tone", "Mamaearth"),
        ],
    },
    {
        "id": "s04", "title": "Sunscreen — WhatsApp broadcast", "channel": "whatsapp",
        "text": "Beach plans? ☀️ Our Sunshield SPF 50 is waterproof and gives 100% protection from UV rays all day. Just ₹549. Reapply never!",
        "expected": [
            ("terminology", "Sunshield"), ("claims", "waterproof"), ("claims", "100% protection"),
            ("claims", "Reapply never"),
        ],
    },
    {
        "id": "s05", "title": "Brightening serum — Instagram ad", "channel": "social",
        "text": "Want fair skin for the wedding season? Our whitening routine with the Glow Ritual Vitamin C Serum gives you visibly fairer skin in 2 weeks. #NeemAndNila #glow",
        "expected": [
            ("terminology", "fair skin"), ("terminology", "whitening"), ("tone", "fairer skin"),
            ("claims", "in 2 weeks"),
        ],
    },
    {
        "id": "s06", "title": "Face wash — compliant Instagram post", "channel": "social",
        "text": "Meet your new everyday cleanser 🌿 The Calm Neem Face Wash is soap-free, pH 5.5 and made with neem and tulsi, so it cleans gently without that tight feeling. ₹299 for 100 ml. #NeemAndNila #CalmNeem",
        "expected": [],
    },
    {
        "id": "s07", "title": "Funding news — press note", "channel": "press",
        "text": "N&N raises Series A 🚀🎉\n\nBengaluru: N&N, the No. 1 skincare brand for Indian skin, today announced its Series A round. The company will use the funds to expand its Bengaluru facility and launch three new products in 2027.",
        "expected": [
            ("terminology", "N&N"), ("style", "🚀🎉"), ("claims", "No. 1"),
        ],
    },
    {
        "id": "s08", "title": "Creator collab — Instagram", "channel": "social",
        "text": "Obsessed with my Glow Ritual Vitamin C Serum from @neemandnila 💛 My skin has never looked this bright. Use my code PRIYA20 for 20% off! #NeemAndNila #skincareroutine",
        "expected": [("legal", "*")],
    },
    {
        "id": "s09", "title": "Diwali offer — Instagram", "channel": "social",
        "text": "Our Diwali offer is here 🪔 Get 20% off everything at Neem & Nila. Treat yourself or someone you love. #NeemAndNila #DiwaliGlow",
        "expected": [("legal", "20% off everything")],
    },
    {
        "id": "s10", "title": "Serum restock — email", "channel": "email",
        "text": "Subject: It's back ✨✨✨\n\nThe Glow Ritual Vitamin C Serum is back in stock. With 20% vitamin C and 1% niacinamide, it helps your skin look brighter in a few weeks. ₹649 for 30 ml, with free shipping on orders above ₹399.",
        "expected": [("style", "✨✨✨"), ("claims", "20% vitamin C")],
    },
    {
        "id": "s11", "title": "Night cream — compliant email", "channel": "email",
        "text": "Subject: Your skin's overnight ally\n\nThe Nila Night Repair Cream has a 2% ceramide complex that helps your skin hold on to moisture while you sleep. Smooth a little on after cleansing. ₹799 for 50 g, vegan and cruelty-free.",
        "expected": [],
    },
    {
        "id": "s12", "title": "Festive banner — Instagram (image)", "channel": "social",
        "image": "banner_offbrand.png", "alt_text": "",
        "text": "Festive glow, the gentle way 🪔 Shop the Glow Ritual Vitamin C Serum. #NeemAndNila",
        "expected": [("accessibility", "*"), ("visual", "*")],
    },
]

# Extra labelled drafts used only by the Evaluation page.
EVAL_EXTRA = [
    {"id": "e01", "channel": "social", "text": "Say goodbye to acne forever! Our Calm Neem Face Wash cures pimples in 3 days. #NeemAndNila",
     "expected": [("claims", "cures pimples"), ("claims", "goodbye to acne forever")]},
    {"id": "e02", "channel": "email", "text": "Subject: A gentle routine for oily skin\n\nThe Calm Neem Face Wash is soap-free with neem and tulsi. Follow it with the Nila Night Repair Cream at night. Find both on our website.",
     "expected": []},
    {"id": "e03", "channel": "social", "text": "ONLY TODAY!!! Grab the Sun Shield SPF 50 Gel before it's GONE. #NeemAndNila",
     "expected": [("style", "ONLY"), ("style", "TODAY"), ("style", "GONE"), ("style", "!!!"), ("tone", "ONLY TODAY"), ("legal", "*")]},
    {"id": "e04", "channel": "blog", "text": "Why we love vitamin C 😍 Vitamin C helps skin look brighter and more even. Our Glow Ritual Vitamin C Serum has 10% vitamin C in a gentle form.",
     "expected": [("style", "😍")]},
    {"id": "e05", "channel": "social", "text": "Dermatologist approved and 100% safe for all skin types. Glow Ritual Vitamin C Serum, ₹649. #NeemAndNila",
     "expected": [("claims", "Dermatologist approved"), ("claims", "100% safe")]},
    {"id": "e06", "channel": "whatsapp", "text": "Hi! Your favorite Neem and Nila serum is back. Grab it at Rs. 649.",
     "expected": [("terminology", "favorite"), ("terminology", "Neem and Nila"), ("terminology", "Rs.")]},
    {"id": "e07", "channel": "social", "text": "Better than Minimalist and way cheaper 😉 Try the Glow Ritual Vitamin C Serum. #NeemAndNila",
     "expected": [("tone", "Minimalist")]},
    {"id": "e08", "channel": "email", "text": "Subject: Free shipping is here\n\nEnjoy free shipping on orders above ₹399 on every Neem & Nila product.",
     "expected": []},
    {"id": "e09", "channel": "social", "text": "Hey gorgeous, ur skin is literally gonna be lit af with this serum lol 🔥 #NeemAndNila",
     "expected": [("tone", "lit af"), ("tone", "*")]},
    {"id": "e10", "channel": "press", "text": "Neem & Nila products are vegan and cruelty-free, certified by PETA in 2024, and made in our Bengaluru facility.",
     "expected": []},
    {"id": "e11", "channel": "social", "text": "Our Nila Night Repair Cream is now just ₹599! Was ₹799. #NeemAndNila",
     "expected": [("claims", "₹599"), ("legal", "*")]},
    {"id": "e12", "channel": "social", "text": "No more scars or dark spots. The Glow Ritual Vitamin C Serum removes dark spots for good. #NeemAndNila",
     "expected": [("claims", "removes dark spots"), ("claims", "No more scars or dark spots")]},
    {"id": "e13", "channel": "email", "text": "Subject: Chemical free skincare 🌿🌿\n\nAll our products are chemical free and made in India.",
     "expected": [("claims", "Chemical free"), ("claims", "chemical free"), ("style", "🌿🌿")]},
    {"id": "e14", "channel": "social", "text": "Tired of your ugly skin? Fix it with the Glow Serum. #NeemAndNila",
     "expected": [("terminology", "ugly skin"), ("terminology", "Glow Serum"), ("tone", "Fix it")]},
    {"id": "e15", "channel": "blog", "text": "Sunscreen is the most important step in any routine. Apply the Sun Shield SPF 50 Gel every morning and reapply every two hours outdoors.",
     "expected": [("claims", "most important step")]},
    {"id": "e16", "channel": "social", "text": "Tag a friend who needs this! Calm Neem Face Wash, ₹299. #NeemAndNila #CalmNeem #facewash #neem #tulsi #cleanser #skincare",
     "expected": [("style", "#skincare")]},
    {"id": "e17", "channel": "social", "text": "Our new moisturizer drops next week. Stay tuned for the color of the year pack! #NeemAndNila",
     "expected": [("terminology", "moisturizer"), ("terminology", "color")]},
    {"id": "e18", "channel": "whatsapp", "text": "Your order is on its way 🚚 Thanks for choosing Neem & Nila.",
     "expected": []},
]
