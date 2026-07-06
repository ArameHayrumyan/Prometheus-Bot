# Moonin — Armenian IT/DS Opportunities Bot & Channels

A Telegram bot + three channels (Undergrad / Masters / PhD) that aggregates
**fully- or mostly-funded** IT, Data Science, Bioinformatics and Engineering
opportunities (internships, scholarships, fellowships, trainings, entry-level
jobs, hackathons), rigorously filters out noise and pay-to-participate
programs, and gives each student a resume-based success-probability analysis.

**Pipeline:** 50+ seeded sources (web pages, RSS, IMAP newsletters, community
boards, LinkedIn guest search) → normalization → **hard gate** (funding /
Armenian eligibility / field / noise) → legitimacy + chance scoring →
AI tiebreak only for borderline items (RAG-grounded with pgvector) →
**admin review queue** (nothing publishes automatically) → channel posts with
Apply / Details / Analyze-my-fit buttons.

Stack: Python 3.11, aiogram 3, httpx + BeautifulSoup + Playwright + feedparser,
APScheduler, PostgreSQL (Supabase/Neon) + SQLAlchemy 2 async + Alembic +
pgvector, sentence-transformers (local CPU embeddings), DeepSeek + Groq +
Gemini behind one failover router.

---

## 1. Create the Telegram bot & channels

1. Open [@BotFather](https://t.me/BotFather) → `/newbot` → pick a name and a
   username ending in `bot`. Copy the token → `BOT_TOKEN`.
2. In BotFather: `/setprivacy` → your bot → **Disable** is *not* needed
   (the bot only works in DMs and channels).
3. Create three Telegram channels (Undergrad, Masters, PhD). In each channel:
   *Manage channel → Administrators → Add admin* → add your bot with
   **Post messages** permission.
4. Get each channel's numeric ID: forward any post from the channel to
   [@userinfobot](https://t.me/userinfobot) (or add [@getidsbot](https://t.me/getidsbot)),
   the ID looks like `-1001234567890`. Fill `CHANNEL_ID_UNDERGRAD`,
   `CHANNEL_ID_MASTERS`, `CHANNEL_ID_PHD`.
5. Get your own Telegram user ID from [@userinfobot](https://t.me/userinfobot)
   → `ADMIN_USER_IDS` (comma-separated for multiple admins).

## 2. Get free AI keys (all three)

| Provider | Where | Notes |
|---|---|---|
| Groq | https://console.groq.com/keys | free tier, very fast — default first priority |
| DeepSeek | https://platform.deepseek.com/api_keys | cheap/free trial credit |
| Gemini | https://aistudio.google.com/apikey | free tier |

Paste them into `.env`. The router fails over automatically and throttles each
provider below its free-tier rate limit (`GROQ_RPM`, `DEEPSEEK_RPM`,
`GEMINI_RPM`).

## 3. Create a free Supabase Postgres and enable pgvector

1. https://supabase.com → New project (free tier). Choose a strong DB password.
2. In the dashboard: **Database → Extensions →** search `vector` → enable it.
   (The first migration also runs `CREATE EXTENSION IF NOT EXISTS vector`, so
   enabling it in the UI is belt-and-suspenders.)
3. **Connect** (top bar) → *Connection string* → use the **Session pooler**
   URI (port 5432). Replace the password placeholder, then set it as
   `DATABASE_URL`. `postgresql://` is converted to `postgresql+asyncpg://`
   automatically.

(Neon works identically: create a project at https://neon.tech, run
`CREATE EXTENSION vector;` in the SQL editor, copy the connection string.)

## 4. Newsletter mailbox (IMAP acquisition channel)

1. Create a dedicated free Gmail account (don't reuse a personal one).
2. Enable 2-Step Verification, then create an **App password**
   (Google Account → Security → App passwords) → `NEWSLETTER_IMAP_PASSWORD`.
3. Set `NEWSLETTER_IMAP_HOST=imap.gmail.com`, `NEWSLETTER_IMAP_USER=<address>`.
4. Subscribe that mailbox to opportunity digests — recommended starters:
   - ProFellow (https://www.profellow.com — weekly fellowship digest)
   - Opportunity Desk (https://opportunitydesk.org — daily digest)
   - Scholarship Positions newsletter
   - University career-center digests, IEEE/ACM student chapter mailing lists
   - **LinkedIn job alerts** — log the mailbox's LinkedIn account in, create
     saved job searches (e.g. "data science intern", location: Worldwide,
     remote) and set email alert frequency to daily. This is the recommended,
     ToS-clean LinkedIn channel; alert emails are parsed like any newsletter.

The bot polls `INBOX` for unseen messages every `NEWSLETTER_POLL_MINUTES`.

### LinkedIn guest scraping (optional, on by default)

`LinkedInGuestScraper` additionally polls the public no-login guest search
endpoint every `LINKEDIN_SCRAPE_HOURS` (default 6h), deliberately gently
(1 request per registered search, jitter, shared domain throttle). Note that
even guest-page scraping may violate LinkedIn's ToS — you can:
- turn it off entirely: `LINKEDIN_ENABLED=false`,
- change its egress IP with **zero code edits**: set `LINKEDIN_PROXY_URL`
  (or `SCRAPER_PROXY_URL` for all scrapers) to any `http://user:pass@host:port`
  proxy.

## 5. Run locally (Docker Compose)

```bash
cp .env.example .env      # then fill in everything from steps 1-4
```

**Option A — with your Supabase DB (default):**
```bash
docker compose up --build bot
```

**Option B — fully offline local Postgres (pgvector included):**
```bash
# in .env set:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/moonin
docker compose --profile localdb up --build
```

Migrations run automatically on container start (schema + the seeded source
registry of ~50 targets + reputation priors). First startup downloads the
~90 MB embedding model into the `hf_cache` volume.

**Without Docker** (Python 3.11+):
```bash
python -m venv .venv && . .venv/Scripts/activate   # or bin/activate on Unix
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
python -m app.main
```

Local runs use **long polling** (`USE_WEBHOOK=false`) — no public URL needed.

### Smoke test

1. DM your bot `/start` → complete onboarding.
2. As admin: `/listsources` (should show ~50 seeded targets), `/ai_status`.
3. Wait for the first RSS cycle (≤20 min) or trigger interest faster by
   temporarily lowering `RSS_POLL_MINUTES=2`.
4. `/queue` → Approve something → it appears in the matching channel(s).
5. Forward that channel post back to the bot → full detail card (+ fit
   analysis if you uploaded a resume via `/mydocs`).

## 6. Run the tests

```bash
pip install -r requirements.txt   # includes pytest
pytest -v
```

Covers: the hard gate (funding/eligibility/field/noise), the scoring pipeline
(legitimacy, band, weights, English flags), AI provider failover
(rate-limit skip, retry+backoff, live priority/disable), and forward-to-bot
matching (origin lookup + `#opp` tag fallback).

## 7. Deploy free on Render (webhook mode)

Render's free web service **sleeps after 15 min idle**; Telegram webhooks wake
it, but the internal scraping scheduler doesn't run while asleep — so step 5
(external keep-alive ping) is required, and also free and takes 2 minutes.

1. Push this repo to GitHub.
2. https://render.com → **New → Blueprint** → select the repo
   (`render.yaml` is picked up automatically) → it creates the
   `moonin-opportunities-bot` free web service.
3. Fill in the `sync: false` env vars in the Render dashboard
   (same values as your `.env`). Leave `WEBHOOK_BASE_URL` empty for now.
4. After the first deploy, copy the service URL
   (`https://moonin-opportunities-bot.onrender.com`), set it as
   `WEBHOOK_BASE_URL`, and redeploy. On boot the app calls `setWebhook`
   itself — check *Logs* for `webhook_started`.
5. **Keep-alive:** at https://cron-job.org (free) create a job that GETs
   `https://<your-service>.onrender.com/health` every **10 minutes**.
   This keeps the instance awake so APScheduler keeps scraping.
6. `PLAYWRIGHT_ENABLED=false` is preset in the blueprint (512 MB RAM);
   JS-heavy sources automatically fall back to plain HTTP fetches. Sources
   that truly need JS will yield fewer items on free hosting — that's the
   documented trade-off; run locally or on a VM for full Playwright coverage.

Free-tier note: Render free instances get 750 h/month — one always-on service
fits exactly. Supabase free pauses after 7 days of *total* inactivity; the
bot's scheduler traffic prevents that.

## 8. Day-2 operations (all live, no redeploy)

| Command | What it does |
|---|---|
| `/queue` | review pending items (Approve / Reject / Edit / Photo / ◀️▶️ nav / 🗂 Later) |
| `/archive` | the "review later" shelf; items can be approved there or sent back to the queue |
| `/discards` | recent hard-gate/low-legitimacy/AI-rejected items |
| `/stats` | pipeline counts per status |
| `/scrape [type\|all]` | run a scrape cycle right now (default: rss) instead of waiting for the scheduler |
| `/addsource <type> <url> [category[:js]] [name]` | add a scrape target (types: webpage, rss, email, community, linkedin) |
| `/listsources`, `/togglesource <id>` | manage the registry |
| `/addfield Name \| kw1, kw2`, `/listfields`, `/togglefield <id>` | field taxonomy |
| `/ai_status`, `/ai_setpriority groq deepseek gemini`, `/ai_enable`, `/ai_disable` | AI router |
| `/setweight acceptance 0.6`, `/setband 40 65`, `/setminduration 15` | scoring tunables |

A nightly job recomputes per-domain reputation from approve/reject history
(moving average) and nudges the AI-tiebreak band based on how often you
approve borderline items.

## Project layout

```
app/
  ai/           # provider abstraction (DeepSeek/Groq/Gemini) + failover router
  analysis/     # document parsing (PDF/DOCX/TXT) + fit analysis
  bot/          # aiogram handlers (student + admin), posting, forward matching
  db/           # models, session, live settings service
  embeddings/   # sentence-transformers + pgvector similarity
  i18n/         # en.yml / hy.yml
  pipeline/     # normalize -> hard gate -> scoring -> RAG tiebreak -> ingest
  scheduler/    # APScheduler jobs
  scraping/     # 5 typed source handlers + polite HTTP client + registry
alembic/        # migrations: 0001 schema, 0002 seeds (~50 sources)
tests/          # hard gate, scoring, AI failover, forward matching
```
