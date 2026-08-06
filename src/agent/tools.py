"""Approved read-only tools for the bounded planner."""
from __future__ import annotations

import re
import time
from typing import Any, Sequence

from .contracts import TOOL_CONTRACT_VERSION, ToolRequest, ToolResult


_SECRET = re.compile(r"(?i)(api[_-]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _sanitize(message: object, sensitive_values: Sequence[str]) -> str:
    text = str(message)
    for value in sensitive_values:
        if value:
            text = text.replace(value, "***")
    return _BEARER.sub("Bearer ***", _SECRET.sub(r"\1\2***", text))[:500]


class RetrievalTool:
    """Typed, read-only wrapper around the repository retriever interface."""

    name = "retrieve"
    contract_version = TOOL_CONTRACT_VERSION

    def __init__(self, retriever: Any, *, sensitive_values: Sequence[str] = ()) -> None:
        self._retriever = retriever
        self._sensitive_values = tuple(sensitive_values)

    def execute(self, request: ToolRequest) -> ToolResult:
        if not isinstance(request, ToolRequest):
            return ToolResult(status="failed", error_type="ValidationError", error_message="Invalid tool request type.")
        if not isinstance(request.query, str) or not request.query.strip() or request.top_k <= 0:
            return ToolResult(status="failed", error_type="ValidationError", error_message="query must be non-empty and top_k positive.")
        started = time.perf_counter()
        try:
            if hasattr(self._retriever, "retrieve_with_latency"):
                result, breakdown = self._retriever.retrieve_with_latency(
                    request.query.strip(),
                    top_k=max(request.top_k * 3, request.top_k),
                    top_n=request.top_k,
                    filter_profile=request.filter_profile,
                )
                stages = _latency_stages(breakdown, self._retriever)
            else:
                result = self._retriever.retrieve(
                    request.query.strip(), filter_profile=request.filter_profile, top_n=request.top_k
                )
                stages = {"dense_retrieval": _elapsed_ms(started)}
            chunks = getattr(result, "chunks", None)
            if chunks is None:
                return ToolResult(
                    status="failed", latency_ms=_elapsed_ms(started), stage_latencies_ms=stages,
                    error_type="MalformedToolResult", error_message="Retriever result has no chunks field."
                )
            items = tuple(chunks)
            return ToolResult(
                status="completed" if items else "empty",
                items=items,
                latency_ms=_elapsed_ms(started),
                stage_latencies_ms=stages,
            )
        except Exception as exc:
            return ToolResult(
                status="failed", latency_ms=_elapsed_ms(started), error_type=type(exc).__name__,
                error_message=_sanitize(exc, self._sensitive_values),
            )


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 6)


def _latency_stages(breakdown: Any, retriever: Any) -> dict[str, float | None]:
    raw = vars(breakdown) if hasattr(breakdown, "__dict__") else breakdown.to_dict()
    result: dict[str, float | None] = {}
    for source, target in {
        "dense_latency_s": "dense_retrieval", "sparse_latency_s": "sparse_retrieval",
        "graph_latency_s": "graph_traversal", "graph_traversal_latency_s": "graph_traversal",
        "fusion_latency_s": "fusion", "cross_encoder_latency_s": "reranker",
        "rerank_latency_s": "reranker",
    }.items():
        if target == "reranker" and hasattr(retriever, "use_cross_encoder") and not retriever.use_cross_encoder:
            continue
        if raw.get(source) is not None:
            result[target] = float(raw[source]) * 1000.0
    return result
