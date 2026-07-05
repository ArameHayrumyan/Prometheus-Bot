"""Hard gate (§4): funding, Armenian eligibility, field relevance, noise."""
from app.constants import Eligibility, FundingTier
from app.db.settings_service import DEFAULTS
from app.pipeline import hard_gate
from app.pipeline.normalize import extract_all

TAXONOMY = {
    "Computer Science": ["computer science", "software", "programming"],
    "Data Science": ["data science", "machine learning", "artificial intelligence"],
    "Bioinformatics": ["bioinformatics", "computational biology", "genomics"],
    "Engineering": ["engineering", "robotics"],
}
NOISE = DEFAULTS["noise_keywords"]
DELIVER = DEFAULTS["deliverable_keywords"]
MIN_DURATION = 15


def run(title: str, text: str) -> tuple:
    extracted = extract_all(title, text, TAXONOMY, NOISE, DELIVER)
    return extracted, hard_gate.evaluate(extracted, MIN_DURATION)


def test_student_pays_rejected_always():
    _, gate = run(
        "Data Science Summer School",
        "Join our 8-week data science program in Berlin. Program fee: $2,500. "
        "Open to all nationalities. Certificate provided.",
    )
    assert not gate.passed
    assert "funding" in gate.discard_reason


def test_fully_funded_wording_beats_incidental_cost_mentions():
    extracted, gate = run(
        "Fully funded ML research internship",
        "This fully-funded machine learning internship includes a monthly stipend. "
        "Open to all nationalities. 3 months in the lab, research project deliverable.",
    )
    assert extracted.funding_tier == FundingTier.FULLY_FUNDED
    assert gate.passed


def test_restricted_country_list_without_armenia_rejected():
    _, gate = run(
        "Software Engineering Scholarship",
        "Full scholarship for a software engineering degree with stipend. "
        "Only open to citizens of Kenya, Nigeria, and Ghana.",
    )
    assert not gate.passed
    assert "eligibility" in gate.discard_reason


def test_restricted_list_including_armenia_passes():
    extracted, gate = run(
        "Eastern Partnership Data Science Fellowship",
        "Fully funded data science fellowship with monthly stipend for citizens of "
        "Eastern Partnership countries including Armenia. Duration: 6 months. "
        "Research project and publication expected.",
    )
    assert extracted.armenian_eligibility == Eligibility.ELIGIBLE
    assert gate.passed
    assert not gate.uncertain_eligibility


def test_ambiguous_eligibility_flagged_not_discarded():
    extracted, gate = run(
        "Machine Learning Internship",
        "Paid machine learning internship with salary, 12 weeks, work on a real "
        "research project with mentorship program.",
    )
    assert extracted.armenian_eligibility == Eligibility.UNCERTAIN
    assert gate.passed  # goes to admin queue…
    assert gate.uncertain_eligibility  # …with the flag visible


def test_us_work_authorization_restriction_rejected():
    _, gate = run(
        "Junior Software Engineer",
        "Entry-level software engineering job, salary $90k. "
        "Applicants must have right to work in the US.",
    )
    assert not gate.passed


def test_irrelevant_field_rejected():
    _, gate = run(
        "Fully funded culinary arts fellowship",
        "Fully funded fellowship in French pastry with monthly stipend, "
        "open to all nationalities, 6 months, diploma awarded.",
    )
    assert not gate.passed
    assert "field" in gate.discard_reason


def test_too_short_program_rejected():
    _, gate = run(
        "AI weekend bootcamp",
        "Fully funded 3 day artificial intelligence bootcamp, open to all "
        "nationalities, certificate provided.",
    )
    assert not gate.passed
    assert "duration" in gate.discard_reason or "noise" in gate.discard_reason


def test_vague_youth_summit_without_deliverable_rejected():
    _, gate = run(
        "Global Youth Leadership Summit on Technology",
        "A fully funded youth summit bringing together young leaders in software "
        "and artificial intelligence for inspiring networking. Open to all "
        "nationalities. 4 weeks of connection and exchange.",
    )
    assert not gate.passed
    assert "noise" in gate.discard_reason


def test_summit_with_concrete_deliverable_passes():
    _, gate = run(
        "AI Research Summit & School",
        "Fully funded youth summit and research school on machine learning with "
        "stipend, structured curriculum and a final research project publication. "
        "Open to all nationalities. 4 weeks.",
    )
    assert gate.passed


def test_good_opportunity_passes_everything():
    extracted, gate = run(
        "Fully funded bioinformatics PhD studentship",
        "Fully funded PhD studentship in bioinformatics and computational biology "
        "at a leading genomics institute. Monthly stipend and tuition waiver. "
        "Open to all nationalities. Deadline: March 15, 2027. Duration: 4 years. "
        "Requirements: MSc in a related field, IELTS 6.5.",
    )
    assert gate.passed
    assert extracted.funding_tier == FundingTier.FULLY_FUNDED
    assert extracted.armenian_eligibility == Eligibility.ELIGIBLE
    assert "phd" in extracted.degree_levels
    assert extracted.english_req_test == "IELTS"
    assert extracted.english_req_score == 6.5
    assert extracted.deadline is not None and extracted.deadline.year == 2027
