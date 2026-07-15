# Tasks: Full FAISS Retrieval System Notebook (SQLite cache + reasoning generator)

**Input**: Design documents from `/specs/001-faiss-retrieval-notebook/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: Included — plan.md and quickstart V6 require unit tests for `src/retrieval/sqlite_faiss_store.py` and `src/generation/reasoning_client.py` under `tests/retrieval/test_sqlite_faiss_store.py` and `tests/generation/test_reasoning_client.py` (synthetic `tmp_path` fixtures + fake OpenAI client only; never the production FAISS index or a live API).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. Sections 1–7 of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) already implement most of US1–US3 inline; this plan extracts the SQLite store and generator client into `src/`, wires the notebook as a thin caller, and adds reasoning-aware generation (US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/`, `notebooks/` under `L_RAG/` repository root (per plan.md)
- Paths below are relative to `L_RAG/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create package/test layout so extracted modules and unit tests have a stable home

- [x] T001 Create [`src/generation/__init__.py`](../../src/generation/__init__.py) package marker (supersedes empty [`src/generation/temp.py`](../../src/generation/temp.py) as package entry; leave `temp.py` in place until reasoning_client lands, then remove or leave unused)
- [x] T002 [P] Create stub [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) with module docstring only (placeholder for `SQLitePayloadFaissVectorStore`)
- [x] T003 [P] Create stub [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) with module docstring only (placeholder for `GeneratorClient` / parsing helpers)
- [x] T004 [P] Create `tests/retrieval/` package with empty [`tests/retrieval/__init__.py`](../../tests/retrieval/__init__.py) and placeholder [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py)
- [x] T005 [P] Create `tests/generation/` package with empty [`tests/generation/__init__.py`](../../tests/generation/__init__.py) and placeholder [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared result types and module skeletons every user story depends on — `VectorStore` ABC conformance contract, payload-cache status types, generator config/result dataclasses

**⚠️ CRITICAL**: No user-story extraction/wiring work should treat these contracts as optional; implement types first so tests and notebook imports share one shape

- [x] T006 Implement `PayloadCacheStatus` frozen dataclass and `_check_payload_cache(index_dir: Path) -> PayloadCacheStatus` helper in [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) per [`data-model.md`](data-model.md) §2 (`exists`, `is_stale`, `payload_size`, `payload_mtime_ns`; compare against `meta` table / `payloads.jsonl` stat)
- [x] T007 Implement skeleton `SQLitePayloadFaissVectorStore(VectorStore)` in [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) with attributes `index`, `conn`, optional `id_map`/`int_to_id`, and method stubs matching the existing [`VectorStore`](../../src/retrieval/stores.py) ABC exactly: `recreate_collection`, `upsert`, `search(vector, *, limit, score_threshold=None, filters=None)`, `scroll(filters, limit)` — plus `load`, `total_vectors`, `close` (do not invent a divergent `top_k` signature)
- [x] T008 [P] Implement generator result dataclasses in [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) per [`data-model.md`](data-model.md) §3: `GeneratorConfig` (`base_url`, `api_key`, `model_name`, `is_complete()`, `masked_key()`), `RawGenerationResponse` (`content`, `reasoning_field`), `ParsedAnswer` (`answer`, `reasoning`, `reasoning_available`, `reasoning_source`), `GenerationOutcome` (`qa_id`, `parsed`, `skipped_empty_context`, `error`)
- [x] T009 [P] Implement skeleton `GeneratorClient` in [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) with `__init__(*, base_url, api_key, model)` and `generate(prompt, *, temperature=0.0) -> RawGenerationResponse` (body may raise `NotImplementedError` until US4)
- [x] T010 Confirm notebook path/config cells in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) already cover FR-003/FR-013 (`resolve_project_root`, `EMBEDDING_MODEL_NAME`, `TOP_K`, `TOP_N`, `SCORE_THRESHOLD`, `EXPAND_UNITS`, `DEFAULT_FILTER_PROFILE` / `FILTER_PROFILE`, `BENCHMARK_SAMPLE_SIZE`); document any rename needed so later wiring tasks only change Section 4 and Sections 8–11 imports — no config redesign in this phase

**Checkpoint**: Foundation ready — both modules importable; dataclasses and ABC skeleton in place; notebook config contract confirmed

---

## Phase 3: User Story 1 - Run retrieval end to end (Priority: P1) 🎯 MVP

**Goal**: Formalize SQLite-backed payload loading as a first-class `VectorStore` so the notebook loads `index.faiss` + `payload_cache.sqlite` (rebuild-if-stale), constructs a retriever, runs sample queries, and displays citation-ready results without inline store logic

**Independent Test**: With `data/faiss_index/` populated, run notebook through load + sample search; confirm preflight, cache reuse/rebuild messages, ranked results with citation metadata; `pytest tests/retrieval/test_sqlite_faiss_store.py -q` green (SC-001, SC-002, SC-005, SC-006 partial)

### Tests for User Story 1

> Write these tests FIRST against synthetic `tmp_path` fixtures; ensure they FAIL before cache/search implementation lands

- [x] T011 [P] [US1] Unit tests for `_check_payload_cache` / `PayloadCacheStatus` covering fresh cache, missing cache, stale-by-size, stale-by-mtime in [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py) (FR-016, data-model §2)
- [x] T012 [P] [US1] Unit tests for `_ensure_payload_cache` rebuild correctness (creates `payload_cache.sqlite` + `meta` row from a tiny `payloads.jsonl`; second call reuses without rewrite when fresh) in [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py)
- [x] T013 [P] [US1] Unit tests for `SQLitePayloadFaissVectorStore.search` / `scroll` against a tiny synthetic FAISS index + payloads fixture under `tmp_path` (filter match, empty results, score threshold) in [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py)
- [x] T014 [P] [US1] Unit tests for `load` missing `index.faiss` / missing `payloads.jsonl` raises clear `FileNotFoundError` (or equivalent) in [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py) (FR-001 edge)

### Implementation for User Story 1

- [x] T015 [US1] Port notebook Section 4 cache logic into [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py): `_ensure_payload_cache` (size+mtime vs `meta`), batched INSERT rebuild, `_load_payloads` / per-`line_no` SQLite lookup — research R2; never silently serve stale cache (FR-015, FR-016, Constitution III)
- [x] T016 [US1] Implement `SQLitePayloadFaissVectorStore.load`, `search`, `scroll`, `total_vectors`, `close` in [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) reusing `payload_matches` from [`src/retrieval/stores.py`](../../src/retrieval/stores.py); mirror filter/score behavior of [`FaissVectorStore`](../../src/retrieval/faiss_store.py); implement `recreate_collection` / `upsert` as explicit unsupported (raise) or minimal stubs only if required for ABC — document choice in module docstring (FR-002 interchangeability)
- [x] T017 [US1] Replace inline `SQLitePayloadFaissVectorStore` class body in Section 4 of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with `from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore` (keep Sections 4.1/4.2 CSV/sqlite export helpers notebook-local) (FR-002, FR-015)
- [x] T018 [US1] Verify preflight + load + `search()` / `show_results()` cells still satisfy FR-001/FR-004/FR-011/FR-012/FR-014 in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): missing files listed before load; zero-hit queries recorded without crash; quarantine assumption stated if applicable; full chunk inspection cell intact

**Checkpoint**: User Story 1 independently runnable as MVP — extract store + notebook import + unit tests green; cache warm path faster than cold rebuild (SC-006)

---

## Phase 4: User Story 2 - Validate retrieval quality against benchmark (Priority: P2)

**Goal**: Keep batch/benchmark mode over `data/benchmark/qa_final.jsonl` working after store extraction; report per-question ground-truth hits, latency, and aggregate hit-rate without requiring generation

**Independent Test**: Run `run_benchmark_sample(sample_size=10–20)` with generator unset; confirm per-question retrieval hit flags, unanswerable handling, aggregate summary (SC-003; FR-006/FR-007/FR-008)

### Tests for User Story 2

- [x] T019 [P] [US2] Unit tests that `SQLitePayloadFaissVectorStore` returns `SearchHit` payloads with `chunk_id` / `parent_unit_id` / `id_str` keys used by benchmark ground-truth matching (synthetic fixtures) in [`tests/retrieval/test_sqlite_faiss_store.py`](../../tests/retrieval/test_sqlite_faiss_store.py) (data-model §4, FR-006)

### Implementation for User Story 2

- [x] T020 [US2] Confirm / harden `run_benchmark_sample` in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): configurable `sample_size` (FR-007); per-question ground-truth `chunk_id`/`provision_id`/`document_id` hit detection; unanswerable (`answer_type` / empty ground truth) not counted as pipeline error (FR-006 edge); per-query + average latency (FR-008); empty retrieval results recorded and loop continues (FR-012)
- [x] T021 [US2] Ensure benchmark cell works with the extracted store (no dependency on removed inline class attributes) and prints aggregate hit-rate excluding unanswerable questions (SC-003)

**Checkpoint**: User Stories 1 and 2 work with extracted store; retrieval-only benchmark is demoable without generator credentials

---

## Phase 5: User Story 3 - Filter profiles and same-provision expansion (Priority: P3)

**Goal**: Demonstrate `current_law` / `broad` / `historical` filter profiles and `expand_units` behavior after store extraction; label `graph_guided` as out of scope

**Independent Test**: Same query under three profiles shows distinct candidate counts/result sets; at least one expansion example when `EXPAND_UNITS=True` (SC-004; FR-005/FR-009/FR-010)

### Implementation for User Story 3

> No new unit-test module required beyond US1 store filter coverage (T013); this story is notebook demonstration over existing `VectorRetriever` behavior

- [x] T022 [US3] Verify filter-profile comparison cells in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) still run the same query under `current_law`, `broad`, and `historical`, displaying profile name, candidate count, empty-filter warnings (FR-005, SC-004)
- [x] T023 [US3] Verify same-provision expansion demo cell(s) with `expand_units=True` show sibling chunks under the same `parent_unit_id` (or diagnostic count) (FR-009)
- [x] T024 [US3] Confirm `graph_guided` is explicitly labeled "not exercised — requires knowledge graph module" rather than silently defaulting (FR-010)

**Checkpoint**: US1–US3 retrieval surface fully demoable on extracted store; no generation required

---

## Phase 6: User Story 4 - Reasoning-backed answer generation (Priority: P2)

**Goal**: Configurable OpenAI-compatible generator that elicits reasoning, parses three response shapes, displays answer vs reasoning distinctly, and supports ad hoc + batch generation without aborting on single failures

**Independent Test**: With credentials set (or fake client in tests), run generation for one question → distinct answer + reasoning sections; batch path records per-question `GenerationOutcome` including forced failure continuity (SC-007, SC-008; FR-017–FR-024)

### Tests for User Story 4

> Write these tests FIRST with fake OpenAI responses; no network calls

- [x] T025 [P] [US4] Unit tests for `GeneratorConfig.masked_key()` never returns raw key (short and long keys) and `is_complete()` true/false matrix in [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py) (FR-018, R6)
- [x] T026 [P] [US4] Unit tests for `parse_generation_response` three cases: (a) non-empty `reasoning_field` → `reasoning_source="field"`; (b) HTML/XML think-delimited block in content → `reasoning_source="think_block"`, answer stripped; (c) neither → `reasoning_source="not_returned"`, `reasoning_available=False` in [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py) (FR-020/FR-021, R4)
- [x] T027 [P] [US4] Unit tests for unterminated think-delimiter (open tag without close) treated as case 3 (no crash) in [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py)
- [x] T028 [P] [US4] Unit tests for `format_context_for_prompt` includes chunk text + citation/title fields and `ANSWER_PROMPT` contains an explicit reasoning instruction (FR-019) in [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py)
- [x] T029 [P] [US4] Unit tests that `GeneratorClient` / exception paths never embed raw `api_key` in returned strings or exception messages (fake client) in [`tests/generation/test_reasoning_client.py`](../../tests/generation/test_reasoning_client.py) (FR-018)

### Implementation for User Story 4

- [x] T030 [US4] Implement `ANSWER_PROMPT` (Vietnamese, context-grounded, explicit reasoning-before-answer instruction), `format_context_for_prompt`, and `parse_generation_response(raw: RawGenerationResponse) -> ParsedAnswer` in [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) per research R4 and data-model §3 (FR-019/FR-020/FR-021)
- [x] T031 [US4] Implement `GeneratorClient.generate` in [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) via `openai.OpenAI(base_url=..., api_key=...)` chat completions; map SDK message to `RawGenerationResponse` reading `reasoning_content` or `reasoning` if present; never log raw key (FR-017/FR-018, R3)
- [x] T032 [US4] Implement `generate_answer(...)` (or equivalent) returning `GenerationOutcome`: skip with `skipped_empty_context=True` when chunks empty (no API call); on success set `parsed`; on exception set `error=str(exc)` without raw key (FR-022/FR-023, Edge Cases)
- [x] T033 [US4] Replace inline `GeneratorClient` / `ANSWER_PROMPT` / `format_context_for_prompt` / `generate_answer` in Sections 8–10 of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with imports from `generation.reasoning_client`; config cell reads `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME` from env, prints masked confirmation only; incomplete config → clear message, no API call (FR-017/FR-018)
- [x] T034 [US4] Wire ad hoc full pipeline cell (`ask()` or equivalent) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) to display final answer and reasoning as two distinct sections (or "not returned by this model") (FR-020/FR-021/FR-022, SC-007)
- [x] T035 [US4] Extend `run_benchmark_sample` in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) to record per-question `GenerationOutcome` (answer, reasoning, reasoning_source / not-returned, error) reusing already-retrieved chunks — no re-query; single generation failure does not stop the loop (FR-022/FR-023, SC-008, R5)
- [x] T036 [US4] Add notebook markdown labeling generation as a thin demonstration/validation layer (not a full judge/scoring pipeline); point to `scripts/evaluate_e2e.py` for judged evaluation (FR-024)

**Checkpoint**: US4 complete — reasoning extraction covered by unit tests; notebook ad hoc + batch generation paths use extracted client; credentials never printed raw

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation, exports, and quickstart acceptance checklist

- [x] T037 [P] Export public API from [`src/generation/__init__.py`](../../src/generation/__init__.py) (`GeneratorConfig`, `GeneratorClient`, `RawGenerationResponse`, `ParsedAnswer`, `GenerationOutcome`, `parse_generation_response`, `format_context_for_prompt`, `ANSWER_PROMPT` as appropriate)
- [x] T038 [P] Optionally re-export `SQLitePayloadFaissVectorStore` from [`src/retrieval/__init__.py`](../../src/retrieval/__init__.py) if that package already re-exports sibling stores; otherwise document notebook import path only (no behavior change required)
- [x] T039 Run `python -m pytest tests/retrieval/test_sqlite_faiss_store.py tests/generation/test_reasoning_client.py -q` and fix failures until green (quickstart V6)
- [x] T040 Validate notebook run order in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) against quickstart steps 1–13: works from project root and `notebooks/`; preflight; warm/stale cache paths; three filter profiles; expansion demo; generator config; ad hoc + batch generation (SC-001–SC-008 narrative)
- [x] T041 Execute automatable quickstart acceptance checklist items: unit tests green; missing FAISS file preflight path; generation skipped on zero chunks; batch continues after forced error (document manual-only items: real LLM call, warm vs cold cache timing)
- [x] T042 [P] Sanity-check [`specs/001-faiss-retrieval-notebook/quickstart.md`](quickstart.md) paths still match implemented module/notebook/test locations (docs-only; no behavior change)
- [x] T043 [P] Remove or leave clearly deprecated [`src/generation/temp.py`](../../src/generation/temp.py) placeholder once `reasoning_client.py` is the real module (prefer delete if unused)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** extraction work that assumes stable types
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP retrieval path + SQLite extraction
- **User Story 2 (Phase 4)**: Depends on US1 store working in the notebook (benchmark uses same load path)
- **User Story 3 (Phase 5)**: Depends on US1 store working; independent of US2 generation concerns
- **User Story 4 (Phase 6)**: Depends on Foundational generator types (T008/T009); can proceed in parallel with US2/US3 *module* work after Phase 2, but notebook batch integration (T035) should follow US2 benchmark cell stability
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — SQLite store extraction is the MVP gate
- **User Story 2 (P2)**: After US1 notebook wiring (T017) — retrieval benchmark reuses extracted store
- **User Story 3 (P3)**: After US1 notebook wiring — filter/expansion cells only need working `search`/`retriever`
- **User Story 4 (P2)**: After Phase 2 types; module implementation independent of US2/US3; notebook batch generation extends US2 benchmark cell

### Within Each User Story

- Tests (T011–T014, T019, T025–T029) should be written to fail first, then pass as implementation lands
- Module helpers before notebook cells that import them
- Story complete and independently testable before treating next priority as required for MVP

### Parallel Opportunities

- Phase 1: T002–T005 parallel after T001 package path (or fully parallel if package dirs created first)
- Phase 2: T006/T007 (retrieval) parallel with T008/T009 (generation); T010 independent
- Phase 3: T011–T014 tests parallel; T015→T016 sequential then T017→T018 notebook
- Phase 4: T019 parallel with early T020 drafting; T021 after T017
- Phase 5: T022–T024 sequential in notebook narrative, all after T017
- Phase 6: T025–T029 tests parallel; T030–T032 module then T033–T036 notebook
- Phase 7: T037, T038, T042, T043 parallel; T039–T041 sequential validation

---

## Parallel Example: User Story 1

```bash
# After Phase 2 types exist, launch US1 unit tests together:
Task: "Unit tests for PayloadCacheStatus fresh/missing/stale-by-size/stale-by-mtime in tests/retrieval/test_sqlite_faiss_store.py"
Task: "Unit tests for _ensure_payload_cache rebuild vs reuse in tests/retrieval/test_sqlite_faiss_store.py"
Task: "Unit tests for search/scroll synthetic FAISS fixture in tests/retrieval/test_sqlite_faiss_store.py"
Task: "Unit tests for load missing index/payloads errors in tests/retrieval/test_sqlite_faiss_store.py"

# Then implement module then notebook wiring:
Task: "Port _ensure_payload_cache + SQLite lookup into src/retrieval/sqlite_faiss_store.py"
Task: "Implement load/search/scroll/close in src/retrieval/sqlite_faiss_store.py"
Task: "Replace inline store class with import in notebooks/faiss_retrieval_ready.ipynb"
```

---

## Parallel Example: User Story 4

```bash
# Tests in parallel:
Task: "Unit tests for GeneratorConfig.masked_key / is_complete in tests/generation/test_reasoning_client.py"
Task: "Unit tests for parse_generation_response three shapes in tests/generation/test_reasoning_client.py"
Task: "Unit tests for unterminated think-delimiter handling in tests/generation/test_reasoning_client.py"
Task: "Unit tests for format_context_for_prompt + ANSWER_PROMPT reasoning instruction in tests/generation/test_reasoning_client.py"
Task: "Unit tests that api_key never leaks in client errors in tests/generation/test_reasoning_client.py"

# Module then notebook:
Task: "Implement ANSWER_PROMPT / format_context_for_prompt / parse_generation_response in src/generation/reasoning_client.py"
Task: "Implement GeneratorClient.generate + generate_answer GenerationOutcome in src/generation/reasoning_client.py"
Task: "Wire notebook Sections 8–11 imports, ask(), and benchmark GenerationOutcome recording"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational (CRITICAL — shared types)  
3. Complete Phase 3: User Story 1 (SQLite store tests + extract + notebook import)  
4. **STOP and VALIDATE**: preflight → load (warm/cold cache) → sample search → `pytest tests/retrieval/test_sqlite_faiss_store.py -q`  
5. Demo MVP retrieval notebook without generator credentials  

### Incremental Delivery

1. Setup + Foundational → types and stubs ready  
2. Add US1 → independent retrieval MVP with formal SQLite cache (SC-001/002/005/006)  
3. Add US2 → benchmark hit-rate + latency (SC-003)  
4. Add US3 → filter profiles + expansion demo (SC-004)  
5. Add US4 → reasoning generator module + notebook (SC-007/008)  
6. Polish → full quickstart acceptance  

### Parallel Team Strategy

With multiple developers after Foundational:

- Developer A: US1 SQLite store module + tests + Section 4 notebook import  
- Developer B: US4 reasoning_client module + tests (notebook wiring after A’s store load path is stable for ad hoc retrieve+generate)  
- Developer C: US2/US3 notebook verification cells + FR-010 labeling  

Integrate in notebook run order without breaking earlier sections (FR-012/FR-023).

---

## Requirements Traceability (summary)

| Requirement | Primary tasks |
| --- | --- |
| FR-001 preflight missing FAISS files | T010, T014, T018 |
| FR-002 load via `src/retrieval/` abstractions | T007, T016, T017 |
| FR-003 top-of-notebook config | T010 |
| FR-004 sample query + citation display | T018 |
| FR-005 three filter profiles | T022 |
| FR-006 benchmark ground-truth hits | T019, T020, T021 |
| FR-007 configurable sample size | T020 |
| FR-008 retrieval latency | T020 |
| FR-009 same-provision expansion demo | T023 |
| FR-010 graph_guided labeled out of scope | T024 |
| FR-011 full chunk inspection | T018 |
| FR-012 zero-hit does not crash | T013, T018, T020 |
| FR-013 project root / `notebooks/` cwd | T010, T040 |
| FR-014 quarantine/citation-safety assumption | T018 |
| FR-015 load `payload_cache.sqlite` | T006, T015, T017 |
| FR-016 staleness check + rebuild | T006, T011, T012, T015 |
| FR-017 generator config (base_url/api_key/model) | T008, T033 |
| FR-018 no hardcoded/printed raw api_key | T008, T025, T029, T031, T033 |
| FR-019 reasoning-eliciting prompt + context | T028, T030 |
| FR-020 parse field / think-block reasoning | T026, T030, T034 |
| FR-021 explicit "not returned" label | T026, T030, T034 |
| FR-022 ad hoc + batch generation reuse retrieval | T032, T034, T035 |
| FR-023 batch continues after generation failure | T032, T035, T041 |
| FR-024 thin demo layer, not full judge pipeline | T036 |
| SC-001–SC-008 | Phase 3–7 validation (T039–T041) |

---

## Notes

- **[P]** tasks = different files, no dependencies on incomplete tasks  
- **[USn]** label maps task to user story for traceability  
- Do **not** point unit tests at the production `data/faiss_index/` or a real LLM endpoint — use `tmp_path` + fake OpenAI client  
- `SQLitePayloadFaissVectorStore.search` MUST match [`VectorStore.search`](../../src/retrieval/stores.py) signature (`vector`, `limit`, `score_threshold`, `filters`), not the simplified `top_k` sketch in data-model.md  
- Notebook remains thin orchestration; heavy logic stays in [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) and [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py)  
- Commit after each task or logical group  
- Stop at any checkpoint to validate the story independently  
- Sections 1–3 and 5–7 of the existing notebook are largely kept; prefer surgical cell edits over full notebook rewrite  
