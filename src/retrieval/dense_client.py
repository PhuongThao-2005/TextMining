from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from knowledge_graph.context_schema import GraphGuidedFilter

from .schema import RetrievalResult, RetrievedChunk, VALID_FILTER_PROFILES
from .stores import SearchHit, payload_matches


TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class DenseRemoteLatencyBreakdown:
    dense_latency_s: float = 0.0
    embedding_latency_s: float = 0.0
    vector_search_latency_s: float = 0.0
    payload_hydration_latency_s: float = 0.0
    total_latency_s: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "dense_latency_s": round(self.dense_latency_s, 4),
            "embedding_latency_s": round(self.embedding_latency_s, 4),
            "vector_search_latency_s": round(self.vector_search_latency_s, 4),
            "payload_hydration_latency_s": round(self.payload_hydration_latency_s, 4),
            "total_latency_s": round(self.total_latency_s, 4),
        }


class DenseClient:
    """HTTP client for the remote Dense retrieval service."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        expected_model: str | None = None,
        expected_index_version: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("DENSE_SERVICE_URL") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else (os.environ.get("DENSE_API_KEY") or "")
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.environ.get("DENSE_TIMEOUT_SECONDS", 30.0)
        self.timeout_seconds = float(raw_timeout)
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self.expected_model = (
            expected_model
            if expected_model is not None
            else os.environ.get("DENSE_EXPECTED_MODEL", "intfloat/multilingual-e5-large")
        )
        self.expected_index_version = (
            expected_index_version
            if expected_index_version is not None
            else os.environ.get("DENSE_EXPECTED_INDEX_VERSION", "")
        )
        self._identity_checked = False
        if not self.base_url:
            raise ValueError("Dense service URL is required. Set DENSE_SERVICE_URL or pass base_url.")

    def health_check(self) -> dict[str, Any]:
        return self._request("GET", "/healthz", None)

    def ready_check(self) -> dict[str, Any]:
        return self._request("GET", "/readyz", None)

    def version(self) -> dict[str, Any]:
        return self._request("GET", "/version", None)

    def search(
        self,
        query: str,
        *,
        top_k: int = 30,
        top_n: int = 10,
        filter_profile: str = "broad",
        score_threshold: float | None = None,
        expand_units: bool = False,
        request_id: str | None = None,
    ) -> RetrievalResult:
        self._validate_identity_once()
        payload = {
            "query": query,
            "top_k": top_k,
            "top_n": top_n,
            "filter_profile": filter_profile,
            "score_threshold": score_threshold,
            "expand_units": expand_units,
            "request_id": request_id or str(uuid.uuid4()),
        }
        data = self._request("POST", "/search", payload)
        return self._parse_search_response(data)

    def _validate_identity_once(self) -> None:
        if self._identity_checked:
            return
        version = self.version()
        model = str(version.get("embedding_model") or "")
        if self.expected_model and model and model != self.expected_model:
            raise RuntimeError(
                "Dense service model mismatch: "
                f"expected {self.expected_model!r}, got {model!r}."
            )
        index = str(version.get("index_version") or "")
        if self.expected_index_version and index and index != self.expected_index_version:
            raise RuntimeError(
                "Dense service index mismatch: "
                f"expected {self.expected_index_version!r}, got {index!r}."
            )
        self._identity_checked = True

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code not in TRANSIENT_HTTP_CODES or attempt == self.max_retries - 1:
                    detail = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"Dense service HTTP {exc.code}: {detail}") from exc
                last_error = exc
            except URLError as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Dense service request failed: {exc.reason}") from exc
                last_error = exc
            time.sleep(self.retry_backoff_seconds * (2**attempt))
        raise RuntimeError(f"Dense service request failed: {last_error}")

    @staticmethod
    def _parse_search_response(data: dict[str, Any]) -> RetrievalResult:
        if not isinstance(data, dict):
            raise ValueError("Malformed Dense response: root must be an object.")
        hits = data.get("hits")
        if not isinstance(hits, list):
            raise ValueError("Malformed Dense response: missing hits list.")
        chunks = [_chunk_from_mapping(hit) for hit in hits if isinstance(hit, dict)]
        latency = data.get("latency_ms") if isinstance(data.get("latency_ms"), dict) else {}
        return RetrievalResult(
            chunks=chunks,
            total_candidates=int(data.get("total_candidates") or len(chunks)),
            filter_profile_used=str(data.get("filter_profile_used") or "broad"),
            empty_filter_warning=bool(data.get("empty_filter_warning", False)),
            latency_ms={str(key): float(value) for key, value in latency.items() if isinstance(value, (int, float))},
        )


class DenseRemoteRetriever:
    """Remote Dense adapter that preserves the existing RetrievalResult shape."""

    def __init__(
        self,
        *,
        client: DenseClient,
        top_k: int = 30,
        top_n: int = 10,
        score_threshold: float | None = 0.3,
        expand_units: bool = False,
    ) -> None:
        self.client = client
        self.top_k = top_k
        self.top_n = top_n
        self.score_threshold = score_threshold
        self.expand_units = expand_units

    def retrieve(
        self,
        query: str,
        filter_profile: str = "current_law",
        id_str_filter: list[str] | None = None,
        graph_guided_filter: GraphGuidedFilter | None = None,
        top_k: int | None = None,
        top_n: int | None = None,
        score_threshold: float | None = None,
        expand_units: bool | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        result, _ = self.retrieve_with_latency(
            query,
            filter_profile=filter_profile,
            id_str_filter=id_str_filter,
            graph_guided_filter=graph_guided_filter,
            top_k=top_k,
            top_n=top_n,
            score_threshold=score_threshold,
            expand_units=expand_units,
            extra_filters=extra_filters,
        )
        return result

    def retrieve_with_latency(
        self,
        query: str,
        filter_profile: str = "current_law",
        id_str_filter: list[str] | None = None,
        graph_guided_filter: GraphGuidedFilter | None = None,
        top_k: int | None = None,
        top_n: int | None = None,
        score_threshold: float | None = None,
        expand_units: bool | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> tuple[RetrievalResult, DenseRemoteLatencyBreakdown]:
        if filter_profile not in VALID_FILTER_PROFILES:
            raise ValueError(f"Unknown filter_profile={filter_profile!r}")
        if graph_guided_filter is not None:
            id_str_filter = list(graph_guided_filter.id_strs)
            filter_profile = "graph_guided"
            if graph_guided_filter.empty_filter_warning:
                empty = RetrievalResult([], 0, filter_profile, empty_filter_warning=True)
                return empty, DenseRemoteLatencyBreakdown()
        if filter_profile == "graph_guided" and not id_str_filter:
            empty = RetrievalResult([], 0, filter_profile, empty_filter_warning=True)
            return empty, DenseRemoteLatencyBreakdown()

        started = time.perf_counter()
        result = self.client.search(
            query,
            top_k=top_k or self.top_k,
            top_n=top_n or self.top_n,
            filter_profile=filter_profile,
            score_threshold=self.score_threshold if score_threshold is None else score_threshold,
            expand_units=self.expand_units if expand_units is None else bool(expand_units),
        )
        if extra_filters or id_str_filter:
            filters = _build_filters(filter_profile, id_str_filter, extra_filters)
            result = RetrievalResult(
                [chunk for chunk in result.chunks if payload_matches(chunk.metadata, filters)],
                result.total_candidates,
                result.filter_profile_used,
                result.empty_filter_warning,
                result.latency_ms,
            )
        elapsed = time.perf_counter() - started
        latency = result.latency_ms
        total_s = float(latency.get("total", elapsed * 1000.0)) / 1000.0
        return result, DenseRemoteLatencyBreakdown(
            dense_latency_s=total_s,
            embedding_latency_s=float(latency.get("embedding", 0.0)) / 1000.0,
            vector_search_latency_s=float(latency.get("vector_search", 0.0)) / 1000.0,
            payload_hydration_latency_s=float(latency.get("payload_hydration", 0.0)) / 1000.0,
            total_latency_s=total_s,
        )

    def search_with_latency(self, query: str, *, top_k: int = 20) -> tuple[list[SearchHit], float]:
        started = time.perf_counter()
        result = self.retrieve(query, filter_profile="broad", top_k=top_k, top_n=top_k, expand_units=False)
        latency = float(result.latency_ms.get("total", (time.perf_counter() - started) * 1000.0)) / 1000.0
        return [
            SearchHit(point_id=chunk.chunk_id, score=chunk.vector_score, payload=chunk.metadata)
            for chunk in result.chunks
        ], latency


def _build_filters(
    filter_profile: str,
    id_str_filter: list[str] | None,
    extra_filters: dict[str, Any] | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if filter_profile == "current_law":
        filters["validity_group"] = {"in": ["active", "partial", "future"]}
    elif filter_profile == "broad":
        filters["validity_group"] = {"in": ["active", "partial", "future", "expired", "unknown"]}
    elif filter_profile == "historical":
        filters["validity_group"] = {"in": ["expired", "active", "partial"]}
    elif filter_profile == "graph_guided":
        filters["id_str"] = {"in": list(id_str_filter or [])}
    if extra_filters:
        filters.update(extra_filters)
    return filters


def _chunk_from_mapping(data: dict[str, Any]) -> RetrievedChunk:
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else dict(data)
    return RetrievedChunk(
        chunk_id=str(data.get("chunk_id") or metadata.get("chunk_id") or ""),
        chunk_text=str(data.get("chunk_text") or data.get("text") or metadata.get("chunk_text") or ""),
        citation_anchor=str(data.get("citation_anchor") or metadata.get("citation_anchor") or ""),
        citation_label=str(data.get("citation_label") or metadata.get("citation_label") or ""),
        title=str(data.get("title") or metadata.get("title") or ""),
        article_number=data.get("article_number") or metadata.get("article_number"),
        unit_type=str(data.get("unit_type") or metadata.get("unit_type") or ""),
        path=data.get("path") or metadata.get("path"),
        validity_group=str(data.get("validity_group") or metadata.get("validity_group") or "unknown"),
        legal_authority_rank=int(data.get("legal_authority_rank") or metadata.get("legal_authority_rank") or 99),
        vector_score=float(data.get("vector_score") or data.get("score") or metadata.get("vector_score") or 0.0),
        rerank_score=float(data.get("rerank_score") or data.get("score") or metadata.get("rerank_score") or 0.0),
        id_str=str(data.get("id_str") or data.get("document_id") or metadata.get("id_str") or ""),
        parent_unit_id=str(data.get("parent_unit_id") or data.get("provision_id") or metadata.get("parent_unit_id") or ""),
        metadata=metadata,
    )
