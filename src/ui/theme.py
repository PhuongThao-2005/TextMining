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


_SANS = '"Work Sans", Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
_MONO = '"DM Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace'

LIGHT_THEME = ThemeTokens(
    _SANS, _MONO,
    "#f6f7f4", "#ffffff", "#edf1ed", "#e2e9e3", "rgba(246,247,244,.97)",
    "#1c302b", "#41574f", "#657a70", "#ffffff",
    "#e2e8e2", "#cdd9d0", "#a5b8ab",
    "#0f766e", "#0b625b", "#e0f0e9", "#135e52",
    "#247449", "#8c651e", "#b43b35", "#28747c",
    "8px", "10px", "14px", "18px",
    "0 2px 4px rgba(24,48,38,.03)",
    "0 6px 24px rgba(24,48,38,.05)",
    "0 16px 56px rgba(24,48,38,.14)",
    "1120px", "820px",
)

DARK_THEME = ThemeTokens(
    _SANS, _MONO,
    "#101d1b", "#172825", "#1c302c", "#263c35", "rgba(16,29,27,.97)",
    "#e9f0eb", "#c4d3c9", "#94ada0", "#0d2722",
    "#223831", "#304b40", "#526f5f",
    "#50c4ac", "#77d4bc", "#203e34", "#a9e4ce",
    "#88cc9f", "#dbc183", "#f0948a", "#8dc6ce",
    "8px", "10px", "14px", "18px",
    "0 2px 4px rgba(0,0,0,.08)",
    "0 6px 24px rgba(0,0,0,.12)",
    "0 16px 56px rgba(0,0,0,.28)",
    "1120px", "820px",
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
