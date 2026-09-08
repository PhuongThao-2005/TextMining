"""Dense retriever without a local model or payload store."""
from __future__ import annotations

import time
import uuid
from typing import Mapping

import httpx
from pydantic import ValidationError

from .dense_protocol import Identity, SearchRequest, SearchResponse
from .schema import RetrievedChunk, RetrievalResult


class DenseServiceError(RuntimeError):
    pass


class DenseRemoteRetriever:
    def __init__(
        self, *, base_url: str, api_key: str | None = None,
        expected_model: str = "intfloat/multilingual-e5-large",
        expected_index_version: str = "chunk-metadata-faiss-v1",
        expected_corpus_version: str = "pre-processed-v1",
        expected_dimension: int = 1024, timeout_seconds: float = 30,
        max_retries: int = 2, top_k: int = 30, top_n: int = 10,
        score_threshold: float | None = 0.3, expand_units: bool = False,
        transport: httpx.BaseTransport | None = None,
    ):
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise DenseServiceError("Configure DENSE_SERVICE_URL with an HTTP(S) service URL.")
        if not 0 < timeout_seconds <= 90 or not 0 <= max_retries <= 3:
            raise ValueError("Dense timeout or retry limit is out of bounds.")
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout = httpx.Timeout(timeout_seconds, connect=min(5, timeout_seconds))
        self.max_retries = max_retries
        self.transport = transport
        self.expected = dict(
            embedding_model=expected_model, index_version=expected_index_version,
            corpus_version=expected_corpus_version, embedding_dimension=expected_dimension,
        )
        self.top_k, self.top_n = top_k, top_n
        self.score_threshold = 0.0 if score_threshold is None else score_threshold
        self.expand_units = expand_units
        self.last_diagnostics = {}

    def _request(self, method: str, path: str, payload: dict | None = None):
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
                    response = client.request(method, self.base_url + path, headers=self.headers, json=payload)
                if response.status_code in (401, 403):
                    raise DenseServiceError("Dense service authentication failed.")
                if response.status_code in (429, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(0.25 * 2 ** attempt)
                    continue
                if response.status_code == 503:
                    raise DenseServiceError("Dense service is not ready.")
                if response.status_code >= 400:
                    raise DenseServiceError(f"Dense service request failed (HTTP {response.status_code}).")
                return response.json()
            except httpx.RequestError:
                if attempt == self.max_retries:
                    raise DenseServiceError("Dense service unavailable or request timed out.") from None
                time.sleep(0.25 * 2 ** attempt)
            except (ValueError, httpx.InvalidURL):
                raise DenseServiceError("Dense service returned malformed JSON or has an invalid URL.") from None

    def _identity(self, payload) -> dict:
        try:
            identity = Identity.model_validate(payload)
        except ValidationError:
            raise DenseServiceError("Dense service returned an invalid identity.") from None
        for key, expected in self.expected.items():
            if getattr(identity, key) != expected:
                raise DenseServiceError(f"Incompatible dense service {key}.")
        return identity.model_dump()

    def check_ready(self) -> dict:
        identity = self._identity(self._request("GET", "/version"))
        ready = self._request("GET", "/readyz")
        if self._identity(ready) != identity:
            raise DenseServiceError("Dense service identity changed during readiness checks.")
        if ready.get("status") != "ready":
            raise DenseServiceError("Dense service is not ready.")
        return identity

    def retrieve(
        self, query: str, filter_profile="current_law", top_k=None, top_n=None,
        score_threshold=None, expand_units=None, **kwargs,
    ) -> RetrievalResult:
        if any(value is not None for value in kwargs.values()):
            raise DenseServiceError("Remote dense v1 does not support graph or custom filters.")
        request = SearchRequest(
            query=query, filter_profile=filter_profile,
            top_k=self.top_k if top_k is None else top_k,
            top_n=self.top_n if top_n is None else top_n,
            score_threshold=self.score_threshold if score_threshold is None else score_threshold,
            expand_units=self.expand_units if expand_units is None else expand_units,
            request_id=uuid.uuid4().hex,
        )
        payload = self._request("POST", "/search", request.model_dump())
        self._identity(payload)
        try:
            result = SearchResponse.model_validate(payload)
        except ValidationError:
            raise DenseServiceError("Dense service returned malformed search results.") from None
        if (
            result.request_id != request.request_id or result.filter_profile_used != filter_profile
            or len(result.hits) > request.top_n or result.total_candidates > request.top_k
            or len({hit.chunk_id for hit in result.hits}) != len(result.hits)
        ):
            raise DenseServiceError("Dense service response does not match the request.")
        self.last_diagnostics = result.model_dump(exclude={"hits"})
        return RetrievalResult(
            [RetrievedChunk(**hit.model_dump()) for hit in result.hits],
            result.total_candidates, result.filter_profile_used, result.empty_filter_warning,
        )


def client_from_config(dense: Mapping, environ: Mapping, *, corpus_version="pre-processed-v1", top_n=10):
    return DenseRemoteRetriever(
        **connection_options(dense, environ, corpus_version=corpus_version),
        top_k=max(top_n * 3, top_n), top_n=top_n,
        score_threshold=dense.get("score_threshold", 0.3), expand_units=bool(dense.get("expand_units", False)))


def connection_options(dense: Mapping, environ: Mapping, *, corpus_version: str) -> dict:
    """One connection configuration shared by UI preflight and runtime."""
    return dict(
        base_url=environ.get(dense.get("service_url_env", "DENSE_SERVICE_URL"), ""),
        api_key=environ.get(dense.get("api_key_env", "DENSE_API_KEY")),
        expected_model=dense.get("model", "intfloat/multilingual-e5-large"),
        expected_index_version=dense.get("index_version", "chunk-metadata-faiss-v1"),
        expected_corpus_version=corpus_version,
        expected_dimension=int(dense.get("embedding_dimension", 1024)),
        timeout_seconds=float(environ.get("DENSE_TIMEOUT_SECONDS") or dense.get("timeout_seconds", 30)))
