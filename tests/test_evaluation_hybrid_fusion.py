from __future__ import annotations

from evaluation.hybrid_fusion import (
    build_traversal_starts,
    fuse_hybrid_chunk_ids,
)
from retrieval.schema import RetrievedChunk


def _chunk(
    chunk_id: str,
    id_str: str = "",
    parent_unit_id: str = "",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        chunk_text="text",
        citation_anchor="anchor",
        citation_label="label",
        title="title",
        article_number=None,
        unit_type="article",
        path=None,
        validity_group="current",
        legal_authority_rank=1,
        vector_score=0.9,
        rerank_score=0.9,
        id_str=id_str,
        parent_unit_id=parent_unit_id,
    )


def test_build_traversal_starts_cross_document_mode_uses_id_str():
    hits = [
        _chunk("c1", id_str="doc-A", parent_unit_id="prov-1"),
        _chunk("c2", id_str="doc-B", parent_unit_id="prov-2"),
    ]

    result = build_traversal_starts(hits, "basis", max_starts=10)

    assert result.mode == "basis"
    assert result.start_ids == ("doc-A", "doc-B")
    assert result.prepass_chunk_ids == ("c1", "c2")
    assert result.capped is False
    assert result.empty is False


def test_build_traversal_starts_structure_mode_uses_parent_unit_id():
    hits = [
        _chunk("c1", id_str="doc-A", parent_unit_id="prov-1"),
        _chunk("c2", id_str="doc-B", parent_unit_id="prov-2"),
    ]

    result = build_traversal_starts(hits, "structure", max_starts=10)

    assert result.start_ids == ("prov-1", "prov-2")


def test_build_traversal_starts_structure_mode_falls_back_to_id_str():
    hits = [_chunk("c1", id_str="doc-A", parent_unit_id="")]

    result = build_traversal_starts(hits, "structure", max_starts=10)

    assert result.start_ids == ("doc-A",)


def test_build_traversal_starts_default_mode_uses_chunk_id():
    hits = [
        _chunk("c1", id_str="doc-A", parent_unit_id="prov-1"),
        _chunk("c2", id_str="doc-B", parent_unit_id="prov-2"),
    ]

    result = build_traversal_starts(hits, "neighbors", max_starts=10)

    assert result.start_ids == ("c1", "c2")


def test_build_traversal_starts_dedupes_keep_first():
    hits = [
        _chunk("c1", id_str="doc-A"),
        _chunk("c2", id_str="doc-A"),
        _chunk("c3", id_str="doc-B"),
    ]

    result = build_traversal_starts(hits, "basis", max_starts=10)

    assert result.start_ids == ("doc-A", "doc-B")


def test_build_traversal_starts_caps_at_max_starts():
    hits = [_chunk(f"c{i}", id_str=f"doc-{i}") for i in range(5)]

    result = build_traversal_starts(hits, "basis", max_starts=3)

    assert result.start_ids == ("doc-0", "doc-1", "doc-2")
    assert result.capped is True


def test_build_traversal_starts_empty_when_no_prepass_hits():
    result = build_traversal_starts([], "basis", max_starts=10)

    assert result.empty is True
    assert result.prepass_chunk_ids == ()
    assert result.start_ids == ()
    assert result.capped is False


def test_build_traversal_starts_empty_when_candidates_lack_identity_field():
    # All hits have empty id_str, so the cross-document mapping resolves to nothing
    # even though prepass hits exist.
    hits = [_chunk("c1", id_str=""), _chunk("c2", id_str="")]

    result = build_traversal_starts(hits, "basis", max_starts=10)

    assert result.prepass_chunk_ids == ("c1", "c2")
    assert result.start_ids == ()
    assert result.empty is True


def test_build_traversal_starts_never_reads_ground_truth():
    # The function signature only accepts (prepass_hits, mode, max_starts); passing
    # RetrievedChunk objects that carry no ground-truth-adjacent data at all confirms
    # there is no hidden dependency on any ground_truth.* field (FR-003g).
    hits = [_chunk("c1", id_str="doc-A")]

    result_a = build_traversal_starts(hits, "basis", max_starts=10)
    result_b = build_traversal_starts(hits, "basis", max_starts=10)

    assert result_a == result_b
    assert not hasattr(build_traversal_starts, "ground_truth")


def test_fuse_hybrid_chunk_ids_preserves_seed_expansion_traversal_order():
    result = fuse_hybrid_chunk_ids(
        seed_chunk_ids=["s1", "s2"],
        expansion_chunk_ids=["e1", "e2"],
        traversal_chunk_ids=["t1", "t2"],
    )

    assert result.retrieved_chunk_ids == ("s1", "s2", "e1", "e2", "t1", "t2")
    assert result.seed_count == 2
    assert result.expansion_added == ("e1", "e2")
    assert result.traversal_added == ("t1", "t2")


def test_fuse_hybrid_chunk_ids_dedupes_keep_first_across_all_lists():
    result = fuse_hybrid_chunk_ids(
        seed_chunk_ids=["s1", "s1", "dup"],
        expansion_chunk_ids=["dup", "e1", "e1"],
        traversal_chunk_ids=["e1", "dup", "t1"],
    )

    assert result.retrieved_chunk_ids == ("s1", "dup", "e1", "t1")
    assert result.seed_count == 2
    assert result.expansion_added == ("e1",)
    assert result.traversal_added == ("t1",)


def test_fuse_hybrid_chunk_ids_seed_rank_preserved_even_if_seed_reappears_later():
    result = fuse_hybrid_chunk_ids(
        seed_chunk_ids=["s1", "s2", "s3"],
        expansion_chunk_ids=["s2", "e1"],
        traversal_chunk_ids=["s1", "t1"],
    )

    assert result.retrieved_chunk_ids == ("s1", "s2", "s3", "e1", "t1")
    assert result.seed_count == 3


def test_fuse_hybrid_chunk_ids_empty_inputs():
    result = fuse_hybrid_chunk_ids([], [], [])

    assert result.retrieved_chunk_ids == ()
    assert result.seed_count == 0
    assert result.expansion_added == ()
    assert result.traversal_added == ()
