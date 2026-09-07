"""HTTP BM25 service for Dense-Sparse production retrieval.

Run from the repository root:

    python -m uvicorn services.bm25_service:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retrieval.sparse_retriever import BM25SparseRetriever  # noqa: E402


app = FastAPI(title="LexVN BM25 Service", version="1.0.0")
_retriever: BM25SparseRetriever | None = None


def _resolve_index_dir() -> Path:
    configured = os.environ.get("BM25_INDEX_DIR", "data/sparse_index")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_retriever() -> BM25SparseRetriever:
    global _retriever
    if _retriever is None:
        _retriever = BM25SparseRetriever.load(_resolve_index_dir())
    return _retriever


def _require_auth(request: Request) -> None:
    expected = os.environ.get("BM25_API_KEY", "").strip()
    if not expected:
        return
    header = request.headers.get("authorization", "")
    if header != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid BM25 API key.")


@app.get("/healthz")
def healthz(request: Request) -> dict[str, Any]:
    _require_auth(request)
    retriever = _load_retriever()
    return {
        "status": "ok",
        "index_dir": str(_resolve_index_dir()),
        "index_version": os.environ.get("BM25_INDEX_VERSION", "local-bm25"),
        "total_documents": retriever.total_documents,
    }


@app.post("/bm25")
async def bm25(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    _require_auth(request)
    body = payload.get("input") if isinstance(payload.get("input"), dict) else payload
    queries = body.get("queries") if isinstance(body, dict) else None
    if not isinstance(queries, list) or not queries:
        raise HTTPException(status_code=400, detail="input.queries must be a non-empty list.")
    try:
        top_k = int(body.get("bm25_top_k", body.get("top_k", 10)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="bm25_top_k must be an integer.") from exc
    if top_k < 1:
        raise HTTPException(status_code=400, detail="bm25_top_k must be >= 1.")

    retriever = _load_retriever()
    results: list[dict[str, Any]] = []
    for index, query in enumerate(queries, start=1):
        if not isinstance(query, dict):
            raise HTTPException(status_code=400, detail="Each query must be an object.")
        qa_id = str(query.get("qa_id") or f"q{index}")
        question = str(query.get("question") or query.get("query") or "").strip()
        if not question:
            results.append({"qa_id": qa_id, "bm25_hits": []})
            continue
        hits = retriever.search(question, top_k=top_k)
        results.append({
            "qa_id": qa_id,
            "bm25_hits": [
                {
                    "chunk_id": str(hit.payload.get("chunk_id") or hit.point_id),
                    "bm25_score": float(hit.score),
                    "rank": rank,
                    "shard_id": 0,
                    "local_index": rank - 1,
                }
                for rank, hit in enumerate(hits, start=1)
            ],
        })

    response: dict[str, Any] = {
        "index_version": os.environ.get("BM25_INDEX_VERSION", "local-bm25"),
        "results": results,
    }
    if body.get("include_diagnostics"):
        response["diagnostics"] = {
            "index_dir": str(_resolve_index_dir()),
            "query_count": len(queries),
            "top_k": top_k,
            "total_documents": retriever.total_documents,
        }
    return response

