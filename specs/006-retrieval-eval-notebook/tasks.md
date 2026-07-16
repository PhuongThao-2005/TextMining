# Tasks: Retrieval Evaluation Notebook

**Input**: Design documents from `/specs/006-retrieval-eval-notebook/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: Required for the new pure helpers per plan.md Testing strategy and research R12 — `tests/test_evaluation_eligibility.py`, `tests/test_evaluation_hybrid_fusion.py`, `tests/test_evaluation_retrieval_eval_report.py`. No `contracts/` directory (in-process notebook + module calls, not a network API). Full acceptance is manual/quickstart validation (V1–V8) against real FAISS + graph artifacts.

**Organization**: Tasks grouped by user story. Thin notebook orchestration over existing `src/evaluation`, `src/retrieval`, `src/knowledge_graph` modules (unmodified) plus three new small pure helper modules under `src/evaluation/`. No changes to `scripts/evaluate_retrieval.py`, `scripts/evaluate_e2e.py`, `src/evaluation/retriever_factory.py`'s Qdrant contract, or `notebooks/faiss_retrieval_ready.ipynb`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/cells/helpers with no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project under `L_RAG/`: `src/`, `notebooks/`, `scripts/`, `tests/` at repository root (per plan.md)
- Paths below relative to `L_RAG/`
- Primary deliverable: [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) (NEW — separate from [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb), per research R1)
- New helper modules (flat under `src/evaluation/`, per research R8 / plan.md Project Structure):
  - [`src/evaluation/eligibility.py`](../../src/evaluation/eligibility.py)
  - [`src/evaluation/hybrid_fusion.py`](../../src/evaluation/hybrid_fusion.py)
  - [`src/evaluation/retrieval_eval_report.py`](../../src/evaluation/retrieval_eval_report.py)
- New tests (flat convention matching [`tests/test_evaluation_metrics.py`](../../tests/test_evaluation_metrics.py)):
  - `tests/test_evaluation_eligibility.py`
  - `tests/test_evaluation_hybrid_fusion.py`
  - `tests/test_evaluation_retrieval_eval_report.py`
- Consume only (do not reimplement): [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py), [`src/evaluation/io_utils.py`](../../src/evaluation/io_utils.py), [`src/retrieval/retriever.py`](../../src/retrieval/retriever.py) `VectorRetriever`, [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py), [`src/retrieval/embeddings.py`](../../src/retrieval/embeddings.py) `SentenceTransformerEmbedder`, [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py) `KnowledgeGraphFacade`, [`src/knowledge_graph/traversal.py`](../../src/knowledge_graph/traversal.py) `GraphTraversal`, [`src/knowledge_graph/expansion.py`](../../src/knowledge_graph/expansion.py) `GraphExpansion`, [`src/knowledge_graph/context_schema.py`](../../src/knowledge_graph/context_schema.py) `GraphGuidedFilter`/`EvidenceContext`, [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) `load_knowledge_graph`
- Reference pattern (do not modify): [`scripts/evaluate_retrieval.py`](../../scripts/evaluate_retrieval.py) eligibility/report shape

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Orient the new notebook and confirm the module surfaces it will consume are importable, without writing any evaluation logic yet

- [ ] T001 Create [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) skeleton: title/markdown overview stating this is the dedicated retrieval-evaluation notebook (distinct from `faiss_retrieval_ready.ipynb`), section outline (Config → Preflight → Vector-only → Hybrid → Comparison → Artifacts), and a pointer to [`specs/006-retrieval-eval-notebook/quickstart.md`](quickstart.md) (FR-001)
- [ ] T002 [P] Confirm import surface for the notebook: `VectorRetriever`, `SQLitePayloadFaissVectorStore`, `SentenceTransformerEmbedder` from `src/retrieval/*`; `KnowledgeGraphFacade`, `GraphTraversal`, `GraphExpansion`, `GraphGuidedFilter` from `src/knowledge_graph/*`; `read_jsonl`/`write_jsonl`/`write_json`/`qa_id` from [`src/evaluation/io_utils.py`](../../src/evaluation/io_utils.py); `recall_at_k`/`hit_at_k`/`mrr_at_k`/`ndcg_at_k`/`jaccard_at_k`/`aggregate`/`aggregate_by` from [`src/evaluation/metrics.py`](../../src/evaluation/metrics.py) (research R2, R3, R4)
- [ ] T003 [P] Verify benchmark path resolution policy (research R10): default `data/benchmark/qa_final.jsonl`; if missing and `data/qa_final.jsonl` exists, single explicit warning + fallback only when `QA_PATH` was not overridden; otherwise fail clearly (Edge Cases, FR-005, FR-016)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared pure helpers that both US1 (vector-only) and US2 (hybrid) build their per-case scoring on — **must complete before either mode's run cell can score a single case**

**⚠️ CRITICAL**: No US1/US2 work can produce a `RetrievalCaseResult` until eligibility filtering and the metric-row builder exist and are unit tested

- [ ] T004 [P] Create [`src/evaluation/eligibility.py`](../../src/evaluation/eligibility.py) with `EligibleCase` and `EligibilitySummary` dataclasses per [`data-model.md`](data-model.md) §2.2–§2.3
- [ ] T005 Implement `select_eligible_cases(rows: list[dict], sample_limit: int | None) -> EligibilitySummary` in `eligibility.py`, mirroring [`scripts/evaluate_retrieval.py`](../../scripts/evaluate_retrieval.py)'s skip logic (unanswerable / missing ground-truth `chunk_ids`), classifying every row into exactly one of eligible / `skipped_unanswerable` / `skipped_missing_ground_truth` (FR-007, data-model §4, SC-006)
- [ ] T006 [P] Create `tests/test_evaluation_eligibility.py`: unit tests for unanswerable skip, missing-GT skip, `sample_limit` truncation, and that `total_rows == eligible + skipped_unanswerable + skipped_missing_ground_truth` for a mixed fixture (FR-007, SC-006)
- [ ] T007 [P] Create [`src/evaluation/retrieval_eval_report.py`](../../src/evaluation/retrieval_eval_report.py) with `RetrievalMode` literal, `HybridDiagnostics`, and `RetrievalCaseResult` dataclasses per [`data-model.md`](data-model.md) §2.4, §2.6, §2.8
- [ ] T008 Implement `build_case_metrics_row(retrieved_chunk_ids: list[str], ground_truth_chunk_ids: set[str], top_k_list: list[int]) -> dict[str, float]` in `retrieval_eval_report.py` as a thin wrapper calling `recall_at_k`/`hit_at_k`/`mrr_at_k`/`ndcg_at_k`/`jaccard_at_k` per k from `metrics.py` (FR-004, FR-006, data-model §2.8)
- [ ] T009 [P] Create `tests/test_evaluation_retrieval_eval_report.py` (initial cases): unit tests for `build_case_metrics_row` against mocked retrieved/ground-truth ID lists, including `k > len(retrieved_chunk_ids)` truncation semantics matching `metrics.py` (FR-006, Edge Cases, SC-003)

**Checkpoint**: `select_eligible_cases` and `build_case_metrics_row` exist, are unit tested, and are ready for both US1 and US2 run cells

---

## Phase 3: User Story 1 - Run vector-only retrieval evaluation on the frozen QA benchmark (Priority: P1) 🎯 MVP

**Goal**: Notebook config + preflight + vector-only run cell scores eligible QA cases via the production FAISS stack using only `metrics.py`/`aggregate`/`aggregate_by`, with explicit skip counters and no ad-hoc metric formulas

**Independent Test**: With FAISS index artifacts and `data/benchmark/qa_final.jsonl` available, run the vector-only section with `SAMPLE_LIMIT=20`; confirm per-case scores plus aggregate metrics at every configured k, with unanswerable/missing-GT rows skipped and counted separately (quickstart V1, SC-001, SC-003, SC-006)

### Implementation for User Story 1

- [ ] T010 [US1] Add config cell to [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) exposing `QA_PATH`, `OUT_DIR`, `TOP_K_LIST`, `SAMPLE_LIMIT`, `FILTER_PROFILE`, `SCORE_THRESHOLD`, `TOP_K_RETRIEVE`, `TOP_N`, `INDEX_DIR`, `EMBEDDING_MODEL`, `RUN_VECTOR_ONLY`, `RUN_HYBRID` per [`quickstart.md`](quickstart.md) config cell / [`data-model.md`](data-model.md) §2.1 `EvalRunConfig`, with path resolution that works from project root or `notebooks/` (FR-009, FR-016, research R13)
- [ ] T011 [US1] Add preflight cell: verify `QA_PATH` exists (apply R10 fallback/warning rule), verify `INDEX_DIR` contains `payloads.jsonl` + FAISS index files matching `EMBEDDING_MODEL`; stop with a clear message before any retrieval if either is missing (Edge Cases, quickstart "Expected inputs" table)
- [ ] T012 [US1] Add vector-only run cell: construct `SQLitePayloadFaissVectorStore` + `SentenceTransformerEmbedder` + `VectorRetriever` over `INDEX_DIR`/`EMBEDDING_MODEL`; call `select_eligible_cases` on `read_jsonl(QA_PATH)` rows with `SAMPLE_LIMIT`; iterate eligible cases calling `VectorRetriever.retrieve(question, filter_profile=FILTER_PROFILE, top_k=TOP_K_RETRIEVE, top_n=TOP_N, score_threshold=SCORE_THRESHOLD)` (FR-002, FR-007, data-model §3)
- [ ] T013 [US1] Wrap each case's retrieval call in try/except: on exception, record `error` on the case and continue to the next case rather than aborting the run (FR-015, Edge Cases, quickstart V7)
- [ ] T014 [US1] For each successfully retrieved case, build `RetrievalCaseResult(mode="vector_only", hybrid_diagnostics=None, ...)` via `build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, TOP_K_LIST)` (FR-006, FR-010, data-model §4)
- [ ] T015 [US1] Aggregate `ModeRunSummary` for vector-only via `aggregate(rows, metric_keys)` (overall) and `aggregate_by(rows, field, metric_keys)` for `category`, `difficulty`, `answer_type` (FR-008, data-model §2.9)
- [ ] T016 [US1] Print evaluated / `skipped_unanswerable` / `skipped_missing_ground_truth` / error counts and the overall metrics table in the notebook cell output (FR-014, US1 AC3)

**Checkpoint**: Vector-only evaluation runs end to end on a sample or full benchmark and produces in-notebook results — MVP deliverable independently testable

---

## Phase 4: User Story 2 - Run hybrid retrieval evaluation with the same metrics and benchmark (Priority: P1)

**Goal**: Hybrid run cell follows GRAPH_MODULE §10 as the primary sequence (seed-derived traversal starts → whitelist → filtered vector search → GraphExpansion → fusion), scores with the same metric suite, and never silently falls back to unlabeled vector-only results

**Independent Test**: With vector index and knowledge-graph inputs available, run the hybrid section on a sample of answerable QA rows; confirm each case is labeled `hybrid`, shows GraphTraversal and GraphExpansion participation (or explicit empty/no-op diagnostics), is scored with the same metrics, and that hybrid-unavailable conditions are surfaced explicitly rather than silently scored as hybrid (quickstart V2, V4, V6; SC-002, SC-007)

### Implementation for User Story 2

- [ ] T017 [US2] Create [`src/evaluation/hybrid_fusion.py`](../../src/evaluation/hybrid_fusion.py) with `TraversalStartSet` dataclass per [`data-model.md`](data-model.md) §2.5
- [ ] T018 [US2] Implement `build_traversal_starts(prepass_hits, mode, max_starts) -> TraversalStartSet` in `hybrid_fusion.py`: deterministic mapping of unfiltered vector pre-pass hits to graph start IDs (document `id_str` for cross-document modes, document/provision/chunk for `structure`), dedupe keep-first, cap at `max_starts`, set `empty=True` when no usable starts resolve; function signature MUST NOT accept or read any `ground_truth.*` field (research R5, FR-003g)
- [ ] T019 [US2] Add `HybridFusionResult` dataclass and implement `fuse_hybrid_chunk_ids(seed_chunk_ids, expansion_chunk_ids, traversal_chunk_ids) -> HybridFusionResult` in `hybrid_fusion.py`: append-unique across seeds → expansion → extra traversal, keep-first dedupe, no re-ranking (FR-003d, research R6, data-model §2.7)
- [ ] T020 [US2] Create `tests/test_evaluation_hybrid_fusion.py`: unit tests for `build_traversal_starts` (dedupe, cap, empty-start flag, and a test asserting the function has no code path that reads a `ground_truth` key) and `fuse_hybrid_chunk_ids` (fusion order, dedupe keep-first, seed rank preserved) (FR-003d, FR-003g, research R5/R6)
- [ ] T021 [US2] Extend the config cell (T010) with hybrid fields: `GRAPH_PICKLE_PATH`, `V2_DATA_DIR`, `ALLOW_JSONL_GRAPH_REBUILD` (default `False`), `TRAVERSAL_MODE`, `TRAVERSAL_MAX_DEPTH` (default 3), `PREPASS_TOP_N`, `MAX_TRAVERSAL_STARTS`, `HYBRID_MAX_HOP`, `HYBRID_MAX_CONTEXT`, `AS_OF_DATE`, `LOCAL_EXPAND_UNITS` (default `False`) per [`quickstart.md`](quickstart.md) / research R13
- [ ] T022 [US2] Add hybrid preflight/gate cell: attempt `KnowledgeGraphFacade.load_graph(GRAPH_PICKLE_PATH)` (pickle preferred; JSONL rebuild only if `ALLOW_JSONL_GRAPH_REBUILD=True`, research R9); attempt to construct `GraphTraversal` and `GraphExpansion` from the loaded graph; on any failure set run-level `hybrid_available=False` with `hybrid_unavailable_reason` in `{"graph_unavailable", "traversal_unavailable", "expansion_unavailable"}` per the state machine in [`data-model.md`](data-model.md) §5 (FR-011, research R7)
- [ ] T023 [US2] Add hybrid run cell implementing the GRAPH_MODULE §10 sequence per eligible case (only when `hybrid_available=True`): (1) unfiltered `VectorRetriever.retrieve(question, top_n=PREPASS_TOP_N)` pre-pass; (2) `build_traversal_starts(prepass hits, TRAVERSAL_MODE, MAX_TRAVERSAL_STARTS)`; (3) `KnowledgeGraphFacade.traverse(graph, start_id, TRAVERSAL_MODE, TRAVERSAL_MAX_DEPTH)` per start, collecting visited ids; (4) `build_overlay_bundle`/`build_graph_guided_filter` to produce the whitelist `GraphGuidedFilter`; (5) filtered `VectorRetriever.retrieve(question, id_str_filter=whitelist, filter_profile="graph_guided", top_k=TOP_K_RETRIEVE, top_n=TOP_N)`; (6) `GraphExpansion.expand(filtered_seed_chunk_ids, HYBRID_MAX_HOP, HYBRID_MAX_CONTEXT)`; (7) `fuse_hybrid_chunk_ids(filtered_seed_chunk_ids, ordered_context_chunks, extra_traversal_chunk_ids)` (FR-003f, FR-003a, FR-003b, data-model §3)
- [ ] T024 [US2] Build a `HybridDiagnostics` record per case: `traversal_mode`, `traversal_start_ids`, `traversal_visited_count`, `whitelist_id_strs`, `whitelist_empty`, `filtered_vector_seed_chunk_ids`, `expansion_seed_count`, `expansion_added_count`, `expansion_empty_added`, `extra_traversal_chunk_ids`, `overlays_available`, `prepass_empty_start`, `hybrid_unavailable_reason` (FR-003c, data-model §2.6)
- [ ] T025 [US2] Handle the empty-pre-pass-starts case explicitly: when `TraversalStartSet.empty=True`, set `prepass_empty_start=True` on diagnostics, do not substitute `ground_truth.*` IDs, and either continue scoring on a legitimate remaining path or mark that case failed — never widen to full-corpus search under a hybrid label (Edge Cases, FR-003g, quickstart V6)
- [ ] T026 [US2] Wrap each case's hybrid pipeline in try/except (per T013 pattern); on success build `RetrievalCaseResult(mode="hybrid", hybrid_diagnostics=..., retrieved_chunk_ids=fusion_result.retrieved_chunk_ids)` via `build_case_metrics_row`; on exception record `error` and continue (FR-015, FR-010)
- [ ] T027 [US2] Aggregate hybrid `ModeRunSummary` via `aggregate`/`aggregate_by` (same slices as US1) plus run-level `hybrid_available`/`hybrid_unavailable_reason`; when `hybrid_available=False`, summary MUST NOT contain metrics computed from an unfiltered vector-only substitution (FR-011, data-model §2.9, SC-007)
- [ ] T028 [US2] Print hybrid evaluated / skipped / error counts and, when unavailable, an explicit "hybrid unavailable: `<reason>`" message instead of any metrics table (FR-011, US2 AC3, quickstart V4)

**Checkpoint**: Hybrid path runs the full GRAPH_MODULE §10 sequence when prerequisites are met, and fails clearly (never silently) when they are not — co-equal P1 deliverable alongside US1

---

## Phase 5: User Story 3 - Compare vector-only vs hybrid side by side (Priority: P2)

**Goal**: One notebook session runs both modes on the same QA subset and shows a side-by-side comparison of overall metrics at shared k cutoffs, plus per-mode evaluated/skipped counts

**Independent Test**: Run both evaluation modes on the same configured sample/full set; confirm the notebook shows overall metrics for vector-only and hybrid in a comparable table with counts, and that when hybrid is unavailable the comparison still reports vector-only results plus an explicit unavailable note (quickstart V3, V4; SC-004, SC-007)

### Implementation for User Story 3

- [ ] T029 [US3] Add `ComparisonSummary` dataclass and implement `build_comparison(vector_summary, hybrid_summary, top_k_list) -> ComparisonSummary` in [`src/evaluation/retrieval_eval_report.py`](../../src/evaluation/retrieval_eval_report.py) per [`data-model.md`](data-model.md) §2.10: one row per `metric@k` with `vector_only`/`hybrid` values; explicit `hybrid_available` branch when hybrid did not run or was unavailable (FR-019, research R6)
- [ ] T030 [US3] Extend `tests/test_evaluation_retrieval_eval_report.py`: unit tests for `build_comparison` with both modes present, and with `hybrid_summary=None`/`hybrid_available=False` (confirm no fabricated hybrid rows) (SC-007)
- [ ] T031 [US3] Add comparison cell to [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb): display the shared-k metric table for both modes plus evaluated/skipped counts per mode; when hybrid is unavailable, show vector-only results with a clear "hybrid comparison unavailable: `<reason>`" note instead of inventing hybrid scores (US3 AC1–AC3, quickstart V3/V4)

**Checkpoint**: Dual-mode comparison view works whenever both modes ran, and degrades explicitly (never silently) when hybrid could not run

---

## Phase 6: User Story 4 - Persist evaluation artifacts for review and reproducibility (Priority: P2)

**Goal**: Every completed mode writes case-level results, aggregate metrics JSON, and a markdown report under a configurable output directory, mode-namespaced so results are never ambiguous

**Independent Test**: After a successful run, confirm `OUT_DIR` contains case-level JSONL, metrics JSON, and a markdown report per completed mode (and comparison files when both ran), each including run configuration and benchmark path, readable without re-running the notebook (US4 AC1–AC3, SC-005)

### Implementation for User Story 4

- [ ] T032 [US4] Implement `write_case_jsonl(path, cases)`, `write_metrics_json(path, summary_dict)` (embedding the `EvalRunConfig` snapshot per FR-009/R13), and `write_markdown_report(path, summary_dict, metric_keys)` in [`src/evaluation/retrieval_eval_report.py`](../../src/evaluation/retrieval_eval_report.py), reusing the table-building pattern from [`scripts/evaluate_retrieval.py`](../../scripts/evaluate_retrieval.py)'s `write_report`/`_group_table` (FR-013, research R2/R8/R11)
- [ ] T033 [US4] Wire vector-only run cell (US1) to call the T032 writers producing `vector_only_cases.jsonl`, `vector_only_metrics.json`, `vector_only_report.md` under `OUT_DIR` (data-model §2.11, US4 AC1)
- [ ] T034 [US4] Wire hybrid run cell (US2) to call the T032 writers producing `hybrid_cases.jsonl`, `hybrid_metrics.json`, `hybrid_report.md` under `OUT_DIR` when hybrid ran; when `hybrid_available=False`, write only an availability/reason note, never a fabricated hybrid table (data-model §2.11, FR-011)
- [ ] T035 [US4] Wire comparison cell (US3) to call the T032 writers producing `comparison_metrics.json` / `comparison.md` under `OUT_DIR` only when both modes completed (data-model §2.11, US4 AC3)
- [ ] T036 [US4] Confirm each markdown report includes `QA_PATH`, mode label, filter/top-k configuration, evaluated/skipped/error counts, and metric tables so a reviewer needs no notebook kernel (US4 AC2, SC-005)
- [ ] T037 [US4] Confirm none of the T032–T035 writers open `QA_PATH` in write mode or otherwise mutate the frozen benchmark file (FR-017, Edge Cases)

**Checkpoint**: All completed-mode artifacts are written, mode-namespaced, and reviewable from disk alone

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety, full quickstart acceptance, and requirements traceability

- [ ] T038 [P] Run `pytest tests/test_evaluation_eligibility.py tests/test_evaluation_hybrid_fusion.py tests/test_evaluation_retrieval_eval_report.py tests/test_evaluation_metrics.py -q` and confirm all pass (plan.md Implementation Outline step 6)
- [ ] T039 [P] Run existing regression suites to confirm no incidental breakage: `pytest tests/ -k "retrieval or knowledge_graph or evaluation" -q`
- [ ] T040 Execute quickstart validation scenarios V1–V8 against real FAISS index artifacts and, where available, a real graph pickle: vector-only happy path (V1), hybrid happy path (V2), dual-mode comparison (V3), hybrid unavailable while vector-only still runs (V4), unanswerable/missing-GT rows never scored (V5), empty pre-pass starts (V6), per-case error does not abort the run (V7), path portability from project root and `notebooks/` (V8) — fix residual notebook gaps found
- [ ] T041 [P] Confirm no changes were made to [`scripts/evaluate_retrieval.py`](../../scripts/evaluate_retrieval.py), [`scripts/evaluate_e2e.py`](../../scripts/evaluate_e2e.py), [`src/evaluation/retriever_factory.py`](../../src/evaluation/retriever_factory.py)'s Qdrant-only contract, or [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (plan.md Structure Decision)
- [ ] T042 [P] Confirm end-to-end generation metrics (exact match, token F1, ROUGE-L, judge scores) do not appear anywhere in [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) (FR-018, "Out of scope checks")
- [ ] T043 Fill in the Requirements Traceability table below against the final implementation and confirm no FR/SC is unmapped

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** US1 and US2 (both need `select_eligible_cases` and `build_case_metrics_row`)
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP vector-only path
- **User Story 2 (Phase 4)**: Depends on Foundational; independent of US1's notebook cells but shares the config cell (T010) which US1 creates first — reuses the same eligible-case iteration approach
- **User Story 3 (Phase 5)**: Depends on US1 and US2 (needs both `ModeRunSummary` objects to compare)
- **User Story 4 (Phase 6)**: Depends on US1 (T014–T016), US2 (T026–T028), and US3 (T029) producing the summaries/rows to persist
- **Polish (Phase 7)**: Depends on desired user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — vector-only MVP, no dependency on US2
- **User Story 2 (P1)**: After Phase 2 — co-equal P1; independent graph/traversal/fusion logic, but notebook-cell work follows T010's config cell
- **User Story 3 (P2)**: After US1 and US2 both produce `ModeRunSummary`
- **User Story 4 (P2)**: After US1/US2/US3 produce the data structures to write; can start writer-helper implementation (T032) in parallel with US1/US2 finishing, but wiring (T033–T035) needs the corresponding summaries
- Note: unlike feature 005, US1 and US2 in this feature are **both P1** and largely independent after Phase 2 — either can be built first

### Within Each User Story

- Dataclasses/helpers before the notebook cells that call them
- Preflight/gate before run cells
- Run cell (retrieval) before per-case metric-row construction
- Per-case results before mode aggregation
- Mode aggregation before persistence (US4) and comparison (US3)

### Parallel Opportunities

- Phase 1: T002 and T003 parallel after T001
- Phase 2: T004→T005→T006 sequential within eligibility; T007→T008→T009 sequential within report module; the two chains (eligibility vs report) can run in parallel
- Phase 3: T010–T011 sequential (config before preflight); T012–T016 mostly sequential (shared per-case loop)
- Phase 4: T017–T020 (hybrid_fusion.py + tests) can proceed in parallel with T010–T016 (US1) once Phase 2 is done; T021–T028 sequential (shared per-case hybrid pipeline)
- Phase 5: T029–T030 parallel with each other; T031 after both
- Phase 6: T032 first; T033/T034/T035 parallelizable once their respective summaries exist; T036–T037 after T033–T035
- Phase 7: T038–T039 parallel; T040 after T038/T039 pass; T041–T042 parallel audits; T043 last

---

## Parallel Example: Foundational helpers (Phase 2)

```bash
# Eligibility chain
Task: "Create EligibleCase/EligibilitySummary dataclasses in src/evaluation/eligibility.py"
Task: "Implement select_eligible_cases() mirroring evaluate_retrieval.py skip logic"
Task: "Unit test eligibility skip/counter behavior in tests/test_evaluation_eligibility.py"

# Report chain (parallel with eligibility chain)
Task: "Create RetrievalMode/HybridDiagnostics/RetrievalCaseResult dataclasses in src/evaluation/retrieval_eval_report.py"
Task: "Implement build_case_metrics_row() wrapping metrics.py"
Task: "Unit test build_case_metrics_row() in tests/test_evaluation_retrieval_eval_report.py"
```

---

## Parallel Example: US1 + US2 after Foundational

```bash
# US1 vector-only (notebook cells)
Task: "Config + preflight cells for vector-only path"
Task: "Vector-only run cell + per-case error handling"
Task: "Vector-only aggregation + count/metrics display"

# US2 hybrid (pure helpers first, independent of US1 cells)
Task: "hybrid_fusion.py: TraversalStartSet + build_traversal_starts()"
Task: "hybrid_fusion.py: HybridFusionResult + fuse_hybrid_chunk_ids()"
Task: "tests/test_evaluation_hybrid_fusion.py: order/dedupe/leakage guard"
```

---

## Implementation Strategy

### MVP First (US1)

1. Complete Phase 1: Setup (notebook skeleton, import surface check, benchmark path check)
2. Complete Phase 2: Foundational (`eligibility.py`, `retrieval_eval_report.py` core dataclasses + `build_case_metrics_row`, unit tests)
3. Complete Phase 3: User Story 1 (config, preflight, vector-only run, aggregation, counts/metrics display)
4. **STOP and VALIDATE**: quickstart V1 + V5 + V7 (happy path, skip counters, per-case error resilience)
5. Demo: vector-only evaluation sample producing correct metrics with skip counters

### Incremental Delivery

1. Setup + Foundational → shared eligibility/metric-row helpers ready
2. Add US1 → vector-only MVP (SC-001, SC-003, SC-006)
3. Add US2 → hybrid co-equal P1 (SC-002, SC-007), no-silent-fallback guarantee
4. Add US3 → dual-mode comparison (SC-004)
5. Add US4 → persisted artifacts for reproducibility (SC-005)
6. Polish → regression pytest + full quickstart V1–V8 + traceability

### Suggested MVP Task Cut Line

T001–T016 (Setup + Foundational + US1). US2/US3/US4 and full polish follow without blocking the first vector-only evaluation sample; because US2 is also P1, it should follow immediately rather than being deferred like a P2/P3 story.

### Parallel Team Strategy

With multiple developers after Foundational:

- Developer A: US1 config/preflight/run cell + aggregation/display
- Developer B: US2 `hybrid_fusion.py` + tests, then hybrid preflight/run cell + diagnostics
- Developer C: US4 writer helpers (T032) in parallel, wiring in as US1/US2 summaries become available; then US3 comparison builder once both summaries exist

Integrate in notebook cell order: Config → Preflight (vector + hybrid) → Vector-only run → Hybrid run → Comparison → Artifacts confirmation.

---

## Requirements Traceability (summary)

| Requirement | Primary tasks |
| --- | --- |
| FR-001 dedicated notebook | T001 |
| FR-002 vector-only evaluation | T012–T016 |
| FR-003 hybrid = Traversal + Expansion | T017–T028 |
| FR-003a GraphExpansion per §7 | T023 |
| FR-003b GraphTraversal per §6 | T022, T023 |
| FR-003c hybrid participation diagnostics | T024 |
| FR-003d fusion order/dedupe | T019, T023 |
| FR-003e no invented semantics; explicit empty filters | T022, T025, T028 |
| FR-003f §10 primary sequence | T023 |
| FR-003g seed-derived starts, no GT leakage | T018, T020, T025 |
| FR-004 evaluation module only, no ad-hoc metrics | T008, T009, T014, T026 |
| FR-005 default QA path + override | T003, T010 |
| FR-006 recall/hit/mrr/ndcg/jaccard per k | T008, T014, T026 |
| FR-007 eligibility skip logic | T004–T006 |
| FR-008 aggregate by category/difficulty/answer_type | T015, T027 |
| FR-009 config section | T010, T021 |
| FR-010 explicit mode labeling | T014, T026, T034 |
| FR-011 no silent hybrid fallback | T022, T027, T028, T034 |
| FR-012 sample + full-run support | T010 |
| FR-013 persisted artifacts per mode | T032–T035 |
| FR-014 evaluated/skipped counts reported | T016, T028 |
| FR-015 per-case error continues run | T013, T026 |
| FR-016 path portability | T010, T040 (V8) |
| FR-017 benchmark file read-only | T037 |
| FR-018 E2E metrics out of scope | T042 |
| FR-019 side-by-side comparison | T029, T031 |
| FR-020 chunk_id-based GT matching | T008, T014, T026 |
| SC-001 vector-only sample ≥20 cases, all metrics | T012–T016, T040 (V1) |
| SC-002 hybrid sample, same metrics, explicit label | T023–T028, T040 (V2) |
| SC-003 100% scored via evaluation module | T008, T038 |
| SC-004 comparison shows both modes or explicit unavailable | T029–T031, T040 (V3/V4) |
| SC-005 reviewable artifacts without re-running | T032–T036 |
| SC-006 skip rows never scored | T005, T006, T040 (V5) |
| SC-007 hybrid-unavailable never mislabeled | T022, T027, T028, T034, T040 (V4) |

---

## Notes

- **[P]** tasks = different files/cells/helpers with no unfinished dependency
- **[USn]** label maps task to user story for traceability
- **Primary surface**: new [`notebooks/retrieval_eval.ipynb`](../../notebooks/retrieval_eval.ipynb) (research R1) — no changes to `faiss_retrieval_ready.ipynb`
- Three new pure helper modules under `src/evaluation/` (flat, no new package) per research R8; corresponding flat `tests/test_evaluation_*.py` files per research R12
- US1 and US2 are both P1 in this feature (unlike typical single-MVP ordering) — hybrid is co-equal to vector-only per spec.md's "Why this priority" rationale
- No silent hybrid fallback is enforced at three layers: the pure `build_traversal_starts` guard (no GT access), the run-level `hybrid_available` gate (T022), and the writer layer (T034 refuses to fabricate a hybrid table)
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Constitution alignment: shared identity `chunk_id → parent_unit_id → id_str` preserved end-to-end (II); every row classified, no silent drops (III); evaluation module is the sole metric source (VI); non-trivial logic extracted into small tested helpers (V)
