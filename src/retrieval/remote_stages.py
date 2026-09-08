"""HTTP adapters for remote Graph and Reranker services."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .dense_client import DEFAULT_USER_AGENT, DenseClient
from .graph_rrf_retriever import GraphRRFGlobalReranker
from .schema import RetrievedChunk
from .stores import SearchHit


class StageClient:
    def __init__(self, url: str, api_key: str, timeout: float = 60.0) -> None:
        if not url or not api_key:
            raise ValueError("Remote stage requires a service URL and API key.")
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, path: str, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.url + path,
            data=body,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Remote stage {path}: HTTP {exc.code}") from None
        except (URLError, TimeoutError):
            raise RuntimeError(f"Remote stage {path} unavailable or timed out") from None


class RemoteGraph:
    """Expand IDs remotely and retain returned chunks for pipeline hydration."""

    def __init__(self, client: StageClient) -> None:
        self.client = client
        self._local = threading.local()

    def expand(self, seed_ids, *, max_hop, max_context):
        data = self.client.request(
            "/graph",
            {
                "seed_chunk_ids": seed_ids,
                "max_hop": max_hop,
                "max_context": max_context,
            },
        )
        hits = data.get("hits")
        if (
            not isinstance(hits, list)
            or len(hits) > max_context
            or any(not isinstance(hit, dict) for hit in hits)
        ):
            raise ValueError("Malformed graph response.")
        self._local.chunks = DenseClient._parse_search_response(data).chunks
        return SimpleNamespace(
            ordered_context_chunks=[chunk.chunk_id for chunk in self._local.chunks]
        )

    def load_chunks(self, ids):
        wanted = set(ids)
        chunks = getattr(self._local, "chunks", ())
        return [chunk for chunk in chunks if chunk.chunk_id in wanted]


class RemoteCrossEncoder:
    def __init__(self, client: StageClient, expected_model: str = "") -> None:
        self.client = client
        self.expected_model = expected_model

    def predict(self, pairs):
        if not pairs:
            return []
        query = pairs[0][0]
        if any(other_query != query for other_query, _ in pairs):
            raise ValueError("Reranker pairs must contain one query.")
        data = self.client.request(
            "/rerank", {"query": query, "texts": [text for _, text in pairs]}
        )
        if self.expected_model and data.get("model") != self.expected_model:
            raise ValueError("Remote reranker model does not match configuration.")
        scores = data.get("scores")
        if not isinstance(scores, list) or len(scores) != len(pairs):
            raise ValueError("Malformed reranker response.")
        return scores


class SQLiteChunkLoader:
    """Read graph payloads from the existing Dense SQLite cache."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)

    def __call__(self, chunk_ids: Sequence[str]) -> list[RetrievedChunk]:
        ids = list(dict.fromkeys(chunk_ids))
        if not ids:
            return []
        chunks = []
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        try:
            for start in range(0, len(ids), 500):
                batch = ids[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT payload FROM payloads WHERE chunk_id IN ({placeholders})",
                    batch,
                )
                for (raw_payload,) in rows:
                    payload = json.loads(raw_payload)
                    chunks.append(
                        GraphRRFGlobalReranker._chunk_from_hit(
                            SearchHit(str(payload["chunk_id"]), 0.0, payload),
                            vector_score=0.0,
                            rerank_score=0.0,
                        )
                    )
        finally:
            connection.close()
        return chunks
