"""Tests for memory probes and lazy embedder (no heavy model download)."""
from __future__ import annotations

from retrieval.embeddings import HashingEmbedder, LazySentenceTransformerEmbedder
from retrieval.memory_utils import print_memory, snapshot_memory


def test_snapshot_memory_has_rss():
    snap = snapshot_memory("unit_test")
    assert snap.label == "unit_test"
    assert snap.rss_mb >= 0
    assert snap.backend in {"psutil", "proc", "resource", "unavailable"}
    printed = print_memory("unit_test_print")
    assert printed.rss_bytes == snapshot_memory("x").rss_bytes or printed.rss_bytes >= 0


def test_lazy_embedder_known_dim_without_load():
    emb = LazySentenceTransformerEmbedder(
        "intfloat/multilingual-e5-large",
        expected_dimension=1024,
    )
    assert emb.dimension == 1024
    assert emb.is_loaded is False


def test_hashing_embedder_still_works():
    emb = HashingEmbedder(dimension=32)
    vecs = emb.encode_queries(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 32
