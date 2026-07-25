"""BM25 Sparse Retriever — rank_bm25-based sparse search over chunk_text.

Builds a BM25Okapi index from ``chunks.jsonl``, persists to disk via pickle,
and returns ``SearchHit`` objects compatible with the Dense retrieval pipeline.

Usage::

    # Build and save
    retriever = BM25SparseRetriever.build_from_chunks(Path("data/v2/chunks.jsonl"))
    retriever.save(Path("data/sparse_index"))

    # Load and search
    retriever = BM25SparseRetriever.load(Path("data/sparse_index"))
    hits = retriever.search("Điều kiện lao động", top_k=20)
"""
from __future__ import annotations

import json
import logging
import pickle
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from .stores import SearchHit

logger = logging.getLogger(__name__)


def _simple_tokenize(text: str) -> list[str]:
    """Unicode-aware whitespace tokenizer with punctuation removal.

    Serves as the default / fallback tokenizer when ``underthesea`` is not
    available (e.g. on Kaggle without the extra dependency).
    """
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return [tok for tok in text.split() if len(tok) > 1]


def _get_tokenizer():
    """Return the best available Vietnamese tokenizer."""
    try:
        from underthesea import word_tokenize  # type: ignore[import-untyped]

        def _tokenize(text: str) -> list[str]:
            segmented = word_tokenize(text, format="text")
            return _simple_tokenize(segmented)

        logger.info("Using underthesea word_tokenize for BM25 tokenization")
        return _tokenize
    except ImportError:
        logger.info("underthesea not available; falling back to simple whitespace tokenizer")
        return _simple_tokenize


class BM25SparseRetriever:
    """BM25Okapi-based sparse retriever with disk persistence.

    Stores the tokenized corpus, chunk IDs, and full payloads so that search
    results carry the same ``SearchHit`` schema used by the Dense pipeline.
    """

    def __init__(
        self,
        *,
        bm25,
        chunk_ids: list[str],
        payloads: list[dict[str, Any]],
        tokenizer,
    ) -> None:
        self._bm25 = bm25
        self._chunk_ids = chunk_ids
        self._payloads = payloads
        self._tokenizer = tokenizer

    # ------------------------------------------------------------------
    # Factory — build from chunks.jsonl
    # ------------------------------------------------------------------

    @classmethod
    def build_from_chunks(
        cls,
        chunks_path: Path,
        *,
        text_field: str = "chunk_text",
        id_field: str = "chunk_id",
        tokenizer=None,
    ) -> "BM25SparseRetriever":
        """Build a BM25 index from a ``chunks.jsonl`` file.

        Each line must be a JSON object containing at least ``chunk_id``
        and ``chunk_text``.
        """
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "rank_bm25 is required for BM25SparseRetriever. "
                "Install it with: pip install rank_bm25"
            ) from exc

        if tokenizer is None:
            tokenizer = _get_tokenizer()

        logger.info("Building BM25 index from %s", chunks_path)
        t0 = time.perf_counter()

        chunk_ids: list[str] = []
        payloads: list[dict[str, Any]] = []
        tokenized_corpus: list[list[str]] = []

        with chunks_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid JSON at %s:%d", chunks_path, line_no)
                    continue

                chunk_id = str(record.get(id_field) or f"chunk_{line_no}")
                text = str(record.get(text_field) or "")
                tokens = tokenizer(text)

                chunk_ids.append(chunk_id)
                payloads.append(record)
                tokenized_corpus.append(tokens)

        bm25 = BM25Okapi(tokenized_corpus)
        duration = time.perf_counter() - t0
        logger.info(
            "BM25 index built: %d documents in %.2fs",
            len(chunk_ids),
            duration,
        )
        return cls(bm25=bm25, chunk_ids=chunk_ids, payloads=payloads, tokenizer=tokenizer)

    @classmethod
    def build_from_records(
        cls,
        records: list[dict[str, Any]],
        *,
        text_field: str = "chunk_text",
        id_field: str = "chunk_id",
        tokenizer=None,
    ) -> "BM25SparseRetriever":
        """Build a BM25 index from a list of chunk dicts (in-memory)."""
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "rank_bm25 is required for BM25SparseRetriever. "
                "Install it with: pip install rank_bm25"
            ) from exc

        if tokenizer is None:
            tokenizer = _get_tokenizer()

        chunk_ids: list[str] = []
        payloads: list[dict[str, Any]] = []
        tokenized_corpus: list[list[str]] = []

        for record in records:
            chunk_id = str(record.get(id_field) or "")
            text = str(record.get(text_field) or "")
            tokens = tokenizer(text)
            chunk_ids.append(chunk_id)
            payloads.append(record)
            tokenized_corpus.append(tokens)

        bm25 = BM25Okapi(tokenized_corpus)
        return cls(bm25=bm25, chunk_ids=chunk_ids, payloads=payloads, tokenizer=tokenizer)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, index_dir: Path) -> None:
        """Save the BM25 index + metadata to disk."""
        index_dir.mkdir(parents=True, exist_ok=True)

        bm25_path = index_dir / "bm25_index.pkl"
        meta_path = index_dir / "bm25_metadata.pkl"

        with bm25_path.open("wb") as f:
            pickle.dump(self._bm25, f, protocol=pickle.HIGHEST_PROTOCOL)

        with meta_path.open("wb") as f:
            pickle.dump(
                {
                    "chunk_ids": self._chunk_ids,
                    "payloads": self._payloads,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        logger.info(
            "Saved BM25 index to %s (%d documents, %.1f MB)",
            index_dir,
            len(self._chunk_ids),
            (bm25_path.stat().st_size + meta_path.stat().st_size) / 1024 / 1024,
        )

    @classmethod
    def load(cls, index_dir: Path) -> "BM25SparseRetriever":
        """Load a previously saved BM25 index from disk."""
        bm25_path = index_dir / "bm25_index.pkl"
        meta_path = index_dir / "bm25_metadata.pkl"

        if not bm25_path.exists():
            raise FileNotFoundError(f"BM25 index not found at {bm25_path}")

        logger.info("Loading BM25 index from %s", index_dir)

        with bm25_path.open("rb") as f:
            bm25 = pickle.load(f)

        with meta_path.open("rb") as f:
            meta = pickle.load(f)

        tokenizer = _get_tokenizer()

        logger.info("Loaded BM25 index: %d documents", len(meta["chunk_ids"]))
        return cls(
            bm25=bm25,
            chunk_ids=meta["chunk_ids"],
            payloads=meta["payloads"],
            tokenizer=tokenizer,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, *, top_k: int = 20) -> list[SearchHit]:
        """Search the BM25 index and return hits in the shared ``SearchHit`` format.

        Returns at most ``top_k`` results sorted by BM25 score descending.
        Each hit carries the full payload (same fields as the Dense pipeline).
        """
        tokenized_query = self._tokenizer(query)
        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices by score
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        hits: list[SearchHit] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            hits.append(
                SearchHit(
                    point_id=self._chunk_ids[idx],
                    score=score,
                    payload=self._payloads[idx],
                )
            )

        return hits

    def search_with_latency(self, query: str, *, top_k: int = 20) -> tuple[list[SearchHit], float]:
        """Search and return ``(hits, latency_seconds)``."""
        t0 = time.perf_counter()
        hits = self.search(query, top_k=top_k)
        latency = time.perf_counter() - t0
        return hits, latency

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_documents(self) -> int:
        return len(self._chunk_ids)
