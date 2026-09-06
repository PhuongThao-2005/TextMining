"""Polished dual-mode Streamlit entry point for grounded document answers."""
from __future__ import annotations

import json
import os
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
import streamlit.components.v1 as st_components  # noqa: E402

from service.qa_service import (  # noqa: E402
    PreflightCheck, QuestionRequest, answer_question, apply_safe_overrides, build_question_resources,
    format_safe_error, load_ui_config_registry,
)
from service.ui_models import (  # noqa: E402
    ConversationTurn, SourceSelection, clear_conversation, clear_source_selection,
    parse_source_selection,
)
from service.ui_runtime import (  # noqa: E402
    DEMO_MODE, PRODUCTION_MODE, DemoAnswerProvider, ProductionAnswerProvider,
    ProductionReadiness, load_demo_qa_examples, resolve_runtime_mode, scan_production_readiness,
)
from src.ui.components import (  # noqa: E402
    render_app_header, render_blocked_setup, render_design_preview,
    render_evidence_panel, render_followup_composer, render_landing_hero,
    render_sidebar_brand, render_turn,
)
from src.ui.i18n import t  # noqa: E402
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
DEFAULT_CONFIG_NAME = "Agent-None-PlainRAG"
DEFAULT_TOP_K = 5
DEFAULT_FILTER_PROFILE = "broad"
RUNTIME_CHOICES = (PRODUCTION_MODE, DEMO_MODE)
BASE_RETRIEVAL_MODES = ("dense_only", "dense_sparse")
MODEL_CHOICES = ("gpt-4o-mini", "gpt-4.1-mini", "gpt-4o")
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
    lang = "vi"
    theme_choice = str(st.session_state.get("theme_choice") or "System")
    with st.sidebar:
        render_sidebar_brand(lang)
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
        render_turn(response, _demo_examples(lang)[0][1], 1, False, lang)
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
    except Exception as exc:
        st.error(f"Configuration registry could not be loaded: {format_safe_error(exc)}")
        return

    settings = _render_settings(registry, lang)
    readiness = settings["readiness"]
    resolution = resolve_runtime_mode(settings["requested_mode"], readiness)
    _isolate_thread(resolution.active_mode, settings["requested_mode"], settings["settings_signature"])
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
        _render_answer_scroll_anchor()
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


def _render_settings(registry: dict[str, dict[str, Any]], lang: str) -> dict[str, Any]:
    with st.sidebar:
        st.markdown("### Chạy")
        requested_mode = _render_choice_toggle(
            t(lang, "mode"), RUNTIME_CHOICES, "runtime_mode", PRODUCTION_MODE,
            lambda value: t(lang, "mode_demo") if value == DEMO_MODE else t(lang, "mode_production"),
        )
        requested_mode = str(requested_mode or PRODUCTION_MODE)

        st.markdown(f"### {t(lang, 'retrieval')}")
        base_retrieval_mode = _render_choice_toggle(
            t(lang, "retrieval_mode"), BASE_RETRIEVAL_MODES, "retrieval_base_mode", "dense_only",
            lambda value: _base_retrieval_label(str(value)),
            columns_per_row=2,
        )
        base_retrieval_mode = str(base_retrieval_mode or "dense_only")
        st.markdown("### Kết hợp")
        graph_enabled = _render_bool_toggle("Graph", "graph_enabled", False)
        reranker_enabled = _render_bool_toggle("Reranker", "reranker_enabled", False)

        generation_settings = _render_generation_controls(lang)

        st.markdown(f"### {t(lang, 'actions')}")
        if st.session_state.get("conversation"):
            if st.button(t(lang, "new_question"), key="new-question", use_container_width=True):
                st.session_state["conversation"] = clear_conversation()
                st.session_state["scroll_to_answer"] = False
                _clear_source_selection()
                st.session_state["notice"] = t(lang, "new_question_ready")
                st.rerun()
        if st.button(t(lang, "clear_resource_cache"), use_container_width=True):
            _cached_registry.clear()
            _cached_resources.clear()
            _cached_readiness.clear()
            st.session_state["cache_epoch"] += 1
            st.session_state["notice"] = t(lang, "cache_cleared")
            st.rerun()

    retrieval_mode = _compose_retrieval_mode(base_retrieval_mode, graph_enabled, reranker_enabled)
    config_name = _config_for_retrieval_mode(base_retrieval_mode)
    mode_blocker = _retrieval_mode_blocker(base_retrieval_mode)
    if config_name not in registry:
        st.sidebar.warning(f"Không tìm thấy cấu hình {config_name}. Đang dùng {DEFAULT_CONFIG_NAME}.")
        config_name = DEFAULT_CONFIG_NAME
    selected = registry[config_name]
    retrieval = selected["retrieval"]
    top_k = int(retrieval.get("top_k") or DEFAULT_TOP_K)
    filter_profile = str(retrieval.get("filter_profile") or DEFAULT_FILTER_PROFILE)
    sparse = base_retrieval_mode == "dense_sparse"
    graph, fusion, reranker = _retrieval_mode_flags(graph_enabled, reranker_enabled)

    try:
        effective = apply_safe_overrides(
            selected, _build_question_request(
                "", config_name, top_k, sparse, graph, fusion, reranker, filter_profile, generation_settings,
            ),
        )
    except Exception as exc:
        effective = selected
        st.sidebar.warning(format_safe_error(exc))

    readiness = _cached_readiness(
        json.dumps(effective, ensure_ascii=False, sort_keys=True), config_name,
        str(PROJECT_ROOT), None, st.session_state["cache_epoch"],
    )
    if mode_blocker is not None:
        readiness = replace(
            readiness,
            ready=False,
            checks=(PreflightCheck("retrieval_mode", "blocked", mode_blocker), *readiness.checks),
            blockers=(mode_blocker, *readiness.blockers),
        )
    if len(readiness.candidates) > 1:
        with st.sidebar:
            choices = {candidate.label: candidate for candidate in readiness.candidates}
            artifact_label = st.selectbox(t(lang, "compatible_artifact"), list(choices))
        readiness = _cached_readiness(
            json.dumps(effective, ensure_ascii=False, sort_keys=True), config_name,
            str(PROJECT_ROOT), str(choices[artifact_label].index_dir), st.session_state["cache_epoch"],
        )
        if mode_blocker is not None:
            readiness = replace(
                readiness,
                ready=False,
                checks=(PreflightCheck("retrieval_mode", "blocked", mode_blocker), *readiness.checks),
                blockers=(mode_blocker, *readiness.blockers),
            )

    with st.sidebar:
        if mode_blocker is not None:
            st.caption(mode_blocker)
        status = "Sẵn sàng" if readiness.ready else "Cần cấu hình"
        st.caption(f"Production: {status}")
        for blocker in readiness.blockers[:2]:
            st.caption(f"• {blocker}")

    return {
        "requested_mode": requested_mode, "config_name": config_name,
        "top_k": int(top_k), "filter_profile": filter_profile,
        "retrieval_mode": retrieval_mode, "retrieval_base_mode": base_retrieval_mode,
        "sparse": sparse, "graph": graph, "fusion": fusion,
        "reranker": reranker, "show_diagnostics": False,
        **generation_settings,
        "settings_signature": "|".join((
            config_name, retrieval_mode, generation_settings["generation_model"],
            generation_settings["prompt_strategy"],
        )),
        "registry": registry, "readiness": readiness, "lang": lang,
    }


def _submit(question: str, settings: dict[str, Any], readiness: ProductionReadiness, active_mode: str) -> None:
    lang = settings.get("lang", "en")
    if not question.strip():
        st.session_state["notice"] = t(lang, "enter_before_submit")
        return
    request = _build_question_request(
        question.strip(), settings["config_name"], settings["top_k"],
        settings["sparse"], settings["graph"], settings["fusion"], settings["reranker"], settings["filter_profile"],
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
        st.session_state["conversation"] = [
            ConversationTurn(question.strip(), response, st.session_state["next_turn_id"])
        ]
        st.session_state["next_turn_id"] += 1
        st.session_state["scroll_to_answer"] = True
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
        "retrieval_mode": settings["retrieval_mode"],
        "sparse_enabled": settings["sparse"],
        "graph_enabled": settings["graph"],
        "fusion_enabled": settings["fusion"],
        "reranker_enabled": settings["reranker"],
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


def _render_answer_scroll_anchor() -> None:
    st.markdown('<div id="answer-scroll-anchor"></div>', unsafe_allow_html=True)
    if not st.session_state.get("scroll_to_answer"):
        return
    st.session_state["scroll_to_answer"] = False
    st_components.html(
        """
        <script>
        const scrollToAnswer = () => {
          const anchor = window.parent.document.getElementById("answer-scroll-anchor");
          if (anchor) {
            anchor.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        };
        window.setTimeout(scrollToAnswer, 80);
        window.setTimeout(scrollToAnswer, 260);
        </script>
        """,
        height=0,
    )


def _render_generation_controls(lang: str) -> dict[str, str]:
    st.markdown("### Model")
    model_choice = st.selectbox(
        t(lang, "model_selector"),
        MODEL_CHOICES,
        key="model_choice",
        label_visibility="collapsed",
    )
    model_key = str(model_choice or MODEL_CHOICES[0])

    st.markdown(f"### {t(lang, 'prompt_strategy')}")
    strategy = _render_choice_toggle(
        t(lang, "prompt_strategy"), PROMPT_STRATEGIES, "prompt_strategy", "base",
        lambda value: _prompt_mode_label(str(value)),
    )
    return {
        "generation_model": _model_choice_value(model_key),
        "prompt_strategy": str(strategy or "base"),
    }


def _build_question_request(
    question: str, config_name: str, top_k: int, sparse: bool, graph: bool,
    fusion: bool, reranker: bool, filter_profile: str, settings: dict[str, Any],
) -> QuestionRequest:
    return QuestionRequest(
        question=question,
        config_name=config_name,
        top_k_override=top_k,
        sparse_enabled_override=sparse,
        graph_enabled_override=graph,
        fusion_enabled_override=fusion,
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


def _config_for_retrieval_mode(value: str) -> str:
    del value
    return DEFAULT_CONFIG_NAME


def _retrieval_mode_flags(graph_enabled: bool, reranker_enabled: bool) -> tuple[bool, bool, bool]:
    graph = bool(graph_enabled)
    reranker = bool(reranker_enabled)
    fusion = graph
    return graph, fusion, reranker


def _base_retrieval_label(value: str) -> str:
    return {
        "dense_only": "Dense Only",
        "dense_sparse": "Dense-Sparse",
    }.get(value, value)


def _compose_retrieval_mode(base_mode: str, graph_enabled: bool, reranker_enabled: bool) -> str:
    label = _base_retrieval_label(base_mode)
    extras = []
    if graph_enabled:
        extras.append("Graph")
    if reranker_enabled:
        extras.append("Reranker")
    return " + ".join((label, *extras))


def _bm25_service_configured() -> bool:
    return bool(os.environ.get("BM25_SERVICE_URL", "").strip())


def _retrieval_mode_blocker(value: str) -> str | None:
    if value != "dense_sparse":
        return None
    if _bm25_service_configured() or _local_sparse_index_available():
        return None
    return (
        "Dense-Sparse cần sparse/BM25. Hãy build data/sparse_index hoặc cấu hình "
        "BM25_SERVICE_URL trước khi chạy production."
    )


def _local_sparse_index_available() -> bool:
    sparse_dir = PROJECT_ROOT / "data" / "sparse_index"
    return (sparse_dir / "bm25_index.pkl").is_file() and (sparse_dir / "bm25_metadata.pkl").is_file()


def _render_bool_toggle(label: str, state_key: str, fallback: bool) -> bool:
    fallback_value = "on" if fallback else "off"
    current = str(st.session_state.get(state_key) or fallback_value)
    if current not in {"off", "on"}:
        current = fallback_value
        st.session_state[state_key] = current
    enabled = current == "on"
    suffix = "selected" if enabled else "option"
    if st.button(label, key=f"choice_{state_key}_{suffix}", use_container_width=True):
        st.session_state[state_key] = "off" if enabled else "on"
        st.rerun()
    return enabled


def _render_choice_toggle(
    label: str,
    choices: Sequence[str],
    state_key: str,
    fallback: str,
    format_func,
    *,
    columns_per_row: int | None = None,
) -> str:
    del label
    current = str(st.session_state.get(state_key) or fallback)
    if current not in choices:
        current = fallback
        st.session_state[state_key] = fallback
    row_size = max(1, columns_per_row or len(choices))
    for row_start in range(0, len(choices), row_size):
        row_choices = choices[row_start: row_start + row_size]
        columns = st.columns(len(row_choices), gap="small")
        for index, choice in enumerate(row_choices):
            selected = choice == current
            suffix = "selected" if selected else "option"
            key = f"choice_{state_key}_{_choice_key_part(choice)}_{suffix}"
            with columns[index]:
                if st.button(str(format_func(choice)), key=key, use_container_width=True):
                    if not selected:
                        st.session_state[state_key] = choice
                        st.rerun()
    return current


def _choice_key_part(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in str(value))
    return slug.strip("_") or "choice"


def _model_choice_value(value: str) -> str:
    return value if value in MODEL_CHOICES else MODEL_CHOICES[0]


def _prompt_mode_label(value: str) -> str:
    return "CoT" if value == "reasoning" else "Base"


def _initialize_state() -> None:
    st.session_state.setdefault("cache_epoch", 0)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("notice", None)
    st.session_state.setdefault("scroll_to_answer", False)
    st.session_state.setdefault("runtime_mode", PRODUCTION_MODE)
    if st.session_state["runtime_mode"] not in RUNTIME_CHOICES:
        st.session_state["runtime_mode"] = PRODUCTION_MODE
    _migrate_retrieval_state()
    st.session_state.setdefault("retrieval_base_mode", "dense_only")
    if st.session_state["retrieval_base_mode"] not in BASE_RETRIEVAL_MODES:
        st.session_state["retrieval_base_mode"] = "dense_only"
    for toggle_key in ("graph_enabled", "reranker_enabled"):
        value = st.session_state.setdefault(toggle_key, "off")
        if value not in {"off", "on"}:
            st.session_state[toggle_key] = "on" if bool(value) else "off"
    st.session_state.setdefault("model_choice", MODEL_CHOICES[0])
    if st.session_state["model_choice"] not in MODEL_CHOICES:
        st.session_state["model_choice"] = MODEL_CHOICES[0]
    st.session_state.setdefault("prompt_strategy", "base")
    if st.session_state["prompt_strategy"] not in PROMPT_STRATEGIES:
        st.session_state["prompt_strategy"] = "base"
    st.session_state.setdefault("theme_choice", "System")
    st.session_state.setdefault("language_choice", "vi")
    st.session_state.setdefault("next_turn_id", 1)
    st.session_state.setdefault("selected_source", None)
    query_theme = st.query_params.get("theme")
    if query_theme in THEME_CHOICES and st.session_state.get("query_theme") != query_theme:
        st.session_state["theme_choice"] = query_theme
        st.session_state["query_theme"] = query_theme


def _migrate_retrieval_state() -> None:
    old_mode = st.session_state.get("retrieval_mode")
    if "retrieval_base_mode" in st.session_state or old_mode is None:
        return
    mapping = {
        "dense_faiss": ("dense_only", "off", "off"),
        "dense_sparse": ("dense_sparse", "off", "off"),
        "graph": ("dense_only", "on", "off"),
        "rrk": ("dense_only", "on", "on"),
    }
    base_mode, graph, reranker = mapping.get(str(old_mode), ("dense_only", "off", "off"))
    st.session_state["retrieval_base_mode"] = base_mode
    st.session_state["graph_enabled"] = graph
    st.session_state["reranker_enabled"] = reranker


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
