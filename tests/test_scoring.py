"""Scoring pipeline (§6): legitimacy components, borderline band, chance weights."""
from datetime import date

from app.constants import FundingTier
from app.pipeline.normalize import Extracted
from app.pipeline.scoring import (StudentSnapshot, chance_percent, english_flag,
                                  in_borderline_band, legitimacy_score)

WEIGHTS = {"acceptance": 0.5, "selectivity": 0.2, "requirements": 0.3}


def make_extracted(**kw) -> Extracted:
    base = dict(
        opportunity_type="internship",
        degree_levels=["masters"],
        funding_tier=FundingTier.FULLY_FUNDED,
        duration_days=90,
        fields_matched=["Data Science"],
        has_deliverable=True,
    )
    base.update(kw)
    return Extracted(**base)


def test_legitimacy_high_for_strong_funded_program():
    score = legitimacy_score(make_extracted(), source_reputation=0.9,
                             is_prestige_domain=True)
    assert score >= 80


def test_legitimacy_low_for_short_unknown_unfunded():
    extracted = make_extracted(
        funding_tier=FundingTier.UNKNOWN, duration_days=10, has_deliverable=False,
    )
    score = legitimacy_score(extracted, source_reputation=0.2, is_prestige_domain=False)
    assert score < 40


def test_borderline_band():
    assert in_borderline_band(40, [40, 65])
    assert in_borderline_band(65, [40, 65])
    assert not in_borderline_band(39, [40, 65])
    assert not in_borderline_band(66, [40, 65])


def test_stated_acceptance_rate_dominates():
    extracted = make_extracted(acceptance_rate=8.0)
    chance = chance_percent(extracted, WEIGHTS, 0.9, True)
    assert chance < 30


def test_few_spots_lowers_chance():
    few = chance_percent(make_extracted(spots=5), WEIGHTS, 0.5, False)
    many = chance_percent(make_extracted(spots=200), WEIGHTS, 0.5, False)
    assert few < many


def test_prestige_lowers_chance_vs_niche_source():
    prestige = chance_percent(make_extracted(), WEIGHTS, 0.9, True)
    niche = chance_percent(make_extracted(), WEIGHTS, 0.4, False)
    assert prestige < niche  # low-visibility sources = higher real chance


def test_weights_are_respected():
    extracted = make_extracted(acceptance_rate=90.0)
    all_acceptance = chance_percent(extracted, {"acceptance": 1.0, "selectivity": 0.0,
                                                "requirements": 0.0}, 0.5, False)
    assert all_acceptance == 90


def test_requirement_match_personalizes_chance():
    extracted = make_extracted(degree_levels=["phd"])
    matching = StudentSnapshot(degree_level="phd", fields=["Data Science"])
    mismatched = StudentSnapshot(degree_level="undergrad", fields=["Engineering"])
    assert (chance_percent(extracted, WEIGHTS, 0.5, False, matching)
            > chance_percent(extracted, WEIGHTS, 0.5, False, mismatched))


def test_english_flag_below():
    extracted = make_extracted(english_req_test="IELTS", english_req_score=7.0)
    student = StudentSnapshot(english_test="IELTS", english_score=6.0,
                              english_expiry=date(2030, 1, 1))
    assert english_flag(extracted, student) == "below"


def test_english_flag_expired_before_deadline():
    extracted = make_extracted(english_req_test="IELTS", english_req_score=6.0,
                               deadline=date(2027, 6, 1))
    student = StudentSnapshot(english_test="IELTS", english_score=7.5,
                              english_expiry=date(2027, 1, 1))
    assert english_flag(extracted, student) == "expired"


def test_english_flag_ok_cross_test_conversion():
    # student has TOEFL 100, requirement IELTS 7.0 (~TOEFL 94) -> ok
    extracted = make_extracted(english_req_test="IELTS", english_req_score=7.0,
                               deadline=date(2027, 6, 1))
    student = StudentSnapshot(english_test="TOEFL", english_score=100,
                              english_expiry=date(2028, 1, 1))
    assert english_flag(extracted, student) is None
