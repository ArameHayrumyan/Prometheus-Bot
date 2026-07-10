"""og:image / twitter:image extraction (the regexes, no network)."""
from app.scraping.og_image import _META_AFTER, _META_BEFORE


def _extract(html: str) -> str | None:
    for rx in (_META_BEFORE, _META_AFTER):
        m = rx.search(html)
        if m:
            return m.group(1).strip()
    return None


def test_og_image_property_before_content():
    html = '<meta property="og:image" content="https://site.org/card.png">'
    assert _extract(html) == "https://site.org/card.png"


def test_og_image_content_before_property():
    html = '<meta content="https://site.org/card.jpg" property="og:image"/>'
    assert _extract(html) == "https://site.org/card.jpg"


def test_twitter_image_fallback():
    html = '<meta name="twitter:image" content="https://site.org/tw.png">'
    assert _extract(html) == "https://site.org/tw.png"


def test_no_image_meta():
    html = '<meta name="description" content="a page about jobs">'
    assert _extract(html) is None
