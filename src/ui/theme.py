"""Central light/dark design tokens and CSS-variable generation."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ThemeTokens:
    font_sans: str
    font_mono: str
    page_background: str
    surface_primary: str
    surface_secondary: str
    surface_tertiary: str
    surface_elevated: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_inverse: str
    border_subtle: str
    border_default: str
    border_strong: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_text: str
    success: str
    warning: str
    danger: str
    info: str
    radius_sm: str
    radius_md: str
    radius_lg: str
    radius_xl: str
    shadow_sm: str
    shadow_md: str
    shadow_lg: str
    content_width: str
    reading_width: str


_SANS = 'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
_MONO = '"SFMono-Regular", Consolas, "Liberation Mono", monospace'

LIGHT_THEME = ThemeTokens(
    _SANS, _MONO,
    "#f7f7f5", "#ffffff", "#f2f2ef", "#ecece8", "rgba(255,255,255,.94)",
    "#171714", "#4f4f48", "#74746c", "#ffffff",
    "#e9e9e4", "#ddddd6", "#c7c7bd",
    "#1f766f", "#175e59", "#e5f2f0", "#124b47",
    "#23835b", "#a85f0d", "#b93b3b", "#3c6da8",
    "9px", "13px", "17px", "23px",
    "0 1px 2px rgba(24,24,20,.04)",
    "0 1px 2px rgba(24,24,20,.04), 0 8px 30px rgba(24,24,20,.05)",
    "0 16px 48px rgba(24,24,20,.08)",
    "1260px", "790px",
)

DARK_THEME = ThemeTokens(
    _SANS, _MONO,
    "#111311", "#181b18", "#20231f", "#292c28", "rgba(24,27,24,.96)",
    "#f1f2ed", "#c4c7bd", "#92968b", "#10120f",
    "#292d28", "#373c35", "#4b5148",
    "#75bdb5", "#8dcac3", "#203c38", "#b7e4df",
    "#65be8d", "#dfa658", "#e27878", "#80a9db",
    "9px", "13px", "17px", "23px",
    "0 1px 2px rgba(0,0,0,.16)",
    "0 8px 28px rgba(0,0,0,.14)",
    "0 16px 48px rgba(0,0,0,.18)",
    "1260px", "790px",
)

THEME_CHOICES = ("System", "Light", "Dark")


def css_variables(tokens: ThemeTokens) -> str:
    """Return deterministic CSS custom properties for one token set."""
    aliases = {
        "page_background": "page-bg",
        "surface_primary": "surface-primary",
        "surface_secondary": "surface-secondary",
        "surface_tertiary": "surface-tertiary",
        "surface_elevated": "surface-elevated",
    }
    values = asdict(tokens)
    return "\n".join(
        f"--{aliases.get(name, name.replace('_', '-'))}: {value};"
        for name, value in values.items()
    )


def build_theme_css(choice: str = "System") -> str:
    """Build variable declarations; System follows prefers-color-scheme."""
    if choice not in THEME_CHOICES:
        raise ValueError(f"Unknown theme choice: {choice}")
    base = DARK_THEME if choice == "Dark" else LIGHT_THEME
    blocks = [f":root {{\n{css_variables(base)}\n}}"]
    if choice == "System":
        blocks.append(
            "@media (prefers-color-scheme: dark) {\n"
            f":root {{\n{css_variables(DARK_THEME)}\n}}\n"
            "}"
        )
    return "\n".join(blocks)


__all__ = ["DARK_THEME", "LIGHT_THEME", "THEME_CHOICES", "ThemeTokens", "build_theme_css", "css_variables"]
