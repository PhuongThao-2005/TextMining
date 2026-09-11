"""Reusable Streamlit presentation components.

All model and retrieved text is rendered through native Streamlit APIs or
escaped before entering application-owned HTML. Citation parsing remains in the
generation/service layer.
"""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

import streamlit as st

from generation.citations import CitationSource
from service.qa_service import QuestionResponse, normalize_latency_rows
from service.ui_models import (
    build_answer_lines, build_source_actions, build_source_cards,
    citation_control_key, clear_source_selection, parse_source_selection,
    select_source_for_turn,
)
from service.ui_runtime import ProductionReadiness

from .i18n import t
from .view_models import (
    build_source_sections, build_source_text_segments, display_value, format_retrieved_text,
    safe_html_text, resolve_source_text, source_segments_html,
)


def render_app_header(
    active_mode: str,
    requested_mode: str,
    ready: bool,
    lang: str = "en",
    *,
    theme_choice: str | None = None,
    is_conversation: bool | None = None,
) -> None:
    del requested_mode, ready
    if is_conversation is None:
        is_conversation = bool(st.session_state.get("conversation"))
    title = t(lang, "legal_title" if is_conversation else "brand_name")
    subtitle = t(lang, "legal_subtitle" if is_conversation else "brand_caption")
    badge = f'<span class="ga-mode demo">{safe_html_text(t(lang, "mode_demo"))}</span>' if active_mode == "demo" else ""
    with st.container(key="app-header"):
        title_col, toggle_col = st.columns([12, 1], vertical_alignment="center")
        title_col.markdown(
            '<div class="ga-header">'
            f'<div class="ga-page-title"><h2>{safe_html_text(title)}</h2>'
            f'<p>{safe_html_text(subtitle)}</p></div>{badge}</div>',
            unsafe_allow_html=True,
        )
        current = theme_choice or str(st.session_state.get("theme_choice", "System"))
        # System remains available in Settings; the header explicitly chooses a theme.
        target = "Light" if current == "Dark" else "Dark"
        toggle_col.button(
            "☀" if target == "Light" else "☾", key="theme-toggle",
            help=t(lang, "switch_theme", theme=t(lang, f"theme_{target.lower()}")),
            on_click=_set_theme, args=(target,),
        )


def _set_theme(value: str) -> None:
    st.session_state["theme_choice"] = value


def render_sidebar_brand(lang: str = "en") -> None:
    st.markdown(
        '<div class="ga-sidebar-brand">'
        '<div class="ga-brand-mark" aria-hidden="true"><span class="ga-brand-document"><i></i><i></i><b>[ ]</b></span></div>'
        f'<div><strong>{safe_html_text(t(lang, "brand_name"))}</strong>'
        f'<span>{safe_html_text(t(lang, "brand_caption"))}</span></div></div>',
        unsafe_allow_html=True,
    )


def render_landing_hero(
    *,
    active_mode: str,
    config_name: str,
    readiness: ProductionReadiness,
    examples: Sequence[tuple[str, str]],
    lang: str = "en",
) -> str | None:
    del active_mode, config_name, readiness
    st.markdown(
        '<section class="ga-hero">'
        f'<div class="ga-eyebrow">{safe_html_text(t(lang, "hero_eyebrow"))}</div>'
        f'<h1>{safe_html_text(t(lang, "hero_title"))}</h1>'
        f'<p>{safe_html_text(t(lang, "hero_body"))}</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    submitted_question: str | None = None
    render_scope_selector(lang, location="landing")
    with st.form("landing-search", clear_on_submit=False):
        question = st.text_area(
            t(lang, "question"),
            height=100,
            placeholder=t(lang, "question_placeholder"),
            label_visibility="collapsed",
        )
        toolbar_shortcut, toolbar_right = st.columns([5, 1])
        toolbar_shortcut.markdown(f'<span class="ga-shortcut">{safe_html_text(t(lang, "submit_shortcut"))}</span>', unsafe_allow_html=True)
        submitted = toolbar_right.form_submit_button(t(lang, "ask"), type="primary", use_container_width=True)
        if submitted:
            submitted_question = question

    if examples:
        st.markdown(f'<div class="ga-section-label">{safe_html_text(t(lang, "examples"))}</div>', unsafe_allow_html=True)
        with st.container(key="landing-examples"):
            columns = st.columns(min(3, len(examples)), gap="small")
            for index, (_, query) in enumerate(examples[:3]):
                if columns[index].button(query, key=f"example-{index}", use_container_width=True):
                    submitted_question = query
    st.markdown(
        f'<p class="ga-legal-disclaimer">{safe_html_text(t(lang, "legal_disclaimer"))}</p>',
        unsafe_allow_html=True,
    )
    return submitted_question


def render_scope_selector(lang: str = "en", *, location: str = "landing") -> None:
    """Keep the query setting durable when landing/chat widgets are unmounted."""
    options = ("current_law", "broad", "historical")
    current = st.session_state.get("filter_profile", "broad")
    if current not in options:
        current = "broad"
    st.session_state["filter_profile"] = current
    widget_key = f"scope-profile-{location}"
    if st.session_state.get(widget_key) not in options:
        st.session_state[widget_key] = current
    with st.container(key=f"scope-selector-{location}"):
        label_col, select_col = st.columns([1.5, 1], gap="small", vertical_alignment="center")
        label_col.markdown(
            '<div class="ga-scope-inline-label">'
            f'<strong>{safe_html_text(t(lang, "scope_title"))}</strong>'
            f'<span>{safe_html_text(t(lang, "scope_description_short"))}</span></div>',
            unsafe_allow_html=True,
        )
        select_col.selectbox(
            t(lang, "scope"), options, key=widget_key,
            format_func=lambda value: t(lang, f"scope_{value}"),
            label_visibility="collapsed",
            help=t(lang, f"scope_{st.session_state.get(widget_key, current)}_help"),
            on_change=_save_scope, args=(widget_key,),
        )


def _save_scope(widget_key: str) -> None:
    st.session_state["filter_profile"] = st.session_state[widget_key]


def render_blocked_setup(readiness: ProductionReadiness, lang: str = "en") -> None:
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(t(lang, "blocked_title"))}</h3>'
        f'<p>{safe_html_text(t(lang, "blocked_detail"))}</p></section>',
        unsafe_allow_html=True,
    )
    if _developer_ui():
        with st.expander(t(lang, "technical_detail")):
            for blocker in readiness.blockers[:5]:
                st.write(f"— {blocker}")


def render_turn(
    response: QuestionResponse,
    question: str,
    turn_number: int,
    show_diagnostics: bool,
    lang: str = "en",
    *,
    show_followups: bool = True,
    is_latest: bool = False,
) -> str | None:
    del show_followups
    if turn_number > 1:
        st.markdown('<div class="ga-turn-divider"></div>', unsafe_allow_html=True)
    with st.container(key=f"answer-thread-{turn_number}"):
        anchor_id = "ga-latest-turn-anchor" if is_latest else f"turn-{turn_number}"
        st.markdown(f'<div id="turn-{turn_number}" class="ga-turn-anchor"></div>', unsafe_allow_html=True)
        if is_latest:
            st.markdown(f'<div id="{anchor_id}" class="ga-turn-scroll-anchor"></div>', unsafe_allow_html=True)
        render_user_message(question)
        with st.container(border=False, key=f"answer-card-{turn_number}"):
            if response.status == "completed":
                if response.citation_sources:
                    st.markdown(
                        '<div class="ga-answer-heading"><span class="ga-answer-sigil">✓</span>'
                        f'<span>{safe_html_text(t(lang, "sourced_badge"))}</span>'
                        f'<small>{safe_html_text(_source_count_label(len(response.citation_sources), lang))}</small></div>',
                        unsafe_allow_html=True,
                    )
                render_answer_article(response, turn_number, lang)
                _render_answer_actions(response, turn_number, lang)
                render_full_sources(response, turn_number, lang)
            elif response.status == "abstained":
                render_abstention_state(lang)
            elif response.status in {"blocked", "deferred"}:
                render_status_state(t(lang, "blocked_title"), t(lang, "service_unavailable"))
            else:
                render_error_state(response, lang)

        render_diagnostics_tabs(response, turn_number, show_diagnostics, lang)
    return None


def render_user_message(question: str) -> None:
    st.markdown(
        '<section class="ga-chat-question"><div class="ga-user-bubble-wrap">'
        f'<div class="ga-user-bubble">{safe_html_text(question)}</div></div></section>',
        unsafe_allow_html=True,
    )


def _render_primary_source_strip(response: QuestionResponse, turn_number: int, lang: str) -> None:
    """Compatibility entry point using the same source cards as the answer."""
    render_full_sources(response, turn_number, lang)


def _render_answer_actions(response: QuestionResponse, turn_number: int, lang: str) -> None:
    if not response.citation_sources:
        return
    if st.button(t(lang, "view_evidence"), key=f"evidence-answer-{turn_number}", type="tertiary"):
        _select_source(response.citation_sources, turn_number, response.citation_sources[0].citation_id, viewer_open=False)
        st.rerun()


def render_answer_article(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    st.markdown('<div class="ga-answer-marker"></div>', unsafe_allow_html=True)
    answer = response.answer or t(lang, "no_final_answer")
    rendered_lines = []
    citation_controls: list[tuple[str, int, int]] = []
    occurrence = 0
    for line_number, line in enumerate(build_answer_lines(answer, response.citation_references)):
        if line.blank:
            rendered_lines.append('<div class="ga-answer-space"></div>')
            continue
        fragments = []
        for segment in line.segments:
            if segment.citation_id is None:
                fragments.append(safe_html_text(segment.text))
                continue
            occurrence += 1
            citation_id = segment.citation_id
            citation_controls.append((segment.text, citation_id, occurrence))
            fragments.append(
                f'<a class="ga-citation-link" href="#source-{turn_number}-{citation_id}" '
                f'title="{safe_html_text(t(lang, "preview_context"))} {citation_id}">'
                f'{safe_html_text(segment.text)}</a>'
            )
        rendered_lines.append(f'<p class="ga-answer-line">{"".join(fragments)}</p>')
    st.markdown('<article class="ga-answer-article">' + "".join(rendered_lines) + "</article>", unsafe_allow_html=True)
    _render_legacy_citation_controls(response, turn_number, citation_controls, lang)


def _render_legacy_citation_controls(
    response: QuestionResponse, turn_number: int, controls: Sequence[tuple[str, int, int]], lang: str,
) -> None:
    if not controls:
        return
    with st.container(key=f"citation-controls-{turn_number}"):
        for label, citation_id, occurrence in controls:
            if st.button(
                label,
                key=citation_control_key(turn_number, citation_id, occurrence),
                type="tertiary",
                help=f'{t(lang, "preview_context")} {citation_id}',
            ):
                _select_source(response.citation_sources, turn_number, citation_id, viewer_open=False)
                st.rerun()


def render_selected_source(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    """Compatibility alias: every source entry point opens the same drawer."""
    render_evidence_panel(response, turn_number, lang)


def _render_source_dialog(source: Any, card: Any, evidence: Any, lang: str = "en", *, turn_number: int = 1) -> None:
    # Dynamic decoration localizes the native accessible dialog title as well.
    @st.dialog(t(lang, "source_details"), width="large", dismissible=True, on_dismiss=_close_source_viewer)
    def drawer() -> None:
        st.markdown('<div class="ga-evidence-drawer"></div>', unsafe_allow_html=True)
        title = _document_title(source, lang)
        subtitle = _document_detail(source)
        st.markdown(
            '<div class="ga-dialog-title">'
            f'<span>{safe_html_text(t(lang, "reference_source"))} [{card.citation_id}]</span>'
            f'<h2>{safe_html_text(title)}</h2>'
            + (f'<p>{safe_html_text(subtitle)}</p>' if subtitle else '') + '</div>',
            unsafe_allow_html=True,
        )
        excerpt_tab, document_tab = st.tabs([t(lang, "cited_excerpt"), t(lang, "document_info")])
        with excerpt_tab:
            if evidence.status == "valid":
                # Show the exact recorded span first, preserving the validated offsets.
                excerpt = "".join(segment.text for segment in evidence.segments if segment.highlighted)
                st.markdown(
                    f'<div class="ga-cited-excerpt">{safe_html_text(format_retrieved_text(excerpt))}</div>',
                    unsafe_allow_html=True,
                )
                if not (source.is_mock and (source.title or "").startswith("Mock QA")) or _developer_ui():
                    with st.expander(t(lang, "source_context")):
                        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
            else:
                st.caption(t(lang, "source_excerpt_unavailable"))
                st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
        with document_tab:
            _render_document_metadata(source, card, lang)
            st.caption(t(lang, "document_metadata_note"))
            actions = build_source_actions(source)
            if actions.original_url and actions.original_label:
                st.link_button(t(lang, "open_original"), actions.original_url, use_container_width=True)
        if st.button(t(lang, "close_evidence"), key=f"close-evidence-panel-{turn_number}-{card.citation_id}", use_container_width=True):
            _close_source_viewer()
            st.rerun()
    drawer()


def render_source_dialog_for_selection(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    """Legacy callers share the unified drawer, including old viewer_open state."""
    render_evidence_panel(response, turn_number, lang)


def render_evidence_panel(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    if selection is None or selection.turn_id != turn_number:
        return
    source, card, evidence = _resolve_selected_source_view(response, selection.citation_id)
    if source is None or card is None or evidence is None:
        _close_source_viewer()
        return
    _render_source_dialog(source, card, evidence, lang, turn_number=turn_number)


def render_cited_source_rail(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    """Compatibility alias for the single compact cited-source section."""
    render_full_sources(response, turn_number, lang)


def render_followup_composer(lang: str = "en") -> str | None:
    # The Streamlit bottom region keeps scope and composer together while scrolling.
    # Root chat_input is the supported fallback if this optional region is absent.
    bottom = getattr(st, "bottom", None)
    if bottom is not None:
        with bottom.container(key="followup-composer"):
            render_scope_selector(lang, location="followup")
            return st.chat_input(t(lang, "followup_placeholder"), key="followup-question")
    render_scope_selector(lang, location="followup")
    return st.chat_input(t(lang, "followup_placeholder"), key="followup-question")


def scroll_to_latest_turn() -> None:
    """Move the viewport to the latest submitted question after its answer renders."""
    script = """
        <script>
        const scrollToLatestTurn = () => {
          const target = window.parent.document.getElementById("ga-latest-turn-anchor");
          target?.scrollIntoView({ behavior: "smooth", block: "start" });
        };
        requestAnimationFrame(scrollToLatestTurn);
        window.setTimeout(scrollToLatestTurn, 250);
        window.setTimeout(scrollToLatestTurn, 650);
        </script>
    """
    iframe = getattr(st, "iframe", None)
    if iframe is not None:
        iframe(script, height="content")
        return
    st.html(script, width="content", unsafe_allow_javascript=True)


def render_diagnostics_tabs(response: QuestionResponse, turn_number: int, show_diagnostics: bool, lang: str = "en") -> None:
    del turn_number
    if not _developer_ui() or not show_diagnostics:
        return
    with st.expander(t(lang, "diagnostics")):
        for warning in (*response.warnings, *response.citation_warnings):
            st.warning(warning, icon=None)
        if response.error:
            st.code(response.error.message, language="text")
        render_details(response, lang)
        render_latency_cards(response.latency, is_mock=response.is_mock)
        render_agent_trace(response, lang)
        render_diagnostics(response, True, lang)
        additional = build_source_sections(response.citation_sources, response.contexts).additional
        if additional:
            st.caption(t(lang, "additional_context"))
            st.json([row.__dict__ for row in additional], expanded=False)


def render_full_sources(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    display_sources = display_sources_for_response(response)
    if not display_sources:
        return
    cited_count = len(response.citation_sources)
    st.markdown(
        '<div class="ga-sources-heading">'
        f'<h2>{safe_html_text(t(lang, "cited_sources"))}</h2>'
        f'<em>{safe_html_text(_source_count_label(len(display_sources), lang))}</em></div>',
        unsafe_allow_html=True,
    )
    for index, card in enumerate(build_source_cards(display_sources)):
        source = next(item for item in display_sources if item.citation_id == card.citation_id)
        if index == cited_count and cited_count > 0:
            st.markdown(
                f'<div class="ga-source-subheading">{safe_html_text(t(lang, "additional_context"))}</div>',
                unsafe_allow_html=True,
            )
        _render_source_row(source, card, None, turn_number, lang)


def _render_source_row(source: Any, card: Any, evidence: Any, turn_number: int, lang: str) -> None:
    del evidence
    with st.container(key=f"source-row-{turn_number}-{card.citation_id}"):
        st.markdown(
            f'<span id="source-{turn_number}-{card.citation_id}" class="ga-source-scroll-anchor"></span>',
            unsafe_allow_html=True,
        )
        body_col, action_col = st.columns([4, 1], gap="small", vertical_alignment="center")
        title = _document_title(source, lang)
        detail = _document_detail(source)
        # Demo metadata is explicitly kept in developer details, never presented as law.
        preview = t(lang, "demo_source_preview") if source.is_mock and (source.title or "").startswith("Mock QA") else format_retrieved_text(card.preview or t(lang, "no_excerpt"))
        body_col.markdown(
            '<div class="ga-source-card ga-source-row-main">'
            f'<div class="ga-source-row-title"><span class="ga-source-id">[{card.citation_id}]</span>'
            f'<h3>{safe_html_text(title)}</h3></div>'
            + (f'<span class="ga-source-meta">{safe_html_text(detail)}</span>' if detail else '')
            + f'<p>{safe_html_text(preview)}</p></div>',
            unsafe_allow_html=True,
        )
        if action_col.button(t(lang, "view_source"), key=f"view-source-tab-{turn_number}-{card.citation_id}", use_container_width=True):
            _select_source((source,), turn_number, card.citation_id, viewer_open=False)
            st.rerun()


def _document_title(source: Any, lang: str) -> str:
    """Use actual document titles, with a neutral label when only IDs exist."""
    title = str(source.title or "").strip()
    if source.is_mock and title.startswith("Mock QA"):
        return t(lang, "demo_document")
    if not title or title in {source.document_id, source.chunk_id, source.context_id}:
        return t(lang, "document_untitled")
    return title


def _document_detail(source: Any) -> str:
    if source.is_mock and str(source.title or "").startswith("Mock QA"):
        return ""
    identifiers = {source.document_id, source.chunk_id, source.context_id}
    values = []
    for value in (source.article, source.section):
        if not value or value in identifiers:
            continue
        text = str(value).strip()
        if "::" in text or re.fullmatch(r"(?:chunk|ctx|doc|provision|section)[_-][\w-]+", text, flags=re.IGNORECASE):
            continue
        values.append(text)
    return " · ".join(values)


def _document_citation(source: Any) -> str | None:
    """Return the human legal citation when retrieval metadata supplies one."""
    for name in ("citation", "citation_anchor", "citation_label", "full_source"):
        value = getattr(source, name, None)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _render_document_metadata(source: Any, card: Any, lang: str) -> None:
    rows = _document_metadata_rows(source, card, lang)
    if not rows:
        return
    html_rows = "".join(
        '<div class="ga-document-info-row">'
        f'<dt>{safe_html_text(label)}</dt>'
        f'<dd>{safe_html_text(value)}</dd>'
        '</div>'
        for label, value in rows
    )
    st.markdown(f'<dl class="ga-document-info">{html_rows}</dl>', unsafe_allow_html=True)


def _document_metadata_rows(source: Any, card: Any, lang: str) -> tuple[tuple[str, str], ...]:
    fields: tuple[tuple[str, Any], ...] = (
        (t(lang, "metadata_citation"), _document_citation(source)),
        (t(lang, "metadata_title"), _document_title(source, lang)),
        (t(lang, "metadata_article"), source.article),
        (t(lang, "metadata_section"), source.section),
        (t(lang, "metadata_document_id"), source.document_id),
        (t(lang, "metadata_chunk_id"), source.chunk_id),
        (t(lang, "metadata_rank"), source.rank),
        (t(lang, "metadata_score"), f"{source.score:.3f}" if isinstance(source.score, (int, float)) else None),
        (t(lang, "metadata_path"), source.source_path),
        (t(lang, "metadata_page"), source.page),
    )
    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, raw_value in fields:
        if raw_value in (None, ""):
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        key = (label, value)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    if not rows and card.title:
        rows.append((t(lang, "metadata_title"), str(card.title)))
    return tuple(rows)


def _developer_ui() -> bool:
    return bool(st.session_state.get("show_developer_ui", False))


def render_details(response: QuestionResponse, lang: str = "en") -> None:
    diagnostics = response.diagnostics
    values = (
        (t(lang, "config"), diagnostics.get("selected_config")),
        ("Retriever", diagnostics.get("retriever_backend")),
        (t(lang, "embedding"), diagnostics.get("embedding_identity")),
        (t(lang, "index"), _nested(diagnostics, "artifact_identity", "index_version")),
        (t(lang, "corpus"), _nested(diagnostics, "artifact_identity", "corpus_identity")),
        (t(lang, "mode"), diagnostics.get("runtime_mode") or response.mode),
    )
    columns = st.columns(2)
    for index, (label, value) in enumerate(values):
        with columns[index % 2].container(border=True):
            st.caption(label)
            st.write(display_value(value))
    st.caption(t(lang, "citation_metrics_note"))
    with st.expander(t(lang, "citation_metrics")):
        st.json(response.citation_metrics, expanded=False)


def render_latency_cards(latency: Mapping[str, Any], *, is_mock: bool) -> None:
    rows = {row["stage"]: row["latency_ms"] for row in normalize_latency_rows(latency)}
    stages = (("Retrieval", "dense_retrieval"), ("Reranking", "reranking"),
              ("Generation", "generation"), ("Planner", "agent_total"), ("Total", "total"))
    visible = [(label, rows.get(key)) for label, key in stages if rows.get(key) is not None or label == "Total"]
    columns = st.columns(len(visible))
    for column, (label, value) in zip(columns, visible):
        with column.container(border=True):
            display = f"{value:.0f}" if isinstance(value, (int, float)) else "N/A"
            st.markdown(
                f'<div class="ga-metric-label">{safe_html_text(label)}</div>'
                f'<div class="ga-metric-value">{display}</div>'
                f'<div class="ga-metric-unit">ms{" · DEMO" if is_mock else ""}</div>',
                unsafe_allow_html=True,
            )


def render_agent_trace(response: QuestionResponse, lang: str = "en") -> None:
    if not response.trace:
        st.caption(t(lang, "no_agent_trace"))
        return
    if response.is_mock:
        st.caption(t(lang, "demo_trace"))
    for row in response.trace:
        step = row.get("step", "—")
        event = row.get("event") or row.get("action") or "Step"
        status = row.get("status") or "completed"
        with st.container(border=True):
            st.markdown(f"**{t(lang, 'step')} {step} · {event}**")
            st.caption(str(status))
    with st.expander(t(lang, "raw_trace")):
        st.json(list(response.trace), expanded=False)


def render_diagnostics(response: QuestionResponse, show_diagnostics: bool, lang: str = "en") -> None:
    if not _developer_ui() or not show_diagnostics:
        return
    warnings = response.citation_warnings
    if warnings:
        st.markdown(f'**{t(lang, "citation_warnings")}**')
        for warning in warnings:
            st.write(f"— {warning}")
    with st.expander(t(lang, "safe_diagnostics"), expanded=True):
        st.json(response.diagnostics, expanded=False)
    with st.expander(t(lang, "effective_configuration")):
        st.json(response.resolved_config, expanded=False)


def render_readiness_summary(readiness: ProductionReadiness, lang: str = "en") -> None:
    if not _developer_ui():
        return
    ready_count = sum(check.status == "ready" for check in readiness.checks)
    st.caption(f"{ready_count}/{len(readiness.checks)} mục sẵn sàng" if lang == "vi" else f"{ready_count} of {len(readiness.checks)} checks ready")
    for check in readiness.checks[:7]:
        symbol = "●" if check.status == "ready" else "○" if check.status in {"warning", "deferred"} else "×"
        st.caption(f"{symbol} {check.name.replace('_', ' ')} · {check.status}")
    if len(readiness.checks) > 7:
        st.caption(f"+ {len(readiness.checks) - 7} more checks")


def render_abstention_state(lang: str = "en") -> None:
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(t(lang, "not_enough_title"))}</h3>'
        f'<p>{safe_html_text(t(lang, "not_enough_body"))}</p></section>',
        unsafe_allow_html=True,
    )


def render_error_state(response: QuestionResponse, lang: str = "en") -> None:
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(t(lang, "error_title"))}</h3>'
        f'<p>{safe_html_text(t(lang, "request_failed"))}</p></section>',
        unsafe_allow_html=True,
    )
    if response.error and _developer_ui():
        with st.expander(t(lang, "technical_detail"), expanded=False):
            st.code(response.error.message, language="text")


def render_status_state(title: str, message: str) -> None:
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(title)}</h3><p>{safe_html_text(message)}</p></section>',
        unsafe_allow_html=True,
    )


def render_design_preview(response: QuestionResponse) -> None:
    """Developer-only component gallery; never calls production services."""
    st.markdown('<div class="ga-hero"><div class="ga-eyebrow">Internal visual QA</div><h1>Design system preview</h1><p>Theme tokens and reusable answer-engine components.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="ga-section-label">Mode badges</div>', unsafe_allow_html=True)
    st.markdown('<span class="ga-mode demo">Demo Preview</span> <span class="ga-mode production">Production</span> <span class="ga-mode blocked">Blocked</span>', unsafe_allow_html=True)
    st.markdown('<div class="ga-section-label">Palette</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ga-palette-grid">'
        '<div class="ga-state" style="background:var(--surface-primary)">Primary</div>'
        '<div class="ga-state" style="background:var(--surface-secondary)">Secondary</div>'
        '<div class="ga-state" style="background:var(--accent-soft);color:var(--accent-text)">Accent</div>'
        '<div class="ga-state" style="border-color:var(--danger);color:var(--danger)">Danger</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ga-section-label">Typography</div>', unsafe_allow_html=True)
    st.markdown("# Page title\n## Section heading\nBody copy remains calm, readable, and source grounded.")
    st.markdown('<div class="ga-section-label">Controls and readiness</div>', unsafe_allow_html=True)
    st.text_area("Preview composer", "Ask a question about the available documents…", disabled=True)
    control_a, control_b = st.columns(2)
    control_a.button("Primary action", type="primary", disabled=True, use_container_width=True)
    control_b.button("Secondary action", disabled=True, use_container_width=True)
    st.caption("● Config · ready")
    st.caption("× Index manifest · blocked")
    st.markdown('<div class="ga-section-label">States and answer components</div>', unsafe_allow_html=True)
    render_turn(response, "What information is required for a request?", 1, True)
    render_abstention_state()
    render_status_state("Production is not ready", "A compatible index manifest is required.")
    render_error_state(response.__class__(**{**response.__dict__, "status": "failed"}))


def _mode_label(active_mode: str, requested_mode: str, ready: bool, lang: str = "en") -> str:
    if requested_mode == "Auto":
        return t(lang, "mode_auto_production") if active_mode == "production" and ready else t(lang, "mode_auto_demo")
    if active_mode == "production" and not ready:
        return t(lang, "mode_production_blocked")
    return t(lang, "mode_production") if active_mode == "production" else t(lang, "mode_demo")


def _landing_status(active_mode: str, readiness: ProductionReadiness, lang: str = "en") -> str:
    if active_mode == "demo":
        return "Demo · không gọi model hoặc retriever thật" if lang == "vi" else "Demo Preview · No retrieval or model call"
    if readiness.ready:
        count = len(readiness.candidates) or (1 if readiness.selected_artifact else 0)
        return f"Production sẵn sàng · phát hiện {count} index tương thích" if lang == "vi" else f"Production ready · {count} compatible index{'es' if count != 1 else ''} detected"
    blocker = readiness.blockers[0] if readiness.blockers else "Readiness checks did not pass"
    return f"Production chưa sẵn sàng · {blocker}" if lang == "vi" else f"Production unavailable · {blocker}"


def _source_count_label(count: int, lang: str) -> str:
    if lang == "vi":
        return f"{count} nguồn"
    noun = "source" if count == 1 else "sources"
    return f"{count} {noun}"


def _resolve_selected_source_view(response: QuestionResponse, citation_id: int) -> tuple[Any | None, Any | None, Any | None]:
    source = next((item for item in display_sources_for_response(response) if item.citation_id == citation_id), None)
    if source is None:
        return None, None, None
    card = next(item for item in build_source_cards((source,)) if item.citation_id == citation_id)
    card = replace(card, full_text=resolve_source_text(source, response.contexts))
    evidence = build_source_text_segments(card.full_text, card.evidence, context_id=source.context_id)
    return source, card, evidence


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _render_source_excerpt(value: Any) -> None:
    text = format_retrieved_text(value)
    st.markdown(
        f'<div class="ga-readable-excerpt">{safe_html_text(text or "No excerpt available.")}</div>',
        unsafe_allow_html=True,
    )


def _render_full_source_text(value: Any) -> None:
    text = format_retrieved_text(value)
    st.markdown(
        f'<div class="ga-source-text">{safe_html_text(text or "Unavailable")}</div>',
        unsafe_allow_html=True,
    )


def _select_source(
    sources: Sequence[Any], turn_id: int, citation_id: int, *, viewer_open: bool,
) -> None:
    selection = select_source_for_turn(sources, turn_id, citation_id, viewer_open=viewer_open)
    if selection is not None:
        st.session_state["selected_source"] = selection.to_state()


def display_sources_for_response(response: QuestionResponse) -> tuple[CitationSource, ...]:
    """Return cited sources plus uncited retrieved contexts as inspectable rows."""
    cited = tuple(response.citation_sources)
    seen = {(source.chunk_id, source.rank) for source in cited}
    next_id = max((source.citation_id for source in cited), default=0) + 1
    additional: list[CitationSource] = []
    for row in response.contexts:
        key = (row.chunk_id, row.rank)
        if key in seen:
            continue
        seen.add(key)
        score = row.rerank_score if row.rerank_score is not None else row.score
        if score is None:
            score = row.vector_score
        context_id = row.chunk_id or row.document_id or f"context-{row.rank}"
        additional.append(CitationSource(
            citation_id=next_id,
            context_id=context_id,
            document_id=row.document_id,
            chunk_id=row.chunk_id,
            title=row.title,
            section=row.provision_id or row.citation,
            article=row.article_number,
            page=None,
            source_path=row.path,
            url=None,
            rank=row.rank,
            score=score,
            text=row.text or row.preview,
            is_mock=row.is_mock,
            evidence=None,
            citation=row.citation,
        ))
        next_id += 1
    return (*cited, *additional)


def _close_source_viewer() -> None:
    clear_source_selection(st.session_state)
    for key in ("citation", "full_source"):
        if key in st.query_params:
            del st.query_params[key]


__all__ = [
    "display_sources_for_response", "render_app_header", "render_blocked_setup", "render_design_preview",
    "render_evidence_panel", "render_followup_composer", "render_landing_hero",
    "render_readiness_summary", "render_scope_selector", "render_sidebar_brand", "render_source_dialog_for_selection",
    "render_turn", "render_user_message", "scroll_to_latest_turn",
]
