from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class BM25Hit:
    chunk_id: str
    bm25_score: float
    rank: int
    shard_id: int
    local_index: int = 0


@dataclass(frozen=True)
class BM25Result:
    qa_id: str
    bm25_hits: list[BM25Hit] = field(default_factory=list)


class BM25Client:
    """HTTP client for the remote BM25 retrieval service."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 300.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.base_url = (base_url or os.environ.get("BM25_SERVICE_URL") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else (os.environ.get("BM25_API_KEY") or "")
        self.timeout_seconds = float(timeout_seconds)
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        if not self.base_url:
            raise ValueError("BM25 service URL is required. Set BM25_SERVICE_URL or pass bm25_service_url.")

    def health_check(self) -> dict[str, Any]:
        return self._request("GET", "/healthz", None)

    def search(
        self,
        queries: list[dict[str, str]],
        *,
        top_k: int = 10,
        include_diagnostics: bool = False,
    ) -> dict[str, Any]:
        if not queries:
            raise ValueError("queries must be a non-empty list")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        payload = {
            "input": {
                "queries": queries,
                "bm25_top_k": top_k,
                "include_diagnostics": include_diagnostics,
            }
        }
        data = self._request("POST", "/bm25", payload)
        if "error" in data:
            raise RuntimeError(f"BM25 service error: {data['error']}")
        if "results" not in data:
            raise ValueError("Malformed BM25 response: missing 'results'")

        return {
            "index_version": data.get("index_version", "unknown"),
            "diagnostics": data.get("diagnostics"),
            "results": [self._parse_result(result) for result in data["results"]],
        }

    def search_single(self, qa_id: str, question: str, *, top_k: int = 10) -> BM25Result:
        response = self.search([{"qa_id": qa_id, "question": question}], top_k=top_k)
        return response["results"][0]

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
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
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.max_retries - 1:
                    detail = exc.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"BM25 service HTTP {exc.code}: {detail}") from exc
                last_error = exc
            except URLError as exc:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"BM25 service request failed: {exc.reason}") from exc
                last_error = exc
            time.sleep(self.retry_backoff_seconds * (2**attempt))

        raise RuntimeError(f"BM25 service request failed: {last_error}")

    @staticmethod
    def _parse_result(result: dict[str, Any]) -> BM25Result:
        hits = [
            BM25Hit(
                chunk_id=str(hit["chunk_id"]),
                bm25_score=float(hit["bm25_score"]),
                rank=int(hit["rank"]),
                shard_id=int(hit["shard_id"]),
                local_index=int(hit.get("local_index", 0)),
            )
            for hit in result.get("bm25_hits", [])
        ]
        return BM25Result(qa_id=str(result["qa_id"]), bm25_hits=hits)


def create_client_from_env() -> BM25Client:
    return BM25Client()
