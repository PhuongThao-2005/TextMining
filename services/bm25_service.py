"""HTTP BM25 service for Dense-Sparse production retrieval.

Run from the repository root:

    python -m uvicorn services.bm25_service:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import gc
import json
import logging
import os
import pickle
import re
import sqlite3
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from fastapi import FastAPI, HTTPException, Request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from retrieval.sparse_retriever import _get_tokenizer  # noqa: E402
from retrieval.stores import payload_matches  # noqa: E402


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _load_index()
    yield


app = FastAPI(title="LexVN BM25 Service", version="1.0.0", lifespan=_lifespan)
_index: "BM25ServiceIndex | None" = None
_SHARD_RE = re.compile(r"^shard_(\d+)$")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BM25ShardSpec:
    name: str
    shard_id: int
    path: Path
    document_count: int | None = None


@dataclass(frozen=True)
class ResidentBM25Shard:
    spec: BM25ShardSpec
    bm25: Any
    chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class LightweightBM25Candidate:
    spec: BM25ShardSpec
    local_index: int
    score: float
    shard_rank: int


@dataclass(frozen=True)
class ShardedSearchHit:
    chunk_id: str
    score: float
    spec: BM25ShardSpec
    shard_rank: int
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryDiagnostics:
    qa_id: str
    total_seconds: float
    per_shard_search_seconds: dict[str, float]
    chunk_id_lookup_seconds: float
    payload_hydration_seconds: float
    rss_bytes: int | None
    filter_profile_used: str = "broad"
    pre_filter_candidate_count: int = 0
    post_filter_candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "qa_id": self.qa_id,
            "filter_profile_used": self.filter_profile_used,
            "total_seconds": round(self.total_seconds, 4),
            "per_shard_search_seconds": {
                name: round(seconds, 4)
                for name, seconds in self.per_shard_search_seconds.items()
            },
            "chunk_id_lookup_seconds": round(self.chunk_id_lookup_seconds, 4),
            "payload_hydration_seconds": round(self.payload_hydration_seconds, 4),
            "metadata_hydration_seconds": round(self.payload_hydration_seconds, 4),
            "pre_filter_candidate_count": self.pre_filter_candidate_count,
            "post_filter_candidate_count": self.post_filter_candidate_count,
            "rss_bytes": self.rss_bytes,
        }


@dataclass(frozen=True)
class SearchOutcome:
    hits: list[ShardedSearchHit]
    diagnostics: QueryDiagnostics


@dataclass(frozen=True)
class HydrationOutcome:
    hits: list[ShardedSearchHit]
    chunk_id_lookup_seconds: float
    payload_hydration_seconds: float
    pre_filter_candidate_count: int
    post_filter_candidate_count: int


@dataclass(frozen=True)
class BM25ServiceIndex:
    index_dir: Path
    shards: tuple[ResidentBM25Shard, ...]
    preload_seconds: float
    rss_after_preload_bytes: int | None
    tokenizer: Any
    payload_lookup: "SQLitePayloadLookup | None"
    search_workers: int

    @property
    def total_documents(self) -> int | None:
        counts = [shard.spec.document_count for shard in self.shards]
        if any(count is None for count in counts):
            return None
        return sum(int(count) for count in counts if count is not None)

    @property
    def shard_count(self) -> int:
        return len(self.shards)

    @property
    def shard_names(self) -> tuple[str, ...]:
        return tuple(shard.spec.name for shard in self.shards)

    @property
    def resident_index_count(self) -> int:
        return len(self.shards)


class SQLitePayloadLookup:
    """Read-only payload lookup backed by the Dense payload cache schema."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute("PRAGMA query_only = ON")
        self._validate_schema()

    def load_payloads(self, chunk_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = list(dict.fromkeys(str(chunk_id) for chunk_id in chunk_ids if chunk_id))
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            rows = self.conn.execute(
                f"SELECT chunk_id, payload FROM payloads WHERE chunk_id IN ({placeholders})",
                ids,
            ).fetchall()
        payloads: dict[str, dict[str, Any]] = {}
        for chunk_id, payload_text in rows:
            if chunk_id is None:
                continue
            payloads[str(chunk_id)] = json.loads(payload_text)
        return payloads

    def _validate_schema(self) -> None:
        columns = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(payloads)").fetchall()
        }
        required = {"chunk_id", "payload"}
        missing = required - columns
        if missing:
            raise RuntimeError(
                f"Payload SQLite cache {self.path} is missing column(s): {', '.join(sorted(missing))}."
            )


def _resolve_index_dir() -> Path:
    configured = os.environ.get("BM25_INDEX_DIR", "data/sparse_index")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_index() -> BM25ServiceIndex:
    global _index
    if _index is not None:
        return _index

    started = time.perf_counter()
    index_dir = _resolve_index_dir()
    specs = _discover_shard_specs(index_dir)
    _log_memory("bm25_startup_preload_start", shard_count=len(specs))
    tokenizer = _get_tokenizer()
    chunk_id_maps = {
        spec.name: _load_or_create_chunk_id_map(spec)
        for spec in specs
    }
    payload_lookup = _open_payload_lookup(index_dir)
    search_workers = _configured_search_workers(len(specs))
    shards = tuple(
        ResidentBM25Shard(
            spec=spec,
            bm25=_load_bm25_index(spec.path),
            chunk_ids=chunk_id_maps[spec.name],
        )
        for spec in specs
    )
    preload_seconds = time.perf_counter() - started
    rss_after_preload = _current_rss_bytes()
    _index = BM25ServiceIndex(
        index_dir=index_dir,
        shards=shards,
        preload_seconds=preload_seconds,
        rss_after_preload_bytes=rss_after_preload,
        tokenizer=tokenizer,
        payload_lookup=payload_lookup,
        search_workers=search_workers,
    )
    _log_memory(
        "bm25_startup_preload_done",
        shard_count=_index.shard_count,
        resident_index_count=_index.resident_index_count,
        preload_seconds=round(preload_seconds, 4),
        payload_lookup_path=str(payload_lookup.path) if payload_lookup else None,
        search_workers=search_workers,
    )
    return _index


def _discover_shard_specs(index_dir: Path) -> tuple[BM25ShardSpec, ...]:
    if not index_dir.exists():
        raise FileNotFoundError(f"BM25_INDEX_DIR does not exist: {index_dir}")
    if not index_dir.is_dir():
        raise NotADirectoryError(f"BM25_INDEX_DIR must be a directory: {index_dir}")

    if _has_bm25_files(index_dir):
        return (
            BM25ShardSpec(
                name=index_dir.name or "single",
                shard_id=0,
                path=index_dir,
                document_count=_manifest_document_count(index_dir),
            ),
        )

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
                document_count=_manifest_document_count(shard_dir),
            )
        )
    return tuple(specs)


def _load_bm25_index(index_dir: Path) -> Any:
    bm25_path = index_dir / "bm25_index.pkl"
    if not bm25_path.exists():
        raise FileNotFoundError(f"BM25 index not found at {bm25_path}")
    logger.info("Loading resident BM25 index object from %s", bm25_path)
    with bm25_path.open("rb") as handle:
        return pickle.load(handle)


def _load_metadata(index_dir: Path) -> dict[str, Any]:
    meta_path = index_dir / "bm25_metadata.pkl"
    if not meta_path.exists():
        raise FileNotFoundError(f"BM25 metadata not found at {meta_path}")
    with meta_path.open("rb") as handle:
        return pickle.load(handle)


def _load_or_create_chunk_id_map(spec: BM25ShardSpec) -> tuple[str, ...]:
    map_path = _chunk_id_map_path(spec.path)
    if map_path.is_file():
        return _load_chunk_id_map(map_path)

    started = time.perf_counter()
    _log_memory("bm25_chunk_id_map_build_start", shard=spec.name, map_path=str(map_path))
    metadata = _load_metadata(spec.path)
    try:
        chunk_ids = metadata.get("chunk_ids") if isinstance(metadata, dict) else None
        if not isinstance(chunk_ids, list):
            raise ValueError(f"BM25 metadata for {spec.name} is missing chunk_ids.")
        values = tuple(str(chunk_id) for chunk_id in chunk_ids)
    finally:
        del metadata
        gc.collect()

    _write_chunk_id_map(map_path, values)
    _log_memory(
        "bm25_chunk_id_map_build_done",
        shard=spec.name,
        map_path=str(map_path),
        chunk_ids=len(values),
        seconds=round(time.perf_counter() - started, 4),
    )
    return values


def _chunk_id_map_path(index_dir: Path) -> Path:
    configured = os.environ.get("BM25_CHUNK_ID_MAP_NAME", "bm25_chunk_ids.jsonl")
    return Path(index_dir) / configured


def _load_chunk_id_map(path: Path) -> tuple[str, ...]:
    started = time.perf_counter()
    values: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            values.append(str(json.loads(line)))
    _log_memory(
        "bm25_chunk_id_map_loaded",
        map_path=str(path),
        chunk_ids=len(values),
        seconds=round(time.perf_counter() - started, 4),
    )
    return tuple(values)


def _write_chunk_id_map(path: Path, chunk_ids: Iterable[str]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for chunk_id in chunk_ids:
            handle.write(json.dumps(str(chunk_id), ensure_ascii=False) + "\n")
    tmp_path.replace(path)


def _open_payload_lookup(index_dir: Path) -> SQLitePayloadLookup | None:
    path = _resolve_payload_cache_path(index_dir)
    if path is None or not path.is_file():
        logger.warning("BM25 payload SQLite cache is unavailable; payload hydration will return empty payloads.")
        return None
    try:
        lookup = SQLitePayloadLookup(path)
    except Exception:
        logger.exception("BM25 payload SQLite cache could not be opened: %s", path)
        return None
    logger.info("Using BM25 payload lookup SQLite cache: %s", path)
    return lookup


def _resolve_payload_cache_path(index_dir: Path) -> Path | None:
    configured = os.environ.get("BM25_PAYLOAD_CACHE_PATH", "").strip()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else PROJECT_ROOT / path

    dense_index_dir = os.environ.get("DENSE_INDEX_DIR", "").strip()
    candidates: list[Path] = []
    if dense_index_dir:
        dense_path = Path(dense_index_dir)
        candidates.append((dense_path if dense_path.is_absolute() else PROJECT_ROOT / dense_path) / "payload_cache.sqlite")
    candidates.extend([
        PROJECT_ROOT / "data" / "chunk metadata" / "payload_cache.sqlite",
        index_dir / "payload_cache.sqlite",
    ])
    return next((path for path in candidates if path.is_file()), candidates[0] if candidates else None)


def _configured_search_workers(shard_count: int) -> int:
    raw = os.environ.get("BM25_SEARCH_WORKERS", "4")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"BM25_SEARCH_WORKERS must be an integer >= 1, got {raw!r}.") from exc
    if value < 1:
        raise ValueError(f"BM25_SEARCH_WORKERS must be >= 1, got {value}.")
    return max(1, min(value, max(1, shard_count)))


def _manifest_document_count(shard_dir: Path) -> int | None:
    for name in ("manifest.json", "index_manifest.json", "meta.json"):
        path = shard_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("total_documents", "document_count", "chunk_count", "payload_count", "count"):
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, bool) or value is None:
                continue
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count >= 0:
                return count
    return None


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
    if _index is None:
        specs = _discover_shard_specs(_resolve_index_dir())
        return {
            "status": "starting",
            "index_dir": str(_resolve_index_dir()),
            "index_version": os.environ.get("BM25_INDEX_VERSION", "local-bm25"),
            "shard_count": len(specs),
            "total_documents": _total_documents_from_specs(specs),
            "preload_seconds": None,
            "resident_index_count": 0,
            "search_workers": _configured_search_workers(len(specs)),
            "payload_lookup_path": None,
            "rss_after_preload_bytes": None,
            "rss_bytes": _current_rss_bytes(),
        }

    _log_memory("bm25_healthz", resident_index_count=_index.resident_index_count)
    return {
        "status": "ok",
        "index_dir": str(_resolve_index_dir()),
        "index_version": os.environ.get("BM25_INDEX_VERSION", "local-bm25"),
        "shard_count": _index.shard_count,
        "total_documents": _index.total_documents,
        "preload_seconds": round(_index.preload_seconds, 4),
        "resident_index_count": _index.resident_index_count,
        "search_workers": _index.search_workers,
        "payload_lookup_path": str(_index.payload_lookup.path) if _index.payload_lookup else None,
        "rss_after_preload_bytes": _index.rss_after_preload_bytes,
        "rss_bytes": _current_rss_bytes(),
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
    filter_profile = str(body.get("filter_profile") or "broad")
    if filter_profile not in {"broad", "current_law", "historical"}:
        raise HTTPException(status_code=400, detail="filter_profile must be broad, current_law, or historical.")

    service_index = _load_index()
    if filter_profile != "broad" and service_index.payload_lookup is None:
        raise HTTPException(
            status_code=503,
            detail="BM25 payload lookup is required for filtered retrieval.",
        )
    results: list[dict[str, Any]] = []
    query_diagnostics: list[QueryDiagnostics] = []
    include_payloads = bool(body.get("include_payloads"))
    for query_index, query in enumerate(queries, start=1):
        if not isinstance(query, dict):
            raise HTTPException(status_code=400, detail="Each query must be an object.")
        qa_id = str(query.get("qa_id") or f"q{query_index}")
        question = str(query.get("question") or query.get("query") or "").strip()
        if not question:
            results.append({"qa_id": qa_id, "bm25_hits": []})
            query_diagnostics.append(
                QueryDiagnostics(
                    qa_id,
                    0.0,
                    {},
                    0.0,
                    0.0,
                    _current_rss_bytes(),
                    filter_profile,
                    0,
                    0,
                )
            )
            continue
        outcome = _search_shards(
            service_index,
            qa_id,
            question,
            top_k=top_k,
            include_payloads=include_payloads,
            filter_profile=filter_profile,
        )
        query_diagnostics.append(outcome.diagnostics)
        results.append({
            "qa_id": qa_id,
            "bm25_hits": [
                _bm25_hit_to_dict(hit, rank, include_payloads=include_payloads)
                for rank, hit in enumerate(outcome.hits, start=1)
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
            "startup_preload_seconds": round(service_index.preload_seconds, 4),
            "resident_index_count": service_index.resident_index_count,
            "search_workers": service_index.search_workers,
            "filter_profile_used": filter_profile,
            "payload_lookup_path": str(service_index.payload_lookup.path) if service_index.payload_lookup else None,
            "rss_after_preload_bytes": service_index.rss_after_preload_bytes,
            "rss_bytes": _current_rss_bytes(),
            "queries": [item.to_dict() for item in query_diagnostics],
        }
    return response


def _search_shards(
    index: BM25ServiceIndex,
    qa_id: str,
    question: str,
    *,
    top_k: int,
    include_payloads: bool,
    filter_profile: str,
) -> SearchOutcome:
    started = time.perf_counter()
    tokenized_query = index.tokenizer(question)
    per_shard_seconds: dict[str, float] = {}
    candidates: list[LightweightBM25Candidate] = []
    shard_top_k = _candidate_search_top_k(top_k, filter_profile)

    for shard, shard_candidates, shard_seconds in _search_all_resident_shards(
        index.shards,
        tokenized_query,
        top_k=shard_top_k,
        workers=index.search_workers,
    ):
        per_shard_seconds[shard.spec.name] = shard_seconds
        candidates.extend(shard_candidates)
        _log_memory(
            "bm25_resident_shard_search_done",
            qa_id=qa_id,
            shard=shard.spec.name,
            shard_hits=len(shard_candidates),
            retained_candidates=len(candidates),
            search_seconds=round(shard_seconds, 4),
        )

    hydration_started = time.perf_counter()
    final_candidates = _final_candidate_pool(candidates, top_k if filter_profile == "broad" else len(candidates))
    hydration = _hydrate_final_hits(
        index,
        final_candidates,
        include_payloads=include_payloads,
        filter_profile=filter_profile,
    )
    hits = hydration.hits[:top_k]
    hydration_seconds = time.perf_counter() - hydration_started
    total_seconds = time.perf_counter() - started
    _log_memory(
        "bm25_payload_hydration_done",
        qa_id=qa_id,
        hydrated_hits=len(hits),
        chunk_id_lookup_seconds=round(hydration.chunk_id_lookup_seconds, 4),
        payload_hydration_seconds=round(hydration.payload_hydration_seconds, 4),
        hydration_total_seconds=round(hydration_seconds, 4),
    )
    _log_memory(
        "bm25_query_done",
        qa_id=qa_id,
        total_seconds=round(total_seconds, 4),
        chunk_id_lookup_seconds=round(hydration.chunk_id_lookup_seconds, 4),
        payload_hydration_seconds=round(hydration.payload_hydration_seconds, 4),
        retained_hits=len(hits),
        resident_index_count=index.resident_index_count,
        search_workers=index.search_workers,
        filter_profile=filter_profile,
        pre_filter_candidate_count=hydration.pre_filter_candidate_count,
        post_filter_candidate_count=hydration.post_filter_candidate_count,
    )
    return SearchOutcome(
        hits=hits,
        diagnostics=QueryDiagnostics(
            qa_id=qa_id,
            total_seconds=total_seconds,
            per_shard_search_seconds=per_shard_seconds,
            chunk_id_lookup_seconds=hydration.chunk_id_lookup_seconds,
            payload_hydration_seconds=hydration.payload_hydration_seconds,
            rss_bytes=_current_rss_bytes(),
            filter_profile_used=filter_profile,
            pre_filter_candidate_count=hydration.pre_filter_candidate_count,
            post_filter_candidate_count=hydration.post_filter_candidate_count,
        ),
    )


def _search_all_resident_shards(
    shards: Iterable[ResidentBM25Shard],
    tokenized_query: list[str],
    *,
    top_k: int,
    workers: int,
) -> list[tuple[ResidentBM25Shard, list[LightweightBM25Candidate], float]]:
    shard_list = list(shards)
    if workers <= 1 or len(shard_list) <= 1:
        return [_timed_search_resident_shard(shard, tokenized_query, top_k=top_k) for shard in shard_list]
    with ThreadPoolExecutor(max_workers=min(workers, len(shard_list))) as executor:
        futures = [
            executor.submit(_timed_search_resident_shard, shard, tokenized_query, top_k=top_k)
            for shard in shard_list
        ]
        return [future.result() for future in futures]


def _timed_search_resident_shard(
    shard: ResidentBM25Shard,
    tokenized_query: list[str],
    *,
    top_k: int,
) -> tuple[ResidentBM25Shard, list[LightweightBM25Candidate], float]:
    started = time.perf_counter()
    candidates = _search_resident_shard(shard, tokenized_query, top_k=top_k)
    return shard, candidates, time.perf_counter() - started


def _search_resident_shard(
    shard: ResidentBM25Shard,
    tokenized_query: list[str],
    *,
    top_k: int,
) -> list[LightweightBM25Candidate]:
    scores = shard.bm25.get_scores(tokenized_query)
    top_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
    candidates: list[LightweightBM25Candidate] = []
    for shard_rank, local_index in enumerate(top_indices, start=1):
        score = float(scores[local_index])
        if score <= 0:
            continue
        candidates.append(
            LightweightBM25Candidate(
                spec=shard.spec,
                local_index=int(local_index),
                score=score,
                shard_rank=shard_rank,
            )
        )
    return candidates


def _hydrate_final_hits(
    index: BM25ServiceIndex,
    candidates: Iterable[LightweightBM25Candidate],
    *,
    include_payloads: bool,
    filter_profile: str,
) -> HydrationOutcome:
    lookup_started = time.perf_counter()
    hits: list[ShardedSearchHit] = []
    chunk_ids_by_shard = {shard.spec.name: shard.chunk_ids for shard in index.shards}
    for candidate in candidates:
        chunk_ids = chunk_ids_by_shard[candidate.spec.name]
        if candidate.local_index < 0 or candidate.local_index >= len(chunk_ids):
            raise IndexError(
                f"BM25 local_index {candidate.local_index} is out of range for {candidate.spec.name}."
            )
        hits.append(
            ShardedSearchHit(
                chunk_id=chunk_ids[candidate.local_index],
                score=candidate.score,
                spec=candidate.spec,
                shard_rank=candidate.shard_rank,
            )
        )
    chunk_id_lookup_seconds = time.perf_counter() - lookup_started

    best_by_chunk_id: dict[str, ShardedSearchHit] = {}
    for hit in hits:
        current = best_by_chunk_id.get(hit.chunk_id)
        if current is None or hit.score > current.score:
            best_by_chunk_id[hit.chunk_id] = hit
    ordered_hits = _sorted_hits(best_by_chunk_id.values())

    payload_started = time.perf_counter()
    filters = _filters_for_profile(filter_profile)
    payloads_by_chunk_id: dict[str, dict[str, Any]] = {}
    if (include_payloads or filters) and ordered_hits and index.payload_lookup is not None:
        payloads_by_chunk_id = index.payload_lookup.load_payloads(hit.chunk_id for hit in ordered_hits)

    pre_filter_count = len(ordered_hits)
    if filters:
        ordered_hits = [
            hit
            for hit in ordered_hits
            if payload_matches(payloads_by_chunk_id.get(hit.chunk_id) or {}, filters)
        ]
    post_filter_count = len(ordered_hits)

    if include_payloads and ordered_hits:
        ordered_hits = [
            ShardedSearchHit(
                chunk_id=hit.chunk_id,
                score=hit.score,
                spec=hit.spec,
                shard_rank=hit.shard_rank,
                payload=dict(payloads_by_chunk_id.get(hit.chunk_id) or {}),
            )
            for hit in ordered_hits
        ]
    payload_hydration_seconds = time.perf_counter() - payload_started
    return HydrationOutcome(
        hits=ordered_hits,
        chunk_id_lookup_seconds=chunk_id_lookup_seconds,
        payload_hydration_seconds=payload_hydration_seconds,
        pre_filter_candidate_count=pre_filter_count,
        post_filter_candidate_count=post_filter_count,
    )


def _candidate_search_top_k(top_k: int, filter_profile: str) -> int:
    if filter_profile == "broad":
        return top_k
    multiplier = _env_int("BM25_FILTER_CANDIDATE_MULTIPLIER", 5)
    minimum = _env_int("BM25_FILTER_CANDIDATE_MIN", 50)
    return max(top_k, top_k * max(1, multiplier), minimum)


def _filters_for_profile(filter_profile: str) -> dict[str, Any]:
    if filter_profile == "current_law":
        return {"validity_group": {"in": ["active", "partial", "future"]}}
    if filter_profile == "historical":
        return {"validity_group": {"in": ["expired", "active", "partial"]}}
    return {}


def _final_candidate_pool(
    candidates: Iterable[LightweightBM25Candidate],
    top_k: int,
) -> list[LightweightBM25Candidate]:
    ordered = _sorted_candidates(candidates)
    if len(ordered) <= top_k:
        return ordered
    cutoff = ordered[top_k - 1].score
    return [candidate for candidate in ordered if candidate.score >= cutoff]


def _candidates_by_shard(
    candidates: Iterable[LightweightBM25Candidate],
) -> list[tuple[BM25ShardSpec, list[LightweightBM25Candidate]]]:
    grouped: dict[str, tuple[BM25ShardSpec, list[LightweightBM25Candidate]]] = {}
    for candidate in _sorted_candidates(candidates):
        _, group = grouped.setdefault(candidate.spec.name, (candidate.spec, []))
        group.append(candidate)
    return list(grouped.values())


def _sorted_candidates(candidates: Iterable[LightweightBM25Candidate]) -> list[LightweightBM25Candidate]:
    return sorted(
        candidates,
        key=lambda item: (-item.score, item.spec.name, item.local_index),
    )


def _sorted_hits(hits: Iterable[ShardedSearchHit]) -> list[ShardedSearchHit]:
    return sorted(
        hits,
        key=lambda item: (-item.score, item.chunk_id, item.spec.name),
    )


def _total_documents_from_specs(specs: Iterable[BM25ShardSpec]) -> int | None:
    counts = [spec.document_count for spec in specs]
    if any(count is None for count in counts):
        return None
    return sum(int(count) for count in counts if count is not None)


def _bm25_hit_to_dict(item: ShardedSearchHit, rank: int, *, include_payloads: bool) -> dict[str, Any]:
    data = {
        "chunk_id": item.chunk_id,
        "bm25_score": float(item.score),
        "rank": rank,
        "shard_id": item.spec.shard_id,
        "shard_name": item.spec.name,
        "shard_rank": item.shard_rank,
    }
    if include_payloads:
        data["payload"] = dict(item.payload)
    return data


def _log_memory(event: str, **fields: Any) -> None:
    rss = _current_rss_bytes()
    payload = {
        "event": event,
        "rss_bytes": rss,
        "rss": _format_bytes(rss),
        **fields,
    }
    logger.info("bm25_memory %s", json.dumps(payload, ensure_ascii=False, default=str))


def _current_rss_bytes() -> int | None:
    try:
        import psutil  # type: ignore[import-untyped]

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        pass

    if os.name != "posix":
        return None
    try:
        import resource

        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return rss * 1024
    except Exception:
        return None


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"
