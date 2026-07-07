"""release batch: hackathons/easy-apply, stipended OSS fellowships, vendor
student programs, summer research (GPA-tier), niche bio/space, aggregators,
Armenian ecosystem

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# (name, source_type, url, category, country, needs_js, meta)
SOURCES = [
    # --- Hackathons & easy-apply competitions (credential-free entry) ---
    ("Devpost - hackathons", "webpage", "https://devpost.com/hackathons",
     "hackathons", None, True, {}),
    ("MLH - hackathon season", "webpage", "https://mlh.io/seasons/2027/events",
     "hackathons", None, False, {}),
    ("Kaggle - competitions", "webpage", "https://www.kaggle.com/competitions",
     "hackathons", None, True, {}),
    ("DrivenData - competitions", "webpage", "https://www.drivendata.org/competitions/",
     "hackathons", None, False, {}),
    ("Zindi - competitions", "webpage", "https://zindi.africa/competitions",
     "hackathons", None, True, {}),
    ("NASA Space Apps Challenge", "webpage", "https://www.spaceappschallenge.org/",
     "hackathons", None, True, {}),
    ("Microsoft Imagine Cup", "webpage", "https://imaginecup.microsoft.com/",
     "hackathons", None, True, {}),
    # --- Stipended open-source fellowships (portfolio > GPA) ---
    ("MLH Fellowship", "webpage", "https://fellowship.mlh.io/", "opensource", None, False, {}),
    ("Summer of Bitcoin", "webpage", "https://www.summerofbitcoin.org/", "opensource", None, True, {}),
    ("LFX Mentorship (Linux Foundation)", "webpage",
     "https://mentorship.lfx.linuxfoundation.org/", "opensource", None, True, {}),
    ("Igalia Coding Experience", "webpage", "https://www.igalia.com/coding-experience/",
     "opensource", None, False, {}),
    # --- Vendor student programs (free, credential-building) ---
    ("GitHub Education for students", "webpage", "https://github.com/education/students",
     "student_program", None, False, {}),
    ("AWS Educate", "webpage", "https://aws.amazon.com/education/awseducate/",
     "student_program", None, False, {}),
    ("Cisco Networking Academy", "webpage", "https://www.netacad.com/",
     "student_program", None, True, {}),
    # --- Summer research programs (the GPA/intermediate tier) ---
    ("ETH Zurich - Student Summer Research Fellowship", "webpage",
     "https://inf.ethz.ch/studies/summer-research-fellowship.html",
     "summer_research", "Switzerland", False, {}),
    ("Summer@EPFL", "webpage", "https://www.epfl.ch/schools/ic/education/summer-at-epfl/",
     "summer_research", "Switzerland", False, {}),
    ("Mitacs Globalink Research Internship", "webpage",
     "https://www.mitacs.ca/our-programs/globalink-research-internship-students/",
     "summer_research", "Canada", False, {}),
    ("UTokyo UTRIP", "webpage", "https://www.s.u-tokyo.ac.jp/en/UTRIP/",
     "summer_research", "Japan", False, {}),
    ("Caltech SURF", "webpage", "https://sfp.caltech.edu/undergraduate-research/programs/surf",
     "summer_research", "USA", False, {}),
    ("OIST Research Internships", "webpage", "https://www.oist.jp/research/research-internships",
     "summer_research", "Japan", False, {}),
    ("KAUST VSRP", "webpage", "https://vsrp.kaust.edu.sa/",
     "summer_research", "Saudi Arabia", True, {}),
    ("DESY Summer Student Programme", "webpage", "https://summerstudents.desy.de/",
     "summer_research", "Germany", False, {}),
    ("RIKEN student programs", "webpage", "https://www.riken.jp/en/careers/programs/",
     "summer_research", "Japan", False, {}),
    ("Amgen Scholars", "webpage", "https://amgenscholars.com/",
     "summer_research", None, False, {}),
    # --- Niche: computational biology / space / neuro ---
    ("ISCB Careers (computational biology)", "webpage", "https://careers.iscb.org/",
     "bioinfo_board", None, False, {}),
    ("Bioinformatics.ca job postings", "webpage", "https://bioinformatics.ca/job-postings/",
     "bioinfo_board", "Canada", False, {}),
    ("Neuromatch (comp-neuro courses & community)", "webpage", "https://neuromatch.io/",
     "bioinfo_board", None, False, {}),
    ("EMBO fellowships & grants", "webpage",
     "https://www.embo.org/funding/fellowships-grants-and-career-support/",
     "fellowship", "EU", False, {}),
    ("ESA student internships", "webpage",
     "https://www.esa.int/About_Us/Careers_at_ESA/Student_internships",
     "institute", "EU", False, {}),
    # --- Aggregators (broad, downstream filters do the work) ---
    ("Scholars4Dev", "rss", "https://www.scholars4dev.com/feed/", "aggregator", None, False, {}),
    ("Youth Opportunities", "webpage", "https://www.youthop.com/", "aggregator", None, False, {}),
    ("Opportunities For Youth", "webpage", "https://opportunitiesforyouth.org/",
     "aggregator", None, False, {}),
    ("Mladiinfo", "rss", "https://www.mladiinfo.eu/feed/", "aggregator", None, False, {}),
    ("WeMakeScholars", "webpage", "https://www.wemakescholars.com/scholarship",
     "aggregator", None, True, {}),
    # --- Armenian ecosystem ---
    ("FAST Foundation (fellowships & programs)", "webpage", "https://fast.foundation/",
     "university", "Armenia", False, {}),
    ("Synopsys Armenia careers", "webpage", "https://careers.synopsys.com/search-jobs/Armenia",
     "company", "Armenia", True, {}),
    ("42 Yerevan", "webpage", "https://42yerevan.am/", "university", "Armenia", False, {}),
    ("Armenian Code Academy", "webpage", "https://aca.am/", "university", "Armenia", False, {}),
]

REPUTATION_PRIORS = [
    ("devpost.com", 0.65), ("mlh.io", 0.75), ("fellowship.mlh.io", 0.75),
    ("kaggle.com", 0.8), ("drivendata.org", 0.7), ("zindi.africa", 0.6),
    ("spaceappschallenge.org", 0.75), ("imaginecup.microsoft.com", 0.85),
    ("summerofbitcoin.org", 0.6), ("mentorship.lfx.linuxfoundation.org", 0.8),
    ("igalia.com", 0.7), ("aws.amazon.com", 0.85), ("netacad.com", 0.8),
    ("inf.ethz.ch", 0.95), ("mitacs.ca", 0.85), ("s.u-tokyo.ac.jp", 0.9),
    ("sfp.caltech.edu", 0.9), ("oist.jp", 0.9), ("vsrp.kaust.edu.sa", 0.85),
    ("summerstudents.desy.de", 0.85), ("riken.jp", 0.9), ("amgenscholars.com", 0.8),
    ("careers.iscb.org", 0.75), ("bioinformatics.ca", 0.75), ("neuromatch.io", 0.7),
    ("embo.org", 0.9), ("esa.int", 0.9), ("scholars4dev.com", 0.6),
    ("youthop.com", 0.5), ("opportunitiesforyouth.org", 0.5), ("mladiinfo.eu", 0.55),
    ("wemakescholars.com", 0.55), ("fast.foundation", 0.85),
    ("careers.synopsys.com", 0.8), ("42yerevan.am", 0.75), ("aca.am", 0.75),
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
