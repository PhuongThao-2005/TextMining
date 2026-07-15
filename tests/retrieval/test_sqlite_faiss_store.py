"""Unit tests for SQLite-backed FAISS payload store (synthetic fixtures only)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pytest

from retrieval.sqlite_faiss_store import (
    PayloadCacheStatus,
    SQLitePayloadFaissVectorStore,
    _check_payload_cache,
    _ensure_payload_cache,
)


def _write_payloads(path: Path, payloads: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_meta(cache_path: Path) -> dict[str, str]:
    conn = sqlite3.connect(str(cache_path))
    try:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()


def test_check_payload_cache_missing(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    _write_payloads(payloads, [{"chunk_id": "c0"}])
    status = _check_payload_cache(tmp_path)
    assert status.exists is False
    assert status.is_stale is True
    assert status.payload_size == payloads.stat().st_size


def test_check_payload_cache_fresh(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    _write_payloads(payloads, [{"chunk_id": "c0"}, {"chunk_id": "c1"}])
    cache = tmp_path / "payload_cache.sqlite"
    _ensure_payload_cache(payloads, cache)

    status = _check_payload_cache(tmp_path)
    assert status == PayloadCacheStatus(
        exists=True,
        is_stale=False,
        payload_size=payloads.stat().st_size,
        payload_mtime_ns=payloads.stat().st_mtime_ns,
    )


def test_check_payload_cache_stale_by_size(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    _write_payloads(payloads, [{"chunk_id": "c0"}])
    cache = tmp_path / "payload_cache.sqlite"
    _ensure_payload_cache(payloads, cache)

    with payloads.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"chunk_id": "c1"}) + "\n")

    status = _check_payload_cache(tmp_path)
    assert status.exists is True
    assert status.is_stale is True


def test_check_payload_cache_stale_by_mtime(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    _write_payloads(payloads, [{"chunk_id": "c0"}])
    cache = tmp_path / "payload_cache.sqlite"
    _ensure_payload_cache(payloads, cache)

    # Keep size identical; bump mtime only.
    original = payloads.read_bytes()
    time.sleep(0.01)
    payloads.write_bytes(original)
    # Ensure mtime actually differs from cached meta.
    newer = payloads.stat().st_mtime_ns + 1_000_000
    os_utime = __import__("os").utime
    os_utime(payloads, ns=(newer, newer))

    status = _check_payload_cache(tmp_path)
    assert status.exists is True
    assert status.is_stale is True


def test_ensure_payload_cache_rebuild_then_reuse(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    cache = tmp_path / "payload_cache.sqlite"
    rows = [
        {
            "chunk_id": "c0",
            "parent_unit_id": "p0",
            "id_str": "d0",
            "chunk_text": "alpha",
            "validity_group": "current",
        },
        {
            "chunk_id": "c1",
            "parent_unit_id": "p1",
            "id_str": "d1",
            "chunk_text": "beta",
            "validity_group": "historical",
        },
    ]
    _write_payloads(payloads, rows)

    _ensure_payload_cache(payloads, cache)
    assert cache.exists()
    meta1 = _read_meta(cache)
    mtime1 = cache.stat().st_mtime_ns

    _ensure_payload_cache(payloads, cache)
    meta2 = _read_meta(cache)
    mtime2 = cache.stat().st_mtime_ns
    assert meta1 == meta2
    assert mtime2 == mtime1  # second call reuses without rewrite

    conn = sqlite3.connect(str(cache))
    try:
        count = conn.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]
        loaded = {
            int(line_no): json.loads(payload)
            for line_no, payload in conn.execute(
                "SELECT line_no, payload FROM payloads ORDER BY line_no"
            )
        }
    finally:
        conn.close()
    assert count == 2
    assert loaded[0]["chunk_id"] == "c0"
    assert loaded[1]["chunk_id"] == "c1"


def _make_index_fixture(tmp_path: Path, n: int = 3, dim: int = 8):
    faiss = pytest.importorskip("faiss")
    rng = np.random.default_rng(0)
    vectors = rng.standard_normal((n, dim), dtype=np.float32)
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    payloads = []
    for i in range(n):
        payloads.append(
            {
                "chunk_id": f"chunk-{i}",
                "parent_unit_id": f"parent-{i // 2}",
                "id_str": f"doc-{i}",
                "chunk_text": f"text-{i}",
                "title": f"Title {i}",
                "citation_anchor": f"Art.{i}",
                "validity_group": "current" if i < 2 else "historical",
                "unit_type": "article",
                "legal_authority_rank": i + 1,
            }
        )
    index_dir = tmp_path / "faiss_index"
    index_dir.mkdir()
    faiss.write_index(index, str(index_dir / "index.faiss"))
    _write_payloads(index_dir / "payloads.jsonl", payloads)
    return index_dir, vectors, payloads


def test_search_and_scroll_with_filters(tmp_path: Path) -> None:
    index_dir, vectors, payloads = _make_index_fixture(tmp_path)
    store = SQLitePayloadFaissVectorStore.load(index_dir)
    try:
        assert store.total_vectors == 3

        hits = store.search(vectors[0].tolist(), limit=2)
        assert len(hits) >= 1
        assert hits[0].payload["chunk_id"] == "chunk-0"
        assert "parent_unit_id" in hits[0].payload
        assert "id_str" in hits[0].payload

        filtered = store.search(
            vectors[0].tolist(),
            limit=5,
            filters={"validity_group": "historical"},
        )
        assert all(h.payload.get("validity_group") == "historical" for h in filtered)

        empty = store.search(
            vectors[0].tolist(),
            limit=5,
            score_threshold=2.0,  # IP of unit vectors maxes at 1.0
        )
        assert empty == []

        scrolled = store.scroll({"validity_group": "current"}, limit=10)
        assert len(scrolled) == 2
        assert {h.payload["chunk_id"] for h in scrolled} == {"chunk-0", "chunk-1"}
    finally:
        store.close()


def test_load_missing_index_raises(tmp_path: Path) -> None:
    payloads = tmp_path / "payloads.jsonl"
    _write_payloads(payloads, [{"chunk_id": "c0"}])
    with pytest.raises(FileNotFoundError, match="FAISS index not found"):
        SQLitePayloadFaissVectorStore.load(tmp_path)


def test_load_missing_payloads_raises(tmp_path: Path) -> None:
    faiss = pytest.importorskip("faiss")
    index = faiss.IndexFlatIP(4)
    index.add(np.zeros((1, 4), dtype=np.float32))
    faiss.write_index(index, str(tmp_path / "index.faiss"))
    with pytest.raises(FileNotFoundError, match="Payload file not found"):
        SQLitePayloadFaissVectorStore.load(tmp_path)


def test_search_hit_identity_fields_for_benchmark(tmp_path: Path) -> None:
    index_dir, vectors, _ = _make_index_fixture(tmp_path, n=2)
    store = SQLitePayloadFaissVectorStore.load(index_dir)
    try:
        hits = store.search(vectors[1].tolist(), limit=1)
        assert hits
        payload = hits[0].payload
        for key in ("chunk_id", "parent_unit_id", "id_str"):
            assert key in payload
            assert payload[key]
    finally:
        store.close()
