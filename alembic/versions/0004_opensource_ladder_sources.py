"""seed open-source / experience-based "ladder" sources (user-curated, 2026-07)

These are credential-first-not-GPA-first opportunities (GSoC orgs, Outreachy,
research residencies, lab internships) — the rungs most reachable for a strong
portfolio regardless of transcript.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# (name, source_type, url, category, country, needs_js, meta)
SOURCES = [
    # --- Bioinformatics: institutes & open-source orgs ---
    ("EMBL Internships", "webpage",
     "https://www.embl.org/careers/internships/", "institute", "EU", False, {}),
    ("EMBL TechDev Internship Programme", "webpage",
     "https://www.embl.org/about/info/scientific-visitor-programme/fellowships/techdev/",
     "institute", "EU", False, {}),
    ("Theory@EMBL Visitor Programme", "webpage",
     "https://www.embl.org/about/info/scientific-visitor-programme/", "institute", "EU", False, {}),
    ("EMBL-EBI Google Summer of Code", "webpage",
     "https://www.ebi.ac.uk/about/events/events/public-event/2025/2026-google-summer-of-code/",
     "opensource", "EU", False, {}),
    ("GMOD / Open Genome Informatics GSoC", "webpage",
     "https://gmod.org/wiki/GSoC.html", "opensource", None, False, {}),
    ("Open Bioinformatics Foundation GSoC", "webpage",
     "https://www.open-bio.org/events/gsoc/", "opensource", None, False, {}),
    ("Biopython GSoC", "webpage",
     "https://biopython.org/wiki/Google_Summer_of_Code", "opensource", None, False, {}),
    ("Galaxy Project", "webpage",
     "https://galaxyproject.org/", "opensource", None, False, {}),
    ("Bioconductor", "webpage",
     "https://bioconductor.org/", "opensource", None, False, {}),
    ("cBioPortal GSoC", "webpage",
     "https://github.com/cBioPortal/GSoC", "opensource", None, False, {}),
    ("MPI CBS - Neural Data Science internships", "webpage",
     "https://www.cbs.mpg.de/career/internships", "institute", "Germany", False, {}),
    ("MPIIB-ISI Integrative Science Internship", "webpage",
     "https://www.mpiib-berlin.mpg.de/2155069/mpiib-isi-application-guide",
     "institute", "Germany", False, {}),
    # --- ML / DS / AI: open-source communities, residencies, scholar programs ---
    ("EleutherAI Community", "webpage",
     "https://www.eleuther.ai/community", "opensource", None, True, {}),
    ("EleutherAI SOAR (Summer of Open AI Research)", "webpage",
     "https://www.eleuther.ai/soar", "opensource", None, True, {}),
    ("LAION", "webpage",
     "https://laion.ai/", "opensource", None, True, {}),
    ("OpenMined / PySyft", "webpage",
     "https://openmined.org/pysyft/", "opensource", None, True, {}),
    ("OpenMined PySyft (GitHub)", "webpage",
     "https://github.com/OpenMined/PySyft", "opensource", None, False, {}),
    ("Cohere Labs Open Science Community", "webpage",
     "https://cohere.com/research/open-science", "research_program", None, True, {}),
    ("Cohere Labs Scholars Program", "webpage",
     "https://cohere.com/research/scholars-program", "research_program", None, True, {}),
    ("Cohere For AI Scholars Program (blog)", "webpage",
     "https://cohere.com/blog/c4ai-scholars-program", "research_program", None, True, {}),
    ("Hugging Face AI Research Residency", "webpage",
     "https://huggingface.co/blog/ai-residency", "research_program", None, False, {}),
    ("Outreachy Applicant Guide", "webpage",
     "https://www.outreachy.org/docs/applicant/", "opensource", None, False,
     {"note": "paid remote internships explicitly for underrepresented backgrounds; no GPA screen"}),
    ("Google Summer of Code - get started", "webpage",
     "https://summerofcode.withgoogle.com/get-started", "opensource", None, True,
     {"note": "SPA; Playwright locally, httpx fallback on free host"}),
    ("OSGeo Google Summer of Code", "webpage",
     "https://wiki.osgeo.org/wiki/Google_Summer_of_Code_2025", "opensource", None, False, {}),
    ("MPI for Intelligent Systems - internships", "webpage",
     "https://is.mpg.de/en/internships", "institute", "Germany", False, {}),
    ("RIGI Research Internship (MPI-IS)", "webpage",
     "https://rig-internships.de/program", "institute", "Germany", False, {}),
    ("MPI-IS internship guide (Zhijing Jin, GitHub)", "webpage",
     "https://github.com/zhijing-jin/nlp-phd-global-equality/blob/main/mpi_internship.md",
     "meta_source", None, False, {}),
    ("Liquid Galaxy Project (GSoC org)", "webpage",
     "https://summerofcode.withgoogle.com/programs/2026/organizations/liquid-galaxy-project",
     "opensource", None, True, {}),
]

# Subdomain-specific priors (reputation lookup keys on the full netloc)
REPUTATION_PRIORS = [
    ("ebi.ac.uk", 0.9), ("gmod.org", 0.6), ("open-bio.org", 0.65),
    ("biopython.org", 0.65), ("galaxyproject.org", 0.65), ("bioconductor.org", 0.7),
    ("cbs.mpg.de", 0.9), ("mpiib-berlin.mpg.de", 0.9), ("is.mpg.de", 0.9),
    ("eleuther.ai", 0.75), ("laion.ai", 0.7), ("openmined.org", 0.7),
    ("cohere.com", 0.85), ("huggingface.co", 0.85), ("outreachy.org", 0.85),
    ("summerofcode.withgoogle.com", 0.9), ("wiki.osgeo.org", 0.7),
    ("rig-internships.de", 0.7),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, stype, url, category, country, needs_js, meta in SOURCES:
        exists = conn.execute(
            sa.text("SELECT 1 FROM sources WHERE url = :u"), {"u": url}
        ).first()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO sources (name, source_type, url, category, country, needs_js, active, meta) "
            "VALUES (:n, :t, :u, :c, :co, :js, true, :m)"
        ), {"n": name, "t": stype, "u": url, "c": category, "co": country,
            "js": needs_js, "m": json.dumps(meta)})
    for domain, score in REPUTATION_PRIORS:
        conn.execute(sa.text(
            "INSERT INTO source_reputation (domain, score) VALUES (:d, :s) "
            "ON CONFLICT (domain) DO NOTHING"
        ), {"d": domain, "s": score})


def downgrade() -> None:
    conn = op.get_bind()
    for _name, _stype, url, *_rest in SOURCES:
        conn.execute(sa.text("DELETE FROM sources WHERE url = :u"), {"u": url})
