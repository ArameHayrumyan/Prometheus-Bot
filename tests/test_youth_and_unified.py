"""Youth-relaxed gate, unified-channel tags, channel refs, Telegram scraper."""
from datetime import date

from app.constants import parse_channel_ref
from app.bot.posting import _tag_slug, post_tags
from app.db.models import Opportunity
from app.db.settings_service import DEFAULTS
from app.pipeline import hard_gate
from app.pipeline.normalize import extract_all
from app.scraping.telegram_channel import normalize_channel_url, parse_channel_page

TAXONOMY = {"Computer Science": ["computer science", "software", "programming"],
            "Data Science": ["data science", "machine learning"]}
NOISE = DEFAULTS["noise_keywords"]
DELIVER = DEFAULTS["deliverable_keywords"]


def gate(title, text, youth):
    extracted = extract_all(title, text, TAXONOMY, NOISE, DELIVER)
    return hard_gate.evaluate(extracted, 15, youth=youth)


# ---- youth-relaxed gate ----

def test_short_camp_fails_student_passes_youth():
    title = "Robotics summer camp for schoolkids"
    text = ("Free 5 day robotics and programming camp, fully funded, open to "
            "all nationalities, certificate awarded.")
    assert not gate(title, text, youth=False).passed
    assert gate(title, text, youth=True).passed


def test_youth_skips_field_taxonomy():
    title = "Young leaders science school"
    text = ("Fully funded 10 day science school for teenagers, open to all "
            "nationalities, diploma awarded.")
    assert not gate(title, text, youth=False).passed  # no taxonomy match
    assert gate(title, text, youth=True).passed


def test_youth_funding_rule_still_absolute():
    result = gate("Coding camp", "Great 2 week coding camp! Participation fee: $500. "
                                 "Open to all nationalities.", youth=True)
    assert not result.passed
    assert "funding" in result.discard_reason


def test_youth_eligibility_rule_still_absolute():
    result = gate("Programming school",
                  "Fully funded programming school with certificate, only open to "
                  "citizens of Japan.", youth=True)
    assert not result.passed


def test_youth_legitimacy_not_punished_for_camp_duration():
    # the gate admits a funded 7-day youth camp; the legitimacy score must not
    # silently discard it again via student-scale duration thresholds
    from app.pipeline.normalize import Extracted
    from app.pipeline.scoring import legitimacy_score

    camp = Extracted(opportunity_type="training", funding_tier="FULLY_FUNDED",
                     duration_days=7, has_deliverable=True)
    youth_score = legitimacy_score(camp, 0.85, False, youth=True)
    student_score = legitimacy_score(camp, 0.85, False, youth=False)
    assert youth_score > student_score
    assert youth_score >= 66  # comfortably above the default discard floor (40)


# ---- channel refs (plain / forum topic) ----

def test_parse_channel_ref():
    assert parse_channel_ref("-1001234567890") == (-1001234567890, None)
    assert parse_channel_ref("-1001234567890:17") == (-1001234567890, 17)
    assert parse_channel_ref(" -100123:5 ") == (-100123, 5)


# ---- unified-channel hashtag navigation ----

def _opp(**kw) -> Opportunity:
    o = Opportunity(url="u", raw_hash="h", title="t", opportunity_type="internship")
    o.id = 42
    o.audience = kw.pop("audience", "student")
    o.degree_levels = kw.pop("degree_levels", [])
    o.fields = kw.pop("fields", [])
    o.country = kw.pop("country", None)
    o.deadline = kw.pop("deadline", None)
    return o


def test_post_tags_full_set():
    tags = post_tags(_opp(degree_levels=["undergrad", "masters"],
                          fields=["Data Science", "Computer Science"],
                          country="Germany", deadline=date(2027, 3, 15)))
    assert tags[:2] == ["#opp42", "#internship"]
    assert "#undergrad" in tags and "#masters" in tags
    assert "#datascience" in tags and "#computerscience" in tags
    assert "#germany" in tags
    assert "#mar2027" in tags


def test_post_tags_youth_and_remote():
    tags = post_tags(_opp(audience="youth", country="Remote (worldwide)"))
    assert "#youth" in tags
    assert "#remote" in tags


def test_tag_slug():
    assert _tag_slug("Data Science") == "datascience"
    assert _tag_slug("Bio-informatics!") == "bioinformatics"


# ---- Telegram channel scraper ----

TG_HTML = """
<html><body>
<div class="tgme_channel_info_header_title">Example AM Company</div>
<div class="tgme_widget_message" data-post="examplecompany/101">
  <div class="tgme_widget_message_text">We are hiring a junior software engineer!
  Requirements: Python, SQL. Apply: <a href="https://example.am/jobs/junior">link</a>
  </div>
  <time datetime="2027-01-05T10:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="examplecompany/102">
  <div class="tgme_widget_message_text">Happy new year to our team! 🎉</div>
</div>
</body></html>
"""


def test_telegram_parse_extracts_vacancy_posts_only():
    items = parse_channel_page(TG_HTML, source_id=1)
    assert len(items) == 1
    item = items[0]
    assert item.url == "https://example.am/jobs/junior"  # external apply link wins
    assert item.extra["tg_post"] == "https://t.me/examplecompany/101"
    assert item.org == "Example AM Company"
    assert "junior software engineer" in item.title.lower()


def test_telegram_url_normalization():
    assert normalize_channel_url("@examplecompany") == "https://t.me/s/examplecompany"
    assert normalize_channel_url("https://t.me/examplecompany") == "https://t.me/s/examplecompany"
    assert normalize_channel_url("https://t.me/s/examplecompany?before=1") == "https://t.me/s/examplecompany"
