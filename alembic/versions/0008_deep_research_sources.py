"""deep-research batch: labs, research programs, internships, trainings
(Perplexity-verified, 2026-07) — incl. Armenian locals (ABI, staff.am) and
lower-competition regions (Bulgaria, China, Austria, Canada)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# (name, url, category, country, needs_js, meta)
SOURCES = [
    # --- Armenian locals ---
    ("Armenian Bioinformatics Institute - open positions",
     "https://oldsite.abi.am/about-us/open-positions/", "lab", "Armenia", False,
     {"gpa_required": "unknown"}),
    ("ABI - Vine bioinformatics internship (Binder Lab)",
     "https://www.abi.am/careers/vine-bioinformatics-internship-binder-lab-2025",
     "research", "Armenia", False, {"gpa_required": "yes"}),
    ("Staff.am - data science internships",
     "https://staff.am/jobs/data-science/data-science-internship",
     "internship", "Armenia", False, {"gpa_required": "unknown"}),
    # --- Research program directories (meta-sources, bursty yield) ---
    ("UC Davis - global research opportunities",
     "https://globallearning.ucdavis.edu/pathways/experience/internships/global-research",
     "research", None, False, {"gpa_required": "yes", "kind": "directory"}),
    ("Ramapo College - bioinformatics research opportunities",
     "https://bioinformatics.ramapo.edu/research/index.html",
     "research", "USA", False, {"gpa_required": "unknown", "kind": "directory"}),
    ("UCSD bioinformatics - nationwide research opportunities",
     "https://bioinformatics.ucsd.edu/undergrad/nationwide-opportunities",
     "research", "USA", False, {"gpa_required": "yes", "kind": "directory"}),
    ("UChicago CCRF - international research opportunities",
     "https://ccrf.uchicago.edu/international-research-opportunities",
     "research", None, False, {"gpa_required": "yes", "kind": "directory"}),
    # --- Structured internships / research programs ---
    ("SASTRA COMBIGS - bioinformatics internship",
     "https://sastra.edu/combigs/intern.html", "training", "India", False,
     {"gpa_required": "unknown"}),
    ("Iowa IHG - summer bioinformatics internship",
     "https://humangenetics.medicine.uiowa.edu/education-division/summer-internship-bioinformatics",
     "research", "USA", False, {"gpa_required": "yes"}),
    ("Nanjing University - summer research intern program",
     "https://stuex.nju.edu.cn/en_/57248/list.htm", "research", "China", False,
     {"gpa_required": "yes"}),
    ("RBC Borealis - ML research internships",
     "https://rbcborealis.com/internships/", "internship", "Canada", False,
     {"gpa_required": "yes"}),
    ("Allen Institute for AI - internships",
     "https://allenai.org/internships", "internship", "USA", True,
     {"gpa_required": "unknown"}),
    ("Vector Institute - AI research internships",
     "https://vectorinstitute.ai/research-talent/students/ai-research-internships/",
     "internship", "Canada", False, {"gpa_required": "unknown"}),
    ("INSAIT SURF - summer undergraduate research fellowship",
     "https://insait.ai/surf/", "research", "Bulgaria", False,
     {"gpa_required": "yes", "note": "GPA 3.5; fully funded incl. travel"}),
    ("Vienna BioCenter summer school",
     "https://training.vbc.ac.at/summer-school/", "training", "Austria", False,
     {"gpa_required": "yes"}),
]

REPUTATION_PRIORS = [
    ("oldsite.abi.am", 0.8), ("abi.am", 0.8), ("staff.am", 0.65),
    ("globallearning.ucdavis.edu", 0.85), ("bioinformatics.ramapo.edu", 0.75),
    ("bioinformatics.ucsd.edu", 0.85), ("ccrf.uchicago.edu", 0.85),
    ("sastra.edu", 0.7), ("humangenetics.medicine.uiowa.edu", 0.85),
    ("stuex.nju.edu.cn", 0.85), ("rbcborealis.com", 0.8),
    ("allenai.org", 0.85), ("vectorinstitute.ai", 0.85),
    ("insait.ai", 0.8), ("training.vbc.ac.at", 0.85),
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
