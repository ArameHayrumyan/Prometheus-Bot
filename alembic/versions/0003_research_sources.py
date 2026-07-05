"""seed additional researched sources (user-curated list, 2026-07)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# (name, source_type, url, category, country, needs_js, meta)
SOURCES = [
    # --- Scholarship databases / portals ---
    ("DAAD RISE research internships", "webpage",
     "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50015638",
     "gov_scholarship", "Germany", True,
     {"note": "classic RISE restricted to NA/UK/IE students; hard gate handles eligibility per listing"}),
    ("Mastersportal - scholarships finder", "webpage",
     "https://www.mastersportal.com/scholarships/", "aggregator", None, True, {}),
    ("Bachelorsportal - DS & Big Data scholarships", "webpage",
     "https://www.bachelorsportal.com/search/scholarships/bachelor/data-science-big-data",
     "aggregator", None, True, {"degree_hint": "undergrad"}),
    ("PhDportal - DS & Big Data scholarships", "webpage",
     "https://www.phdportal.com/search/scholarships/phd/data-science-big-data",
     "aggregator", None, True, {"degree_hint": "phd"}),
    ("ScholarshipsAds - internship scholarships", "webpage",
     "https://www.scholarshipsads.com/category/degree/internship", "aggregator", None, False, {}),
    # --- Internship & training platforms (funding gate filters fee-based ones) ---
    ("Intern Abroad HQ - CS & IT", "webpage",
     "https://www.internhq.com/fields/computer-science-and-it/", "internship_platform", None, False, {}),
    ("IES Internships - CS/Data/Math", "webpage",
     "https://www.iesabroad.org/intern-abroad/fields/computer-science-math-statistics",
     "internship_platform", None, True, {}),
    ("Code.org - CS internships & apprenticeships", "webpage",
     "https://code.org/en-US/students/internships-and-apprenticeships",
     "meta_source", "USA", False, {}),
    ("Prosple - DS internships (USA/remote)", "webpage",
     "https://prosple.com/data-science-internships-in-usa", "internship_platform", "USA", True, {}),
    ("Augustana tech-majors internship hub", "webpage",
     "https://careers.augustana.edu/resources/internships-jobs-for-tech-majors-computer-science-data-it/",
     "meta_source", "USA", False, {}),
    ("Global Internship List (GitHub)", "webpage",
     "https://github.com/VikashPR/Global-Internship-List", "meta_source", None, False, {}),
    # --- Bioinformatics / computational biology ---
    ("PathwaysToScience - bioinformatics", "webpage",
     "https://www.pathwaystoscience.org/discipline.aspx?sort=TEC-Bioinformatics_Bioinformatics",
     "bioinfo_board", "USA", False, {}),
    ("PathwaysToScience - bioinformatics & genomics", "webpage",
     "https://www.pathwaystoscience.org/Discipline.aspx?sort=TEC-Bioinformatics_Bioinformatics+%2A+Genomics",
     "bioinfo_board", "USA", False, {}),
    ("HackBio - bioinformatics/DS internships", "webpage",
     "https://internship.thehackbio.com/opportunities-in-bfx", "bioinfo_board", None, True, {}),
    ("Biotecnika - KWIK scholarship", "webpage",
     "https://www.biotecnika.org/2023/11/kwik-scholarship-for-biotech-life-science-ug-pg-students/",
     "bioinfo_board", "India", False, {}),
    ("Achilleus - medical informatics internship", "webpage",
     "https://eic-achilleus.eu/job/it-specialist-for-medical-informatics/",
     "institute", "EU", False, {}),
    ("Nature Careers - life science internships EU", "webpage",
     "https://www.nature.com/naturecareers/jobs/life-science/internship/europe/full-time/",
     "academic_board", "EU", False, {}),
    # --- University & institute pages ---
    ("ISTA - internships & scholarships", "webpage",
     "https://ista.ac.at/en/education/internship-and-scholarship/", "institute", "Austria", False, {}),
    ("HKU CS - research internship programme", "webpage",
     "https://www.cs.hku.hk/rintern/", "university", "Hong Kong", False, {}),
    ("ULB - MA-BINF bioinformatics internships", "webpage",
     "https://sciences.ulb.be/en/computer-sciences/internships/m-binf-internships",
     "university", "Belgium", False, {}),
    ("URI - CS & DS projects/internships", "webpage",
     "https://web.uri.edu/cs/academics/projects-and-internships/", "university", "USA", False, {}),
    ("UN ICC - data science internships", "webpage",
     "https://www.unicc.org/working-with-icc/data-science-intern/", "institute", None, False, {}),
    # --- Big boards, strict downstream filtering ---
    ("LinkedIn guest - DS intern jobs worldwide (SEO page)", "linkedin",
     "https://www.linkedin.com/jobs/data-science-intern-jobs-worldwide", "linkedin", None, False, {}),
    ("Indeed - DS student internships", "webpage",
     "https://www.indeed.com/q-data-science-student-internship-jobs.html",
     "job_board", "USA", True,
     {"note": "Cloudflare-protected; may fail without SCRAPER_PROXY_URL - handler logs and skips"}),
]

REPUTATION_PRIORS = [
    ("mastersportal.com", 0.7), ("bachelorsportal.com", 0.7), ("phdportal.com", 0.7),
    ("scholarshipsads.com", 0.4), ("internhq.com", 0.5), ("iesabroad.org", 0.6),
    ("code.org", 0.8), ("prosple.com", 0.6), ("careers.augustana.edu", 0.7),
    ("github.com", 0.6), ("pathwaystoscience.org", 0.8),
    ("internship.thehackbio.com", 0.55), ("biotecnika.org", 0.45),
    ("eic-achilleus.eu", 0.6), ("ista.ac.at", 0.9), ("cs.hku.hk", 0.85),
    ("sciences.ulb.be", 0.8), ("web.uri.edu", 0.7), ("unicc.org", 0.85),
    ("indeed.com", 0.5),
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
