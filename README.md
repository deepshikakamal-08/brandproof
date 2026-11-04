# Brandproof

**Brand governance before publication.** Brandproof checks posts, emails, blogs, PDFs and images against an organisation's own brand guidelines, approved facts, terminology and assets. Every issue is explained, cites the exact guideline clause or approved fact it breaks, and comes with a minimal fix. A person makes the final decision.

Built for the We Code Coders CodeNexus hackathon (Inkloom AI problem statement), Round 2.

**Live demo:** `<your-vercel-url>` (no sign-up: click **Start the demo**)
**API docs:** `<your-vercel-url>/api/docs`

---

## Try it in 2 minutes (judge path)

1. Open the link and click **Start the demo, no sign-up**. You get a private workspace with the fictional brand *Neem & Nila Skincare*.
2. Pick the sample **Diwali glow serum — Instagram** (or paste your own text, upload an image or a PDF).
3. Read the issues: each one shows the quote, why it's a problem, the cited guideline clause or approved fact, and a suggested fix. Claims are labelled Supported / Outdated / Contradicted / Unsupported against the fact sheet.
4. **Accept**, **Edit** or **Dispute** each issue (or *Accept all remaining fixes*), then **Submit for review**.
5. Switch **Role** (top right) to **Manager**, open the draft, see the final text, the diff and any disputes, then **Approve** or **Send back** with a comment.
6. Also explore **Rulebook** (import any guideline PDF), **Insights**, **Evaluation** (accuracy numbers) and **How it works**.

## What's built (Round 2)

| Area | Feature |
| --- | --- |
| Workspace | One-click guest workspace per visitor, signed sessions, every query scoped to the organisation; roles: creator, manager, reviewer, admin |
| Rulebook | 25 clauses, 13 approved facts (incl. an expired price), 24 terms, colour palette; edit clauses; add facts; **import any guideline PDF or text into rule cards** (AI classifies each clause as exact or AI-judged and extracts terms) |
| Intake | Paste text, upload an image (with alt text) or a PDF; 6 channels with channel-specific rules; 12 sample drafts |
| Exact checks (code) | Brand and product names, banned and inclusive-language terms, Indian English spelling, risky claim words, medical/cure claims, emoji per channel, readability, ALL CAPS, exclamation marks, hashtags, alt text, image colours vs palette (k-means in Lab colour space) |
| AI checks | Tone, messaging, false urgency, competitor mentions, legal disclosure (#ad, offer terms), claim-vs-fact verification, visual rules on images (logo, retouching, text contrast) |
| Citation gate | An AI finding is kept only if it cites a clause/fact that was actually provided **and** quotes text that really appears in the draft; the rest are discarded and counted |
| Explain + fix | Highlighted text, severity, confidence, Rule/AI label with model name, cited source, minimal fix as a diff; intent check drops fixes that rewrite too much |
| Workflow | Accept / edit / dispute with notes; submit only when every issue is decided; fixes applied into a new version; manager approve / send back with comment; disputed high-severity claims need a justification; versions, comments, full audit log |
| Insights | Issues by type, most-broken guidelines, **possibly unclear guidelines** (clauses disputed often), rule vs AI counts |
| Evaluation | 30 hand-labelled drafts (74 known issues); precision / recall / F1 overall and per issue type, per-draft misses and false alarms |
| API | `POST /api/v1/check` stateless check for integrations; OpenAPI docs at `/api/docs` |
| Reliability | AI timeouts + retry, results cached by content hash, rules still return if AI fails, friendly errors |

## Architecture

```
Web app (HTML/CSS/JS)   Public API (/api/v1/check)
            \                 /
        FastAPI on Vercel (Python function)
        signed sessions · org scoping · roles
                     |
   Check engine: exact rules -> retrieval (BM25 + embeddings)
   -> AI judgement + claim check (structured JSON) -> citation gate
   -> minimal fix + intent check -> findings with source + confidence
   Rulebook · Workflow · Insights · Evaluation
          |                              |
 Supabase Postgres                 AI gateway: PII redaction, retries,
 (org data, audit log, cache)      Sarvam sarvam-105b (text), Gemini (vision, embeddings)
```

Code map:

| Path | What |
| --- | --- |
| `api/index.py` | All HTTP routes |
| `api/_core/rules.py` | Exact checks |
| `api/_core/engine.py` | Check pipeline, citation gate, fixes, caching |
| `api/_core/llm.py` | AI gateway (providers, redaction, retries, structured output) |
| `api/_core/retrieval.py` | BM25 + embedding retrieval with rank fusion |
| `api/_core/rulebook.py` | Guideline PDF import |
| `api/_core/workflow.py` | Drafts, versions, decisions, approvals, insights |
| `api/_core/evaluation.py`, `samples.py` | Labelled test set and scoring |
| `api/_core/demo_data.py` | Demo brand rulebook, facts, terms |
| `public/` | Web app |

## Models, APIs and libraries

- **Sarvam AI `sarvam-105b`** (chat completions, JSON-schema structured output): tone, claims, legal checks and guideline import.
- **Google Gemini** (OpenAI-compatible endpoint): vision checks on images (`gemini-3.8-flash`) and embeddings (`gemini-embedding-001`) for retrieval. Optional: without a key, retrieval falls back to BM25 and image checks to code-only palette and alt-text checks.
- **Supabase Postgres** for storage.
- Python: FastAPI, Pydantic, httpx, psycopg 3, rapidfuzz, NumPy, Pillow, PyMuPDF.
- No external front-end libraries.

**AI disclosure:** AI coding assistants (Claude) were used to help write this code. Every AI finding inside the product is labelled with the model that produced it.

## Deploy (Vercel + Supabase)

1. Create a Supabase project. Copy the **Transaction pooler** connection string (port 6543) from *Connect*.
2. Import this repo into Vercel (Framework preset: **Other**). No build command is needed.
3. Add environment variables:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | Supabase transaction pooler URL, with your DB password |
| `SECRET_KEY` | Any long random string |
| `SARVAM_API_KEY` | Sarvam API key |
| `LLM_PROVIDER` | `sarvam` |
| `GEMINI_API_KEY` | Google AI Studio key (vision + embeddings) |

4. Deploy. Tables are created automatically on the first request. Open `/api/health` to confirm the database and models.

## Run locally

```bash
pip install -r requirements.txt uvicorn
cd api
SERVE_STATIC=1 LLM_PROVIDER=mock python -m uvicorn index:app --port 8000
# open http://localhost:8000   (SQLite is used when DATABASE_URL is not set)
python ../tests/test_engine.py          # offline tests, no API keys needed
```

## Changes from the Round 1 plan

- Frontend in plain HTML/CSS/JavaScript instead of React: no build step, faster first load, nothing to break at deploy time.
- Everything on Vercel (instead of Vercel + Render): one link, no cold-start sleep of a separate backend.
- Sarvam `sarvam-105b` for text checks instead of Gemini; Gemini kept for vision and embeddings.
- Hosted models instead of local models (Vercel functions can't run local LLMs); the separate NLI model is replaced by fact-grounded LLM claim checks plus the citation gate.
- Guest demo workspaces with signed sessions instead of full sign-up, so judges can start instantly; each guest still gets an isolated organisation.
- Retrieval uses BM25 + embeddings rank fusion in Python instead of pgvector (rulebooks are small; no extension needed).
- Added: public check API, PDF guideline import, evaluation page.

## Round 3: three improvements

1. **Learning from reviewer decisions to cut false flags.** Accept/dispute history per clause tunes severity and confidence thresholds and adds few-shot examples to the prompt. Target: false alarms ≤ 10% on the same test set.
2. **Indian-language and code-mixed review** (Tamil, Hindi, Tanglish/Hinglish) using Sarvam's Indian-language strength, with a 20-draft labelled test set.
3. **Guideline-gap assistant.** Clauses that are disputed often get a suggested clearer rewrite with do/don't examples for the admin to approve, with rulebook versioning.

## License

MIT
