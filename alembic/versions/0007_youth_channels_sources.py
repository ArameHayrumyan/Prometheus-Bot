"""youth audience + flexible channels (topics, free targets) + Armenian
youth-oriented sources

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# All tagged audience=youth per the curated list's intent; retag any with
# /sourcemeta <id> audience student. kind: official_program_page /
# aggregator / directory (informational tag).
# (name, url, kind, needs_js)
SOURCES = [
    ("ARMACAD - Armenia", "https://armacad.info/country/armenia", "aggregator", False),
    ("AGBU Scholarships", "https://agbu.org/scholarships", "official_program_page", False),
    ("AGBU Programs", "https://agbu.org/programs", "official_program_page", False),
    ("AGBU Scholarship Eligibility", "https://agbu.org/scholarship-eligibility",
     "official_program_page", False),
    ("Armenian Assembly - internships", "https://www.armenian-assembly.org/internship",
     "official_program_page", False),
    ("Armenian Assembly - Intern DC", "https://www.armenian-assembly.org/students/interndc",
     "official_program_page", False),
    ("Armenian Assembly - financial aid directory",
     "https://www.armenian-assembly.org/post/armenian-assembly-releases-updated-financial-aid-directory",
     "directory", False),
    ("ANCA Youth", "https://anca.org/youth/", "official_program_page", False),
    ("ANCA - Armenian American scholarship guide",
     "https://anca.org/armenian-american-scholarship-guide/", "directory", False),
    ("COAF - Youredjian scholarships", "https://www.coaf.org/blog/youredjian-scholarships-2025",
     "official_program_page", False),
    ("COAF - alumni programs", "https://www.coaf.org/programs/education/coaf-alumni-programs",
     "official_program_page", False),
    ("ARISC - grants & fellowships", "https://arisc.org/?cat=59",
     "official_program_page", False),
    ("Birthright Armenia - internship organizations",
     "https://www.birthrightarmenia.org/en/program/internshipOrganizations/20",
     "directory", False),
    ("EU4Armenia - 20 free youth opportunities",
     "https://eu4armenia.eu/dont-miss-out-20-free-opportunities-for-young-people-in-armenia/",
     "directory", False),
    ("Scholarships.plus - Armenia", "https://scholarships.plus/scholarships/all-degrees/armenia/",
     "aggregator", False),
    ("Scholarships.plus", "https://scholarships.plus/", "aggregator", False),
]
# NOTE: the EU4Armenia PDF link is intentionally NOT seeded — the webpage
# scraper parses HTML, not PDF. Its content is covered by the article above.

REPUTATION_PRIORS = [
    ("agbu.org", 0.9), ("armenian-assembly.org", 0.85), ("anca.org", 0.85),
    ("coaf.org", 0.85), ("arisc.org", 0.8), ("birthrightarmenia.org", 0.8),
    ("eu4armenia.eu", 0.8), ("scholarships.plus", 0.5),
]


def upgrade() -> None:
    op.add_column("channels", sa.Column("thread_id", sa.Integer, nullable=True))
    op.add_column("channels", sa.Column("name", sa.String(100), nullable=False,
                                        server_default=""))
    op.add_column("channels", sa.Column("audience", sa.String(10), nullable=False,
                                        server_default="student"))
    op.add_column("opportunities", sa.Column("audience", sa.String(10), nullable=False,
                                             server_default="student"))

    conn = op.get_bind()
    for name, url, kind, needs_js in SOURCES:
        exists = conn.execute(sa.text("SELECT 1 FROM sources WHERE url = :u"),
                              {"u": url}).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO sources (name, source_type, url, category, country, needs_js, active, meta) "
            "VALUES (:n, 'webpage', :u, :c, 'Armenia', :js, true, :m)"
        ), {"n": name, "u": url, "c": kind, "js": needs_js,
            "m": json.dumps({"audience": "youth", "kind": kind})})
    # tag the already-seeded broad youth aggregator
    conn.execute(sa.text(
        "UPDATE sources SET meta = meta || :m WHERE url = 'https://www.youthop.com/'"
    ), {"m": json.dumps({"audience": "youth"})})
    for domain, score in REPUTATION_PRIORS:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO NOTHING"
        ), {"d": domain, "s": score})


def downgrade() -> None:
    conn = op.get_bind()
    for _name, url, *_ in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
    op.drop_column("opportunities", "audience")
    op.drop_column("channels", "audience")
    op.drop_column("channels", "name")
    op.drop_column("channels", "thread_id")
