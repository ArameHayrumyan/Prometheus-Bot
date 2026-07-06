"""Full detail card for an opportunity (deep-link Details / forwarded posts)."""
import html

from app.constants import english_to_toefl
from app.db.models import Opportunity, User
from app.i18n import t
from app.pipeline.normalize import Extracted
from app.pipeline.scoring import StudentSnapshot, chance_percent, english_flag


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def _snapshot(user: User) -> StudentSnapshot:
    return StudentSnapshot(
        degree_level=user.degree_level_code,
        fields=user.fields or [],
        gpa=user.gpa,
        english_test=user.english_test,
        english_score=user.english_score,
        english_expiry=user.english_expiry,
    )


def _extracted_from_opp(opp: Opportunity) -> Extracted:
    return Extracted(
        opportunity_type=opp.opportunity_type,
        degree_levels=opp.degree_levels or [],
        funding_tier=opp.funding_tier,
        armenian_eligibility=opp.armenian_eligibility,
        deadline=opp.deadline,
        duration_days=opp.duration_days,
        english_req_test=opp.english_req_test,
        english_req_score=opp.english_req_score,
        spots=opp.spots,
        acceptance_rate=opp.acceptance_rate,
        fields_matched=opp.fields or [],
    )


def personal_chance(opp: Opportunity, user: User, weights: dict) -> int:
    return chance_percent(
        _extracted_from_opp(opp), weights,
        source_reputation=0.5, is_prestige_domain=False,
        student=_snapshot(user),
    )


def build_detail_text(opp: Opportunity, user: User, weights: dict) -> str:
    lang = user.language
    lines = [f"<b>{_esc(opp.title)}</b>"]
    if opp.org:
        lines.append(f"🏛 <i>{_esc(opp.org)}</i>")
    lines.append("")
    lines.append(f"{t('detail_type', lang)}: <b>{opp.opportunity_type}</b>")
    lines.append(f"{t('detail_funding', lang)}: <b>{t('funding_' + opp.funding_tier, lang)}</b>")
    deadline = opp.deadline.isoformat() if opp.deadline else t("no_deadline", lang)
    lines.append(f"{t('detail_deadline', lang)}: <b>{deadline}</b>")
    if opp.duration_days:
        lines.append(f"{t('detail_duration', lang)}: ~{opp.duration_days}d")
    if opp.country:
        lines.append(f"{t('detail_country', lang)}: {_esc(opp.country)}")
    if opp.fields:
        lines.append(f"{t('detail_fields', lang)}: {_esc(' · '.join(opp.fields))}")
    if opp.degree_levels:
        lines.append(f"{t('detail_degrees', lang)}: {', '.join(opp.degree_levels)}")
    lines.append("")
    # Armenian eligibility note — always shown explicitly
    lines.append(t("eligibility_" + opp.armenian_eligibility, lang)
                 if opp.armenian_eligibility in ("ELIGIBLE", "UNCERTAIN")
                 else t("eligibility_UNCERTAIN", lang))
    # English requirement vs the student's stored score/expiry (§7 — flagged, not hidden)
    if opp.english_req_score is not None:
        req_str = f"{opp.english_req_test} {opp.english_req_score:g}"
        lines.append(t("english_req", lang, req=req_str))
        if user.english_test and user.english_score is not None:
            flag = english_flag(_extracted_from_opp(opp), _snapshot(user))
            if flag == "expired":
                lines.append(t("english_flag_expired", lang))
            elif flag == "below" or (
                (have := english_to_toefl(user.english_test, user.english_score)) is not None
                and (req := english_to_toefl(opp.english_req_test, opp.english_req_score)) is not None
                and have < req
            ):
                lines.append(t("english_flag_below", lang,
                               test=user.english_test, score=f"{user.english_score:g}"))
            else:
                lines.append(t("english_flag_ok", lang,
                               test=user.english_test, score=f"{user.english_score:g}"))
        else:
            lines.append(t("english_none_on_req", lang))
    if opp.requirements:
        lines.append("")
        lines.append(f"<b>{t('detail_requirements', lang)}</b>")
        lines.append(f"<blockquote expandable>{_esc(opp.requirements[:800])}</blockquote>")
    lines.append("")
    if user.onboarded:
        lines.append(f"{t('detail_chance_personal', lang)}: ~{personal_chance(opp, user, weights)}%")
    else:
        lines.append(f"{t('detail_chance', lang)}: ~{opp.chance_percent}%")
    return "\n".join(lines)[:4096]
