# 🌙 Moonin — Funded Opportunities Bot for Armenian STEM Students

> A Telegram bot + three curated channels (Undergrad · Masters · PhD) that
> hunt down **fully- and mostly-funded** IT, Data Science, Bioinformatics and
> Engineering opportunities across ~140 sources, filter out everything not
> realistically attainable or genuinely valuable, and tell each student —
> based on their actual resume — what their real chances are.

`Python 3.11` · `aiogram 3` · `PostgreSQL + pgvector` · `SQLAlchemy 2 async` ·
`APScheduler` · `sentence-transformers` · `DeepSeek / Groq / Gemini` ·
`65 tests` · `MIT`

---

## Why this exists

Opportunity aggregators are noisy: pay-to-participate "youth summits",
programs closed to Armenian citizens, prestige listings with 0.5% acceptance
rates presented next to genuinely reachable niche programs. Moonin inverts
the priorities:

- **Funding is a hard gate, not a filter option.** If the student pays
  tuition or program fees, it never reaches a channel. Ever.
- **Armenian eligibility is resolved explicitly.** Restricted country lists
  that exclude Armenia are rejected; ambiguous cases are flagged for human
  review — never silently published, never silently dropped.
- **Low-visibility beats prestige.** The scoring model deliberately ranks a
  legitimate-but-obscure lab internship *above* a FAANG listing, because
  fewer applicants means a higher real chance.
- **Humans stay in the loop.** Nothing is ever posted to a channel without
  an explicit admin tap — including AI-generated content and weekly digests.

## Feature map

| Area | What you get |
|---|---|
| **Acquisition** | ~140 seeded sources across 5 typed handlers: web pages (httpx/BS4 + optional Playwright), RSS feeds, an IMAP newsletter mailbox, community boards (reddit/HN), LinkedIn guest search. New source = one `/addsource` command; per-source CSS-selector precision via `/sourcemeta`; new newsletter = just subscribe the mailbox. Zero code either way. |
| **Filtering** | 4-rule hard gate (funding / Armenian eligibility / field taxonomy / noise), then a rule-based legitimacy score. AI is called **only** for borderline scores, grounded via pgvector retrieval of past admin verdicts (RAG few-shot). |
| **Scoring** | Weighted success-chance estimate from stated acceptance rates, spots, prestige/selectivity signals, and per-student requirement matching (degree, field, GPA, English score + expiry). All weights live-tunable. |
| **Review** | Admin queue with list + card views, prev/next navigation, archive shelf, free-text/photo editing, AI post enrichment with preview, per-post channel picker. Full audit log. |
| **AI (frugal)** | Three providers behind one failover router with per-provider throttling. Used in exactly 3 places: borderline tiebreak, approve-time post enrichment (daily-capped), resume fit analysis. Everything else is heuristics — free-tier quotas survive. |
| **Students** | Bilingual (EN/HY) onboarding, filterable search, saved filters with push notifications, resume upload → fit analysis (score, gaps, suggested bullets), ⭐ saved items, deadline reminders (7/3/1 days), application tracker with outcome collection, forward-a-post-get-full-details. |
| **Operations** | Every user-facing string customizable live (`/settext`), broadcast messaging, on-demand scraping, weekly digest previews, self-tuning source reputation, structured JSON logging. |

## Architecture at a glance

```
                 ┌─────────────────────────────────────────────┐
   ~140 sources  │              SOURCE REGISTRY (DB)           │
 ┌──────────┐    │  webpage │ rss │ email │ community │ linkedin│
 │ web pages│──▶ └────────────────────┬────────────────────────┘
 │ RSS feeds│──▶      APScheduler     │ RawOpportunity
 │ IMAP inbox──▶  (15min…6h cadences) ▼
 │ reddit/HN│──▶ ┌─────────────────────────────────────────────┐
 │ LinkedIn │──▶ │ PIPELINE  normalize → hard gate → scoring   │
 └──────────┘    │   dedupe     │           │          │       │
                 │              ▼           ▼          ▼       │
                 │          DISCARDED   borderline?→ AI+RAG    │
                 └──────────────────────────┬──────────────────┘
                                            ▼ PENDING_REVIEW
                 ┌─────────────────────────────────────────────┐
                 │ ADMIN QUEUE  list/card · edit · photo ·      │
                 │ archive · AI-enrich preview · channel picker │
                 └──────────────────────────┬──────────────────┘
                                 explicit 🚀 tap only
                                            ▼
                 ┌────────────┬─────────────┬────────────┐
                 │ 🎓 Undergrad│ 🎓 Masters  │ 🎓 PhD      │   Telegram channels
                 └─────┬──────┴──────┬──────┴─────┬──────┘
                       ▼             ▼            ▼
                 users: ⭐ save · reminders · fit analysis · tracker
```

Deep dive: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — data flow,
schema, scoring formulas, AI router internals, scheduler table.

## Quick start

```bash
git clone <this repo> && cd moonin-ai
cp .env.example .env        # fill it — see deploy.md §2 for every credential
docker compose up --build bot
```

Fully offline variant (bundled pgvector Postgres):

```bash
# .env: DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/moonin
docker compose --profile localdb up --build
```

Migrations (schema + all seeded sources) run automatically at container
start. The complete runbook — credentials walkthrough, an 8-step acceptance
test with pass criteria, Render free-tier deployment with webhook setup —
lives in **[deploy.md](deploy.md)**.

## Configuration reference

All configuration is via `.env` (template: [.env.example](.env.example)).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | BotFather token |
| `CHANNEL_ID_UNDERGRAD` / `_MASTERS` / `_PHD` | ✅ | — | numeric channel IDs (`-100…`); bot must be channel admin |
| `ADMIN_USER_IDS` | ✅ | — | comma-separated Telegram user IDs with admin powers |
| `DATABASE_URL` | ✅ | — | Postgres URL (Supabase session pooler recommended); `postgres://` auto-converted to asyncpg |
| `GROQ_API_KEY` / `DEEPSEEK_API_KEY` / `GEMINI_API_KEY` | ≥1 | — | AI providers; router fails over between all configured ones |
| `GROQ_RPM` / `DEEPSEEK_RPM` / `GEMINI_RPM` | | 25/30/12 | requests-per-minute throttles, kept below free-tier limits |
| `USE_WEBHOOK` | | `false` | `false` = long polling (local), `true` = webhook (prod) |
| `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`, `PORT` | if webhook | — /—/8080 | public https URL, header secret, listen port |
| `NEWSLETTER_IMAP_HOST` / `_USER` / `_PASSWORD` | | — | dedicated mailbox for newsletter ingestion (blank = channel disabled gracefully) |
| `SCRAPER_PROXY_URL` | | — | HTTP(S) proxy for all scrapers — change egress IP with zero code edits |
| `LINKEDIN_PROXY_URL`, `LINKEDIN_ENABLED` | | — / `true` | LinkedIn-only proxy; kill switch for guest scraping |
| `PLAYWRIGHT_ENABLED` | | `true` | headless Chromium for JS pages; set `false` on 512 MB hosts |
| `RSS_POLL_MINUTES` / `NEWSLETTER_POLL_MINUTES` | | 20 / 15 | fast-cadence polling |
| `WEB_SCRAPE_HOURS` / `COMMUNITY_SCRAPE_HOURS` / `LINKEDIN_SCRAPE_HOURS` | | 4 / 4 / 6 | slow-cadence scraping |
| `EMBEDDING_MODEL` | | `all-MiniLM-L6-v2` | local CPU sentence-transformers model (RAG retrieval only) |
| `LOG_LEVEL`, `TZ` | | `INFO`, `Asia/Yerevan` | logging & scheduler timezone |

Runtime-tunable settings (no restart, stored in DB): scoring weights, AI
priority/disable, borderline band, minimum duration, enrichment cap, noise &
deliverable keyword lists, all user-facing texts.

## Commands

Students get `/search`, `/saved`, `/filters`, `/mydocs`, `/profile`,
`/language`, `/help` — plus forward-any-channel-post for instant details.
Admins additionally get the review queue, source/taxonomy management, the AI
router console, scoring tunables, text customization and broadcast.

Every command is documented with worked examples in
**[docs/COMMANDS.md](docs/COMMANDS.md)** — the same content is available
inside the bot via `/help` (students) and `/adminhelp` (admins). For
step-by-step operational recipes (adding sources, CSS-selector precision
mode, testing the email channel, the full review→publish path, text
customization, pipeline tuning) see **[docs/GUIDES.md](docs/GUIDES.md)**.

## Project structure

```
app/
├── ai/            # provider abstraction, failover router, enrichment, prompts
├── analysis/      # PDF/DOCX/TXT parsing, resume-fit analysis
├── bot/           # aiogram: middlewares, keyboards, posting, forward matching
│   └── handlers/  # student flows + admin/ (queue, sources, AI, texts, help)
├── db/            # models, async engine, live settings service
├── embeddings/    # sentence-transformers + pgvector similarity
├── i18n/          # en.yml, hy.yml + live override layer
├── pipeline/      # normalize → hard_gate → scoring → rag → ingest
├── scheduler/     # APScheduler job definitions
├── scraping/      # 5 typed handlers, polite HTTP client, registry
└── utils/         # text helpers
alembic/           # 0001 schema · 0002-0004,0006 source seeds · 0005 features
docs/              # ARCHITECTURE.md, COMMANDS.md
tests/             # 65 tests: gate, scoring, AI failover, forwarding, i18n…
```

## Testing

```bash
pip install -r requirements.txt
pytest -v
```

The suite covers the hard gate (funding/eligibility/field/noise rules), the
scoring pipeline (legitimacy components, weights, English flags), AI provider
failover (rate-limit skip, retry/backoff, live priority switching),
forward-to-bot matching, extraction quality regressions, enrichment
guardrails, reminder/digest scheduling, and the i18n override layer. Pure
logic is tested without a database or network.

## Deployment

Local Docker Compose for development (long polling), Render free tier for
production (webhook mode + external keep-alive ping). Full walkthrough with
success criteria at every step: **[deploy.md](deploy.md)**.

## License

[MIT](LICENSE) © 2026 Arame Hayrumyan
