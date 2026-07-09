"""Reddit OAuth URL rewrite + config gating (no network)."""
import app.scraping.reddit_auth as ra


def test_configured_gating(monkeypatch):
    from app.config import Settings

    def fake(**over):
        base = dict(bot_token="0:x", channel_id_main="-1",
                    database_url="postgresql://x:x@h/d")
        base.update(over)
        return Settings(**base)

    monkeypatch.setattr(ra, "get_settings", lambda: fake())
    assert ra.reddit_configured() is False
    monkeypatch.setattr(ra, "get_settings",
                        lambda: fake(reddit_client_id="a", reddit_client_secret="b"))
    assert ra.reddit_configured() is True


def test_oauth_url_rewrite():
    # the rewrite that makes datacenter requests work: www -> oauth host
    url = "https://www.reddit.com/r/bioinformatics/new.json?limit=40"
    rewritten = url.replace("https://www.reddit.com", "https://oauth.reddit.com")
    assert rewritten == "https://oauth.reddit.com/r/bioinformatics/new.json?limit=40"
