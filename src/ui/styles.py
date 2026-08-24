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
  --legal-side: #0f172a;
  --legal-side-line: #1e293b;
  --legal-side-text: #e2e8f0;
  --legal-side-dim: #94a3b8;
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

/* Sidebar */
[data-testid="stSidebar"] {
  width: 292px !important; min-width: 292px !important; max-width: 292px !important;
  border-right: 1px solid var(--legal-side-line); background: var(--legal-side); color: var(--legal-side-text);
}
[data-testid="stSidebar"] > div:first-child { background: var(--legal-side); padding: 22px 14px 28px; }
.ga-sidebar-brand {
  display:flex; align-items:center; gap:10px; padding: 6px 4px 24px; margin-bottom: 14px;
  border-bottom:1px solid var(--legal-side-line);
}
.ga-brand-mark {
  display:grid; place-items:center; width:32px; height:32px; border:1px solid #334155; border-radius:9px;
  color:#bfdbfe; background:#172554; font: 17px var(--legal-mono);
}
.ga-sidebar-brand strong { display:block; color:#fff; font-size:16px; letter-spacing:0; }
.ga-sidebar-brand span { display:block; margin-top:2px; color:#94a3b8; font: 10px/1.35 var(--legal-mono); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
  margin: 20px 4px 11px; color:#94a3b8; font: 500 10px var(--legal-mono);
  letter-spacing:.14em; text-transform:uppercase;
}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p {
  color:#cbd5e1; font-size:12px; font-weight:500;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
  background:#111827; color:#f8fafc; border-color:#334155; border-radius:8px;
}
[data-testid="stSidebar"] [data-testid="stButton"] button {
  justify-content:flex-start; min-height:34px; border:0; border-radius:7px; padding:7px 9px;
  background:transparent; color:#dbeafe; font-size:12px; font-weight:560;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
  background:rgba(37,99,235,.16); color:#dbeafe; transform:none;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] input { color:#f8fafc; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#94a3b8; font: 10px var(--legal-mono); }
[data-testid="stSidebar"] [data-testid="stExpander"] {
  background:transparent; border:1px solid var(--legal-side-line); border-radius:9px;
}
[data-testid="stSidebar"] hr { border-color: var(--legal-side-line); }

/* Topbar */
.ga-header {
  height:76px; display:flex; align-items:center; justify-content:space-between; gap:18px;
  padding:0 36px; border-bottom:1px solid var(--legal-line);
  background: color-mix(in srgb, var(--legal-panel) 88%, transparent);
}
.ga-page-title h2 {
  margin:0; color:var(--legal-ink); font:600 21px/1.15 var(--legal-serif); letter-spacing:0;
}
.ga-page-title p { margin:4px 0 0; color:var(--legal-muted); font-size:13px; }
.ga-top-controls { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
.ga-compact-select {
  display:inline-flex; align-items:center; gap:10px; min-height:38px; padding:0 11px;
  border:1px solid var(--legal-line); border-radius:8px; color:var(--text-secondary);
  background:var(--legal-panel); font-size:13px;
}
.ga-mode {
  display:inline-flex; align-items:center; gap:7px; min-height:29px; padding:0 10px;
  border:1px solid var(--border-default); border-radius:8px; color:#557d5d;
  background:#f3f8f1; font: 500 12px var(--legal-mono);
}
.ga-mode i, .ga-status-dot {
  width:7px; height:7px; border-radius:50%; background:#72a17c;
  box-shadow:0 0 0 3px rgba(114,161,124,.12);
}
.ga-mode.demo { color:#075985; border-color:#bae6fd; background:#f0f9ff; }
.ga-mode.demo i { background:#0ea5e9; box-shadow:0 0 0 3px rgba(14,165,233,.13); }
.ga-mode.blocked { color:#9d6258; border-color:#ead0ca; background:#f9e8e5; }
.ga-mode.blocked i { background:#b46a61; box-shadow:0 0 0 3px rgba(180,106,97,.13); }

/* Landing */
.ga-hero { max-width:850px; margin: clamp(92px, 17vh, 170px) auto 30px; padding:0 28px; text-align:center; }
.ga-eyebrow {
  color:#2563eb; font:500 12px var(--legal-mono); letter-spacing:.16em; text-transform:uppercase;
}
.ga-hero h1 {
  margin:20px auto 16px; color:var(--legal-ink);
  font:600 clamp(42px, 5vw, 58px)/1.06 var(--legal-serif); letter-spacing:0;
}
.ga-hero p {
  max-width:720px; margin:0 auto; color:#475569; font:500 19px/1.55 var(--legal-serif);
}
div[data-testid="stForm"] {
  max-width:1014px; margin:0 auto; padding:12px 13px 10px 18px;
  border:1px solid #cbd5e1; border-radius:15px; background:var(--legal-panel);
  box-shadow:0 14px 32px rgba(47,42,34,.08);
}
div[data-testid="stForm"]:focus-within {
  border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.12), 0 14px 32px rgba(15,23,42,.08);
}
[data-testid="stTextArea"] textarea, [data-testid="stChatInput"] textarea {
  color:var(--legal-ink); background:transparent; border:0; box-shadow:none;
  font-size:16px; line-height:1.55;
}
[data-testid="stTextArea"] textarea::placeholder, [data-testid="stChatInput"] textarea::placeholder { color:#9a978f; }
[data-testid="stTextArea"] textarea:focus { box-shadow:none; }
[data-testid="stTextArea"] [data-baseweb="base-input"], [data-testid="stChatInput"] [data-baseweb="base-input"] {
  background:transparent; color:var(--legal-ink);
}
[data-testid="stFormSubmitButton"] button {
  min-height:48px; border:0; border-radius:10px; padding:0 18px;
  background:#1d4ed8; color:#fff; font-size:14px; font-weight:650;
}
[data-testid="stFormSubmitButton"] button:hover { background:#1e40af; color:#fff; }
.ga-composer-meta, .ga-shortcut {
  display:flex; align-items:center; min-height:36px; color:#64748b; font: 12px var(--legal-mono);
}
.ga-shortcut { justify-content:center; color:#94a3b8; }
.ga-landing-meta {
  margin:16px auto 34px; display:flex; align-items:center; justify-content:center; gap:9px;
  color:var(--legal-muted); font: 12px var(--legal-mono);
}
.ga-examples { max-width:1014px; margin:0 auto; }
.ga-examples .ga-section-label { display:none; }
[class*="st-key-example-"] button {
  position:relative; min-height:142px; justify-content:flex-start; align-items:flex-start; text-align:left;
  white-space:pre-wrap; padding:18px 42px 18px 18px; border:1px solid var(--legal-line);
  border-radius:12px; background:var(--legal-panel); color:var(--legal-ink);
  font:600 16px/1.38 var(--legal-serif); box-shadow:none;
}
[class*="st-key-example-"] button:hover { border-color:#93c5fd; background:#f8fbff; transform:translateY(-1px); }
.ga-landing-status { max-width:1014px; margin:22px auto 0; text-align:center; color:var(--legal-muted); font-size:13px; }

/* Thread and answer */
[class*="st-key-answer-thread-"] { max-width:930px; margin:0 auto; padding:38px 0 0; }
.ga-thread-head { margin:0 0 26px; }
.ga-thread-head .ga-eyebrow { color:#2563eb; margin-bottom:14px; }
.ga-thread-head h1 {
  margin:0 0 17px; color:var(--legal-ink);
  font:600 clamp(32px, 3.5vw, 43px)/1.13 var(--legal-serif); letter-spacing:0;
}
.ga-status-row {
  display:flex; align-items:center; flex-wrap:wrap; gap:0; color:var(--legal-muted); font: 12px var(--legal-mono);
}
.ga-status-row > span:not(.ga-mode) { padding:0 14px; border-left:1px solid var(--legal-line); }
[class*="st-key-answer-card-"] [data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid var(--legal-line); border-radius:14px; background:var(--legal-panel);
  box-shadow:0 8px 20px rgba(48,42,30,.025);
}
[class*="st-key-answer-card-"] [data-testid="stVerticalBlockBorderWrapper"] > div { padding:28px 32px 18px; }
.ga-answer-heading {
  display:flex; align-items:center; gap:10px; margin-bottom:20px;
  color:#1e40af; font:500 11px var(--legal-mono); letter-spacing:.12em; text-transform:uppercase;
}
.ga-answer-sigil {
  width:23px; height:23px; display:grid; place-items:center; border-radius:7px;
  background:#dbeafe; color:#1e3a8a; font:700 12px var(--legal-serif);
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
  border:1px solid #93c5fd; border-radius:5px; background:#eff6ff; color:#1d4ed8;
  font:500 11px var(--legal-mono); line-height:1;
}
[class*="st-key-citation-line-"] [data-testid="stButton"] button:hover {
  background:#dbeafe; border-color:#2563eb; color:#1e40af; transform:none;
}
.ga-answer-actions-rule { height:1px; background:var(--legal-line); margin:22px 0 12px; }
[class*="st-key-copy-answer"] button,
[class*="st-key-helpful-answer"] button,
[class*="st-key-not-helpful-answer"] button,
[class*="st-key-evidence-answer"] button {
  min-height:32px; border:0; background:transparent; color:var(--legal-muted);
  font-size:12px; justify-content:flex-start; padding:5px 7px;
}
[class*="st-key-evidence-answer"] button { justify-content:flex-end; color:#1d4ed8; }

/* Tabs and source rows */
[data-testid="stTabs"] { margin-top:38px; }
[data-testid="stTabs"] [role="tablist"] { gap:22px; border-bottom:1px solid var(--legal-line); }
[data-testid="stTabs"] button {
  color:var(--legal-muted); font-size:14px; font-weight:500; padding-bottom:13px;
}
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--legal-ink); font-weight:650; }
[data-testid="stTabs"] button[aria-selected="true"]::after { background:#2563eb; height:2px; }
.ga-sources-heading {
  display:flex; align-items:end; justify-content:space-between; gap:14px; margin:28px 0 16px;
}
.ga-sources-heading span {
  display:block; margin-bottom:5px; color:#2563eb; font:500 11px var(--legal-mono); letter-spacing:.13em;
}
.ga-sources-heading h2 { margin:0; color:var(--legal-ink); font:600 25px var(--legal-serif); }
.ga-sources-heading em {
  align-self:center; color:var(--legal-muted); background:var(--legal-wash); border-radius:5px;
  padding:3px 6px; font:10px var(--legal-mono); font-style:normal;
}
[class*="st-key-source-row-"] {
  border-top:1px solid var(--legal-line); padding:16px 0 14px;
}
.ga-source-id { color:#2563eb; font: 12px var(--legal-mono); padding-top:7px; }
.ga-doc-symbol {
  display:grid; place-items:center; width:38px; height:42px; background:#eff6ff; color:#2563eb;
  border:1px solid #bfdbfe; border-radius:8px; font: 18px var(--legal-mono);
}
.ga-source-row-title { display:flex; align-items:center; gap:9px; flex-wrap:wrap; }
.ga-source-row-title h3 { margin:0; color:var(--legal-ink); font-size:15px; font-weight:650; }
.ga-source-row-title span {
  color:#1d4ed8; background:#dbeafe; border-radius:5px; padding:3px 6px; font:10px var(--legal-mono);
}
.ga-source-meta { color:var(--legal-muted); font: 11px var(--legal-mono); margin:6px 0; }
.ga-source-row-main p {
  margin:0; color:var(--legal-muted); font: 14px/1.5 var(--legal-serif);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
[class*="st-key-view-source-tab"] button {
  min-height:32px; border:0; background:transparent; color:#1d4ed8; font-size:12px; justify-content:flex-end;
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
  color:#2563eb; font:500 11px var(--legal-mono); letter-spacing:.13em; text-transform:uppercase;
}
.ga-evidence-title h2 { margin:7px 0 0; color:var(--legal-ink); font:600 21px var(--legal-serif); }
.ga-evidence-doc { display:flex; gap:12px; align-items:center; margin:18px 0 10px; }
.ga-evidence-doc h3 { margin:0 0 4px; color:var(--legal-ink); font-size:15px; }
.ga-evidence-doc p { margin:0; color:var(--legal-muted); font: 11px var(--legal-mono); }
.ga-doc-pills { display:flex; gap:6px; margin:8px 0 18px; }
.ga-doc-pills span { padding:5px 7px; border-radius:5px; background:#dbeafe; color:#1d4ed8; font:10px var(--legal-mono); }
.ga-doc-pills span:last-child { background:#ecfdf5; color:#15803d; }
.ga-evidence-tabs { display:flex; gap:20px; border-bottom:1px solid var(--legal-line); margin:0 -22px 18px; padding:0 22px; }
.ga-evidence-tabs span { padding:10px 0; color:var(--legal-muted); font-size:12px; }
.ga-evidence-tabs .active { color:var(--legal-ink); border-bottom:2px solid #2563eb; }
.ga-source-text {
  white-space:pre-wrap; overflow-wrap:anywhere; color:var(--legal-ink);
  font: 16px/1.78 var(--legal-serif);
}
[class*="st-key-evidence-panel-"] .ga-source-text {
  max-height:52vh; overflow:auto; padding-right:8px;
}
.ga-readable-excerpt { white-space:pre-wrap; overflow-wrap:anywhere; color:var(--text-secondary); font-size:15px; line-height:1.68; margin:10px 0 4px; }
.ga-evidence-highlight {
  display:inline; padding:2px 1px; border-bottom:2px solid #2563eb;
  background:#dbeafe; color:var(--legal-ink);
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
.ga-section-label { margin:30px 0 12px; color:var(--legal-muted); font:600 12px var(--legal-mono); letter-spacing:.08em; text-transform:uppercase; }
.ga-state {
  padding:24px; margin:20px 0; border:1px solid var(--legal-line); border-radius:13px; background:var(--legal-wash);
}
.ga-state h3 { margin:0 0 8px; color:var(--legal-ink); font:600 21px var(--legal-serif); }
.ga-state p { margin:0; font-size:14px; }
.ga-palette-grid { display:grid; grid-template-columns:repeat(4,minmax(100px,1fr)); gap:12px; }
[data-testid="stLinkButton"] a {
  min-height:38px; border-radius:8px; border:1px solid var(--legal-line);
  background:var(--legal-wash); color:var(--legal-ink); text-decoration:none;
}
.ga-metric-label { color:var(--legal-muted); font: 11px var(--legal-mono); text-transform:uppercase; letter-spacing:.06em; }
.ga-metric-value { color:var(--legal-ink); font-size:23px; line-height:1.2; font-weight:680; }
.ga-metric-unit { color:var(--legal-muted); font-size:12px; }
.st-key-followup-composer { max-width:930px; margin:22px auto 0; }
[data-testid="stChatInput"] {
  border:1px solid #cbd5e1; background:var(--legal-panel); border-radius:15px;
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
  .ga-compact-select { display:none; }
  .ga-hero { margin-top:56px; text-align:left; }
  .ga-hero h1 { font-size:38px; }
  .ga-hero p { font-size:17px; }
  [data-testid="stMainBlockContainer"] { overflow-x:hidden; }
  [class*="st-key-answer-thread-"], .st-key-followup-composer { padding-inline:18px; }
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
