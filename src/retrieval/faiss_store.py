"""FAISS-based vector store — persistent index file, no server needed.

Saves the FAISS index + payload data to disk. Load once, search instantly.
Ideal for local development and projects that don't need a running DB server.

Usage:
    # Build and save
    store = FaissVectorStore.create(dimension=1024, index_dir=Path("data/faiss_index"))
    store.upsert(records)
    store.save()

    # Load and search
    store = FaissVectorStore.load(Path("data/faiss_index"))
    results = store.search(query_vector, limit=20)
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from .schema import VectorRecord
from .stores import SearchHit, VectorStore, payload_matches

logger = logging.getLogger(__name__)


class FaissVectorStore(VectorStore):
    """FAISS-backed vector store with payload filtering and disk persistence."""

    def __init__(
        self,
        *,
        index,  # faiss.Index
        dimension: int,
        index_dir: Path,
        payloads: dict[int, dict[str, Any]] | None = None,
        id_to_int: dict[str, int] | None = None,
        int_to_id: dict[int, str] | None = None,
    ) -> None:
        self._faiss = _import_faiss()
        self.index = index
        self.dimension = dimension
        self.index_dir = index_dir
        self.payloads: dict[int, dict[str, Any]] = payloads or {}
        self.id_to_int: dict[str, int] = id_to_int or {}
        self.int_to_id: dict[int, str] = int_to_id or {}
        self._next_int_id: int = max(self.int_to_id.keys(), default=-1) + 1

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, dimension: int, index_dir: Path) -> "FaissVectorStore":
        """Create a new empty FAISS store."""
        faiss = _import_faiss()
        index = faiss.IndexFlatIP(dimension)  # Inner product (cosine for normalized vectors)
        index_dir.mkdir(parents=True, exist_ok=True)
        return cls(index=index, dimension=dimension, index_dir=index_dir)

    @classmethod
    def load(cls, index_dir: Path) -> "FaissVectorStore":
        """Load a previously saved FAISS store from disk."""
        faiss = _import_faiss()

        index_path = index_dir / "index.faiss"
        payloads_path = index_dir / "payloads.jsonl"
        id_map_path = index_dir / "id_map.json"

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}")

        logger.info("Loading FAISS index from %s", index_dir)
        index = faiss.read_index(str(index_path))
        dimension = index.d

        # Load payloads
        payloads: dict[int, dict[str, Any]] = {}
        if payloads_path.exists():
            with payloads_path.open("r", encoding="utf-8") as f:
                for line_no, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    payloads[line_no] = json.loads(line)

        # Load ID mapping
        id_to_int: dict[str, int] = {}
        int_to_id: dict[int, str] = {}
        if id_map_path.exists():
            with id_map_path.open("r", encoding="utf-8") as f:
                id_map = json.load(f)
            id_to_int = {str(k): int(v) for k, v in id_map.items()}
            int_to_id = {v: k for k, v in id_to_int.items()}

        logger.info(
            "Loaded FAISS index: %d vectors, %d payloads, dim=%d",
            index.ntotal, len(payloads), dimension,
        )
        return cls(
            index=index,
            dimension=dimension,
            index_dir=index_dir,
            payloads=payloads,
            id_to_int=id_to_int,
            int_to_id=int_to_id,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Save the FAISS index + payloads + ID map to disk."""
        faiss = self._faiss
        self.index_dir.mkdir(parents=True, exist_ok=True)

        index_path = self.index_dir / "index.faiss"
        payloads_path = self.index_dir / "payloads.jsonl"
        id_map_path = self.index_dir / "id_map.json"

        # Save FAISS index
        faiss.write_index(self.index, str(index_path))

        # Save payloads ordered by int_id
        max_id = max(self.payloads.keys(), default=-1)
        with payloads_path.open("w", encoding="utf-8") as f:
            for i in range(max_id + 1):
                payload = self.payloads.get(i, {})
                f.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

        # Save ID map
        with id_map_path.open("w", encoding="utf-8") as f:
            json.dump(self.id_to_int, f, ensure_ascii=False)

        logger.info(
            "Saved FAISS index: %d vectors to %s (%.1f MB)",
            self.index.ntotal,
            index_path,
            index_path.stat().st_size / 1024 / 1024,
        )

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    def recreate_collection(self, vector_size: int) -> None:
        """Reset the store with a new empty index."""
        faiss = self._faiss
        self.index = faiss.IndexFlatIP(vector_size)
        self.dimension = vector_size
        self.payloads.clear()
        self.id_to_int.clear()
        self.int_to_id.clear()
        self._next_int_id = 0

    def upsert(self, records: list[VectorRecord]) -> None:
        """Add vectors and payloads to the index."""
        if not records:
            return

        vectors = np.zeros((len(records), self.dimension), dtype=np.float32)
        for i, record in enumerate(records):
            int_id = self._get_or_assign_int_id(record.point_id)
            vectors[i] = np.array(record.vector, dtype=np.float32)
            self.payloads[int_id] = record.payload

        # FAISS IndexFlatIP doesn't support upsert by ID, so we append
        # For the use case (build once, search many), this is fine
        self.index.add(vectors)

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if self.index.ntotal == 0:
            return []

        query = np.array([vector], dtype=np.float32)

        # Search more candidates if filtering (need extra to compensate for filtered-out)
        search_limit = limit * 10 if filters else limit
        search_limit = min(search_limit, self.index.ntotal)

        scores, indices = self.index.search(query, search_limit)

        hits: list[SearchHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue

            payload = self.payloads.get(int(idx), {})

            if score_threshold is not None and float(score) < score_threshold:
                continue

            if filters and not payload_matches(payload, filters):
                continue

            point_id = self.int_to_id.get(int(idx), str(idx))
            hits.append(SearchHit(point_id=point_id, score=float(score), payload=payload))

            if len(hits) >= limit:
                break

        return hits

    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]:
        """Scan payloads matching filters (no vector similarity)."""
        hits: list[SearchHit] = []
        for int_id, payload in self.payloads.items():
            if payload_matches(payload, filters):
                point_id = self.int_to_id.get(int_id, str(int_id))
                hits.append(SearchHit(point_id=point_id, score=0.0, payload=payload))
                if len(hits) >= limit:
                    break
        return hits

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_assign_int_id(self, point_id: str) -> int:
        """Map a string chunk_id to an integer FAISS ID."""
        if point_id in self.id_to_int:
            return self.id_to_int[point_id]
        int_id = self._next_int_id
        self._next_int_id += 1
        self.id_to_int[point_id] = int_id
        self.int_to_id[int_id] = point_id
        return int_id

    @property
    def total_vectors(self) -> int:
        return self.index.ntotal


def _import_faiss():
    try:
        import faiss
        return faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is required for FaissVectorStore. "
            "Install it with: pip install faiss-cpu"
        ) from exc
