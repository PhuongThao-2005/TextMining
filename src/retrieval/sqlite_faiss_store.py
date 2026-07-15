"""FAISS vector store with a SQLite payload cache.

``SQLitePayloadFaissVectorStore`` implements the existing :class:`VectorStore`
ABC so it is interchangeable with :class:`FaissVectorStore` for read/search
workloads. Payload metadata is served from ``payload_cache.sqlite`` (keyed by
``line_no``) instead of an in-memory ``payloads.jsonl`` list.

``recreate_collection`` / ``upsert`` are intentionally unsupported: this store
is a load-time read path for an already-built ``data/faiss_index/`` artifact
(build/write remains on :class:`FaissVectorStore`).

Payload cache schema v2 extracts filter columns
(``chunk_id``, ``parent_unit_id``, ``chunk_index_in_unit``, ``validity_group``,
``id_str``) so ``scroll()`` can use SQL indexes instead of a full-table Python
scan. That matters for ``expand_units`` which previously re-scanned every row
once per FAISS hit.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .schema import VectorRecord
from .stores import SearchHit, VectorStore, payload_matches

logger = logging.getLogger(__name__)

# Bump when the SQLite payload table / index layout changes so stale caches rebuild.
_PAYLOAD_CACHE_SCHEMA_VERSION = "2"

_SQL_FILTER_FIELDS = frozenset(
    {
        "chunk_id",
        "parent_unit_id",
        "chunk_index_in_unit",
        "validity_group",
        "id_str",
    }
)


@dataclass(frozen=True)
class PayloadCacheStatus:
    """Result of comparing ``payload_cache.sqlite`` against ``payloads.jsonl``."""

    exists: bool
    is_stale: bool
    payload_size: int
    payload_mtime_ns: int


def _expected_cache_meta(payloads_path: Path) -> dict[str, str]:
    payload_stat = payloads_path.stat()
    return {
        "schema_version": _PAYLOAD_CACHE_SCHEMA_VERSION,
        "payload_mtime_ns": str(payload_stat.st_mtime_ns),
        "payload_size": str(payload_stat.st_size),
    }


def _read_cache_meta(cache_path: Path) -> dict[str, str] | None:
    try:
        conn = sqlite3.connect(str(cache_path))
        try:
            return dict(conn.execute("SELECT key, value FROM meta").fetchall())
        finally:
            conn.close()
    except Exception:
        logger.debug("payload cache meta read failed", exc_info=True)
        return None


def _check_payload_cache(index_dir: Path) -> PayloadCacheStatus:
    """Return freshness status for ``payload_cache.sqlite`` under ``index_dir``."""
    payloads_path = index_dir / "payloads.jsonl"
    cache_path = index_dir / "payload_cache.sqlite"

    if not payloads_path.exists():
        return PayloadCacheStatus(
            exists=cache_path.exists(),
            is_stale=True,
            payload_size=0,
            payload_mtime_ns=0,
        )

    payload_stat = payloads_path.stat()
    payload_size = int(payload_stat.st_size)
    payload_mtime_ns = int(payload_stat.st_mtime_ns)

    if not cache_path.exists():
        return PayloadCacheStatus(
            exists=False,
            is_stale=True,
            payload_size=payload_size,
            payload_mtime_ns=payload_mtime_ns,
        )

    expected = _expected_cache_meta(payloads_path)
    rows = _read_cache_meta(cache_path)
    if rows == expected:
        return PayloadCacheStatus(
            exists=True,
            is_stale=False,
            payload_size=payload_size,
            payload_mtime_ns=payload_mtime_ns,
        )

    return PayloadCacheStatus(
        exists=True,
        is_stale=True,
        payload_size=payload_size,
        payload_mtime_ns=payload_mtime_ns,
    )


def _extract_index_fields(payload_text: str) -> tuple[str | None, str | None, int | None, str | None, str | None]:
    """Pull scroll/filter columns out of a raw JSON payload line."""
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None, None, None, None, None

    chunk_id = payload.get("chunk_id")
    parent_unit_id = payload.get("parent_unit_id")
    validity_group = payload.get("validity_group")
    id_str = payload.get("id_str")
    index_raw = payload.get("chunk_index_in_unit")
    chunk_index: int | None
    if isinstance(index_raw, bool):
        chunk_index = None
    elif isinstance(index_raw, int):
        chunk_index = index_raw
    elif isinstance(index_raw, float) and index_raw.is_integer():
        chunk_index = int(index_raw)
    else:
        chunk_index = None

    return (
        None if chunk_id is None else str(chunk_id),
        None if parent_unit_id is None else str(parent_unit_id),
        chunk_index,
        None if validity_group is None else str(validity_group),
        None if id_str is None else str(id_str),
    )


def _ensure_payload_cache(payloads_path: Path, cache_path: Path) -> None:
    """Reuse ``cache_path`` when fresh; otherwise rebuild from ``payloads_path``."""
    meta = _expected_cache_meta(payloads_path)

    if cache_path.exists():
        rows = _read_cache_meta(cache_path)
        if rows == meta:
            print(f"Reusing SQLite payload cache: {cache_path.name}")
            return
        cache_path.unlink(missing_ok=True)

    tmp_path = cache_path.with_suffix(".sqlite.tmp")
    tmp_path.unlink(missing_ok=True)
    print(
        "Building SQLite payload cache once. This may take a while for a large "
        "JSONL, but future starts will skip it."
    )
    t0 = time.perf_counter()
    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute(
            """
            CREATE TABLE payloads (
                line_no INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                chunk_id TEXT,
                parent_unit_id TEXT,
                chunk_index_in_unit INTEGER,
                validity_group TEXT,
                id_str TEXT
            )
            """
        )
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            "CREATE INDEX idx_payloads_parent_unit "
            "ON payloads(parent_unit_id, chunk_index_in_unit)"
        )
        conn.execute("CREATE INDEX idx_payloads_chunk_id ON payloads(chunk_id)")
        conn.execute("CREATE INDEX idx_payloads_validity ON payloads(validity_group)")
        conn.execute("CREATE INDEX idx_payloads_id_str ON payloads(id_str)")

        batch: list[tuple[int, str, str | None, str | None, int | None, str | None, str | None]] = []
        with payloads_path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle):
                line = line.strip()
                if not line:
                    continue
                chunk_id, parent_unit_id, chunk_index, validity_group, id_str = _extract_index_fields(
                    line
                )
                batch.append(
                    (
                        line_no,
                        line,
                        chunk_id,
                        parent_unit_id,
                        chunk_index,
                        validity_group,
                        id_str,
                    )
                )
                if len(batch) >= 10_000:
                    conn.executemany(
                        """
                        INSERT INTO payloads(
                            line_no, payload, chunk_id, parent_unit_id,
                            chunk_index_in_unit, validity_group, id_str
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    batch.clear()
        if batch:
            conn.executemany(
                """
                INSERT INTO payloads(
                    line_no, payload, chunk_id, parent_unit_id,
                    chunk_index_in_unit, validity_group, id_str
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )

        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", list(meta.items()))
        conn.commit()
    finally:
        conn.close()

    tmp_path.replace(cache_path)
    print(f"Built SQLite payload cache in {time.perf_counter() - t0:.2f}s")


def _import_faiss():
    try:
        import faiss

        return faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is required for SQLitePayloadFaissVectorStore. "
            "Install it with: pip install faiss-cpu"
        ) from exc


class SQLitePayloadFaissVectorStore(VectorStore):
    """FAISS index + SQLite payload cache implementing :class:`VectorStore`."""

    def __init__(
        self,
        *,
        index,
        dimension: int,
        index_dir: Path,
        payloads_path: Path,
        cache_path: Path,
        int_to_id: dict[int, str] | None = None,
    ) -> None:
        self.index = index
        self.dimension = dimension
        self.index_dir = Path(index_dir)
        self.payloads_path = Path(payloads_path)
        self.cache_path = Path(cache_path)
        self.int_to_id: dict[int, str] = int_to_id or {}
        self.id_map = self.int_to_id  # data-model alias
        self.conn = sqlite3.connect(str(self.cache_path))
        self.conn.execute("PRAGMA query_only = ON")
        # Notebook export helpers historically used store._conn.
        self._conn = self.conn

    @classmethod
    def load(cls, index_dir: Path) -> "SQLitePayloadFaissVectorStore":
        """Load FAISS index and ensure a fresh SQLite payload cache under ``index_dir``."""
        faiss = _import_faiss()
        index_dir = Path(index_dir)

        index_path = index_dir / "index.faiss"
        payloads_path = index_dir / "payloads.jsonl"
        cache_path = index_dir / "payload_cache.sqlite"
        id_map_path = index_dir / "id_map.json"

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}")
        if not payloads_path.exists():
            raise FileNotFoundError(f"Payload file not found at {payloads_path}")

        _ensure_payload_cache(payloads_path, cache_path)

        t0 = time.perf_counter()
        read_flags = getattr(faiss, "IO_FLAG_MMAP", 0) | getattr(faiss, "IO_FLAG_READ_ONLY", 0)
        try:
            index = faiss.read_index(str(index_path), read_flags)
        except TypeError:
            index = faiss.read_index(str(index_path))
        print(f"FAISS index loaded in {time.perf_counter() - t0:.2f}s")

        int_to_id: dict[int, str] = {}
        if id_map_path.exists():
            with id_map_path.open("r", encoding="utf-8") as handle:
                id_map = json.load(handle)
            id_to_int = {str(k): int(v) for k, v in id_map.items()}
            int_to_id = {v: k for k, v in id_to_int.items()}

        return cls(
            index=index,
            dimension=index.d,
            index_dir=index_dir,
            payloads_path=payloads_path,
            cache_path=cache_path,
            int_to_id=int_to_id,
        )

    def recreate_collection(self, vector_size: int) -> None:
        raise NotImplementedError(
            "SQLitePayloadFaissVectorStore is read-only; use FaissVectorStore to rebuild indexes."
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        raise NotImplementedError(
            "SQLitePayloadFaissVectorStore is read-only; use FaissVectorStore to write vectors."
        )

    def _load_payloads(self, line_nos: list[int]) -> dict[int, dict[str, Any]]:
        if not line_nos:
            return {}
        placeholders = ",".join("?" for _ in line_nos)
        rows = self.conn.execute(
            f"SELECT line_no, payload FROM payloads WHERE line_no IN ({placeholders})",
            line_nos,
        ).fetchall()
        return {int(line_no): json.loads(payload) for line_no, payload in rows}

    def _iter_payloads(self):
        for line_no, payload_text in self.conn.execute(
            "SELECT line_no, payload FROM payloads ORDER BY line_no"
        ):
            yield int(line_no), json.loads(payload_text)

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if self.index.ntotal == 0:
            return []

        t_faiss = time.perf_counter()
        query = np.array([vector], dtype=np.float32)
        # Validity filters still require payload inspection; keep modest over-fetch.
        search_limit = limit * 3 if filters else limit
        search_limit = min(max(search_limit, limit), self.index.ntotal)
        scores, indices = self.index.search(query, search_limit)
        faiss_time = time.perf_counter() - t_faiss

        valid_pairs = [
            (float(score), int(idx))
            for score, idx in zip(scores[0], indices[0])
            if idx >= 0
        ]
        if score_threshold is not None:
            valid_pairs = [
                (score, idx) for score, idx in valid_pairs if score >= score_threshold
            ]

        t_payload = time.perf_counter()
        payloads = self._load_payloads([idx for _, idx in valid_pairs])
        payload_time = time.perf_counter() - t_payload

        hits: list[SearchHit] = []
        for score, idx in valid_pairs:
            payload = payloads.get(idx, {})
            if filters and not payload_matches(payload, filters):
                continue

            point_id = self.int_to_id.get(idx) or str(payload.get("chunk_id") or idx)
            hits.append(SearchHit(point_id=point_id, score=score, payload=payload))
            if len(hits) >= limit:
                break

        print(
            f"FAISS search: {faiss_time:.3f}s | payload batch load: {payload_time:.3f}s | "
            f"inspected: {len(valid_pairs)}"
        )
        return hits

    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]:
        """Return payloads matching ``filters`` without vector similarity.

        Fast path: pure equality / ``in`` / range filters on indexed columns are
        pushed into SQL. Anything else falls back to a full-table Python scan.
        """
        t0 = time.perf_counter()
        sql_hits = self._scroll_sql(filters, limit)
        if sql_hits is not None:
            print(
                f"scroll SQL: {time.perf_counter() - t0:.3f}s | "
                f"matched={len(sql_hits)} limit={limit}"
            )
            return sql_hits

        hits: list[SearchHit] = []
        for line_no, payload in self._iter_payloads():
            if payload_matches(payload, filters):
                point_id = self.int_to_id.get(line_no) or str(
                    payload.get("chunk_id") or line_no
                )
                hits.append(SearchHit(point_id=point_id, score=0.0, payload=payload))
                if len(hits) >= limit:
                    break
        print(
            f"scroll full-scan: {time.perf_counter() - t0:.3f}s | "
            f"matched={len(hits)} limit={limit}"
        )
        return hits

    def _scroll_sql(
        self, filters: dict[str, Any], limit: int
    ) -> list[SearchHit] | None:
        """Translate simple filters into an indexed SQL query.

        Returns ``None`` when the filter set cannot be fully expressed in SQL so
        the caller can fall back to a full-table Python scan.
        """
        if limit <= 0:
            return []
        if not filters:
            rows = self.conn.execute(
                "SELECT line_no, payload FROM payloads ORDER BY line_no LIMIT ?",
                (limit,),
            ).fetchall()
            return self._rows_to_hits(rows)

        if any(field not in _SQL_FILTER_FIELDS for field in filters):
            return None

        where_clauses: list[str] = []
        params: list[Any] = []
        for field, expected in filters.items():
            clause, clause_params = self._sql_predicate(field, expected)
            if clause is None:
                return None
            where_clauses.append(clause)
            params.extend(clause_params)

        sql = (
            "SELECT line_no, payload FROM payloads WHERE "
            + " AND ".join(where_clauses)
            + " ORDER BY line_no LIMIT ?"
        )
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return self._rows_to_hits(rows)

    @staticmethod
    def _sql_predicate(field: str, expected: Any) -> tuple[str | None, list[Any]]:
        if isinstance(expected, dict):
            if "in" in expected:
                values = list(expected["in"])
                if not values:
                    return "0", []
                placeholders = ",".join("?" for _ in values)
                return f"{field} IN ({placeholders})", values
            if "range" in expected:
                low, high = expected["range"]
                return f"{field} BETWEEN ? AND ?", [low, high]
            if "lte" in expected or "gte" in expected:
                parts: list[str] = []
                params: list[Any] = []
                if "gte" in expected:
                    parts.append(f"{field} >= ?")
                    params.append(expected["gte"])
                if "lte" in expected:
                    parts.append(f"{field} <= ?")
                    params.append(expected["lte"])
                return " AND ".join(parts), params
            return None, []

        if isinstance(expected, (list, tuple, set)):
            values = list(expected)
            if not values:
                return "0", []
            placeholders = ",".join("?" for _ in values)
            return f"{field} IN ({placeholders})", values

        return f"{field} = ?", [expected]

    def _rows_to_hits(self, rows: list[tuple[Any, ...]]) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for line_no, payload_text in rows:
            line_no_int = int(line_no)
            payload = json.loads(payload_text)
            point_id = self.int_to_id.get(line_no_int) or str(
                payload.get("chunk_id") or line_no_int
            )
            hits.append(SearchHit(point_id=point_id, score=0.0, payload=payload))
        return hits

    @property
    def total_vectors(self) -> int:
        return int(self.index.ntotal)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
