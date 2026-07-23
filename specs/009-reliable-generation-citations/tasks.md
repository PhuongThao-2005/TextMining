# Tasks: Reliable Generation Citations

**Input**: Design documents from `/specs/009-reliable-generation-citations/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/generation-citations.md, quickstart.md  
**Aligned to**: Clarification 2026-07-24 (eval record + local ids + so_hieu)

**Tests**: Included — FR-014 / SC-005–SC-008 require offline unit tests without a live model.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`)
- Exact file paths in every task description

## Path Conventions

- Library: `src/generation/`
- Tests: `tests/generation/`
- Spec docs: `docs/spec/GENERATION_MODULE.md`
- Benchmark: `data/benchmark/qa_final.jsonl`
- Consumers: `notebooks/archive/faiss_retrieval_ready.ipynb`, `scripts/_patch_faiss_hybrid_notebook.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm feature surface and as-built field availability

- [ ] T001 Confirm design package under `specs/009-reliable-generation-citations/` matches FR-015–FR-019 (eval record, local ids, `so_hieu`, chunk grain)
- [ ] T002 [P] Inventory evidence field access paths (`id_str`, `article_number`, `chunk_id`, `parent_unit_id`, `metadata.so_ky_hieu`, `metadata.chunk_index_in_unit`) in `src/retrieval/schema.py`, `src/retrieval/retriever.py`, and `GenerationOutcome` constructions in `src/generation/reasoning_client.py`, `src/generation/__init__.py`, `tests/generation/test_reasoning_client.py`, `scripts/_patch_faiss_hybrid_notebook.py`, `notebooks/archive/faiss_retrieval_ready.ipynb`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types and constants every user story depends on

**⚠️ CRITICAL**: No user story work until this phase is complete

- [ ] T003 Extract fixed abstention phrase into module constant `INSUFFICIENT_CONTEXT_ANSWER` and wire `ANSWER_PROMPT` to use it in `src/generation/reasoning_client.py`
- [ ] T004 Add frozen `SystemCitation` dataclass with fields `law_id`, `so_hieu`, `article_id`, `chunk_id`, `corpus_chunk_id`, `parent_unit_id`, `display_label`, `identity_key` in `src/generation/reasoning_client.py` per `specs/009-reliable-generation-citations/data-model.md`
- [ ] T005 Add frozen `CitationBuildResult` (or equivalent) with `citations`, `dropped_uncitable`, `dropped_unsafe` in `src/generation/reasoning_client.py`
- [ ] T006 Extend `GenerationOutcome` with `citations: tuple[SystemCitation, ...] = ()`, `dropped_uncitable: int = 0`, `dropped_unsafe: int = 0` in `src/generation/reasoning_client.py`
- [ ] T007 Re-export `SystemCitation`, `build_system_citations` (stub ok until US1), `to_relevant_article`, `build_evaluation_case_record` (stubs ok until US3), and `INSUFFICIENT_CONTEXT_ANSWER` from `src/generation/__init__.py`

**Checkpoint**: Types importable; keyword `GenerationOutcome(...)` still works without citations args

---

## Phase 3: User Story 1 - Trustworthy legal citations on every answer (Priority: P1) 🎯 MVP

**Goal**: System-owned citation list on substantive success equals deterministic evidence projection with local ids + `so_hieu`; model text cannot invent or omit official citations

**Independent Test**: Fixed evidence + mocked generator inventing/omitting citations → `outcome.citations` matches evidence-only projection with local `article_id`/`chunk_id`

### Tests for User Story 1

- [ ] T008 [P] [US1] Add offline builder tests for local-id projection (`article_number`→`article_id`, unit-suffix fallback, `chunk_index_in_unit`→local `chunk_id`, `::chunk::` suffix fallback, never full compound as eval ids) in `tests/generation/test_system_citations.py`
- [ ] T009 [P] [US1] Add offline builder tests for `law_id`=`id_str`, `so_hieu` from attr/metadata `so_ky_hieu`, chunk-grain order/dedupe, object vs dict vs metadata field resolution in `tests/generation/test_system_citations.py`
- [ ] T010 [P] [US1] Add offline builder tests for `citation_safe=False` exclusion, default-true when absent, uncitable drop counting, no `chunk-{rank}` fabrication in `tests/generation/test_system_citations.py`
- [ ] T011 [US1] Add mocked `generate_answer` tests: invented model citation not in list; omitted model citations still present; substantive success attaches full eligible list in `tests/generation/test_system_citations.py`

### Implementation for User Story 1

- [ ] T012 [US1] Implement field readers + pure `build_system_citations(chunks)` in `src/generation/reasoning_client.py` per `contracts/generation-citations.md` (local ids, `so_hieu`, chunk-grain identity, safety, drops; no I/O; no answer text)
- [ ] T013 [US1] In `generate_answer` in `src/generation/reasoning_client.py`, on substantive success attach `build_system_citations(chunks)` to `GenerationOutcome.citations` and drop counts
- [ ] T014 [US1] Update equality/construction assertions in `tests/generation/test_reasoning_client.py` for new `GenerationOutcome` defaults
- [ ] T015 [US1] Run `pytest tests/generation -q` and fix failures until US1 offline green

**Checkpoint**: US1 independently testable — evidence-derived local-id citations on success

---

## Phase 4: User Story 2 - Clear citations when the system abstains or skips (Priority: P2)

**Goal**: Empty context, config/API errors, and fixed abstention never present non-empty citations as answer authority

**Independent Test**: Empty chunks, client None, raised generator error, exact `INSUFFICIENT_CONTEXT_ANSWER` → `citations == ()`

### Tests for User Story 2

- [ ] T016 [P] [US2] Add tests for empty-context skip → `citations == ()` in `tests/generation/test_system_citations.py`
- [ ] T017 [P] [US2] Add tests for `client is None` and mocked API/format exception → `citations == ()` in `tests/generation/test_system_citations.py`
- [ ] T018 [US2] Add test for exact abstention phrase (after strip) → `citations == ()` with non-empty evidence in `tests/generation/test_system_citations.py`

### Implementation for User Story 2

- [ ] T019 [US2] Wire all non-substantive paths in `generate_answer` in `src/generation/reasoning_client.py` to return empty `citations` per data-model state matrix
- [ ] T020 [US2] Detect abstention via `parsed.answer.strip() == INSUFFICIENT_CONTEXT_ANSWER` and force `citations=()` in `src/generation/reasoning_client.py`
- [ ] T021 [US2] Run `pytest tests/generation -q` confirming US1 + US2 offline

**Checkpoint**: Skip/error/abstention never show supporting citations

---

## Phase 5: User Story 3 - Evaluation and review use the same citation contract (Priority: P3)

**Goal**: Eval consumers get FR-015 records (`question_id`, `question_type`, `question`, `answer`, `relevant_articles`) without parsing answer prose; phrasing-independent citations

**Independent Test**: Three mocked answer phrasings → identical citations; eval record projects local ids only; `question_type` from `answer_type`

### Tests for User Story 3

- [ ] T022 [US3] Add SC-003 phrasing-independence test on `outcome.citations` in `tests/generation/test_system_citations.py`
- [ ] T023 [P] [US3] Add tests for `to_relevant_article` / `build_evaluation_case_record` (keys, `question_id`←`qa_id`, `question_type`←`answer_type`, `relevant_articles` shape, no internal fields leaked) in `tests/generation/test_system_citations.py`
- [ ] T024 [P] [US3] Add export smoke test for public imports from `generation` in `tests/generation/test_system_citations.py`

### Implementation for User Story 3

- [ ] T025 [US3] Implement `to_relevant_article` and `build_evaluation_case_record` in `src/generation/reasoning_client.py` per `contracts/generation-citations.md`
- [ ] T026 [US3] Finalize public exports and `__all__` in `src/generation/__init__.py`
- [ ] T027 [US3] Document eval record, local-id rules, and structured citation consumption in `docs/spec/GENERATION_MODULE.md`
- [ ] T028 [US3] Verify keyword `GenerationOutcome(...)` in `scripts/_patch_faiss_hybrid_notebook.py` and `notebooks/archive/faiss_retrieval_ready.ipynb`; touch only if breakage requires it
- [ ] T029 [US3] Run `pytest tests/generation -q` confirming US1–US3 offline

**Checkpoint**: Eval can score `relevant_articles` alone; local ids and `qa_final` field map proven

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Spec alignment, full quickstart gate, residual hygiene

- [ ] T030 [P] Finish `docs/spec/GENERATION_MODULE.md` acceptance criteria, API surface, §14 scope (system citations in-scope; model-text faithfulness optional out of scope)
- [ ] T031 [P] Align remaining examples/tables in `docs/spec/GENERATION_MODULE.md` with `data-model.md` state matrix and eval record
- [ ] T032 Confirm `format_context_for_prompt` in `src/generation/reasoning_client.py` keeps `chunk-{rank}` as prompt-only and never feeds it into `build_system_citations` identity
- [ ] T033 Run full quickstart validation from `specs/009-reliable-generation-citations/quickstart.md` (`pytest tests/generation -q` + checklist)
- [ ] T034 [P] Optional status note in `specs/009-reliable-generation-citations/spec.md` when implementation complete (no requirement rewrites)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP
- **US2 (Phase 4)**: After US1 orchestration exists (same function)
- **US3 (Phase 5)**: Needs US1 citations field; eval helpers + docs
- **Polish (Phase 6)**: After US1–US3 desired scope

### User Story Dependencies

- **US1 (P1)**: Core reliability + local ids + so_hieu
- **US2 (P2)**: Empty citations on skip/error/abstention
- **US3 (P3)**: Eval case record + exports + docs

### Parallel Opportunities

- T001–T002 setup
- T008–T010 builder test groups
- T016–T017 skip/error tests
- T023–T024 eval helper tests
- T030–T031 docs polish

---

## Parallel Example: User Story 1

```text
Task: T008 local-id projection tests in tests/generation/test_system_citations.py
Task: T009 law_id/so_hieu/dedupe/metadata tests in tests/generation/test_system_citations.py
Task: T010 safety/uncitable tests in tests/generation/test_system_citations.py
# Then sequential on reasoning_client.py:
Task: T012 implement build_system_citations
Task: T013 attach on substantive success
Task: T015 pytest green
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1–2: types + constants
2. Phase 3: builder (local ids, so_hieu) + success attachment + tests
3. **STOP**: `pytest tests/generation -q`
4. Then US2 → US3 → polish

### Incremental Delivery

1. Foundational types
2. US1 evidence citations with local eval fields
3. US2 safe empty paths
4. US3 eval record serializer + docs
5. Polish + quickstart gate

---

## Notes

- Do **not** parse model answer text for official citations
- Do **not** emit compound `doc::…::chunk::n` as eval `article_id` / `chunk_id`
- `law_id` = doc id (`id_str`); `so_hieu` = `so_ky_hieu`
- `question_type` = QA `answer_type` from `qa_final`
- Chunk-grain dedupe; default `citation_safe=True` when absent
- Abstention = exact `INSUFFICIENT_CONTEXT_ANSWER` after strip
- Prefer keyword `GenerationOutcome(...)` at all call sites

---

## Task Summary

| Metric | Value |
|--------|--------|
| **Total tasks** | 34 |
| **Phase 1 Setup** | 2 |
| **Phase 2 Foundational** | 5 |
| **US1 (P1)** | 8 (T008–T015) |
| **US2 (P2)** | 6 (T016–T021) |
| **US3 (P3)** | 8 (T022–T029) |
| **Polish** | 5 (T030–T034) |
| **Suggested MVP** | Phases 1–3 (US1 only) |
| **Format validation** | All tasks use `- [ ]`, TaskID, optional `[P]`/`[USn]`, file paths |

### Independent Test Criteria (per story)

| Story | Independent test |
|-------|------------------|
| US1 | Evidence + mock invent/omit → system list = local-id evidence projection |
| US2 | Empty / error / abstention → `citations == ()` |
| US3 | Phrasing-invariant citations; eval record with `relevant_articles` local ids + `qa_final` field map |
