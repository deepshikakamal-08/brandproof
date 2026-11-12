# Brandproof

**Brand governance before publication.** Brandproof checks social posts, emails, blogs, press notes, PDFs and images against an organisation's own brand guidelines, approved facts, terminology and assets, in English, Tamil, Hindi, Tanglish and Hinglish. Every issue is explained, cites the exact guideline clause or approved fact it breaks, and comes with a minimal fix. A person makes the final decision, and the system learns from those decisions.

Built for the We Code Coders CodeNexus India hackathon (Inkloom AI problem statement) by team **Zero Downtime**.

- **Live product:** https://brandproof-opal.vercel.app (no sign-up: click **Start the demo**)
- **API docs:** https://brandproof-opal.vercel.app/api/docs
- **Health check:** https://brandproof-opal.vercel.app/api/health (add `?probe=1` to test each AI provider)

---

## Try it in 3 minutes

A **Try this** button (bottom right) ticks these off as you go.

1. Open the link and click **Start the demo, no sign-up**. You get your own private workspace with the fictional brand *Neem & Nila Skincare*.
2. **New check →** pick a sample (English, or **Tamil & Hindi**), or paste your own text, upload an image or a PDF.
3. Read the issues: highlighted text, why it breaks the rule, the cited clause or fact, and a fix. Claims are marked Supported / Outdated / Contradicted / Unsupported against the fact sheet.
4. **Accept**, **Edit** or **Dispute** each issue (or *Accept all fixes*), then **Submit for review**.
5. Switch **Role** (top right) to **Manager**, open **Review queue**, then **Approve** or **Send back** with a comment.
6. Explore **Learning** (what it learned from decisions), **Rulebook** (guideline gaps, version history, PDF import as Admin), **Evaluation** (accuracy numbers) and **Insights**.

## Features

| Area | What works |
| --- | --- |
| Workspace | One-click guest workspace per visitor; signed sessions; every query scoped to the organisation; roles creator / manager / reviewer / admin |
| Rulebook | 25 clauses, 13 approved facts (incl. an expired price and an expired offer), 24 terms, colour palette; edit clauses, add facts; **import any guideline PDF or text** into rule cards |
| Intake | Paste text (any language), upload an image with alt text, or a PDF; 6 channels with channel rules; 16 samples |
| Exact checks | Brand and product names, banned and inclusive-language terms, Indian English spelling, absolute and medical claims, emoji per channel, readability (English), ALL CAPS, exclamation marks, hashtags, alt text, image colours vs palette (k-means in Lab colour space) |
| AI checks | Tone, messaging, false urgency, competitor mentions, legal disclosure (#ad, offer terms), claims vs approved facts (with validity dates), image review against visual rules |
| Citation gate | An AI finding is kept only if it cites a clause or fact that was given to the model **and** quotes text that really is in the draft; the finding type follows the cited clause; AI repeats of rule flags are dropped |
| Fixes | Minimal fixes shown as a diff; long rewrites rejected; accepted fixes applied into a new version |
| Workflow | Accept / edit / dispute with notes; submit only when all issues are decided; manager approve / send back; disputed high-severity claims need a justification; versions, comments, audit log |
| **Learning** (Round 3) | Every decision is stored; per-guideline modes (trusted / normal / softened / muted); learned AI confidence cut-off; real accepted and disputed examples added to the AI prompt; disputed text not re-flagged; hidden flags always listed with the reason; admins can switch learning off or reset per guideline |
| **Indian languages** (Round 3) | Detects English, Tamil, Hindi, Tanglish, Hinglish; exact Tamil/Hindi/romanised checks for medical and absolute claims, fair-skin language, shaming words and the brand name in another script; fixes in the same language and script; AI quotes in the original script and adds the English meaning |
| **Guideline gaps + versions** (Round 3) | Finds often-disputed or low-confidence guidelines; suggests a clearer rewrite with do/don't examples (AI, or drafted from reviewer decisions if the AI is down); admin edits, approves or rejects; every rulebook change saves a numbered version with a diff; every check records the version it used |
| Evaluation | 30 hand-labelled English drafts and 20 Tamil/Hindi/Tanglish/Hinglish drafts; precision, recall, F1 per issue type and language; every miss and false alarm listed; learning experiment (learn on 12, test on 18 unseen, before vs after); results can be published for all visitors |
| Insights | Issues by type, most-broken guidelines, possibly unclear guidelines, rule vs AI counts |
| API | `POST /api/v1/check` stateless check; OpenAPI docs at `/api/docs` |
| Reliability | AI timeouts, retry, provider fallback (skips providers with no credits; backup model on rate limits), cached results, exact checks always return, rate limits, input validation, friendly errors, works with browser storage blocked |

## Architecture

```
 Web app (HTML/CSS/JS)          Public API  POST /api/v1/check
                \                    /
          FastAPI on Vercel (Python function, Mumbai region)
          signed sessions · org scoping · roles · rate limits
                           |
  Check engine
   1 language detection (en / ta / hi / Tanglish / Hinglish)
   2 exact rules (code)  ->  3 retrieval (BM25 + embeddings, rank fusion)
   4 two AI calls in parallel, JSON schema: issues | claims vs facts
     (+ reviewer examples from Learning, + language guidance)
   5 citation gate  ->  6 minimal fix  ->  7 learning policy (soften / mute / cut-off)
  Rulebook + versions · Gap assistant · Workflow · Learning · Insights · Evaluation
           |                                   |
  Supabase Postgres                     AI gateway
  (orgs, drafts, versions, findings,    PII redaction · timeouts · retry · fallback
   feedback, rulebook versions,         Gemini 3.5 Flash Lite (+ backup model), Sarvam,
   audit log, cache, rate limits)       any OpenAI-compatible model; Gemini embeddings
```

| Path | What |
| --- | --- |
| `api/index.py` | All HTTP routes, rate limits, input validation |
| `api/_core/engine.py` | Check pipeline, citation gate, fixes, caching |
| `api/_core/rules.py` | Exact checks |
| `api/_core/lang.py` | Language detection, Tamil/Hindi checks, language prompt |
| `api/_core/learning.py` | Learning from reviewer decisions |
| `api/_core/gaps.py`, `versions.py` | Guideline-gap assistant, rulebook versions |
| `api/_core/llm.py` | AI gateway |
| `api/_core/retrieval.py` | BM25 + embedding retrieval |
| `api/_core/rulebook.py` | Guideline PDF import |
| `api/_core/workflow.py` | Drafts, versions, decisions, approvals, insights |
| `api/_core/evaluation.py`, `samples.py`, `regional.py` | Labelled test sets and scoring |
| `api/_core/demo_data.py` | Demo brand rulebook |
| `public/` | Web app (no build step) |
| `tests/test_engine.py` | Offline tests (no keys needed) |

## Models and libraries

- **Google Gemini** via the OpenAI-compatible endpoint: text and image review (`gemini-3.5-flash-lite`, backup `gemini-3.1-flash-lite`), embeddings (`gemini-embedding-001`).
- **Sarvam AI** (`sarvam-105b`, `glm5.3-flash`): supported and used during development; set `LLM_PROVIDER=sarvam` when the account has credits.
- Any OpenAI-compatible model via `OPENAI_COMPAT_URL`, `OPENAI_COMPAT_KEY`, `OPENAI_COMPAT_MODEL`.
- Python: FastAPI, Pydantic, httpx, psycopg 3, rapidfuzz, NumPy, Pillow, PyMuPDF. No front-end libraries.

Without any AI key the app still runs: exact checks, Tamil/Hindi rules, palette and alt-text checks work, and the page says the AI was unavailable.

## Run it locally

Needs Python 3.11+.

```bash
git clone https://github.com/deepshikakamal-08/brandproof.git
cd brandproof
pip install -r requirements.txt uvicorn

# offline: no keys, mock AI, local SQLite
cd api
SERVE_STATIC=1 LLM_PROVIDER=mock python -m uvicorn index:app --port 8000
# open http://localhost:8000

# tests (from the repo root, no keys needed)
cd .. && LLM_PROVIDER=mock python tests/test_engine.py
```

On Windows PowerShell set variables with `$env:SERVE_STATIC=1; $env:LLM_PROVIDER="mock"` before the uvicorn command.

To use real AI locally, also set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` (see `.env.example`).

## Deploy (Vercel + Supabase)

1. Create a Supabase project and copy the **Transaction pooler** connection string (port 6543). In Supabase, turn off the public Data API and keep row-level security on; the app connects directly.
2. Import the repo into Vercel (Framework preset **Other**, no build command).
3. Add environment variables (all listed in `.env.example`):

| Name | Value |
| --- | --- |
| `DATABASE_URL` | Supabase transaction pooler URL |
| `SECRET_KEY` | Long random string (signs sessions) |
| `LLM_PROVIDER` | `gemini` (or `sarvam`) |
| `GEMINI_API_KEY` | Google AI Studio key |
| `GEMINI_MODEL`, `VISION_MODEL` | `gemini-3.5-flash-lite` |
| `GEMINI_BACKUP_MODEL` | `gemini-3.1-flash-lite` (used when the main model is rate-limited) |
| `SARVAM_API_KEY` | Optional |
| `PUBLISH_CODE` | Optional: lets the owner publish evaluation results to every visitor |

4. Deploy. Tables are created on the first request. Open `/api/health?probe=1` to confirm the database and each AI provider.

## Security and privacy

Signed, expiring sessions; every query filtered by organisation; role checks on approval, import and admin actions; keys only in environment variables; emails and phone numbers removed before any AI call; input size limits and image validation; rate limits on checks, imports, rewrites, API and new workspaces; escaped output; Content-Security-Policy and anti-framing headers. No auto-publishing: a person decides every change.

## Changes from the plan

See the project PDF for the full list. In short: plain JS instead of React; everything on Vercel; hosted models instead of local ones; BM25 + embeddings instead of pgvector; guest workspaces instead of sign-up. In Round 3 the live AI moved from Sarvam to Gemini Flash Lite after the Sarvam trial credits ran out (the gateway supports both with one setting).

## Roadmap

- Learn per channel and per reviewer, and suggest new exact rules from repeated accepted fixes.
- More Indian languages (Telugu, Kannada, Malayalam, Bengali) and voice-note checks.
- CMS, Google Docs and Slack integrations on top of `/api/v1/check`; SSO and real team accounts.
- Logo detection on images and video frame checks.

## AI disclosure

AI coding assistants were used to help write this code. Inside the product, every AI finding is labelled with the model that produced it. The demo brand *Neem & Nila Skincare* and all its guidelines and facts are fictional.

## License

MIT
