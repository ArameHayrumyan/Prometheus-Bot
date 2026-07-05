"""Forward-to-bot matching (§12): #opp tag parsing + origin/tag resolution."""
from app.bot.forward_match import extract_opp_id, resolve_forwarded
from app.db.models import Opportunity


def test_extract_opp_id_from_post_footer():
    text = "🎓 SCHOLARSHIP\n\nSome program…\n\n#opp1234 #scholarship"
    assert extract_opp_id(text) == 1234


def test_extract_opp_id_absent():
    assert extract_opp_id("no tags here #internship") is None
    assert extract_opp_id(None) is None
    assert extract_opp_id("#oppX12") is None


def test_extract_opp_id_word_boundary():
    assert extract_opp_id("#opp42abc") is None  # not a valid tag
    assert extract_opp_id("see #opp42 now") == 42


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    """Covers the two lookups resolve_forwarded performs."""

    def __init__(self, by_channel_post: Opportunity | None = None,
                 by_id: dict[int, Opportunity] | None = None):
        self.by_channel_post = by_channel_post
        self.by_id = by_id or {}
        self.executed = 0

    async def execute(self, stmt):
        self.executed += 1
        return FakeResult(self.by_channel_post)

    async def get(self, model, pk):
        return self.by_id.get(pk)


def opp(opp_id: int) -> Opportunity:
    o = Opportunity(url="u", raw_hash=str(opp_id), title="t", opportunity_type="job")
    o.id = opp_id
    return o


async def test_resolves_via_channel_post_lookup():
    expected = opp(7)
    session = FakeSession(by_channel_post=expected)
    found = await resolve_forwarded(session, origin_chat_id=-100123,
                                    origin_message_id=55, text=None)
    assert found is expected


async def test_falls_back_to_opp_tag_when_origin_unknown():
    expected = opp(99)
    session = FakeSession(by_channel_post=None, by_id={99: expected})
    found = await resolve_forwarded(session, origin_chat_id=-100123,
                                    origin_message_id=55, text="…\n#opp99 #job")
    assert found is expected


async def test_tag_only_no_origin():
    expected = opp(5)
    session = FakeSession(by_id={5: expected})
    found = await resolve_forwarded(session, None, None, "#opp5")
    assert found is expected
    assert session.executed == 0  # no origin -> no channel_posts query


async def test_unmatchable_returns_none():
    session = FakeSession()
    assert await resolve_forwarded(session, None, None, "hello") is None
