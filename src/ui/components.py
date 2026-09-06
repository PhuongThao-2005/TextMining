"""Reusable Streamlit presentation components.

All model and retrieved text is rendered through native Streamlit APIs or
escaped before entering application-owned HTML. Citation parsing remains in the
generation/service layer.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from typing import Any, Mapping, Sequence

import streamlit as st

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
) -> None:
    label = _mode_label(active_mode, requested_mode, ready, lang)
    badge_class = "production" if active_mode == "production" and ready else "blocked" if active_mode == "production" else "demo"
    del theme_choice
    st.markdown(
        '<div class="ga-header">'
        '<div class="ga-page-title">'
        f'<h2>{safe_html_text(t(lang, "legal_title"))}</h2>'
        f'<p>{safe_html_text(t(lang, "legal_subtitle"))}</p></div>'
        '<div class="ga-top-controls">'
        f'<span class="ga-mode {badge_class}"><i></i>{safe_html_text(label)}</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def render_sidebar_brand(lang: str = "en") -> None:
    st.markdown(
        '<div class="ga-sidebar-brand">'
        '<div class="ga-brand-mark" aria-hidden="true">▤</div>'
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
    st.markdown(
        '<section class="ga-hero">'
        f'<div class="ga-eyebrow">{safe_html_text(t(lang, "hero_eyebrow"))}</div>'
        f'<h1>{safe_html_text(t(lang, "hero_title"))}</h1>'
        f'<p>{safe_html_text(t(lang, "hero_body"))}</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    submitted_question: str | None = None
    with st.form("landing-search", clear_on_submit=False):
        question = st.text_area(
            t(lang, "question"),
            height=72,
            placeholder="Hỏi về luật, điều khoản hoặc quyền lợi của bạn..." if lang == "vi" else "Ask about a law, article, or legal right...",
            label_visibility="collapsed",
        )
        toolbar_left, toolbar_shortcut, toolbar_right = st.columns([6, 1, 0.9])
        mode_text = f'{t(lang, "mode_demo")} · {t(lang, "no_external_calls")}' if active_mode == "demo" else f'{t(lang, "mode_production")} · {config_name}'
        toolbar_left.markdown(f'<span class="ga-composer-meta">{safe_html_text(mode_text)}</span>', unsafe_allow_html=True)
        toolbar_shortcut.markdown(f'<span class="ga-shortcut">{safe_html_text(t(lang, "submit_shortcut"))}</span>', unsafe_allow_html=True)
        submitted = toolbar_right.form_submit_button(t(lang, "ask"), type="primary", use_container_width=True)
        if submitted:
            submitted_question = question

    st.markdown(
        '<div class="ga-landing-meta">'
        f'<span class="ga-mode {"demo" if active_mode == "demo" else "production"}"><i></i>{safe_html_text(t(lang, "mode_demo") if active_mode == "demo" else t(lang, "mode_production"))}</span>'
        f'<span>{safe_html_text(config_name)}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="ga-examples"><div class="ga-section-label">{safe_html_text(t(lang, "examples"))}</div></div>', unsafe_allow_html=True)
    with st.container(key="landing-examples"):
        columns = st.columns(min(4, len(examples)), gap="medium")
        for index, (label, query) in enumerate(examples):
            button_label = f"**{label}**\n\n{query} ->"
            if columns[index % len(columns)].button(button_label, key=f"example-{index}", use_container_width=True):
                submitted_question = query
    st.markdown(
        f'<div class="ga-landing-status"><span class="ga-status-dot"></span>{safe_html_text(_landing_status(active_mode, readiness, lang))}</div>',
        unsafe_allow_html=True,
    )
    return submitted_question


def render_blocked_setup(readiness: ProductionReadiness, lang: str = "en") -> None:
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(t(lang, "blocked_title"))}</h3>'
        f'<p>{safe_html_text(t(lang, "blocked_detail"))}</p></section>',
        unsafe_allow_html=True,
    )
    for blocker in readiness.blockers[:5]:
        st.write(f"— {blocker}")


def render_turn(response: QuestionResponse, question: str, turn_number: int, show_diagnostics: bool, lang: str = "en") -> str | None:
    if turn_number > 1:
        st.markdown('<div class="ga-turn-divider"></div>', unsafe_allow_html=True)
    with st.container(key=f"answer-thread-{turn_number}"):
        elapsed = response.latency.get("total")
        elapsed_label = f"{elapsed:.0f} ms" if isinstance(elapsed, (int, float)) else "N/A"
        mode_label = t(lang, "mode_demo") if response.is_mock else t(lang, "mode_production")
        st.markdown(
            '<section class="ga-chat-question">'
            f'<div class="ga-chat-time">{safe_html_text(_clock_label())}</div>'
            '<div class="ga-user-bubble-wrap">'
            f'<div class="ga-user-bubble">{safe_html_text(question)}</div>'
            '<div class="ga-user-avatar" aria-hidden="true">U</div>'
            '</div></section>',
            unsafe_allow_html=True,
        )

        avatar_col, answer_col, status_col = st.columns([0.07, 0.75, 0.18], gap="small")
        avatar_col.markdown('<div class="ga-assistant-avatar" aria-hidden="true">G</div>', unsafe_allow_html=True)
        with answer_col:
            with st.container(border=True, key=f"answer-card-{turn_number}"):
                st.markdown(
                    '<div class="ga-answer-heading"><span class="ga-answer-sigil">✓</span>'
                    f'<span>{safe_html_text(t(lang, "verified_answer"))}</span>'
                    f'<small>{safe_html_text(_source_count_label(len(response.citation_sources), lang))} · {safe_html_text(elapsed_label)}</small></div>',
                    unsafe_allow_html=True,
                )
                if response.status == "completed":
                    render_answer_article(response, turn_number, lang)
                    _render_primary_source_strip(response, turn_number, lang)
                    _render_answer_actions(response, turn_number, lang)
                elif response.status == "abstained":
                    render_abstention_state(lang)
                elif response.status in {"blocked", "deferred"}:
                    title = t(lang, "configuration_deferred") if response.status == "deferred" else t(lang, "blocked_title")
                    render_status_state(title, response.error.message if response.error else t(lang, "readiness_details"))
                else:
                    render_error_state(response, lang)
        status_col.markdown(
            '<div class="ga-chat-status">'
            f'<span class="ga-mode {"demo" if response.is_mock else "production"}"><i></i>{safe_html_text(mode_label)}</span>'
            f'<span>{safe_html_text(t(lang, "mock_no_external_call") if response.is_mock else _today_label(lang))}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        for warning in (*response.warnings, *response.citation_warnings):
            if response.is_mock and (
                warning.startswith("Demo values only")
                or warning.startswith("Structural citation coverage")
            ):
                continue
            st.warning(warning, icon=None)

        suggestion = render_followup_suggestions(response.suggested_followups, turn_number, lang)
        render_diagnostics_tabs(response, turn_number, show_diagnostics, lang)
        render_source_dialog_for_selection(response, turn_number, lang)
    return suggestion


def _render_primary_source_strip(response: QuestionResponse, turn_number: int, lang: str) -> None:
    if not response.citation_sources:
        return
    source = response.citation_sources[0]
    card = build_source_cards((source,))[0]
    st.markdown(
        '<div class="ga-answer-source-strip">'
        f'<span>[{safe_html_text(card.citation_id)}]</span>'
        f'<strong>{safe_html_text(card.title)}</strong>'
        f'<em>{safe_html_text(card.detail or card.source_path or t(lang, "source_details"))}</em>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button(t(lang, "view_source"), key=f"answer-primary-source-{turn_number}-{card.citation_id}", use_container_width=True):
        _select_source(response.citation_sources, turn_number, card.citation_id, viewer_open=False)
        st.rerun()


def _render_answer_actions(response: QuestionResponse, turn_number: int, lang: str) -> None:
    if not response.citation_sources:
        return
    st.markdown('<div class="ga-answer-actions-rule"></div>', unsafe_allow_html=True)
    action_cols = st.columns([1, 1, 1, 3], gap="small")
    if action_cols[0].button(t(lang, "copy"), key=f"copy-answer-{turn_number}", use_container_width=True):
        st.toast(t(lang, "copy_notice"))
    if action_cols[1].button(t(lang, "helpful"), key=f"helpful-answer-{turn_number}", use_container_width=True):
        st.toast(t(lang, "feedback_notice"))
    if action_cols[2].button(t(lang, "not_helpful"), key=f"not-helpful-answer-{turn_number}", use_container_width=True):
        st.toast(t(lang, "feedback_notice"))
    if action_cols[3].button(t(lang, "view_evidence"), key=f"evidence-answer-{turn_number}", use_container_width=True):
        _select_source(response.citation_sources, turn_number, response.citation_sources[0].citation_id, viewer_open=False)
        st.rerun()


def render_answer_article(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    st.markdown('<div class="ga-answer-marker"></div>', unsafe_allow_html=True)
    answer = response.answer or t(lang, "no_final_answer")
    occurrence = 0
    for line_number, line in enumerate(build_answer_lines(answer, response.citation_references)):
        if line.blank:
            st.markdown('<div class="ga-answer-space"></div>', unsafe_allow_html=True)
            continue
        if not any(segment.citation_id is not None for segment in line.segments):
            st.markdown("".join(segment.text for segment in line.segments))
            continue
        with st.container(
            horizontal=True, vertical_alignment="center", gap=None,
            key=f"citation-line-{turn_number}-{line_number}",
        ):
            for segment in line.segments:
                if segment.citation_id is None:
                    if segment.text:
                        st.markdown(segment.text, width="content")
                    continue
                occurrence += 1
                citation_id = segment.citation_id
                if st.button(
                    segment.text,
                    key=citation_control_key(turn_number, citation_id, occurrence),
                    type="tertiary",
                    help=f'{t(lang, "preview_context")} {citation_id}',
                ):
                    _select_source(response.citation_sources, turn_number, citation_id, viewer_open=False)
                    st.rerun()


def render_selected_source(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    if selection is None or selection.turn_id != turn_number:
        return
    citation_id = selection.citation_id
    source = next((item for item in response.citation_sources if item.citation_id == citation_id), None)
    if source is None:
        st.session_state["selected_source"] = None
        return
    card = next(item for item in build_source_cards((source,)) if item.citation_id == citation_id)
    # Citation metadata may carry a bounded preview; the normalized response owns
    # the complete retrieved chunk, so the viewer reuses that exact in-memory row.
    card = replace(card, full_text=resolve_source_text(source, response.contexts))
    actions = build_source_actions(source)
    st.markdown(f'<div class="ga-section-label">{safe_html_text(t(lang, "selected_citation"))}</div>', unsafe_allow_html=True)
    with st.container(border=True):
        header_left, header_right = st.columns([5, 1])
        header_left.markdown(f"**[{card.citation_id}] {card.title}**")
        header_right.caption(t(lang, "mode_demo") if card.is_mock else t(lang, "retrieval"))
        st.caption(" · ".join(value for value in (
            card.detail or "Article/section N/A",
            f"Page {card.page}" if card.page is not None else "Page N/A",
            f"Rank {card.rank}",
            f"Score {card.score:.3f}" if card.score is not None else "Score N/A",
        )))
        _render_source_excerpt(card.preview or t(lang, "no_preview"))
        evidence = build_source_text_segments(card.full_text, card.evidence, context_id=source.context_id)
        status = evidence.label or (
            "Span unavailable" if evidence.status == "unavailable" else "Recorded span invalid"
        )
        st.caption(t(lang, "evidence_status", status=status))
        action_columns = st.columns(2 if actions.original_url else 1)
        if action_columns[0].button(
            t(lang, "view_source"), key=f"view-source-preview-{turn_number}-{citation_id}",
            type="primary", use_container_width=True,
        ):
            _select_source(response.citation_sources, turn_number, citation_id, viewer_open=True)
            st.rerun()
        if actions.original_url and actions.original_label:
            action_columns[1].link_button(
                t(lang, "open_original"), actions.original_url, use_container_width=True,
            )
    if selection.viewer_open:
        _render_source_dialog(source, card, evidence, lang)


@st.dialog("Source details", width="large", dismissible=True)
def _render_source_dialog(source: Any, card: Any, evidence: Any, lang: str = "en") -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    turn_id = selection.turn_id if selection else 0
    close_label = "Close" if lang == "en" else "Đóng"
    heading, close_column = st.columns([6, 1])
    heading.markdown(
        '<div class="ga-dialog-title">'
        f'<span>{safe_html_text(t(lang, "reference_source"))} · [{card.citation_id}]</span>'
        f'<h2>{safe_html_text(card.title)}</h2>'
        f'<p>{safe_html_text(card.detail or card.source_path or "N/A")}</p></div>',
        unsafe_allow_html=True,
    )
    if close_column.button(close_label, key=f"close-source-{turn_id}-{card.citation_id}", use_container_width=True):
        _close_source_viewer()
        st.rerun()
    score_label = f"{card.score:.3f}" if card.score is not None else "N/A"
    st.markdown(
        '<div class="ga-dialog-meta">'
        f'<span>{safe_html_text(t(lang, "original_text"))}</span>'
        f'<span>Score {safe_html_text(score_label)}</span>'
        f'<span>Rank {safe_html_text(card.rank)}</span>'
        f'<span>{safe_html_text(t(lang, "evidence_span"))}: {safe_html_text(evidence.label or evidence.status)}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    if evidence.status == "valid":
        st.caption(f"{evidence.label} · Recorded evidence for this source")
        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
    elif evidence.status == "invalid":
        st.warning("The recorded evidence span could not be validated against this source.", icon=None)
        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
    else:
        st.info("This source was cited, but an exact supporting passage was not recorded.", icon=None)
        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
    actions = build_source_actions(source)
    footer_columns = st.columns(2 if actions.original_url else 1)
    if footer_columns[0].button(
        close_label, key=f"close-source-footer-{turn_id}-{card.citation_id}", use_container_width=True,
    ):
        _close_source_viewer()
        st.rerun()
    if actions.original_url and actions.original_label:
        footer_columns[1].link_button(t(lang, "open_original"), actions.original_url, use_container_width=True)


def render_source_dialog_for_selection(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    if selection is None or selection.turn_id != turn_number or not selection.viewer_open:
        return
    source, card, evidence = _resolve_selected_source_view(response, selection.citation_id)
    if source is not None and card is not None and evidence is not None:
        _render_source_dialog(source, card, evidence, lang)


def render_evidence_panel(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    if selection is None or selection.turn_id != turn_number or selection.viewer_open:
        return
    source, card, evidence = _resolve_selected_source_view(response, selection.citation_id)
    if source is None or card is None or evidence is None:
        return
    actions = build_source_actions(source)
    with st.container(border=True, key=f"evidence-panel-{turn_number}-{card.citation_id}"):
        header_left, header_right = st.columns([5, 1])
        header_left.markdown(
            f'<div class="ga-evidence-title"><span>{safe_html_text(t(lang, "reference_source"))}</span>'
            f'<h2>{safe_html_text(t(lang, "cited_evidence"))}</h2></div>',
            unsafe_allow_html=True,
        )
        if header_right.button("×", key=f"close-evidence-panel-{turn_number}-{card.citation_id}", help="Close" if lang == "en" else "Đóng"):
            _close_source_viewer()
            st.rerun()
        st.markdown(
            '<div class="ga-evidence-doc">'
            '<div class="ga-doc-symbol">▤</div><div>'
            f'<h3>{safe_html_text(card.title)}</h3>'
            f'<p>{safe_html_text(card.detail or card.source_path or "N/A")}</p></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="ga-doc-pills">'
            f'<span>{safe_html_text(t(lang, "original_text"))}</span>'
            f'<span>{safe_html_text(t(lang, "high_confidence"))}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="ga-evidence-tabs">'
            f'<span class="active">{safe_html_text(t(lang, "legal_content"))}</span>'
            f'<span>{safe_html_text(t(lang, "document_info"))}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
        footer_columns = st.columns(2 if actions.original_url else 1)
        if footer_columns[0].button(
            t(lang, "view_source"), key=f"open-evidence-dialog-{turn_number}-{card.citation_id}", use_container_width=True,
        ):
            _select_source(response.citation_sources, turn_number, card.citation_id, viewer_open=True)
            st.rerun()
        if actions.original_url and actions.original_label:
            footer_columns[1].link_button(t(lang, "open_original"), actions.original_url, use_container_width=True)


def render_cited_source_rail(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    cards = build_source_cards(response.citation_sources)
    if not cards:
        return
    st.markdown(f'<div class="ga-section-label">{safe_html_text(t(lang, "sources_referenced"))}</div><div class="ga-source-rail"></div>', unsafe_allow_html=True)
    columns = st.columns(min(4, len(cards)))
    for index, card in enumerate(cards):
        source = next(item for item in response.citation_sources if item.citation_id == card.citation_id)
        actions = build_source_actions(source)
        with columns[index % len(columns)].container(border=True):
            demo = '<div class="ga-demo-label">DEMO SOURCE</div>' if card.is_mock else ""
            st.markdown(
                demo
                + f'<div class="ga-source-number">[{card.citation_id}]</div>'
                + f'<div class="ga-source-title">{safe_html_text(card.title)}</div>'
                + f'<div class="ga-source-meta">{safe_html_text(card.detail or card.source_path or "Source metadata unavailable")}</div>'
                + f'<div class="ga-source-excerpt">{safe_html_text(format_retrieved_text(card.preview or "No preview available."))}</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                t(lang, "view_source"), key=f"view-source-card-{turn_number}-{card.citation_id}",
                use_container_width=True,
            ):
                _select_source(response.citation_sources, turn_number, card.citation_id, viewer_open=True)
                st.rerun()
            if actions.original_url and actions.original_label:
                st.link_button(t(lang, "open_original"), actions.original_url, use_container_width=True)


def render_followup_suggestions(suggestions: Sequence[str], turn_number: int, lang: str = "en") -> str | None:
    if not suggestions:
        return None
    st.markdown(f'<div class="ga-section-label">{safe_html_text("Hỏi tiếp" if lang == "vi" else "Explore further")}</div>', unsafe_allow_html=True)
    for index, suggestion in enumerate(suggestions[:3]):
        if st.button(f"{suggestion}  →", key=f"followup-{turn_number}-{index}", use_container_width=True):
            return suggestion
    return None


def render_followup_composer(lang: str = "en") -> str | None:
    with st.container(key="followup-composer"):
        return st.chat_input(t(lang, "followup_placeholder"))


def render_diagnostics_tabs(response: QuestionResponse, turn_number: int, show_diagnostics: bool, lang: str = "en") -> None:
    del show_diagnostics
    render_full_sources(response, turn_number, lang)


def render_full_sources(response: QuestionResponse, turn_number: int, lang: str = "en") -> None:
    sections = build_source_sections(response.citation_sources, response.contexts)
    contexts = {(row.chunk_id, row.rank): row for row in response.contexts}
    if response.citation_sources:
        st.markdown(
            '<div class="ga-sources-heading">'
            f'<span>{safe_html_text(t(lang, "sources").upper())}</span>'
            f'<h2>{safe_html_text(t(lang, "cited_sources"))}</h2>'
            f'<em>{len(sections.cited)} {safe_html_text(t(lang, "sources").lower())}</em></div>',
            unsafe_allow_html=True,
        )
        for card in sections.cited:
            source = next(item for item in response.citation_sources if item.citation_id == card.citation_id)
            context = contexts.get((source.chunk_id, card.rank))
            full_text = (context.text if context else card.full_text) or ""
            evidence = build_source_text_segments(full_text, card.evidence, context_id=source.context_id)
            _render_source_row(source, card, evidence, turn_number, lang)

    additional = sections.additional
    if additional:
        st.markdown(
            f'<h3 class="ga-retrieved-title">{safe_html_text(t(lang, "additional_context"))} '
            f'<span>{len(additional)}</span></h3>',
            unsafe_allow_html=True,
        )
        for row in additional:
            score = f"{row.score:.3f}" if isinstance(row.score, (int, float)) else "N/A"
            st.markdown(
                '<div class="ga-extra-source"><span>▤</span>'
                f'<strong>{safe_html_text(row.title or row.document_id or row.chunk_id or "Retrieved context")}</strong>'
                f'<em>Score {safe_html_text(score)} · Rank {safe_html_text(row.rank)}</em></div>',
                unsafe_allow_html=True,
            )
    if not response.contexts:
        st.caption(t(lang, "no_context"))


def _render_source_row(source: Any, card: Any, evidence: Any, turn_number: int, lang: str) -> None:
    score_label = f"{card.score:.3f}" if card.score is not None else "N/A"
    actions = build_source_actions(source)
    with st.container(key=f"source-row-{turn_number}-{card.citation_id}"):
        id_col, icon_col, body_col, action_col = st.columns([0.04, 0.06, 0.72, 0.18], gap="small")
        id_col.markdown(f'<div class="ga-source-id">{safe_html_text(card.citation_id)}</div>', unsafe_allow_html=True)
        icon_col.markdown('<div class="ga-doc-symbol">▤</div>', unsafe_allow_html=True)
        body_col.markdown(
            '<div class="ga-source-row-main">'
            f'<div class="ga-source-row-title"><h3>{safe_html_text(card.title)}</h3>'
            f'<span>{safe_html_text(card.detail or source.article or t(lang, "source_details"))}</span></div>'
            f'<div class="ga-source-meta">Score {safe_html_text(score_label)} · Rank {safe_html_text(card.rank)} · {safe_html_text(evidence.label or evidence.status)}</div>'
            f'<p>{safe_html_text(format_retrieved_text(card.preview or t(lang, "no_excerpt")))}</p></div>',
            unsafe_allow_html=True,
        )
        if action_col.button(t(lang, "view_source"), key=f"view-source-tab-{turn_number}-{card.citation_id}", use_container_width=True):
            _select_source((source,), turn_number, card.citation_id, viewer_open=True)
            st.rerun()
        if actions.original_url and actions.original_label:
            action_col.link_button(t(lang, "open_original"), actions.original_url, use_container_width=True)


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
    if not show_diagnostics:
        st.caption("Bật Chẩn đoán ở thanh bên để xem metadata an toàn." if lang == "vi" else "Enable Show diagnostics in Settings to inspect safe runtime metadata.")
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
    stage = safe_html_text(response.error.stage if response.error else "unknown")
    st.markdown(
        f'<section class="ga-state"><h3>{safe_html_text(t(lang, "error_title"))}</h3>'
        f'<p>{safe_html_text(t(lang, "error_body", stage=stage))}</p></section>',
        unsafe_allow_html=True,
    )
    if response.error:
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


def _today_label(lang: str) -> str:
    today = date.today()
    if lang == "vi":
        return f"{today.day} tháng {today.month}, {today.year}"
    month = today.strftime("%B")
    return f"{month} {today.day}, {today.year}"


def _clock_label() -> str:
    return datetime.now().strftime("%H:%M")


def _source_count_label(count: int, lang: str) -> str:
    if lang == "vi":
        return f"{count} nguồn trích dẫn"
    noun = "source" if count == 1 else "sources"
    return f"{count} cited {noun}"


def _resolve_selected_source_view(response: QuestionResponse, citation_id: int) -> tuple[Any | None, Any | None, Any | None]:
    source = next((item for item in response.citation_sources if item.citation_id == citation_id), None)
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


def _close_source_viewer() -> None:
    clear_source_selection(st.session_state)
    for key in ("citation", "full_source"):
        if key in st.query_params:
            del st.query_params[key]


__all__ = [
    "render_app_header", "render_blocked_setup", "render_design_preview",
    "render_evidence_panel", "render_followup_composer", "render_landing_hero",
    "render_readiness_summary", "render_sidebar_brand", "render_source_dialog_for_selection",
    "render_turn",
]
