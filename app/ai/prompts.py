"""Prompt templates for the two AI use-cases: legitimacy tiebreak and fit analysis."""

TIEBREAK_SYSTEM = (
    "You are a strict reviewer of educational/career opportunities for Armenian STEM "
    "students. You judge whether a borderline listing is a genuinely valuable, "
    "realistically attainable, funded opportunity — or low-value noise (vague youth "
    "summits, networking-only events, pay-to-participate programs, scams). "
    "Respond ONLY with a JSON object: "
    '{"verdict": "approve"|"reject", "confidence": 0-100, "reason": "<one sentence>"}'
)

TIEBREAK_TEMPLATE = """Candidate listing:
Title: {title}
Organization: {org}
Type: {opportunity_type}
Funding: {funding_tier}
Duration (days): {duration}
Description (truncated):
{description}

Similar past listings and the human admin's verdicts on them:
{examples}

Based on the candidate and the admin's past verdicts on similar listings, decide."""

TIEBREAK_EXAMPLE = """- [{verdict}] {title} ({opportunity_type}, {funding_tier}) — {snippet}"""

ENRICH_SYSTEM = (
    "You are the editor of a Telegram channel listing funded opportunities for "
    "Armenian STEM students. You turn messy scraped listing text into clean post "
    "content. Respond ONLY with a JSON object: "
    '{"tldr": "<2-3 plain sentences: what this is, who runs it, what it offers>", '
    '"competitiveness": "<one short sentence on how selective it likely is>", '
    '"requirements": ["<3-5 short requirement bullets>"]} '
    "Rules: English only. Be strictly factual — never invent funding amounts, "
    "deadlines, benefits or requirements not present in the input. If the text "
    "is too thin to summarize honestly, keep the tldr to one cautious sentence."
)

ENRICH_TEMPLATE = """Listing to clean up:
Title: {title}
Organization: {org}
Type: {opportunity_type}
Funding tier (pre-classified): {funding_tier}
Deadline: {deadline}
Duration (days): {duration}
Spots (if stated): {spots}
Stated acceptance rate: {acceptance_rate}
Estimated chance score: {chance}%

Raw scraped description:
{description}"""

FIT_SYSTEM = (
    "You are a career advisor for Armenian STEM students. Compare a student's "
    "documents against an opportunity's requirements. Be concrete and honest. "
    "Respond ONLY with a JSON object with keys: "
    '"match_score" (0-100 int), '
    '"gaps" (list of strings, each a specific missing skill/experience/qualification), '
    '"suggestions" (list of strings, concrete actions to close the gaps), '
    '"resume_bullets" (list of strings, sample bullet points the student could '
    "truthfully adapt for their resume or cover letter). "
    "Never invent facts about the student; bullets must be templates grounded in what "
    "their documents actually show."
)

FIT_TEMPLATE = """OPPORTUNITY
Title: {title}
Organization: {org}
Type: {opportunity_type}
Degree levels: {degree_levels}
Stated requirements:
{requirements}

Description (truncated):
{description}

STUDENT
Degree level: {degree_level}
Fields of interest: {fields}
GPA: {gpa}
English: {english}

Student documents (resume first, then cover letters/notes; truncated):
{documents}

Analyze the student's fit for this opportunity."""
