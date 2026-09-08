"""HTTP BM25 service for Dense-Sparse production retrieval.

Run from the repository root:

    python -m uvicorn services.bm25_service:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retrieval.sparse_retriever import BM25SparseRetriever  # noqa: E402


app = FastAPI(title="LexVN BM25 Service", version="1.0.0")
_index: "BM25ServiceIndex | None" = None
_SHARD_RE = re.compile(r"^shard_(\d+)$")


@dataclass(frozen=True)
class BM25ShardSpec:
    name: str
    shard_id: int
    path: Path


@dataclass(frozen=True)
class LoadedBM25Shard:
    spec: BM25ShardSpec
    retriever: BM25SparseRetriever


@dataclass(frozen=True)
class ShardedSearchHit:
    hit: Any
    shard: LoadedBM25Shard
    shard_rank: int


@dataclass(frozen=True)
class BM25ServiceIndex:
    index_dir: Path
    shards: tuple[LoadedBM25Shard, ...]

    @property
    def total_documents(self) -> int:
        return sum(int(shard.retriever.total_documents) for shard in self.shards)

    @property
    def shard_count(self) -> int:
        return len(self.shards)

    @property
    def shard_names(self) -> tuple[str, ...]:
        return tuple(shard.spec.name for shard in self.shards)


def _resolve_index_dir() -> Path:
    configured = os.environ.get("BM25_INDEX_DIR", "data/sparse_index")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_index() -> BM25ServiceIndex:
    global _index
    if _index is None:
        index_dir = _resolve_index_dir()
        shards = tuple(
            LoadedBM25Shard(spec=spec, retriever=BM25SparseRetriever.load(spec.path))
            for spec in _discover_shard_specs(index_dir)
        )
        _index = BM25ServiceIndex(index_dir=index_dir, shards=shards)
    return _index


def _discover_shard_specs(index_dir: Path) -> tuple[BM25ShardSpec, ...]:
    if not index_dir.exists():
        raise FileNotFoundError(f"BM25_INDEX_DIR does not exist: {index_dir}")
    if not index_dir.is_dir():
        raise NotADirectoryError(f"BM25_INDEX_DIR must be a directory: {index_dir}")

    if _has_bm25_files(index_dir):
        return (BM25ShardSpec(name=index_dir.name or "single", shard_id=0, path=index_dir),)

    shard_dirs = sorted(
        (path for path in index_dir.iterdir() if path.is_dir() and path.name.startswith("shard_")),
        key=lambda path: _shard_sort_key(path.name),
    )
    if not shard_dirs:
        raise FileNotFoundError(
            "BM25_INDEX_DIR must contain bm25_index.pkl/bm25_metadata.pkl directly "
            "or at least one shard_* child directory."
        )

    specs: list[BM25ShardSpec] = []
    for fallback_id, shard_dir in enumerate(shard_dirs):
        missing = _missing_bm25_files(shard_dir)
        if missing:
            raise FileNotFoundError(
                f"BM25 shard {shard_dir.name!r} is missing required artifact(s): "
                f"{', '.join(missing)}."
            )
        specs.append(
            BM25ShardSpec(
                name=shard_dir.name,
                shard_id=_parse_shard_id(shard_dir.name, fallback_id),
                path=shard_dir,
            )
        )
    return tuple(specs)


def _has_bm25_files(path: Path) -> bool:
    return not _missing_bm25_files(path)


def _missing_bm25_files(path: Path) -> list[str]:
    return [
        name
        for name in ("bm25_index.pkl", "bm25_metadata.pkl")
        if not (path / name).is_file()
    ]


def _shard_sort_key(name: str) -> tuple[int, int | str]:
    match = _SHARD_RE.match(name)
    if match:
        return (0, int(match.group(1)))
    return (1, name)


def _parse_shard_id(name: str, fallback: int) -> int:
    match = _SHARD_RE.match(name)
    return int(match.group(1)) if match else fallback


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
    index = _load_index()
    return {
        "status": "ok",
        "index_dir": str(_resolve_index_dir()),
        "index_version": os.environ.get("BM25_INDEX_VERSION", "local-bm25"),
        "shard_count": index.shard_count,
        "total_documents": index.total_documents,
    }


@app.post("/bm25")
async def bm25(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    _require_auth(request)
    body = payload.get("input") if isinstance(payload.get("input"), dict) else payload
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be an object.")
    queries = body.get("queries") if isinstance(body, dict) else None
    if not isinstance(queries, list) or not queries:
        raise HTTPException(status_code=400, detail="input.queries must be a non-empty list.")
    try:
        top_k = int(body.get("bm25_top_k", body.get("top_k", 10)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="bm25_top_k must be an integer.") from exc
    if top_k < 1:
        raise HTTPException(status_code=400, detail="bm25_top_k must be >= 1.")

    service_index = _load_index()
    results: list[dict[str, Any]] = []
    include_payloads = bool(body.get("include_payloads"))
    for query_index, query in enumerate(queries, start=1):
        if not isinstance(query, dict):
            raise HTTPException(status_code=400, detail="Each query must be an object.")
        qa_id = str(query.get("qa_id") or f"q{query_index}")
        question = str(query.get("question") or query.get("query") or "").strip()
        if not question:
            results.append({"qa_id": qa_id, "bm25_hits": []})
            continue
        hits = _search_shards(service_index, question, top_k=top_k)
        results.append({
            "qa_id": qa_id,
            "bm25_hits": [
                _bm25_hit_to_dict(hit, rank, include_payloads=include_payloads)
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
            "shard_count": service_index.shard_count,
            "shard_names": list(service_index.shard_names),
            "total_documents": service_index.total_documents,
        }
    return response


def _search_shards(index: BM25ServiceIndex, question: str, *, top_k: int) -> list[ShardedSearchHit]:
    best_by_chunk_id: dict[str, ShardedSearchHit] = {}
    for shard in index.shards:
        for shard_rank, hit in enumerate(shard.retriever.search(question, top_k=top_k), start=1):
            chunk_id = _chunk_id(hit)
            current = best_by_chunk_id.get(chunk_id)
            candidate = ShardedSearchHit(hit=hit, shard=shard, shard_rank=shard_rank)
            if current is None or float(hit.score) > float(current.hit.score):
                best_by_chunk_id[chunk_id] = candidate
    return sorted(
        best_by_chunk_id.values(),
        key=lambda item: (-float(item.hit.score), _chunk_id(item.hit), item.shard.spec.name),
    )[:top_k]


def _chunk_id(hit: Any) -> str:
    payload = dict(getattr(hit, "payload", {}) or {})
    return str(payload.get("chunk_id") or getattr(hit, "point_id", ""))


def _bm25_hit_to_dict(item: ShardedSearchHit, rank: int, *, include_payloads: bool) -> dict[str, Any]:
    hit = item.hit
    payload = dict(getattr(hit, "payload", {}) or {})
    data = {
        "chunk_id": _chunk_id(hit),
        "bm25_score": float(hit.score),
        "rank": rank,
        "shard_id": item.shard.spec.shard_id,
        "shard_name": item.shard.spec.name,
        "shard_rank": item.shard_rank,
    }
    if include_payloads:
        data["payload"] = payload
    return data
