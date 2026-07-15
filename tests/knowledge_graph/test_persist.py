"""Tests for structural knowledge-graph pickle save/load (004-kg-pickle-persist)."""

from __future__ import annotations

import pickle
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_graph import (
    FORMAT_NAME,
    FORMAT_VERSION,
    AuthorityIndexEntry,
    GraphExpansion,
    GraphLoaderPaths,
    GraphPickleCorruptError,
    GraphPickleEnvelope,
    GraphPickleIncompatibleError,
    GraphPickleNotFoundError,
    KnowledgeGraphFacade,
    OverlayBundle,
    ValidityEvent,
    load_knowledge_graph,
    save_knowledge_graph,
)
from knowledge_graph.builder import KnowledgeGraph
from knowledge_graph.persist import GraphPickleArtifactInfo, GraphPickleLoadResult


def _build_fixture_graph(mock_dataset_dir: Path):
    paths = GraphLoaderPaths(data_dir=mock_dataset_dir)
    facade = KnowledgeGraphFacade(paths=paths)
    return facade.build_graph()


# --- US1: save path ---------------------------------------------------------


def test_save_writes_artifact_info(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"

    info = save_knowledge_graph(
        build.graph,
        out,
        stats=build.stats,
        warnings=build.warnings,
        source_data_dir=str(mock_dataset_dir),
    )

    assert isinstance(info, GraphPickleArtifactInfo)
    assert out.exists()
    assert info.byte_size > 0
    assert info.format_version == FORMAT_VERSION
    assert info.path == out.resolve()
    assert info.created_at_utc


def test_save_creates_missing_parent_directory(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "nested" / "dir" / "knowledge_graph.gpickle"

    info = save_knowledge_graph(build.graph, out, stats=build.stats)
    assert out.exists()
    assert info.byte_size > 0


def test_missing_structural_inputs_no_final_artifact(tmp_path: Path):
    empty_dir = tmp_path / "empty_v2"
    empty_dir.mkdir()
    out = tmp_path / "graph" / "knowledge_graph.gpickle"

    paths = GraphLoaderPaths(data_dir=empty_dir)
    facade = KnowledgeGraphFacade(paths=paths)

    with pytest.raises(FileNotFoundError) as exc_info:
        facade.build_and_save_graph(out)

    message = str(exc_info.value)
    assert "Missing graph loader inputs" in message
    assert not out.exists()


def test_build_and_save_graph_success(mock_dataset_dir: Path, tmp_path: Path):
    out = tmp_path / "kg.gpickle"
    facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=mock_dataset_dir))
    build, artifact = facade.build_and_save_graph(out)

    assert out.exists()
    assert artifact.byte_size > 0
    assert build.stats.document_count == 2
    assert build.stats.chunk_count == 3


# --- US2: load / round-trip -------------------------------------------------


def test_round_trip_counts_and_identities(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    save_knowledge_graph(
        build.graph,
        out,
        stats=build.stats,
        warnings=build.warnings,
        source_data_dir=str(mock_dataset_dir),
    )

    loaded = load_knowledge_graph(out)
    assert isinstance(loaded, GraphPickleLoadResult)
    g = loaded.graph
    assert isinstance(g, KnowledgeGraph)

    assert len(g.documents) == build.stats.document_count
    assert len(g.external_stubs) == build.stats.external_stub_count
    assert len(g.provisions) == build.stats.provision_count
    assert len(g.chunks) == build.stats.chunk_count
    assert len(g.document_edges) == build.stats.document_edge_count
    assert len(g.verified_document_edges) == build.stats.verified_document_edge_count
    assert len(g.structural_edges) == build.stats.structural_edge_count

    chunk_id = "1::article::1::chunk::1"
    chunk = g.chunks[chunk_id]
    assert chunk.parent_unit_id == "1::article::1"
    assert chunk.id_str == "1"
    provision = g.provisions[chunk.parent_unit_id]
    assert provision.id_str == "1"
    assert provision.id_str in g.documents
    assert g.document_to_provisions["1"]
    assert g.provision_to_chunks["1::article::1"] == (chunk_id,)

    assert loaded.format_version == FORMAT_VERSION
    assert loaded.source_data_dir == str(mock_dataset_dir)
    assert loaded.stats is not None


def test_load_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "nope.gpickle"
    with pytest.raises(GraphPickleNotFoundError) as exc_info:
        load_knowledge_graph(missing)
    assert "not found" in str(exc_info.value).lower() or "Graph pickle not found" in str(exc_info.value)


def test_load_corrupt_raises(tmp_path: Path):
    bad = tmp_path / "corrupt.gpickle"
    bad.write_bytes(b"not-a-valid-pickle-payload")
    with pytest.raises(GraphPickleCorruptError):
        load_knowledge_graph(bad)


def test_load_wrong_format_name_raises(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    bad_env = GraphPickleEnvelope(
        format_name="not-the-right-name",
        format_version=FORMAT_VERSION,
        created_at_utc="2026-07-15T00:00:00Z",
        source_data_dir=None,
        stats=build.stats,
        warnings=(),
        graph=build.graph,
    )
    path = tmp_path / "bad_name.gpickle"
    with path.open("wb") as handle:
        pickle.dump(bad_env, handle)

    with pytest.raises(GraphPickleIncompatibleError) as exc_info:
        load_knowledge_graph(path)
    assert "format_name" in str(exc_info.value)


def test_load_unknown_format_version_raises(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    bad_env = GraphPickleEnvelope(
        format_name=FORMAT_NAME,
        format_version=999,
        created_at_utc="2026-07-15T00:00:00Z",
        source_data_dir=None,
        stats=build.stats,
        warnings=(),
        graph=build.graph,
    )
    path = tmp_path / "bad_version.gpickle"
    with path.open("wb") as handle:
        pickle.dump(bad_env, handle)

    with pytest.raises(GraphPickleIncompatibleError) as exc_info:
        load_knowledge_graph(path)
    assert "format_version" in str(exc_info.value)


def test_loaded_graph_usable_by_expansion_and_traverse(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    save_knowledge_graph(build.graph, out, stats=build.stats)

    loaded = load_knowledge_graph(out)
    graph = loaded.graph

    expansion = GraphExpansion(graph)
    result = expansion.expand(
        seed_chunk_ids=["1::article::1::chunk::1"],
        max_hop=1,
        max_context=8,
    )
    assert result is not None

    facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=mock_dataset_dir))
    traversal = facade.traverse(graph, start_id="2", mode="guidance", max_depth=3)
    assert "2" in traversal.visited_ids
    assert "1" in traversal.visited_ids


def test_external_stubs_and_verified_edges_preserved(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    save_knowledge_graph(build.graph, out, stats=build.stats)
    g = load_knowledge_graph(out).graph

    assert g.external_stubs
    assert all(stub.citation_safe is False for stub in g.external_stubs.values())

    assert len(g.verified_document_edges) <= len(g.document_edges)
    verified_ids = {e.edge_id for e in g.verified_document_edges}
    full_ids = {e.edge_id for e in g.document_edges}
    assert verified_ids.issubset(full_ids)
    # Fixture has one unverified edge (2->4)
    assert len(g.verified_document_edges) < len(g.document_edges)


def test_facade_load_graph_wrapper(mock_dataset_dir: Path, tmp_path: Path):
    out = tmp_path / "kg.gpickle"
    facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=mock_dataset_dir))
    build, _artifact = facade.build_and_save_graph(out)
    loaded = facade.load_graph(out)
    assert len(loaded.graph.documents) == build.stats.document_count


# --- US3: overlays optional -------------------------------------------------


def test_load_succeeds_without_overlay_files(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    save_knowledge_graph(build.graph, out, stats=build.stats)

    # Only the pickle is required; no validity/authority files in tmp_path
    loaded = load_knowledge_graph(out)
    assert loaded.graph.documents
    assert not hasattr(loaded.graph, "document_overlays")

    with out.open("rb") as handle:
        envelope = pickle.load(handle)
    assert isinstance(envelope, GraphPickleEnvelope)
    assert isinstance(envelope.graph, KnowledgeGraph)
    # Structural envelope must not carry overlay bundle types
    assert not isinstance(envelope.stats, OverlayBundle)


def test_overlay_join_after_load(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    save_knowledge_graph(build.graph, out, stats=build.stats)
    graph = load_knowledge_graph(out).graph

    events = [
        ValidityEvent("1", "enacted", "2026-01-01", "0", "whole", "based_on", "e1", True),
        ValidityEvent("2", "enacted", "2026-03-01", "0", "whole", "based_on", "e2", True),
    ]
    entries = [
        AuthorityIndexEntry("Luật", 2, "Law", "authority@1"),
        AuthorityIndexEntry("Nghị định", 4, "Decree", "authority@1"),
    ]
    facade = KnowledgeGraphFacade()
    bundle = facade.build_overlay_bundle(
        documents=graph.documents.values(),
        validity_events=events,
        authority_entries=entries,
        as_of_date="2026-07-13",
    )
    assert isinstance(bundle, OverlayBundle)
    assert len(bundle.document_overlays) == 2
    # Structural graph unchanged (still no overlay fields on KnowledgeGraph)
    assert len(graph.documents) == 2


# --- US4: replace / atomic --------------------------------------------------


def test_second_save_replaces_artifact(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"

    first = save_knowledge_graph(build.graph, out, stats=build.stats, warnings=("w1",))
    first_created = first.created_at_utc
    first_size = first.byte_size

    second = save_knowledge_graph(
        build.graph,
        out,
        stats=build.stats,
        warnings=("w2",),
        source_data_dir="second-build",
    )
    loaded = load_knowledge_graph(out)

    assert out.exists()
    assert second.byte_size > 0
    assert loaded.source_data_dir == "second-build"
    assert loaded.warnings == ("w2",)
    # created_at may match if same second; source_data_dir proves second write won
    assert second.created_at_utc >= first_created
    assert second.byte_size == first_size or second.byte_size > 0


def test_failed_serialize_leaves_prior_artifact(mock_dataset_dir: Path, tmp_path: Path):
    build = _build_fixture_graph(mock_dataset_dir)
    out = tmp_path / "kg.gpickle"
    first = save_knowledge_graph(
        build.graph,
        out,
        stats=build.stats,
        warnings=("keep-me",),
        source_data_dir="first",
    )
    prior_bytes = out.read_bytes()
    assert first.byte_size == len(prior_bytes)

    with patch("knowledge_graph.persist.pickle.dump", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            save_knowledge_graph(build.graph, out, stats=build.stats, source_data_dir="failed")

    assert out.exists()
    assert out.read_bytes() == prior_bytes
    loaded = load_knowledge_graph(out)
    assert loaded.source_data_dir == "first"
    assert loaded.warnings == ("keep-me",)
    # No leftover temp files in the directory
    temps = list(tmp_path.glob("*.gpickle.tmp")) + list(tmp_path.glob(".*.gpickle.tmp"))
    assert temps == []
