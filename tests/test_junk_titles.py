"""Junk navigation/filter anchor texts must be rejected; real listings kept."""
from app.scraping.webpage import _looks_like_listing

HREF = "https://site.org/jobs/123"

JUNK = [
    "Skip to job results", "Skip to refine results", "Skip to main content",
    "Skip to AI Search", "Back to Top ⬆️", "View open jobs", "See all",
    "High School Students", "Undergraduate Students", "Graduate Students",
    "Faculty & Administrators", "Post-Baccalaureate", "Postdoc & Early Career",
    "Apprenticeships", "College internships", "High school internships",
    "Explore internships in Computer Science & IT", "Remove selection",
]

REAL = [
    "Graduate Research Assistant in Bioinformatics",
    "PhD Position in Machine Learning at EMBL",
    "Software Engineering Internship (funded)",
    "Bioinformatics research internship, stipend included",
    "Postdoctoral Researcher in Computational Genomics",
    "Data Science Summer Fellowship 2027",
]


def test_junk_titles_rejected():
    for title in JUNK:
        assert _looks_like_listing(title, HREF) is False, f"should reject: {title}"


def test_real_titles_kept():
    for title in REAL:
        assert _looks_like_listing(title, HREF) is True, f"should keep: {title}"
