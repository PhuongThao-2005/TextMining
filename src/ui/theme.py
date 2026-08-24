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
    "#f7fbff", "#ffffff", "#eef6ff", "#e2eefc", "rgba(255,255,255,.92)",
    "#0f172a", "#334155", "#64748b", "#ffffff",
    "#e2e8f0", "#cbd5e1", "#94a3b8",
    "#2563eb", "#1d4ed8", "#dbeafe", "#1e3a8a",
    "#16a34a", "#0ea5e9", "#dc2626", "#2563eb",
    "7px", "9px", "13px", "16px",
    "0 1px 2px rgba(48,42,30,.04)",
    "0 8px 20px rgba(48,42,30,.04)",
    "0 20px 56px rgba(48,42,30,.12)",
    "1180px", "930px",
)

DARK_THEME = ThemeTokens(
    _SANS, _MONO,
    "#0f172a", "#111827", "#1e293b", "#263449", "rgba(17,24,39,.94)",
    "#f8fafc", "#cbd5e1", "#94a3b8", "#0f172a",
    "#1e293b", "#334155", "#475569",
    "#60a5fa", "#93c5fd", "#1e3a8a", "#dbeafe",
    "#4ade80", "#38bdf8", "#f87171", "#60a5fa",
    "7px", "9px", "13px", "16px",
    "0 1px 2px rgba(0,0,0,.16)",
    "0 8px 28px rgba(0,0,0,.16)",
    "0 18px 52px rgba(0,0,0,.24)",
    "1180px", "930px",
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
