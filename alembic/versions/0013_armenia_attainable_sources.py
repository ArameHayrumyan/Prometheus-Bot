"""Armenia-attainable internships/trainings: local companies, banks, gov,
EU/UN, tuition-free schools, plus the EPAM training Telegram channel.

Triage: seeded durable LISTING/portal pages; dropped single-posting URLs
(Grid Dynamics /vacancy/N, Adobe /job/R…, Wolfram startup.jobs, TeamViewer
/jobs/N, GIZ careercenter job_id, UNDP cj_view_job ids) — they 404 when
filled and are covered by the listing pages / staff.am / careercenter.am.
FB + IG handles are NOT seedable (see response) — use /ingest for those.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# (name, source_type, url, country, needs_js)
SOURCES = [
    ("Grid Dynamics - Armenia internship portal", "webpage",
     "https://portal.griddynamics.net/internship/armenia", "Armenia", False),
    ("Deep Origin - careers (Yerevan R&D)", "webpage",
     "https://deeporigin.com/careers", "Armenia", True),
    ("Ameriabank - Ameria Generation (student)", "webpage",
     "https://ameriabank.am/en/career/student", "Armenia", False),
    ("Acba Bank - trainee/internship", "webpage",
     "https://www.acba.am/en/trainee", "Armenia", False),
    ("RA Ministry of High-Tech - Internship in Practice", "webpage",
     "https://hightech.gov.am/en/projects/annual/internship-in-practice", "Armenia", False),
    ("EPAM Campus - training catalog (Armenia)", "webpage",
     "https://campus.epam.com/en/training/5342", "Armenia", True),
    ("TUMO Labs - guided self-learning", "webpage",
     "https://tumolabs.am/en/guided-self-learning/", "Armenia", False),
    ("FAST - Generation AI school program", "webpage",
     "https://fast.foundation/en/program/4379", "Armenia", False),
    ("EU Delegation to Armenia - funded traineeships", "webpage",
     "https://www.eeas.europa.eu/eeas/funded-traineeships-young-graduates-eu-delegation-armenia-various-sections_und_en",
     "Armenia", False),
    ("UNTalent - internships in Armenia", "webpage",
     "https://untalent.org/jobs/in-anything/contract-internship/armenia", "Armenia", False),
    ("careercenter.am - jobs (Armenia NGO/dev)", "webpage",
     "https://careercenter.am/en/jobs", "Armenia", False),
    # Telegram: EPAM's regional training + internship announcements
    ("EPAM Training Center (Telegram)", "telegram",
     "https://t.me/epamtrainingcenter", "Armenia", False),
]

REPUTATION_PRIORS = [
    ("portal.griddynamics.net", 0.75), ("griddynamics.com", 0.75),
    ("deeporigin.com", 0.7), ("ameriabank.am", 0.75), ("acba.am", 0.7),
    ("hightech.gov.am", 0.85), ("campus.epam.com", 0.8),
    ("eeas.europa.eu", 0.9), ("untalent.org", 0.6), ("careercenter.am", 0.7),
    ("t.me", 0.6),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, stype, url, country, needs_js in SOURCES:
        exists = conn.execute(sa.text("SELECT 1 FROM sources WHERE url = :u"),
                              {"u": url}).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO sources (name, source_type, url, category, country, needs_js, active, meta) "
            "VALUES (:n, :t, :u, 'company', :co, :js, true, :m)"
        ), {"n": name, "t": stype, "u": url, "co": country, "js": needs_js,
            "m": json.dumps({"tier": "local_attainable"})})
    for domain, score in REPUTATION_PRIORS:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO NOTHING"
        ), {"d": domain, "s": score})


def downgrade() -> None:
    conn = op.get_bind()
    for _n, _t, url, *_ in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
