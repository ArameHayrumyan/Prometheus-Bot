"""The hard eligibility gate (§4) — applied before scoring, pure & testable.

Every candidate must pass ALL rules:
  1. funding    — STUDENT_PAYS is rejected outright, no exceptions
  2. eligibility— explicit non-Armenian restriction is rejected;
                  UNCERTAIN is flagged (not discarded) and routed to admins
  3. field      — must match the configurable taxonomy
  4. not-noise  — the single most important filter: too-short or
                  vague-summit/networking-only programs with no deliverable
"""
from dataclasses import dataclass

from app.constants import Eligibility, FundingTier
from app.pipeline.normalize import Extracted


@dataclass
class GateResult:
    passed: bool
    discard_reason: str | None = None
    uncertain_eligibility: bool = False


def evaluate(extracted: Extracted, min_duration_days: int,
             youth: bool = False) -> GateResult:
    """youth=True relaxes rules 3-4 for youth-audience sources: camps,
    olympiads and school programs are short, summit-flavored and rarely
    match adult STEM keywords — the funding and eligibility rules stay
    absolute."""
    # Rule 1 — funding coverage (never relaxed)
    if extracted.funding_tier == FundingTier.STUDENT_PAYS:
        return GateResult(False, "funding: student pays tuition/program fees")

    # Rule 2 — Armenian eligibility (never relaxed)
    if extracted.armenian_eligibility == Eligibility.INELIGIBLE:
        return GateResult(False, "eligibility: restricted country list excludes Armenia")
    uncertain = extracted.armenian_eligibility == Eligibility.UNCERTAIN

    # Rule 3 — field relevance (skipped for youth sources)
    if not youth and not extracted.fields_matched:
        return GateResult(False, "field: no match against taxonomy")

    # Rule 4 — noise filter (youth: 2-day floor instead of the configured one)
    effective_min = 2 if youth else min_duration_days
    if extracted.duration_days is not None and extracted.duration_days < effective_min:
        return GateResult(
            False,
            f"noise: duration {extracted.duration_days}d < minimum {effective_min}d",
        )
    if extracted.noise_hits and not extracted.has_deliverable:
        return GateResult(
            False,
            "noise: matched noise keywords ({}) with no concrete deliverable".format(
                ", ".join(extracted.noise_hits[:3])
            ),
        )

    return GateResult(True, uncertain_eligibility=uncertain)
