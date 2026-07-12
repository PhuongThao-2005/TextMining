from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .schema import VectorRecord


@dataclass(frozen=True)
class SearchHit:
    point_id: str
    score: float
    payload: dict[str, Any]


class VectorStore(ABC):
    @abstractmethod
    def recreate_collection(self, vector_size: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert(self, records: list[VectorRecord]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        raise NotImplementedError

    @abstractmethod
    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]:
        raise NotImplementedError


def payload_matches(payload: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for field, expected in filters.items():
        actual = payload.get(field)
        if isinstance(expected, dict):
            if "in" in expected and actual not in set(expected["in"]):
                return False
            if "lte" in expected and (actual is None or actual > expected["lte"]):
                return False
            if "gte" in expected and (actual is None or actual < expected["gte"]):
                return False
            if "range" in expected:
                low, high = expected["range"]
                if actual is None or actual < low or actual > high:
                    return False
        elif isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def cosine_similarity(a: list[float], b: list[float]) -> float:
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / denom


class InMemoryVectorStore(VectorStore):
    """Small local vector store used for tests and smoke indexing."""

    def __init__(self) -> None:
        self.records: dict[str, VectorRecord] = {}
        self.vector_size: int | None = None

    def recreate_collection(self, vector_size: int) -> None:
        self.records.clear()
        self.vector_size = vector_size

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self.records[record.point_id] = record

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        hits = []
        for record in self.records.values():
            if not payload_matches(record.payload, filters):
                continue
            score = cosine_similarity(vector, record.vector)
            if score_threshold is not None and score < score_threshold:
                continue
            hits.append(SearchHit(record.point_id, score, record.payload))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]:
        hits = [
            SearchHit(record.point_id, 0.0, record.payload)
            for record in self.records.values()
            if payload_matches(record.payload, filters)
        ]
        return hits[:limit]


class QdrantVectorStore(VectorStore):
    """Qdrant adapter with payload filtering support."""

    def __init__(
        self,
        collection_name: str = "legal_chunks",
        url: str = "http://localhost:6333",
        api_key: str | None = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
        except ImportError as exc:
            raise RuntimeError("qdrant-client is required for QdrantVectorStore.") from exc
        self.collection_name = collection_name
        self.client = QdrantClient(url=url, api_key=api_key)
        self.models = models

    def recreate_collection(self, vector_size: int) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=self.models.VectorParams(size=vector_size, distance=self.models.Distance.COSINE),
            hnsw_config=self.models.HnswConfigDiff(m=16, ef_construct=100),
        )
        for field, schema in {
            "legal_authority_rank": self.models.PayloadSchemaType.INTEGER,
            "validity_group": self.models.PayloadSchemaType.KEYWORD,
            "id_str": self.models.PayloadSchemaType.KEYWORD,
            "unit_type": self.models.PayloadSchemaType.KEYWORD,
            "loai_van_ban": self.models.PayloadSchemaType.KEYWORD,
            "legal_field_code": self.models.PayloadSchemaType.KEYWORD,
            "sector_code": self.models.PayloadSchemaType.KEYWORD,
            "scope_code": self.models.PayloadSchemaType.KEYWORD,
            "issuing_authority_code": self.models.PayloadSchemaType.KEYWORD,
            "issue_year": self.models.PayloadSchemaType.INTEGER,
            "parent_unit_id": self.models.PayloadSchemaType.KEYWORD,
        }.items():
            self.client.create_payload_index(self.collection_name, field_name=field, field_schema=schema)

    def upsert(self, records: list[VectorRecord]) -> None:
        points = [
            self.models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, record.point_id)), vector=record.vector, payload=record.payload)
            for record in records
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            query_filter=self._to_qdrant_filter(filters),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [SearchHit(str(hit.id), float(hit.score), dict(hit.payload or {})) for hit in hits]

    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=self._to_qdrant_filter(filters),
            limit=limit,
            with_vectors=False,
            with_payload=True,
        )
        return [SearchHit(str(point.id), 0.0, dict(point.payload or {})) for point in points]

    def _to_qdrant_filter(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        must = []
        for field, expected in filters.items():
            if isinstance(expected, dict):
                if "in" in expected:
                    must.append(self.models.FieldCondition(key=field, match=self.models.MatchAny(any=expected["in"])))
                elif "lte" in expected or "gte" in expected:
                    must.append(
                        self.models.FieldCondition(
                            key=field,
                            range=self.models.Range(gte=expected.get("gte"), lte=expected.get("lte")),
                        )
                    )
                elif "range" in expected:
                    low, high = expected["range"]
                    must.append(self.models.FieldCondition(key=field, range=self.models.Range(gte=low, lte=high)))
            elif isinstance(expected, (list, tuple, set)):
                must.append(self.models.FieldCondition(key=field, match=self.models.MatchAny(any=list(expected))))
            else:
                must.append(self.models.FieldCondition(key=field, match=self.models.MatchValue(value=expected)))
        return self.models.Filter(must=must)
