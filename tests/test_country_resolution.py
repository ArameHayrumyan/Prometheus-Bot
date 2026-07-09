"""Country resolution so the search country filter is meaningful."""
from app.pipeline.ingest import resolve_country
from app.scraping.base import RawOpportunity


class _FakeSession:
    def __init__(self, source=None):
        self._source = source

    async def get(self, model, pk):
        return self._source


class _Src:
    def __init__(self, country):
        self.country = country


async def test_extracted_country_wins():
    raw = RawOpportunity(source_id=5, url="u", title="t", text="x")
    assert await resolve_country(_FakeSession(_Src("Japan")), raw, "USA") == "USA"


async def test_falls_back_to_source_country():
    raw = RawOpportunity(source_id=5, url="u", title="Intern", text="join us")
    assert await resolve_country(_FakeSession(_Src("Germany")), raw, None) == "Germany"


async def test_detects_remote_when_no_source_country():
    raw = RawOpportunity(source_id=None, url="u",
                         title="Remote Data Science Internship", text="work anywhere")
    assert await resolve_country(_FakeSession(), raw, None) == "Remote"


async def test_none_when_nothing_known():
    raw = RawOpportunity(source_id=None, url="u", title="Onsite role", text="office based")
    assert await resolve_country(_FakeSession(), raw, None) is None


async def test_source_country_beats_remote_word():
    raw = RawOpportunity(source_id=5, url="u", title="Remote-friendly role", text="x")
    assert await resolve_country(_FakeSession(_Src("Armenia")), raw, None) == "Armenia"
