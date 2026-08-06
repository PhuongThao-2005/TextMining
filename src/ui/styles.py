"""Organized application CSS built from the central theme tokens.

Version-sensitive selectors are limited to documented Streamlit ``data-testid``
hooks. If Streamlit renames one, only the corresponding cosmetic enhancement
is lost; native controls and content remain usable.
"""
from __future__ import annotations

from .theme import build_theme_css


def build_application_css(theme_choice: str = "System") -> str:
    return build_theme_css(theme_choice) + """
/* Base reset and page shell */
html, body, [class*="css"] { font-family: var(--font-sans); }
[data-testid="stAppViewContainer"] { background: var(--page-bg); color: var(--text-primary); }
[data-testid="stMainBlockContainer"] {
  max-width: var(--content-width); padding: 2.5rem 3rem 5rem; margin: 0 auto;
}
[data-testid="stHeader"] { background: color-mix(in srgb, var(--page-bg) 86%, transparent); height: 2.5rem; }
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] { visibility: hidden; }
p, li { color: var(--text-secondary); }
a { color: var(--accent); }
code, pre { font-family: var(--font-mono); }
*:focus-visible { outline: 3px solid color-mix(in srgb, var(--accent) 55%, transparent); outline-offset: 2px; }

/* App-owned header and mode pills */
.ga-header { position: sticky; top: .25rem; z-index: 20; min-height: 60px; display:flex; align-items:center;
  justify-content:space-between; gap:16px; padding:10px 16px; margin-bottom:24px;
  border:1px solid var(--border-subtle); border-radius:var(--radius-lg);
  background:var(--surface-elevated); backdrop-filter:blur(14px); box-shadow:var(--shadow-sm); }
.ga-brand { display:flex; align-items:center; gap:12px; color:var(--text-primary); font-size:15px; font-weight:680; }
.ga-mark { width:24px; height:24px; border:2px solid var(--accent); border-radius:8px; position:relative; }
.ga-mark:after { content:""; position:absolute; width:7px; height:7px; right:3px; bottom:3px; background:var(--accent); border-radius:2px; }
.ga-mode { display:inline-flex; align-items:center; min-height:26px; padding:2px 10px; border-radius:999px;
  border:1px solid var(--border-default); background:var(--surface-secondary); color:var(--text-secondary);
  font-size:12px; font-weight:650; letter-spacing:.01em; }
.ga-mode.demo { color:var(--warning); background:color-mix(in srgb, var(--warning) 10%, var(--surface-primary)); }
.ga-mode.production { color:var(--accent-text); background:var(--accent-soft); }
.ga-mode.blocked { color:var(--danger); background:color-mix(in srgb, var(--danger) 10%, var(--surface-primary)); }

/* Sidebar */
[data-testid="stSidebar"] { border-right:1px solid var(--border-subtle); overflow:hidden; }
[data-testid="stSidebar"] > div:first-child { background:var(--surface-primary); padding-top:2rem; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 { margin-top:24px; font-size:12px;
  color:var(--text-muted); text-transform:uppercase; letter-spacing:.09em; }
[data-testid="stSidebar"] label { color:var(--text-secondary); font-size:13px; font-weight:560; }

/* Native controls */
[data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {
  min-height:44px; border-radius:var(--radius-md); border-color:var(--border-default);
  background:var(--surface-primary); color:var(--text-primary); font-weight:620;
  transition:border-color 170ms ease, transform 170ms ease, background 170ms ease;
}
[data-testid="stButton"] button:hover { border-color:var(--border-strong); transform:translateY(-1px); }
[data-testid="stFormSubmitButton"] button { background:var(--accent); color:var(--text-inverse); border-color:var(--accent); }
[data-testid="stFormSubmitButton"] button:hover { background:var(--accent-hover); color:var(--text-inverse); }
[data-testid="stTextArea"] textarea, [data-testid="stChatInput"] textarea {
  color:var(--text-primary); background:transparent; border:0; box-shadow:none; font-size:17px; line-height:1.55;
}
[data-testid="stTextArea"] textarea:focus { box-shadow:none; }
[data-testid="stTextArea"] [data-baseweb="base-input"], [data-testid="stChatInput"] [data-baseweb="base-input"] {
  background:var(--surface-primary); color:var(--text-primary);
}
/* BaseWeb select/input hooks are version-sensitive cosmetic overrides. */
[data-baseweb="select"] > div, [data-baseweb="input"] > div {
  background:var(--surface-primary); color:var(--text-primary); border-color:var(--border-default);
}
[data-baseweb="popover"] { background:var(--surface-elevated); color:var(--text-primary); }

/* Landing hero and composer */
.ga-hero { max-width:800px; margin:clamp(56px, 11vh, 112px) auto 32px; text-align:center; }
.ga-eyebrow { color:var(--accent); font-size:12px; font-weight:680; letter-spacing:.1em; text-transform:uppercase; }
.ga-hero h1 { margin:16px auto 14px; max-width:760px; color:var(--text-primary); font-size:clamp(42px, 5vw, 56px);
  line-height:1.08; letter-spacing:-.038em; font-weight:700; }
.ga-hero p { max-width:620px; margin:0 auto; color:var(--text-secondary); font-size:17px; line-height:1.6; }
div[data-testid="stForm"] { max-width:800px; margin:0 auto; padding:16px 18px 14px;
  border:1px solid var(--border-default); border-radius:var(--radius-xl); background:var(--surface-primary);
  box-shadow:var(--shadow-md); }
div[data-testid="stForm"]:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 14%, transparent), var(--shadow-md); }
.ga-composer-meta { color:var(--text-muted); font-size:12px; font-weight:560; }
.ga-examples { max-width:800px; margin:20px auto 0; }
.ga-landing-status { max-width:800px; margin:16px auto 0; text-align:center; color:var(--text-muted); font-size:13px; }
.ga-status-dot { display:inline-block; width:7px; height:7px; margin-right:7px; border-radius:999px; background:var(--accent); }

/* Answer research thread */
.ga-thread { max-width:var(--reading-width); margin:32px auto 0; }
[class*="st-key-answer-thread-"] { max-width:var(--reading-width); margin-inline:auto; }
.st-key-followup-composer { max-width:var(--reading-width); margin:24px auto 0; }
.ga-question { margin:40px 0 20px; color:var(--text-primary); font-size:clamp(28px, 3.2vw, 34px);
  line-height:1.2; letter-spacing:-.025em; font-weight:680; }
.ga-turn-divider { height:1px; background:var(--border-subtle); margin:52px 0 0; }
.ga-status-row { display:flex; flex-wrap:wrap; gap:8px 16px; margin-bottom:24px; color:var(--text-muted); font-size:12px; font-weight:560; }
.ga-answer-marker { height:0; overflow:hidden; }
.ga-answer-space { height:8px; }
/* :has is cosmetic and version-sensitive; content stays readable without it. */
div[data-testid="stVerticalBlock"]:has(.ga-answer-marker) [data-testid="stMarkdownContainer"] > p {
  color:var(--text-primary); font-size:17.5px; line-height:1.78; margin:0 0 16px;
}
div[data-testid="stVerticalBlock"]:has(.ga-answer-marker) [data-testid="stMarkdownContainer"] li { font-size:17px; line-height:1.7; }
/* Citation occurrences are native Streamlit buttons, never navigation links. */
[class*="st-key-citation-line-"] { flex-wrap:wrap; align-items:baseline !important; column-gap:3px !important; row-gap:2px !important; }
[class*="st-key-citation-line-"] [data-testid="stMarkdownContainer"] p { margin:0; }
[class*="st-key-citation-line-"] [data-testid="stButton"] button {
  min-width:24px; min-height:23px; height:23px; padding:0 6px; margin:0 1px;
  border:1px solid color-mix(in srgb, var(--accent) 28%, var(--border-default)); border-radius:999px;
  background:var(--accent-soft); color:var(--accent-text); font-size:11.5px; font-weight:720; line-height:1;
}
[class*="st-key-citation-line-"] [data-testid="stButton"] button:hover {
  background:color-mix(in srgb, var(--accent-soft) 75%, var(--accent)); border-color:var(--accent); color:var(--accent-text);
}

/* Source rail, full cards, and suggestions */
.ga-section-label { margin:32px 0 12px; color:var(--text-muted); font-size:12px; font-weight:680; letter-spacing:.08em; text-transform:uppercase; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--border-subtle); border-radius:var(--radius-lg); background:var(--surface-primary); box-shadow:none; }
[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color:var(--border-default); }
[data-testid="stLinkButton"] a { min-height:42px; border-radius:var(--radius-md); border:1px solid var(--border-default);
  background:var(--surface-secondary); color:var(--text-primary); text-decoration:none; }
[data-testid="stLinkButton"] a:hover { border-color:var(--border-strong); background:var(--surface-tertiary); color:var(--text-primary); }
.ga-source-number { color:var(--accent); font-size:12px; font-weight:720; }
.ga-source-title { color:var(--text-primary); font-size:15px; line-height:1.35; font-weight:650; }
.ga-source-meta { color:var(--text-muted); font-size:12px; line-height:1.5; }
.ga-source-excerpt { color:var(--text-secondary); font-size:14px; line-height:1.55; display:-webkit-box;
  -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.ga-demo-label { color:var(--warning); font-size:11px; font-weight:700; letter-spacing:.07em; }
.ga-source-text { white-space:pre-wrap; overflow-wrap:anywhere; color:var(--text-primary); font-size:15px; line-height:1.72; }
.ga-evidence-highlight { padding:2px 1px; border-bottom:2px solid color-mix(in srgb, var(--warning) 62%, var(--accent));
  border-radius:3px; background:color-mix(in srgb, var(--warning) 18%, var(--surface-primary)); color:var(--text-primary); }

/* Streamlit 1.52 dialog: viewport-bounded, themed, and internally scrollable. */
[data-testid="stDialog"] [role="dialog"] { width:min(860px, calc(100vw - 48px)); max-width:860px; max-height:86vh;
  border:1px solid var(--border-default); border-radius:var(--radius-xl); background:var(--surface-primary); color:var(--text-primary); }
[data-testid="stDialog"] [data-testid="stVerticalBlock"] { min-width:0; }
[data-testid="stDialog"] .ga-source-text { max-height:48vh; overflow:auto; padding:16px;
  border:1px solid var(--border-subtle); border-radius:var(--radius-md); background:var(--surface-secondary); }
.ga-palette-grid { display:grid; grid-template-columns:repeat(4,minmax(100px,1fr)); gap:12px; }
.ga-state { padding:20px; margin:20px 0; border:1px solid var(--border-default); border-radius:var(--radius-lg); background:var(--surface-secondary); }
.ga-state h3 { margin:0 0 6px; color:var(--text-primary); font-size:19px; }
.ga-state p { margin:0; font-size:14px; }

/* Tabs, expanders, and metrics */
[data-testid="stTabs"] { margin-top:32px; }
[data-testid="stTabs"] button { color:var(--text-muted); font-size:13px; font-weight:620; }
[data-testid="stTabs"] button[aria-selected="true"] { color:var(--text-primary); }
[data-testid="stExpander"] { border-color:var(--border-subtle); border-radius:var(--radius-md); background:var(--surface-secondary); }
.ga-metric-label { color:var(--text-muted); font-size:11px; font-weight:680; text-transform:uppercase; letter-spacing:.06em; }
.ga-metric-value { color:var(--text-primary); font-size:22px; line-height:1.2; font-weight:680; }
.ga-metric-unit { color:var(--text-muted); font-size:12px; }

/* Responsive behavior */
@media (min-width:1024px) {
  [data-testid="stSidebar"][aria-expanded="true"] { min-width:320px; max-width:340px; }
  .ga-source-rail [data-testid="column"] { min-width:220px; }
}
@media (max-width:1023px) {
  [data-testid="stSidebar"] { min-width:0; max-width:none; }
  [data-testid="stMainBlockContainer"] { padding:2rem 24px 4rem; }
  .ga-hero { margin-top:7vh; }
  .ga-hero h1 { font-size:38px; }
  .ga-palette-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width:640px) {
  html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { max-width:100vw; overflow-x:hidden; }
  [data-testid="stMainBlockContainer"] { padding:1.25rem 16px 3.5rem; overflow-x:hidden; }
  .ga-header { min-height:54px; margin-bottom:12px; padding:8px 12px; }
  .ga-brand span:last-child { display:none; }
  .ga-hero { margin-top:32px; text-align:left; }
  .ga-hero h1 { font-size:32px; line-height:1.1; }
  .ga-hero p { font-size:15px; }
  div[data-testid="stForm"] { padding:12px; border-radius:18px; }
  [data-testid="stTextArea"] textarea { min-height:104px; }
  .ga-question { margin-top:28px; font-size:29px; }
  div[data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:12px; }
  div[data-testid="column"] { min-width:100% !important; width:100% !important; }
  [data-testid="stButton"] button { width:100%; min-height:44px; }
  .ga-status-row { margin-bottom:16px; }
  .ga-palette-grid { grid-template-columns:1fr; }
  [class*="st-key-answer-thread-"], [data-testid="stVerticalBlock"], [data-testid="stMarkdownContainer"] {
    width:100%; max-width:100%; min-width:0; overflow-wrap:anywhere;
  }
  [data-testid="stTabs"] { width:100%; max-width:calc(100vw - 32px); overflow:hidden; }
  [data-testid="stTabs"] [role="tablist"] { overflow-x:auto; scrollbar-width:thin; }
  [data-testid="stDialog"] [role="dialog"] { width:calc(100vw - 16px); max-width:calc(100vw - 16px); max-height:88vh; }
  [data-testid="stDialog"] [data-testid="stVerticalBlock"] { padding-inline:0; }
  [class*="st-key-citation-line-"] [data-testid="stButton"] button { min-width:36px; min-height:32px; height:32px; }
  [data-testid="stSidebar"][aria-expanded="false"] { width:0; min-width:0; }
}
@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { scroll-behavior:auto !important; transition:none !important; animation:none !important; }
}
"""


__all__ = ["build_application_css"]
