# Command Reference

Every command with worked examples. The same content is available inside the
bot: `/help` (students, bilingual) and `/adminhelp` (admins, English).
For longer step-by-step recipes (with screenshots-in-text of each flow), see
[GUIDES.md](GUIDES.md).

---

## Student commands

### `/start`
First contact and onboarding: language (🇬🇧/🇦🇲) → degree level → fields of
interest (multi-select) → English certificate (IELTS/TOEFL score + expiry,
skippable) → GPA (optional). Also the target of every deep-link button on
channel posts (Details / Analyze / Save open the bot through it).

> Redo anytime: `/profile` → «✏️ Redo onboarding».

### `/search` — filterable opportunity browser
Menu of tap-to-cycle filters; every tap advances that filter to its next
value (`any` → value₁ → value₂ → … → `any`).

**Example session:**
```
/search
[Field: any]      → tap → [Field: Data Science]
[Degree: any]     → tap → [Degree: undergrad]
[Deadline within: any] → tap → [7 days] → tap → [30 days]
[Min. chance: any]     → tap → [20] → tap → [40]
▶️ Run search
```
Results arrive as full post cards (5 per page, ◀️ ▶️ pagination) with
Apply / ⭐ Save / Details / Analyze buttons.

### `/filters` — saved searches & push notifications
From any `/search` setup, tap «💾 Save this filter» and name it (e.g.
`ML internships EU`). From then on, every newly published post matching it
triggers a DM. `/filters` lists them with per-filter controls:
`▶️` run again · `🔔/🔕` toggle notifications · `🗑` delete.

### `/saved` — bookmarks, reminders, application tracker
Tap **⭐ Save** on any channel post or bot card. Saved items get:
- **deadline reminders** 7, 3 and 1 days before, at 10:00 Yerevan time;
- **✅ Applied** — marks it applied, silences its reminders, and ~30 days
  after the deadline the bot asks how it went (🎉 Accepted / 😞 Rejected /
  ⏳ Still waiting — waiting is re-asked monthly).

**Example list:**
```
⭐ Your saved opportunities
1. OIST Research Internship 📅 2027-04-15
2. Fully funded ML fellowship 📅 2027-02-01 ✅
[1 ℹ️] [1 ✅ Applied] [1 🔕] [1 🗑]
[2 ℹ️] [2 ↩️✅]      [2 🔕] [2 🗑]
```

### `/mydocs` — resume & documents
Upload a resume (PDF/DOCX/TXT, ≤10 MB — replaces the previous one) and any
number of cover letters/notes (files or plain text). Text is extracted and
stored; this unlocks **📊 Analyze my fit** everywhere.

**Fit analysis output:** overall match score /100 · specific gaps · concrete
improvement suggestions · sample resume/cover bullets you can adapt.

### Forward any channel post to the bot
No command needed. Forward a post from any of the three channels into the
bot's DM → full detail card: funding classification, deadline, duration,
requirements, 🇦🇲 Armenian-eligibility note, English requirement checked
against *your* stored score and expiry, your personalized chance — plus an
automatic fit analysis if a resume is on file.

### `/profile`, `/language`, `/help`
View profile / switch 🇬🇧⇄🇦🇲 instantly / this reference.

---

## Admin commands

Admin access = your Telegram ID is in `ADMIN_USER_IDS`. Admin UI is English.

### Review workflow

| Command | Purpose | Example |
|---|---|---|
| `/queue` | paginated **list view** of pending items (type + title + ⚠️ eligibility flags); numbered buttons open the classic card | `/queue` → tap `3` |
| `/archive` | same view over the «review later» shelf | `/archive` |
| `/discards` | last 15 auto-discarded items **with reasons** — your window into the silent filter | `/discards` |
| `/stats` | pipeline counts per status + users/saves/applied/outcomes | `/stats` |
| `/scrape [type\|all]` | run a scrape cycle now instead of waiting for the scheduler | `/scrape` (rss) · `/scrape webpage` · `/scrape all` |
| `/digest` | compile weekly-digest previews on demand (post/skip per channel) | `/digest` |

**The card** (opened from the list) offers:
`✅ Approve` `❌ Reject` / `✏️ Edit text` `🖼 Photo` / `◀️` `🗂 Later` `▶️` / `📋 List view`.

**Approve flow:** Approve → one capped AI call generates TL;DR +
competitiveness + requirement bullets → **preview** with a channel picker
(`✅ Undergrad ⬜ Masters ⬜ Phd` toggles, pre-checked from detected degree
levels) → `🚀 Publish to selected` / `✏️ Edit first` / `↩️ Use original (no
AI)`. Nothing posts without the 🚀 tap; on AI cap/failure the preview simply
shows the original text.

### Sources & taxonomy

| Command | Example |
|---|---|
| `/addsource <type> <url> [category[:js]] [name…]` | `/addsource rss https://example.org/feed/ aggregator Example feed`<br>`/addsource webpage https://lab.edu/jobs institute:js Lab careers` (`:js` = render with Playwright) |
| `/listsources` | registry with per-source status and last-checked times |
| `/togglesource <id>` | `/togglesource 42` — disable/enable without deleting |
| `/sourcemeta <id> <key> <value>` | `/sourcemeta 12 selector div.jobs-list` — scope that source's scraping to a CSS container (precision mode); `-` as value removes the key |
| `/addfield <Name> \| <kw1, kw2…>` | `/addfield Robotics \| robotics, ros, autonomous systems` |
| `/listfields`, `/togglefield <id>` | inspect / toggle taxonomy entries |

### AI router & scoring tunables (all live, no redeploy)

| Command | Example | Effect |
|---|---|---|
| `/ai_status` | — | providers, priority, request/error/429 counts, last errors |
| `/ai_setpriority <order>` | `/ai_setpriority gemini groq deepseek` | reorder failover chain |
| `/ai_disable` / `/ai_enable <name>` | `/ai_disable groq` | pull a provider out of rotation |
| `/setweight <key> <0..1>` | `/setweight acceptance 0.6` | chance-score weights |
| `/setband <low> <high>` | `/setband 45 70` | AI-tiebreak legitimacy band |
| `/setminduration <days>` | `/setminduration 21` | noise-rule minimum duration |
| `/setcap <n>` | `/setcap 30` | daily AI-enrichment budget |

### Text customization & communication

| Command | Example |
|---|---|
| `/listtexts [filter]` | `/listtexts reminder` — find keys (✏️ marks customized) |
| `/gettext <key>` | `/gettext saved_ok` — current EN/HY values + originals |
| `/settext <en\|hy> <key> <text…>` | `/settext en btn_apply 🔥 Apply now!` — HTML + emoji allowed; **keep the `{placeholders}`** |
| `/resettext <en\|hy> <key>` | `/resettext en btn_apply` |
| `/refreshcommands` | push edited `cmd_*` menu descriptions to Telegram — the ≡ command menu is localized (EN default, HY for Armenian Telegram clients) |
| `/broadcast <message>` | `/broadcast 🎉 We just launched deadline reminders — tap ⭐ Save on any post!` → preview → confirm → rate-limited DM to every user |

### Operational habits that keep quality high

- **Reject ruthlessly.** Every reject trains per-domain reputation; borderline
  garbage approved today is a worse channel tomorrow.
- **Skim `/discards` weekly.** All-`field:` reasons → widen taxonomy keywords;
  a gem in the discards → loosen the specific rule that killed it.
- **`⚠️ UNCERTAIN` eligibility flags mean *you* verify** the official page
  before approving — that flag exists so nothing is silently wrong.
- A source erroring for weeks in `/listsources` → `/togglesource` it off;
  ~5% of sources failing per cycle is normal steady state, not an incident.
