"""Central application styles for LexVN's Streamlit interface.

Application-owned containers use stable ``st-key-*`` selectors. Native widget
overrides target Streamlit test IDs, keeping both themes on the same tokens.
"""
from __future__ import annotations

from .theme import build_theme_css


def build_application_css(theme_choice: str = "System") -> str:
    return build_theme_css(theme_choice) + """
:root {
  --legal-sans:var(--font-sans);
  --legal-serif:var(--font-sans);
  --legal-mono:var(--font-mono);
  --legal-ink:var(--text-primary);
  --legal-muted:var(--text-muted);
  --legal-line:var(--border-default);
  --legal-panel:var(--surface-primary);
  --legal-wash:var(--surface-secondary);
  --legal-accent:var(--accent);
  --legal-accent-soft:var(--accent-soft);
  --legal-accent-text:var(--accent-text);
  --legal-side:var(--surface-secondary);
  --sidebar-width:270px;
}

/* Application shell. Keep Streamlit's native sidebar and its mobile menu. */
html, body, [data-testid="stApp"] { font-family:var(--legal-sans); letter-spacing:0; }
[data-testid="stAppViewContainer"], [data-testid="stApp"] {
  background:var(--page-bg); color:var(--legal-ink);
}
[data-testid="stMainBlockContainer"] {
  max-width:none; padding:18px 32px 9rem; margin:0; min-width:0;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap:1rem; }
[data-testid="stHeader"] { height:0; background:transparent; }
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] { visibility:hidden; }
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
[data-testid="stCaptionContainer"], [data-testid="stExpander"] { color:var(--legal-ink); }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
  color:var(--text-secondary); font-weight:400; line-height:1.7;
}
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 {
  color:var(--legal-ink); font-family:var(--legal-sans); font-weight:600;
}
[data-testid="stMarkdownContainer"] strong { font-weight:600; }
[data-testid="stCaptionContainer"] p { color:var(--legal-muted); font-size:12px; line-height:1.55; }
a { color:var(--legal-accent); text-underline-offset:3px; }
code, pre { font-family:var(--legal-mono); }
*:focus-visible { outline:2px solid var(--legal-accent); outline-offset:3px; }
::selection { background:var(--accent-soft); color:var(--accent-text); }

/* Native controls share one theme rather than individual dark overrides. */
[data-testid="stButton"] button, [data-testid="stLinkButton"] a,
[data-testid="stDownloadButton"] button, [data-testid="stFormSubmitButton"] button,
[data-testid="stPopover"] button {
  min-height:38px; border:1px solid var(--border-subtle); border-radius:var(--radius-md);
  background:var(--legal-panel); color:var(--legal-ink); font-weight:500;
  box-shadow:none; transition:background .15s ease, border-color .15s ease;
}
[data-testid="stButton"] button:hover, [data-testid="stLinkButton"] a:hover,
[data-testid="stDownloadButton"] button:hover, [data-testid="stPopover"] button:hover {
  background:var(--legal-wash); border-color:var(--legal-line); color:var(--legal-ink);
}
[data-testid="stButton"] button p, [data-testid="stLinkButton"] a p,
[data-testid="stDownloadButton"] button p, [data-testid="stFormSubmitButton"] button p,
[data-testid="stPopover"] button p {
  color:inherit !important; font-size:inherit !important; font-weight:inherit !important; line-height:1.4;
}
[data-testid="stButton"] button[kind="primary"], [data-testid="stFormSubmitButton"] button {
  background:var(--legal-accent); border-color:transparent; color:var(--text-inverse);
}
[data-testid="stButton"] button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover {
  background:var(--accent-hover); color:var(--text-inverse); border-color:transparent;
}
[data-testid="stButton"] button[kind="tertiary"] { background:transparent; border-color:transparent; }
[data-testid="stButton"] button[kind="tertiary"]:hover { background:var(--legal-wash); }
[data-testid="stButton"] button:disabled, [data-testid="stFormSubmitButton"] button:disabled {
  background:var(--surface-tertiary); color:var(--text-muted); opacity:.65; border-color:transparent;
}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] > div,
[data-baseweb="textarea"], [data-testid="stNumberInput"] > div {
  background:var(--legal-panel) !important; color:var(--legal-ink) !important;
  border-color:var(--legal-line) !important; border-radius:var(--radius-md);
}
[data-baseweb="select"] [role="combobox"], [data-baseweb="select"] [data-baseweb="tag"],
[data-baseweb="select"] input, [data-baseweb="input"] input,
[data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stChatInput"] textarea {
  color:var(--legal-ink) !important; -webkit-text-fill-color:var(--legal-ink) !important;
  background:transparent !important; caret-color:var(--legal-accent); font-family:var(--legal-sans);
}
[data-baseweb="select"] [aria-hidden="true"], [data-testid="stSelectbox"] button[aria-label="Open"],
[data-testid="stNumberInput"] button {
  background:transparent !important; color:var(--legal-muted) !important; border:0;
}
[data-testid="stSelectbox"] button[aria-label="Open"] svg path[fill="none"] { fill:none !important; }
[data-testid="stSelectbox"] button[aria-label="Open"] svg path:not([fill="none"]) { fill:currentColor !important; }
[data-testid="stTextArea"] textarea::placeholder, [data-testid="stChatInput"] textarea::placeholder,
[data-testid="stTextInput"] input::placeholder {
  color:var(--legal-muted) !important; -webkit-text-fill-color:var(--legal-muted) !important; opacity:1;
}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"], [role="listbox"],
[data-testid="stPopoverBody"] {
  background:var(--legal-panel) !important; color:var(--legal-ink) !important;
  border:1px solid var(--border-subtle); border-radius:var(--radius-md); box-shadow:var(--shadow-md);
}
[data-baseweb="popover"] [role="option"], [data-baseweb="menu"] li, [role="listbox"] [role="option"] {
  color:var(--legal-ink) !important; background:var(--legal-panel) !important;
}
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][aria-selected="true"],
[role="listbox"] [role="option"][data-focus="true"] {
  background:var(--legal-wash) !important; color:var(--legal-accent-text) !important;
}
[data-testid="stExpander"] details {
  background:transparent; border:1px solid var(--border-subtle); border-radius:var(--radius-md);
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {
  color:var(--text-secondary); font-size:13px; font-weight:500;
}
[data-testid="stExpander"] summary:hover { color:var(--legal-accent); }
[data-testid="stRadio"] label p, [data-testid="stCheckbox"] label p { color:var(--text-secondary); }
[data-testid="stAlert"] {
  border:1px solid var(--border-subtle); border-radius:var(--radius-md);
  background:var(--legal-wash); color:var(--legal-ink);
}
[data-testid="stAlert"] p { color:var(--text-secondary); }

/* Sidebar navigation and intentionally retained demo/developer controls. */
[data-testid="stSidebar"] {
  width:var(--sidebar-width) !important; min-width:var(--sidebar-width) !important;
  max-width:var(--sidebar-width) !important; background:var(--legal-side);
  color:var(--legal-ink); border-right:1px solid var(--border-subtle);
}
[data-testid="stSidebarContent"] { background:var(--legal-side); padding:0 18px 20px; }
[data-testid="stSidebarUserContent"] { padding:0; }
[data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"] {
  min-height:calc(100dvh - 86px); gap:.7rem;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.6rem; }
[data-testid="stSidebar"][aria-expanded="false"], [data-testid="stSidebarCollapsed"] {
  width:0 !important; min-width:0 !important; max-width:0 !important; border:0; padding:0;
}
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button, [data-testid="collapsedControl"] button {
  width:34px; height:34px; border-radius:var(--radius-md); color:var(--legal-muted);
  background:var(--legal-side); border:0;
}
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
  z-index:100; top:18px; left:12px;
}
.ga-sidebar-brand { display:flex; align-items:center; gap:11px; padding:2px 0 24px; }
.ga-brand-mark {
  width:38px; height:42px; flex-shrink:0; display:grid; place-items:center;
  color:var(--legal-accent-text); background:var(--legal-accent-soft); border-radius:11px;
}
.ga-brand-document {
  position:relative; display:block; width:21px; height:26px;
  border:1.5px solid currentColor; border-radius:3px; padding:5px 4px;
}
.ga-brand-document i { display:block; width:11px; height:1.5px; margin-bottom:3px; background:currentColor; }
.ga-brand-document i:nth-child(2) { width:7px; }
.ga-brand-document b {
  position:absolute; bottom:-4px; right:-7px; padding:0 2px; background:var(--legal-accent-soft);
  font:600 12px/1.3 var(--legal-mono);
}
.ga-sidebar-brand strong { display:block; color:var(--legal-ink); font-size:21px; font-weight:650; letter-spacing:-.5px; }
.ga-sidebar-brand > div > span { display:block; margin-top:2px; color:var(--legal-muted); font-size:11px; line-height:1.45; }
[data-testid="stSidebar"] [data-testid="stButton"] button { width:100%; font-size:13px; }
.st-key-new-question button {
  min-height:48px !important; margin:2px 0 10px; border-radius:11px !important;
  background:var(--legal-accent) !important; border-color:transparent !important;
  color:var(--text-inverse) !important; font-size:14px !important; font-weight:600 !important;
}
.st-key-new-question button::before {
  content:"+"; display:inline-grid; place-items:center; width:18px; height:18px; margin-right:8px;
  color:inherit; font-size:20px; line-height:18px; font-weight:500;
}
.st-key-new-question button:hover { background:var(--accent-hover) !important; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size:12px; color:var(--text-secondary); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
.ga-sidebar-section-label { margin:15px 2px 4px; color:var(--legal-muted); font-size:12px; font-weight:500; }
.st-key-sidebar-help, .st-key-sidebar-settings, .st-key-sidebar-developer { margin-top:4px; }
.st-key-sidebar-help [data-testid="stExpander"] details,
.st-key-sidebar-settings [data-testid="stExpander"] details,
.st-key-sidebar-developer [data-testid="stExpander"] details {
  overflow:hidden; border:1px solid transparent; border-radius:11px; background:transparent;
}
.st-key-sidebar-help [data-testid="stExpander"] details[open],
.st-key-sidebar-settings [data-testid="stExpander"] details[open],
.st-key-sidebar-developer [data-testid="stExpander"] details[open] {
  border-color:var(--border-subtle); background:var(--legal-panel);
}
.st-key-sidebar-help [data-testid="stExpander"] summary,
.st-key-sidebar-settings [data-testid="stExpander"] summary,
.st-key-sidebar-developer [data-testid="stExpander"] summary {
  position:relative; min-height:46px; padding:11px 12px 11px 42px !important;
  color:var(--text-secondary); border-radius:10px;
}
.st-key-sidebar-help [data-testid="stExpander"] summary:hover,
.st-key-sidebar-settings [data-testid="stExpander"] summary:hover,
.st-key-sidebar-developer [data-testid="stExpander"] summary:hover {
  color:var(--legal-ink); background:var(--legal-wash);
}
.st-key-sidebar-help [data-testid="stExpander"] summary::before,
.st-key-sidebar-settings [data-testid="stExpander"] summary::before,
.st-key-sidebar-developer [data-testid="stExpander"] summary::before {
  position:absolute; left:13px; top:50%; width:18px; height:18px; transform:translateY(-50%);
  background:currentColor; content:""; opacity:.9;
  -webkit-mask-position:center; -webkit-mask-repeat:no-repeat; -webkit-mask-size:contain;
  mask-position:center; mask-repeat:no-repeat; mask-size:contain;
}
.st-key-sidebar-help [data-testid="stExpander"] summary::before {
  -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='9' fill='none' stroke='black' stroke-width='1.8'/%3E%3Cpath d='M9.7 9a2.45 2.45 0 0 1 4.7 1c0 1.7-2.4 2-2.4 3.7M12 17.3v.1' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");
  mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='9' fill='none' stroke='black' stroke-width='1.8'/%3E%3Cpath d='M9.7 9a2.45 2.45 0 0 1 4.7 1c0 1.7-2.4 2-2.4 3.7M12 17.3v.1' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");
}
.st-key-sidebar-settings [data-testid="stExpander"] summary::before,
.st-key-sidebar-developer [data-testid="stExpander"] summary::before {
  -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M4 7h5m4 0h7M4 17h8m4 0h4M9 4v6m7 4v6' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3Ccircle cx='11' cy='7' r='2' fill='black'/%3E%3Ccircle cx='14' cy='17' r='2' fill='black'/%3E%3C/svg%3E");
  mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M4 7h5m4 0h7M4 17h8m4 0h4M9 4v6m7 4v6' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3Ccircle cx='11' cy='7' r='2' fill='black'/%3E%3Ccircle cx='14' cy='17' r='2' fill='black'/%3E%3C/svg%3E");
}
.st-key-sidebar-help [data-testid="stExpanderDetails"] p { font-size:12px; line-height:1.6; }
.st-key-sidebar-settings [data-testid="stExpanderDetails"],
.st-key-sidebar-developer [data-testid="stExpanderDetails"] { padding:0 14px 14px; }
.st-key-sidebar-settings [data-testid="stSelectbox"] { margin-top:2px; }
.st-key-developer-settings { padding-top:4px; }
.ga-sidebar-empty { padding:12px 2px; color:var(--legal-muted); font-size:12px; line-height:1.65; }
.st-key-sidebar-footer { margin-top:auto; padding-top:24px; }
.ga-toggle-label { margin:4px 0 6px; color:var(--text-secondary); font-size:12px; font-weight:500; }
[class*="st-key-choice_"] button {
  min-height:36px !important; padding:4px 8px !important; border-color:var(--border-subtle) !important;
  background:var(--legal-panel) !important; color:var(--text-secondary) !important; font-size:12px !important;
}
[class*="st-key-choice_"][class*="_selected"] button {
  background:var(--legal-accent-soft) !important; color:var(--legal-accent-text) !important;
  border-color:color-mix(in srgb, var(--legal-accent) 35%, transparent) !important;
}
[data-testid="stSegmentedControl"] button {
  background:transparent; border-color:var(--border-subtle); color:var(--text-secondary); font-weight:500;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] button[aria-selected="true"],
[data-testid="stSegmentedControl"] button[aria-checked="true"] {
  background:var(--legal-accent-soft); color:var(--legal-accent-text); border-color:var(--legal-line);
}

/* Header and landing bring the question field above the fold. */
.st-key-app-header { max-width:var(--content-width); margin:0 auto; padding:0 0 12px; }
.st-key-app-header [data-testid="stHorizontalBlock"] { align-items:center; flex-wrap:nowrap; }
.ga-header {
  display:flex; align-items:center; gap:12px; min-height:48px; padding:10px 0 8px;
  border-bottom:1px solid var(--border-subtle);
}
.ga-page-title h2 { margin:0; padding:0; font-size:18px; font-weight:650; line-height:1.35; }
.ga-page-title p { margin:0; color:var(--legal-muted); font-size:12px; }
.ga-top-controls { margin-left:auto; display:flex; align-items:center; gap:8px; }
.st-key-theme-toggle { display:flex; justify-content:flex-end; }
.st-key-theme-toggle button {
  width:36px !important; min-width:36px !important; height:36px !important; min-height:36px !important;
  padding:0 !important; border-radius:10px !important; background:transparent !important;
  border:1px solid var(--border-subtle) !important; color:var(--text-secondary) !important;
}
.st-key-theme-toggle button:hover { background:var(--legal-wash) !important; }
.ga-mode {
  display:inline-flex; align-items:center; gap:5px; padding:3px 8px; border-radius:6px;
  background:var(--legal-wash); color:var(--legal-muted); font-size:11px; line-height:1.5; font-weight:500;
}
.ga-mode.demo { background:var(--legal-accent-soft); color:var(--legal-accent-text); }
.ga-mode.blocked { color:var(--danger); }
.ga-mode i { width:5px; height:5px; border-radius:50%; background:currentColor; }
.ga-hero {
  max-width:760px; margin:28px auto 14px; padding:26px 30px 24px; text-align:center;
  border:1px solid var(--border-subtle); border-radius:var(--radius-xl);
  background:linear-gradient(145deg, color-mix(in srgb, var(--legal-panel) 72%, transparent), color-mix(in srgb, var(--legal-accent-soft) 26%, transparent));
  box-shadow:var(--shadow-sm);
}
.ga-eyebrow {
  display:inline-flex; align-items:center; min-height:24px; padding:3px 9px; border-radius:999px;
  background:var(--legal-accent-soft); color:var(--legal-accent-text);
  font-size:11px; font-weight:650; letter-spacing:.035em;
}
.ga-hero h1 {
  margin:16px 0 12px; padding:0; color:var(--legal-ink);
  font-size:clamp(32px, 3.9vw, 48px); font-weight:720; line-height:1.12; letter-spacing:-1.35px;
}
.ga-hero p { max-width:600px; margin:0 auto; color:var(--text-secondary); font-size:15px; font-weight:450; line-height:1.75; }
[class*="st-key-scope-selector-"] { max-width:var(--reading-width); margin:0 auto 10px; }
[class*="st-key-scope-selector-"] [data-testid="stHorizontalBlock"] {
  max-width:var(--reading-width); margin:0 auto; align-items:center; justify-content:flex-start; gap:8px; flex-wrap:nowrap;
}
.ga-scope-inline-label {
  min-height:34px; display:flex; align-items:baseline; justify-content:flex-start; gap:6px; white-space:nowrap;
}
.ga-scope-inline-label strong { color:var(--legal-ink); font-size:12px; font-weight:700; }
.ga-scope-inline-label span { color:var(--legal-muted); font-size:11px; line-height:1.4; }
[class*="st-key-scope-selector-"] [data-testid="stSelectbox"] { width:150px; min-width:150px; }
[class*="st-key-scope-selector-"] [data-testid="stSelectbox"] > div { margin:0; }
[class*="st-key-scope-selector-"] [data-baseweb="select"] > div {
  min-height:34px; border-radius:var(--radius-md); border-color:var(--border-subtle);
  background:color-mix(in srgb, var(--surface-elevated) 78%, var(--legal-accent-soft)) !important;
}
[class*="st-key-scope-selector-"] [data-baseweb="select"] span,
[class*="st-key-scope-selector-"] [data-baseweb="select"] div { font-size:12px; }
[class*="st-key-scope-selector-"] [data-testid="stWidgetLabel"] { display:none; }
[data-testid="stForm"] {
  max-width:var(--reading-width); margin:0 auto; padding:16px 18px 13px;
  border:1px solid color-mix(in srgb, var(--legal-accent) 28%, var(--legal-line)); border-radius:var(--radius-xl);
  background:color-mix(in srgb, var(--legal-panel) 88%, var(--legal-accent-soft)); box-shadow:var(--shadow-md);
}
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap:.5rem; }
[data-testid="stForm"] [data-testid="stHorizontalBlock"] { align-items:center; flex-wrap:nowrap; }
[data-testid="stForm"]:focus-within, [data-testid="stChatInput"]:focus-within {
  border-color:var(--legal-accent); box-shadow:0 0 0 2px color-mix(in srgb, var(--legal-accent) 15%, transparent);
}
[data-testid="stForm"] [data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stForm"] [data-testid="stTextArea"] [data-baseweb="base-input"] {
  border:0 !important; box-shadow:none !important; background:transparent !important;
}
[data-testid="stForm"] [data-testid="stTextArea"] textarea {
  padding:4px 0 !important; font-size:16px; line-height:1.6; resize:vertical; min-height:72px;
}
[data-testid="stFormSubmitButton"] button { min-height:38px; padding:6px 15px; font-size:13px; }
.ga-composer-meta, .ga-shortcut { display:flex; align-items:center; min-height:34px; color:var(--legal-muted); font-size:11px; }
.ga-shortcut { justify-content:flex-end; white-space:nowrap; }
.ga-landing-meta, .ga-landing-status { max-width:var(--reading-width); margin:0 auto; color:var(--legal-muted); font-size:11px; text-align:center; }
.ga-examples { max-width:var(--reading-width); margin:8px auto 0; }
.ga-examples .ga-section-label { margin:0; font-size:11px; }
.st-key-landing-examples { max-width:var(--reading-width); margin:0 auto; }
.st-key-landing-examples [data-testid="stHorizontalBlock"] { gap:10px; }
[class*="st-key-example-"] button {
  width:100%; min-height:76px !important; padding:12px 14px !important;
  justify-content:flex-start !important; text-align:left !important;
  border:1px solid var(--border-subtle) !important; background:transparent !important;
  color:var(--text-secondary) !important; border-radius:var(--radius-lg) !important;
}
[class*="st-key-example-"] button p { font-size:12px !important; line-height:1.6 !important; text-align:left; }
[class*="st-key-example-"] button strong { display:block; margin-bottom:4px; font-size:11px; font-weight:500; color:var(--legal-muted); }
[class*="st-key-example-"] button:hover { background:var(--legal-panel) !important; border-color:var(--legal-line) !important; }
.ga-value-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:24px; max-width:var(--reading-width); margin:28px auto 0; }
.ga-value-block { color:var(--legal-muted); font-size:12px; line-height:1.7; }
.ga-value-block strong { display:block; margin-bottom:6px; color:var(--text-secondary); font-size:12px; font-weight:500; }
.ga-legal-disclaimer { max-width:680px; margin:18px auto 0; color:var(--legal-muted); font-size:11px; line-height:1.6; text-align:center; }

/* Conversation: restrained user bubble, open and readable assistant answer. */
[class*="st-key-answer-thread-"] { max-width:var(--reading-width); margin:0 auto; padding-top:16px; }
.ga-turn-divider { max-width:var(--reading-width); height:1px; background:var(--border-subtle); margin:26px auto 0; }
.ga-chat-question { margin:0 0 24px; }
.ga-user-bubble-wrap { display:flex; justify-content:flex-end; align-items:flex-end; gap:10px; }
.ga-user-bubble {
  max-width:min(85%, 650px); padding:13px 18px; border-radius:var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  background:var(--surface-secondary); color:var(--legal-ink); font-size:15px;
  font-weight:550; line-height:1.65; overflow-wrap:anywhere;
}
.ga-chat-time { margin:0 0 6px; text-align:right; font-size:10px; color:var(--legal-muted); }
.ga-user-avatar, .ga-assistant-avatar { display:none; }
[class*="st-key-answer-card-"] { padding:0; background:transparent; }
.ga-answer-heading { display:flex; align-items:center; gap:7px; margin:0 0 14px; color:var(--legal-accent-text); font-size:12px; font-weight:500; }
.ga-answer-heading small { margin-left:auto; font-size:11px; color:var(--legal-muted); font-weight:400; }
.ga-answer-sigil { color:var(--legal-accent); font-size:13px; }
.ga-answer-article { color:var(--text-secondary); font-size:15px; line-height:1.7; overflow-wrap:anywhere; }
.ga-answer-line { margin:0 0 16px; color:var(--text-secondary); font-size:15px; line-height:1.7; font-weight:400; }
.ga-answer-line:last-child { margin-bottom:0; }
.ga-citation-link {
  display:inline-flex; align-items:center; min-height:22px; margin:0 2px; padding:0 5px;
  border-radius:5px; background:var(--legal-accent-soft); color:var(--legal-accent-text);
  font:500 11px/1.55 var(--legal-mono); text-decoration:none;
}
.ga-citation-link:hover { background:var(--surface-tertiary); color:var(--legal-accent-text); text-decoration:none; }
[class*="st-key-citation-controls-"] {
  position:absolute; width:1px; height:1px; overflow:hidden; opacity:0; pointer-events:none;
}
[class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] p,
[class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] li {
  font-size:15px; line-height:1.7; font-weight:400; color:var(--text-secondary); overflow-wrap:anywhere;
}
[class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] h2 { font-size:20px; line-height:1.4; padding-top:12px; }
[class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] h3 { font-size:17px; line-height:1.5; padding-top:10px; }
.ga-answer-marker { display:none; }
.ga-turn-scroll-anchor { scroll-margin-top:22px; height:1px; }
.ga-answer-space { height:4px; }
[class*="st-key-citation-line-"] { flex-wrap:wrap; align-items:baseline !important; column-gap:4px !important; row-gap:3px !important; }
[class*="st-key-citation-line-"] [data-testid="stMarkdownContainer"] p { margin:0; }
[class*="st-key-citation-line-"] [data-testid="stButton"] button {
  min-height:24px !important; height:24px; padding:1px 5px !important;
  background:var(--legal-accent-soft) !important; border:0 !important; color:var(--legal-accent-text) !important;
  border-radius:5px !important; font-size:11px !important; font-weight:500 !important;
}
[class*="st-key-citation-line-"] [data-testid="stButton"] button:hover { background:var(--surface-tertiary) !important; }
.ga-answer-actions-rule { height:1px; background:var(--border-subtle); margin:16px 0 4px; }
[class*="st-key-copy-answer"] button, [class*="st-key-helpful-answer"] button,
[class*="st-key-not-helpful-answer"] button, [class*="st-key-evidence-answer"] button {
  min-height:34px; padding:5px 9px; background:transparent; border-color:transparent; color:var(--legal-muted); font-size:11px;
}
[class*="st-key-evidence-answer"] button { color:var(--legal-accent-text); }
[class*="st-key-evidence-answer"] button p { width:100%; margin:0; text-align:center !important; }
[class*="st-key-answer-primary-source-"] { max-width:180px; margin:8px 0 0; }
.ga-answer-source-strip { display:flex; align-items:center; gap:8px; padding:8px 0; font-size:12px; color:var(--legal-muted); }
.ga-answer-source-strip strong { color:var(--text-secondary); font-weight:500; }
.ga-answer-source-strip em { font-size:11px; font-style:normal; }
/* Compact source rows share the evidence action with inline citations. */
.ga-sources-heading { display:flex; align-items:center; gap:8px; margin:20px 0 8px; }
.ga-sources-heading h2 { margin:0; padding:0; color:var(--text-secondary); font-size:13px; font-weight:600; }
.ga-sources-heading span { font-size:12px; color:var(--legal-accent); }
.ga-sources-heading em { margin-left:auto; font-size:11px; color:var(--legal-muted); font-style:normal; }
.ga-source-subheading { margin:14px 2px 7px; color:var(--legal-muted); font-size:12px; font-weight:550; }
[class*="st-key-source-row-"] { padding:13px 15px; border-radius:var(--radius-md); background:var(--legal-wash); }
.ga-source-scroll-anchor { display:block; scroll-margin-top:24px; height:1px; }
[class*="st-key-source-row-"] [data-testid="stHorizontalBlock"] { align-items:center; gap:12px; }
.ga-source-row-title { display:flex; gap:8px; align-items:baseline; }
.ga-source-row-title h3 { margin:0; padding:0; color:var(--legal-ink); font-size:13px; font-weight:550; line-height:1.6; }
.ga-source-row-title span, .ga-source-id { flex-shrink:0; color:var(--legal-accent-text); font:500 11px/1.6 var(--legal-mono); }
.ga-source-row-main p { margin:4px 0 0; color:var(--legal-muted); font-size:12px !important; line-height:1.65 !important; }
.ga-source-meta { margin:5px 0; color:var(--legal-muted); font-size:11px; line-height:1.55; }
[class*="st-key-view-source-tab"] button { font-size:11px; background:transparent; border-color:transparent; color:var(--legal-accent-text); }
.ga-source-excerpt { color:var(--legal-muted); font-size:12px; line-height:1.65; }
.ga-doc-symbol { color:var(--legal-accent-text); font-size:20px; }
.ga-retrieved-title { margin:20px 0 8px; font-size:13px; font-weight:500; }
.ga-extra-source { padding:10px 0; border-top:1px solid var(--border-subtle); font-size:12px; color:var(--legal-muted); }
.ga-extra-source strong { color:var(--text-secondary); }
.ga-extra-source em { font-style:normal; font-family:var(--legal-mono); }

/* One evidence surface: desktop overlay drawer and a mobile sheet.
   BaseWeb owns focus trapping, Escape, backdrop dismissal and scroll locking. */
[data-testid="stDialog"] {
  display:flex !important; justify-content:flex-end !important; align-items:stretch !important;
  padding:0 !important; background:rgba(4,15,12,.25);
}
[data-testid="stDialog"] > div {
  width:min(520px, 100vw) !important; max-width:520px !important; height:100dvh !important;
  max-height:100dvh !important; margin:0 0 0 auto !important; border-radius:0 !important;
  background:var(--legal-panel) !important; box-shadow:var(--shadow-lg);
}
[data-testid="stDialog"] [role="dialog"] {
  width:100%; max-width:none; height:100dvh; max-height:100dvh;
  margin:0 !important; border:0 !important; border-radius:0 !important;
  background:var(--legal-panel) !important; color:var(--legal-ink);
}
[data-testid="stDialog"] [role="dialog"] > div {
  max-height:100dvh; overflow-y:auto; overflow-x:hidden; padding:28px 28px 36px;
  scrollbar-color:var(--border-strong) var(--legal-wash); scrollbar-width:thin;
}
[data-testid="stDialog"] button[aria-label="Close"] {
  top:19px; right:20px; width:32px; height:32px; border:0 !important;
  background:transparent !important; color:var(--legal-muted) !important; box-shadow:none !important;
}
[data-testid="stDialog"] button[aria-label="Close"]:hover { background:var(--legal-wash) !important; color:var(--legal-ink) !important; }
[data-testid="stDialog"] button[aria-label="Close"] svg { fill:currentColor !important; }
[data-testid="stDialog"] [role="dialog"] > div::-webkit-scrollbar { width:7px; }
[data-testid="stDialog"] [role="dialog"] > div::-webkit-scrollbar-track { background:var(--legal-wash); }
[data-testid="stDialog"] [role="dialog"] > div::-webkit-scrollbar-thumb { background:var(--border-strong); border-radius:8px; }
[data-testid="stDialog"] [data-testid="stDialogHeader"] { color:var(--legal-muted); font-size:12px; font-weight:500; }
.ga-evidence-drawer { height:0; }
.ga-dialog-title, .ga-dialog-meta { overflow-wrap:anywhere; }
.ga-dialog-title > span { color:var(--legal-accent-text); font-size:11px; }
.ga-dialog-title h2 { margin:8px 0 12px; padding:0; color:var(--legal-ink); font-size:23px; font-weight:600; line-height:1.4; }
.ga-dialog-title p { margin:0; color:var(--legal-muted); font-size:12px; line-height:1.7; }
.ga-dialog-meta { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
.ga-dialog-meta span { padding:4px 7px; border-radius:5px; background:var(--legal-wash); color:var(--legal-muted); font-size:11px; }
[data-testid="stTabs"] [role="tablist"] { gap:18px; border-bottom:1px solid var(--border-subtle); }
[data-testid="stTabs"] button { background:transparent; color:var(--legal-muted); font-size:12px; font-weight:500; }
[data-testid="stTabs"] button p { color:inherit; font-size:inherit; }
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--legal-accent-text); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:var(--legal-accent); }
.ga-cited-excerpt, .ga-evidence-highlight {
  margin:12px 0; padding:16px 18px; border-left:3px solid var(--legal-accent);
  border-radius:0 var(--radius-md) var(--radius-md) 0; background:var(--legal-accent-soft);
  white-space:pre-wrap; overflow-wrap:anywhere; color:var(--text-secondary); font-size:14px; line-height:1.75;
}
.ga-source-text, .ga-readable-excerpt { white-space:pre-wrap; overflow-wrap:anywhere; color:var(--text-secondary); font-size:14px; line-height:1.75; }
.ga-source-text { padding:14px 0; }
.ga-document-info { display:grid; gap:0; margin:8px 0 14px; border:1px solid var(--border-subtle); border-radius:var(--radius-md); overflow:hidden; }
.ga-document-info-row { display:grid; grid-template-columns:minmax(105px, .75fr) minmax(0, 1.25fr); gap:12px; padding:10px 12px; border-top:1px solid var(--border-subtle); }
.ga-document-info-row:first-child { border-top:0; }
.ga-document-info dt { margin:0; color:var(--legal-muted); font-size:11px; line-height:1.55; }
.ga-document-info dd { margin:0; color:var(--text-secondary); font-size:12px; line-height:1.55; overflow-wrap:anywhere; }

/* Follow-up stays in Streamlit's bottom area with its query scope. */
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div { background:var(--page-bg) !important; }
[data-testid="stBottomBlockContainer"] { padding:0 32px 18px; }
.st-key-followup-composer {
  max-width:var(--reading-width); margin:0 auto; padding:10px 0 0;
  background:var(--surface-elevated); border-top:1px solid var(--border-subtle);
}
.st-key-followup-composer > [data-testid="stVerticalBlock"] { gap:5px; }
[data-testid="stChatInput"] {
  background:transparent !important; border:0 !important; border-radius:var(--radius-lg); box-shadow:none !important;
}
[data-testid="stChatInput"] > div {
  background:var(--legal-panel) !important; border:1px solid var(--legal-line) !important;
  border-radius:var(--radius-lg) !important; box-shadow:var(--shadow-sm);
}
[data-testid="stChatInput"] [data-baseweb="textarea"], [data-testid="stChatInput"] [data-baseweb="base-input"] {
  background:transparent !important; border:0 !important;
}
[data-testid="stChatInput"] textarea { font-size:14px; line-height:1.65; }
[data-testid="stChatInputSubmitButton"] {
  background:var(--legal-accent) !important; color:var(--text-inverse) !important;
  border:0 !important; border-radius:9px !important; box-shadow:none !important;
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) { background:var(--accent-hover) !important; }
[data-testid="stChatInputSubmitButton"]:disabled { opacity:.45; }
[data-testid="stChatInputSubmitButton"] svg { fill:currentColor !important; }

/* Notifications and secondary states follow the active appearance. */
[data-testid="stToast"] {
  background:var(--legal-panel) !important; color:var(--legal-ink) !important;
  border:1px solid var(--border-subtle) !important; border-radius:var(--radius-md) !important;
  filter:none !important; box-shadow:var(--shadow-lg) !important;
}
[data-testid="stToast"] [data-testid="stToastText"],
[data-testid="stToast"] [data-testid="stToastText"] * {
  color:var(--legal-ink) !important; -webkit-text-fill-color:var(--legal-ink) !important;
}
[data-testid="stToast"] button[aria-label="Close"] { color:var(--legal-muted) !important; background:transparent !important; }
.ga-section-label { margin:18px 0 8px; color:var(--legal-muted); font-size:12px; font-weight:500; }
.ga-state { max-width:var(--reading-width); margin:16px auto; padding:20px; background:var(--legal-wash); border-radius:var(--radius-lg); }
.ga-state h3 { margin:0 0 8px; color:var(--legal-ink); font-size:17px; font-weight:600; }
.ga-state p { margin:0; color:var(--text-secondary); font-size:13px; line-height:1.7; }
.ga-palette-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.ga-metric-label, .ga-metric-unit { color:var(--legal-muted); font-size:11px; }
.ga-metric-value { color:var(--legal-ink); font-size:22px; font-weight:550; }

/* Preserve native navigation and separately scrolling evidence on tablets. */
@media (max-width:1023px) {
  :root { --sidebar-width:260px; }
  [data-testid="stMainBlockContainer"] { padding-inline:24px; }
  [data-testid="stBottomBlockContainer"] { padding-inline:24px; }
  .ga-hero { margin-top:24px; }
  .ga-hero h1 { font-size:36px; }
  .ga-value-grid { gap:18px; }
}
@media (max-width:640px) {
  [data-testid="stMainBlockContainer"] { padding:14px 18px 9rem; }
  [data-testid="stBottomBlockContainer"] { padding:0 12px max(12px, env(safe-area-inset-bottom)); }
  [data-testid="stSidebar"][aria-expanded="true"] { max-width:85vw !important; }
  .st-key-app-header { padding-left:28px; padding-bottom:8px; }
  .st-key-app-header [data-testid="stColumn"] { min-width:0 !important; }
  .st-key-app-header [data-testid="stColumn"]:last-child { flex:0 0 36px !important; }
  .ga-hero { margin:14px auto 2px; text-align:left; }
  .ga-hero h1 { margin:13px 0; font-size:32px; line-height:1.2; letter-spacing:-.8px; }
  .ga-hero p { font-size:14px; line-height:1.7; }
  .ga-eyebrow { font-size:11px; }
  [data-testid="stForm"] { padding:12px; }
  [data-testid="stForm"] [data-testid="stTextArea"] textarea { font-size:16px; }
  [data-testid="stForm"] [data-testid="stColumn"] { min-width:0 !important; }
  .ga-shortcut { display:none; }
  [class*="st-key-scope-selector-"] [data-testid="stColumn"] { min-width:0 !important; }
  [class*="st-key-scope-selector-"] [data-testid="stCaptionContainer"] { display:none; }
  .st-key-landing-examples [data-testid="stHorizontalBlock"] { flex-direction:column; gap:8px; }
  .st-key-landing-examples [data-testid="stColumn"] { width:100% !important; flex:1 1 100%; }
  [class*="st-key-example-"] button { min-height:52px !important; padding:10px 12px !important; }
  [class*="st-key-example-"] button strong { display:inline; margin-right:6px; }
  .ga-value-grid { grid-template-columns:1fr; gap:14px; margin-top:18px; }
  .ga-value-block strong { margin-bottom:2px; }
  .ga-legal-disclaimer { text-align:left; font-size:10px; }
  .ga-user-bubble { max-width:92%; padding:12px 14px; font-size:14px; }
  [class*="st-key-answer-thread-"] { padding-top:12px; }
  [class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] p,
  [class*="st-key-answer-card-"] [data-testid="stMarkdownContainer"] li { font-size:14px; }
  .ga-answer-article, .ga-answer-line { font-size:14px; }
  [class*="st-key-source-row-"] { padding:12px; }
  [class*="st-key-source-row-"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap; }
  [class*="st-key-source-row-"] [data-testid="stColumn"] { min-width:0 !important; }
  [class*="st-key-source-row-"] [data-testid="stColumn"]:last-child { flex:0 0 78px !important; }
  [data-testid="stDialog"] > div { width:100vw !important; max-width:100vw !important; }
  [data-testid="stDialog"] [role="dialog"] > div { padding:24px 18px max(24px, env(safe-area-inset-bottom)); }
  [data-testid="stDialog"] button[aria-label="Close"] { top:15px; right:14px; }
  .ga-dialog-title h2 { font-size:21px; }
  [data-testid="stTabs"] [role="tablist"] { gap:14px; overflow-x:auto; }
  .ga-cited-excerpt { padding:14px; }
  .ga-palette-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { scroll-behavior:auto !important; transition:none !important; animation:none !important; }
}
"""


__all__ = ["build_application_css"]
