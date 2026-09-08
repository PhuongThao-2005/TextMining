"""HTTP Dense retrieval service for RunPod/VPS deployment.

Run from the repository root:

    python -m uvicorn services.dense_service:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retrieval.config import VectorIndexConfig  # noqa: E402
from retrieval.embeddings import SentenceTransformerEmbedder  # noqa: E402
from retrieval.retriever import VectorRetriever  # noqa: E402
from retrieval.schema import RetrievedChunk, VALID_FILTER_PROFILES  # noqa: E402
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore  # noqa: E402


SERVICE_VERSION = "dense-retrieval-v1"
DEFAULT_MODEL = "intfloat/multilingual-e5-large"
MANIFEST_NAMES = ("index_manifest.json", "manifest.json", "meta.json")


@dataclass(frozen=True)
class DenseServiceState:
    retriever: VectorRetriever
    manifest: dict[str, Any]
    index_dir: Path
    embedding_model: str
    embedding_dimension: int
    index_version: str | None
    corpus_version: str | None
    vector_count: int
    payload_count: int | None


app = FastAPI(title="LexVN Dense Retrieval Service", version=SERVICE_VERSION)
_state: DenseServiceState | None = None
_startup_error: str | None = None


@app.on_event("startup")
def startup() -> None:
    global _state, _startup_error
    try:
        _state = _load_state()
        _startup_error = None
    except Exception as exc:
        _startup_error = _safe_error(exc)
        raise


def _load_state() -> DenseServiceState:
    index_dir = _resolve_path(os.environ.get("DENSE_INDEX_DIR") or "data/chunk metadata")
    manifest_path = _resolve_manifest_path(index_dir)
    manifest = _read_manifest(manifest_path)

    configured_model = os.environ.get("DENSE_MODEL") or os.environ.get("DENSE_EXPECTED_MODEL") or DEFAULT_MODEL
    expected_index = os.environ.get("DENSE_EXPECTED_INDEX_VERSION") or os.environ.get("DENSE_INDEX_VERSION") or ""
    expected_corpus = os.environ.get("DENSE_EXPECTED_CORPUS_VERSION") or ""

    manifest_model = str(manifest.get("embedding_model") or manifest.get("embedding_identity") or "")
    if manifest_model and manifest_model != configured_model:
        raise RuntimeError(f"Dense model mismatch: configured={configured_model}, manifest={manifest_model}.")

    manifest_index = _optional_text(manifest.get("index_version"))
    if expected_index and manifest_index and expected_index != manifest_index:
        raise RuntimeError(f"Dense index mismatch: configured={expected_index}, manifest={manifest_index}.")

    manifest_corpus = _optional_text(manifest.get("corpus_version") or manifest.get("corpus_identity"))
    if expected_corpus and manifest_corpus and expected_corpus != manifest_corpus:
        raise RuntimeError(f"Dense corpus mismatch: configured={expected_corpus}, manifest={manifest_corpus}.")

    store = SQLitePayloadFaissVectorStore.load(index_dir)
    embedder = SentenceTransformerEmbedder(
        configured_model,
        query_prefix=os.environ.get("DENSE_QUERY_PREFIX", "query: "),
        passage_prefix=os.environ.get("DENSE_PASSAGE_PREFIX", "passage: "),
        device=os.environ.get("DENSE_DEVICE") or None,
    )
    if embedder.dimension != store.dimension:
        raise RuntimeError(
            "Embedding/index dimension mismatch: "
            f"embedder={embedder.dimension}, faiss={store.dimension}."
        )
    manifest_dimension = _optional_int(manifest.get("embedding_dimension") or manifest.get("dimension"))
    if manifest_dimension and manifest_dimension != embedder.dimension:
        raise RuntimeError(
            "Manifest embedding dimension mismatch: "
            f"manifest={manifest_dimension}, runtime={embedder.dimension}."
        )

    vector_count = int(store.total_vectors)
    payload_count = _payload_count(store)
    manifest_vector_count = _optional_int(manifest.get("vector_count") or manifest.get("index_vector_count"))
    manifest_payload_count = _optional_int(manifest.get("payload_count"))
    if manifest_vector_count is not None and manifest_vector_count != vector_count:
        raise RuntimeError(f"Manifest vector count mismatch: manifest={manifest_vector_count}, faiss={vector_count}.")
    if payload_count is not None and vector_count != payload_count:
        raise RuntimeError(f"FAISS vector count does not match payload count: faiss={vector_count}, payloads={payload_count}.")
    if manifest_payload_count is not None and payload_count is not None and manifest_payload_count != payload_count:
        raise RuntimeError(f"Manifest payload count mismatch: manifest={manifest_payload_count}, payloads={payload_count}.")

    _validate_citation_payloads(store)
    config = VectorIndexConfig(
        embedding_model=configured_model,
        top_k=_env_int("DENSE_TOP_K", 30),
        top_n=_env_int("DENSE_TOP_N", 10),
        score_threshold=_env_optional_float("DENSE_SCORE_THRESHOLD", 0.3),
        expand_units=_env_bool("DENSE_EXPAND_UNITS", False),
    )
    retriever = VectorRetriever(config=config, embedder=embedder, store=store)
    return DenseServiceState(
        retriever=retriever,
        manifest=manifest,
        index_dir=index_dir,
        embedding_model=configured_model,
        embedding_dimension=embedder.dimension,
        index_version=manifest_index,
        corpus_version=manifest_corpus,
        vector_count=vector_count,
        payload_count=payload_count,
    )


@app.get("/healthz")
def healthz(request: Request) -> dict[str, Any]:
    _require_auth(request)
    return {"status": "ok", "service": "dense-retrieval", "service_version": SERVICE_VERSION}


@app.get("/readyz")
def readyz(request: Request) -> dict[str, Any]:
    _require_auth(request)
    state = _require_ready()
    return {"status": "ready", **_version_payload(state)}


@app.get("/version")
def version(request: Request) -> dict[str, Any]:
    _require_auth(request)
    state = _require_ready()
    return _version_payload(state)


@app.post("/search")
async def search(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    _require_auth(request)
    state = _require_ready()
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must be a non-empty string.")
    if len(query) > _env_int("DENSE_MAX_QUERY_CHARS", 4000):
        raise HTTPException(status_code=400, detail="query is too long.")
    filter_profile = str(payload.get("filter_profile") or "broad")
    if filter_profile not in VALID_FILTER_PROFILES - {"graph_guided"}:
        raise HTTPException(status_code=400, detail="filter_profile must be current_law, broad, or historical.")
    top_k = _bounded_int(payload.get("top_k", 30), "top_k", minimum=1, maximum=_env_int("DENSE_MAX_TOP_K", 100))
    top_n = _bounded_int(payload.get("top_n", 10), "top_n", minimum=1, maximum=top_k)
    score_threshold = _optional_request_float(payload.get("score_threshold"))
    expand_units = bool(payload.get("expand_units", False))

    started = time.perf_counter()
    result, breakdown = state.retriever.retrieve_with_latency(
        query,
        filter_profile=filter_profile,
        top_k=top_k,
        top_n=top_n,
        score_threshold=score_threshold,
        expand_units=expand_units,
    )
    total_ms = (time.perf_counter() - started) * 1000.0
    latency_ms = {
        "embedding": breakdown.embedding_latency_s * 1000.0,
        "vector_search": breakdown.vector_search_latency_s * 1000.0,
        "payload_hydration": breakdown.payload_hydration_latency_s * 1000.0,
        "total": total_ms,
    }
    return {
        "request_id": payload.get("request_id"),
        **_version_payload(state),
        "filter_profile_used": result.filter_profile_used,
        "total_candidates": result.total_candidates,
        "empty_filter_warning": result.empty_filter_warning,
        "latency_ms": latency_ms,
        "hits": [_chunk_to_dict(chunk, rank) for rank, chunk in enumerate(result.chunks, start=1)],
    }


def _version_payload(state: DenseServiceState) -> dict[str, Any]:
    return {
        "service_version": SERVICE_VERSION,
        "embedding_model": state.embedding_model,
        "embedding_dimension": state.embedding_dimension,
        "index_version": state.index_version,
        "corpus_version": state.corpus_version,
        "vector_count": state.vector_count,
        "payload_count": state.payload_count,
        "index_dir": str(state.index_dir),
    }


def _chunk_to_dict(chunk: RetrievedChunk, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "chunk_text": chunk.chunk_text,
        "citation_anchor": chunk.citation_anchor,
        "citation_label": chunk.citation_label,
        "title": chunk.title,
        "article_number": chunk.article_number,
        "unit_type": chunk.unit_type,
        "path": chunk.path,
        "validity_group": chunk.validity_group,
        "legal_authority_rank": chunk.legal_authority_rank,
        "vector_score": chunk.vector_score,
        "rerank_score": chunk.rerank_score,
        "id_str": chunk.id_str,
        "parent_unit_id": chunk.parent_unit_id,
        "metadata": chunk.metadata,
    }


def _require_ready() -> DenseServiceState:
    if _state is None:
        detail = "Dense service is not ready."
        if _startup_error:
            detail = f"{detail} Startup error: {_startup_error}"
        raise HTTPException(status_code=503, detail=detail)
    return _state


def _require_auth(request: Request) -> None:
    expected = os.environ.get("DENSE_API_KEY", "").strip()
    if not expected:
        return
    header = request.headers.get("authorization", "")
    if header != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid Dense API key.")


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _resolve_manifest_path(index_dir: Path) -> Path:
    explicit = os.environ.get("DENSE_MANIFEST_PATH")
    if explicit:
        path = _resolve_path(explicit)
        if path.is_file():
            return path
        raise FileNotFoundError(f"Dense manifest not found at {path}.")
    for name in MANIFEST_NAMES:
        candidate = index_dir / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Dense manifest not found in {index_dir}.")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Dense manifest is unreadable: {path.name}.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Dense manifest root must be a JSON object.")
    return payload


def _payload_count(store: SQLitePayloadFaissVectorStore) -> int | None:
    try:
        row = store.conn.execute("SELECT COUNT(*) FROM payloads").fetchone()
        return int(row[0]) if row is not None else None
    except Exception:
        return None


def _validate_citation_payloads(store: SQLitePayloadFaissVectorStore) -> None:
    hits = store.scroll({}, limit=_env_int("DENSE_CITATION_SAMPLE_LIMIT", 8))
    for hit in hits:
        payload = hit.payload
        missing = [name for name in ("chunk_id", "chunk_text") if not payload.get(name)]
        has_locator = any(payload.get(name) for name in ("citation_anchor", "citation_label", "title", "article_number"))
        if missing or not has_locator:
            chunk_id = payload.get("chunk_id") or hit.point_id
            raise RuntimeError(
                "Dense payload is missing citation metadata for "
                f"chunk {chunk_id!r}: missing={missing}, has_locator={has_locator}."
            )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_float(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    if raw.strip().lower() in {"none", "null"}:
        return None
    return float(raw)


def _bounded_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} must be an integer.") from exc
    if result < minimum or result > maximum:
        raise HTTPException(status_code=400, detail=f"{label} must be between {minimum} and {maximum}.")
    return result


def _optional_request_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="score_threshold must be a number or null.") from exc


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for name in ("DENSE_API_KEY", "BM25_API_KEY", "LLM_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, "***")
    return text
