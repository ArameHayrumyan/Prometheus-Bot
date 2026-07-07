"""youth deep-research batch: olympiads, teen CTFs/contests, funded research
programs and camps, Armenian school-STEM ecosystem — all audience=youth

Dropped from the submitted list: ArmOI PDF (unscrapeable conference paper;
olymp.am covers the pipeline), picoCTF CMU outreach page + Lumiere
application page + Armath FAQ (subpage duplicates), TeamsCode resources
(learning-links list, not opportunities). WRO India national page replaced
by the global WRO association site.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-08
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

# (name, url, category, country, needs_js, meta)
SOURCES = [
    # --- Olympiads & competitions ---
    ("International Olympiad in Informatics (IOI)", "https://ioinformatics.org/",
     "olympiad", None, False, {"field": "cs", "min_age": "14-19", "cost": "free"}),
    ("International Mathematical Olympiad (IMO)", "https://www.imo-official.org/",
     "olympiad", None, False, {"field": "math", "min_age": "14-19", "cost": "free"}),
    ("Olymp.am - Armenian national subject olympiads", "https://www.olymp.am",
     "olympiad", "Armenia", False,
     {"field": "general-stem", "min_age": "grades 6-12", "cost": "free"}),
    ("Open Olympiad in Informatics (Moscow)", "https://inf-open.ru/?lang=en",
     "olympiad", "Russia", False,
     {"field": "cs", "min_age": "13-19", "cost": "fully-funded"}),
    ("International Computing Olympiad", "https://www.computingolympiad.org/",
     "olympiad", None, False,
     {"field": "cs", "min_age": "13-19", "cost": "unknown"}),
    ("FIRST Global Challenge (robotics)", "https://first.global/fgc/",
     "olympiad", None, True,
     {"field": "robotics", "min_age": "14-18", "cost": "scholarship-track"}),
    ("World Robot Olympiad (global)", "https://wro-association.org/",
     "olympiad", None, False,
     {"field": "robotics", "min_age": "8-19", "cost": "scholarship-track",
      "note": "substituted for the submitted India national page"}),
    ("International Computer Science Competition", "https://icscompetition.org",
     "olympiad", None, False,
     {"field": "cs", "min_age": "13-19", "cost": "unknown"}),
    # --- Teen programming contests & CTFs ---
    ("CPI - student programming contests hub", "https://joincpi.org/contests",
     "olympiad", None, False,
     {"field": "cs", "min_age": "13-19", "cost": "free", "kind": "directory"}),
    ("TeamsCode - programming contests", "https://www.teamscode.org/contests/",
     "olympiad", None, False, {"field": "cs", "min_age": "13-19", "cost": "free"}),
    ("CALICO informatics competition (UC Berkeley)", "https://calico.cs.berkeley.edu",
     "olympiad", "USA", False, {"field": "cs", "min_age": "14-19", "cost": "free"}),
    ("CodeHER competition", "https://codehercompetition.org",
     "olympiad", None, False,
     {"field": "cs", "min_age": "13-19", "cost": "free",
      "note": "girls/non-binary students"}),
    ("picoCTF (CMU cybersecurity)", "https://picoctf.org",
     "olympiad", None, True,
     {"field": "cs", "min_age": "13-19", "cost": "free",
      "note": "competition + year-round practice, certificates"}),
    ("Newark Academy CTF", "https://ctf.nactf.net",
     "olympiad", None, False,
     {"field": "cs", "min_age": "13-19", "cost": "free",
      "note": "prizes US-only, participation worldwide"}),
    # --- Funded research programs & camps ---
    ("Research Science Institute (RSI, MIT)",
     "https://math.mit.edu/research/highschool/rsi/",
     "research", "USA", False,
     {"field": "general-stem", "min_age": "grade 11", "cost": "fully-funded"}),
    ("MIT high-school research programs (RSI & PRIMES)",
     "https://math.mit.edu/research/highschool/",
     "research", "USA", False,
     {"field": "math/cs", "min_age": "15-18", "cost": "scholarship-track",
      "kind": "directory"}),
    ("Lumiere Research Inclusion Foundation", "https://lumiere.foundation",
     "research", None, False,
     {"field": "general-stem", "min_age": "15-19", "cost": "fully-funded",
      "note": "free 1-on-1 research mentorship for low-income students worldwide"}),
    ("MIT admissions - STEM summer programs list",
     "https://mitadmissions.org/apply/prepare/summer/",
     "camp", "USA", False,
     {"field": "general-stem", "min_age": "15-18", "cost": "scholarship-track",
      "kind": "directory"}),
    ("Harry Messel International Science School (Sydney)",
     "https://www.sydney.edu.au/science/iss",
     "camp", "Australia", False,
     {"field": "general-stem", "min_age": "16-19", "cost": "free",
      "note": "verify URL — submitted short path may redirect"}),
    # --- Armenian ecosystem ---
    ("Armath engineering laboratories (UATE)", "https://armath.am/en/about",
     "ecosystem", "Armenia", False,
     {"field": "robotics/cs", "min_age": "10-18", "cost": "free",
      "note": "600+ free after-school engineering labs"}),
]

REPUTATION_PRIORS = [
    ("ioinformatics.org", 0.9), ("imo-official.org", 0.9), ("olymp.am", 0.85),
    ("inf-open.ru", 0.7), ("computingolympiad.org", 0.5), ("first.global", 0.85),
    ("wro-association.org", 0.85), ("icscompetition.org", 0.5),
    ("joincpi.org", 0.65), ("teamscode.org", 0.65),
    ("calico.cs.berkeley.edu", 0.85), ("codehercompetition.org", 0.6),
    ("picoctf.org", 0.9), ("ctf.nactf.net", 0.55), ("math.mit.edu", 0.95),
    ("lumiere.foundation", 0.7), ("mitadmissions.org", 0.9),
    ("sydney.edu.au", 0.9), ("armath.am", 0.85),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, url, category, country, needs_js, meta in SOURCES:
        exists = conn.execute(sa.text("SELECT 1 FROM sources WHERE url = :u"),
                              {"u": url}).first()
        if exists:
            continue
        meta = dict(meta, audience="youth")
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
