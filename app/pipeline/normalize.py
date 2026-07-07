"""Rule-based extraction of structured fields from raw scraped text.

Pure functions over strings — no DB, no network — so the hard gate and
scoring stay unit-testable. AI is deliberately NOT used here (quota).
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from dateutil import parser as dateparser

from app.constants import Eligibility, FundingTier, OpportunityType

# ---------------------------------------------------------------- funding ---

FULLY_FUNDED_PATTERNS = [
    r"fully[\s-]funded", r"full scholarship", r"full funding", r"all expenses (paid|covered)",
    r"tuition (waiver|waived|covered|free)", r"free of charge", r"no (tuition|program|participation) fee",
    r"stipend", r"salary", r"paid (internship|position|role|traineeship)", r"remunerat",
    r"monthly allowance", r"fellowship award", r"living allowance", r"costs? (are|is|fully) covered",
]
MOSTLY_FUNDED_PATTERNS = [
    r"(participant|student)s? (only )?(pay|cover)s? (their )?(own )?(travel|visa|flight)",
    r"accommodation (and meals )?(is |are )?(provided|covered)",
    r"travel (costs? )?(not|isn't|is not) covered",
    r"partial(ly)? funded", r"partial scholarship", r"tuition[\s-]free",
]
STUDENT_PAYS_PATTERNS = [
    r"tuition fees?:?\s?[\$€£]", r"program(me)? fee", r"participation fee", r"registration fee of",
    r"course fee", r"costs? [\$€£]?\d", r"fee:?\s?[\$€£]\s?\d", r"self[\s-]funded",
    r"(pay|payment) (of|for) (the )?(course|program|tuition)", r"tuition:? [\$€£]?\d",
    r"scholarships? (may be|are) available (to|for) (cover|offset)",  # fee-based w/ maybe-aid
]

# ------------------------------------------------------------- eligibility ---

OPEN_ELIGIBILITY_PATTERNS = [
    r"open to all nationalities", r"applicants? (from|of) (all|any) (countries|nationalit)",
    r"international (students?|applicants?|candidates?) (are )?(welcome|eligible|encouraged)",
    r"worldwide", r"any country", r"all countries", r"global(ly)? eligible", r"no nationality restriction",
    r"open globally", r"citizens of (all|any)",
]
# Region/list phrases that DO include Armenia
ARMENIA_INCLUSIVE_TERMS = [
    "armenia", "eastern partnership", "eap countr", "post-soviet", "former soviet",
    "cis countr", "commonwealth of independent states", "caucasus", "south caucasus",
    "developing countr", "low- and middle-income", "lmic", "oda-eligible", "oda recipient",
    "eastern europe and central asia", "europe and central asia", "council of europe",
    "erasmus\\+ partner countr", "eligible countries list",
]
RESTRICTION_PATTERNS = [
    r"only (open to|for) (citizens|residents|nationals) of ([^.;\n]+)",
    r"(open|available) (only )?to (citizens|nationals|residents) of ([^.;\n]+)",
    r"must be a (citizen|national|permanent resident) of ([^.;\n]+)",
    r"eligible countries?:?\s*([^.;\n]+)",
    r"restricted to ([^.;\n]+) (citizens|nationals)",
    r"applicants? must (hold|have) ([^.;\n]*?)(citizenship|nationality)",
    r"(us|u\.s\.|uk|eu|eea) (citizens?|nationals?|work authorization|persons?) only",
    r"right to work in (the )?(us|u\.s\.|uk|eu|germany|canada|australia)\b",
]

# ------------------------------------------------------------------ types ---

TYPE_PATTERNS: list[tuple[str, str]] = [
    (OpportunityType.INTERNSHIP, r"\bintern(ship)?s?\b|\btraineeship\b|\bsummer (research )?program"),
    (OpportunityType.SCHOLARSHIP, r"\bscholarship"),
    (OpportunityType.FELLOWSHIP, r"\bfellowship|\bgrant(s)?\b|\bstudentship"),
    (OpportunityType.HACKATHON, r"\bhackathon|\bcompetition|\bchallenge\b|\bolympiad|\bdatathon"),
    (OpportunityType.TRAINING, r"\bbootcamp|\btraining (course|program)|\bworkshop series|\bcourse\b"),
    (OpportunityType.JOB, r"\b(junior|entry.level|graduate) (developer|engineer|analyst|scientist|position)"
                          r"|\bnew grad\b|\bhiring\b|\bvacanc|\bjob opening|\bfull.time\b"),
]

DEGREE_PATTERNS: dict[str, str] = {
    "undergrad": r"\bundergrad|\bbachelor|\bbsc\b|\bb\.s\.|\bfirst.year student|\bfreshman|\bsophomore",
    "masters": r"\bmaster'?s?\b|\bmsc\b|\bm\.s\.|\bgraduate student|\bpostgraduate\b",
    "phd": r"\bphd\b|\bdoctora(l|te)|\bdphil\b|\bdoctoral candidate|\bgraduate research",
}

NOISE_DELIVERABLE_HINTS = []  # kept in app_settings (see settings_service.DEFAULTS)

ENGLISH_REQ_PATTERNS = [
    ("IELTS", r"ielts[^0-9]{0,30}(\d(?:\.\d)?)"),
    ("TOEFL", r"toefl[^0-9]{0,30}(\d{2,3})"),
]

DEADLINE_PATTERNS = [
    r"(?:deadline|apply by|applications? (?:close|due)|closing date)[:\s]*"
    r"([A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})",
]

DURATION_PATTERNS = [
    (r"(\d{1,2})\s*[-–]?\s*(?:to\s*)?(\d{1,2})?\s*week", 7),
    (r"(\d{1,2})\s*[-–]?\s*(?:to\s*)?(\d{1,2})?\s*month", 30),
    (r"(\d)\s*[-–]?\s*(?:to\s*)?(\d)?\s*year", 365),
    (r"(\d{1,3})\s*day", 1),
]

SPOTS_PATTERN = re.compile(
    r"(\d{1,4})\s*(?:spots?|places?|positions?|participants? will be selected|"
    r"students? will be selected|awards? (?:are|will be) (?:made|granted)|openings?)",
    re.IGNORECASE,
)
ACCEPTANCE_PATTERN = re.compile(
    r"(?:acceptance|success|selection) rate[^0-9]{0,20}(\d{1,2}(?:\.\d)?)\s?%", re.IGNORECASE
)


@dataclass
class Extracted:
    opportunity_type: str = OpportunityType.JOB
    degree_levels: list[str] = field(default_factory=list)
    funding_tier: str = FundingTier.UNKNOWN
    armenian_eligibility: str = Eligibility.UNCERTAIN
    deadline: date | None = None
    duration_days: int | None = None
    english_req_test: str | None = None
    english_req_score: float | None = None
    spots: int | None = None
    acceptance_rate: float | None = None
    fields_matched: list[str] = field(default_factory=list)
    has_deliverable: bool = False
    noise_hits: list[str] = field(default_factory=list)
    country: str | None = None
    requirements: str = ""


def _search_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_funding(text: str) -> str:
    t = text.lower()
    fully = _search_any(FULLY_FUNDED_PATTERNS, t)
    pays = _search_any(STUDENT_PAYS_PATTERNS, t)
    mostly = _search_any(MOSTLY_FUNDED_PATTERNS, t)
    if pays and not fully:
        return FundingTier.STUDENT_PAYS
    if fully and pays:
        # explicit "fully funded" wins over incidental cost mentions
        return FundingTier.FULLY_FUNDED
    if fully:
        return FundingTier.FULLY_FUNDED
    if mostly:
        return FundingTier.MOSTLY_FUNDED_ACCEPTABLE
    return FundingTier.UNKNOWN


def classify_armenian_eligibility(text: str) -> str:
    t = text.lower()
    if _search_any(OPEN_ELIGIBILITY_PATTERNS, t):
        return Eligibility.ELIGIBLE
    if "armenia" in t:
        # named explicitly (list of eligible countries, or Armenia-based listing)
        return Eligibility.ELIGIBLE
    for pattern in RESTRICTION_PATTERNS:
        m = re.search(pattern, t, re.IGNORECASE)
        if m:
            clause = m.group(0)
            if any(re.search(term, clause) for term in ARMENIA_INCLUSIVE_TERMS):
                return Eligibility.ELIGIBLE
            return Eligibility.INELIGIBLE
    return Eligibility.UNCERTAIN


def classify_type(text: str) -> str:
    t = text.lower()
    for opp_type, pattern in TYPE_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return opp_type
    return OpportunityType.JOB


def detect_degree_levels(text: str, opp_type: str) -> list[str]:
    t = text.lower()
    levels = [lvl for lvl, pat in DEGREE_PATTERNS.items() if re.search(pat, t, re.IGNORECASE)]
    if levels:
        return levels
    # sensible defaults per type when unstated
    if opp_type == OpportunityType.INTERNSHIP:
        return ["undergrad", "masters"]
    if opp_type == OpportunityType.FELLOWSHIP:
        return ["masters", "phd"]
    if opp_type in (OpportunityType.HACKATHON, OpportunityType.TRAINING, OpportunityType.JOB):
        return ["undergrad", "masters", "phd"]
    return ["undergrad", "masters", "phd"]


def extract_deadline(text: str) -> date | None:
    for pattern in DEADLINE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                parsed = dateparser.parse(m.group(1), dayfirst=False, fuzzy=True)
                if parsed:
                    return parsed.date()
            except (ValueError, OverflowError):
                continue
    return None


def extract_duration_days(text: str) -> int | None:
    t = text.lower()
    for pattern, multiplier in DURATION_PATTERNS:
        m = re.search(pattern, t)
        if m:
            try:
                low = int(m.group(1))
                high = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else low
                return max(low, high) * multiplier
            except (ValueError, IndexError):
                continue
    return None


def extract_english_req(text: str) -> tuple[str | None, float | None]:
    t = text.lower()
    for test, pattern in ENGLISH_REQ_PATTERNS:
        m = re.search(pattern, t)
        if m:
            try:
                return test, float(m.group(1))
            except ValueError:
                continue
    return None, None


# Role titles that are NOT target opportunities even when the posting/company
# mentions tech keywords in its boilerplate ("marketing manager at a software
# company" must not match Computer Science).
NON_TECH_TITLE = re.compile(
    r"\b(marketing|sales|business development|account (?:manager|executive)|"
    r"human resources|hr (?:manager|specialist|intern|assistant)|recruit(?:er|ment)|"
    r"communications?|public relations|social media|copywrit\w*|"
    r"content (?:writer|creator|manager|marketing)|community manager|"
    r"office (?:manager|assistant)|administrative|receptionist|"
    r"customer (?:support|success|service)|finance|accounting|accountant|"
    r"legal|paralegal|event (?:manager|coordinator)|fundrais\w*|logistics|"
    r"procurement|business analyst|brand|growth manager|seo )",
    re.IGNORECASE,
)


def match_fields(title: str, body: str, taxonomy: dict[str, list[str]]) -> list[str]:
    """taxonomy: {field_name: [keywords...]} — from the DB-backed table.

    The *title* names the role, so it decides:
      1. a field keyword in the title -> match;
      2. a non-tech role title with no tech keyword -> no match, ever
         (kills marketing/management jobs at tech companies);
      3. otherwise fall back to the body, but only trust keywords that appear
         near the top (first 300 chars, where the role summary lives) or that
         occur as 2+ distinct keywords — a lone keyword buried in company
         boilerplate is not evidence.
    """
    padded_title = " " + title.lower() + " "
    padded_body = " " + body.lower() + " "
    body_head = padded_body[:300]

    title_matched = [name for name, keywords in taxonomy.items()
                     if any(kw in padded_title for kw in keywords)]
    if title_matched:
        return title_matched
    if NON_TECH_TITLE.search(title):
        return []
    matched = []
    for name, keywords in taxonomy.items():
        hits = [kw for kw in keywords if kw in padded_body]
        if len(hits) >= 2 or any(kw in body_head for kw in hits):
            matched.append(name)
    return matched


# Organization-name extraction: title first ("Intern at Broad Institute"),
# then the first lines of the body, where announcements name themselves.
_ORG_TITLE_AT = re.compile(
    r"\bat (?:the )?([A-Z][\w&.'()-]*(?:\s+(?:of|for|and|the|[A-Z&][\w&.'()-]*)){0,5})"
)
_ORG_BODY_PATTERNS = [
    re.compile(r"^\s*(?:the )?([A-Z][\w&.'() -]{2,60}?)\s+(?:is|are)\s+"
               r"(?:seeking|looking|hiring|recruiting|offering|inviting|accepting)",
               re.MULTILINE),
    re.compile(r"(?:company|organi[sz]ation|employer|institution|institute|host(?:ing)? lab)"
               r"\s*[:\-–]\s*([^\n.;|]{2,60})", re.IGNORECASE),
    re.compile(r"\bjoin (?:the )?([A-Z][\w&.'-]+(?:\s+[A-Z&][\w&.'-]+){0,4})"),
]


def extract_org(title: str, text: str) -> str | None:
    m = _ORG_TITLE_AT.search(title)
    if m:
        return m.group(1).strip(" ,.;:-")[:80]
    head = text[:400]
    for pattern in _ORG_BODY_PATTERNS:
        m = pattern.search(head)
        if m:
            org = m.group(1).strip(" ,.;:-")
            if 2 < len(org) <= 80:
                return org
    return None


def find_noise(text: str, noise_keywords: list[str]) -> list[str]:
    t = text.lower()
    return [kw for kw in noise_keywords if kw in t]


def has_deliverable(text: str, deliverable_keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in deliverable_keywords)


def extract_requirements(text: str) -> str:
    """Pull requirement-looking sentences for display + fit analysis."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hits = [
        s.strip() for s in sentences
        if re.search(r"\b(require|must (be|have|hold)|eligib|minimum|at least|"
                     r"applicants? should|qualification|proficien|gpa)\b", s, re.IGNORECASE)
    ]
    return " ".join(hits)[:2000]


def content_hash(url: str, title: str) -> str:
    normalized_url = url.split("?")[0].rstrip("/").lower()
    normalized = f"{normalized_url}|{title.strip().lower()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def extract_all(title: str, text: str, taxonomy: dict[str, list[str]],
                noise_keywords: list[str], deliverable_keywords: list[str]) -> Extracted:
    blob = f"{title}\n{text}"
    opp_type = classify_type(blob)
    eng_test, eng_score = extract_english_req(blob)
    return Extracted(
        opportunity_type=opp_type,
        degree_levels=detect_degree_levels(blob, opp_type),
        funding_tier=classify_funding(blob),
        armenian_eligibility=classify_armenian_eligibility(blob),
        deadline=extract_deadline(blob),
        duration_days=extract_duration_days(blob),
        english_req_test=eng_test,
        english_req_score=eng_score,
        spots=(int(m.group(1)) if (m := SPOTS_PATTERN.search(blob)) else None),
        acceptance_rate=(float(m.group(1)) if (m := ACCEPTANCE_PATTERN.search(blob)) else None),
        fields_matched=match_fields(title, text, taxonomy),
        has_deliverable=has_deliverable(blob, deliverable_keywords),
        noise_hits=find_noise(blob, noise_keywords),
        requirements=extract_requirements(blob),
    )
