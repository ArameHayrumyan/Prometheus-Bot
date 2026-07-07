"""/adminhelp — the complete admin reference, with an example per command.
Mirrors docs/COMMANDS.md; sent in chunks to respect Telegram's 4096 limit."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.handlers.admin import IsAdmin

router = Router()
router.message.filter(IsAdmin())

PART_1 = """🛠 <b>Admin reference (1/2) — review &amp; sources</b>

📥 <b>Review workflow</b>

/queue — pending items as a numbered list (type · title · ⚠️ flags).
Tap a number → the classic card: ✅ Approve · ❌ Reject · ✏️ Edit text ·
🖼 Photo · ◀️ 🗂 Later ▶️ · 📋 List view.

<b>Approve flow:</b> Approve → one AI call (TL;DR + competitiveness +
requirement bullets, daily-capped) → preview with channel toggles
(✅ Undergrad ⬜ Masters ⬜ Phd) → 🚀 Publish to selected / ✏️ Edit first /
↩️ Use original. <i>Nothing posts without the 🚀 tap.</i>

/archive — the «🗂 Later» shelf; same card actions + move back to queue.
/discards — last 15 auto-filtered items with reasons.
   <i>All-«field:» reasons → widen taxonomy keywords (/listfields).</i>
/stats — pipeline counts + users, saves, applied, outcomes.
/scrape [type|all] — run a cycle NOW instead of waiting.
   <code>/scrape</code> (rss, fastest) · <code>/scrape webpage</code> ·
   <code>/scrape all</code> (long, fire &amp; forget — you get a summary DM)
/digest — compile the weekly digest previews on demand;
   each preview has 📣 Post to channel / ✖️ Skip buttons.

🗂 <b>Sources &amp; taxonomy</b>

/addsource &lt;type&gt; &lt;url&gt; [category[:js]] [name…]
   <code>/addsource rss https://example.org/feed/ aggregator Example feed</code>
   <code>/addsource webpage https://lab.edu/jobs institute:js Lab careers</code>
   (types: webpage, rss, email, community, linkedin; «:js» = Playwright)
/listsources — full registry with last-checked times.
/togglesource &lt;id&gt; — <code>/togglesource 42</code> — pause/resume a source.
/addfield Name | kw1, kw2 —
   <code>/addfield Robotics | robotics, ros, autonomous systems</code>
/listfields · /togglefield &lt;id&gt; — inspect / toggle taxonomy."""

PART_2 = """🛠 <b>Admin reference (2/2) — AI, tunables, texts</b>

🤖 <b>AI router</b> (all live, no redeploy)

/ai_status — providers, priority, request/error/429 counts.
/ai_setpriority — <code>/ai_setpriority gemini groq deepseek</code>
/ai_disable · /ai_enable — <code>/ai_disable groq</code>

⚖️ <b>Scoring tunables</b>

/setweight &lt;key&gt; &lt;0..1&gt; — <code>/setweight acceptance 0.6</code>
   (keys: acceptance, selectivity, requirements)
/setband &lt;low&gt; &lt;high&gt; — <code>/setband 45 70</code> — AI-tiebreak band.
/setminduration &lt;days&gt; — <code>/setminduration 21</code> — noise rule.
/setcap &lt;n&gt; — <code>/setcap 30</code> — daily AI-enrichment budget
   (also shows today's usage when called bare).

🔤 <b>Text customization</b> (any user-facing string, instant, survives redeploys)

/listtexts [filter] — <code>/listtexts reminder</code> — find keys (✏️ = customized).
/gettext &lt;key&gt; — <code>/gettext saved_ok</code> — current EN/HY + originals.
/settext &lt;en|hy&gt; &lt;key&gt; &lt;text&gt; —
   <code>/settext en btn_apply 🔥 Apply now!</code>
   HTML + emojis allowed; <b>keep the {placeholders}</b> of the original.
/resettext &lt;en|hy&gt; &lt;key&gt; — back to default.
/refreshcommands — push edited cmd_* menu descriptions to Telegram
   (menus are localized: EN default, HY for Armenian Telegram clients).

📢 <b>Communication</b>

/broadcast &lt;message&gt; —
   <code>/broadcast 🎉 Deadline reminders are live — tap ⭐ Save on any post!</code>
   Preview → confirm → rate-limited DM to every bot user.

💡 <b>Habits:</b> reject ruthlessly (trains source reputation) · skim
/discards weekly · ⚠️ UNCERTAIN eligibility means YOU verify the official
page before approving · a source failing for weeks → /togglesource off."""


@router.message(Command("adminhelp"))
async def cmd_adminhelp(message: Message):
    await message.answer(PART_1, parse_mode="HTML", disable_web_page_preview=True)
    await message.answer(PART_2, parse_mode="HTML", disable_web_page_preview=True)
