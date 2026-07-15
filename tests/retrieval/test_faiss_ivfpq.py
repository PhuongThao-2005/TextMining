"""Unit tests for FAISS IVFPQ rebuild helpers (synthetic vectors only)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

faiss = pytest.importorskip("faiss")

from retrieval.faiss_index_types import (  # noqa: E402
    FaissIndexConfig,
    create_empty_index,
    describe_index,
    rebuild_index_to_ivfpq,
    train_and_add_ivfpq,
)
from retrieval.faiss_store import FaissVectorStore  # noqa: E402
from retrieval.schema import VectorRecord  # noqa: E402


def _unit_vectors(n: int, dim: int = 32, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, dim), dtype=np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    return x


def test_create_empty_flat_and_ivfpq():
    flat = create_empty_index(32, FaissIndexConfig(index_type="flat"))
    assert type(flat).__name__ == "IndexFlatIP"
    ivf = create_empty_index(32, FaissIndexConfig(index_type="ivfpq", nlist=4, m=8, nbits=4))
    assert "IVFPQ" in type(ivf).__name__
    assert not ivf.is_trained


def test_train_and_search_ivfpq_roundtrip(tmp_path: Path):
    # nbits=8 → PQ needs ≥256 train points; use n=300 for headroom.
    dim, n = 32, 300
    vectors = _unit_vectors(n, dim)
    cfg = FaissIndexConfig(index_type="ivfpq", nlist=8, m=8, nbits=8, nprobe=4, seed=1)
    index = create_empty_index(dim, cfg)
    train_and_add_ivfpq(index, vectors, cfg)
    assert index.ntotal == n
    assert index.is_trained

    scores, ids = index.search(vectors[:1], 5)
    assert ids.shape == (1, 5)
    assert ids[0, 0] >= 0

    dest = tmp_path / "index.faiss"
    faiss.write_index(index, str(dest))
    loaded = faiss.read_index(str(dest))
    info = describe_index(loaded)
    assert info["ntotal"] == n
    assert info["dimension"] == dim


def test_rebuild_index_to_ivfpq_from_flat(tmp_path: Path):
    dim, n = 32, 300
    vectors = _unit_vectors(n, dim)
    flat = faiss.IndexFlatIP(dim)
    flat.add(vectors)
    src = tmp_path / "flat" / "index.faiss"
    src.parent.mkdir(parents=True)
    faiss.write_index(flat, str(src))

    dest = tmp_path / "ivfpq" / "index.faiss"
    cfg = FaissIndexConfig(index_type="ivfpq", nlist=8, m=8, nbits=8, nprobe=4)
    meta = rebuild_index_to_ivfpq(src, dest, cfg)
    assert dest.exists()
    assert meta["dest"]["ntotal"] == n
    assert meta["compression_ratio"] >= 1.0 or meta["dest_bytes"] > 0

    loaded = faiss.read_index(str(dest))
    scores, ids = loaded.search(vectors[:3], 3)
    assert ids.shape == (3, 3)


def test_faiss_store_ivfpq_buffer_and_save(tmp_path: Path):
    dim = 32
    # nbits=4 → only 16 PQ centroids; 80 vectors is enough for tiny unit tests.
    cfg = FaissIndexConfig(index_type="ivfpq", nlist=4, m=8, nbits=4, nprobe=2, seed=0)
    store = FaissVectorStore.create(dimension=dim, index_dir=tmp_path, index_config=cfg)
    records = [
        VectorRecord(
            point_id=f"c{i}",
            vector=_unit_vectors(1, dim, seed=i)[0].tolist(),
            payload={"chunk_id": f"c{i}", "validity_group": "active"},
        )
        for i in range(80)
    ]
    store.upsert(records[:20])
    store.upsert(records[20:])
    assert store.index.ntotal == 0  # still buffered
    store.save()
    assert store.index.ntotal == 40
    assert (tmp_path / "index.faiss").exists()
    assert (tmp_path / "index_type.json").exists()

    hits = store.search(records[0].vector, limit=3)
    assert hits
    assert hits[0].payload["chunk_id"].startswith("c")

    reloaded = FaissVectorStore.load(tmp_path)
    assert reloaded.total_vectors == 40
    hits2 = reloaded.search(records[0].vector, limit=3)
    assert hits2
