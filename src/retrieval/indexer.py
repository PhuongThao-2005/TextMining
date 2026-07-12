from __future__ import annotations

import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import VectorIndexConfig, VectorPaths
from .embeddings import Embedder
from .io_utils import batched, read_jsonl
from .schema import VectorRecord
from .stores import VectorStore
from .text_builder import build_payload, build_retrieval_text


@dataclass
class IndexStats:
    total_chunks_in_source: int = 0
    total_chunks_indexed: int = 0
    total_chunks_skipped: int = 0
    duplicate_chunk_ids: int = 0
    join_misses: int = 0
    missing_chunk_text: int = 0
    missing_citation_anchor: int = 0
    invalid_validity_or_rank: int = 0
    unique_documents: set[str] = field(default_factory=set)
    unique_provisions: set[str] = field(default_factory=set)
    token_estimates: list[int] = field(default_factory=list)
    validity_counts: Counter[str] = field(default_factory=Counter)
    rank_counts: Counter[int] = field(default_factory=Counter)
    unit_type_counts: Counter[str] = field(default_factory=Counter)
    doc_type_counts: Counter[str] = field(default_factory=Counter)
    legal_field_counts: Counter[str] = field(default_factory=Counter)
    elapsed_seconds: float = 0.0


class VectorIndexer:
    """Build a vector index from v2 chunks by joining provisions and documents."""

    def __init__(
        self,
        *,
        paths: VectorPaths,
        config: VectorIndexConfig,
        embedder: Embedder,
        store: VectorStore,
    ) -> None:
        self.paths = paths
        self.config = config
        self.embedder = embedder
        self.store = store

    def build(self, *, recreate: bool = True, limit: int | None = None, write_report: bool = True) -> IndexStats:
        self._validate_inputs()
        documents = self._load_by_key(self.paths.documents_path, "id_str")
        provisions = self._load_by_key(self.paths.provisions_path, "unit_id")

        if recreate:
            self.store.recreate_collection(self.embedder.dimension)

        stats = IndexStats()
        seen_chunk_ids: set[str] = set()
        start = time.time()
        source = read_jsonl(self.paths.chunks_path)
        if limit is not None:
            source = self._limited(source, limit)

        for batch_no, chunk_batch in enumerate(batched(source, self.config.batch_size), start=1):
            records, texts = [], []
            for chunk in chunk_batch:
                stats.total_chunks_in_source += 1
                chunk_id = str(chunk.get("chunk_id") or "")
                if chunk_id in seen_chunk_ids:
                    stats.duplicate_chunk_ids += 1
                    stats.total_chunks_skipped += 1
                    continue
                seen_chunk_ids.add(chunk_id)

                provision = provisions.get(str(chunk.get("parent_unit_id") or ""))
                document = documents.get(str(chunk.get("id_str") or ""))
                if not provision or not document:
                    stats.join_misses += 1
                    stats.total_chunks_skipped += 1
                    continue

                text = build_retrieval_text(chunk, provision, document)
                payload = build_payload(chunk, provision, document)
                self._update_quality_stats(stats, payload)
                texts.append(text)
                records.append((chunk_id, payload))

            if records:
                vectors = self.embedder.encode_passages(texts)
                self.store.upsert(
                    [
                        VectorRecord(point_id=chunk_id, vector=vector, payload=payload)
                        for (chunk_id, payload), vector in zip(records, vectors)
                    ]
                )
                stats.total_chunks_indexed += len(records)

            if batch_no % max(1, 1000 // max(1, self.config.batch_size)) == 0:
                print(f"Indexed {stats.total_chunks_indexed:,} chunks...")

        stats.elapsed_seconds = time.time() - start
        if write_report:
            self.write_report(stats)
        return stats

    def write_report(self, stats: IndexStats) -> None:
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)
        avg_time = stats.elapsed_seconds / stats.total_chunks_indexed if stats.total_chunks_indexed else 0.0
        token_stats = self._token_summary(stats.token_estimates)
        report = [
            "# Vector Index Report",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| collection | `{self.config.collection_name}` |",
            f"| embedding_model | `{self.embedder.model_name}` |",
            f"| vector_dimension | {self.embedder.dimension} |",
            f"| retrieval_text_template_version | `{self.config.retrieval_text_template_version}` |",
            f"| distance | {self.config.distance} |",
            f"| total_chunks_in_source | {stats.total_chunks_in_source} |",
            f"| total_chunks_indexed | {stats.total_chunks_indexed} |",
            f"| total_chunks_skipped | {stats.total_chunks_skipped} |",
            f"| duplicate_chunk_ids | {stats.duplicate_chunk_ids} |",
            f"| join_misses | {stats.join_misses} |",
            f"| unique_documents_indexed | {len(stats.unique_documents)} |",
            f"| unique_provisions_indexed | {len(stats.unique_provisions)} |",
            f"| missing_chunk_text | {stats.missing_chunk_text} |",
            f"| missing_citation_anchor | {stats.missing_citation_anchor} |",
            f"| invalid_validity_or_rank | {stats.invalid_validity_or_rank} |",
            f"| elapsed_seconds | {stats.elapsed_seconds:.2f} |",
            f"| avg_embed_index_seconds_per_chunk | {avg_time:.6f} |",
            "",
            "## Token Estimates",
            "",
            "| Metric | Value |",
            "| --- | --- |",
        ]
        report.extend(f"| {key} | {value} |" for key, value in token_stats.items())
        report.extend(
            [
                "",
                "## Metadata Distribution",
                "",
                "### validity_group",
                self._counter_table(stats.validity_counts),
                "### legal_authority_rank",
                self._counter_table(stats.rank_counts),
                "### unit_type",
                self._counter_table(stats.unit_type_counts),
                "### loai_van_ban Top 10",
                self._counter_table(stats.doc_type_counts, limit=10),
                "### legal_field_code Top 10",
                self._counter_table(stats.legal_field_counts, limit=10),
                "",
                "## Acceptance Snapshot",
                "",
                f"- `total_chunks_indexed == total_chunks_in_source`: {stats.total_chunks_indexed == stats.total_chunks_in_source}",
                f"- `total_chunks_skipped == 0`: {stats.total_chunks_skipped == 0}",
                f"- `duplicate_chunk_ids == 0`: {stats.duplicate_chunk_ids == 0}",
                f"- `join_misses == 0`: {stats.join_misses == 0}",
                f"- `missing_chunk_text == 0`: {stats.missing_chunk_text == 0}",
                f"- `missing_citation_anchor == 0`: {stats.missing_citation_anchor == 0}",
                "",
                "Sample retrieval tests must be appended after running the query smoke set.",
            ]
        )
        self.paths.report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    def _validate_inputs(self) -> None:
        missing = [
            path
            for path in (self.paths.chunks_path, self.paths.provisions_path, self.paths.documents_path)
            if not path.exists()
        ]
        if missing:
            missing_list = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Missing vector input files: {missing_list}")

    @staticmethod
    def _load_by_key(path: Path, key: str) -> dict[str, dict[str, Any]]:
        out = {}
        for row in read_jsonl(path):
            row_key = str(row.get(key) or "")
            if row_key:
                out[row_key] = row
        return out

    @staticmethod
    def _limited(source, limit: int):
        for index, item in enumerate(source):
            if index >= limit:
                break
            yield item

    @staticmethod
    def _update_quality_stats(stats: IndexStats, payload: dict[str, Any]) -> None:
        stats.unique_documents.add(payload["id_str"])
        stats.unique_provisions.add(payload["parent_unit_id"])
        stats.token_estimates.append(int(payload.get("chunk_token_estimate") or 0))
        stats.validity_counts[payload.get("validity_group") or "unknown"] += 1
        stats.rank_counts[int(payload.get("legal_authority_rank") or 99)] += 1
        stats.unit_type_counts[payload.get("unit_type") or "unknown"] += 1
        stats.doc_type_counts[payload.get("loai_van_ban") or "unknown"] += 1
        stats.legal_field_counts[payload.get("legal_field_code") or "MISSING"] += 1
        if not payload.get("chunk_text"):
            stats.missing_chunk_text += 1
        if not payload.get("citation_anchor"):
            stats.missing_citation_anchor += 1
        if not payload.get("validity_group") or not isinstance(payload.get("legal_authority_rank"), int):
            stats.invalid_validity_or_rank += 1

    @staticmethod
    def _token_summary(values: list[int]) -> dict[str, str]:
        if not values:
            return {"min": "0", "max": "0", "mean": "0", "p50": "0", "p95": "0"}
        sorted_values = sorted(values)
        p95_index = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
        return {
            "min": str(min(values)),
            "max": str(max(values)),
            "mean": f"{statistics.mean(values):.2f}",
            "p50": f"{statistics.median(values):.2f}",
            "p95": str(sorted_values[p95_index]),
        }

    @staticmethod
    def _counter_table(counter: Counter[Any], limit: int | None = None) -> str:
        rows = ["| Value | Count |", "| --- | ---: |"]
        items = counter.most_common(limit)
        rows.extend(f"| `{key}` | {value} |" for key, value in items)
        return "\n".join(rows)
