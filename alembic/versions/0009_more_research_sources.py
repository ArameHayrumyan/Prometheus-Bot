"""deep-research batch 2 (deduped): Armenian job boards + labs, HSE, A*STAR

5 of the 10 submitted rows were already seeded in 0008 (ABI, Iowa IHG,
Nanjing, UChicago CCRF, staff.am). Two single-posting URLs were replaced by
their durable parent job boards (anq.am, aijobs.net) so the sources keep
yielding after the specific vacancies close.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-08
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# (name, url, category, country, needs_js, meta)
SOURCES = [
    ("ANQ.am job board (Armenia)", "https://anq.am/en/jobs",
     "internship", "Armenia", True,
     {"gpa_required": "unknown",
      "note": "seeded instead of a single NVIDIA-Yerevan posting UUID"}),
    ("aijobs.net - AI/ML job board", "https://aijobs.net/",
     "internship", None, False,
     {"gpa_required": "unknown",
      "note": "seeded instead of a single Deep Origin posting; title filter "
              "catches intern/junior roles"}),
    ("YerevaNN - ML research lab", "https://yerevann.com/about/",
     "lab", "Armenia", False,
     {"gpa_required": "unknown", "note": "student research projects"}),
    ("HSE CS faculty - internships", "https://cs.hse.ru/en/internships/",
     "lab", "Russia", False, {"gpa_required": "yes"}),
    ("A*STAR GIS computational biology internships (via jglab)",
     "https://jglab.org/2021/07/01/research-internships-in-singapore-2019-2020/",
     "lab", "Singapore", False,
     {"gpa_required": "yes",
      "note": "stale blog directory (2019-2020) — links may be outdated; "
              "verify per listing"}),
]

REPUTATION_PRIORS = [
    ("anq.am", 0.6), ("aijobs.net", 0.6), ("yerevann.com", 0.85),
    ("cs.hse.ru", 0.85), ("jglab.org", 0.5),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, url, category, country, needs_js, meta in SOURCES:
        exists = conn.execute(sa.text("SELECT 1 FROM sources WHERE url = :u"),
                              {"u": url}).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO sources (name, source_type, url, category, country, needs_js, active, meta) "
            "VALUES (:n, 'webpage', :u, :c, :co, :js, true, :m)"
        ), {"n": name, "u": url, "c": category, "co": country,
            "js": needs_js, "m": json.dumps(meta)})
    for domain, score in REPUTATION_PRIORS:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO NOTHING"
        ), {"d": domain, "s": score})


def downgrade() -> None:
    conn = op.get_bind()
    for _name, url, *_ in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
