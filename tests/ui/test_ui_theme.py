from dataclasses import fields

import pytest

from src.ui.styles import build_application_css
from src.ui.theme import DARK_THEME, LIGHT_THEME, ThemeTokens, build_theme_css, css_variables


def test_light_and_dark_tokens_are_complete_nonempty_and_distinct() -> None:
    required = {field.name for field in fields(ThemeTokens)}
    for theme in (LIGHT_THEME, DARK_THEME):
        values = theme.__dict__
        assert set(values) == required
        assert all(isinstance(value, str) and value for value in values.values())
        assert "http" not in theme.font_sans.lower()
        assert "secret" not in repr(theme).lower()
    assert LIGHT_THEME.page_background != DARK_THEME.page_background
    assert LIGHT_THEME.text_primary != LIGHT_THEME.page_background
    assert DARK_THEME.text_primary != DARK_THEME.page_background
    assert DARK_THEME.page_background != "#000000"


@pytest.mark.parametrize("choice", ["System", "Light", "Dark"])
def test_theme_css_is_valid_and_contains_required_contracts(choice: str) -> None:
    css = build_application_css(choice)
    assert ":root" in css and "--page-bg:" in css and "--reading-width:" in css
    assert "@media (max-width:1023px)" in css
    assert "@media (max-width:640px)" in css
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "https://" not in css and "@import" not in css
    assert css.count("{") == css.count("}")


def test_system_theme_contains_dark_media_override() -> None:
    assert "prefers-color-scheme: dark" in build_theme_css("System")
    assert "prefers-color-scheme: dark" not in build_theme_css("Light")
    assert "--accent:" in css_variables(LIGHT_THEME)


def test_select_arrow_keeps_svg_background_transparent() -> None:
    css = build_application_css("Dark")
    transparent_path = 'svg path[fill="none"] {'
    arrow_path = 'svg path:not([fill="none"]) {'

    assert transparent_path in css
    assert arrow_path in css
    transparent_rule = css.split(transparent_path, 1)[1].split("}", 1)[0]
    arrow_rule = css.split(arrow_path, 1)[1].split("}", 1)[0]
    assert "fill:none !important;" in transparent_rule
    assert "fill:currentColor !important;" in arrow_rule


def test_toast_uses_application_theme_tokens() -> None:
    css = build_application_css("Dark")
    toast_rule = css.split('[data-testid="stToast"] {', 1)[1].split("}", 1)[0]
    toast_text_rule = css.split('[data-testid="stToast"] [data-testid="stToastText"],', 1)[1].split("}", 1)[0]

    assert "background:var(--legal-panel) !important;" in toast_rule
    assert "color:var(--legal-ink) !important;" in toast_rule
    assert "color:var(--legal-ink) !important;" in toast_text_rule


def test_invalid_theme_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_theme_css("Neon")
