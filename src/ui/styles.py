"""Application CSS for the legal document retrieval Streamlit UI."""
from __future__ import annotations

from .theme import build_theme_css


def build_application_css(theme_choice: str = "System") -> str:
    return build_theme_css(theme_choice) + """
:root {
  --legal-sans: "Work Sans", Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --legal-serif: var(--legal-sans);
  --legal-mono: "DM Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --legal-ink: var(--text-primary);
  --legal-muted: var(--text-muted);
  --legal-line: var(--border-default);
  --legal-panel: var(--surface-primary);
  --legal-wash: var(--surface-secondary);
  --legal-accent: var(--accent);
  --legal-accent-soft: var(--accent-soft);
  --legal-side: var(--surface-primary);
  --legal-side-line: var(--border-default);
  --legal-side-text: var(--text-primary);
  --legal-side-dim: var(--text-muted);
  --legal-side-control: var(--surface-primary);
  --legal-side-control-hover: var(--surface-secondary);
}

html, body, [class*="css"] { font-family: var(--legal-sans); letter-spacing:0; }
[data-testid="stAppViewContainer"] { background: var(--page-bg); color: var(--legal-ink); }
[data-testid="stMainBlockContainer"] { max-width: none; padding: 0 0 6rem; margin: 0; }
[data-testid="stHeader"] { height: 0; background: transparent; }
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] { visibility: hidden; }
p, li { color: var(--text-secondary); }
a { color: var(--legal-accent); }
code, pre { font-family: var(--legal-mono); }
*:focus-visible { outline: 2px solid color-mix(in srgb, var(--legal-accent) 72%, transparent); outline-offset: 2px; }

/* Toasts render in Streamlit's global notification layer, outside the app content tree. */
[data-testid="stToast"] {
  background:var(--legal-panel) !important;
  border:1px solid var(--legal-line) !important;
  border-radius:var(--radius-md) !important;
  color:var(--legal-ink) !important;
  filter:none !important;
  box-shadow:var(--shadow-lg) !important;
}
[data-testid="stToast"] [data-testid="stToastText"],
[data-testid="stToast"] [data-testid="stToastText"] * {
  color:var(--legal-ink) !important;
  -webkit-text-fill-color:var(--legal-ink) !important;
}
[data-testid="stToast"] button[aria-label="Close"] {
  background:transparent !important;
  border:0 !important;
  color:var(--legal-muted) !important;
  box-shadow:none !important;
}
[data-testid="stToast"] button[aria-label="Close"]:hover {
  background:var(--legal-wash) !important;
  color:var(--legal-ink) !important;
}
[data-testid="stToast"] button[aria-label="Close"] svg {
  fill:currentColor !important;
}
[data-testid="stToast"] [data-testid="stToastViewButton"] {
  color:var(--legal-accent-text) !important;
}

[data-testid="stButton"] button,
[data-testid="stLinkButton"] a {
  border:1px solid var(--legal-line);
  background:var(--legal-panel);
  color:var(--legal-ink);
  box-shadow:0 1px 2px rgba(24,33,31,.05);
  transition:border-color .16s ease, background .16s ease, box-shadow .16s ease, transform .16s ease;
}
[data-testid="stButton"] button:hover,
[data-testid="stLinkButton"] a:hover {
  border-color:color-mix(in srgb, var(--legal-accent) 44%, var(--legal-line));
  background:color-mix(in srgb, var(--legal-accent-soft) 38%, var(--legal-panel));
  color:var(--legal-accent-text);
  box-shadow:0 8px 18px rgba(24,33,31,.08);
  transform:translateY(-1px);
}
[data-testid="stButton"] button p,
[data-testid="stLinkButton"] a p {
  color:inherit !important;
  font-size:inherit !important;
  font-weight:inherit !important;
  line-height:inherit !important;
}
[data-testid="stButton"] button:disabled,
[data-testid="stFormSubmitButton"] button:disabled {
  border-color:var(--legal-line);
  background:var(--surface-tertiary);
  color:var(--text-muted);
  opacity:.78;
  box-shadow:none;
  transform:none;
}
[data-testid="collapsedControl"] {
  position:fixed !important;
  top:16px !important;
  left:0 !important;
  z-index:100000 !important;
  transform:none !important;
}
[data-testid="stSidebarCollapsed"] {
  width:0 !important;
  min-width:0 !important;
}
[data-testid="stSidebarCollapsed"] [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] button {
  position:fixed !important;
  top:16px !important;
  left:8px !important;
  z-index:100001 !important;
  width:42px !important;
  height:42px !important;
  border:1px solid var(--legal-line) !important;
  border-radius:10px !important;
  background:var(--legal-panel) !important;
  color:var(--legal-accent-text) !important;
  box-shadow:0 10px 24px rgba(24,33,31,.10) !important;
}
[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarCollapseButton"] {
  position:static !important;
  width:34px !important;
  height:34px !important;
  box-shadow:none !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  width: 292px !important; min-width: 292px !important; max-width: 292px !important;
  border-right: 1px solid var(--legal-side-line); background: var(--legal-side); color: var(--legal-side-text);
}
[data-testid="stSidebar"][aria-expanded="false"],
section.stSidebarCollapsed,
[data-testid="stSidebarCollapsed"] {
  width:0 !important;
  min-width:0 !important;
  max-width:0 !important;
  margin:0 !important;
  padding:0 !important;
  border-right:0 !important;
  overflow:visible !important;
}
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"],
section.stSidebarCollapsed [data-testid="stSidebarContent"],
[data-testid="stSidebarCollapsed"] [data-testid="stSidebarContent"] {
  display:none !important;
}
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"],
section.stSidebarCollapsed [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsed"] [data-testid="stSidebarCollapseButton"] {
  position:fixed !important;
  top:16px !important;
  left:8px !important;
  z-index:100001 !important;
}
[data-testid="stSidebar"] > div:first-child { background: var(--legal-side); padding: 0 14px 28px; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.58rem; }
.stSidebar [data-testid="stSidebarContent"],
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding:0 14px 28px !important;
  background:var(--legal-side);
}
[data-testid="stSidebarUserContent"] {
  padding-top:0 !important;
  margin-top:0 !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] > div:first-child {
  padding-top:0 !important;
  margin-top:0 !important;
}
.ga-sidebar-brand {
  display:flex; align-items:center; gap:10px; padding: 4px 4px 12px; margin:0 0 4px;
  border-bottom:1px solid var(--legal-side-line);
}
.ga-brand-mark {
  display:grid; place-items:center; width:34px; height:34px;
  border:1px solid color-mix(in srgb, var(--legal-accent) 35%, var(--legal-side-line)); border-radius:8px;
  color:var(--legal-accent-text); background:var(--legal-accent-soft); font: 17px var(--legal-mono);
}
.ga-sidebar-brand strong { display:block; color:var(--legal-side-text); font-size:17px; line-height:1.2; letter-spacing:0; }
.ga-sidebar-brand span { display:block; margin-top:4px; color:var(--legal-side-dim); font: 12px/1.35 var(--legal-sans); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
  margin: 9px 4px 4px; color:var(--legal-side-dim); font: 650 13px var(--legal-sans);
  letter-spacing:0; text-transform:none;
}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p {
  color:var(--legal-side-text); font-size:13px; line-height:1.45; font-weight:500;
}
[data-testid="stSidebar"] label {
  margin-bottom:3px;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"],
[data-testid="stSidebar"] [data-testid="stNumberInput"],
[data-testid="stSidebar"] [data-testid="stToggle"],
[data-testid="stSidebar"] [data-testid="stExpander"] {
  margin-bottom:2px;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  border-color:var(--legal-side-line) !important;
  border-radius:8px;
  min-height:40px;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] div,
[data-testid="stSidebar"] [data-testid="stSelectbox"] span,
[data-testid="stSidebar"] [data-testid="stSelectbox"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="button"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] {
  background-color:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
[data-testid="stSidebar"] [data-baseweb="select"] [aria-haspopup="listbox"],
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="input"] input,
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] div,
[data-testid="stSidebar"] [data-baseweb="input"] div {
  background-color:var(--legal-side-control) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] *,
[data-testid="stSidebar"] [data-baseweb="input"] *,
[data-testid="stSidebar"] input {
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
/* Streamlit 1.62+ renders the select trigger with React Aria, not BaseWeb. */
[data-testid="stSidebar"] [data-testid="stSelectbox"] button[aria-label="Open"] {
  background:transparent !important;
  border:0 !important;
  box-shadow:none !important;
  color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] button[aria-label="Open"] svg {
  color:inherit !important;
  fill:none !important;
  stroke:none !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] button[aria-label="Open"] svg path[fill="none"] {
  fill:none !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] button[aria-label="Open"] svg path:not([fill="none"]) {
  fill:currentColor !important;
}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"],
[role="listbox"] {
  background:var(--legal-side-control) !important;
  border:1px solid var(--legal-side-line) !important;
  border-radius:8px !important;
  box-shadow:var(--shadow-lg) !important;
  color:var(--legal-side-text) !important;
}
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] li,
[role="listbox"] [role="option"] {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] li:hover,
[role="listbox"] [role="option"]:hover,
[role="listbox"] [role="option"][aria-selected="true"] {
  background:var(--legal-side-control-hover) !important;
  color:var(--legal-accent-text) !important;
  -webkit-text-fill-color:var(--legal-accent-text) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button {
  justify-content:flex-start; min-height:38px; border:1px solid var(--legal-side-line); border-radius:7px; padding:8px 10px;
  background:var(--legal-side-control); color:var(--legal-side-text); font-size:13px; font-weight:650;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
  border-color:color-mix(in srgb, var(--legal-accent) 38%, var(--legal-side-line));
  background:var(--legal-side-control-hover); color:var(--legal-accent-text); transform:none;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"],
[data-testid="stSidebar"] [data-testid="stNumberInput"] > div,
[data-testid="stSidebar"] [data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-testid="stNumberInput"] [data-baseweb="input"] > div {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  border-color:var(--legal-side-line) !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
  min-width:36px !important;
  border:1px solid var(--legal-side-line) !important;
  border-left:0 !important;
  border-radius:0 !important;
  background:var(--legal-side-control-hover) !important;
  color:var(--legal-side-text) !important;
  box-shadow:none !important;
  transform:none !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button:hover {
  background:color-mix(in srgb, var(--legal-accent-soft) 42%, var(--legal-side-control-hover)) !important;
  color:var(--legal-accent-text) !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button p,
[data-testid="stSidebar"] [data-testid="stNumberInput"] button span,
[data-testid="stSidebar"] [data-testid="stNumberInput"] button svg {
  color:var(--legal-side-text) !important;
  fill:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="InputInstructions"] { display:none !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:var(--legal-side-dim); font: 12px/1.4 var(--legal-sans); }
[data-testid="stSidebar"] [data-testid="stExpander"] {
  background:var(--legal-side-control); border:1px solid var(--legal-side-line); border-radius:9px;
  color:var(--legal-side-text);
}
[data-testid="stSidebar"] [data-testid="stExpander"] *,
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  color:var(--legal-side-text) !important;
}
[data-testid="stSidebar"] hr { border-color: var(--legal-side-line); }

/* Topbar */
.ga-header {
  min-height:84px; display:flex; align-items:center; justify-content:space-between; gap:18px;
  padding:14px 36px 16px; border-bottom:1px solid var(--legal-line);
  background: color-mix(in srgb, var(--legal-panel) 88%, transparent);
}
.ga-page-title h2 {
  margin:0; color:var(--legal-ink); font:650 22px/1.2 var(--legal-serif); letter-spacing:0;
}
.ga-page-title p { margin:10px 0 0; color:var(--legal-muted); font-size:15px; line-height:1.55; }
.ga-top-controls { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
.ga-compact-select, .ga-context-pill {
  display:inline-flex; align-items:center; gap:10px; min-height:38px; padding:0 11px;
  border:1px solid var(--legal-line); border-radius:8px; color:var(--text-secondary);
  background:var(--legal-panel); font-size:13px;
}
.ga-context-pill { cursor:default; color:var(--legal-muted); background:var(--legal-wash); }
.ga-mode {
  display:inline-flex; align-items:center; gap:7px; min-height:29px; padding:0 10px;
  border:1px solid var(--border-default); border-radius:8px; color:var(--success);
  background:color-mix(in srgb, var(--success) 12%, var(--legal-panel)); font: 500 12px var(--legal-mono);
}
.ga-mode i, .ga-status-dot {
  width:7px; height:7px; border-radius:50%; background:var(--success);
  box-shadow:0 0 0 3px color-mix(in srgb, var(--success) 18%, transparent);
}
.ga-mode.production { color:var(--success); border-color:color-mix(in srgb, var(--success) 32%, var(--legal-line)); background:color-mix(in srgb, var(--success) 12%, var(--legal-panel)); }
.ga-mode.production i { background:var(--success); box-shadow:0 0 0 3px color-mix(in srgb, var(--success) 16%, transparent); }
.ga-mode.demo { color:var(--info); border-color:color-mix(in srgb, var(--info) 36%, var(--legal-line)); background:color-mix(in srgb, var(--info) 10%, var(--legal-panel)); }
.ga-mode.demo i { background:var(--info); box-shadow:0 0 0 3px color-mix(in srgb, var(--info) 16%, transparent); }
.ga-mode.blocked { color:var(--danger); border-color:color-mix(in srgb, var(--danger) 34%, var(--legal-line)); background:color-mix(in srgb, var(--danger) 10%, var(--legal-panel)); }
.ga-mode.blocked i { background:var(--danger); box-shadow:0 0 0 3px color-mix(in srgb, var(--danger) 16%, transparent); }

/* Landing */
.ga-hero { max-width:850px; margin: clamp(54px, 9vh, 92px) auto 26px; padding:0 28px; text-align:center; }
.ga-eyebrow {
  color:var(--legal-accent-text); font:700 15px/1.4 var(--legal-sans); letter-spacing:.01em; text-transform:none;
}
.ga-hero h1 {
  margin:20px auto 16px; color:var(--legal-ink);
  font:600 clamp(42px, 5vw, 58px)/1.06 var(--legal-serif); letter-spacing:0;
}
.ga-hero p {
  max-width:720px; margin:22px auto 0; color:var(--text-secondary); font:500 20px/1.58 var(--legal-serif);
}
div[data-testid="stForm"] {
  max-width:940px; margin:0 auto; padding:12px 14px 12px 16px;
  border:1px solid var(--legal-line); border-radius:15px; background:var(--legal-panel);
  box-shadow:0 12px 28px rgba(47,42,34,.08);
}
div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
  gap:.45rem;
}
div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
  align-items:center;
}
div[data-testid="stForm"]:focus-within {
  border-color:var(--legal-accent); box-shadow:0 0 0 3px color-mix(in srgb, var(--legal-accent) 14%, transparent), 0 14px 32px rgba(15,23,42,.08);
}
[data-testid="stTextArea"],
[data-testid="stTextArea"] > div,
[data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stTextArea"] [data-baseweb="base-input"],
[data-testid="stTextArea"] [data-baseweb="base-input"] > div,
[data-testid="stChatInput"],
[data-testid="stChatInput"] [data-baseweb="textarea"],
[data-testid="stChatInput"] [data-baseweb="base-input"],
[data-testid="stChatInput"] [data-baseweb="base-input"] > div,
[data-testid="stTextInput"] [data-baseweb="input"] > div {
  background:var(--legal-panel) !important;
  color:var(--legal-ink) !important;
  border-color:var(--legal-line) !important;
}
[data-testid="stForm"] [data-testid="stTextArea"],
[data-testid="stForm"] [data-testid="stTextArea"] > div,
[data-testid="stForm"] [data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stForm"] [data-testid="stTextArea"] [data-baseweb="base-input"],
[data-testid="stForm"] [data-testid="stTextArea"] [data-baseweb="base-input"] > div {
  border:0 !important;
  box-shadow:none !important;
  padding:0 !important;
}
[data-testid="stTextArea"] textarea,
[data-testid="stChatInput"] textarea,
[data-testid="stTextInput"] input {
  color:var(--legal-ink) !important;
  -webkit-text-fill-color:var(--legal-ink) !important;
  background:var(--legal-panel) !important;
  caret-color:var(--legal-accent);
  border:0 !important; box-shadow:none !important; outline:0 !important;
  font-size:16px; line-height:1.55;
}
[data-testid="stForm"] [data-testid="stTextArea"] textarea {
  min-height:58px !important;
  height:58px !important;
  padding:4px 0 0 !important;
  resize:none;
}
[data-testid="stTextArea"] textarea::selection,
[data-testid="stChatInput"] textarea::selection,
[data-testid="stTextInput"] input::selection {
  background:color-mix(in srgb, var(--legal-accent) 30%, transparent);
  color:var(--legal-ink);
}
[data-testid="stTextArea"] textarea::placeholder,
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stTextInput"] input::placeholder { color:var(--legal-muted) !important; opacity:1; }
[data-testid="stTextArea"] textarea:focus { box-shadow:none; }
[data-testid="stTextArea"] [data-baseweb="base-input"],
[data-testid="stChatInput"] [data-baseweb="base-input"],
[data-testid="stTextInput"] [data-baseweb="input"] > div {
  background:var(--legal-panel) !important;
  color:var(--legal-ink) !important;
  border-color:var(--legal-line) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
  background:var(--legal-side-control) !important;
  color:var(--legal-side-text) !important;
  -webkit-text-fill-color:var(--legal-side-text) !important;
  border-color:var(--legal-side-line) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input::placeholder { color:var(--legal-side-dim) !important; }
[data-testid="stFormSubmitButton"] button {
  min-height:44px; border:1px solid color-mix(in srgb, var(--legal-accent) 72%, var(--legal-line)); border-radius:10px; padding:0 18px;
  background:var(--legal-accent); color:#ffffff !important; -webkit-text-fill-color:#ffffff !important; font-size:15px; font-weight:750;
  display:flex; align-items:center; justify-content:center;
  box-shadow:0 8px 18px color-mix(in srgb, var(--legal-accent) 18%, transparent);
}
[data-testid="stFormSubmitButton"] button *,
[data-testid="stFormSubmitButton"] button p {
  color:#ffffff !important;
  -webkit-text-fill-color:#ffffff !important;
}
[data-testid="stFormSubmitButton"] button:hover {
  border-color:var(--accent-hover); background:var(--accent-hover); color:#ffffff !important;
  box-shadow:0 12px 22px color-mix(in srgb, var(--legal-accent) 24%, transparent);
}
.ga-composer-meta, .ga-shortcut {
  display:flex; align-items:center; min-height:44px; color:var(--legal-muted); font: 13px var(--legal-sans);
}
.ga-shortcut { justify-content:flex-end; color:var(--legal-muted); white-space:nowrap; }
.ga-landing-meta {
  margin:12px auto 26px; display:flex; align-items:center; justify-content:center; gap:9px;
  color:var(--legal-muted); font: 12px var(--legal-mono);
}
.ga-examples { max-width:1014px; margin:0 auto; }
.ga-examples .ga-section-label { display:none; }
.st-key-landing-examples {
  max-width:860px;
  margin:0 auto;
}
.st-key-landing-examples [data-testid="stHorizontalBlock"] {
  gap:14px;
}
[class*="st-key-example-"] button {
  position:relative; min-height:84px; justify-content:flex-start; align-items:flex-start; text-align:left;
  white-space:normal; padding:14px 16px; border:1px solid color-mix(in srgb, var(--legal-line) 80%, var(--legal-accent) 20%);
  border-radius:12px; background:var(--legal-panel); color:var(--legal-ink);
  font:400 14px/1.45 var(--legal-serif); box-shadow:var(--shadow-sm);
}
[class*="st-key-example-"] button p {
  width:100%;
  text-align:left;
  margin:0;
  font-weight:400 !important;
}
[class*="st-key-example-"] button strong {
  display:block;
  margin-bottom:7px;
  color:var(--legal-ink);
  font:750 15px/1.25 var(--legal-sans);
}
[class*="st-key-example-"] button:hover {
  border-color:color-mix(in srgb, var(--legal-accent) 40%, var(--legal-line)); background:color-mix(in srgb, var(--legal-accent-soft) 42%, var(--legal-panel)); transform:translateY(-1px);
}
.ga-landing-status { max-width:1014px; margin:22px auto 0; text-align:center; color:var(--legal-muted); font-size:13px; }

/* Thread and answer */
[class*="st-key-answer-thread-"] { max-width:1040px; margin:0 auto; padding:34px 0 0; }
.ga-chat-question { margin:0 0 24px; }
.ga-chat-time {
  max-width:930px; margin:0 auto 8px; text-align:right; color:var(--legal-muted); font:12px var(--legal-sans);
}
.ga-user-bubble-wrap {
  display:flex; justify-content:flex-end; align-items:center; gap:14px; max-width:930px; margin:0 auto;
}
.ga-user-bubble {
  max-width:min(620px, 72%); padding:18px 22px; border:1px solid var(--legal-line); border-radius:15px;
  background:var(--surface-secondary); color:var(--legal-ink); font:600 16px/1.55 var(--legal-sans);
  box-shadow:var(--shadow-sm);
}
.ga-user-avatar,
.ga-assistant-avatar {
  display:grid; place-items:center; flex:0 0 auto; width:42px; height:42px; border-radius:50%;
  border:1px solid var(--legal-line); background:var(--legal-panel); color:var(--legal-accent);
  font:700 14px var(--legal-sans); box-shadow:var(--shadow-sm);
}
.ga-assistant-avatar {
  margin:5px auto 0; background:var(--legal-accent-soft); color:var(--legal-accent-text);
}
.ga-chat-status {
  display:flex; flex-direction:column; gap:8px; align-items:flex-start; padding-top:4px;
  color:var(--legal-muted); font:11px var(--legal-mono);
}
[class*="st-key-answer-card-"] [data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--legal-line); border-radius:14px; background:var(--legal-panel);
  box-shadow:0 10px 28px rgba(15,23,42,.06);
}
[class*="st-key-answer-card-"] [data-testid="stVerticalBlockBorderWrapper"] > div { padding:22px 24px 18px; }
.ga-answer-heading {
  display:flex; align-items:center; gap:10px; margin-bottom:20px; flex-wrap:wrap;
  color:var(--legal-accent-text); font:600 12px var(--legal-sans);
}
.ga-answer-heading small { margin-left:auto; color:var(--legal-muted); font:11px var(--legal-mono); }
.ga-answer-sigil {
  width:23px; height:23px; display:grid; place-items:center; border-radius:7px;
  background:var(--legal-accent-soft); color:var(--legal-accent-text); font:700 12px var(--legal-sans);
}
.ga-answer-marker { height:0; overflow:hidden; }
.ga-answer-space { height:8px; }
div[data-testid="stVerticalBlock"]:has(.ga-answer-marker) [data-testid="stMarkdownContainer"] > p {
  color:var(--legal-ink); font: 17px/1.76 var(--legal-serif); margin:0 0 17px; letter-spacing:0; word-spacing:0;
}
div[data-testid="stVerticalBlock"]:has(.ga-answer-marker) [data-testid="stMarkdownContainer"] li {
  color:var(--legal-ink); font-size:16px; line-height:1.7; letter-spacing:0; word-spacing:0;
}
[class*="st-key-citation-line-"] { flex-wrap:wrap; align-items:baseline !important; column-gap:4px !important; row-gap:4px !important; }
[class*="st-key-citation-line-"] [data-testid="stMarkdownContainer"] p { margin:0; }
[class*="st-key-citation-line-"] [data-testid="stButton"] button {
  min-width:30px; min-height:24px; height:24px; padding:0 6px; margin:0 2px;
  border:1px solid color-mix(in srgb, var(--legal-accent) 36%, var(--legal-line)); border-radius:5px;
  background:color-mix(in srgb, var(--legal-accent-soft) 62%, var(--legal-panel)); color:var(--legal-accent-text);
  font:500 11px var(--legal-mono); line-height:1;
}
[class*="st-key-citation-line-"] [data-testid="stButton"] button:hover {
  background:var(--legal-accent-soft); border-color:var(--legal-accent); color:var(--legal-accent-text); transform:none;
}
.ga-answer-actions-rule { height:1px; background:var(--legal-line); margin:22px 0 12px; }
[class*="st-key-copy-answer"] button,
[class*="st-key-helpful-answer"] button,
[class*="st-key-not-helpful-answer"] button,
[class*="st-key-evidence-answer"] button {
  min-height:36px; border:1px solid var(--legal-line); border-radius:8px;
  background:var(--legal-panel); color:var(--legal-ink);
  font-size:13px; font-weight:600; justify-content:center; padding:6px 10px;
}
[class*="st-key-evidence-answer"] button { justify-content:center; color:var(--legal-accent-text); background:var(--legal-accent-soft); }
[class*="st-key-answer-primary-source-"] button {
  min-height:38px; margin-top:8px; border:1px solid var(--legal-line); border-radius:8px;
  background:var(--legal-wash); color:var(--legal-accent-text); font-size:13px; font-weight:650;
}
.ga-answer-source-strip {
  display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:12px;
  margin:18px 0 4px; padding:12px 14px; border:1px solid var(--legal-line); border-radius:10px;
  background:color-mix(in srgb, var(--legal-accent-soft) 22%, var(--legal-panel));
}
.ga-answer-source-strip span {
  color:var(--legal-accent); font:700 12px var(--legal-mono);
}
.ga-answer-source-strip strong {
  color:var(--legal-ink); font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.ga-answer-source-strip em {
  color:var(--legal-muted); font:11px var(--legal-mono); font-style:normal;
}

/* Tabs and source rows */
[data-testid="stTabs"] { margin-top:38px; }
[data-testid="stTabs"] [role="tablist"] { gap:22px; border-bottom:1px solid var(--legal-line); }
[data-testid="stTabs"] button {
  color:var(--legal-muted); font-size:15px; font-weight:550; padding-bottom:13px;
}
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--legal-ink); font-weight:650; }
[data-testid="stTabs"] button[aria-selected="true"]::after { background:var(--legal-accent); height:2px; }
.ga-sources-heading {
  display:flex; align-items:end; justify-content:space-between; gap:14px; margin:28px 0 16px;
}
.ga-sources-heading span {
  display:block; margin-bottom:5px; color:var(--legal-accent); font:600 11px var(--legal-sans); letter-spacing:.02em;
}
.ga-sources-heading h2 { margin:0; color:var(--legal-ink); font:600 25px var(--legal-serif); }
.ga-sources-heading em {
  align-self:center; color:var(--legal-muted); background:var(--legal-wash); border-radius:5px;
  padding:3px 6px; font:10px var(--legal-mono); font-style:normal;
}
[class*="st-key-source-row-"] {
  border-top:1px solid var(--legal-line); padding:16px 0 14px;
}
.ga-source-id { color:var(--legal-accent); font: 12px var(--legal-mono); padding-top:7px; }
.ga-doc-symbol {
  display:grid; place-items:center; width:38px; height:42px;
  background:color-mix(in srgb, var(--legal-accent-soft) 62%, var(--legal-panel)); color:var(--legal-accent);
  border:1px solid color-mix(in srgb, var(--legal-accent) 30%, var(--legal-line)); border-radius:8px; font: 18px var(--legal-mono);
}
.ga-source-row-title { display:flex; align-items:center; gap:9px; flex-wrap:wrap; }
.ga-source-row-title h3 { margin:0; color:var(--legal-ink); font-size:15px; font-weight:650; }
.ga-source-row-title span {
  color:var(--legal-accent-text); background:var(--legal-accent-soft); border-radius:5px; padding:3px 6px; font:10px var(--legal-mono);
}
.ga-source-meta { color:var(--legal-muted); font: 11px var(--legal-mono); margin:6px 0; }
.ga-source-row-main p {
  margin:0; color:var(--legal-muted); font: 14px/1.5 var(--legal-serif);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
[class*="st-key-view-source-tab"] button {
  min-height:36px; border:1px solid var(--legal-line); border-radius:8px;
  background:var(--legal-panel); color:var(--legal-accent-text); font-size:13px; font-weight:650; justify-content:center;
}
.ga-retrieved-title {
  margin:28px 0 10px; color:var(--legal-muted); font:500 12px var(--legal-mono);
}
.ga-retrieved-title span { font-size:10px; background:var(--legal-wash); padding:2px 5px; border-radius:4px; }
.ga-extra-source {
  display:flex; gap:10px; align-items:center; border:1px solid var(--legal-line); border-radius:9px;
  padding:12px 14px; color:var(--legal-muted); font-size:13px;
}
.ga-extra-source strong { color:var(--legal-ink); }
.ga-extra-source em { margin-left:auto; font:10px var(--legal-mono); font-style:normal; }

/* Evidence panel and source dialog */
[class*="st-key-evidence-panel-"] [data-testid="stVerticalBlockBorderWrapper"] {
  position:sticky; top:94px; max-height:calc(100vh - 112px); overflow:hidden;
  border:1px solid var(--legal-line); border-radius:0; background:var(--legal-panel); box-shadow:none;
}
[class*="st-key-evidence-panel-"] [data-testid="stVerticalBlockBorderWrapper"] > div { padding:20px 22px; }
.ga-evidence-title span, .ga-dialog-title span {
  color:var(--legal-accent); font:600 11px var(--legal-sans); letter-spacing:.02em; text-transform:none;
}
.ga-evidence-title h2 { margin:7px 0 0; color:var(--legal-ink); font:600 21px var(--legal-serif); }
.ga-evidence-doc { display:flex; gap:12px; align-items:center; margin:18px 0 10px; }
.ga-evidence-doc h3 { margin:0 0 4px; color:var(--legal-ink); font-size:15px; }
.ga-evidence-doc p { margin:0; color:var(--legal-muted); font: 11px var(--legal-mono); }
.ga-doc-pills { display:flex; gap:6px; margin:8px 0 18px; }
.ga-doc-pills span { padding:5px 7px; border-radius:5px; background:var(--legal-accent-soft); color:var(--legal-accent-text); font:10px var(--legal-mono); }
.ga-doc-pills span:last-child { background:color-mix(in srgb, var(--success) 14%, var(--legal-panel)); color:var(--success); }
.ga-evidence-tabs { display:flex; gap:20px; border-bottom:1px solid var(--legal-line); margin:0 -22px 18px; padding:0 22px; }
.ga-evidence-tabs span { padding:10px 0; color:var(--legal-muted); font-size:12px; }
.ga-evidence-tabs .active { color:var(--legal-ink); border-bottom:2px solid var(--legal-accent); }
.ga-source-text {
  white-space:pre-wrap; overflow-wrap:anywhere; color:var(--legal-ink);
  font: 16px/1.78 var(--legal-serif);
}
[class*="st-key-evidence-panel-"] .ga-source-text {
  max-height:52vh; overflow:auto; padding-right:8px;
}
.ga-readable-excerpt { white-space:pre-wrap; overflow-wrap:anywhere; color:var(--text-secondary); font-size:15px; line-height:1.68; margin:10px 0 4px; }
.ga-evidence-highlight {
  display:inline; padding:2px 1px; border-bottom:2px solid var(--legal-accent);
  background:var(--legal-accent-soft); color:var(--legal-ink);
}
[data-testid="stDialog"] [role="dialog"] {
  width:min(860px, calc(100vw - 64px)); max-width:860px; max-height:88vh; overflow:hidden;
  border:1px solid var(--legal-line); border-radius:16px; background:var(--legal-panel); color:var(--legal-ink);
  box-shadow:0 24px 64px rgba(34,29,22,.26);
}
[data-testid="stDialog"] [role="dialog"] > div { max-height:88vh; overflow-y:auto; overflow-x:hidden; }
.ga-dialog-title h2 { margin:8px 0 6px; color:var(--legal-ink); font:600 30px/1.12 var(--legal-serif); }
.ga-dialog-title p { margin:0; color:var(--legal-muted); font:11px var(--legal-mono); }
.ga-dialog-meta {
  display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:14px -24px 24px; padding:14px 24px;
  border-top:1px solid var(--legal-line); border-bottom:1px solid var(--legal-line);
}
.ga-dialog-meta span { background:var(--legal-wash); color:var(--legal-muted); border-radius:5px; padding:5px 7px; font:10px var(--legal-mono); }
[data-testid="stDialog"] .ga-source-text {
  max-height:52vh; overflow:auto; padding:26px 36px;
  border:0; background:transparent; font-size:18px; line-height:1.75;
}

/* Supporting components */
.ga-section-label { margin:30px 0 12px; color:var(--legal-muted); font:600 12px var(--legal-sans); letter-spacing:.02em; text-transform:none; }
.ga-state {
  padding:24px; margin:20px 0; border:1px solid var(--legal-line); border-radius:13px; background:var(--legal-wash);
}
.ga-state h3 { margin:0 0 8px; color:var(--legal-ink); font:600 21px var(--legal-serif); }
.ga-state p { margin:0; font-size:14px; }
.ga-palette-grid { display:grid; grid-template-columns:repeat(4,minmax(100px,1fr)); gap:12px; }
[data-testid="stLinkButton"] a {
  min-height:38px; border-radius:8px; border:1px solid var(--legal-line);
  background:var(--legal-wash); color:var(--legal-ink); text-decoration:none;
  display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:650;
}
.ga-metric-label { color:var(--legal-muted); font: 11px var(--legal-mono); text-transform:uppercase; letter-spacing:.06em; }
.ga-metric-value { color:var(--legal-ink); font-size:23px; line-height:1.2; font-weight:680; }
.ga-metric-unit { color:var(--legal-muted); font-size:12px; }
.st-key-followup-composer { max-width:930px; margin:22px auto 0; }
[data-testid="stChatInput"] {
  border:1px solid var(--legal-line); background:var(--legal-panel); border-radius:15px;
  box-shadow:0 9px 24px rgba(47,42,34,.08);
}

@media (max-width:1023px) {
  [data-testid="stSidebar"] { width:76px !important; min-width:76px !important; max-width:76px !important; }
  .ga-sidebar-brand > div:not(.ga-brand-mark),
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] [data-testid="stSelectbox"],
  [data-testid="stSidebar"] [data-testid="stNumberInput"],
  [data-testid="stSidebar"] [data-testid="stToggle"],
  [data-testid="stSidebar"] [data-testid="stExpander"],
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { display:none; }
  .ga-sidebar-brand { justify-content:center; border-bottom:0; padding-bottom:4px; }
  .ga-header { padding:0 28px; }
}

@media (max-width:640px) {
  [data-testid="stSidebar"] { display:none; }
  .ga-header { height:auto; min-height:76px; padding:16px 18px; align-items:flex-start; }
  .ga-top-controls { justify-content:flex-start; }
  .ga-compact-select, .ga-context-pill { display:none; }
  .ga-hero { margin-top:56px; text-align:left; }
  .ga-hero h1 { font-size:38px; }
  .ga-hero p { font-size:17px; }
  [data-testid="stMainBlockContainer"] { overflow-x:hidden; }
  [class*="st-key-answer-thread-"], .st-key-followup-composer { padding-inline:18px; }
  .ga-user-bubble { max-width:calc(100% - 58px); padding:14px 16px; }
  .ga-chat-time { padding-right:56px; }
  .ga-chat-status { display:none; }
  .ga-assistant-avatar { margin:0; }
  [class*="st-key-answer-card-"] [data-testid="stVerticalBlockBorderWrapper"] > div { padding:18px 16px 14px; }
  .ga-answer-heading small { width:100%; margin-left:33px; }
  .ga-answer-source-strip { grid-template-columns:auto 1fr; }
  .ga-answer-source-strip em { grid-column:2; }
  div[data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:12px; }
  div[data-testid="column"] { min-width:100% !important; width:100% !important; }
  [data-testid="stTabs"] [role="tablist"] { overflow-x:auto; scrollbar-width:thin; }
  [data-testid="stDialog"] [role="dialog"] { width:calc(100vw - 18px); max-width:calc(100vw - 18px); }
}

@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { scroll-behavior:auto !important; transition:none !important; animation:none !important; }
}
"""


__all__ = ["build_application_css"]
