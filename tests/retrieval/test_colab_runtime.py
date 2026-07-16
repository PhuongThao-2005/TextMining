"""Unit tests for Colab-safe runtime helpers (feature 005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrieval.colab_runtime import (
    CleanupRequest,
    apply_cleanup,
    build_load_plan,
    decide_graph_source_mode,
    inventory_artifacts,
    resolve_runtime_profile,
    session_outcome_label,
)


def test_resolve_colab_safe_defaults(tmp_path: Path) -> None:
    profile = resolve_runtime_profile("colab_safe", project_root=tmp_path)
    assert profile.name == "colab_safe"
    assert profile.colab_safe is True
    assert profile.allow_jsonl_graph_rebuild is False
    assert profile.top_k == 20
    assert profile.top_n == 8
    assert profile.hybrid_max_context == 8
    assert profile.run_payload_csv_export is False
    assert profile.run_payload_cache_export is False
    assert profile.run_benchmark_sample is False
    assert profile.enable_graph_guided_prefilter_demo is False
    assert profile.graph_pickle_path == tmp_path / "data" / "graph" / "knowledge_graph.gpickle"


def test_resolve_unconstrained_defaults(tmp_path: Path) -> None:
    profile = resolve_runtime_profile("unconstrained", project_root=tmp_path)
    assert profile.name == "unconstrained"
    assert profile.colab_safe is False
    assert profile.allow_jsonl_graph_rebuild is True
    assert profile.top_k == 30
    assert profile.top_n == 10
    assert profile.hybrid_max_context == 12


def test_decide_pickle_preferred(tmp_path: Path) -> None:
    pickle = tmp_path / "kg.gpickle"
    pickle.write_bytes(b"x")
    v2 = tmp_path / "v2"
    v2.mkdir()
    for name in (
        "documents.jsonl",
        "provisions.jsonl",
        "chunks.jsonl",
        "edges.jsonl",
        "external_stubs.jsonl",
    ):
        (v2 / name).write_text("{}\n", encoding="utf-8")

    decision = decide_graph_source_mode(
        pickle_path=pickle,
        v2_data_dir=v2,
        colab_safe=True,
        allow_jsonl_graph_rebuild=False,
    )
    assert decision.mode == "pickle"
    assert decision.pickle_present is True
    assert decision.rebuild_opt_in_required is False


def test_decide_colab_safe_blocks_silent_jsonl_rebuild(tmp_path: Path) -> None:
    v2 = tmp_path / "v2"
    v2.mkdir()
    for name in (
        "documents.jsonl",
        "provisions.jsonl",
        "chunks.jsonl",
        "edges.jsonl",
        "external_stubs.jsonl",
    ):
        (v2 / name).write_text("{}\n", encoding="utf-8")
    pickle = tmp_path / "missing.gpickle"

    decision = decide_graph_source_mode(
        pickle_path=pickle,
        v2_data_dir=v2,
        colab_safe=True,
        allow_jsonl_graph_rebuild=False,
    )
    assert decision.mode == "unavailable"
    assert decision.rebuild_opt_in_required is True
    assert decision.rebuild_warning is not None


def test_decide_opt_in_jsonl_rebuild(tmp_path: Path) -> None:
    v2 = tmp_path / "v2"
    v2.mkdir()
    for name in (
        "documents.jsonl",
        "provisions.jsonl",
        "chunks.jsonl",
        "edges.jsonl",
        "external_stubs.jsonl",
    ):
        (v2 / name).write_text("{}\n", encoding="utf-8")

    decision = decide_graph_source_mode(
        pickle_path=tmp_path / "missing.gpickle",
        v2_data_dir=v2,
        colab_safe=True,
        allow_jsonl_graph_rebuild=True,
    )
    assert decision.mode == "jsonl_rebuild"
    assert decision.rebuild_warning is not None


def test_decide_unavailable_without_sources(tmp_path: Path) -> None:
    decision = decide_graph_source_mode(
        pickle_path=tmp_path / "no.gpickle",
        v2_data_dir=tmp_path / "empty_v2",
        colab_safe=True,
        allow_jsonl_graph_rebuild=False,
    )
    assert decision.mode == "unavailable"
    assert decision.rebuild_opt_in_required is False


def test_inventory_and_load_plan_pickle(tmp_path: Path) -> None:
    index = tmp_path / "faiss"
    index.mkdir()
    (index / "index.faiss").write_bytes(b"idx")
    (index / "payloads.jsonl").write_text("{}\n", encoding="utf-8")
    (index / "payload_cache.sqlite").write_bytes(b"db")
    pickle = tmp_path / "graph" / "knowledge_graph.gpickle"
    pickle.parent.mkdir(parents=True)
    pickle.write_bytes(b"g")
    v2 = tmp_path / "v2"
    v2.mkdir()
    for name in (
        "documents.jsonl",
        "provisions.jsonl",
        "chunks.jsonl",
        "edges.jsonl",
        "external_stubs.jsonl",
    ):
        (v2 / name).write_text("{}\n", encoding="utf-8")

    profile = resolve_runtime_profile(
        "colab_safe",
        project_root=tmp_path,
        graph_pickle_path=pickle,
        v2_data_dir=v2,
    )
    arts = inventory_artifacts(index_dir=index, graph_pickle_path=pickle, v2_data_dir=v2)
    assert any(a.key == "index.faiss" and a.present for a in arts)
    assert any(a.key == "knowledge_graph.gpickle" and a.present for a in arts)

    plan = build_load_plan(profile, index_dir=index)
    assert plan.graph_source_mode == "pickle"
    assert plan.hybrid_expected is True
    assert plan.profile == "colab_safe"
    actions = {a.component: a.action for a in plan.actions}
    assert actions["structural_graph"] == "load"
    assert actions["payload_csv_export"] == "skip"


def test_session_outcome_labels() -> None:
    assert (
        session_outcome_label(
            colab_safe=True,
            structural_ready=False,
            loaded_from_pickle=False,
            hybrid_used=False,
            vector_ok=True,
        )
        == "vector_only_colab_safe_success"
    )
    assert (
        session_outcome_label(
            colab_safe=True,
            structural_ready=True,
            loaded_from_pickle=True,
            hybrid_used=True,
            vector_ok=True,
        )
        == "hybrid_colab_safe_success_pickle"
    )
    assert (
        session_outcome_label(
            colab_safe=True,
            structural_ready=False,
            loaded_from_pickle=False,
            hybrid_used=False,
            vector_ok=True,
            hybrid_requested=True,
        )
        == "hybrid_unavailable"
    )


def test_apply_cleanup_unloads_graph() -> None:
    class Status:
        structural_ready = True
        overlays_ready = True
        graph_source_mode = "pickle"
        loaded_from_pickle = True

    ns = {
        "kg_graph": object(),
        "graph_expansion": object(),
        "hybrid_retriever": object(),
        "comparison_record": {"x": 1},
        "graph_load_status": Status(),
        "document_overlays": {"a": 1},
        "overlay_bundle": object(),
    }
    actions = apply_cleanup(
        ns,
        CleanupRequest(
            drop_comparison_records=True,
            unload_overlays=True,
            unload_structural_graph=True,
            run_gc=True,
        ),
    )
    assert ns["kg_graph"] is None
    assert ns["hybrid_retriever"] is None
    assert ns["comparison_record"] is None
    assert ns["document_overlays"] == {}
    assert ns["graph_load_status"].structural_ready is False
    assert any("gc.collect" in a for a in actions)


def test_unknown_profile_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_runtime_profile("laptop_turbo", project_root=tmp_path)
