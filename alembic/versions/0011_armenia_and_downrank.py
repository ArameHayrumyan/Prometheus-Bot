"""Armenian company market (staff.am general) + down-rank the mega remote
boards so they stop dominating and flooding the student's queue.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# staff.am aggregates virtually every Armenian tech company's openings
# (incl. internships) — one reliable source covering the whole local market,
# which is exactly the low-competition, Armenia-relevant tier. The pipeline's
# field + title filters keep the relevant roles.
SOURCES = [
    ("staff.am - all IT jobs (Armenia)", "https://staff.am/en/jobs",
     "company", "Armenia", True, {"max_items": 25}),
    ("staff.am - internships (Armenia)", "https://staff.am/en/jobs?type=6",
     "company", "Armenia", True, {"max_items": 25}),
    ("myjob.am (Armenia)", "https://www.myjob.am/en/jobs/", "company", "Armenia", False, {}),
]

# lower reputation -> lower legitimacy score -> the flood of high-competition
# remote-board listings mostly falls to borderline/discard instead of filling
# the queue. Combined with the per-source cap (max_items_per_source).
DOWNRANK = [
    ("remoteok.com", 0.30),
    ("weworkremotely.com", 0.30),
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
    for domain, score in DOWNRANK:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO UPDATE SET score = :s"
        ), {"d": domain, "s": score})
    # also cap the two mega RSS boards per-source in their meta
    for url in ("https://remoteok.com/remote-dev-jobs.rss",
                "https://weworkremotely.com/remote-jobs.rss",
                "https://weworkremotely.com/categories/remote-programming-jobs.rss"):
        conn.execute(sa.text(
            "UPDATE sources SET meta = meta || :m WHERE url = :u"
        ), {"m": json.dumps({"max_items": 6}), "u": url})


def downgrade() -> None:
    conn = op.get_bind()
    for _n, url, *_ in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
