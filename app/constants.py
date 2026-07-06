"""Shared string-enums (stored as plain strings in the DB)."""
from enum import StrEnum


class OpportunityType(StrEnum):
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    TRAINING = "training"
    JOB = "job"
    HACKATHON = "hackathon"


class FundingTier(StrEnum):
    FULLY_FUNDED = "FULLY_FUNDED"
    MOSTLY_FUNDED_ACCEPTABLE = "MOSTLY_FUNDED_ACCEPTABLE"
    STUDENT_PAYS = "STUDENT_PAYS"
    UNKNOWN = "UNKNOWN"


class Eligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNCERTAIN = "UNCERTAIN"


class OppStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ARCHIVED = "ARCHIVED"  # admin's "review later" shelf
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    DISCARDED = "DISCARDED"
    EXPIRED = "EXPIRED"


class SourceType(StrEnum):
    WEBPAGE = "webpage"
    RSS = "rss"
    EMAIL = "email"
    COMMUNITY = "community"
    LINKEDIN = "linkedin"


DEGREE_LEVELS = ("undergrad", "masters", "phd")

# IELTS -> approximate TOEFL iBT equivalence, used to compare mixed requirements
IELTS_TO_TOEFL = {5.0: 35, 5.5: 46, 6.0: 60, 6.5: 79, 7.0: 94, 7.5: 102, 8.0: 110, 8.5: 115, 9.0: 118}


def english_to_toefl(test: str | None, score: float | None) -> float | None:
    """Normalize an English score to the TOEFL iBT scale for comparison."""
    if test is None or score is None:
        return None
    test = test.upper()
    if test == "TOEFL":
        return float(score)
    if test == "IELTS":
        # round down to nearest listed band
        bands = sorted(IELTS_TO_TOEFL)
        best = bands[0]
        for b in bands:
            if score >= b:
                best = b
        return float(IELTS_TO_TOEFL[best])
    return None
