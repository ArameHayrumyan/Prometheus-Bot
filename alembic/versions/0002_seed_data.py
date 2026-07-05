"""seed degree levels, field taxonomy, source registry, reputation priors

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DEGREE_LEVELS = [
    ("undergrad", "Undergraduate"),
    ("masters", "Masters"),
    ("phd", "PhD"),
]

FIELDS = [
    ("Computer Science", ["computer science", "software", "programming", "cs ", "informatics",
                          "algorithms", "cybersecurity", "web develop", "mobile develop", "devops",
                          "backend", "frontend", "cloud comput"]),
    ("Data Science", ["data science", "machine learning", "deep learning", "artificial intelligence",
                      " ai ", "data analy", "nlp", "computer vision", "statistics", "big data",
                      "data engineer", "llm"]),
    ("Bioinformatics", ["bioinformatics", "computational biology", "genomics", "proteomics",
                        "systems biology", "biostatistics", "biotech", "molecular biology",
                        "single-cell", "sequencing"]),
    ("Engineering", ["engineering", "electrical", "mechanical", "robotics", "embedded",
                     "hardware", "mechatronics", "aerospace", "civil engineer", "chemical engineer"]),
]

# (name, source_type, url, category, country, needs_js, meta)
SOURCES = [
    # --- Niche academic / research boards (webpage) ---
    ("FindAPhD - funded CS/DS", "webpage", "https://www.findaphd.com/phds/computer-science/?01M0", "phd_board", None, False, {}),
    ("FindAPhD - bioinformatics", "webpage", "https://www.findaphd.com/phds/bioinformatics/?01M0", "phd_board", None, False, {}),
    ("FindAMasters - scholarships", "webpage", "https://www.findamasters.com/masters-degrees/computer-science/", "masters_board", None, False, {}),
    ("AcademicJobsOnline", "webpage", "https://academicjobsonline.org/ajo/jobs?joblist-0-0-0-0-0-d", "academic_board", None, False, {}),
    ("Euraxess - jobs & fellowships", "rss", "https://euraxess.ec.europa.eu/f/rss/jobs", "fellowship", "EU", False, {}),
    ("Bioinformatics.org jobs", "webpage", "https://www.bioinformatics.org/jobs/", "bioinfo_board", None, False, {}),
    ("Nature Careers - bioinformatics", "webpage", "https://www.nature.com/naturecareers/jobs/bioinformatics", "academic_board", None, False, {}),
    # --- Research institute open-position pages (webpage) ---
    ("EMBL Jobs", "webpage", "https://www.embl.org/jobs/searchjobs/", "institute", "EU", False, {}),
    ("Broad Institute Careers", "webpage", "https://broadinstitute.avature.net/en_US/careers/SearchJobs", "institute", "USA", True, {}),
    ("Wellcome Sanger Institute Jobs", "webpage", "https://jobs.sanger.ac.uk/vacancies.html", "institute", "UK", False, {}),
    ("Max Planck Society Jobs", "webpage", "https://www.mpg.de/jobboard", "institute", "Germany", False, {}),
    ("CERN Students & Graduates", "webpage", "https://careers.cern/students-graduates", "institute", "Switzerland", True, {}),
    ("ETH Zurich Open Positions", "webpage", "https://jobs.ethz.ch/", "institute", "Switzerland", True, {}),
    ("EPFL Open Positions", "webpage", "https://www.epfl.ch/about/working/working-at-epfl/job-openings/", "institute", "Switzerland", False, {}),
    # --- Government / multilateral scholarship portals (webpage) ---
    ("Chevening Scholarships", "webpage", "https://www.chevening.org/scholarships/", "gov_scholarship", "UK", False, {}),
    ("Australia Awards", "webpage", "https://www.dfat.gov.au/people-to-people/australia-awards/australia-awards-scholarships", "gov_scholarship", "Australia", False, {}),
    ("Japan MEXT Scholarship", "webpage", "https://www.studyinjapan.go.jp/en/planning/scholarship/", "gov_scholarship", "Japan", False, {}),
    ("Swiss Government Excellence Scholarships", "webpage", "https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants/swiss-government-excellence-scholarships.html", "gov_scholarship", "Switzerland", False, {}),
    ("Vanier Canada Graduate Scholarships", "webpage", "https://vanier.gc.ca/en/home-accueil.html", "gov_scholarship", "Canada", False, {}),
    ("Commonwealth Scholarships", "webpage", "https://cscuk.fcdo.gov.uk/scholarships/", "gov_scholarship", "UK", False, {}),
    ("Open Society Foundations Grants", "webpage", "https://www.opensocietyfoundations.org/grants", "gov_scholarship", None, False, {}),
    ("DAAD Scholarship Database", "webpage", "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/", "gov_scholarship", "Germany", True, {}),
    ("Fulbright Armenia", "webpage", "https://am.usembassy.gov/education-culture/educational-exchange/", "gov_scholarship", "USA", False, {}),
    ("Erasmus+ Opportunities", "webpage", "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals", "gov_scholarship", "EU", False, {}),
    # --- Niche / startup job boards ---
    ("Wellfound (AngelList) - internships", "webpage", "https://wellfound.com/role/r/software-engineer-intern", "startup_board", None, True, {}),
    ("RemoteOK - dev jobs", "rss", "https://remoteok.com/remote-dev-jobs.rss", "startup_board", None, False, {}),
    ("WeWorkRemotely - programming", "rss", "https://weworkremotely.com/categories/remote-programming-jobs.rss", "startup_board", None, False, {}),
    ("WeWorkRemotely - all jobs", "rss", "https://weworkremotely.com/remote-jobs.rss", "startup_board", None, False, {}),
    # --- Country talent / relocation portals ---
    ("Make it in Germany", "webpage", "https://www.make-it-in-germany.com/en/working-in-germany/job-listings", "relocation", "Germany", True, {}),
    ("Work in Estonia", "webpage", "https://workinestonia.com/jobs/", "relocation", "Estonia", True, {}),
    ("Work in Denmark - IT", "webpage", "https://www.workindenmark.dk/search-job?q=software", "relocation", "Denmark", True, {}),
    # --- University / local bulletins (Armenia-relevant) ---
    ("AUA Career Opportunities", "webpage", "https://careers.aua.am/", "university", "Armenia", False, {}),
    ("TUMO Labs", "webpage", "https://tumolabs.am/en/", "university", "Armenia", False, {}),
    ("Enterprise Incubator Foundation News", "webpage", "https://www.eif.am/eng/news/", "university", "Armenia", False, {}),
    # --- Aggregators ---
    ("Opportunity Desk", "rss", "https://opportunitydesk.org/feed/", "aggregator", None, False, {}),
    ("ProFellow Blog", "rss", "https://www.profellow.com/feed/", "aggregator", None, False, {}),
    ("Opportunities Circle", "webpage", "https://www.opportunitiescircle.com/", "aggregator", None, False, {}),
    ("Scholarship Positions", "rss", "https://scholarship-positions.com/feed/", "aggregator", None, False, {}),
    ("Armacad (Armenia-focused academia)", "webpage", "https://armacad.info/", "aggregator", "Armenia", False, {}),
    # --- Company career pages ---
    ("JetBrains Careers", "webpage", "https://www.jetbrains.com/careers/jobs/", "company", None, True, {}),
    ("Picsart Careers", "webpage", "https://picsart.com/jobs", "company", "Armenia", True, {}),
    ("Krisp Careers", "webpage", "https://krisp.ai/careers/", "company", "Armenia", True, {}),
    ("ServiceTitan Careers (Armenia)", "webpage", "https://www.servicetitan.com/careers", "company", "Armenia", True, {}),
    ("EPAM Careers Armenia", "webpage", "https://www.epam.com/careers/job-listings?country=Armenia", "company", "Armenia", True, {}),
    ("NVIDIA University Jobs", "webpage", "https://www.nvidia.com/en-us/about-nvidia/careers/university-recruiting/", "company", None, True, {}),
    # --- Community boards ---
    ("r/bioinformatics", "community", "https://www.reddit.com/r/bioinformatics/new.json?limit=40", "community", None, False, {}),
    ("r/datascience", "community", "https://www.reddit.com/r/datascience/new.json?limit=40", "community", None, False, {}),
    ("r/MachineLearning", "community", "https://www.reddit.com/r/MachineLearning/new.json?limit=40", "community", None, False, {}),
    ("HN Who is Hiring (Algolia)", "community", "https://hn.algolia.com/api/v1/search_by_date?query=%22who%20is%20hiring%22&tags=story&hitsPerPage=3", "community", None, False, {"kind": "hn"}),
    # --- Newsletter mailbox (single logical source; IMAP creds from env) ---
    ("Newsletter mailbox (IMAP)", "email", "imap://inbox", "newsletter", None, False, {}),
    # --- LinkedIn guest job search (polite, throttled; proxy via LINKEDIN_PROXY_URL) ---
    ("LinkedIn guest - DS internships (worldwide remote)", "linkedin",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=data%20science%20intern&location=Worldwide&f_WT=2&start=0",
     "linkedin", None, False, {}),
    ("LinkedIn guest - junior software (Armenia)", "linkedin",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=junior%20software%20engineer&location=Armenia&start=0",
     "linkedin", "Armenia", False, {}),
    ("LinkedIn guest - bioinformatics (remote)", "linkedin",
     "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=bioinformatics&location=Worldwide&f_WT=2&start=0",
     "linkedin", None, False, {}),
]

# Reputation priors so known institutions start above unknown domains
REPUTATION_PRIORS = [
    ("embl.org", 0.95), ("broadinstitute.org", 0.95), ("sanger.ac.uk", 0.95),
    ("mpg.de", 0.95), ("cern.ch", 0.95), ("ethz.ch", 0.95), ("epfl.ch", 0.95),
    ("chevening.org", 0.9), ("dfat.gov.au", 0.9), ("studyinjapan.go.jp", 0.9),
    ("sbfi.admin.ch", 0.9), ("vanier.gc.ca", 0.9), ("cscuk.fcdo.gov.uk", 0.9),
    ("daad.de", 0.9), ("erasmus-plus.ec.europa.eu", 0.9), ("euraxess.ec.europa.eu", 0.9),
    ("opensocietyfoundations.org", 0.85), ("nature.com", 0.9),
    ("findaphd.com", 0.8), ("findamasters.com", 0.8), ("academicjobsonline.org", 0.8),
    ("jetbrains.com", 0.85), ("nvidia.com", 0.85), ("epam.com", 0.75),
    ("picsart.com", 0.75), ("krisp.ai", 0.75), ("servicetitan.com", 0.75),
    ("aua.am", 0.8), ("tumolabs.am", 0.8), ("eif.am", 0.75), ("armacad.info", 0.7),
    ("opportunitydesk.org", 0.6), ("profellow.com", 0.65),
    ("scholarship-positions.com", 0.5), ("opportunitiescircle.com", 0.5),
    ("weworkremotely.com", 0.6), ("remoteok.com", 0.55), ("wellfound.com", 0.6),
    ("linkedin.com", 0.6), ("reddit.com", 0.45), ("news.ycombinator.com", 0.55),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, name in DEGREE_LEVELS:
        conn.execute(sa.text(
            "INSERT INTO degree_levels (code, name) VALUES (:c, :n) ON CONFLICT DO NOTHING"
        ), {"c": code, "n": name})
    for name, keywords in FIELDS:
        conn.execute(sa.text(
            "INSERT INTO field_taxonomy (name, keywords, active) VALUES (:n, :k, true) "
            "ON CONFLICT (name) DO NOTHING"
        ), {"n": name, "k": json.dumps(keywords)})
    for name, stype, url, category, country, needs_js, meta in SOURCES:
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
    conn.execute(sa.text("DELETE FROM sources"))
    conn.execute(sa.text("DELETE FROM source_reputation"))
    conn.execute(sa.text("DELETE FROM field_taxonomy"))
    conn.execute(sa.text("DELETE FROM degree_levels"))
