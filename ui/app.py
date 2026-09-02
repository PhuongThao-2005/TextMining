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

from service.local_env import apply_local_environment  # noqa: E402

apply_local_environment(PROJECT_ROOT)

import streamlit as st  # noqa: E402

from service.qa_service import (  # noqa: E402
    FILTER_PROFILES, TOP_K_MAX, TOP_K_MIN, QuestionRequest, answer_question,
    apply_safe_overrides, build_question_resources, format_safe_error,
    list_interactive_configs, load_ui_config_registry,
)
from service.ui_models import (  # noqa: E402
    ConversationTurn, SourceSelection, append_conversation_turn, clear_conversation,
    clear_source_selection, parse_source_selection,
)
from service.ui_runtime import (  # noqa: E402
    AUTO_MODE, DEMO_MODE, RUNTIME_MODES, DemoAnswerProvider, ProductionAnswerProvider,
    ProductionReadiness, graph_download_warnings, load_demo_qa_examples, resolve_graph_pickle_path,
    resolve_runtime_mode, scan_production_readiness,
)
from src.ui.components import (  # noqa: E402
    render_app_header, render_blocked_setup, render_design_preview,
    render_evidence_panel, render_followup_composer, render_landing_hero,
    render_readiness_summary, render_sidebar_brand, render_turn,
)
from src.ui.i18n import LANGUAGE_LABELS, LANGUAGE_OPTIONS, normalize_language, t, theme_label  # noqa: E402
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
DEMO_EXAMPLES_VI = (
    ("Câu trả lời dài · 3 nguồn", "Hiển thị ví dụ đầy đủ với nhiều nguồn hỗ trợ"),
    ("Một nguồn", "Hiển thị ví dụ với một nguồn"),
    ("Nhiều nguồn", "Hiển thị ví dụ với nhiều nguồn"),
    ("Không đủ bằng chứng", "Hiển thị ví dụ hệ thống từ chối trả lời."),
    ("Trích dẫn sai", "Hiển thị ví dụ trích dẫn không hợp lệ."),
)
PRODUCTION_EXAMPLES_EN = (
    ("Rule", "How many annual leave days does an employee receive?"),
    ("Exception", "Which cases do not apply this rule?"),
    ("Legal source", "Which document governs severance allowance?"),
)
PRODUCTION_EXAMPLES_VI = (
    ("Quy định", "Người lao động được nghỉ phép năm bao nhiêu ngày?"),
    ("Ngoại lệ", "Trường hợp nào không áp dụng quy định này?"),
    ("Nguồn pháp lý", "Văn bản nào quy định về trợ cấp thôi việc?"),
)
CUSTOM_MODEL_OPTION = "__custom_model__"
PROMPT_STRATEGIES = ("base", "reasoning")


def _demo_examples(lang: str) -> tuple[tuple[str, str], ...]:
    qa_examples = load_demo_qa_examples(PROJECT_ROOT, lang=lang)
    if qa_examples:
        return qa_examples
    return DEMO_EXAMPLES_VI if lang == "vi" else DEMO_EXAMPLES


def _production_examples(lang: str) -> tuple[tuple[str, str], ...]:
    return PRODUCTION_EXAMPLES_VI if lang == "vi" else PRODUCTION_EXAMPLES_EN


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
    st.set_page_config(page_title="LexVN · Legal Q&A", layout="wide", initial_sidebar_state="expanded")
    _initialize_state()
    with st.sidebar:
        sidebar_lang = normalize_language(st.session_state.get("language_choice"))
        render_sidebar_brand(sidebar_lang)
        st.markdown(f"### {t(sidebar_lang, 'navigation')}")
        if st.button(t(sidebar_lang, "new_search"), key="sidebar-new-search", use_container_width=True):
            st.session_state["conversation"] = clear_conversation()
            _clear_source_selection()
            st.rerun()
        if st.button(t(sidebar_lang, "nav_history"), key="sidebar-history", use_container_width=True):
            st.session_state["notice"] = t(sidebar_lang, "history_notice")
        st.markdown(f"### {t(sidebar_lang, 'preferences')}")
        lang = normalize_language(st.selectbox(
            "Ngôn ngữ / Language",
            LANGUAGE_OPTIONS,
            key="language_choice",
            format_func=lambda value: LANGUAGE_LABELS[value],
        ))
        st.markdown(f"### {t(lang, 'runtime')}")
        theme_choice = st.selectbox(
            t(lang, "theme"), THEME_CHOICES, key="theme_choice",
            format_func=lambda value: theme_label(lang, value),
        )
    st.markdown(f"<style>{build_application_css(theme_choice)}</style>", unsafe_allow_html=True)

    preview_page = st.query_params.get("preview")
    if preview_page == "design-system":
        render_app_header("demo", DEMO_MODE, False, lang, theme_choice=theme_choice)
        response = DemoAnswerProvider().answer(QuestionRequest(_demo_examples(lang)[0][1], "design-preview"))
        render_design_preview(response)
        return
    if preview_page == "landing":
        render_app_header("demo", DEMO_MODE, False, lang, theme_choice=theme_choice)
        preview_readiness = ProductionReadiness(
            False, "design-preview", "faiss", None, (), ("Missing compatible index manifest.",),
            (), (), None, {},
        )
        render_landing_hero(
            active_mode="demo", config_name="design-preview",
            readiness=preview_readiness, examples=_demo_examples(lang), lang=lang,
        )
        return
    if preview_page in {"long-answer", "production-mapping"}:
        response = DemoAnswerProvider().answer(QuestionRequest(_demo_examples(lang)[0][1], "design-preview"))
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
        render_app_header(active_mode, DEMO_MODE if active_mode == "demo" else "Production", True, lang, theme_choice=theme_choice)
        render_turn(response, _demo_examples(lang)[0][1], 1, True, lang)
        return
    if preview_page == "blocked":
        render_app_header("production", "Production", False, lang, theme_choice=theme_choice)
        preview_readiness = ProductionReadiness(
            False, "design-preview", "faiss", None, (),
            ("Missing compatible index manifest.", "Provider credential is not configured."),
            (), (), None, {},
        )
        render_blocked_setup(preview_readiness, lang)
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

    settings = _render_settings(registry, options, lang)
    readiness = settings["readiness"]
    resolution = resolve_runtime_mode(settings["requested_mode"], readiness)
    _isolate_thread(resolution.active_mode, settings["requested_mode"], settings["config_name"])
    render_app_header(resolution.active_mode, settings["requested_mode"], readiness.ready, lang, theme_choice=theme_choice)

    turns: list[ConversationTurn] = st.session_state["conversation"]
    if not turns:
        examples = _demo_examples(lang) if resolution.active_mode == "demo" else _production_examples(lang)
        question = render_landing_hero(
            active_mode=resolution.active_mode, config_name=settings["config_name"],
            readiness=readiness, examples=examples, lang=lang,
        )
        if settings["requested_mode"] == "Production" and not readiness.ready:
            render_blocked_setup(readiness, lang)
        if question is not None:
            _submit(question, settings, readiness, resolution.active_mode)
    else:
        evidence_turn = _selected_evidence_turn(turns)
        suggested: str | None = None
        if evidence_turn is None:
            for index, turn in enumerate(turns, 1):
                turn_id = turn.turn_id if turn.turn_id is not None else index
                value = render_turn(turn.response, turn.question, turn_id, settings["show_diagnostics"], lang)
                suggested = suggested or value
            followup = suggested or render_followup_composer(lang)
            if followup:
                _submit(followup, settings, readiness, resolution.active_mode)
        else:
            main_col, evidence_col = st.columns([0.68, 0.32], gap="large")
            with main_col:
                for index, turn in enumerate(turns, 1):
                    turn_id = turn.turn_id if turn.turn_id is not None else index
                    value = render_turn(turn.response, turn.question, turn_id, settings["show_diagnostics"], lang)
                    suggested = suggested or value
                followup = suggested or render_followup_composer(lang)
                if followup:
                    _submit(followup, settings, readiness, resolution.active_mode)
            with evidence_col:
                render_evidence_panel(evidence_turn.response, evidence_turn.turn_id or len(turns), lang)

    if st.session_state.get("notice"):
        st.toast(st.session_state["notice"])
        st.session_state["notice"] = None


def _render_settings(registry: dict[str, dict[str, Any]], options: Sequence[Any], lang: str) -> dict[str, Any]:
    labels = {f"{item.name} · {item.status}": item.name for item in options}
    with st.sidebar:
        requested_mode = st.selectbox(
            t(lang, "mode"), RUNTIME_MODES, key="runtime_mode",
            format_func=lambda value: {
                AUTO_MODE: t(lang, "mode_auto"),
                DEMO_MODE: t(lang, "mode_demo"),
                "Production": t(lang, "mode_production"),
            }.get(value, value),
        )
        st.markdown(f"### {t(lang, 'retrieval')}")
        label_values = list(labels)
        preferred_index = next((index for index, label in enumerate(label_values) if labels[label] == "Agent-None-PlainRAG"), 0)
        selected_label = st.selectbox(t(lang, "named_configuration"), label_values, index=preferred_index)
        config_name = labels[selected_label]
        selected = registry[config_name]
        retrieval = selected["retrieval"]
        top_k = st.number_input(t(lang, "top_k"), TOP_K_MIN, TOP_K_MAX, int(retrieval["top_k"]))
        profile = str(retrieval.get("filter_profile") or "broad")
        filter_profile = st.selectbox(
            t(lang, "filter_profile"), FILTER_PROFILES,
            index=FILTER_PROFILES.index(profile) if profile in FILTER_PROFILES else 0,
            format_func=lambda value: _filter_profile_label(value, lang),
        )
        generation_settings = _render_generation_controls(selected, lang)
        st.markdown("### Nâng cao" if lang == "vi" else "### Advanced")
        graph_path = resolve_graph_pickle_path(PROJECT_ROOT)
        graph_help = (
            t(lang, "graph_stack_help", path=graph_path.relative_to(PROJECT_ROOT).as_posix())
            if graph_path and graph_path.is_relative_to(PROJECT_ROOT)
            else t(lang, "graph_stack_help", path=graph_path) if graph_path
            else t(lang, "graph_stack_missing")
        )
        graph_stack = st.toggle(
            t(lang, "graph_stack"),
            value=False,
            disabled=graph_path is None,
            help=graph_help,
        )
        for warning in graph_download_warnings(PROJECT_ROOT):
            st.caption(f"{t(lang, 'warning')} · {warning}")
        graph = graph_stack
        reranker = graph_stack
        show_diagnostics = st.toggle(t(lang, "diagnostics"), value=False)

    try:
        effective = apply_safe_overrides(
            selected, _build_question_request(
                "", config_name, int(top_k), graph, reranker, filter_profile, generation_settings,
            ),
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
            artifact_label = st.selectbox(t(lang, "compatible_artifact"), list(choices))
        readiness = _cached_readiness(
            json.dumps(effective, ensure_ascii=False, sort_keys=True), config_name,
            str(PROJECT_ROOT), str(choices[artifact_label].index_dir), st.session_state["cache_epoch"],
        )

    with st.sidebar:
        st.markdown(f"### {t(lang, 'actions')}")
        action_a, action_b = st.columns(2)
        if action_a.button(t(lang, "new_search"), use_container_width=True):
            st.session_state["conversation"] = clear_conversation()
            _clear_source_selection()
            st.rerun()
        if action_b.button(t(lang, "clear_conversation"), use_container_width=True):
            st.session_state["conversation"] = clear_conversation()
            _clear_source_selection()
            st.session_state["notice"] = "Đã xóa hội thoại." if lang == "vi" else "Conversation cleared."
            st.rerun()
        if st.button(t(lang, "clear_resource_cache"), use_container_width=True):
            _cached_registry.clear()
            _cached_resources.clear()
            _cached_readiness.clear()
            st.session_state["cache_epoch"] += 1
            st.session_state["notice"] = t(lang, "cache_cleared")
            st.rerun()
        st.markdown(f"### {t(lang, 'production_readiness')}")
        render_readiness_summary(readiness, lang)
        with st.expander(t(lang, "readiness_details")):
            for blocker in readiness.blockers:
                st.write(f"Blocked · {blocker}")
            for warning in readiness.warnings:
                st.write(f"Warning · {warning}")

    return {
        "requested_mode": requested_mode, "config_name": config_name,
        "top_k": int(top_k), "filter_profile": filter_profile,
        "graph": graph, "reranker": reranker, "show_diagnostics": show_diagnostics,
        **generation_settings,
        "registry": registry, "readiness": readiness, "lang": lang,
    }


def _submit(question: str, settings: dict[str, Any], readiness: ProductionReadiness, active_mode: str) -> None:
    lang = settings.get("lang", "en")
    if not question.strip():
        st.session_state["notice"] = t(lang, "enter_before_submit")
        return
    request = _build_question_request(
        question.strip(), settings["config_name"], settings["top_k"],
        settings["graph"], settings["reranker"], settings["filter_profile"],
        settings,
    )
    try:
        with st.status(t(lang, "checking_sources"), expanded=True) as progress:
            if active_mode == "demo":
                progress.update(label="Đang chuẩn bị demo giao diện..." if lang == "vi" else "Preparing the deterministic interface preview...")
                provider = DemoAnswerProvider()
            else:
                if not readiness.ready:
                    progress.update(label=t(lang, "runtime_blocked_status"), state="error")
                    st.session_state["notice"] = t(lang, "runtime_blocked")
                    return
                progress.update(label=t(lang, "loading_resources"))
                resources = _cached_resources(
                    json.dumps(readiness.resolved_config, ensure_ascii=False, sort_keys=True),
                    str(PROJECT_ROOT), st.session_state["cache_epoch"],
                )
                provider = ProductionAnswerProvider(lambda value: answer_question(
                    value, registry={settings["config_name"]: readiness.resolved_config},
                    resources=resources, project_root=PROJECT_ROOT,
                ))
                progress.update(label="Đang truy xuất ngữ cảnh và chuẩn bị câu trả lời..." if lang == "vi" else "Retrieving context and preparing a grounded answer...")
            response = provider.answer(request)
            progress.update(label=t(lang, "validate_sources"))
            response = replace(response, diagnostics=_response_diagnostics(response, settings, readiness))
            progress.update(label=t(lang, "answer_ready"), state="complete", expanded=False)
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
        "generation_model": settings.get("generation_model"),
        "prompt_strategy": settings.get("prompt_strategy"),
        "temperature": settings.get("temperature"),
        "top_p": settings.get("top_p"),
        "max_output_tokens": settings.get("max_output_tokens"),
        "timeout_seconds": settings.get("timeout_seconds"),
        "max_retries": settings.get("max_retries"),
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


def _render_generation_controls(selected: dict[str, Any], lang: str) -> dict[str, Any]:
    generation = selected.get("generation") if isinstance(selected.get("generation"), dict) else {}
    current_model = str(generation.get("model") or "env:LLM_BASE_MODEL")
    model_options = _unique_options((current_model, "env:LLM_BASE_MODEL", "env:LLM_LARGER_MODEL", CUSTOM_MODEL_OPTION))
    st.markdown(f"### {t(lang, 'model_hyperparameters')}")
    model_choice = st.selectbox(
        t(lang, "model_selector"), model_options,
        index=0,
        format_func=lambda value: _generation_model_label(value, current_model, lang),
    )
    if model_choice == CUSTOM_MODEL_OPTION:
        custom_model = st.text_input(
            t(lang, "custom_model"),
            value="",
            placeholder="gpt-4.1-mini, qwen2.5:7b, llama-3.1-8b...",
            help=t(lang, "custom_model_help"),
        ).strip()
        model = custom_model or current_model
    else:
        model = str(model_choice)

    current_strategy = str(generation.get("prompt_strategy") or "base")
    strategy = st.selectbox(
        t(lang, "prompt_strategy"), PROMPT_STRATEGIES,
        index=PROMPT_STRATEGIES.index(current_strategy) if current_strategy in PROMPT_STRATEGIES else 0,
        format_func=lambda value: t(lang, f"prompt_strategy_{value}"),
    )
    with st.expander(t(lang, "decoding_hyperparameters"), expanded=True):
        temperature = st.number_input(
            t(lang, "temperature"), min_value=0.0, max_value=2.0,
            value=_clamp_float(generation.get("temperature", 0.0), 0.0, 2.0),
            step=0.1, format="%.2f",
        )
        top_p = st.number_input(
            t(lang, "top_p"), min_value=0.05, max_value=1.0,
            value=_clamp_float(generation.get("top_p", 1.0), 0.05, 1.0),
            step=0.05, format="%.2f",
        )
        max_output_tokens = st.number_input(
            t(lang, "max_output_tokens"), min_value=128, max_value=8192,
            value=_clamp_int(generation.get("max_output_tokens", 1024), 128, 8192),
            step=128,
        )
        timeout_seconds = st.number_input(
            t(lang, "timeout_seconds"), min_value=5.0, max_value=300.0,
            value=_clamp_float(generation.get("timeout_seconds", 60.0), 5.0, 300.0),
            step=5.0, format="%.1f",
        )
        max_retries = st.number_input(
            t(lang, "max_retries"), min_value=0, max_value=5,
            value=_clamp_int(generation.get("max_retries", 2), 0, 5),
            step=1,
        )
    st.caption(t(lang, "runtime_override_note"))
    return {
        "generation_model": model,
        "prompt_strategy": strategy,
        "temperature": float(temperature),
        "top_p": float(top_p),
        "max_output_tokens": int(max_output_tokens),
        "timeout_seconds": float(timeout_seconds),
        "max_retries": int(max_retries),
    }


def _build_question_request(
    question: str, config_name: str, top_k: int, graph: bool, reranker: bool,
    filter_profile: str, settings: dict[str, Any],
) -> QuestionRequest:
    return QuestionRequest(
        question=question,
        config_name=config_name,
        top_k_override=top_k,
        graph_enabled_override=graph,
        reranker_enabled_override=reranker,
        filter_profile=filter_profile,
        generation_model_override=settings.get("generation_model"),
        prompt_strategy_override=settings.get("prompt_strategy"),
        temperature_override=settings.get("temperature"),
        top_p_override=settings.get("top_p"),
        max_output_tokens_override=settings.get("max_output_tokens"),
        timeout_seconds_override=settings.get("timeout_seconds"),
        max_retries_override=settings.get("max_retries"),
    )


def _generation_model_label(value: str, current_model: str, lang: str) -> str:
    if value == CUSTOM_MODEL_OPTION:
        return t(lang, "custom_model")
    if value == current_model:
        return f"{t(lang, 'current_config_model')} · {value}"
    if value == "env:LLM_BASE_MODEL":
        return f"{t(lang, 'base_model_env')} · {value}"
    if value == "env:LLM_LARGER_MODEL":
        return f"{t(lang, 'larger_model_env')} · {value}"
    return value


def _unique_options(values: Sequence[str]) -> list[str]:
    options: list[str] = []
    for value in values:
        if value not in options:
            options.append(value)
    return options


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = minimum
    return min(max(numeric, minimum), maximum)


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = minimum
    return min(max(numeric, minimum), maximum)


def _initialize_state() -> None:
    st.session_state.setdefault("cache_epoch", 0)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("notice", None)
    st.session_state.setdefault("runtime_mode", AUTO_MODE)
    st.session_state.setdefault("theme_choice", "System")
    st.session_state.setdefault("language_choice", "vi")
    st.session_state.setdefault("next_turn_id", 1)
    st.session_state.setdefault("selected_source", None)
    query_theme = st.query_params.get("theme")
    if query_theme in THEME_CHOICES and st.session_state.get("query_theme") != query_theme:
        st.session_state["theme_choice"] = query_theme
        st.session_state["query_theme"] = query_theme


def _filter_profile_label(value: str, lang: str) -> str:
    if lang != "vi":
        return value.replace("_", " ").title()
    return {
        "broad": "Rộng",
        "current_law": "Luật hiện hành",
        "historical": "Lịch sử",
    }.get(value, value)


def _isolate_thread(active_mode: str, requested_mode: str, config_name: str) -> None:
    signature = (requested_mode, active_mode, config_name)
    if st.session_state.get("thread_signature") not in (None, signature):
        st.session_state["conversation"] = clear_conversation()
        _clear_source_selection()
        st.session_state["notice"] = "Conversation cleared because runtime mode or configuration changed."
    st.session_state["thread_signature"] = signature


def _selected_evidence_turn(turns: Sequence[ConversationTurn]) -> ConversationTurn | None:
    selection = parse_source_selection(st.session_state.get("selected_source"))
    if selection is None or selection.viewer_open:
        return None
    for index, turn in enumerate(turns, 1):
        turn_id = turn.turn_id if turn.turn_id is not None else index
        if turn_id == selection.turn_id:
            return turn
    return None


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
