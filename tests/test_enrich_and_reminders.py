"""AI enrichment guardrails + reminder/digest scheduling logic."""
from datetime import date

from app.ai.enrich import normalize_enrichment
from app.scheduler.jobs import pick_digest_items, reminder_day_due


# ---- enrichment normalization (never trust model output blindly) ----

def test_enrichment_good_output_normalized():
    out = normalize_enrichment({
        "tldr": "A fully funded 6-month research internship at EMBL for students.",
        "competitiveness": "Highly selective, ~20 spots.",
        "requirements": ["Enrolled BSc/MSc student", "Python experience", "English B2"],
    })
    assert out is not None
    assert out["tldr"].startswith("A fully funded")
    assert len(out["requirements"]) == 3
    assert "generated_at" in out


def test_enrichment_thin_tldr_rejected():
    assert normalize_enrichment({"tldr": "An internship."}) is None
    assert normalize_enrichment({"tldr": ""}) is None
    assert normalize_enrichment({}) is None


def test_enrichment_truncates_and_caps_bullets():
    out = normalize_enrichment({
        "tldr": "x" * 2000,
        "competitiveness": "y" * 1000,
        "requirements": [f"bullet {i}" for i in range(10)],
    })
    assert len(out["tldr"]) == 800
    assert len(out["competitiveness"]) == 300
    assert len(out["requirements"]) == 5


def test_enrichment_skips_empty_bullets():
    out = normalize_enrichment({
        "tldr": "A perfectly reasonable summary of an opportunity for students.",
        "requirements": ["", "  ", "real requirement"],
    })
    assert out["requirements"] == ["real requirement"]


# ---- reminder scheduling ----

def test_reminder_due_at_7_3_1():
    deadline = date(2027, 3, 10)
    assert reminder_day_due(deadline, [], date(2027, 3, 3)) == 7
    assert reminder_day_due(deadline, [], date(2027, 3, 7)) == 3
    assert reminder_day_due(deadline, [], date(2027, 3, 9)) == 1


def test_reminder_not_resent():
    deadline = date(2027, 3, 10)
    assert reminder_day_due(deadline, [7], date(2027, 3, 3)) is None
    assert reminder_day_due(deadline, [7, 3], date(2027, 3, 7)) is None
    assert reminder_day_due(deadline, [7, 3], date(2027, 3, 9)) == 1


def test_reminder_silent_on_other_days():
    deadline = date(2027, 3, 10)
    assert reminder_day_due(deadline, [], date(2027, 3, 5)) is None  # 5 days
    assert reminder_day_due(deadline, [], date(2027, 3, 10)) is None  # deadline day
    assert reminder_day_due(deadline, [], date(2027, 3, 11)) is None  # past


# ---- digest selection ----

class _Opp:
    def __init__(self, deadline, chance):
        self.deadline = deadline
        self.chance_percent = chance


def test_digest_ranks_by_deadline_then_chance():
    opps = [
        _Opp(date(2027, 5, 1), 30),
        _Opp(date(2027, 4, 1), 20),
        _Opp(date(2027, 4, 1), 60),
        _Opp(date(2027, 6, 1), 90),
    ]
    picked = pick_digest_items(opps, limit=3, minimum=3)
    assert [(o.deadline, o.chance_percent) for o in picked] == [
        (date(2027, 4, 1), 60), (date(2027, 4, 1), 20), (date(2027, 5, 1), 30),
    ]


def test_digest_skipped_below_minimum():
    opps = [_Opp(date(2027, 4, 1), 50), _Opp(date(2027, 5, 1), 50)]
    assert pick_digest_items(opps, limit=5, minimum=3) == []
