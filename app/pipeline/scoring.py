"""Scoring (§6): rule-based legitimacy/quality score + weighted chance estimate.

Pure functions; weights/band come from app_settings so they are live-tunable.
"""
from dataclasses import dataclass
from datetime import date

from app.constants import FundingTier, english_to_toefl
from app.pipeline.normalize import Extracted

# ------------------------------------------------------------- legitimacy ---


def legitimacy_score(extracted: Extracted, source_reputation: float,
                     is_prestige_domain: bool, youth: bool = False) -> int:
    """0..100 rule-based quality/legitimacy score.

    Components: duration (0-25), funding tier (0-30),
    org legitimacy from the reputation table (0-25), deliverable (0-20).
    youth=True uses camp-scale duration thresholds — otherwise the relaxed
    hard gate would admit short youth programs only for this score to
    silently discard them again (contradicting rules).
    """
    score = 0
    # duration (youth: camps/olympiads are structurally short)
    d = extracted.duration_days
    long_t, mid_t = (14, 5) if youth else (60, 21)
    if d is None:
        score += 12  # unknown: neutral-ish
    elif d >= long_t:
        score += 25
    elif d >= mid_t:
        score += 15
    else:
        score += 5
    # funding
    if extracted.funding_tier == FundingTier.FULLY_FUNDED:
        score += 30
    elif extracted.funding_tier == FundingTier.MOSTLY_FUNDED_ACCEPTABLE:
        score += 18
    else:  # UNKNOWN
        score += 8
    # organizational legitimacy
    rep = max(source_reputation, 0.85 if is_prestige_domain else source_reputation)
    score += round(rep * 25)
    # concrete deliverable
    if extracted.has_deliverable:
        score += 20
    return min(score, 100)


def in_borderline_band(score: int, band: list[int]) -> bool:
    return band[0] <= score <= band[1]


# ----------------------------------------------------------------- chance ---


def acceptance_subscore(extracted: Extracted) -> float:
    """0..100 from stated acceptance rate, else from stated spots, else neutral."""
    if extracted.acceptance_rate is not None:
        return max(1.0, min(extracted.acceptance_rate, 100.0))
    if extracted.spots is not None:
        if extracted.spots >= 100:
            return 60.0
        if extracted.spots >= 30:
            return 45.0
        if extracted.spots >= 10:
            return 30.0
        return 15.0
    return 35.0  # unknown


def selectivity_subscore(is_prestige_domain: bool, source_reputation: float) -> float:
    """0..100 — prestigious brands attract huge applicant pools -> lower chance;
    obscure-but-legit sources are exactly where the real chance is higher."""
    if is_prestige_domain:
        return 20.0
    # unknown/low-visibility source: fewer applicants competing
    if source_reputation <= 0.6:
        return 70.0
    return 45.0


@dataclass
class StudentSnapshot:
    degree_level: str | None = None
    fields: list[str] | None = None
    gpa: float | None = None
    english_test: str | None = None
    english_score: float | None = None
    english_expiry: date | None = None


def requirements_subscore(extracted: Extracted, student: StudentSnapshot | None) -> float:
    """0..100 hard-requirement match. Neutral 50 when no profile is available
    (channel posts show the generic chance; the personal one appears in the
    detail/fit views)."""
    if student is None:
        return 50.0
    score = 50.0
    if student.degree_level and extracted.degree_levels:
        score += 20.0 if student.degree_level in extracted.degree_levels else -30.0
    if student.fields and extracted.fields_matched:
        score += 15.0 if set(student.fields) & set(extracted.fields_matched) else -15.0
    if extracted.english_req_score is not None:
        req = english_to_toefl(extracted.english_req_test, extracted.english_req_score)
        have = english_to_toefl(student.english_test, student.english_score)
        expired = (
            student.english_expiry is not None
            and extracted.deadline is not None
            and student.english_expiry < extracted.deadline
        )
        if have is None or expired or (req is not None and have < req):
            score -= 25.0
        else:
            score += 15.0
    return max(1.0, min(score, 100.0))


def chance_percent(extracted: Extracted, weights: dict[str, float],
                   source_reputation: float, is_prestige_domain: bool,
                   student: StudentSnapshot | None = None) -> int:
    total_w = sum(weights.values()) or 1.0
    value = (
        weights.get("acceptance", 0.5) * acceptance_subscore(extracted)
        + weights.get("selectivity", 0.2) * selectivity_subscore(is_prestige_domain, source_reputation)
        + weights.get("requirements", 0.3) * requirements_subscore(extracted, student)
    ) / total_w
    return int(round(max(1.0, min(value, 99.0))))


def english_flag(extracted: Extracted, student: StudentSnapshot) -> str | None:
    """Return 'below' | 'expired' | None — surfaced in UI, never silently filtered."""
    if extracted.english_req_score is None:
        return None
    req = english_to_toefl(extracted.english_req_test, extracted.english_req_score)
    have = english_to_toefl(student.english_test, student.english_score)
    if (student.english_expiry is not None and extracted.deadline is not None
            and student.english_expiry < extracted.deadline):
        return "expired"
    if have is None or (req is not None and have < req):
        return "below"
    return None
