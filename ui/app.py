"""Polished dual-mode Streamlit entry point for grounded document answers."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import streamlit as st  # noqa: E402

from service.qa_service import (  # noqa: E402
    FILTER_PROFILES, TOP_K_MAX, TOP_K_MIN, QuestionRequest, answer_question,
    apply_safe_overrides, build_question_resources, format_safe_error,
    list_interactive_configs, load_ui_config_registry,
)
from service.ui_models import (  # noqa: E402
    ConversationTurn, SourceSelection, append_conversation_turn, clear_conversation,
    clear_source_selection,
)
from service.ui_runtime import (  # noqa: E402
    AUTO_MODE, DEMO_MODE, RUNTIME_MODES, DemoAnswerProvider, ProductionAnswerProvider,
    ProductionReadiness, resolve_runtime_mode, scan_production_readiness,
)
from src.ui.components import (  # noqa: E402
    render_app_header, render_blocked_setup, render_design_preview,
    render_followup_composer, render_landing_hero, render_readiness_summary, render_turn,
)
from src.ui.styles import build_application_css  # noqa: E402
from src.ui.theme import THEME_CHOICES  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "configs" / "ablation_configs.yaml"
DEMO_EXAMPLES = (
    ("Long answer · 3 sources", "Show a complete example with several supporting sources"),
    ("Single source", "Show a single source example"),
    ("Multiple sources", "Show an example with multiple sources"),
    ("Insufficient evidence", "Show an abstention example."),
    ("Invalid citation", "Show an invalid citation example."),
)
PRODUCTION_EXAMPLES = (
    ("Requirements", "What requirements are described in these documents?"),
    ("Best source", "Which retrieved source most directly addresses my question?"),
    ("Limitations", "What exceptions or limitations should I review?"),
)


@st.cache_resource(show_spinner=False)
def _cached_registry(path: str, modified_ns: int) -> dict[str, dict[str, Any]]:
    del modified_ns
    return load_ui_config_registry(Path(path))


@st.cache_resource(show_spinner=False)
def _cached_resources(config_json: str, project_root: str, cache_epoch: int):
    del cache_epoch
    return build_question_resources(json.loads(config_json), project_root=Path(project_root))


@st.cache_data(show_spinner=False)
def _cached_readiness(
    config_json: str, config_name: str, project_root: str,
    selected_artifact: str | None, cache_epoch: int,
) -> ProductionReadiness:
    del cache_epoch
    config = json.loads(config_json)
    return scan_production_readiness(
        {config_name: config}, config_name, project_root=Path(project_root),
        selected_artifact=Path(selected_artifact) if selected_artifact else None,
    )


def main() -> None:
    st.set_page_config(page_title="Grounded · Document Answer Engine", layout="wide", initial_sidebar_state="auto")
    _initialize_state()
    with st.sidebar:
        st.markdown("### Runtime")
        theme_choice = st.selectbox("Theme", THEME_CHOICES, key="theme_choice")
    st.markdown(f"<style>{build_application_css(theme_choice)}</style>", unsafe_allow_html=True)

    preview_page = st.query_params.get("preview")
    if preview_page == "design-system":
        render_app_header("demo", DEMO_MODE, False)
        response = DemoAnswerProvider().answer(QuestionRequest(DEMO_EXAMPLES[0][1], "design-preview"))
        render_design_preview(response)
        return
    if preview_page == "landing":
        render_app_header("demo", DEMO_MODE, False)
        preview_readiness = ProductionReadiness(
            False, "design-preview", "faiss", None, (), ("Missing compatible index manifest.",),
            (), (), None, {},
        )
        render_landing_hero(
            active_mode="demo", config_name="design-preview",
            readiness=preview_readiness, examples=DEMO_EXAMPLES,
        )
        return
    if preview_page in {"long-answer", "production-mapping"}:
        response = DemoAnswerProvider().answer(QuestionRequest(DEMO_EXAMPLES[0][1], "design-preview"))
        active_mode = "demo"
        if preview_page == "production-mapping":
            active_mode = "production"
            response = replace(
                response, mode="production", is_mock=False,
                warnings=(), citation_warnings=(),
                contexts=tuple(replace(row, is_mock=False) for row in response.contexts),
                citation_sources=tuple(replace(source, is_mock=False, evidence=None) for source in response.citation_sources),
                citation_references=tuple(replace(reference, evidence=None) for reference in response.citation_references),
                diagnostics={
                    **response.diagnostics,
                    "runtime_mode": "production-fixture",
                    "evidence_capability": "SOURCE_MAPPING_ONLY",
                    "evidence_spans_available": 0,
                    "evidence_spans_valid": 0,
                    "evidence_spans_rejected": 0,
                    "span_validation_warnings": [],
                },
            )
        _set_preview_selection(response)
        render_app_header(active_mode, DEMO_MODE if active_mode == "demo" else "Production", True)
        render_turn(response, DEMO_EXAMPLES[0][1], 1, True)
        return
    if preview_page == "blocked":
        render_app_header("production", "Production", False)
        preview_readiness = ProductionReadiness(
            False, "design-preview", "faiss", None, (),
            ("Missing compatible index manifest.", "Provider credential is not configured."),
            (), (), None, {},
        )
        render_blocked_setup(preview_readiness)
        return

    try:
        registry = _cached_registry(str(CONFIG_PATH), CONFIG_PATH.stat().st_mtime_ns)
        options = list_interactive_configs(registry, project_root=PROJECT_ROOT)
    except Exception as exc:
        st.error(f"Configuration registry could not be loaded: {format_safe_error(exc)}")
        return
    if not options:
        st.error("No interactive production configurations are available.")
        return

    settings = _render_settings(registry, options)
    readiness = settings["readiness"]
    resolution = resolve_runtime_mode(settings["requested_mode"], readiness)
    _isolate_thread(resolution.active_mode, settings["requested_mode"], settings["config_name"])
    render_app_header(resolution.active_mode, settings["requested_mode"], readiness.ready)

    turns: list[ConversationTurn] = st.session_state["conversation"]
    if not turns:
        examples = DEMO_EXAMPLES if resolution.active_mode == "demo" else PRODUCTION_EXAMPLES
        question = render_landing_hero(
            active_mode=resolution.active_mode, config_name=settings["config_name"],
            readiness=readiness, examples=examples,
        )
        if settings["requested_mode"] == "Production" and not readiness.ready:
            render_blocked_setup(readiness)
        if question is not None:
            _submit(question, settings, readiness, resolution.active_mode)
    else:
        suggested: str | None = None
        for index, turn in enumerate(turns, 1):
            turn_id = turn.turn_id if turn.turn_id is not None else index
            value = render_turn(turn.response, turn.question, turn_id, settings["show_diagnostics"])
            suggested = suggested or value
        followup = suggested or render_followup_composer()
        if followup:
            _submit(followup, settings, readiness, resolution.active_mode)

    if st.session_state.get("notice"):
        st.toast(st.session_state["notice"])
        st.session_state["notice"] = None


def _render_settings(registry: dict[str, dict[str, Any]], options: Sequence[Any]) -> dict[str, Any]:
    labels = {f"{item.name} · {item.status}": item.name for item in options}
    with st.sidebar:
        requested_mode = st.selectbox("Mode", RUNTIME_MODES, key="runtime_mode")
        st.markdown("### Retrieval")
        label_values = list(labels)
        preferred_index = next((index for index, label in enumerate(label_values) if labels[label] == "Agent-None-PlainRAG"), 0)
        selected_label = st.selectbox("Named configuration", label_values, index=preferred_index)
        config_name = labels[selected_label]
        selected = registry[config_name]
        retrieval = selected["retrieval"]
        top_k = st.number_input("Top-k", TOP_K_MIN, TOP_K_MAX, int(retrieval["top_k"]))
        profile = str(retrieval.get("filter_profile") or "broad")
        filter_profile = st.selectbox(
            "Filter profile", FILTER_PROFILES,
            index=FILTER_PROFILES.index(profile) if profile in FILTER_PROFILES else 0,
        )
        st.markdown("### Advanced")
        graph = st.toggle("Graph", value=False, disabled=True, help="Unavailable until the production graph adapter is integrated.")
        reranker = st.toggle("Reranker", value=False, disabled=True, help="Unavailable until the production reranker adapter is integrated.")
        show_diagnostics = st.toggle("Show diagnostics", value=False)

    try:
        effective = apply_safe_overrides(
            selected, QuestionRequest("", config_name, int(top_k), graph, reranker, filter_profile),
        )
    except Exception as exc:
        effective = selected
        st.sidebar.warning(format_safe_error(exc))

    readiness = _cached_readiness(
        json.dumps(effective, ensure_ascii=False, sort_keys=True), config_name,
        str(PROJECT_ROOT), None, st.session_state["cache_epoch"],
    )
    if len(readiness.candidates) > 1:
        with st.sidebar:
            choices = {candidate.label: candidate for candidate in readiness.candidates}
            artifact_label = st.selectbox("Compatible artifact", list(choices))
        readiness = _cached_readiness(
            json.dumps(effective, ensure_ascii=False, sort_keys=True), config_name,
            str(PROJECT_ROOT), str(choices[artifact_label].index_dir), st.session_state["cache_epoch"],
        )

    with st.sidebar:
        st.markdown("### Actions")
        action_a, action_b = st.columns(2)
        if action_a.button("New search", use_container_width=True):
            st.session_state["conversation"] = clear_conversation()
            _clear_source_selection()
            st.rerun()
        if action_b.button("Clear conversation", use_container_width=True):
            st.session_state["conversation"] = clear_conversation()
            _clear_source_selection()
            st.session_state["notice"] = "Conversation cleared."
            st.rerun()
        if st.button("Clear resource cache", use_container_width=True):
            _cached_registry.clear()
            _cached_resources.clear()
            _cached_readiness.clear()
            st.session_state["cache_epoch"] += 1
            st.session_state["notice"] = "Production resources and readiness were refreshed."
            st.rerun()
        st.markdown("### Production readiness")
        render_readiness_summary(readiness)
        with st.expander("Readiness details"):
            for blocker in readiness.blockers:
                st.write(f"Blocked · {blocker}")
            for warning in readiness.warnings:
                st.write(f"Warning · {warning}")

    return {
        "requested_mode": requested_mode, "config_name": config_name,
        "top_k": int(top_k), "filter_profile": filter_profile,
        "graph": graph, "reranker": reranker, "show_diagnostics": show_diagnostics,
        "registry": registry, "readiness": readiness,
    }


def _submit(question: str, settings: dict[str, Any], readiness: ProductionReadiness, active_mode: str) -> None:
    if not question.strip():
        st.session_state["notice"] = "Enter a question before submitting."
        return
    request = QuestionRequest(
        question.strip(), settings["config_name"], settings["top_k"],
        settings["graph"], settings["reranker"], settings["filter_profile"],
    )
    try:
        with st.status("Checking available sources…", expanded=True) as progress:
            if active_mode == "demo":
                progress.update(label="Preparing the deterministic interface preview…")
                provider = DemoAnswerProvider()
            else:
                if not readiness.ready:
                    progress.update(label="Production readiness checks did not pass.", state="error")
                    st.session_state["notice"] = "Production is blocked; no demo fallback was used."
                    return
                progress.update(label="Loading the configured retrieval resources…")
                resources = _cached_resources(
                    json.dumps(readiness.resolved_config, ensure_ascii=False, sort_keys=True),
                    str(PROJECT_ROOT), st.session_state["cache_epoch"],
                )
                provider = ProductionAnswerProvider(lambda value: answer_question(
                    value, registry={settings["config_name"]: readiness.resolved_config},
                    resources=resources, project_root=PROJECT_ROOT,
                ))
                progress.update(label="Retrieving context and preparing a grounded answer…")
            response = provider.answer(request)
            progress.update(label="Validating source references…")
            response = replace(response, diagnostics=_response_diagnostics(response, settings, readiness))
            progress.update(label="Answer ready", state="complete", expanded=False)
        st.session_state["conversation"] = append_conversation_turn(
            st.session_state["conversation"], ConversationTurn(
                question.strip(), response, st.session_state["next_turn_id"],
            ),
        )
        st.session_state["next_turn_id"] += 1
        _clear_source_selection()
        st.rerun()
    except Exception as exc:
        st.session_state["notice"] = f"Unable to complete the request safely: {format_safe_error(exc)}"


def _response_diagnostics(response: Any, settings: dict[str, Any], readiness: ProductionReadiness) -> dict[str, Any]:
    diagnostics = dict(response.diagnostics)
    diagnostics.update({
        "runtime_mode": response.mode, "production_ready": readiness.ready,
        "selected_config": settings["config_name"], "retriever_backend": readiness.retriever_backend,
        "embedding_identity": readiness.embedding_identity,
        "top_k": settings["top_k"], "filter_profile": settings["filter_profile"],
        "graph_enabled": settings["graph"], "reranker_enabled": settings["reranker"],
        "selected_artifact": str(readiness.selected_artifact.index_dir) if readiness.selected_artifact else None,
        "artifact_identity": ({
            "manifest": str(readiness.selected_artifact.manifest_path),
            "embedding_dimension": readiness.selected_artifact.embedding_dimension,
            "index_version": readiness.selected_artifact.index_version,
            "corpus_identity": readiness.selected_artifact.corpus_identity,
            "payload_count": readiness.selected_artifact.payload_count,
            "vector_count": readiness.selected_artifact.vector_count,
            "created_at": readiness.selected_artifact.created_at,
        } if readiness.selected_artifact else None),
    })
    return diagnostics


def _initialize_state() -> None:
    st.session_state.setdefault("cache_epoch", 0)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("notice", None)
    st.session_state.setdefault("runtime_mode", AUTO_MODE)
    st.session_state.setdefault("theme_choice", "System")
    st.session_state.setdefault("next_turn_id", 1)
    st.session_state.setdefault("selected_source", None)
    query_theme = st.query_params.get("theme")
    if query_theme in THEME_CHOICES and st.session_state.get("query_theme") != query_theme:
        st.session_state["theme_choice"] = query_theme
        st.session_state["query_theme"] = query_theme


def _isolate_thread(active_mode: str, requested_mode: str, config_name: str) -> None:
    signature = (requested_mode, active_mode, config_name)
    if st.session_state.get("thread_signature") not in (None, signature):
        st.session_state["conversation"] = clear_conversation()
        _clear_source_selection()
        st.session_state["notice"] = "Conversation cleared because runtime mode or configuration changed."
    st.session_state["thread_signature"] = signature


def _clear_source_selection() -> None:
    clear_source_selection(st.session_state)
    if "citation" in st.query_params:
        del st.query_params["citation"]
    if "full_source" in st.query_params:
        del st.query_params["full_source"]


def _set_preview_selection(response: Any) -> None:
    value = st.query_params.get("citation")
    if isinstance(value, str) and value.startswith("1-"):
        try:
            citation_id = int(value.split("-", 1)[1])
        except ValueError:
            return
        if any(source.citation_id == citation_id for source in response.citation_sources):
            st.session_state["selected_source"] = SourceSelection(
                1, citation_id, st.query_params.get("full_source") == "1",
            ).to_state()


if __name__ == "__main__":
    main()
