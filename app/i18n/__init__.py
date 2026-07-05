"""Tiny YAML-based i18n. Usage: t("key", lang, **fmt)."""
from pathlib import Path

import yaml

_DIR = Path(__file__).parent
_catalogs: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _catalogs:
        path = _DIR / f"{lang}.yml"
        if not path.exists():
            path = _DIR / "en.yml"
        with open(path, encoding="utf-8") as f:
            _catalogs[lang] = yaml.safe_load(f) or {}
    return _catalogs[lang]


def t(key: str, lang: str = "en", **kwargs) -> str:
    catalog = _load(lang)
    template = catalog.get(key) or _load("en").get(key) or key
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
