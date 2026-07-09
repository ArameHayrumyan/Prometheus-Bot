"""Reddit OAuth (free 'script' app) — token fetch + authenticated GET.

The public www.reddit.com/.json endpoint is blocked from datacenter IPs
(GitHub Actions, cloud VMs). oauth.reddit.com with an app token is not, and
is fully ToS-compliant. Register an app at
https://www.reddit.com/prefs/apps (type: script) → put the client id/secret
in REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET. Read-only, app-only auth (no
user password needed) via the client-credentials grant.
"""
import time

import httpx

from app.config import get_settings

USER_AGENT = "python:moonin-opportunities-bot:1.0 (by /u/moonin-bot)"
_token: str | None = None
_token_expiry: float = 0.0


def reddit_configured() -> bool:
    s = get_settings()
    return bool(s.reddit_client_id and s.reddit_client_secret)


async def _get_token() -> str:
    global _token, _token_expiry
    if _token and time.monotonic() < _token_expiry - 60:
        return _token
    s = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(s.reddit_client_id, s.reddit_client_secret),
            headers={"User-Agent": USER_AGENT},
        )
    resp.raise_for_status()
    payload = resp.json()
    _token = payload["access_token"]
    _token_expiry = time.monotonic() + int(payload.get("expires_in", 3600))
    return _token


async def oauth_get_json(url: str) -> dict:
    """GET a reddit URL via oauth.reddit.com with an app token."""
    # public listing URLs point at www.reddit.com/.json — rewrite to the API host
    api_url = url.replace("https://www.reddit.com", "https://oauth.reddit.com")
    token = await _get_token()
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        resp = await client.get(
            api_url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        )
    resp.raise_for_status()
    return resp.json()
