# Tasks: Notebook Graph Module Integration

**Input**: Design documents from `/specs/003-notebook-graph-integration/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: **Not required for this feature.** Plan/research R10 and Constitution Check: no new unit-test module; reuse existing `tests/knowledge_graph/*`, retrieval tests, and notebook quickstart validation (V1–V8). Graph correctness remains covered by module tests and [`scripts/verify_kg.py`](../../scripts/verify_kg.py); judged evaluation remains [`scripts/evaluate_e2e.py`](../../scripts/evaluate_e2e.py).

**Organization**: Tasks are grouped by user story. Unlike `001`/`002`, this feature does **not** extract a new `src/` package — all work extends [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) as thin orchestration over existing `knowledge_graph`, `retrieval`, and `generation` modules (FR-002, SC-001, research R2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different cells/helpers with no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project under `L_RAG/`: `src/`, `notebooks/`, `tests/`, `scripts/` at repository root (per plan.md)
- Paths below are relative to `L_RAG/`
- Primary deliverable: [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) only
- Integration surface (read/import only, do not reimplement): [`src/knowledge_graph/`](../../src/knowledge_graph/), [`src/retrieval/retriever.py`](../../src/retrieval/retriever.py), [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Orient the existing notebook for hybrid sections without changing retrieval/generation behavior yet

- [x] T001 Inventory current sections of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) that must stay intact (FAISS preflight/load, filter profiles, local `expand_units`, benchmark, generation config, existing `ask()`) and mark insertion points for hybrid cells (after FAISS load; before/around full-pipeline helper)
- [x] T002 [P] Confirm import surface in a scratch cell or notes: `KnowledgeGraphFacade`, `GraphLoaderPaths`, `GraphExpansion`, overlay join helpers, `GraphGuidedFilter` / `build_graph_guided_filter`, `VectorRetriever(graph_expansion=..., graph_guided_filter=...)`, `format_context_for_prompt` / `generate_answer` — document intended imports for later cells (FR-002; no new `src/` package)
- [x] T003 [P] Add notebook markdown outline section for hybrid pipeline (vector-first path diagram + note that graph-guided pre-filter is secondary; FR-001/FR-017/FR-020) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hybrid config, graph preflight/load/overlays, expansion wiring, and availability state — **must complete before any hybrid user-story demo**

**⚠️ CRITICAL**: No hybrid US work should claim hybrid mode until `GraphLoadStatus.structural_ready` and expansion wiring exist

- [x] T004 Extend top config cell in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with hybrid settings per [`data-model.md`](data-model.md) `PipelineConfig` / quickstart: `V2_DATA_DIR`, `ENABLE_HYBRID_EXPANSION`, `HYBRID_MAX_HOP`, `HYBRID_MAX_CONTEXT`, `AS_OF_DATE`, `USE_HYBRID_EVIDENCE_FOR_GENERATION`, `LOCAL_EXPAND_UNITS` (default `False` for hybrid demos), `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` (default `False`), keep existing `DEFAULT_FILTER_PROFILE` / FAISS knobs (FR-021)
- [x] T005 Implement notebook-local `preflight_graph_sources(v2_dir) -> GraphLoadStatus` (or equivalent dict) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): check structural files via `GraphLoaderPaths.required_paths()` / present-missing list; separately check optional `validity_timeline.jsonl` + `authority_index.jsonl`; print missing files exactly (FR-003, Edge Cases)
- [x] T006 Implement graph build cell: on structural preflight success, construct `KnowledgeGraphFacade(paths=...)`, call `build_graph()`, print duration + smoke-check stats (documents, provisions, chunks, document edges, verified vs unverified when available), store `graph` + `GraphBuildStats` + warnings (FR-004, research R5; mirror [`scripts/verify_kg.py`](../../scripts/verify_kg.py) operational class)
- [x] T007 Implement overlay join cell: when overlay files present, parse/load and `build_overlay_bundle(..., as_of_date=AS_OF_DATE)`; report overlay coverage; when missing, set `overlays_ready=False` and label currency/authority unavailable without blocking structural expansion (FR-005, Edge Cases, research R6)
- [x] T008 Construct `GraphExpansion(graph)` and optionally rebuild/wire `VectorRetriever(..., graph_expansion=graph_expansion)` for hybrid path while keeping a vector-only retriever (or `graph_expansion=None`) usable when graph missing (FR-006, FR-010, research R3/R9)
- [x] T009 Implement hybrid availability guard helper (e.g. `require_graph_for_hybrid()` / state machine from data-model §6): vector-only always allowed; hybrid expansion or hybrid-labeled `ask()` **fails clearly** if graph not loaded — never silent vector-only under a hybrid label (FR-015, SC-005)

**Checkpoint**: Foundation ready — config flags present; graph preflight/build/overlays/expansion objects available when data exists; pure vector path still works when graph missing

---

## Phase 3: User Story 1 - Run the hybrid retrieve → expand → generate pipeline (Priority: P1) 🎯 MVP

**Goal**: One sample legal question runs embed → vector seed retrieve → graph expand (+ overlays) → optional LLM generation inside the existing notebook

**Independent Test**: With FAISS + structural graph sources present, run setup + one sample query with `ENABLE_HYBRID_EXPANSION=True`; confirm seed hits, graph-expanded evidence, and optional answer/reasoning (or retrieval-only if no credentials) without unhandled exceptions (SC-001/SC-002/SC-003; quickstart V1)

### Tests for User Story 1

> No new mandatory unit tests. Optional smoke: `python -m pytest tests/knowledge_graph -q` remains green (regression only; not a blocker for notebook cells).

### Implementation for User Story 1

- [x] T010 [US1] Implement two-stage hybrid helper in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) producing `SeedRetrievalView` then `GraphExpansionView` / `HybridEvidenceContext` shapes from [`data-model.md`](data-model.md): seed pass with `expand_units=False` (or explicit seed-only retrieve); when hybrid enabled and graph ready, `GraphExpansion.expand(seed_chunk_ids, max_hop=HYBRID_MAX_HOP, max_context=HYBRID_MAX_CONTEXT)`; resolve expanded chunk payloads via store `scroll`; set `mechanism_label="graph_expansion"` (FR-001, FR-006, FR-007, FR-018, research R3)
- [x] T011 [US1] Handle empty/partial expansion edges in the hybrid helper: zero seeds → skip expansion + generation, record empty context; missing seed/parent warnings from `ExpansionResult.warnings` preserved; expansion with zero added neighbors reported as success with zero-added note; respect max-context cap and set `capped` when truncated (Edge Cases, FR-014)
- [x] T012 [US1] Attach document overlays by evidence `id_str` into `HybridEvidenceContext.document_overlays` when overlays loaded; never invent currency/authority when overlays unavailable (FR-008, research R6)
- [x] T013 [US1] Enforce shared identity on displayed hybrid evidence rows: show `chunk_id` → `parent_unit_id` → `id_str` (plus citation/title when present); never present external stubs / non-citation-safe nodes as citation-ready evidence (FR-012, FR-013, SC-006)
- [x] T014 [US1] Update full-pipeline helper `ask()` (or equivalent) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) so default demo path is vector seed → graph expansion/overlays → generation when hybrid enabled and graph loaded; pass **expanded** evidence into `format_context_for_prompt` / `generate_answer` when `USE_HYBRID_EVIDENCE_FOR_GENERATION=True` (FR-009, FR-022, research R8)
- [x] T015 [US1] Generation handoff edge cases in `ask()`: missing generator credentials → complete hybrid retrieval/expansion only; empty usable evidence text → skip generation with explicit empty-context message (`GenerationOutcome.skipped_empty_context` or equivalent); never hardcode secrets (FR-014, FR-019, US1 scenarios 3–4)
- [x] T016 [US1] Demo cell: run one sample query end-to-end with hybrid enabled; print stage labels (seed vs graph-expanded) and optional answer + reasoning as distinct sections (SC-001–SC-003, quickstart V1)

**Checkpoint**: User Story 1 independently runnable as MVP hybrid pipeline (preflight → graph load → hybrid query → optional generate)

---

## Phase 4: User Story 2 - Inspect seed hits, graph expansion, and overlay signals (Priority: P2)

**Goal**: After one hybrid query, diagnostics make seed set, expansion deltas, provision/document linkage, overlay fields, and warnings visible

**Independent Test**: After hybrid query with ≥1 seed hit, notebook shows seed vs expanded counts/samples, at least one identity chain, overlay field when available, and any expansion warnings (SC-002; quickstart V2)

### Implementation for User Story 2

- [x] T017 [US2] Diagnostics cell/table for seed vs expanded in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): seed count, expanded count, added-count, sample `chunk_id` / `parent_unit_id` / `id_str` rows, `mechanism_label=graph_expansion` (FR-007, FR-012, FR-018)
- [x] T018 [US2] Overlay diagnostics: report overlay coverage summary; display currency/authority (and as-of date) for at least one document involved in the hybrid result when overlays loaded; label unavailable when not (FR-005, FR-008, Edge Cases)
- [x] T019 [US2] Surface expansion warnings explicitly (missing seeds, missing parents, cap truncation notes) — never drop silently (US2 scenario 3, Constitution III)

**Checkpoint**: US1 + US2 — hybrid run produces inspectable intermediate legal structure, not only final chunks

---

## Phase 5: User Story 3 - Compare vector-only vs hybrid expanded retrieval (Priority: P2)

**Goal**: Same fixed query under vector-only vs hybrid-expanded modes with clear labels, counts, and expansion deltas

**Independent Test**: One fixed query both modes; distinct mode labels; result/expansion counts; explicit zero-added message if expansion added nothing (SC-004; quickstart V3)

### Implementation for User Story 3

- [x] T020 [US3] Implement comparison helper producing `ModeComparisonRecord` in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): run vector-only (`mode=vector_only`, no graph expansion) and hybrid-expanded for the same query; record counts, `expansion_ran`, `added_context_count`, sample ids, notes (FR-011, data-model)
- [x] T021 [US3] Comparison display cell: label modes distinctly (`vector_only` vs `hybrid_expanded`); show candidate/result counts and whether expansion added context (or explicitly “added nothing”) (US3 scenarios 1–2, SC-004)
- [x] T022 [US3] Comparison path respects FR-015: requesting hybrid side while graph unavailable fails clearly or records unavailable-graph note — never silent vector-only under hybrid label (US3 scenario 3)

**Checkpoint**: Side-by-side comparison proves graph integration changes evidence, not only imports

---

## Phase 6: User Story 4 - Optional graph-guided pre-filter demo (Priority: P3)

**Goal**: Secondary whitelist-before-search path remains available with explicit empty-filter handling; not the default `ask()` path

**Independent Test**: With graph (+ overlays when needed) loaded and demo enabled, run one graph-guided pre-filter query; whitelist size and empty-filter status shown; empty whitelist never silently unfilters under graph-guided label (SC-007; quickstart V7)

### Implementation for User Story 4

- [x] T023 [US4] Implement secondary demo helper producing `GraphGuidedDemoResult` in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): choose start `id_str` (config or seed hit); `facade.traverse(...)`; `build_graph_guided_filter(...)`; `VectorRetriever.retrieve(..., graph_guided_filter=...)` (FR-020, research R7)
- [x] T024 [US4] Display whitelist size, `empty_filter_warning`, filter reason/profile; if empty whitelist, surface warning and do **not** present unfiltered hits as graph-guided (SC-007, US4 scenarios 1–2)
- [x] T025 [US4] Gate demo on `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO`; keep markdown/comments stating this is secondary — primary full pipeline remains vector-first hybrid expansion (FR-001, FR-020, R1)

**Checkpoint**: Module coverage for graph-guided path without redefining primary hybrid story; replace prior “graph_guided not exercised” message with real demo when enabled

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Labeling consistency, degradation paths, documentation, and quickstart acceptance

- [x] T026 [P] Audit all hybrid-facing prints/tables in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) for FR-018: graph expansion labeled distinctly from local `expand_units` / “local same-provision expansion”; hybrid demos prefer graph path when wired (research R9)
- [x] T027 [P] Add/refresh notebook markdown that this notebook is a hybrid **demonstration** layered on existing modules — not a replacement for [`scripts/verify_kg.py`](../../scripts/verify_kg.py) or [`scripts/evaluate_e2e.py`](../../scripts/evaluate_e2e.py) (FR-017)
- [x] T028 Verify pure vector-only path and non-graph profiles (`current_law`, `broad`, `historical`) still run when structural graph inputs are missing or hybrid disabled (FR-010, SC-005, quickstart V4)
- [x] T029 Verify overlays-missing path: structural expansion still works with explicit overlays-unavailable label (quickstart V5)
- [x] T030 Confirm project-root resolution still works from project root and `notebooks/` for both FAISS and `V2_DATA_DIR` (FR-016)
- [x] T031 Confirm read-only behavior: no writes to `data/v2/` or FAISS source artifacts; secrets never hardcoded (FR-019)
- [x] T032 Run existing regression smoke (optional but recommended): `python -m pytest tests/knowledge_graph -q` (and generation/retrieval tests if touched) — expect green; no new test files required
- [x] T033 Execute quickstart validation narrative V1–V8 against [`quickstart.md`](quickstart.md) (happy path, diagnostics, comparison, missing graph, missing overlays, empty seeds/expansion/generation, graph-guided empty filter, citation safety + labeling) and fix residual notebook gaps
- [x] T034 [P] Sanity-check [`specs/003-notebook-graph-integration/quickstart.md`](quickstart.md) paths/flags still match implemented notebook config and cell order (docs-only)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all hybrid user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP hybrid pipeline
- **User Story 2 (Phase 4)**: Depends on US1 hybrid helper producing `HybridEvidenceContext` (diagnostics over same objects)
- **User Story 3 (Phase 5)**: Depends on Foundational + hybrid helper (can share US1 two-stage helper); comparison cells after seed/expand path works
- **User Story 4 (Phase 6)**: Depends on Foundational graph load; independent of US2/US3 display polish
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 only — core hybrid pipeline MVP
- **User Story 2 (P2)**: After US1 helper returns seed/expansion/overlays — diagnostics only
- **User Story 3 (P2)**: After hybrid helper exists; may parallelize with US2 if both use shared helper
- **User Story 4 (P3)**: After Phase 2 graph load; secondary path, not required for MVP

### Within Each User Story

- Foundational load/guards before hybrid-labeled retrieve
- Two-stage helper before `ask()` hybrid handoff
- Story complete and independently demoable before treating next priority as required for MVP

### Parallel Opportunities

- Phase 1: T002 and T003 parallel after T001 inventory
- Phase 2: T004 config first; T005 preflight then T006 build then T007 overlays; T008/T009 after graph object exists
- Phase 3: T010–T013 sequential helper pipeline; T014–T016 after helper stable
- Phase 4: T017–T019 sequential diagnostics over US1 outputs
- Phase 5: T020 then T021–T022
- Phase 6: T023 then T024–T025
- Phase 7: T026, T027, T034 parallel; T028–T033 validation sequential

---

## Parallel Example: User Story 1

```bash
# After Phase 2 graph + expansion are loaded:
Task: "Two-stage hybrid helper SeedRetrievalView + GraphExpansionView in notebooks/faiss_retrieval_ready.ipynb"
Task: "Empty-seed / zero-added / cap handling in hybrid helper"
Task: "Overlay attach + identity/citation safety on HybridEvidenceContext"

# Then full pipeline:
Task: "Update ask() to feed expanded evidence into generation"
Task: "Demo one sample hybrid query end-to-end"
```

---

## Parallel Example: Diagnostics + Comparison (after US1 helper)

```bash
Task: "Seed vs expanded diagnostics table (US2) in notebooks/faiss_retrieval_ready.ipynb"
Task: "Overlay + warning diagnostics (US2)"
Task: "ModeComparisonRecord vector_only vs hybrid_expanded (US3)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (inventory + outline)
2. Complete Phase 2: Foundational (config, preflight, build, overlays, expansion wire, hybrid guard)
3. Complete Phase 3: User Story 1 (two-stage hybrid + `ask()` + demo)
4. **STOP and VALIDATE**: quickstart V1 (+ V4/V6 edge cases if data allows)
5. Demo hybrid retrieve → expand → optional generate without credentials required

### Incremental Delivery

1. Setup + Foundational → graph load and pure-vector fallback ready
2. Add US1 → MVP hybrid pipeline (SC-001–SC-003)
3. Add US2 → inspectable seed/expand/overlay diagnostics (SC-002/SC-006)
4. Add US3 → vector-only vs hybrid comparison (SC-004)
5. Add US4 → optional graph-guided pre-filter (SC-007)
6. Polish → full quickstart V1–V8 acceptance

### Parallel Team Strategy

With multiple developers after Foundational:

- Developer A: US1 hybrid helper + `ask()` wiring
- Developer B: US2 diagnostics cells (after A’s helper shape lands)
- Developer C: US3 comparison + US4 graph-guided demo (graph load shared)

Integrate in notebook run order without breaking existing FAISS/filter/benchmark/generation sections.

---

## Requirements Traceability (summary)

| Requirement | Primary tasks |
| --- | --- |
| FR-001 primary vector-first hybrid pipeline | T003, T010, T014, T016 |
| FR-002 use existing KG module (no reimplementation) | T002, T006–T008, T010 |
| FR-003 graph preflight missing files | T005 |
| FR-004 graph build smoke-check stats | T006 |
| FR-005 overlays + as-of + coverage | T007, T012, T018 |
| FR-006 wire graph expansion into retrieval path | T008, T010 |
| FR-007 seed vs expanded distinguishable stages | T010, T016, T017 |
| FR-008 display overlay validity/authority signals | T012, T018 |
| FR-009 generation uses expanded evidence | T014, T015 |
| FR-010 pure vector profiles without graph | T008, T009, T028 |
| FR-011 vector-only vs hybrid comparison | T020, T021, T022 |
| FR-012 shared identity end-to-end | T013, T017 |
| FR-013 stubs non-citable | T013, T026 |
| FR-014 skip generation on empty usable evidence | T011, T015 |
| FR-015 hybrid-without-graph fails clearly | T009, T022, T028 |
| FR-016 root or `notebooks/` paths | T004, T030 |
| FR-017 demo not replacement for verify/eval scripts | T003, T027 |
| FR-018 label graph expansion vs local expand_units | T010, T017, T026 |
| FR-019 no secrets; read-only inputs | T015, T031 |
| FR-020 optional graph-guided pre-filter + empty warning | T023, T024, T025 |
| FR-021 hybrid config near top | T004 |
| FR-022 `ask()` full pipeline uses hybrid when loaded | T014, T016 |
| SC-001 end-to-end hybrid without new library modules | Phase 3 + T033 |
| SC-002 seed + expansion diagnostics | T016, T017, T019 |
| SC-003 expanded evidence or explicit gen skip | T014, T015 |
| SC-004 comparison labels + counts | T020, T021 |
| SC-005 non-graph flows when graph missing | T009, T028 |
| SC-006 identity metadata on hybrid rows | T013, T017 |
| SC-007 empty graph-guided filter warning | T024 |
| Edge: missing graph / overlays / empty seeds / zero-added / caps / stubs | T005, T007, T011, T013, T029 |

---

## Notes

- **[P]** tasks = different cells/docs with no unfinished dependency
- **[USn]** label maps task to user story for traceability
- **No new `src/` package** and **no mandatory new unit tests** for this feature (research R10)
- Prefer surgical cell edits in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb); do not rewrite working FAISS/filter/benchmark/generation sections
- Primary architecture is **vector-first** hybrid expansion; graph-guided pre-filter is secondary only
- Full in-memory graph build may be heavy (same class as `verify_kg.py`) — report duration/stats; do not hide failures
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Constitution: expanded evidence stays citation-grounded (I); preserve `chunk_id → parent_unit_id → id_str` (II); no silent hybrid fallback or dropped warnings (III); overlays are query-time signals, stubs non-citable (IV); orchestrate existing modules (V); notebook is demo, not judged eval (VI)
