# Admin Cookbook — step-by-step guides

Worked, end-to-end recipes for every operational task. Companion to
[COMMANDS.md](COMMANDS.md) (reference) and [ARCHITECTURE.md](ARCHITECTURE.md)
(internals). Everything here happens in your Telegram chat with the bot —
no redeploys, no code.

---

## 1. Adding a new source (basic)

**Scenario:** you found `https://csjobs.example.edu/openings` — a university
CS department's openings page.

**Step 1 — add it:**
```
/addsource webpage https://csjobs.example.edu/openings university Example Uni CS
```
The bot replies with the new source's id, e.g. `Source #141 added`.

**Step 2 — test it immediately** (don't wait up to 4 h for the scheduler):
```
/scrape webpage
```
Watch for the completion DM: `✅ Cycle done (webpage): 2 new items queued — /queue`.

**Step 3 — check what the filter did.** If nothing was queued:
```
/discards
```
- Reasons like `funding: student pays…` → the page's listings genuinely
  failed the gate. Working as intended.
- Reasons like `field: no match against taxonomy` on items that ARE relevant
  → your taxonomy keywords are too narrow (see recipe 7).
- Nothing in discards either → the page yielded no candidates at all →
  go to recipe 2 (selector) or 3 (JS rendering).

**Variants:**
- JS-rendered page (content appears only after the page "loads"):
  ```
  /addsource webpage https://spa.example.com/jobs company:js Example SPA
  ```
  The `:js` suffix makes Playwright render it (works locally; on Render free
  tier it falls back to plain HTTP).
- RSS feed (always prefer it when a site offers one — cheaper, cleaner,
  polled every 20 min instead of 4 h):
  ```
  /addsource rss https://blog.example.org/feed/ aggregator Example feed
  ```
- Pause / resume any source: `/togglesource 141`.

---

## 2. Precision mode: CSS selector per source

**Problem it solves:** the generic scraper harvests every opportunity-looking
link on a page. On busy pages it also picks up "Careers" menu items, sidebar
teasers, related-articles blocks — noise that lands in your queue.

**Scenario:** source #141 keeps producing junk candidates like "Why work in
software? (blog)" from the sidebar.

**Step 1 — find the listing container.** Open the page in your browser →
right-click one real job listing → **Inspect**. In DevTools, look upward
from the highlighted element until you find the element wrapping *all* the
listings, e.g.:

```html
<div class="jobs-list">          ← this is what you want
  <li><a href="/jobs/1">Bioinformatics research internship</a></li>
  <li><a href="/jobs/2">Junior software engineer</a></li>
</div>
<div class="sidebar">…noise…</div>
```

**Step 2 — attach the selector to the source:**
```
/sourcemeta 141 selector div.jobs-list
```
Bot confirms: `✅ Source #141 meta: {'selector': 'div.jobs-list'}`.

**Step 3 — verify:**
```
/scrape webpage
```
Now only links inside `div.jobs-list` are considered; the sidebar is
invisible to the scraper.

**Selector tips:**
- Any CSS works: `#vacancies`, `table.results`, `main .openings`,
  and selectors matching the links themselves: `div.jobs-list a.job-link`.
- Multiple containers? Comma-separate: `div.internships, div.fellowships`.
- Remove it later with the `-` value:
  ```
  /sourcemeta 141 selector -
  ```
- Wrong selector = zero candidates (not an error). If a source suddenly
  yields nothing after you set one, the site probably changed its markup —
  re-inspect and update.

---

## 3. The newsletter mailbox (email channel), tested end-to-end

The email channel turns **any newsletter subscription into a source** with
zero configuration — often surfacing opportunities before they're indexed
anywhere scrapeable.

**One-time setup** (deploy.md §2.6): dedicated Gmail, 2FA + app password,
`NEWSLETTER_IMAP_*` in `.env`.

**Adding "sources"** = subscribing the mailbox:
1. Go to profellow.com / opportunitydesk.org / any university career-center
   page → subscribe with the mailbox address.
2. LinkedIn: log the mailbox's LinkedIn account in → search e.g.
   *data science intern*, location *Worldwide*, filter *Remote* → **Set alert**
   → frequency: daily email. Repeat per search. This is the recommended,
   ToS-clean LinkedIn channel.

**How ingestion works:** every 15 minutes the bot reads UNSEEN messages,
extracts opportunity-looking links plus their surrounding text, feeds them
into the same normalize → gate → scoring pipeline as everything else, and
marks the email read. The newsletter's subject is preserved in the item's
description as `[newsletter: <subject>]`.

**Test it right now, deterministically:**
1. From your personal email, send the mailbox a message containing:
   ```
   Fully funded data science internship with stipend, open to all
   nationalities: https://careers.example.org/ds-intern-2027
   ```
2. In the bot: `/scrape email`
3. Expected: completion DM reports 1 new item; `/queue` shows it with the
   `[newsletter: …]` marker in its description.

**Quirks to know:**
- Gmail's Promotions tab doesn't matter — IMAP sees the whole INBOX.
- Tracking-redirect links (Mailchimp etc.) are kept as-is; the same
  opportunity from two newsletters may appear twice → just Reject the dupe.
- Emails are marked read after parsing; if you want a message re-processed,
  mark it unread in Gmail and `/scrape email` again.

---

## 4. Review & publish, the full path

**Scenario:** the bot DMs you `📥 5 new opportunities awaiting review`.

1. `/queue` → **list view**:
   ```
   📥 Review queue · 5 items · page 1/1
   1. 🧑‍💻 INTERNSHIP — OIST Research Internship 2027
   2. 💼 JOB — Junior Backend Engineer, Yerevan ⚠️
   ...
   [1] [2] [3] [4] [5]
   [🃏 Card view]
   ```
   `⚠️` = uncertain Armenian eligibility → *you* verify the official page
   before approving that one.
2. Tap `[1]` → the **card**: full details, scores, description, and actions
   (`✅ ❌ / ✏️ 🖼 / ◀️ 🗂 ▶️ / 📋`). `🗂 Later` shelves it to `/archive`.
3. Tap **✅ Approve** → `✨ Enriching…` → one AI call (daily-capped, cached)
   → **preview** of the exact post: AI TL;DR instead of the messy scraped
   text, 📋 requirement bullets, 📊 competitiveness line, plus:
   ```
   [✅ Undergrad] [⬜ Masters] [⬜ Phd]
   [🚀 Publish to selected] [✏️ Edit first]
   [↩️ Use original (no AI)]
   [◀️ Back to queue]
   ```
4. Channel toggles are pre-checked from detected degree levels — tap to
   adjust (e.g. also enable Masters).
5. **🚀 Publish to selected** → posts to those channels with auto-generated
   buttons (Apply · ⭐ Save · Details · Analyze), notifies matching saved
   filters, records your channel choice in the audit log, and shows the next
   card.

**Edit-first path:** `✏️ Edit first` → send replacement body text (HTML ok)
→ send a photo or `/skip` → preview → Approve again (uses the cached
enrichment — no second AI call) → publish.

**No-AI path:** `↩️ Use original` re-renders the preview with the regex
description. If the daily AI cap is exhausted, the preview simply appears
with the original text and a ⚠️ note — the flow never blocks.

---

## 5. Customizing any text (and the command menus)

Every string a user sees is a key. Three-command workflow:

**Step 1 — find the key.** You want to change the reminder message:
```
/listtexts remind
→ reminder_msg — ⏰ <b>{days} day(s) left</b> to apply:…
```

**Step 2 — inspect both languages:**
```
/gettext reminder_msg
→ [en] (default): ⏰ <b>{days} day(s) left</b> to apply: …
→ [hy] (default): ⏰ <b>Մնացել է {days} օր</b> …
```

**Step 3 — override (per language, HTML + emoji fine, KEEP the placeholders):**
```
/settext en reminder_msg 🔥 Only {days} day(s) left for <b>{title}</b>! Deadline: {deadline}
/settext hy reminder_msg 🔥 Մնացել է ընդամենը {days} օր՝ <b>{title}</b>։ Վերջնաժամկետ․ {deadline}
```
Applies instantly, survives restarts and redeploys. Undo anytime:
`/resettext en reminder_msg`.

⚠️ If you drop a `{placeholder}`, nothing crashes — the text just shows the
raw braces. `/gettext` always shows the original so you can copy its
placeholders.

**Command menus (the ≡ button)** are the `cmd_*` keys and need one extra
push because Telegram caches menus:
```
/settext en cmd_search 🔍 Find opportunities
/settext hy cmd_search 🔍 Գտիր հնարավորություններ
/refreshcommands
```
English Telegram clients see the EN menu, Armenian clients the HY menu —
each fully monolingual.

**Post appearance:** the channel-post type headers are keys too:
```
/settext en type_internship 🧑‍💻 INTERNSHIP OPPORTUNITY
```
Set your real channel links once:
```
/settext en channels_promo 📣 Channels: @moonin_bsc · @moonin_msc · @moonin_phd
```

---

## 6. Digest & broadcast

**Digest** (never auto-posts): every Sunday 19:00 — or on demand with
`/digest` — you receive one preview per channel: top-5 open items ranked by
deadline urgency then chance, skipped when a channel has <3 dated open items.
Tap `📣 Post to channel` (it re-compiles at that moment, so it's never stale)
or `✖️ Skip this week`.

**Broadcast** (launch announcements, feature news):
```
/broadcast 🎉 New: tap ⭐ Save on any post and I'll remind you 7, 3 and 1 days before the deadline!
```
→ preview → `📤 Send to everyone` → rate-limited delivery → report:
`📤 Broadcast done: 517 delivered, 3 failed/blocked`.

---

## 7. Tuning the pipeline

**Queue too empty?** `/discards` tells you which rule is eating things:
- many `field:` discards → widen keywords:
  `/addfield Data Science | mlops, generative ai, prompt engineering`
  (merges into the existing field's keyword list)
- many `noise: duration` discards on legit short programs →
  `/setminduration 10`
- many `legitimacy score below band` → `/setband 35 65` (lowers the discard
  floor; more items get the AI tiebreak instead of dying silently)

**Queue too noisy?** Reject freely — the nightly reputation job de-weights
domains you reject. For structurally noisy sources: recipe 2 (selector), or
`/togglesource`.

**Chance% feels off?** `/setweight acceptance 0.6` (trust stated rates
more), `/setweight selectivity 0.3` (punish prestige harder). Current values
show when called bare.

**AI budget:** `/setcap` bare shows today's usage; `/ai_status` shows
per-provider health; `/ai_setpriority deepseek groq gemini` reorders
failover live.

---

## 8. What a student experiences (so you can support them)

1. Finds `@your_channel` → sees a post → taps **⭐ Save** → bot opens with
   "⭐ Saved! I'll remind you 7, 3 and 1 days before the deadline."
2. At 10:00 Yerevan, 7 days out: reminder DM with Details / ✅ Applied / 🔕.
3. Taps **✅ Applied** → reminders for that item stop.
4. ~30 days after the deadline: "You applied to «…» — how did it go?"
   (🎉 / 😞 / ⏳). Answers accumulate in `/stats` — your real acceptance-rate
   dataset.
5. Uploads a resume via `/mydocs` once → every post's **📊 Analyze my fit**
   returns a match score, gaps, and suggested resume bullets; forwarding any
   channel post to the bot gives the full detail card + that analysis.
