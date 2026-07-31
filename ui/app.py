"""Canonical local Streamlit entry point for single-question production QA."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

import streamlit as st  # noqa: E402

from service.qa_service import (  # noqa: E402
    FILTER_PROFILES,
    TOP_K_MAX,
    TOP_K_MIN,
    QuestionRequest,
    QuestionResponse,
    answer_question,
    apply_safe_overrides,
    build_question_resources,
    format_safe_error,
    list_interactive_configs,
    load_ui_config_registry,
    normalize_latency_rows,
    run_preflight,
)


CONFIG_PATH = PROJECT_ROOT / "configs" / "ablation_configs.yaml"


@st.cache_resource(show_spinner=False)
def _cached_registry(config_path: str, modified_ns: int) -> dict[str, dict[str, Any]]:
    del modified_ns
    return load_ui_config_registry(Path(config_path))


@st.cache_resource(show_spinner=False)
def _cached_resources(config_json: str, project_root: str, cache_epoch: int):
    del cache_epoch
    return build_question_resources(json.loads(config_json), project_root=Path(project_root))


def main() -> None:
    st.set_page_config(page_title="Legal RAG Local Demo", page_icon="🔎", layout="wide")
    st.title("Legal RAG Local QA Demo")
    st.caption(
        "Single-question local UI backed by the repository's production config, retrieval, generation, agent, and E2E contracts."
    )
    st.info("Retrieved source rows are evidence/context references, not independently verified formal citations.")

    st.session_state.setdefault("cache_epoch", 0)
    st.session_state.setdefault("latest_response", None)
    st.session_state.setdefault("submission_message", None)

    try:
        registry = _cached_registry(str(CONFIG_PATH), CONFIG_PATH.stat().st_mtime_ns)
        options = list_interactive_configs(registry, project_root=PROJECT_ROOT)
    except Exception as exc:
        st.error(f"Configuration registry could not be loaded: {format_safe_error(exc)}")
        st.stop()
        return

    if not options:
        st.error("No interactive configurations are present in the canonical config registry.")
        st.stop()
        return

    labels = {f"{option.name} — {option.status}": option.name for option in options}
    option_by_name = {option.name: option for option in options}

    with st.sidebar:
        st.header("Configuration")
        if st.button("Clear resource cache", use_container_width=True):
            _cached_registry.clear()
            _cached_resources.clear()
            st.session_state["cache_epoch"] += 1
            st.session_state["submission_message"] = "Resource cache cleared."

        with st.form("question_form", clear_on_submit=False):
            selected_label = st.selectbox("Pipeline config", list(labels), key="selected_config_label")
            selected_name = labels[selected_label]
            selected_config = registry[selected_name]
            retrieval = selected_config["retrieval"]
            default_top_k = int(retrieval["top_k"])
            top_k = st.number_input(
                "Top-k (interactive override)", min_value=TOP_K_MIN, max_value=TOP_K_MAX,
                value=default_top_k, step=1, key=f"top_k_{selected_name}",
                help="Applied in memory only; the YAML config is not modified.",
            )
            configured_profile = str(retrieval.get("filter_profile") or "broad")
            profile_index = FILTER_PROFILES.index(configured_profile) if configured_profile in FILTER_PROFILES else 0
            filter_profile = st.selectbox(
                "Filter profile", FILTER_PROFILES, index=profile_index, key=f"filter_{selected_name}"
            )
            graph_enabled = st.toggle(
                "Graph", value=bool(retrieval.get("graph", {}).get("enabled")), key=f"graph_{selected_name}",
                help="Execution is blocked when enabled because no graph adapter is wired into the production ablation stack.",
            )
            reranker_enabled = st.toggle(
                "Reranker", value=bool(retrieval.get("reranker", {}).get("enabled")), key=f"reranker_{selected_name}",
                help="Execution is blocked when enabled because no reranker adapter is wired into the production ablation stack.",
            )
            question = st.text_area(
                "Question", height=140, placeholder="Enter one question; execution occurs only after Ask.",
            )
            submitted = st.form_submit_button("Ask", type="primary", use_container_width=True)

        selected_option = option_by_name[selected_name]
        st.caption(f"Registry status: **{selected_option.status}**")
        if selected_option.reason:
            st.caption(selected_option.reason)

    request = QuestionRequest(
        question=question, config_name=selected_name, top_k_override=int(top_k),
        graph_enabled_override=graph_enabled, reranker_enabled_override=reranker_enabled,
        filter_profile=filter_profile,
    )
    preflight = None
    effective: dict[str, Any] | None = None
    try:
        effective = apply_safe_overrides(selected_config, request)
        preflight = run_preflight(effective, config_name=selected_name, project_root=PROJECT_ROOT)
    except Exception as exc:
        st.session_state["submission_message"] = format_safe_error(exc)

    with st.sidebar:
        st.subheader("Environment readiness")
        if preflight is None:
            st.error(st.session_state.get("submission_message") or "Override validation failed.")
        else:
            if preflight.status == "runtime-ready":
                st.success("Runtime ready")
            elif preflight.status == "deferred":
                st.info("Deferred")
            else:
                st.warning("Runtime blocked")
            for check in preflight.checks:
                symbol = {"ready": "✅", "warning": "⚠️", "deferred": "⏸️"}.get(check.status, "❌")
                st.caption(f"{symbol} {check.message}")

    if submitted:
        if not question.strip():
            st.session_state["submission_message"] = "Question must not be empty. Previous output is preserved."
        elif preflight is None:
            st.session_state["submission_message"] = "The selected overrides are invalid. Previous output is preserved."
        elif not preflight.runnable:
            label = "deferred" if preflight.status == "deferred" else "blocked"
            st.session_state["submission_message"] = f"Execution {label}: " + "; ".join(preflight.blockers)
        else:
            try:
                assert effective is not None
                resources = _cached_resources(
                    json.dumps(preflight.resolved_config, ensure_ascii=False, sort_keys=True),
                    str(PROJECT_ROOT), st.session_state["cache_epoch"],
                )
                with st.spinner("Running retrieval and grounded generation…"):
                    response = answer_question(
                        request, registry=registry, resources=resources, project_root=PROJECT_ROOT
                    )
                st.session_state["latest_response"] = response
                st.session_state["submission_message"] = None
            except Exception as exc:
                st.session_state["submission_message"] = (
                    f"Resource construction or execution failed safely: {format_safe_error(exc)}"
                )

    if st.session_state.get("submission_message"):
        st.warning(st.session_state["submission_message"])

    response = st.session_state.get("latest_response")
    if response is None:
        st.subheader("Answer/status")
        st.caption("Submit a runtime-ready configuration and non-empty question to see an answer.")
        return
    _render_response(response)


def _render_response(response: QuestionResponse) -> None:
    st.subheader("Answer/status")
    if response.status == "completed":
        st.success("Completed")
        st.markdown(response.answer or "No final answer returned.")
    elif response.status == "abstained":
        st.info("Abstained")
        st.write("No sufficient retrieved context was available, so generation was not treated as a grounded answer.")
    elif response.status == "deferred":
        st.info("Deferred")
    elif response.status == "blocked":
        st.warning("Blocked")
    else:
        st.error("Failed")

    if response.error:
        st.error(f"Stage `{response.error.stage}` — {response.error.message}")
        st.caption(response.error.next_step)
    for warning in response.warnings:
        st.warning(warning)

    sources_tab, latency_tab, trace_tab, diagnostics_tab = st.tabs(
        ["Sources / context", "Latency", "Agent trace", "Diagnostics"]
    )
    with sources_tab:
        if not response.contexts:
            st.info("No retrieved context rows are available.")
        else:
            st.dataframe(
                [{
                    "rank": row.rank, "score": row.score, "document_id": row.document_id,
                    "provision_id": row.provision_id, "chunk_id": row.chunk_id,
                    "title": row.title, "article": row.article_number,
                    "citation/context reference": row.citation, "preview": row.preview,
                } for row in response.contexts],
                hide_index=True, use_container_width=True,
            )
            st.caption("For the configured dense/reranker stages, higher scores indicate a stronger match; compare scores only within the same pipeline configuration.")
            for row in response.contexts:
                label = row.citation or row.chunk_id or f"Context {row.rank}"
                with st.expander(f"#{row.rank} — {label}"):
                    st.text(row.text or "Unavailable")
                    st.caption(
                        f"Score: {row.score if row.score is not None else 'N/A'} | "
                        f"Vector: {row.vector_score if row.vector_score is not None else 'N/A'} | "
                        f"Reranker: {row.rerank_score if row.rerank_score is not None else 'N/A'}"
                    )
    with latency_tab:
        rows = normalize_latency_rows(response.latency)
        st.dataframe(
            [{"stage": row["stage"], "milliseconds": row["latency_ms"] if row["latency_ms"] is not None else "N/A"} for row in rows],
            hide_index=True, use_container_width=True,
        )
        st.caption("Missing stages remain N/A. `agent_total` includes component stages and is not added to them.")
    with trace_tab:
        if response.trace:
            st.dataframe(list(response.trace), hide_index=True, use_container_width=True)
            st.caption("Only bounded action metadata is shown; hidden reasoning and prompts are never persisted.")
        else:
            st.info("No agent trace applies to this response (for example, Plain RAG).")
    with diagnostics_tab:
        st.json(response.diagnostics, expanded=False)
        st.caption("Environment variable names and configured/missing states may appear; secret values do not.")


if __name__ == "__main__":
    main()
