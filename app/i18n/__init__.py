"""Tiny YAML-based i18n with live DB-backed overrides.

Lookup order: admin override (app_settings "i18n_overrides") -> base catalog
for the language -> English override -> English catalog -> the key itself.
Overrides are loaded into memory at startup and refreshed by /settext, so
t() stays synchronous everywhere.
"""
from pathlib import Path

import yaml

_DIR = Path(__file__).parent
_catalogs: dict[str, dict] = {}
_overrides: dict[str, dict[str, str]] = {}


def _load(lang: str) -> dict:
    if lang not in _catalogs:
        path = _DIR / f"{lang}.yml"
        if not path.exists():
            path = _DIR / "en.yml"
        with open(path, encoding="utf-8") as f:
            _catalogs[lang] = yaml.safe_load(f) or {}
    return _catalogs[lang]


def set_overrides(data: dict | None) -> None:
    """Replace the in-memory override map: {lang: {key: text}}."""
    global _overrides
    _overrides = data or {}


def get_overrides() -> dict:
    return _overrides


def base_keys() -> list[str]:
    """All known string keys (from the English base catalog)."""
    return sorted(_load("en").keys())


def base_value(key: str, lang: str = "en") -> str | None:
    return _load(lang).get(key)


def t(key: str, lang: str = "en", **kwargs) -> str:
    template = (
        (_overrides.get(lang) or {}).get(key)
        or _load(lang).get(key)
        or (_overrides.get("en") or {}).get(key)
        or _load("en").get(key)
        or key
    )
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
