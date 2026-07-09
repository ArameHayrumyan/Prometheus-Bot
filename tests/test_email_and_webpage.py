"""Email newsletter extraction + webpage candidate harvesting (incl. the
per-source CSS selector precision mode)."""
from app.scraping.email_newsletter import extract_email_opportunities
from app.scraping.webpage import extract_candidates

HTML_EMAIL = """
<html><body>
  <table><tr><td>
    <a href="https://uni.example.org/scholarships/full-ride#details">
      Fully funded Masters scholarship in Data Science
    </a>
    <p>Deadline: March 1, 2027. Stipend included.</p>
  </td></tr></table>
  <a href="https://twitter.com/newsletter">Follow us</a>
  <a href="https://example.org/unsubscribe-internship">unsub</a>
  <a href="#top">Back to top</a>
  <a href="https://jobs.example.com/junior-ml-engineer">Junior ML Engineer position</a>
</body></html>
"""


def test_email_html_extracts_opportunity_links():
    items = extract_email_opportunities("Weekly digest", HTML_EMAIL, True, source_id=1)
    urls = [i.url for i in items]
    # fragment URL must survive (the old '#' substring skip dropped it)
    assert "https://uni.example.org/scholarships/full-ride#details" in urls
    assert "https://jobs.example.com/junior-ml-engineer" in urls
    # social + anchor-only links excluded
    assert not any("twitter.com" in u for u in urls)
    assert not any(u.startswith("#") for u in urls)


def test_email_html_context_carries_newsletter_subject():
    items = extract_email_opportunities("ProFellow weekly", HTML_EMAIL, True, source_id=1)
    assert all(i.text.startswith("[newsletter: ProFellow weekly]") for i in items)


def test_email_html_embeds_secondary_links_for_ai_preservation():
    html = """<td>
      <a href="https://uni.example.org/phd-scholarship">Fully funded PhD scholarship in Data Science</a>
      <a href="https://uni.example.org/apply-now">Apply</a>
      <a href="https://uni.example.org/deadline-info">Deadline details</a>
    </td>"""
    items = extract_email_opportunities("Digest", html, True, source_id=1)
    assert items, "should extract the scholarship listing"
    text = items[0].text
    # secondary links embedded so the AI TL;DR (which replaces the body) can't drop them
    assert "apply-now" in text and "deadline-info" in text
    # the primary link is not duplicated into the embedded list
    assert text.count("phd-scholarship") == 0


PLAIN_EMAIL = """New opportunities this week:

1) Fully funded PhD position in bioinformatics, apply at
https://lab.example.edu/phd-opening.
2) Nothing relevant here http://example.com/cats.
"""


def test_email_plaintext_strips_trailing_punctuation():
    items = extract_email_opportunities("Digest", PLAIN_EMAIL, False, source_id=1)
    urls = [i.url for i in items]
    assert "https://lab.example.edu/phd-opening" in urls  # no trailing dot
    assert not any(u.endswith(".") for u in urls)


PAGE = """
<html><body>
  <nav><a href="/jobs/fake-nav-internship">Internships (menu)</a></nav>
  <div class="sidebar">
    <a href="/random/software-blog-post">Our software blog anniversary post</a>
  </div>
  <div class="jobs-list">
    <li><a href="/jobs/1">Bioinformatics research internship, funded</a>
        <span>6 months, stipend</span></li>
    <li><a href="/jobs/2">Junior software engineer position</a></li>
  </div>
</body></html>
"""


def test_webpage_selector_scopes_extraction():
    scoped = extract_candidates(PAGE, "https://site.org", 1, selector="div.jobs-list")
    urls = [i.url for i in scoped]
    assert "https://site.org/jobs/1" in urls
    assert "https://site.org/jobs/2" in urls
    assert not any("blog" in u for u in urls)  # sidebar excluded by selector


def test_webpage_without_selector_still_harvests():
    items = extract_candidates(PAGE, "https://site.org", 1)
    assert any("/jobs/1" in i.url for i in items)


def test_webpage_anchor_selector_direct():
    # selector matching <a> elements directly also works
    items = extract_candidates(PAGE, "https://site.org", 1,
                               selector="div.jobs-list a")
    assert len(items) == 2
