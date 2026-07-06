"""Extraction-quality regressions: field mismatch on non-tech roles,
org extraction, sentence-safe truncation."""
from app.pipeline.normalize import extract_org, match_fields
from app.utils.text import smart_truncate

TAXONOMY = {
    "Computer Science": ["computer science", "software", "programming", "cybersecurity"],
    "Data Science": ["data science", "machine learning", "artificial intelligence", " ai "],
    "Bioinformatics": ["bioinformatics", "computational biology", "genomics"],
    "Engineering": ["engineering", "robotics"],
}


# ---- field matching: the title decides the role ----

def test_marketing_job_at_software_company_rejected():
    # the exact reported failure: tech boilerplate around a non-tech role
    assert match_fields(
        "Marketing Manager",
        "Join our fast-growing software company! We build machine learning "
        "products used worldwide. You will own our marketing campaigns.",
        TAXONOMY,
    ) == []


def test_business_development_with_ai_buzzwords_rejected():
    assert match_fields(
        "Business Development Intern",
        "Our artificial intelligence startup is scaling. Help us grow revenue "
        "through partnerships and outreach.",
        TAXONOMY,
    ) == []


def test_hr_and_sales_titles_rejected():
    for title in ("HR Intern", "Sales Executive", "Content Writer",
                  "Customer Success Manager", "Account Manager"):
        assert match_fields(title, "software software programming", TAXONOMY) == [], title


def test_tech_title_wins_even_with_business_text():
    assert "Computer Science" in match_fields(
        "Software Engineering Intern",
        "You'll work with our sales and marketing teams to deliver value.",
        TAXONOMY,
    )


def test_neutral_title_matches_when_keyword_in_body_head():
    # role summary near the top of the body counts
    assert "Data Science" in match_fields(
        "Summer Internship Programme 2027",
        "This machine learning internship places students in research labs.",
        TAXONOMY,
    )


def test_neutral_title_single_buried_keyword_not_enough():
    body = ("Our institute welcomes students every summer. " * 12
            + "The campus also hosts a software museum.")
    assert match_fields("Summer Internship Programme 2027", body, TAXONOMY) == []


def test_neutral_title_two_distinct_keywords_match():
    body = ("Fellows join projects across our departments. " * 10
            + "Topics include bioinformatics pipelines and genomics analysis.")
    assert "Bioinformatics" in match_fields("Research Fellowship", body, TAXONOMY)


# ---- org extraction ----

def test_org_from_title_at_pattern():
    assert extract_org("Data Science Intern at Broad Institute", "") == "Broad Institute"


def test_org_from_body_is_seeking():
    org = extract_org(
        "Bioinformatics internship",
        "Wellcome Sanger Institute is seeking motivated students for its "
        "summer programme.",
    )
    assert org == "Wellcome Sanger Institute"


def test_org_from_labelled_field():
    assert extract_org("Internship", "Organization: EMBL Heidelberg\nDuration: 3 months") \
        == "EMBL Heidelberg"


def test_org_none_when_absent():
    assert extract_org("Junior developer wanted", "great team, apply now") is None


# ---- smart truncation ----

def test_truncate_prefers_sentence_boundary():
    text = "First sentence here. Second sentence is longer. Third one gets dropped entirely."
    out = smart_truncate(text, 55)
    assert out.endswith(".")
    assert "Third" not in out
    assert out == "First sentence here. Second sentence is longer."


def test_truncate_never_cuts_mid_word():
    text = "word " * 50
    out = smart_truncate(text, 23)
    assert out.endswith("…")
    assert "wor…" not in out and "wo…" not in out


def test_truncate_short_text_untouched():
    assert smart_truncate("short text.", 100) == "short text."
