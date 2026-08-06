"""Reusable Streamlit presentation components.

All model and retrieved text is rendered through native Streamlit APIs or
escaped before entering application-owned HTML. Citation parsing remains in the
generation/service layer.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

import streamlit as st

from service.qa_service import QuestionResponse, normalize_latency_rows
from service.ui_models import (
    build_answer_lines, build_source_actions, build_source_cards,
    citation_control_key, clear_source_selection, parse_source_selection,
    select_source_for_turn,
)
from service.ui_runtime import ProductionReadiness

from .view_models import (
    build_source_sections, build_source_text_segments, display_value, safe_html_text,
    resolve_source_text, source_segments_html,
)


def render_app_header(active_mode: str, requested_mode: str, ready: bool) -> None:
    label = _mode_label(active_mode, requested_mode, ready)
    badge_class = "production" if active_mode == "production" and ready else "blocked" if active_mode == "production" else "demo"
    st.markdown(
        '<div class="ga-header">'
        '<div class="ga-brand"><span class="ga-mark" aria-hidden="true"></span>'
        '<span>Grounded</span><span>Document Answer Engine</span></div>'
        f'<span class="ga-mode {badge_class}">{safe_html_text(label)}</span></div>',
        unsafe_allow_html=True,
    )


def render_landing_hero(
    *,
    active_mode: str,
    config_name: str,
    readiness: ProductionReadiness,
    examples: Sequence[tuple[str, str]],
) -> str | None:
    st.markdown(
        '<section class="ga-hero">'
        '<div class="ga-eyebrow">Grounded answers from your documents</div>'
        '<h1>What would you like to understand?</h1>'
        '<p>Ask a question and trace every answer back to its retrieved evidence.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    submitted_question: str | None = None
    with st.form("landing-search", clear_on_submit=False):
        question = st.text_area(
            "Question",
            height=126,
            placeholder="Ask a question about the available documents…",
            label_visibility="collapsed",
        )
        toolbar_left, toolbar_right = st.columns([5, 1])
        mode_text = "Demo Preview · no external calls" if active_mode == "demo" else f"Production · {config_name}"
        toolbar_left.markdown(f'<span class="ga-composer-meta">{safe_html_text(mode_text)}</span>', unsafe_allow_html=True)
        submitted = toolbar_right.form_submit_button("Ask", type="primary", use_container_width=True)
        if submitted:
            submitted_question = question

    st.markdown('<div class="ga-examples"><div class="ga-section-label">Try an example</div></div>', unsafe_allow_html=True)
    columns = st.columns(min(4, len(examples)))
    for index, (label, query) in enumerate(examples):
        if columns[index % len(columns)].button(label, key=f"example-{index}", use_container_width=True):
            submitted_question = query
    st.markdown(
        f'<div class="ga-landing-status"><span class="ga-status-dot"></span>{safe_html_text(_landing_status(active_mode, readiness))}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Enter submits with the Ask button; use Shift+Enter for a new line in the composer.")
    return submitted_question


def render_blocked_setup(readiness: ProductionReadiness) -> None:
    st.markdown(
        '<section class="ga-state"><h3>Production is not ready</h3>'
        '<p>Resolve the required setup items, or switch to Demo Preview to inspect the interface.</p></section>',
        unsafe_allow_html=True,
    )
    for blocker in readiness.blockers[:5]:
        st.write(f"— {blocker}")


def render_turn(response: QuestionResponse, question: str, turn_number: int, show_diagnostics: bool) -> str | None:
    if turn_number > 1:
        st.markdown('<div class="ga-turn-divider"></div>', unsafe_allow_html=True)
    with st.container(key=f"answer-thread-{turn_number}"):
        st.markdown(f'<h1 class="ga-question">{safe_html_text(question)}</h1>', unsafe_allow_html=True)
        elapsed = response.latency.get("total")
        elapsed_label = f"{elapsed:.0f} ms" if isinstance(elapsed, (int, float)) else "Time N/A"
        mode_label = "Demo Preview" if response.is_mock else "Production"
        mock_note = '<span>Mock content · no real retrieval or model call</span>' if response.is_mock else ""
        st.markdown(
            '<div class="ga-status-row">'
            f'<span class="ga-mode {"demo" if response.is_mock else "production"}">{mode_label}</span>'
            f'<span>{len(response.citation_sources)} cited source{"s" if len(response.citation_sources) != 1 else ""}</span>'
            f'<span>{safe_html_text(elapsed_label)}</span>{mock_note}</div>',
            unsafe_allow_html=True,
        )

        if response.status == "completed":
            render_answer_article(response, turn_number)
        elif response.status == "abstained":
            render_abstention_state()
        elif response.status in {"blocked", "deferred"}:
            title = "Configuration deferred" if response.status == "deferred" else "Production is not ready"
            render_status_state(title, response.error.message if response.error else "Review runtime readiness in Settings.")
        else:
            render_error_state(response)

        for warning in (*response.warnings, *response.citation_warnings):
            if response.is_mock and (
                warning.startswith("Demo values only")
                or warning.startswith("Structural citation coverage")
            ):
                continue
            st.warning(warning, icon=None)

        render_selected_source(response, turn_number)
        render_cited_source_rail(response, turn_number)
        suggestion = render_followup_suggestions(response.suggested_followups, turn_number)
        render_diagnostics_tabs(response, turn_number, show_diagnostics)
    return suggestion


def render_answer_article(response: QuestionResponse, turn_number: int) -> None:
    st.markdown('<div class="ga-answer-marker"></div>', unsafe_allow_html=True)
    answer = response.answer or "No final answer returned."
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
                    help=f"Preview source {citation_id}",
                ):
                    _select_source(response.citation_sources, turn_number, citation_id, viewer_open=False)
                    st.rerun()


def render_selected_source(response: QuestionResponse, turn_number: int) -> None:
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
    st.markdown('<div class="ga-section-label">Selected citation</div>', unsafe_allow_html=True)
    with st.container(border=True):
        header_left, header_right = st.columns([5, 1])
        header_left.markdown(f"**[{card.citation_id}] {card.title}**")
        header_right.caption("DEMO SOURCE" if card.is_mock else "RETRIEVED")
        st.caption(" · ".join(value for value in (
            card.detail or "Article/section N/A",
            f"Page {card.page}" if card.page is not None else "Page N/A",
            f"Rank {card.rank}",
            f"Score {card.score:.3f}" if card.score is not None else "Score N/A",
        )))
        st.write(card.preview or "No preview available.")
        evidence = build_source_text_segments(card.full_text, card.evidence, context_id=source.context_id)
        status = evidence.label or (
            "Span unavailable" if evidence.status == "unavailable" else "Recorded span invalid"
        )
        st.caption(f"Evidence-span status · {status}")
        action_columns = st.columns(2 if actions.original_url else 1)
        if action_columns[0].button(
            actions.view_label, key=f"view-source-preview-{turn_number}-{citation_id}",
            type="primary", use_container_width=True,
        ):
            _select_source(response.citation_sources, turn_number, citation_id, viewer_open=True)
            st.rerun()
        if actions.original_url and actions.original_label:
            action_columns[1].link_button(
                actions.original_label, actions.original_url, use_container_width=True,
            )
    if selection.viewer_open:
        _render_source_dialog(source, card, evidence)


@st.dialog("Source details", width="large", dismissible=False)
def _render_source_dialog(source: Any, card: Any, evidence: Any) -> None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    turn_id = selection.turn_id if selection else 0
    heading, close_column = st.columns([5, 1])
    heading.markdown(f"### Source [{card.citation_id}]")
    if close_column.button(
        "Close", key=f"close-source-{turn_id}-{card.citation_id}", use_container_width=True,
    ):
        _close_source_viewer()
        st.rerun()
    st.markdown(f"**{card.title}**")
    st.caption("DEMO SOURCE · MOCK CONTENT" if card.is_mock else "PRODUCTION · RETRIEVED CHUNK")
    metadata = (
        ("Document ID", card.document_id or "N/A"), ("Chunk ID", card.chunk_id or "N/A"),
        ("Article", source.article or "N/A"), ("Section", source.section or "N/A"),
        ("Page", card.page if card.page is not None else "N/A"),
        ("Source path", card.source_path or "N/A"),
        ("Retrieval rank", card.rank), ("Score", f"{card.score:.3f}" if card.score is not None else "N/A"),
        ("Citation use", f"[{card.citation_id}]"), ("Evidence span", evidence.label or evidence.status),
    )
    metadata_columns = st.columns(2)
    for index, (label, value) in enumerate(metadata):
        metadata_columns[index % 2].caption(f"{label.upper()} · {value}")
    if card.is_mock:
        st.caption("Mock content — not an authoritative document")
    st.markdown("#### Full retrieved context")
    if evidence.status == "valid":
        st.caption(f"{evidence.label} · Recorded evidence for this source")
        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
    elif evidence.status == "invalid":
        st.warning("The recorded evidence span could not be validated against this source.", icon=None)
        st.text(card.full_text or "Unavailable")
    else:
        st.info("This source was cited, but an exact supporting passage was not recorded.", icon=None)
        st.text(card.full_text or "Unavailable")
    actions = build_source_actions(source)
    footer_columns = st.columns(2 if actions.original_url else 1)
    if footer_columns[0].button(
        "Close", key=f"close-source-footer-{turn_id}-{card.citation_id}", use_container_width=True,
    ):
        _close_source_viewer()
        st.rerun()
    if actions.original_url and actions.original_label:
        footer_columns[1].link_button(actions.original_label, actions.original_url, use_container_width=True)


def render_cited_source_rail(response: QuestionResponse, turn_number: int) -> None:
    cards = build_source_cards(response.citation_sources)
    if not cards:
        return
    st.markdown('<div class="ga-section-label">Sources referenced</div><div class="ga-source-rail"></div>', unsafe_allow_html=True)
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
                + f'<div class="ga-source-excerpt">{safe_html_text(card.preview or "No preview available.")}</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                actions.view_label, key=f"view-source-card-{turn_number}-{card.citation_id}",
                use_container_width=True,
            ):
                _select_source(response.citation_sources, turn_number, card.citation_id, viewer_open=True)
                st.rerun()
            if actions.original_url and actions.original_label:
                st.link_button(actions.original_label, actions.original_url, use_container_width=True)


def render_followup_suggestions(suggestions: Sequence[str], turn_number: int) -> str | None:
    if not suggestions:
        return None
    st.markdown('<div class="ga-section-label">Explore further</div>', unsafe_allow_html=True)
    for index, suggestion in enumerate(suggestions[:3]):
        if st.button(f"{suggestion}  →", key=f"followup-{turn_number}-{index}", use_container_width=True):
            return suggestion
    return None


def render_followup_composer() -> str | None:
    with st.container(key="followup-composer"):
        return st.chat_input("Ask a follow-up about the available evidence")


def render_diagnostics_tabs(response: QuestionResponse, turn_number: int, show_diagnostics: bool) -> None:
    sources_tab, details_tab, latency_tab, trace_tab, diagnostics_tab = st.tabs(
        ["Sources", "Details", "Latency", "Agent trace", "Diagnostics"]
    )
    with sources_tab:
        render_full_sources(response, turn_number)
    with details_tab:
        render_details(response)
    with latency_tab:
        render_latency_cards(response.latency, is_mock=response.is_mock)
    with trace_tab:
        render_agent_trace(response)
    with diagnostics_tab:
        render_diagnostics(response, show_diagnostics)


def render_full_sources(response: QuestionResponse, turn_number: int) -> None:
    sections = build_source_sections(response.citation_sources, response.contexts)
    contexts = {(row.chunk_id, row.rank): row for row in response.contexts}
    if response.citation_sources:
        st.markdown("### Cited sources")
        for card in sections.cited:
            with st.container(border=True):
                top_left, top_right = st.columns([5, 1])
                top_left.markdown(f"**[{card.citation_id}] {card.title}**")
                top_right.caption("DEMO SOURCE" if card.is_mock else "RETRIEVED")
                metadata = " · ".join((
                    card.detail or "Article/section N/A",
                    f"Page {card.page}" if card.page is not None else "Page N/A",
                    f"Rank {card.rank}",
                    f"Score {card.score:.3f}" if card.score is not None else "Score N/A",
                ))
                st.caption(metadata)
                st.write(card.preview or "No excerpt available.")
                source = next(item for item in response.citation_sources if item.citation_id == card.citation_id)
                source_actions = build_source_actions(source)
                context = contexts.get((source.chunk_id, card.rank))
                with st.expander("Preview retrieved context"):
                    full_text = (context.text if context else card.full_text) or ""
                    evidence = build_source_text_segments(full_text, card.evidence, context_id=source.context_id)
                    if evidence.status == "valid":
                        st.caption(f"{evidence.label} · Recorded evidence for this source")
                        st.markdown(source_segments_html(evidence), unsafe_allow_html=True)
                    elif evidence.status == "invalid":
                        st.warning("The recorded evidence span could not be validated against this source text.", icon=None)
                        st.text(full_text or "Unavailable")
                    else:
                        st.caption("Exact supporting passage was not recorded for this citation.")
                        st.text(full_text or "Unavailable")
                action_columns = st.columns(2 if source_actions.original_url else 1)
                if action_columns[0].button(
                    source_actions.view_label,
                    key=f"view-source-tab-{turn_number}-{card.citation_id}",
                    use_container_width=True,
                ):
                    _select_source(response.citation_sources, turn_number, card.citation_id, viewer_open=True)
                    st.rerun()
                if source_actions.original_url and source_actions.original_label:
                    action_columns[1].link_button(
                        source_actions.original_label, source_actions.original_url,
                        use_container_width=True,
                    )

    additional = sections.additional
    if additional:
        st.markdown("### Additional retrieved sources")
        st.caption("Retrieved context that was not cited in the answer.")
        for row in additional:
            with st.container(border=True):
                st.caption("DEMO SOURCE" if row.is_mock else "ADDITIONAL CONTEXT")
                st.markdown(f"**{row.title or row.document_id or row.chunk_id or 'Retrieved context'}**")
                st.caption(f"Rank {row.rank} · Score {row.score if row.score is not None else 'N/A'}")
                st.write(row.preview or "No excerpt available.")
                with st.expander("Expand context"):
                    st.text(row.text or "Unavailable")
    if not response.contexts:
        st.caption("No retrieved sources are available for this turn.")


def render_details(response: QuestionResponse) -> None:
    diagnostics = response.diagnostics
    values = (
        ("Config", diagnostics.get("selected_config")),
        ("Retriever", diagnostics.get("retriever_backend")),
        ("Embedding", diagnostics.get("embedding_identity")),
        ("Index", _nested(diagnostics, "artifact_identity", "index_version")),
        ("Corpus", _nested(diagnostics, "artifact_identity", "corpus_identity")),
        ("Mode", diagnostics.get("runtime_mode") or response.mode),
    )
    columns = st.columns(2)
    for index, (label, value) in enumerate(values):
        with columns[index % 2].container(border=True):
            st.caption(label.upper())
            st.write(display_value(value))
    st.caption("Citation metrics are structural placement checks, not semantic entailment.")
    with st.expander("Citation metrics"):
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


def render_agent_trace(response: QuestionResponse) -> None:
    if not response.trace:
        st.caption("No agent trace applies to this turn.")
        return
    if response.is_mock:
        st.caption("DEMO TRACE · No production planner executed.")
    for row in response.trace:
        step = row.get("step", "—")
        event = row.get("event") or row.get("action") or "Step"
        status = row.get("status") or "completed"
        with st.container(border=True):
            st.markdown(f"**Step {step} · {event}**")
            st.caption(str(status))
    with st.expander("Raw bounded trace"):
        st.json(list(response.trace), expanded=False)


def render_diagnostics(response: QuestionResponse, show_diagnostics: bool) -> None:
    if not show_diagnostics:
        st.caption("Enable Show diagnostics in Settings to inspect safe runtime metadata.")
        return
    warnings = response.citation_warnings
    if warnings:
        st.markdown("**Citation warnings**")
        for warning in warnings:
            st.write(f"— {warning}")
    with st.expander("Safe runtime diagnostics", expanded=True):
        st.json(response.diagnostics, expanded=False)
    with st.expander("Effective configuration"):
        st.json(response.resolved_config, expanded=False)


def render_readiness_summary(readiness: ProductionReadiness) -> None:
    ready_count = sum(check.status == "ready" for check in readiness.checks)
    st.caption(f"{ready_count} of {len(readiness.checks)} checks ready")
    for check in readiness.checks[:7]:
        symbol = "●" if check.status == "ready" else "○" if check.status in {"warning", "deferred"} else "×"
        st.caption(f"{symbol} {check.name.replace('_', ' ').title()} · {check.status}")
    if len(readiness.checks) > 7:
        st.caption(f"+ {len(readiness.checks) - 7} more checks")


def render_abstention_state() -> None:
    st.markdown(
        '<section class="ga-state"><h3>Not enough evidence</h3>'
        '<p>The available sources did not provide sufficient support for a reliable answer.</p></section>',
        unsafe_allow_html=True,
    )


def render_error_state(response: QuestionResponse) -> None:
    stage = safe_html_text(response.error.stage if response.error else "unknown")
    st.markdown(
        '<section class="ga-state"><h3>Unable to complete this request</h3>'
        f'<p>Stage: {stage}. Review diagnostics and retry.</p></section>',
        unsafe_allow_html=True,
    )
    if response.error:
        st.write(response.error.message)


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


def _mode_label(active_mode: str, requested_mode: str, ready: bool) -> str:
    if requested_mode == "Auto":
        return f"Auto · {'Production' if active_mode == 'production' and ready else 'Demo'}"
    if active_mode == "production" and not ready:
        return "Production · Blocked"
    return "Production" if active_mode == "production" else "Demo Preview"


def _landing_status(active_mode: str, readiness: ProductionReadiness) -> str:
    if active_mode == "demo":
        return "Demo Preview · No retrieval or model call"
    if readiness.ready:
        count = len(readiness.candidates) or (1 if readiness.selected_artifact else 0)
        return f"Production ready · {count} compatible index{'es' if count != 1 else ''} detected"
    blocker = readiness.blockers[0] if readiness.blockers else "Readiness checks did not pass"
    return f"Production unavailable · {blocker}"


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


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
    "render_followup_composer", "render_landing_hero", "render_readiness_summary", "render_turn",
]
