# Tasks: Vector-Only Retrieval Evaluation Notebook

**Input**: Design documents from `L_RAG/specs/008-vector-retrieval-eval-notebook/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/notebook-io-contract.md](./contracts/notebook-io-contract.md), [quickstart.md](./quickstart.md)

**Tests**: Not explicitly requested in the feature specification for the notebook itself, but FR-002a's `retriever_factory.py` extension is new `src/` logic and per constitution Principle V MUST ship with unit tests. Test tasks for that extension are therefore included; no test tasks are generated for the notebook file itself since notebooks are not natively pytest-collectible in this repo (per plan.md's Testing section).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project layout (per plan.md): `L_RAG/src/`, `L_RAG/tests/`, `L_RAG/notebooks/`, `L_RAG/data/`, `L_RAG/evaluation_runs/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the environment and create the notebook skeleton before any story-specific work begins.

- [X] T001 Confirm `L_RAG/data/qa_final.jsonl` exists and `L_RAG/pyproject.toml` dependencies (pytest, faiss-cpu, sentence-transformers, pandas) are installed in the active environment; note any gaps before proceeding.
- [X] T002 Create the new notebook file `L_RAG/notebooks/vector_retrieval_eval.ipynb` with a title/header cell clearly labeled "Vector-Only Retrieval Evaluation" (FR-001, FR-010), and an empty configuration cell placeholder (filled in Phase 3).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend `src/evaluation/retriever_factory.py` (FR-002a) so it can construct a FAISS-backed `VectorRetriever`. This is required by every user story's retrieval cell and MUST be complete, tested, and passing before any notebook story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Read current `L_RAG/src/evaluation/retriever_factory.py` and `L_RAG/src/retrieval/sqlite_faiss_store.py` to confirm the exact constructor signature of `SQLitePayloadFaissVectorStore.load(index_dir)` and `VectorRetriever.__init__` before making changes.
- [X] T004 Extend `RetrieverRuntimeConfig` in `L_RAG/src/evaluation/retriever_factory.py`: add `store: Literal["faiss", "qdrant"] = "faiss"` and `index_dir: str | Path = "data/faiss_index"` fields, keeping existing `qdrant_url`/`qdrant_api_key`/`collection_name` fields for backward compatibility with the Qdrant path.
- [X] T005 Extend `build_vector_retriever(runtime)` in `L_RAG/src/evaluation/retriever_factory.py`: when `runtime.store == "faiss"` (and not `runtime.dev_hashing`), construct the vector store via `SQLitePayloadFaissVectorStore.load(Path(runtime.index_dir))` and wire it into `VectorRetriever` the same way the existing Qdrant branch does; preserve the existing Qdrant branch when `runtime.store == "qdrant"`; preserve the existing `dev_hashing` smoke-test branch unchanged.
- [X] T006 Update `build_vector_retriever`'s error handling in `L_RAG/src/evaluation/retriever_factory.py` so a missing/invalid `index_dir` (i.e., `SQLitePayloadFaissVectorStore.load`'s `FileNotFoundError`) propagates as a clear, actionable error rather than being swallowed (FR-012).
- [X] T007 [P] Add unit tests in `L_RAG/tests/test_evaluation_retriever_factory.py` covering: (a) `store="faiss"` builds a retriever backed by `SQLitePayloadFaissVectorStore` given a valid `index_dir` fixture (reuse patterns from `L_RAG/tests/retrieval/test_sqlite_faiss_store.py` for constructing a minimal `index.faiss`/`payloads.jsonl` fixture), (b) a missing `index_dir` raises a clear error, (c) the existing `store="qdrant"` and `dev_hashing=True` branches still behave as before (regression coverage).
- [X] T008 Run `pytest L_RAG/tests/test_evaluation_retriever_factory.py -v` and confirm all new and existing tests pass before proceeding to Phase 3.

**Checkpoint**: `retriever_factory.py` supports FAISS-backed construction, is tested, and existing Qdrant/dev-hashing behavior is unchanged — user story implementation can now begin.

---

## Phase 3: User Story 1 - Run vector-only retrieval evaluation end-to-end in a notebook (Priority: P1) 🎯 MVP

**Goal**: A user can open the notebook, configure it, run all cells top to bottom against a populated local FAISS index directory (or the dev-hashing smoke path) and `data/qa_final.jsonl`, and see overall + breakdown metrics tables and per-case results, with an option to persist output.

**Independent Test**: Run the notebook top to bottom per Scenario A (smoke, `DEV_HASHING=True`) in [quickstart.md](./quickstart.md); confirm an overall metrics table and category/difficulty/answer_type breakdown tables are displayed, with no cell requiring knowledge-graph or hybrid-specific objects.

### Implementation for User Story 1

- [X] T009 [US1] Build the configuration cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb`: variables `QA_PATH` (default `data/qa_final.jsonl`), `TOP_K_LIST` (default `[1, 5, 10]`), `INDEX_DIR` (default `data/faiss_index/`), `MODEL_NAME` (default `intfloat/multilingual-e5-large`), `SCORE_THRESHOLD` (default `0.3`), `EXPAND_UNITS` (default `True`), `SAMPLE_LIMIT` (default `None`), `DEV_HASHING` (default `False`), `OUT_DIR` (default `evaluation_runs/vector_only/<run_id>/`) — per data-model.md §6 (FR-006).
- [X] T010 [US1] Add a QA-load cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb`: guard `QA_PATH` existence and raise/display a clear error naming the expected path if missing (FR-011), otherwise load rows via `evaluation.io_utils.read_jsonl`.
- [X] T011 [US1] Add an eligibility cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` calling `evaluation.eligibility.select_eligible_cases(rows, sample_limit=SAMPLE_LIMIT)` and displaying total/eligible/skipped-unanswerable/skipped-missing-ground-truth counts (FR-003, FR-007).
- [X] T012 [US1] Add a retriever-construction cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` building `RetrieverRuntimeConfig(store="faiss", index_dir=INDEX_DIR, model=MODEL_NAME, score_threshold=SCORE_THRESHOLD, expand_units=EXPAND_UNITS, dev_hashing=DEV_HASHING)` and calling `build_vector_retriever(...)` (from the Phase 2 extension), with the FAISS load/config failure guarded and surfaced as a clear error (FR-012).
- [X] T013 [US1] Add a retrieval + scoring loop cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb`: for each eligible case (freshly re-initialized `cases = []` per FR-014), call `retriever.retrieve(question, filter_profile=..., top_n=max(TOP_K_LIST))`, extract `retrieved_chunk_ids`, and build a `RetrievalCaseResult` via `evaluation.retrieval_eval_report.build_case_metrics_row(retrieved_chunk_ids, ground_truth_chunk_ids, TOP_K_LIST)` for each case (FR-004).
- [X] T014 [US1] Add a display cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` rendering the overall `aggregate(case_dicts, metric_keys)` table and `aggregate_by(..., "category"/"difficulty"/"answer_type", metric_keys)` breakdown tables via pandas (FR-005).
- [X] T015 [US1] Add a per-case display cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` showing, for each evaluated case, `qa_id`, question, ground-truth chunk IDs, retrieved chunk IDs, and computed per-k metrics (Acceptance Scenario 2 of US1).
- [X] T016 [US1] Add an optional persistence cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` that, when triggered, calls `evaluation.retrieval_eval_report.write_case_jsonl(out_dir / "retrieval_cases.jsonl", cases)` and `write_metrics_json(out_dir / "retrieval_metrics.json", summary, run_config)` under a fresh `OUT_DIR/<run_id>/` directory (FR-008), matching [contracts/notebook-io-contract.md](./contracts/notebook-io-contract.md) shapes.
- [X] T017 [US1] Validate FR-002/FR-009: confirm no cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` imports from `L_RAG/notebooks/archive/*` or references knowledge-graph/`GraphExpansion`/`GraphTraversal`/hybrid-fusion objects (SC-005).
- [ ] T018 [US1] Run Scenario A from [quickstart.md](./quickstart.md) (`DEV_HASHING=True`, `SAMPLE_LIMIT=25`) end-to-end in Jupyter and confirm the expected outcomes (metrics tables render, run summary shows counts, header labeled "vector-only").

**Checkpoint**: User Story 1 is fully functional and independently testable via Scenario A (and Scenario B/E once a real FAISS index is available).

---

## Phase 4: User Story 2 - Correctly exclude unanswerable/missing-ground-truth rows (Priority: P2)

**Goal**: The notebook's skipped-unanswerable / skipped-missing-ground-truth counts and evaluated count are provably correct and match `select_eligible_cases`'s independently computed counts.

**Independent Test**: Run the notebook against `data/qa_final.jsonl`, then independently run `select_eligible_cases` on the same file per [quickstart.md](./quickstart.md) Scenario B's cross-check snippet, and confirm the counts match exactly (SC-002).

### Implementation for User Story 2

- [X] T019 [US2] Confirm (no new code expected) that the eligibility cell added in T011 already surfaces `total_rows`, `len(eligible)`, `skipped_unanswerable`, `skipped_missing_ground_truth` distinctly in its displayed output — adjust display formatting in `L_RAG/notebooks/vector_retrieval_eval.ipynb` if any count is not individually visible (Acceptance Scenarios 1–2 of US2).
- [X] T020 [US2] Confirm the eligibility cell in `L_RAG/notebooks/vector_retrieval_eval.ipynb` visibly states when `SAMPLE_LIMIT` was applied (e.g., "evaluated N of M eligible cases due to SAMPLE_LIMIT") (Acceptance Scenario 3 of US2).
- [X] T021 [US2] Run [quickstart.md](./quickstart.md) Scenario B's cross-check snippet (`select_eligible_cases` run standalone against `data/qa_final.jsonl`) and compare against the notebook's own reported counts from T019/T020; confirm exact parity (SC-002).

**Checkpoint**: User Stories 1 AND 2 both work independently; eligibility counts are verified correct.

---

## Phase 5: User Story 3 - Configure retrieval parameters without editing library code (Priority: P3)

**Goal**: A user can change `TOP_K_LIST`, `SCORE_THRESHOLD`, `MODEL_NAME`, or `EXPAND_UNITS` in the configuration cell only, rerun retrieval/evaluation cells, and see the new configuration reflected — with clear errors on invalid FAISS index configuration.

**Independent Test**: Change `TOP_K_LIST` from `[1, 5, 10]` to `[1, 3]` and `SCORE_THRESHOLD` in the config cell only, rerun the retrieval/evaluation cells (not the whole kernel), and confirm the metrics table reflects the new `k` values and threshold without any `src/` edits (SC-003).

### Implementation for User Story 3

- [X] T022 [US3] Verify the retrieval + scoring cell (T013) re-reads `TOP_K_LIST`/`SCORE_THRESHOLD`/`MODEL_NAME`/`EXPAND_UNITS` from the config cell's current values on every execution (no cached/stale config captured at notebook-load time) in `L_RAG/notebooks/vector_retrieval_eval.ipynb`.
- [X] T023 [US3] Verify the retrieval + scoring cell (T013) re-initializes `cases = []` at the top of its execution every time it runs, so reruns after a config change never mix stale per-case rows into the new aggregate (FR-014, Edge Case in spec.md).
- [X] T024 [US3] Add/verify explicit error handling around the retriever-construction cell (T012) in `L_RAG/notebooks/vector_retrieval_eval.ipynb` so an invalid, missing, or corrupt `INDEX_DIR` (missing `index.faiss`/`payloads.jsonl`, unreadable `payload_cache.sqlite`) surfaces a clear, specific error message at that cell rather than an unexplained stack trace propagating into later cells (Acceptance Scenario 2 of US3, FR-012).
- [X] T025 [US3] Run [quickstart.md](./quickstart.md) Scenario C end-to-end: change only `TOP_K_LIST`/`SCORE_THRESHOLD` in the config cell, rerun retrieval/evaluation cells, and confirm the metrics table reflects the new values with zero `src/` edits (SC-003).
- [X] T026 [US3] Run [quickstart.md](./quickstart.md) Scenario D's error-handling checks (missing QA file, missing/corrupt FAISS index directory, zero eligible cases) and confirm each surfaces the expected clear error or zero-count summary without an unrelated downstream exception (FR-011, FR-012, FR-013).

**Checkpoint**: All user stories are independently functional; configuration changes require zero `src/` edits, and error paths are verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all user stories.

- [X] T027 [P] Run the full [quickstart.md](./quickstart.md) Scenario E persistence check: trigger the persistence cell (T016), confirm `retrieval_cases.jsonl` and `retrieval_metrics.json` are written under a fresh `evaluation_runs/vector_only/<run_id>/` directory and can be independently reloaded with structure matching [contracts/notebook-io-contract.md](./contracts/notebook-io-contract.md) (FR-008, SC-004).
- [X] T028 [P] Re-run `pytest L_RAG/tests/` (full suite) to confirm the Phase 2 `retriever_factory.py` extension introduced no regressions in existing evaluation/retrieval tests.
- [X] T029 Clean up any `evaluation_runs/vector_only/<run_id>/` directories created during manual quickstart validation that are not needed as committed artifacts.
- [X] T030 Final full read-through of `L_RAG/notebooks/vector_retrieval_eval.ipynb` confirming: header/output clearly labeled "vector-only" (FR-010), no archive-notebook imports (FR-009, SC-005), and all six spec.md Edge Cases are handled as described.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories (the FAISS-backed `build_vector_retriever` path is required by every story's retrieval cell).
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - User Story 1 (Phase 3) has no dependency on Stories 2/3.
  - User Story 2 (Phase 4) builds on cells introduced in Phase 3 (T011) but adds no new `src/` dependency — can be validated once Phase 3's eligibility cell exists.
  - User Story 3 (Phase 5) builds on cells introduced in Phase 3 (T012, T013) but adds no new `src/` dependency — can be validated once Phase 3's retrieval cells exist.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependency on other stories. This is the MVP.
- **User Story 2 (P2)**: Depends on Phase 3's eligibility cell (T011) existing; otherwise independently testable via its own cross-check script.
- **User Story 3 (P3)**: Depends on Phase 3's config/retrieval cells (T009, T012, T013) existing; otherwise independently testable via config-only reruns.

### Within Each Phase

- Phase 2: T003 (investigation) before T004/T005 (implementation) before T006 (error handling) before T007 (tests) before T008 (test run/gate).
- Phase 3: T009 (config) before T010 (load) before T011 (eligibility) before T012 (retriever) before T013 (retrieval loop) before T014/T015 (display) before T016 (persistence) before T017/T018 (validation).

### Parallel Opportunities

- T007 (unit tests) can be drafted in parallel with T006 (error handling) since they touch different concerns, but both must land before T008's gate.
- T027 and T028 in Phase 6 are independent validation passes and can run in parallel.
- Because this feature is a single notebook file plus one shared `src/` module, most notebook-cell tasks (T009–T016) are inherently sequential (same file, ordered cells) rather than parallelizable; no `[P]` marker is applied within Phase 3–5 notebook tasks.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (`retriever_factory.py` FAISS extension + tests — CRITICAL, blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run quickstart.md Scenario A (and B once a FAISS index is available); confirm independent test passes.
5. This is a usable MVP: a working vector-only evaluation notebook.

### Incremental Delivery

1. Setup + Foundational → FAISS-backed retriever construction ready and tested.
2. Add User Story 1 → validate via Scenario A/B → MVP notebook usable.
3. Add User Story 2 → validate eligibility-count parity via Scenario B's cross-check.
4. Add User Story 3 → validate config-only reruns via Scenario C and error paths via Scenario D.
5. Polish → validate persistence via Scenario E, run full test suite, final read-through.

---

## Parallel Example: Phase 2 (Foundational)

```
# T007 (tests) can be drafted while T006 (error-handling polish) is finalized,
# but both must complete before the T008 gate:
Task: "Add unit tests in L_RAG/tests/test_evaluation_retriever_factory.py covering FAISS/Qdrant/dev_hashing branches"
Task: "Update build_vector_retriever's error handling for missing/invalid index_dir"
```

## Parallel Example: Phase 6 (Polish)

```
Task: "Run Scenario E persistence check end-to-end"
Task: "Re-run full pytest suite for regressions"
```
