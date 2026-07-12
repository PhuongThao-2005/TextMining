from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import Iterable

from .io_utils import clean_text


class Embedder(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


def l2_normalize(vector: Iterable[float]) -> list[float]:
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        return values
    return [v / norm for v in values]


class SentenceTransformerEmbedder(Embedder):
    """Production embedder using sentence-transformers."""

    def __init__(
        self,
        model_name: str,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
        device: str | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for SentenceTransformerEmbedder. "
                "Install it before running the production embedding job."
            ) from exc

        self.model_name = model_name
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.model = SentenceTransformer(model_name, device=device)
        dim = self.model.get_sentence_embedding_dimension()
        if not dim:
            raise RuntimeError(f"Could not determine embedding dimension for {model_name}")
        self.dimension = int(dim)

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self.passage_prefix + text for text in texts]
        vectors = self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [l2_normalize(row) for row in vectors.tolist()]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self.query_prefix + text for text in texts]
        vectors = self.model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        return [l2_normalize(row) for row in vectors.tolist()]


class HashingEmbedder(Embedder):
    """Deterministic lightweight embedder for smoke tests and local development."""

    def __init__(self, dimension: int = 384) -> None:
        self.model_name = f"hashing-dev-{dimension}"
        self.dimension = dimension

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def encode_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    def _encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in clean_text(text).lower().split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return l2_normalize(vector)
