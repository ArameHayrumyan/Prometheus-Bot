# deploy.md — Testing & Deployment Runbook

This is the operational guide for **moonin-ai**: how to configure it, run it
locally, verify every subsystem actually works (with explicit success
criteria), and deploy it to Render's free tier. Follow it top to bottom the
first time; later you'll only need §5 (verification) and §7 (deploy).

The system has four moving parts, and each has its own "is it working?" signal:

| Part | What it does | Success signal |
|---|---|---|
| Bot process | Telegram DM interface + admin commands | responds to `/start`, `/ai_status` |
| Scheduler | scrapes ~100 sources on intervals | `scrape_cycle_done` log lines; `/queue` fills up |
| Pipeline | filters/scores candidates | items in `/queue` and `/discards` with reasons |
| Publishing | posts approved items to 3 channels | post appears in channel; forwarding it back to the bot resolves |

---

## 1. Prerequisites

- **Docker Desktop** (recommended path), or Python **3.11+** for bare-metal.
- A Telegram account.
- 30–60 minutes for the full first-time setup (most of it is collecting keys).

Nothing else. All third-party services below have free tiers.

---

## 2. Collect every credential (one-time)

Copy the template first:

```bash
cp .env.example .env
```

Now fill it in, variable by variable.

### 2.1 `BOT_TOKEN`

1. Open [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Name: anything (e.g. `Moonin Opportunities`). Username: must end in `bot`
   (e.g. `moonin_opps_bot`).
3. Copy the token that looks like `7123456789:AAE...` into `BOT_TOKEN`.

### 2.2 `CHANNEL_ID_UNDERGRAD` / `CHANNEL_ID_MASTERS` / `CHANNEL_ID_PHD`

1. Create three Telegram channels (public or private, both work).
2. In **each** channel: *Manage channel → Administrators → Add administrator*
   → search your bot's username → grant at least **Post messages**.
   ⚠️ If you skip this, publishing fails with `chat not found` / `not enough rights`.
3. Get each channel's numeric ID: forward any message *from the channel* to
   [@userinfobot](https://t.me/userinfobot). It replies with a
   `forwarded from chat #-100XXXXXXXXXX` line. IDs always start with `-100`.
4. Put the three IDs in `.env`. Do not quote them.

### 2.3 `ADMIN_USER_IDS`

DM [@userinfobot](https://t.me/userinfobot) yourself; it replies with your
numeric `Id`. Comma-separate multiple admins: `ADMIN_USER_IDS=11111111,22222222`.

Only these IDs see the admin commands (`/queue`, `/addsource`, `/ai_status`…).
Everyone else gets the student interface.

### 2.4 `DATABASE_URL` (Supabase)

1. https://supabase.com → **New project** (free). Pick a region near you,
   set a strong DB password, wait ~2 min for provisioning.
2. **Database → Extensions** → search `vector` → **enable**.
   (Migration 0001 also runs `CREATE EXTENSION IF NOT EXISTS vector`, so this
   is redundancy, but enabling in the UI confirms your plan supports it.)
3. Click **Connect** (top bar) → *Connection string* tab → choose
   **Session pooler** (port **5432**, *not* the transaction pooler on 6543).
4. Copy the URI, replace `[YOUR-PASSWORD]`, paste as `DATABASE_URL`.
   `postgresql://...` is fine — the app rewrites it to `postgresql+asyncpg://`.

> Why session pooler: asyncpg + transaction-mode pgbouncer can misbehave with
> prepared statements. The app already sets `statement_cache_size=0` as a
> safety net, but session mode (5432) is the tested configuration.

**Local-only alternative (no Supabase at all):** set
`DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/moonin`
and use the `localdb` compose profile in §4.2.

### 2.5 AI keys — `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`

| Provider | Get key at | Free tier notes |
|---|---|---|
| Groq | https://console.groq.com/keys | free, fast; default first in priority |
| DeepSeek | https://platform.deepseek.com/api_keys | trial credit |
| Gemini | https://aistudio.google.com/apikey | free tier |

The router fails over automatically, so the system runs even with **one** key —
but fill all three; the whole point is never being blocked by one quota.
Leave the `*_RPM` throttles at their defaults unless you know your limits.

### 2.6 Newsletter mailbox — `NEWSLETTER_IMAP_*`

1. Create a **dedicated** free Gmail account (never your personal one — the
   password lives in `.env`).
2. Google Account → Security → enable **2-Step Verification** → then
   **App passwords** → create one for "Mail". That 16-character string is
   `NEWSLETTER_IMAP_PASSWORD` (spaces are fine).
3. `NEWSLETTER_IMAP_HOST=imap.gmail.com`, `NEWSLETTER_IMAP_USER=<the address>`.
4. Subscribe the mailbox to: ProFellow, Opportunity Desk, Scholarship
   Positions, and **LinkedIn job alerts** (create saved searches on LinkedIn
   with that account, set alerts to daily email).

If you leave these blank the email channel is skipped gracefully
(`email_skipped_not_configured` in logs) — everything else still works.

### 2.7 Optional scraping knobs

- `SCRAPER_PROXY_URL` — route **all** scrapers through an HTTP(S) proxy
  (`http://user:pass@host:port`). Change egress IP with zero code edits.
- `LINKEDIN_PROXY_URL` — proxy for the LinkedIn guest scraper only.
- `LINKEDIN_ENABLED=false` — kill switch for LinkedIn guest scraping.
- `PLAYWRIGHT_ENABLED=false` — disable headless Chromium (set on 512 MB
  hosts); JS-heavy sources fall back to plain HTTP and yield less.

### 2.8 Leave alone for local runs

`USE_WEBHOOK=false`, `WEBHOOK_BASE_URL` (empty), `PORT=8080`. These only
matter for Render (§7).

---

## 3. Sanity check before first run

```bash
docker --version            # any recent version
type .env | findstr BOT_TOKEN   # Windows: confirm .env is filled (or `grep` on Unix)
```

Checklist — all must be true:

- [ ] `.env` exists next to `docker-compose.yml` and has no placeholder values left
- [ ] bot is admin (Post messages) in all three channels
- [ ] the three channel IDs start with `-100`
- [ ] Supabase project shows the `vector` extension enabled
- [ ] your own Telegram ID is in `ADMIN_USER_IDS`

---

## 4. Local run

### 4.1 Standard: Docker + Supabase

```bash
docker compose up --build bot
```

First build takes 5–15 min (CPU torch + Chromium). Subsequent starts: seconds.

### 4.2 Fully offline: Docker + local pgvector Postgres

In `.env`: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/moonin`

```bash
docker compose --profile localdb up --build
```

The bot container retries migrations for up to 60 s while Postgres boots —
`alembic upgrade head` failing once or twice at the start is normal.
The DB is also reachable from your host at `localhost:5433` (user/pass
`postgres`/`postgres`, db `moonin`) for inspection with any SQL client.

### 4.3 Bare Python (no Docker)

```bash
python -m venv .venv
.venv\Scripts\activate            # Unix: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
playwright install chromium
alembic upgrade head              # needs DATABASE_URL in the environment
python -m app.main
```

Note the difference in how the two commands read config: `python -m app.main`
reads `.env` directly (pydantic-settings), but `alembic upgrade head` needs
`DATABASE_URL` as a real environment variable:

```powershell
# Windows PowerShell
$env:DATABASE_URL = "postgresql+asyncpg://..."
alembic upgrade head
python -m app.main
```

```bash
# Unix
export DATABASE_URL="postgresql+asyncpg://..."
alembic upgrade head
python -m app.main
```

### 4.4 What a healthy startup looks like

Watch the logs. **Success = all of these lines appear, in roughly this order:**

```
starting                          webhook=False
channels_synced                   channels={'undergrad': -100..., ...}
scheduler_started                 jobs=['rss', 'email', 'webpage', 'community', 'linkedin', 'reputation', 'expire']
polling_started
```

**Failure modes at this stage:**

| Symptom | Cause | Fix |
|---|---|---|
| `ValidationError ... bot_token Field required` | `.env` missing/not filled | check §2, file must be named exactly `.env` |
| `alembic ... connection refused` loops forever | wrong `DATABASE_URL`, or localdb profile without the db service | verify URL; use `--profile localdb` |
| `InvalidPasswordError` from asyncpg | Supabase password placeholder still in URL | re-copy connection string |
| `TelegramUnauthorizedError` | bad `BOT_TOKEN` | re-copy from BotFather |
| `extension "vector" is not available` | pgvector not enabled | Supabase → Extensions → vector |

---

## 5. Local verification — the full acceptance test

Run these in order. Each step has an explicit pass condition. When all 8 pass,
the system is working end-to-end and you're clear to deploy.

### Test 0 — automated suite

```bash
# on the host, with the venv from §4.3 (tests are excluded from the Docker
# image by .dockerignore, so run them outside the container)
pytest -q
```

✅ **Pass:** `36 passed`. Covers hard gate, scoring, AI failover, forward matching.

### Test 1 — student onboarding

DM your bot `/start`. Walk through: language → degree → fields → English cert
→ GPA.

✅ **Pass:** you get the "Profile saved" message and the command list.
Switch language with `/language` → the interface flips EN↔HY instantly.

### Test 2 — admin surface

From your admin account:

- `/listsources` → ✅ **~100 sources** listed across types (webpage/rss/email/community/linkedin)
- `/ai_status` → ✅ all three providers show 🟢 (or ⚪️ for keys you skipped),
  priority `groq → deepseek → gemini`
- `/stats` → ✅ responds (all zeros on a fresh DB is correct)

### Test 3 — the pipeline actually ingests

Don't wait for the scheduler (interval jobs fire their *first* run one full
interval after startup — 20 min for RSS, 4 h for webpages). Trigger a cycle
on demand from your admin account:

```
/scrape           ← runs the RSS sources now (fastest, ~1-2 min)
/scrape webpage   ← runs all webpage sources (several minutes, polite spacing)
/scrape all       ← everything; can take a long while, fine to leave running
```

The bot replies immediately, then DMs a summary when the cycle finishes
("N new items queued" or "nothing new queued"). Meanwhile, watch the logs:

✅ **Pass:** log lines like

```
rss_fetched            source=Opportunity Desk entries=30
loading_embedding_model  (first time only; downloads ~90 MB)
discarded              title=... reason=field: no match against taxonomy
queued_for_review      opp_id=1 legitimacy=62 chance=41
scrape_cycle_done      types=['rss'] new_pending=3
```

and a DM to your admin account: *"📥 N new opportunities awaiting review — /queue"*.

`discarded` lines are **normal and good** — most scraped candidates should
die at the hard gate. Inspect them with `/discards`; each shows its reason
(funding / eligibility / field / noise / low legitimacy).

⚠️ If *every* item is discarded and `/queue` stays empty after several cycles,
check `/discards` reasons: all-`field:` means taxonomy keywords are too narrow
(`/listfields`, `/addfield`); all-`funding:` is expected from fee-heavy sources.
Re-running `/scrape` right away and getting "nothing new queued" is also
correct — already-seen items are deduplicated silently.

### Test 4 — review queue & publishing

1. `/queue` → a card with Approve / Reject / Edit / Skip buttons.
2. Press **Edit** → send replacement body text → send a photo or `/skip` →
   you get a preview. ✅ Body changed; buttons and `#opp<id>` tag intact.
3. Press **Approve**.

✅ **Pass:** callback answers *"Published to N channel(s)"* and the post
appears in every channel matching the item's degree levels, with three
buttons: 🚀 Apply / ℹ️ Details / 📊 Analyze my fit, and a `#opp<id>` footer.

⚠️ *"Published to 0 channel(s)"* = bot isn't admin in the target channel, or
wrong channel ID. Check §2.2 and the `publish_failed` log line.

### Test 5 — forward-to-bot matching

Forward the just-published post from the channel back to the bot's DM.

✅ **Pass:** full detail card: type, funding tier, deadline, degree levels,
🇦🇲 Armenian-eligibility note, English requirement vs your profile score
(✅ meets / ⚠️ below / ⚠️ expired), requirements, and your personal chance %.

### Test 6 — documents & fit analysis

1. `/mydocs` → Upload resume → send a PDF/DOCX/TXT.
   ✅ *"Saved and parsed «file» (N characters extracted)"* with N > 0.
2. In the channel post, tap **📊 Analyze my fit** (deep-links into the bot),
   or forward the post again (with a resume on file it auto-analyzes).

✅ **Pass:** within ~20–30 s you get: match score /100, concrete gaps,
suggestions, and sample resume bullets. This also proves the AI router works
end-to-end (check `/ai_status` afterwards — request counts incremented).

### Test 7 — search & saved filters

`/search` → tap filters (they cycle on tap) → **Run search**.
✅ Published items matching the filters are returned.
**Save this filter** → name it. `/filters` → toggle 🔔.
✅ Next time you approve a matching item, that user gets a DM notification.

### Test 8 — live config (no restart)

- `/ai_setpriority gemini groq deepseek` → `/ai_status` shows the new order.
- `/ai_disable groq` → `/ai_status` shows groq 🔴 → `/ai_enable groq`.
- `/addsource rss https://opportunitydesk.org/feed/ aggregator Test dup` →
  ✅ accepted (it will just dedupe against existing items).
- `/setband 40 65`, `/setminduration 15` → echo current values.

✅ **Pass:** all take effect immediately, no restart.

### Test 9 (optional) — newsletter mailbox end-to-end

Only if you configured `NEWSLETTER_IMAP_*`. This tests the whole email
acquisition channel deterministically:

1. From your personal email, send a message **to the dedicated mailbox**
   containing an opportunity-shaped line, e.g.:
   ```
   Fully funded data science internship with stipend, open to all
   nationalities: https://careers.example.org/ds-intern-2027
   ```
2. In the bot (admin): `/scrape email`

✅ **Pass:** completion DM reports ≥1 new item; `/queue` shows it with
`[newsletter: <your subject>]` at the start of its description.

⚠️ `email_skipped_not_configured` in logs = IMAP vars are blank.
`source_fetch_failed` with `LOGIN` in the error = wrong app password
(it must be a Gmail App Password, not the account password).
Nothing found on a re-run is correct — the email was marked read; mark it
unread in Gmail to re-process it.

**All green → the system is fully functional. Proceed to deploy.**

---

## 6. Understanding steady-state (what "running well" looks like)

- **Cadence:** RSS every 20 min, email every 15 min, webpages/community every
  4 h, LinkedIn every 6 h, reputation recompute 03:30, expiry sweep 00:15
  (times in `TZ`, default Asia/Yerevan).
- **Volume:** expect a burst of pending items in the first 24 h (backlog of
  ~100 sources), then a trickle. The queue is meant to be triaged daily —
  Reject aggressively; the reputation job learns from it.
- **Discard ratio:** 80–95% of raw candidates being discarded is healthy.
  The system's job is to waste *your* time as little as possible.
- **Source failures:** individual `source_fetch_failed` warnings are normal
  (sites change, Indeed blocks, timeouts). The cycle continues. A source
  failing *every* run for weeks → `/togglesource <id>` it off.
- **AI usage:** tiebreaks only fire for legitimacy scores inside the band
  (default 40–65) and fit analyses when users request them. If `/ai_status`
  shows heavy 429s, lower `*_RPM` values or reorder priority.

---

## 7. Deploy to Render (free tier, webhook mode)

### 7.1 The one honest caveat first

Render's free web service **spins down after ~15 min without HTTP traffic**.
Telegram webhooks wake it (with a ~50 s cold start), but **APScheduler does
not run while it sleeps** — no scraping. The fix is an external keep-alive
ping (step 7.5), which is also free. Skipping it = the bot answers users but
the channels go quiet. Don't skip it.

Also preset in the blueprint: `PLAYWRIGHT_ENABLED=false` (512 MB RAM cap).
JS-heavy sources yield less on Render than locally — documented trade-off.
The embedding model (~90 MB) re-downloads on each cold start (ephemeral disk);
first embed after a restart is slow, then cached in memory.

### 7.2 Push to GitHub

```bash
git remote add origin https://github.com/<you>/moonin-ai.git
git push -u origin main
```

(`.env` is gitignored — verify with `git status` that it's not staged.)

### 7.3 Create the service from the blueprint

1. https://render.com → sign up (GitHub login) → **New → Blueprint**.
2. Select the repo. Render reads `render.yaml` and proposes
   `moonin-opportunities-bot` (free web service, Docker). Approve.
3. It will prompt for every `sync: false` env var — paste the same values as
   your local `.env` (`BOT_TOKEN`, channel IDs, `ADMIN_USER_IDS`,
   `DATABASE_URL`, three AI keys, IMAP trio, proxies if any).
   **Leave `WEBHOOK_BASE_URL` empty for now** — you don't know the URL yet.
4. First deploy will build (10–20 min: torch) and then **fail to fully start**
   (webhook mode requires `WEBHOOK_BASE_URL`) — expected, next step fixes it.

### 7.4 Set the webhook URL

1. Copy the service URL from the dashboard header:
   `https://moonin-opportunities-bot.onrender.com` (yours will differ).
2. Environment → set `WEBHOOK_BASE_URL` to exactly that URL → **Save** →
   Render redeploys automatically.
3. ✅ **Pass:** Logs show
   `webhook_started port=8080 url=https://....onrender.com/webhook`
   and the health check turns green.

Verify from your machine that Telegram accepted the webhook:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

✅ **Pass:** `"url":"https://....onrender.com/webhook"`, `"pending_update_count":0`
(or draining), and **no** `"last_error_message"`. If you see
`wrong response from the webhook: 502` right after deploy, the instance was
cold — send the bot a message and re-check.

> Polling vs webhook are mutually exclusive per token. If you later run
> locally again, local start calls `delete_webhook` automatically — but then
> Render is dead until it re-registers on its next restart. Rule of thumb:
> **one environment at a time per bot token** (or create a second BotFather
> bot for dev).

### 7.5 Keep-alive ping (mandatory)

1. https://cron-job.org → free account → **Create cronjob**:
   - URL: `https://<your-service>.onrender.com/health`
   - Schedule: **every 10 minutes**
   - Notifications: on failure only (optional but useful — it doubles as
     uptime monitoring).
2. ✅ **Pass:** cron-job.org execution history shows HTTP 200 with body
   `{"status": "ok"}`, and after 30+ idle minutes the Render logs show **no**
   "spinning down" events during the day.

### 7.6 Post-deploy acceptance test (10 minutes)

Re-run the essentials against production:

- [ ] DM the bot `/start` → responds within a few seconds (cold start may add
      ~1 min the very first time)
- [ ] `/ai_status`, `/listsources`, `/stats` respond
- [ ] Wait ≤ 20 min → `scrape_cycle_done` appears in Render logs
- [ ] `/queue` → approve one item → lands in the channel
- [ ] Forward it back → detail card resolves
- [ ] `getWebhookInfo` still clean, cron-job history all-green

All checked → **production is live.**

### 7.7 Free-tier budget notes

- Render free: 750 instance-hours/month = exactly one always-on service.
- Supabase free: pauses after ~7 days of zero traffic — the scheduler's
  constant queries prevent that as long as keep-alive works.
- The keep-alive ping (~4,300 requests/month) costs nothing on either side.

---

## 8. Troubleshooting quick reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot silent in DM (prod) | webhook broken | `getWebhookInfo`; check `WEBHOOK_BASE_URL` matches service URL exactly, redeploy |
| Bot silent in DM (local) | webhook still registered from prod | start locally once (it deletes the webhook) or `curl .../deleteWebhook`; remember: one env at a time |
| "Published to 0 channel(s)" | bot not channel admin / wrong ID | §2.2; see `publish_failed` in logs |
| Queue always empty | over-aggressive gate or dead sources | `/discards` for reasons; `/listfields` keywords; `/listsources` last-checked times |
| `email_skipped_not_configured` | IMAP vars blank | fine if intentional; else §2.6 (app password, not account password) |
| Fit analysis always fails | all AI keys bad/throttled | `/ai_status` last-error lines; test one provider's key with curl |
| Frequent 429 in `/ai_status` | RPM throttles too high for your tier | lower `GROQ_RPM`/`DEEPSEEK_RPM`/`GEMINI_RPM` |
| OOM / restarts on Render | Playwright enabled on 512 MB | keep `PLAYWRIGHT_ENABLED=false` on free tier |
| Indeed/LinkedIn sources always fail | anti-bot blocking | expected without proxy; set `SCRAPER_PROXY_URL`/`LINKEDIN_PROXY_URL` or toggle sources off |
| `asyncpg` prepared-statement errors | transaction pooler (port 6543) | switch `DATABASE_URL` to session pooler (5432) |

## 9. Routine operations

Daily (2 min): `/queue` triage. Weekly: `/stats`, `/discards` skim,
cron-job.org history glance. When adding sources: `/addsource <type> <url>
[category[:js]] [name]` — takes effect next cycle, no deploy. When a batch of
sources arrives, prefer a seed migration (see `alembic/versions/0003`/`0004`
as templates) so they're versioned and survive DB resets.
