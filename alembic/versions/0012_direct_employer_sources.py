"""direct-employer career pages (remote-first / globally-hiring companies) —
lower competition than mega-boards, genuinely accessible from Armenia.

Triage of the researched list:
  kept: real listing pages that hire remote/EMEA/global.
  dropped: JPMorgan/TikTok/ByteDance/Tesla — single-posting or search-ID
    URLs (break when filled) and/or US-work-authorization-only (the
    eligibility gate would discard them, wasting cycles). Taskintern —
    unverified legitimacy.
  fixed: Leaning Technologies pointed at one job posting -> its board.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# (name, url, country, needs_js)  — all category "company", meta tier=direct
SOURCES = [
    ("Automattic careers (remote, global)", "https://automattic.com/work-with-us/jobs/", "Remote", True),
    ("Zapier careers (Ashby, EMEA remote)", "https://jobs.ashbyhq.com/zapier", "Remote", True),
    ("Canonical careers (remote-first, 40+ countries)", "https://canonical.com/careers/all", "Remote", True),
    ("GitLab jobs (all-remote)", "https://about.gitlab.com/jobs/all-jobs/", "Remote", True),
    ("Hotjar careers (EMEA remote)", "https://www.hotjar.com/careers/", "Remote", True),
    ("Revolut engineering careers", "https://www.revolut.com/careers/", "EU", True),
    ("Wise early-careers programs", "https://wise.jobs/wisestart-programs", "UK", False),
    ("DataCamp careers (remote, data)", "https://www.datacamp.com/careers", "Remote", True),
    ("X-Team careers (remote worldwide)", "https://x-team.com/careers", "Remote", False),
    ("Leaning Technologies jobs (Freshteam)", "https://leaningtech.freshteam.com/jobs", "Remote", True),
    ("Dropbox emerging talent (internships)", "https://www.dropbox.jobs/en/emerging-talent", "USA", True),
]

REPUTATION_PRIORS = [
    ("automattic.com", 0.8), ("ashbyhq.com", 0.7), ("jobs.ashbyhq.com", 0.7),
    ("canonical.com", 0.85), ("gitlab.com", 0.85), ("about.gitlab.com", 0.85),
    ("hotjar.com", 0.7), ("revolut.com", 0.8), ("wise.jobs", 0.8), ("wise.com", 0.8),
    ("datacamp.com", 0.75), ("x-team.com", 0.6), ("dropbox.com", 0.8),
    ("dropbox.jobs", 0.8), ("leaningtech.freshteam.com", 0.6),
    # ATS hosts (extracted job links land here) so they aren't default-penalised
    ("boards.greenhouse.io", 0.7), ("job-boards.greenhouse.io", 0.7),
    ("jobs.lever.co", 0.7),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, url, country, needs_js in SOURCES:
        exists = conn.execute(sa.text("SELECT 1 FROM sources WHERE url = :u"),
                              {"u": url}).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO sources (name, source_type, url, category, country, needs_js, active, meta) "
            "VALUES (:n, 'webpage', :u, 'company', :co, :js, true, :m)"
        ), {"n": name, "u": url, "co": country, "js": needs_js,
            "m": json.dumps({"tier": "direct_employer"})})
    for domain, score in REPUTATION_PRIORS:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO NOTHING"
        ), {"d": domain, "s": score})


def downgrade() -> None:
    conn = op.get_bind()
    for _n, url, *_ in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
