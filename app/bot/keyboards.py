"""Inline keyboard builders shared across handlers."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t


def kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
        for row in rows
    ])


def language_kb() -> InlineKeyboardMarkup:
    return kb([[("🇬🇧 English", "lang:en"), ("🇦🇲 Հայերեն", "lang:hy")]])


def degree_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([
        [(t("degree_undergrad", lang), "deg:undergrad")],
        [(t("degree_masters", lang), "deg:masters")],
        [(t("degree_phd", lang), "deg:phd")],
    ])


def fields_kb(all_fields: list[str], selected: list[str], lang: str) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for i, name in enumerate(all_fields):
        mark = "✅ " if name in selected else "▫️ "
        rows.append([(mark + name, f"fld:{i}")])
    rows.append([(t("btn_done", lang), "fld:done")])
    return kb(rows)


def english_test_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([
        [("IELTS", "eng:IELTS"), ("TOEFL", "eng:TOEFL")],
        [(t("btn_no_cert", lang), "eng:none")],
    ])


def skip_kb(lang: str) -> InlineKeyboardMarkup:
    return kb([[(t("btn_skip", lang), "skip")]])
