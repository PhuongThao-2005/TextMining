# Phase 1 Data Model: Retrieval Evaluation Notebook

## 1. Source entities (read-only)

### Shared legal identity (must not be lost)

- `chunk_id → parent_unit_id → id_str` — every retrieved/expanded/traversed chunk MUST resolve back through this chain (Constitution Principle II). All new entities below carry `chunk_id` and, where available, `id_str`/`parent_unit_id` rather than inventing opaque IDs.

### Benchmark (frozen input)

- `qa_final.jsonl` row (per [`docs/spec/EVALUATION_MODULE.md`](../../docs/spec/EVALUATION_MODULE.md) §4.1): `qa_id`, `question`, `category`, `difficulty`, `answer_type`, reference answer fields, `ground_truth.document_ids`, `ground_truth.provision_ids`, `ground_truth.chunk_ids`.

### Evaluation module (existing, consumed as-is)

- [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py): `recall_at_k`, `hit_at_k`, `mrr_at_k`, `ndcg_at_k`, `jaccard_at_k`, `aggregate(rows, metric_keys)`, `aggregate_by(rows, field, metric_keys)`, `is_unanswerable_text(text)`.
- [`src/evaluation/io_utils.py`](../../src/evaluation/io_utils.py): `read_jsonl(path)`, `write_jsonl(path, rows)`, `write_json(path, obj)`, `qa_id(row, index)`.
- [`src/evaluation/retriever_factory.py`](../../src/evaluation/retriever_factory.py): `RetrieverRuntimeConfig`, `build_vector_retriever` — Qdrant-only; **not used** by this notebook (see research R3). Referenced only as the CLI's existing contract for consistency of eligibility/report shape.

### Vector retrieval (existing, consumed as-is)

- [`src/retrieval/retriever.py`](../../src/retrieval/retriever.py) `VectorRetriever.retrieve(query, filter_profile, top_k, top_n, score_threshold, expand_units, id_str_filter, graph_guided_filter, extra_filters, ...) -> RetrievalResult` with `RetrievedChunk` items (`chunk_id`, `score`, `payload`, ...).
- [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) `SQLitePayloadFaissVectorStore` — FAISS + SQLite payload cache read path.
- [`src/retrieval/embeddings.py`](../../src/retrieval/embeddings.py) `SentenceTransformerEmbedder` (production) — `HashingEmbedder` is test-only, never used for official scored runs.

### Knowledge graph (existing, consumed as-is)

- [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py) `KnowledgeGraphFacade`: `load_graph(path)`, `build_graph()`, `traverse(graph, start_id, mode, max_depth)`, `build_overlay_bundle(...)`, `build_graph_guided_filter(...)`, `build_evidence_context(...)`.
- [`src/knowledge_graph/traversal.py`](../../src/knowledge_graph/traversal.py) `GraphTraversal` / `TraversalResult(start_id, mode, max_depth, visited_ids, visited_edges, paths)`.
- [`src/knowledge_graph/expansion.py`](../../src/knowledge_graph/expansion.py) `GraphExpansion.expand(seed_chunk_ids, max_hop, max_context) -> ExpansionResult(seed_chunk_ids, max_hop, max_context, expanded_node_ids, traversed_edges, ordered_context_chunks, warnings)`.
- [`src/knowledge_graph/context_schema.py`](../../src/knowledge_graph/context_schema.py) `GraphGuidedFilter(id_strs, empty_filter_warning, filter_profile, reason)`, `EvidenceContext(filter, traversal, paths, documents, overlays, warnings)`.
- [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) `load_knowledge_graph` / `GraphPickleLoadResult` — pickle-first graph source.

## 2. New notebook-facing entities (orchestration shapes)

These are added under `src/evaluation/` as small, pure, testable helpers per research R8. They are plain dataclasses / TypedDicts, not persisted classes — shapes only, to keep the notebook thin and give pytest a stable surface.

### 2.1 `EvalRunConfig` (config cell → dataclass)

```text
EvalRunConfig
  qa_path: Path                      # default data/benchmark/qa_final.jsonl
  out_dir: Path                      # default evaluation_runs/retrieval_notebook/<run_name>/
  run_name: str
  top_k_list: list[int]              # e.g. [1, 5, 10]
  sample_limit: int | None           # None = full benchmark
  filter_profile: str                # VALID_FILTER_PROFILES
  score_threshold: float | None
  top_k_retrieve: int
  top_n: int
  index_dir: Path
  embedding_model: str
  run_vector_only: bool
  run_hybrid: bool
  graph_pickle_path: Path
  v2_data_dir: Path
  allow_jsonl_graph_rebuild: bool    # default False
  traversal_mode: str                # basis|guidance|validity|structure|neighbors
  traversal_max_depth: int           # default 3
  prepass_top_n: int                 # unfiltered vector pre-pass size for traversal starts
  max_traversal_starts: int
  hybrid_max_hop: int
  hybrid_max_context: int
  as_of_date: str | None             # overlays
  local_expand_units: bool           # default False for scored hybrid (R13)
```

Written verbatim (as a dict) into every `*_metrics.json` for reproducibility (FR-009, R13).

### 2.2 `EligibleCase`

Result of eligibility filtering over raw QA rows (mirrors `scripts/evaluate_retrieval.py` skip logic).

```text
EligibleCase
  qa_id: str
  question: str
  category: str | None
  difficulty: str | None
  answer_type: str | None
  ground_truth_chunk_ids: set[str]
  ground_truth_document_ids: set[str]
  ground_truth_provision_ids: set[str]
  raw_row: dict                       # original row for report context
```

### 2.3 `EligibilitySummary`

```text
EligibilitySummary
  total_rows: int
  eligible: list[EligibleCase]
  skipped_unanswerable: int
  skipped_missing_ground_truth: int
```

Helper: `select_eligible_cases(rows: list[dict], sample_limit: int | None) -> EligibilitySummary` — pure function, unit tested (FR-007, SC-006).

### 2.4 `RetrievalMode` (Literal)

```text
RetrievalMode = Literal["vector_only", "hybrid"]
```

Always explicit; never inferred implicitly from available components (FR-010, R7).

### 2.5 `TraversalStartSet`

Result of mapping an unfiltered vector pre-pass to graph traversal starts (research R5).

```text
TraversalStartSet
  prepass_chunk_ids: tuple[str, ...]       # vector rank order, unfiltered
  start_ids: tuple[str, ...]               # deduped, capped, mode-appropriate (doc id_str / provision / chunk)
  mode: str
  capped: bool
  empty: bool                              # True when prepass_chunk_ids or start_ids resolve to nothing
```

Helper: `build_traversal_starts(prepass_hits, mode, max_starts) -> TraversalStartSet` — pure function; unit-tested for the "never substitute ground truth" guard (FR-003g).

### 2.6 `HybridDiagnostics`

Per-case hybrid participation record (FR-003c).

```text
HybridDiagnostics
  traversal_mode: str
  traversal_start_ids: tuple[str, ...]
  traversal_visited_count: int
  whitelist_id_strs: tuple[str, ...]
  whitelist_empty: bool
  filtered_vector_seed_chunk_ids: tuple[str, ...]
  expansion_seed_count: int
  expansion_added_count: int             # len(ordered_context_chunks) - overlap with seeds
  expansion_empty_added: bool
  extra_traversal_chunk_ids: tuple[str, ...]
  overlays_available: bool
  prepass_empty_start: bool
  hybrid_unavailable_reason: str | None  # None when hybrid fully ran
```

### 2.7 `HybridFusionResult`

Output of the pure fusion helper (research R6).

```text
HybridFusionResult
  retrieved_chunk_ids: tuple[str, ...]   # seeds -> expansion -> extra traversal, keep-first dedup
  seed_count: int
  expansion_added: tuple[str, ...]
  traversal_added: tuple[str, ...]
```

Helper: `fuse_hybrid_chunk_ids(seed_chunk_ids, expansion_chunk_ids, traversal_chunk_ids) -> HybridFusionResult` — pure, unit tested for fusion order + dedupe semantics.

### 2.8 `RetrievalCaseResult` (per-case score row; persisted)

Unifies vector-only and hybrid case output shape so artifacts are directly comparable (FR-013, FR-014, FR-020).

```text
RetrievalCaseResult
  qa_id: str
  mode: RetrievalMode
  question: str
  category: str | None
  difficulty: str | None
  answer_type: str | None
  ground_truth_chunk_ids: list[str]
  retrieved_chunk_ids: list[str]
  metrics: dict[str, float]              # e.g. {"recall@5": ..., "hit@5": ..., "mrr@5": ..., "ndcg@5": ..., "jaccard@5": ...} for every configured k
  hybrid_diagnostics: HybridDiagnostics | None   # None for vector_only
  error: str | None                      # set + case still recorded when retrieval raised (FR-015)
```

Helper: `build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, top_k_list) -> dict[str, float]` calls `src/evaluation/metrics.py` functions per k — pure, unit tested (FR-004, FR-006, SC-003).

### 2.9 `ModeRunSummary` (aggregate; persisted)

```text
ModeRunSummary
  mode: RetrievalMode
  config: dict                            # EvalRunConfig snapshot
  total_rows: int
  evaluated: int
  skipped_unanswerable: int
  skipped_missing_ground_truth: int
  error_count: int
  overall: dict                           # aggregate() output over metric_keys
  by_category: dict                       # aggregate_by(rows, "category", metric_keys)
  by_difficulty: dict                     # aggregate_by(rows, "difficulty", metric_keys)
  by_answer_type: dict                    # aggregate_by(rows, "answer_type", metric_keys)
  hybrid_available: bool                  # False + reason for vector_only-only runs when hybrid requested but unavailable
  hybrid_unavailable_reason: str | None
```

### 2.10 `ComparisonSummary` (dual-mode; persisted only when both modes ran)

```text
ComparisonSummary
  shared_top_k: list[int]
  vector_only: ModeRunSummary | None
  hybrid: ModeRunSummary | None
  hybrid_available: bool
  rows: list[dict]                        # one row per metric@k: {"metric": "recall@5", "vector_only": 0.62, "hybrid": 0.71}
```

Helper: `build_comparison(vector_summary, hybrid_summary, top_k_list) -> ComparisonSummary` — pure; handles hybrid-unavailable branch explicitly (FR-019, SC-004, SC-007).

### 2.11 `EvaluationArtifacts` (paths written to disk)

```text
EvaluationArtifacts
  out_dir: Path
  vector_only_cases: Path | None          # vector_only_cases.jsonl
  vector_only_metrics: Path | None        # vector_only_metrics.json
  vector_only_report: Path | None         # vector_only_report.md
  hybrid_cases: Path | None
  hybrid_metrics: Path | None
  hybrid_report: Path | None
  comparison_metrics: Path | None         # comparison_metrics.json
  comparison_report: Path | None          # comparison.md
```

## 3. Relationships and pipeline mapping

```text
qa_final.jsonl rows
  -> select_eligible_cases()               -> EligibilitySummary (eligible: list[EligibleCase])

vector_only path (per EligibleCase):
  VectorRetriever.retrieve(question, filter_profile=..., top_k=..., ...)
    -> RetrievedChunk[] -> retrieved_chunk_ids
  build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, top_k_list)
    -> RetrievalCaseResult(mode="vector_only")

hybrid path (per EligibleCase), GRAPH_MODULE §10:
  1. VectorRetriever.retrieve(question, unfiltered, top_n=PREPASS_TOP_N)   # pre-pass, never GT
       -> prepass hits
  2. build_traversal_starts(prepass hits, mode, max_starts) -> TraversalStartSet
  3. KnowledgeGraphFacade.traverse(graph, start_id, mode, max_depth) for each start
       -> TraversalResult[] -> visited ids / whitelist id_strs
       (+ optional build_overlay_bundle / build_graph_guided_filter -> GraphGuidedFilter)
  4. VectorRetriever.retrieve(question, id_str_filter=whitelist, filter_profile="graph_guided", ...)
       -> filtered vector seed hits -> filtered_vector_seed_chunk_ids
  5. GraphExpansion.expand(filtered_vector_seed_chunk_ids, max_hop, max_context)
       -> ExpansionResult -> ordered_context_chunks
  6. fuse_hybrid_chunk_ids(filtered_vector_seed_chunk_ids, ordered_context_chunks, extra_traversal_chunk_ids)
       -> HybridFusionResult -> retrieved_chunk_ids
  7. build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, top_k_list)
       -> RetrievalCaseResult(mode="hybrid", hybrid_diagnostics=HybridDiagnostics(...))

Per mode:
  list[RetrievalCaseResult] -> aggregate() / aggregate_by() -> ModeRunSummary
  write_jsonl(cases) + write_json(metrics) + markdown report -> EvaluationArtifacts

Both modes complete:
  build_comparison(vector_summary, hybrid_summary, top_k_list) -> ComparisonSummary
    -> comparison.md / comparison_metrics.json
```

## 4. Validation rules (from FRs / Edge Cases)

- `select_eligible_cases` MUST classify every row into exactly one of: eligible, `skipped_unanswerable`, `skipped_missing_ground_truth` — never silently drop a row (FR-007, SC-006).
- `build_traversal_starts` MUST NOT read `ground_truth.*` fields; input is restricted to pre-pass retrieval hits only (FR-003g).
- `fuse_hybrid_chunk_ids` MUST preserve first-seen order across the three input lists and MUST NOT re-sort by any score (FR-003d, R6).
- A `RetrievalCaseResult` with `mode="hybrid"` MUST always carry a non-`None` `hybrid_diagnostics`; a `mode="vector_only"` row MUST have `hybrid_diagnostics=None` (FR-010).
- Hybrid case construction MUST refuse to proceed past traversal/whitelist/expansion when a required graph service could not be constructed for the run and MUST instead set `ModeRunSummary.hybrid_available=False` with `hybrid_unavailable_reason` set at the run level; it MUST NOT emit `RetrievalCaseResult(mode="hybrid")` rows built from an unfiltered fallback (FR-011, R7).
- `EvaluationArtifacts` paths MUST be namespaced by mode (`vector_only_*` / `hybrid_*`) so files are never ambiguous (FR-010, US4 AC3).
- Writers MUST NOT touch `qa_path` (read-only) (FR-017).
- `k` values greater than `len(retrieved_chunk_ids)` MUST be handled by `src/evaluation/metrics.py` semantics unchanged (Edge Cases, FR-006).

## 5. State machine for hybrid availability

```text
[start] -> check graph pickle / JSONL rebuild opt-in
  -> graph unavailable ---------------------------> hybrid_available=False, reason="graph_unavailable"
  -> graph available
       -> build GraphTraversal ------ fails -------> hybrid_available=False, reason="traversal_unavailable"
       -> build GraphExpansion ------ fails -------> hybrid_available=False, reason="expansion_unavailable"
       -> both available -> hybrid_available=True
            -> per case: prepass empty starts -> hybrid-failed-for-case (still not GT substitution),
               case recorded with error/empty diagnostics, does not flip run-level hybrid_available
```

Vector-only path has no equivalent gate: it must remain runnable whenever the FAISS index artifacts load (FR-011).

## 6. Out of scope entities

- E2E generation/judge rows (`exact_match`, `token_f1`, `rouge_l`, judge scores) — remain in `scripts/evaluate_e2e.py`'s domain only (FR-018).
- Index-building / QA-synthesis entities — not reproduced here; this notebook only reads existing artifacts.
- A new re-ranker over the fused hybrid list — explicitly not introduced (R6).
