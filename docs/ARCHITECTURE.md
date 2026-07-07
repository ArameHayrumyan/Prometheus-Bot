# Architecture

Technical deep-dive into Moonin's design. For setup, see
[../deploy.md](../deploy.md); for command usage, see [COMMANDS.md](COMMANDS.md).

## Design principles

1. **Humans publish, machines triage.** The pipeline's job is to shrink
   thousands of raw candidates to a reviewable queue — never to post.
2. **AI is a scarce resource.** Free-tier quotas are a hard constraint, so
   AI runs at exactly three narrow points; everything else is deterministic
   heuristics that cost nothing and are unit-testable.
3. **Config over code.** New sources, taxonomy fields, scoring weights,
   provider priority, and every user-facing string are DB rows changeable
   from the admin chat — a redeploy is never required for operations.
4. **Lossy at the edges, precise at the gate.** Individual sources may fail
   any cycle (sites change, block, time out); the system logs, skips, and
   continues. Precision is enforced downstream, where it matters.

## Data flow

```
Source (DB row) ──handler──▶ RawOpportunity(url, title, text, org?, posted_at)
    │
    ▼ content_hash(url, title) — dedupe against everything ever seen
normalize.extract_all()          regex/keyword heuristics, zero AI:
    type · degree levels · funding tier · Armenian eligibility · deadline ·
    duration · English req · spots · acceptance rate · fields · noise flags
    │
    ▼ hard_gate.evaluate()       ALL rules must pass (see below)
    │        └─ fail → status DISCARDED + reason (admin: /discards)
    ▼ scoring                    legitimacy 0-100 + chance% (weighted)
    │        ├─ below band  → DISCARDED ("low legitimacy")
    │        ├─ inside band → AI tiebreak w/ RAG few-shot → maybe DISCARDED
    │        └─ above band  → continue
    ▼ embed (MiniLM, 384d) → pgvector          status: PENDING_REVIEW
    ▼ admin DM notification
```

## The hard gate (§ the most important code in the repo)

| # | Rule | Outcome |
|---|---|---|
| 1 | **Funding**: classified `FULLY_FUNDED` / `MOSTLY_FUNDED_ACCEPTABLE` (student covers only travel/visa/partial accommodation) / `STUDENT_PAYS` / `UNKNOWN` from ~30 regex patterns. Explicit "fully funded" wording beats incidental cost mentions. | `STUDENT_PAYS` → reject, no exceptions |
| 2 | **Armenian eligibility**: open-eligibility phrases → `ELIGIBLE`; restriction clauses parsed and checked for Armenia and Armenia-inclusive regions (Eastern Partnership, CIS, post-Soviet, developing countries…) → `INELIGIBLE` if excluded; nothing conclusive → `UNCERTAIN` | `INELIGIBLE` → reject; `UNCERTAIN` → **queued with a visible ⚠️ flag**, never silently dropped |
| 3 | **Field relevance**: title-driven matching against the DB taxonomy. A non-tech role title (marketing/sales/HR/BD/…) never matches, regardless of tech buzzwords in company boilerplate; neutral titles need a keyword near the top of the body or 2+ distinct keywords | no match → reject |
| 4 | **Noise**: duration < `min_duration_days` (default 15, tunable), or noise keywords ("youth summit", "leadership camp"…) without a concrete deliverable (certificate, stipend, publication, curriculum…) | reject |

Both keyword lists live in `app_settings` and are tunable at runtime.

## Scoring

**Legitimacy (0–100, rule-based)** = duration (0–25) + funding tier (0–30) +
org reputation from `source_reputation` (0–25) + concrete deliverable (0–20).

- `< band[0]` (default 40) → discard.
- inside `[40, 65]` → **AI tiebreak**: embed the candidate, retrieve the 5
  nearest previously admin-reviewed posts via pgvector cosine similarity,
  include their approve/reject verdicts as few-shot context, ask for a JSON
  verdict. Rejects only on confidence ≥ 60; AI failure **fails open** to the
  human queue.
- `> 65` → straight to the queue.

**Chance % (weighted, live-tunable via `/setweight`)**:

```
chance = w_acceptance · acceptance_subscore     (stated rate, else spots-derived, else 35)
       + w_selectivity · selectivity_subscore   (prestige domain → 20, obscure → 70)
       + w_requirements · requirements_subscore (neutral 50 in channels;
                                                 personalized per student in detail views:
                                                 degree ±, field ±, English vs req & expiry)
```

Defaults: 0.5 / 0.2 / 0.3. The selectivity inversion is intentional — the
project's core thesis is that low-visibility legitimate sources give
Armenian students a higher real chance than prestige brands.

**Feedback loops** (nightly): per-domain reputation = 0.7·old + 0.3·(approve
ratio) from the admin action log; the tiebreak band's lower bound drifts ±1
based on how often borderline items actually get approved.

## AI layer

```
AIRouter ── priority list (app_settings, live) ──▶ Groq → DeepSeek → Gemini
   │  per-provider RateLimiter (RPM spacing, below free tiers)
   │  per-provider retry w/ exponential backoff + jitter
   │  429 → no retry, immediate failover to next provider
   └─ error stats surface in /ai_status
```

Each provider implements one `_generate()` with its own wire format
(OpenAI-compatible for Groq/DeepSeek, native for Gemini) behind a common
interface — no vendor SDKs, just httpx.

**The only three AI call sites:**

| Call | Trigger | Budget control |
|---|---|---|
| Legitimacy tiebreak | score inside borderline band only | band width itself |
| Post enrichment (TL;DR + competitiveness + requirement bullets) | admin taps Approve | daily cap (`/setcap`, default 50), cached on the row forever, graceful fallback to regex content |
| Resume fit analysis | student requests it | provider throttles |

## Publishing & student loop

- Approve → optional AI enrichment → **preview** with a channel picker
  (degree-level toggles encoded as a bitmask in callback data) → explicit
  🚀 tap → post to selected channels with auto-generated buttons
  (Apply / ⭐ Save / Details / Analyze — deep links into the bot) and a
  `#opp<id>` tag.
- Admin free-edit text and the auto-generated template parts are strictly
  separated in the data model (`edited_text` vs computed sections).
- **Forward matching**: a forwarded channel post is resolved primarily via
  `(channel_id, message_id)` in `channel_posts`, falling back to the
  `#opp<id>` tag — then the full detail card + personalized fit analysis.
- **Saved items** drive deadline reminders (7/3/1 days, skipped once the
  user marks Applied) and the outcome tracker (asked ~30 days post-deadline;
  "still waiting" re-asks monthly). Outcomes accumulate into a real
  acceptance dataset for future chance calibration.

## Scheduler

| Job | Cadence (TZ-aware, default Asia/Yerevan) |
|---|---|
| RSS sources | every 20 min |
| IMAP newsletter | every 15 min |
| Web pages / community boards | every 4 h |
| LinkedIn guest search | every 6 h (+ jitter, per-domain spacing) |
| Expiry sweep (deadline passed → `EXPIRED`) | daily 00:15 |
| Reputation & band feedback | daily 03:30 |
| Deadline reminders | daily 10:00 |
| Outcome follow-ups | daily 10:10 |
| Weekly digest → **admin preview** (never auto-posts) | Sun 19:00 |

Every scrape job is also triggerable on demand via `/scrape [type|all]`.
Interval jobs fire their first run one interval after startup — `/scrape`
exists precisely so verification never waits.

## Storage

PostgreSQL (Supabase/Neon/local pgvector image), SQLAlchemy 2 async, Alembic.

| Table | Purpose |
|---|---|
| `opportunities` | everything scraped, every status (`PENDING_REVIEW`, `ARCHIVED`, `APPROVED`, `PUBLISHED`, `REJECTED`, `DISCARDED`, `EXPIRED`), extraction results, scores, AI enrichment, edit state |
| `opportunity_embeddings` | 384-d MiniLM vectors (pgvector) for the RAG tiebreak |
| `sources` / `source_reputation` | the registry + per-domain trust (seeded priors, nightly updates) |
| `users` / `documents` | profiles (language, degree, fields, GPA, English score+expiry) and parsed resume/letter texts |
| `saved_filters` / `saved_opportunities` | subscriptions and the save/remind/apply/outcome lifecycle |
| `analysis_results` | fit-analysis history |
| `channel_posts` | (channel, message_id) → opportunity, for forward matching |
| `admin_actions` | full audit: approve/reject/edit/archive/channel choice/broadcast/… |
| `app_settings` | every live-tunable knob, including `i18n_overrides` |

## Localization & text customization

Lookup order for any string: **admin override** (per language, stored in
`app_settings.i18n_overrides`, edited via `/settext`) → base YAML catalog
(`en.yml` / `hy.yml`) → English override → English base → the key itself.
Overrides load into memory at startup and refresh instantly on change, so
`t()` stays synchronous. Even channel-post type headers (`type_internship` →
"🧑‍💻 INTERNSHIP") are keys.

## Reliability notes

- Structured JSON logs (structlog) throughout; pretty console in a TTY.
- Scraping: rotating UAs, per-domain minimum spacing with jitter,
  exponential backoff, `Retry-After` honoring, optional global/LinkedIn
  proxies, one-shot unverified retry on broken cert chains (public read-only
  content, human-reviewed downstream).
- Each source runs in its own DB transaction — one failure never poisons a
  cycle. Dedupe is a unique constraint on `content_hash(url, title)`.
- asyncpg is configured with `statement_cache_size=0` for pgbouncer
  compatibility (Supabase poolers).
