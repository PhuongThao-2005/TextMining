"""Load pre-computed embedding shards into a VectorStore.

Each shard directory contains:
  - vectors.npy      (N × dim, float16)
  - payloads.jsonl    (N lines, one JSON object per chunk)
  - meta.json         (shard metadata: count, model, dimension, etc.)

Typical layout produced by the Kaggle embedding notebook:
  embedding/
    vector_shards_part_00/
      shard_000000/  {vectors.npy, payloads.jsonl, meta.json}
      shard_000001/
      shard_000002/
      summary.json
    vector_shards_part_01/
      ...
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .schema import VectorRecord
from .stores import VectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ShardInfo:
    """Metadata about a single shard directory."""
    path: Path
    shard_index: int
    count: int
    model: str
    dimension: int

    @classmethod
    def from_dir(cls, shard_dir: Path) -> "ShardInfo":
        meta_path = shard_dir / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing meta.json in {shard_dir}")
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        return cls(
            path=shard_dir,
            shard_index=meta.get("shard_index", 0),
            count=meta.get("count", 0),
            model=meta.get("model", "unknown"),
            dimension=meta.get("dimension", 0),
        )


@dataclass
class LoadStats:
    """Accumulated statistics from loading shards into the store."""
    total_shards: int = 0
    total_records_loaded: int = 0
    total_records_skipped: int = 0
    duplicate_chunk_ids: int = 0
    missing_chunk_text: int = 0
    missing_citation_anchor: int = 0
    quarantine_filtered: int = 0
    external_stub_filtered: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shard discovery
# ---------------------------------------------------------------------------

def discover_shards(embedding_dir: Path) -> list[Path]:
    """Find all shard directories under an embedding output directory.

    Handles both flat layout (embedding_dir/shard_XXXXXX/) and
    partitioned layout (embedding_dir/vector_shards_part_XX/shard_XXXXXX/).
    Returns shard directories sorted by name.
    """
    shard_dirs: list[Path] = []

    # Partitioned layout: embedding_dir/vector_shards_part_XX/shard_XXXXXX/
    for part_dir in sorted(embedding_dir.iterdir()):
        if part_dir.is_dir() and part_dir.name.startswith("vector_shards_part_"):
            for shard_dir in sorted(part_dir.iterdir()):
                if shard_dir.is_dir() and shard_dir.name.startswith("shard_"):
                    if (shard_dir / "vectors.npy").exists():
                        shard_dirs.append(shard_dir)

    # Flat layout fallback: embedding_dir/shard_XXXXXX/
    if not shard_dirs:
        for shard_dir in sorted(embedding_dir.iterdir()):
            if shard_dir.is_dir() and shard_dir.name.startswith("shard_"):
                if (shard_dir / "vectors.npy").exists():
                    shard_dirs.append(shard_dir)

    return shard_dirs


# ---------------------------------------------------------------------------
# Shard reading
# ---------------------------------------------------------------------------

def read_shard(shard_dir: Path) -> Iterator[tuple[list[float], dict[str, Any]]]:
    """Yield (vector, payload) pairs from a single shard directory.

    Vectors are loaded from vectors.npy (float16 → float32) and
    payloads from payloads.jsonl, paired by index.
    """
    vectors_path = shard_dir / "vectors.npy"
    payloads_path = shard_dir / "payloads.jsonl"

    if not vectors_path.exists():
        raise FileNotFoundError(f"Missing vectors.npy in {shard_dir}")
    if not payloads_path.exists():
        raise FileNotFoundError(f"Missing payloads.jsonl in {shard_dir}")

    # Load vectors: float16 → float32 for compatibility with vector DBs
    vectors = np.load(vectors_path).astype(np.float32)

    with payloads_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if idx >= len(vectors):
                logger.warning(
                    "Shard %s: more payloads than vectors (idx=%d, vectors=%d)",
                    shard_dir.name, idx, len(vectors),
                )
                break
            payload = json.loads(line)
            vector = vectors[idx].tolist()
            yield vector, payload

    if idx + 1 < len(vectors):
        logger.warning(
            "Shard %s: more vectors (%d) than payloads (%d)",
            shard_dir.name, len(vectors), idx + 1,
        )


# ---------------------------------------------------------------------------
# Blacklist loading (quarantine + external stubs)
# ---------------------------------------------------------------------------

def load_blacklist_id_strs(data_dir: Path) -> set[str]:
    """Load id_str values from documents_quarantine.jsonl and external_stubs.jsonl.

    Chunks belonging to these documents must NOT be indexed (SPEC §2, §5.3).
    """
    blacklist: set[str] = set()

    for filename in ("documents_quarantine.jsonl", "external_stubs.jsonl"):
        path = data_dir / filename
        if not path.exists():
            logger.info("Blacklist file %s not found at %s — skipping", filename, data_dir)
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    id_str = str(row.get("id_str") or "")
                    if id_str:
                        blacklist.add(id_str)
                except json.JSONDecodeError:
                    continue

    logger.info(
        "Loaded blacklist: %d id_strs from quarantine + external_stubs",
        len(blacklist),
    )
    return blacklist


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

class ShardLoader:
    """Load pre-computed embedding shards into a VectorStore.

    Usage:
        loader = ShardLoader(store=qdrant_store, embedding_dir=Path("embedding"))
        stats = loader.load_all(recreate=True, data_dir=Path("data/v2"))
    """

    def __init__(
        self,
        *,
        store: VectorStore,
        embedding_dir: Path,
        upsert_batch_size: int = 100,
    ) -> None:
        self.store = store
        self.embedding_dir = embedding_dir
        self.upsert_batch_size = upsert_batch_size

    def load_all(
        self,
        *,
        recreate: bool = True,
        data_dir: Path | None = None,
        limit: int | None = None,
    ) -> LoadStats:
        """Discover all shards, optionally filter quarantine/stubs, and upsert.

        Args:
            recreate: If True, recreate the collection before loading.
            data_dir: Path to data/v2 directory containing quarantine/stub files.
                      If None, quarantine filtering is skipped.
            limit: Max total records to load (for testing). None = load all.
        """
        stats = LoadStats()
        start = time.time()

        # Discover shards
        shard_dirs = discover_shards(self.embedding_dir)
        if not shard_dirs:
            stats.errors.append(f"No shard directories found in {self.embedding_dir}")
            return stats

        # Determine vector dimension from first shard
        first_info = ShardInfo.from_dir(shard_dirs[0])
        dimension = first_info.dimension
        logger.info(
            "Found %d shards, dimension=%d, model=%s",
            len(shard_dirs), dimension, first_info.model,
        )

        # Load blacklist
        blacklist: set[str] = set()
        if data_dir is not None:
            blacklist = load_blacklist_id_strs(data_dir)

        # Recreate collection
        if recreate:
            logger.info("Recreating collection with dimension=%d", dimension)
            self.store.recreate_collection(dimension)

        # Load shards
        seen_chunk_ids: set[str] = set()
        batch: list[VectorRecord] = []
        done = False

        for shard_dir in shard_dirs:
            if done:
                break

            stats.total_shards += 1
            shard_name = f"{shard_dir.parent.name}/{shard_dir.name}"
            logger.info("Loading shard: %s", shard_name)

            try:
                for vector, payload in read_shard(shard_dir):
                    chunk_id = str(payload.get("chunk_id") or "")
                    id_str = str(payload.get("id_str") or "")

                    # Skip duplicates
                    if chunk_id in seen_chunk_ids:
                        stats.duplicate_chunk_ids += 1
                        stats.total_records_skipped += 1
                        continue
                    seen_chunk_ids.add(chunk_id)

                    # Skip quarantine/external_stubs
                    if id_str in blacklist:
                        source = "quarantine" if "quarantine" in id_str else "external_stub"
                        if source == "quarantine":
                            stats.quarantine_filtered += 1
                        else:
                            stats.external_stub_filtered += 1
                        stats.total_records_skipped += 1
                        continue

                    # Quality tracking
                    if not payload.get("chunk_text"):
                        stats.missing_chunk_text += 1
                    if not payload.get("citation_anchor"):
                        stats.missing_citation_anchor += 1

                    batch.append(VectorRecord(
                        point_id=chunk_id,
                        vector=vector,
                        payload=payload,
                    ))

                    # Flush batch
                    if len(batch) >= self.upsert_batch_size:
                        self.store.upsert(batch)
                        stats.total_records_loaded += len(batch)
                        batch = []

                    # Check limit
                    if limit is not None and stats.total_records_loaded + len(batch) >= limit:
                        done = True
                        break

            except Exception as exc:
                msg = f"Error loading shard {shard_name}: {exc}"
                logger.error(msg)
                stats.errors.append(msg)

            logger.info(
                "Progress: %d shards, %d loaded, %d skipped",
                stats.total_shards,
                stats.total_records_loaded + len(batch),
                stats.total_records_skipped,
            )

        # Flush remaining batch
        if batch:
            self.store.upsert(batch)
            stats.total_records_loaded += len(batch)

        stats.elapsed_seconds = time.time() - start
        logger.info(
            "Done: %d records loaded, %d skipped, %d shards, %.1fs",
            stats.total_records_loaded,
            stats.total_records_skipped,
            stats.total_shards,
            stats.elapsed_seconds,
        )
        return stats
