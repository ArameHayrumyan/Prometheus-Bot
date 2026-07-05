"""Concrete AIProvider implementations: DeepSeek, Groq, Gemini.

All three are called through httpx directly (no vendor SDKs) so each class
fully owns its request/response format.
"""
import json

import httpx

from app.ai.base import AIError, AIProvider, AIRateLimited

_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


class _OpenAICompatProvider(AIProvider):
    """Shared logic for OpenAI-compatible chat/completions APIs (DeepSeek, Groq)."""

    base_url: str = ""
    model: str = ""

    async def _generate(self, system: str, user: str, max_tokens: int, json_mode: bool) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
        if resp.status_code == 429:
            raise AIRateLimited(f"{self.name}: 429 {resp.text[:200]}")
        if resp.status_code >= 400:
            raise AIError(f"{self.name}: HTTP {resp.status_code} {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise AIError(f"{self.name}: malformed response: {e}") from e


class GroqProvider(_OpenAICompatProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"
    model = "llama-3.3-70b-versatile"


class DeepSeekProvider(_OpenAICompatProvider):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    model = "deepseek-chat"


class GeminiProvider(AIProvider):
    name = "gemini"
    model = "gemini-1.5-flash"

    async def _generate(self, system: str, user: str, max_tokens: int, json_mode: bool) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload: dict = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 429:
            raise AIRateLimited(f"gemini: 429 {resp.text[:200]}")
        if resp.status_code >= 400:
            raise AIError(f"gemini: HTTP {resp.status_code} {resp.text[:200]}")
        try:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise AIError(f"gemini: malformed response: {e}") from e
