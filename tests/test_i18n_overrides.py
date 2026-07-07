"""Live text customization: override precedence, fallbacks, placeholders."""
import pytest

from app.i18n import base_keys, set_overrides, t


@pytest.fixture(autouse=True)
def reset_overrides():
    set_overrides({})
    yield
    set_overrides({})


def test_override_wins_over_base():
    assert t("btn_apply", "en") == "🚀 Apply"
    set_overrides({"en": {"btn_apply": "🔥 Apply now!"}})
    assert t("btn_apply", "en") == "🔥 Apply now!"
    # other language untouched
    assert "Դիմել" in t("btn_apply", "hy")


def test_override_with_placeholders():
    set_overrides({"en": {"saved_ok": "Bookmarked: {title} ✨"}})
    assert t("saved_ok", "en", title="EMBL internship") == "Bookmarked: EMBL internship ✨"


def test_broken_placeholder_falls_back_to_template():
    set_overrides({"en": {"saved_ok": "Bookmarked {titl} oops"}})
    # missing kwarg in the custom text -> raw template returned, no crash
    assert t("saved_ok", "en", title="X") == "Bookmarked {titl} oops"


def test_hy_falls_back_to_en_override_then_en_base():
    set_overrides({"en": {"btn_apply": "APPLY"}})
    # key present in hy base -> hy base wins for hy users
    assert "Դիմել" in t("btn_apply", "hy")
    # key missing everywhere -> the key itself
    assert t("nonexistent_key_xyz", "hy") == "nonexistent_key_xyz"


def test_type_labels_are_keys():
    for opp_type in ("internship", "scholarship", "fellowship", "training",
                     "job", "hackathon"):
        assert f"type_{opp_type}" in base_keys()
        assert t(f"type_{opp_type}", "en") != f"type_{opp_type}"


def test_reset_restores_default():
    set_overrides({"en": {"btn_apply": "custom"}})
    assert t("btn_apply", "en") == "custom"
    set_overrides({})
    assert t("btn_apply", "en") == "🚀 Apply"
