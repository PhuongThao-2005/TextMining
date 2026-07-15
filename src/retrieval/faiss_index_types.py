"""FAISS index construction helpers (Flat IP and compressed IVFPQ).

``IndexFlatIP`` is exact but ~4 bytes × dim × ntotal in RAM (~6 GB for
1.5M × 1024-d float32). ``IndexIVFPQ`` trades a small recall loss for a
much smaller resident set (typically hundreds of MB for the same corpus).

Rebuild is one-shot: train on vectors reconstructed from an existing Flat
index (or a training sample), then replace ``index.faiss``. Payload JSONL /
SQLite cache stay unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FaissIndexConfig:
    """Parameters for building or rebuilding a FAISS index."""

    index_type: str = "flat"  # "flat" | "ivfpq"
    # IVF coarse quantizer clusters. ~4k is a solid default for ~1–2M vectors.
    nlist: int = 4096
    # PQ sub-quantizers; must divide embedding dim (1024 → 64 or 128).
    m: int = 64
    nbits: int = 8
    # Search-time probes; higher = better recall, more CPU/RAM traffic.
    nprobe: int = 32
    # Optional train sample size; None → faiss recommendation min(ntotal, nlist * 39).
    train_size: int | None = None
    # Random seed for train sampling (reproducible rebuilds).
    seed: int = 42

    def normalized(self) -> "FaissIndexConfig":
        kind = (self.index_type or "flat").strip().lower()
        if kind not in {"flat", "ivfpq"}:
            raise ValueError(f"Unsupported index_type={self.index_type!r}; use 'flat' or 'ivfpq'")
        if kind == "ivfpq":
            if self.nlist < 1:
                raise ValueError("nlist must be >= 1 for ivfpq")
            if self.m < 1:
                raise ValueError("m must be >= 1 for ivfpq")
            if self.nbits < 1:
                raise ValueError("nbits must be >= 1 for ivfpq")
            if self.nprobe < 1:
                raise ValueError("nprobe must be >= 1 for ivfpq")
        return FaissIndexConfig(
            index_type=kind,
            nlist=int(self.nlist),
            m=int(self.m),
            nbits=int(self.nbits),
            nprobe=int(self.nprobe),
            train_size=None if self.train_size is None else int(self.train_size),
            seed=int(self.seed),
        )

    def to_meta(self) -> dict[str, Any]:
        return asdict(self.normalized())


def _import_faiss():
    try:
        import faiss

        return faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is required for FAISS index helpers. "
            "Install it with: pip install faiss-cpu"
        ) from exc


def create_empty_index(dimension: int, config: FaissIndexConfig | None = None):
    """Create an empty FAISS index for the given dimension.

    Flat indexes are immediately addable. IVFPQ indexes are created but still
    require :func:`train_and_add` (or an external train step) before ``add``.
    """
    faiss = _import_faiss()
    cfg = (config or FaissIndexConfig()).normalized()
    if cfg.index_type == "flat":
        return faiss.IndexFlatIP(dimension)

    if dimension % cfg.m != 0:
        raise ValueError(
            f"IVFPQ m={cfg.m} must divide dimension={dimension} "
            f"(e.g. m=64 or m=128 for dim=1024)"
        )
    quantizer = faiss.IndexFlatIP(dimension)
    # Prefer IP metric for L2-normalized e5 embeddings (cosine via inner product).
    # FAISS ≥1.6 supports METRIC_INNER_PRODUCT on IndexIVFPQ; fall back to L2
    # (ranking-equivalent on unit vectors) if the binding rejects the metric kw.
    try:
        index = faiss.IndexIVFPQ(
            quantizer,
            dimension,
            cfg.nlist,
            cfg.m,
            cfg.nbits,
            faiss.METRIC_INNER_PRODUCT,
        )
    except TypeError:
        index = faiss.IndexIVFPQ(quantizer, dimension, cfg.nlist, cfg.m, cfg.nbits)
        try:
            index.metric_type = faiss.METRIC_INNER_PRODUCT
        except Exception:
            logger.warning(
                "IndexIVFPQ IP metric unavailable; using default L2 "
                "(still rank-compatible for unit vectors; scores are distances)."
            )
    return index


def apply_search_params(index, config: FaissIndexConfig | None = None) -> None:
    """Set runtime search parameters (nprobe) when the index supports them."""
    cfg = (config or FaissIndexConfig()).normalized()
    if hasattr(index, "nprobe"):
        index.nprobe = min(cfg.nprobe, max(1, int(getattr(index, "nlist", cfg.nprobe) or cfg.nprobe)))


def describe_index(index) -> dict[str, Any]:
    """Return a small JSON-serializable description of a FAISS index."""
    name = type(index).__name__
    info: dict[str, Any] = {
        "class_name": name,
        "dimension": int(getattr(index, "d", 0) or 0),
        "ntotal": int(getattr(index, "ntotal", 0) or 0),
        "is_trained": bool(getattr(index, "is_trained", True)),
    }
    if hasattr(index, "nlist"):
        info["nlist"] = int(index.nlist)
    if hasattr(index, "nprobe"):
        info["nprobe"] = int(index.nprobe)
    if hasattr(index, "pq"):
        try:
            info["pq_m"] = int(index.pq.M)
            info["pq_nbits"] = int(index.pq.nbits)
        except Exception:
            pass
    # Rough RSS estimate: Flat = 4*d*n; IVFPQ codes ≈ n * (m * nbits / 8) + coarse.
    d = info["dimension"]
    n = info["ntotal"]
    if "Flat" in name and d and n:
        info["approx_vector_bytes"] = int(n * d * 4)
    elif "IVFPQ" in name or "IVF" in name:
        m = int(info.get("pq_m") or 0)
        nbits = int(info.get("pq_nbits") or 8)
        if m and n:
            info["approx_vector_bytes"] = int(n * m * nbits / 8)
    return info


def _sample_train_vectors(
    vectors: np.ndarray,
    *,
    nlist: int,
    train_size: int | None,
    seed: int,
) -> np.ndarray:
    ntotal = int(vectors.shape[0])
    # FAISS rule of thumb: at least ~39 training vectors per centroid.
    recommended = min(ntotal, max(nlist * 39, nlist))
    target = recommended if train_size is None else min(ntotal, max(int(train_size), nlist))
    if target >= ntotal:
        return np.ascontiguousarray(vectors)
    rng = np.random.default_rng(seed)
    idx = rng.choice(ntotal, size=target, replace=False)
    idx.sort()
    return np.ascontiguousarray(vectors[idx])


def train_and_add_ivfpq(
    index,
    vectors: np.ndarray,
    config: FaissIndexConfig,
) -> None:
    """Train an empty IVFPQ index and add all ``vectors`` (float32, shape N×d)."""
    faiss = _import_faiss()
    cfg = config.normalized()
    if vectors.dtype != np.float32:
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    else:
        vectors = np.ascontiguousarray(vectors)

    if vectors.ndim != 2:
        raise ValueError(f"vectors must be 2-D, got shape={vectors.shape}")
    if int(vectors.shape[1]) != int(index.d):
        raise ValueError(f"vector dim {vectors.shape[1]} != index.d {index.d}")
    # IVF needs ≥ nlist points; product quantizer needs ≥ 2**nbits codes per subspace.
    min_train = max(cfg.nlist, 2 ** cfg.nbits)
    if vectors.shape[0] < min_train:
        raise ValueError(
            f"Need at least max(nlist, 2**nbits)={min_train} vectors to train IVFPQ; "
            f"got {vectors.shape[0]} (nlist={cfg.nlist}, nbits={cfg.nbits})"
        )

    train_x = _sample_train_vectors(
        vectors, nlist=cfg.nlist, train_size=cfg.train_size, seed=cfg.seed
    )
    if train_x.shape[0] < min_train:
        # Ensure the train sample itself satisfies PQ/IVF minima.
        train_x = _sample_train_vectors(
            vectors,
            nlist=cfg.nlist,
            train_size=min_train,
            seed=cfg.seed,
        )
    logger.info(
        "Training IVFPQ: ntotal=%d train=%d nlist=%d m=%d nbits=%d",
        vectors.shape[0],
        train_x.shape[0],
        cfg.nlist,
        cfg.m,
        cfg.nbits,
    )
    index.train(train_x)
    index.add(vectors)
    apply_search_params(index, cfg)
    logger.info("IVFPQ ready: ntotal=%d nprobe=%s", index.ntotal, getattr(index, "nprobe", None))


def reconstruct_all_vectors(index, batch_size: int = 50_000) -> np.ndarray:
    """Materialize all vectors from an index that supports reconstruct.

    Flat indexes support ``reconstruct``. IVF/PQ product-quantized indexes
    only return approximate reconstructions; prefer rebuilding from the original
    Flat ``index.faiss`` when available.
    """
    ntotal = int(index.ntotal)
    dim = int(index.d)
    out = np.empty((ntotal, dim), dtype=np.float32)
    for start in range(0, ntotal, batch_size):
        end = min(start + batch_size, ntotal)
        for i in range(start, end):
            out[i] = index.reconstruct(i)
        if end % (batch_size * 5) == 0 or end == ntotal:
            logger.info("Reconstructed vectors %d / %d", end, ntotal)
    return out


def rebuild_index_to_ivfpq(
    source_index_path: Path | str,
    dest_index_path: Path | str,
    config: FaissIndexConfig | None = None,
    *,
    meta_path: Path | str | None = None,
    batch_size: int = 50_000,
) -> dict[str, Any]:
    """Rebuild ``source_index_path`` as IndexIVFPQ and write ``dest_index_path``.

    Vectors are reconstructed from the source index (exact for Flat). Payload
    files are not touched. Returns a stats dict suitable for logging / reports.
    """
    import json
    import time

    faiss = _import_faiss()
    cfg = (config or FaissIndexConfig(index_type="ivfpq")).normalized()
    if cfg.index_type != "ivfpq":
        cfg = FaissIndexConfig(
            index_type="ivfpq",
            nlist=cfg.nlist,
            m=cfg.m,
            nbits=cfg.nbits,
            nprobe=cfg.nprobe,
            train_size=cfg.train_size,
            seed=cfg.seed,
        ).normalized()

    source_index_path = Path(source_index_path)
    dest_index_path = Path(dest_index_path)
    if not source_index_path.exists():
        raise FileNotFoundError(f"Source FAISS index not found: {source_index_path}")

    t0 = time.perf_counter()
    logger.info("Loading source index from %s", source_index_path)
    source = faiss.read_index(str(source_index_path))
    source_info = describe_index(source)
    logger.info("Source index: %s", source_info)

    if source.ntotal == 0:
        raise RuntimeError("Source index has zero vectors; nothing to compress")

    # Prefer reconstruct on Flat; for already-compressed sources this is lossy.
    if not hasattr(source, "reconstruct"):
        raise RuntimeError(
            f"Source index type {type(source).__name__} does not support reconstruct(); "
            "rebuild IVFPQ from the original IndexFlatIP artifact."
        )

    vectors = reconstruct_all_vectors(source, batch_size=batch_size)
    del source  # free Flat RSS before training when possible

    index = create_empty_index(vectors.shape[1], cfg)
    train_and_add_ivfpq(index, vectors, cfg)
    del vectors

    dest_index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(dest_index_path))
    dest_info = describe_index(index)
    elapsed = time.perf_counter() - t0

    meta = {
        "config": cfg.to_meta(),
        "source": source_info,
        "dest": dest_info,
        "source_path": str(source_index_path),
        "dest_path": str(dest_index_path),
        "elapsed_seconds": round(elapsed, 3),
        "source_bytes": source_index_path.stat().st_size,
        "dest_bytes": dest_index_path.stat().st_size,
        "compression_ratio": round(
            source_index_path.stat().st_size / max(1, dest_index_path.stat().st_size), 3
        ),
    }
    out_meta = Path(meta_path) if meta_path is not None else dest_index_path.with_suffix(".ivfpq.meta.json")
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info(
        "Wrote IVFPQ index to %s (%.1f MB → %.1f MB, ratio %.2fx) in %.1fs",
        dest_index_path,
        meta["source_bytes"] / 1024 / 1024,
        meta["dest_bytes"] / 1024 / 1024,
        meta["compression_ratio"],
        elapsed,
    )
    return meta
