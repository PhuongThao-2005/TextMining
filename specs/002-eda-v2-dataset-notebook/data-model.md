# Phase 1 Data Model: EDA Notebook for Dataset v2

This feature reads existing `data/v2/` artifacts; it does not define new persisted entities. This document describes (a) the on-disk entities it reads, restated from `docs/spec/SPEC_Dataset_v2.md` and the spec's Key Entities section for traceability, and (b) the in-memory result shapes the extracted `src/eda/dataset_v2.py` helpers return to the notebook.

## 1. Source entities (read-only)

| Entity | File | Grain | Fields the notebook depends on |
| --- | --- | --- | --- |
| Document | `data/v2/documents.jsonl` | 1 legal document | `id_str`, `legal_authority_rank`, `loai_van_ban`, `validity_group`, `currency_hint`, `scope.code`, `legal_field.code`, `issuing_authority.code`, `sector.code`, `issue_year`, `citation_label` |
| Document (quarantined) | `data/v2/documents_quarantine.jsonl` | 1 excluded document | same shape + `exclusion_reasons: list[str]` |
| Edge | `data/v2/edges.jsonl` | 1 directed relationship | `edge_id`, `src_id`, `dst_id`, `rel_canonical`, `rel_group`, `direction_verified`, `external_target`, `edge_quality_flags` |
| Edge (quarantined) | `data/v2/edges_quarantine.jsonl` | 1 excluded relationship | same shape + `exclusion_reasons: list[str]` |
| Text provenance | `data/v2/text_provenance.jsonl` | 1 per document | `id_str`, `content_row_count`, `text_status`, `extracted_char_count`, `structuring_status`, `chunk_count`, `html_quality_flags` |
| Provision | `data/v2/provisions.jsonl` | 1 Điều/khoản | `unit_id`, `id_str`, `unit_type`, `chunk_count`, `coverage_verified` — **streamed/sampled only** |
| Chunk | `data/v2/chunks.jsonl` | 1 embeddable slice | `chunk_id`, `parent_unit_id`, `id_str`, `chunk_text`, `chunk_char_count` — **streamed/sampled only** |
| Validity event | `data/v2/validity_timeline.jsonl` | 1 validity event | `id_str`, `event_type`, `event_date_iso`, `source_edge_id`, `direction_verified` |
| Authority index entry | `data/v2/authority_index.jsonl` | 1 doc-type → rank row | `loai_van_ban`, `legal_authority_rank`, `rank_label` |
| External stub | `data/v2/external_stubs.jsonl` | 1 referenced-but-missing doc | `id_str`, `citation_safe`, `referenced_by_edge_count` |
| Vocabulary mapping | `data/v2/vocabularies/*.json` | 1 code→surface map per facet | `code`, `surface` keyed mapping for `issuing_authority`, `legal_field`, `sector`, `scope` |
| Reconciliation report | `data/v2/reconciliation_report.md` | ground-truth counts | parsed via regex for the two identity rows (documents, edges) |
| Raw metadata | `data/untracked_data/metadata.jsonl` | 1 raw record | row count only (reconciliation) |
| Raw relationships | `data/untracked_data/relationships.jsonl` | 1 raw record | row count only (reconciliation) |

No field beyond what's listed above is required by any FR; the notebook must tolerate any of these fields being absent/null on a given row (Edge Cases: `null`/`"MISSING"`/`"UNMAPPED"`).

## 2. In-memory result shapes (`src/eda/dataset_v2.py`)

These are the contracts the extracted module exposes to notebook cells. Implemented as small `@dataclass` return types (not `TypedDict`, to get default values and readability in notebook `repr()` output) — see Phase 2 tasks for exact signatures.

### `PreflightResult`
```text
present: list[Path]     # files that exist
missing: list[Path]     # files that do not
by_artifact: dict[str, bool]   # e.g. {"chunks.jsonl": True, "authority_index.jsonl": True, ...}
```
Produced by `preflight(project_root: Path) -> PreflightResult`. Backs FR-001 and the Edge Case "required files missing."

### `StreamCountResult`
```text
total_rows: int
malformed_lines: int          # lines that failed json.loads, skipped and counted (FR-014)
field_counters: dict[str, Counter[str]]   # one Counter per requested field, missing/None/"MISSING"/"UNMAPPED" coerced to explicit sentinel strings (R6)
```
Produced by `stream_count(path: Path, category_fields: list[str], coerce_missing: bool = True) -> StreamCountResult`. Backs FR-003, FR-004, FR-006, FR-007, FR-011 — the "total row count + distribution of field X" pattern repeated across artifacts.

### `ReservoirSample`
```text
seed: int
sample_size: int
rows_seen: int                 # total rows streamed past (population size)
sample: list[dict]              # <= sample_size raw parsed rows, uniformly sampled
```
Produced by `reservoir_sample(path: Path, sample_size: int, seed: int, predicate: Callable[[dict], bool] | None = None) -> ReservoirSample`. Backs FR-002/FR-005's sampled `chunk_text` length distribution and any "example rows" display, and Edge Case "MUST state the sampling method and sample size."

### `ReconciliationCheck`
```text
label: str                      # e.g. "documents"
raw_count: int
final_count: int
quarantine_count: int
identity_holds: bool             # raw_count == final_count + quarantine_count
report_raw: int | None           # parsed from reconciliation_report.md, None if unparseable
report_final: int | None
report_quarantine: int | None
matches_report: bool             # recomputed counts equal parsed report counts
```
Produced by `reconcile(raw_path: Path, final_path: Path, quarantine_path: Path, report_path: Path, label: str) -> ReconciliationCheck`. Backs FR-008, US2, SC-002.

### `TagTally`
```text
row_count: int                   # number of rows examined (denominator; no double count)
tag_counts: Counter[str]         # per-reason-tag counts, a row with N tags contributes to N counters
```
Produced by `tally_tags(path: Path, tag_field: str) -> TagTally`. Backs FR-009 and Dataset_SPEC_v2 §9's "reasons are tags, rows are authoritative" rule.

### `VocabCoverage`
```text
facet: str                       # "issuing_authority" | "legal_field" | "sector" | "scope"
total: int
unmapped_or_missing: int
pct_unmapped_or_missing: float
```
Produced by `vocab_coverage(documents_path: Path, facet: str) -> VocabCoverage`. Backs FR-011, SC-005.

### `resolve_project_root() -> Path`
No result dataclass; returns the resolved project root per R4. Backs FR-013.

### `coerce_category(value: Any) -> str`
Utility used inside `stream_count` and directly in notebook cells for ad hoc groupbys; maps `None` → `"(missing)"`, the literal strings `"MISSING"`/`"UNMAPPED"` passed through as-is (they're already explicit, per Dataset_SPEC_v2 §7), everything else to `str(value)`. Backs R6/Edge Case handling.

## 3. Relationships the notebook must preserve when displaying samples

Per Constitution Principle I/II, any sampled chunk or provision row shown in notebook output must be resolvable back to its document, honoring `chunk_id → parent_unit_id → id_str`:

```text
ReservoirSample.sample (from chunks.jsonl)
  └─ parent_unit_id  ──lookup──▶  provisions.jsonl (by unit_id, on demand, single-row seek not full load)
        └─ id_str     ──lookup──▶  documents.jsonl (by id_str, on demand)
```

The notebook does not build a full in-memory join across the large files; instead, `dataset_v2.py` exposes a `lookup_by_key(path: Path, key_field: str, key_value: str) -> dict | None` helper that streams the target file once, stopping at first match, used only for the handful of sampled rows displayed to the user (not for full-corpus aggregation).
