# Tasks: Colab-Safe Full Pipeline Memory Fit

**Input**: Design documents from `/specs/005-colab-ram-fit/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: **Not required for this feature** unless pure helpers are extracted from the notebook. Plan/research R11: validation is primarily quickstart scenarios (V1–V12) and policy checks; reuse existing `tests/knowledge_graph/*` and retrieval tests for underlying modules only. If a tiny pure module (e.g. `src/retrieval/colab_runtime.py` or `src/utils/runtime_profile.py`) is extracted, add focused unit tests under `tests/` for profile resolution, graph source mode, and inventory helpers.

**Organization**: Tasks grouped by user story. Same stance as feature `003`: thin notebook orchestration over existing `retrieval`, `knowledge_graph` (004 pickle APIs), and `generation` modules. **No** new hybrid ranking algorithm, **no** silent embedder swap, **no** local in-process LLM.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different cells/helpers/docs with no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- Single project under `L_RAG/`: `src/`, `notebooks/`, `scripts/`, `tests/` at repository root (per plan.md)
- Paths below relative to `L_RAG/`
- Primary deliverable: [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb)
- Consume only (do not reimplement): [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) (`load_knowledge_graph`), [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py) (`load_graph` / `build_graph`), retrieval FAISS/SQLite store, [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py)
- Optional extract: `src/retrieval/colab_runtime.py` or `src/utils/runtime_profile.py` (only if branching worth unit tests)
- Optional patcher: extend [`scripts/_patch_faiss_hybrid_notebook.py`](../../scripts/_patch_faiss_hybrid_notebook.py) or sibling for idempotent notebook updates
- Operator pickle build (already exists from 004): [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Orient the existing hybrid notebook for Colab-safe profile work without changing retrieval/hybrid semantics yet

- [ ] T001 Inventory current sections of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) that affect RAM / Colab policy: config cell (`ENABLE_HYBRID_*`, caps), FAISS/embedder load, graph build cell (current JSONL `build_graph()` path), hybrid helpers (`require_graph_for_hybrid`, `run_hybrid_retrieve`, `ask()`), eager heavy cells (`export_payloads_to_csv()`, payload-cache export, benchmark/auto demos, graph-guided), and mark insertion points for profile / load-plan / staged docs
- [ ] T002 [P] Confirm 004 pickle load surface is importable for notebook use: `load_knowledge_graph` / `KnowledgeGraphFacade.load_graph`, default path `data/graph/knowledge_graph.gpickle`, no auto-JSONL fallback on load (research R3; FR-003/FR-004)
- [ ] T003 [P] Add notebook markdown outline for Colab-safe vs unconstrained profiles, staged run order (vector → graph → generate → opt-in heavy), and artifact packs pointer to [`specs/005-colab-ram-fit/quickstart.md`](quickstart.md) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (FR-017, US5 preview)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Profile switch, conservative caps, graph-source policy types, load-plan + memory helpers, and extended graph-load status — **must complete before user-story demos claim Colab-safe success**

**⚠️ CRITICAL**: No US1–US5 work should claim Colab-safe hybrid success until profile flags, pickle-prefer graph policy, and load-plan visibility exist

- [ ] T004 Extend top config cell in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with `RuntimeProfile` knobs per [`data-model.md`](data-model.md) §3.1 / quickstart: `RUNTIME_PROFILE` (`"colab_safe"` | `"unconstrained"`), `COLAB_SAFE` convenience alias, `GRAPH_PICKLE_PATH`, `ALLOW_JSONL_GRAPH_REBUILD` (default `False` under Colab-safe), conservative caps when Colab-safe (`TOP_K=20`, `TOP_N` 5–8, `HYBRID_MAX_HOP=1`, `HYBRID_MAX_CONTEXT=8`), heavy opt-in flags default False under Colab-safe (`RUN_PAYLOAD_CSV_EXPORT`, `RUN_PAYLOAD_CACHE_EXPORT`, `RUN_BENCHMARK_SAMPLE`, `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO`, optional `RUN_FILTER_PROFILE_COMPARISON`), `BENCHMARK_SAMPLE_SIZE` small when enabled, keep `EMBEDDING_MODEL` matching FAISS (FR-001, FR-007, FR-008, FR-013, FR-018, FR-019, FR-021, research R2/R7/R8)
- [ ] T005 Implement notebook-local (or optional pure helper) graph source decision + status extensions in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): `GraphSourceMode` (`pickle` | `jsonl_rebuild` | `unavailable`), extended `GraphLoadStatus` fields (`graph_source_mode`, `pickle_path`, `loaded_from_pickle`, `rebuild_opt_in_required`, `rebuild_warning_emitted`) per data-model §3.3/§3.8; decision rules under Colab-safe: pickle present → pickle; else JSONL + opt-in → warn rebuild; else unavailable (FR-003, FR-004, SC-005, SC-006, research R3)
- [ ] T006 Implement `ArtifactPresence` inventory + `ComponentLoadAction` / `LoadPlan` builder+printer in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (or optional pure helper): list FAISS (`index.faiss`, `payloads.jsonl`, `payload_cache.sqlite`, `id_map.json`), graph pickle, structural v2 JSONL set, overlays; present/missing + approximate sizes; planned load/reuse/defer/skip/opt_in_required/warn_rebuild; print profile, graph source mode, hybrid_expected (FR-009, data-model §3.2–3.5, research R5)
- [ ] T007 [P] Implement best-effort `MemorySnapshot` helper in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (or optional pure helper): prefer optional `psutil`; fallbacks `/proc/self/status` VmRSS / `resource.getrusage`; if unavailable print note and continue — never block retrieval (FR-010, data-model §3.6)
- [ ] T008 [P] Implement `ResidentComponentSnapshot` printer (store, embedder, structural graph, graph source mode, overlays, hybrid ready, generator configured, optional frames held) for use after major loads (FR-009, data-model §3.7)
- [ ] T009 Preserve and reaffirm hybrid availability guard: existing `require_graph_for_hybrid()` remains hard fail for hybrid-labeled paths; pure vector remains usable without graph (FR-005, FR-006, research R9) — no behavioral regression in Foundational

**Checkpoint**: Foundation ready — Colab-safe profile + caps + load-plan/memory helpers + graph source mode decision exist; hybrid guard intact; graph load cell not yet switched to pickle-prefer (that is US1)

---

## Phase 3: User Story 1 - Run the full hybrid demo on a 12GB Colab runtime (Priority: P1) 🎯 MVP

**Goal**: With Colab-safe defaults and hybrid artifact pack (FAISS + `knowledge_graph.gpickle`), complete setup + one hybrid query via pickle load (not full JSONL rebuild) without OOM on ~12GB-class path; heavy optional cells off by default

**Independent Test**: Colab-safe profile, pickle present, `ALLOW_JSONL_GRAPH_REBUILD=False` → Stages A–C + one hybrid sample; load plan reports `pickle`; hybrid labels used; no silent JSONL rebuild (SC-002, SC-005; quickstart V2)

### Tests for User Story 1

> No new mandatory unit tests. Optional: if pure graph-source/load-plan helpers extracted, unit-test decision table (pickle / opt-in rebuild / unavailable). Policy smoke can be run by executing notebook cells or a small pure-function test.

### Implementation for User Story 1

- [ ] T010 [US1] Replace/extend graph load cell in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) to prefer `load_knowledge_graph(GRAPH_PICKLE_PATH)` / `facade.load_graph` when pickle present; under Colab-safe never auto-`build_graph()` from full v2 JSONL without `ALLOW_JSONL_GRAPH_REBUILD=True` + explicit warning that rebuild may exceed 12GB; on skip set `structural_ready=False` and hybrid unavailable (FR-003, FR-004, SC-002, SC-005, SC-006, research R3)
- [ ] T011 [US1] After successful pickle (or opt-in rebuild) load, wire `GraphExpansion` / hybrid retriever as today; keep overlays optional join after structural load without requiring overlays for hybrid success (FR-016, SC-002)
- [ ] T012 [US1] Gate heavy optional cell **bodies** so Colab-safe default Run-all skips them: wrap/call `export_payloads_to_csv()` only if `RUN_PAYLOAD_CSV_EXPORT`; gate payload-cache export on `RUN_PAYLOAD_CACHE_EXPORT`; keep `run_benchmark_sample` / large loops off unless `RUN_BENCHMARK_SAMPLE`; keep `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` False under Colab-safe; functions may remain defined (FR-007, FR-019, SC-003, research R7)
- [ ] T013 [US1] Apply Colab-safe conservative caps to hybrid helper / demo path (`TOP_K`, `TOP_N`, `HYBRID_MAX_HOP`, `HYBRID_MAX_CONTEXT`) and ensure expansion still reports `capped=True` when truncated (FR-008)
- [ ] T014 [US1] Add success-mode messaging helpers / prints using `SessionOutcomeLabel` rules: `hybrid_colab_safe_success_pickle` only when structural graph loaded (preferably pickle) and hybrid path used; never conflate with vector-only (FR-023, data-model §3.10)
- [ ] T015 [US1] Demo cell path under Colab-safe: after pickle graph load, run one sample hybrid query (`run_hybrid_retrieve` / hybrid `ask()` optional); print hybrid labels and optional generation skip if no credentials (US1 scenarios 1–3, SC-002)
- [ ] T016 [US1] Payload-cache path under Colab-safe: when cache missing/stale, print explicit warning that cold rebuild from `payloads.jsonl` can be costly before existing store rebuild proceeds (FR-020, research R10)

**Checkpoint**: US1 MVP — Colab-safe hybrid via pickle + gated heavy cells + success labels; no silent JSONL rebuild

---

## Phase 4: User Story 2 - See memory pressure and choose a safe load path (Priority: P1)

**Goal**: Preflight/load plan and diagnostics show profile, artifact inventory/sizes, planned actions, graph source mode, and resident components so operators avoid accidental full rebuilds

**Independent Test**: Run preflight under Colab-safe with both pickle and JSONL present → inventory + planned graph source `pickle`; after loads, resident snapshot visible (SC-005; quickstart V4)

### Implementation for User Story 2

- [ ] T017 [US2] Add/execute preflight cell early (Stage A) in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb): call load-plan builder (T006), print profile, artifacts, actions, graph source mode, optional `MemorySnapshot` before major loads (FR-009, FR-010, US2 scenarios 1–2)
- [ ] T018 [US2] Capture and print `MemorySnapshot` (best-effort) around major load points: preflight, after FAISS/embedder load, after graph load, after heavy optional cells if run (FR-010, research R5)
- [ ] T019 [US2] After vector and graph stages, print `ResidentComponentSnapshot` so ownership of store/embedder/graph/overlays is visible (US2 scenario 4, data-model §3.7)
- [ ] T020 [US2] When pickle missing + JSONL present + Colab-safe + `ALLOW_JSONL_GRAPH_REBUILD=False`, preflight/graph stage messages must state hybrid unavailable or rebuild requires opt-in — never silent rebuild start (US2 scenario 3, SC-006, Edge Cases)

**Checkpoint**: US1 + US2 — operators see load plan and graph source mode before/during heavy loads

---

## Phase 5: User Story 3 - Keep pure vector retrieval usable when hybrid is too heavy (Priority: P2)

**Goal**: Vector-only path works without loading structural graph; hybrid-labeled calls fail clearly; results never silently labeled hybrid

**Independent Test**: Graph skipped/unavailable under Colab-safe → sample vector query labeled `vector_only`; hybrid helper raises/clear `hybrid_unavailable` (SC-001, SC-004; quickstart V1, V6)

### Implementation for User Story 3

- [ ] T021 [US3] Ensure Stage B (FAISS + embedder + vector smoke) runs and supports pure vector queries without Stage C graph load in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (FR-005, FR-011, SC-001, SC-004)
- [ ] T022 [US3] Vector-only success messaging: when graph not used, label results/session as `vector_only` / `vector_only_colab_safe_success` — no hybrid wording (FR-023, research R9)
- [ ] T023 [US3] Hybrid request without loaded graph: `require_graph_for_hybrid()` / hybrid `ask()` / hybrid demos fail clearly or report `hybrid_unavailable` — never return silent vector results under hybrid name (FR-006, SC-004, US3 scenario 2)
- [ ] T024 [US3] Optional graph diagnostics when graph skipped: report unavailable/skipped and do not attempt full JSONL rebuild by default under Colab-safe (US3 scenario 3, FR-004)

**Checkpoint**: Graceful explicit degradation — vector-only usable; hybrid never silent

---

## Phase 6: User Story 4 - Stage the pipeline so peak RAM stays bounded (Priority: P2)

**Goal**: Documented staged order (config → vector → graph → generate → opt-in heavy); default Run-all skips Stage E; best-effort cleanup between stages

**Independent Test**: Run Stage B then later Stage C without undocumented edits; Colab-safe Run-all does not execute heavy export/benchmark bodies (SC-003, SC-007; quickstart V3, V7)

### Implementation for User Story 4

- [ ] T025 [US4] Structure/reorder notebook markdown + cell comments in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) for staged execution: Stage A config/preflight; Stage B vector load+smoke; Stage C graph (pickle preferred)+hybrid smoke; Stage D optional generation; Stage E opt-in heavy demos only (FR-011, research R6, data-model §3.9)
- [ ] T026 [US4] Verify default Colab-safe top-to-bottom execution does not call Stage E bodies unless corresponding flags true (ties to T012; SC-003, FR-019)
- [ ] T027 [US4] Implement best-effort `CleanupRequest` / `release_optional_objects(...)` helper: drop export/comparison frames; optional unload overlays/structural graph; `gc.collect()`; document that hybrid becomes unavailable if graph unloaded; not OS memory reservation (FR-012, data-model §3.11, Edge Cases)
- [ ] T028 [US4] Confirm hybrid becomes available after Stage C without requiring kernel restart solely for staging (unless user explicitly freed graph via cleanup) (US4 scenario 2, SC-007)

**Checkpoint**: Staged UX + cleanup helper; peak RAM controllable without deleting unconstrained capabilities

---

## Phase 7: User Story 5 - Document the Colab artifact pack and operator workflow (Priority: P3)

**Goal**: Operators can list vector-only vs hybrid packs, Colab-safe flags, staged order, and unconstrained opt-out from docs alone

**Independent Test**: New operator reading quickstart (+ notebook intro) identifies packs A/B, flags, avoid-list, unconstrained switch (SC-008, SC-010; quickstart V8, V10)

### Implementation for User Story 5

- [ ] T029 [P] [US5] Align notebook intro/config markdown in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) with [`quickstart.md`](quickstart.md): vector-only pack, hybrid pack (FAISS + gpickle; overlays optional; full JSONL not required when pickle present), avoid-on-12GB list (FR-017, SC-008)
- [ ] T030 [P] [US5] Document unconstrained profile switch in notebook + ensure [`quickstart.md`](quickstart.md) still describes fuller demos (exports, larger samples, optional JSONL rebuild) when `RUNTIME_PROFILE="unconstrained"` (FR-018, SC-010)
- [ ] T031 [P] [US5] Sanity-check [`specs/005-colab-ram-fit/quickstart.md`](quickstart.md) flags, paths, stage order, and success labels match implemented notebook config (docs-only fix if drift)

**Checkpoint**: Documentation contract complete; unconstrained path not permanently removed

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Citation safety, secrets/read-only, CPU-only validity, regression, full quickstart acceptance

- [ ] T032 [P] Audit Colab-safe vector/hybrid display paths for FR-014 / SC-009: citation-ready rows expose `chunk_id` → `parent_unit_id` → `id_str`; external stubs / non-citation-safe nodes not presented as citable (quickstart V9)
- [ ] T033 [P] Confirm no hardcoded secrets; generator remains env-based; no mutation of source FAISS/v2 beyond allowed payload-cache rebuild (FR-015)
- [ ] T034 Confirm CPU-only path remains valid (no GPU required for Colab-safe success messaging) (FR-022)
- [ ] T035 Confirm embedder identity not silently swapped under Colab-safe; alternate model only with explicit user config + matching index (FR-013, Edge Cases)
- [ ] T036 [P] If pure helpers were extracted, add focused unit tests under `tests/` for graph source mode decision, profile defaults, and artifact inventory; otherwise skip (research R11)
- [ ] T037 Run existing regression smoke (optional but recommended): `python -m pytest tests/knowledge_graph -q` (and retrieval tests if store messaging touched) — expect green; no new mandatory suite if logic stays notebook-local
- [ ] T038 Execute quickstart validation narrative V1–V12 against [`quickstart.md`](quickstart.md): vector-only Colab-safe; hybrid pickle; Run-all skips heavy; load plan pickle preference; no silent JSONL rebuild; hybrid-without-graph clear fail; staged order; packs documented; citation identities; unconstrained still available; cache rebuild warning; overlays optional — fix residual notebook gaps (SC-001–SC-010)
- [ ] T039 Optional live ~12GB Colab (or equivalent) run for SC-001 and SC-002 when hardware available; policy checks may validate locally without true 12GB session
- [ ] T040 [P] Optional: extend [`scripts/_patch_faiss_hybrid_notebook.py`](../../scripts/_patch_faiss_hybrid_notebook.py) or add sibling patcher for idempotent Colab-safe cell updates if that is the chosen edit tactic (implementation convenience only)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories that claim Colab-safe behavior
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP pickle hybrid + heavy gates
- **User Story 2 (Phase 4)**: Depends on Foundational load-plan/memory helpers (T006–T008); should ship with or immediately after US1 so operators see why loads are safe
- **User Story 3 (Phase 5)**: Depends on Foundational hybrid guard + Stage B usability; can proceed once graph load can be skipped (T010 skip path)
- **User Story 4 (Phase 6)**: Depends on Foundational + heavy gates (T012); staging docs after stages exist
- **User Story 5 (Phase 7)**: Docs alignment; can start in parallel with polish once flags/cells stable
- **Polish (Phase 8)**: Depends on desired user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — core Colab-safe hybrid MVP (pickle + gates + labels)
- **User Story 2 (P1)**: After Phase 2 helpers; co-equal P1 for “safe path visible”; preflight cell uses T006–T007
- **User Story 3 (P2)**: After skip-graph path exists; strengthens labeling and clear hybrid failure
- **User Story 4 (P2)**: After gates + vector/graph stages; staging + cleanup
- **User Story 5 (P3)**: Documentation; quickstart already drafted in planning — notebook/docs sync

### Within Each User Story

- Profile/caps before claiming Colab-safe defaults
- Graph source decision before pickle load cell
- Load plan before/at major loads
- Heavy cell gates before “Run all” claims
- Success labels after real load modes exist
- Story independently demoable before treating next priority as required for MVP

### Parallel Opportunities

- Phase 1: T002 and T003 parallel after T001 inventory
- Phase 2: T004 config first; T005 graph-source types; T006 load plan; T007/T008 memory/resident parallel; T009 guard check parallel
- Phase 3: T010–T011 graph path sequential; T012 gates parallelizable with T013 caps; T014–T016 after load path works
- Phase 4: T017–T020 sequential over shared load-plan objects
- Phase 5: T021–T024 after skip-graph path
- Phase 6: T025–T028 after Stage E gates exist
- Phase 7: T029–T031 parallel docs
- Phase 8: T032–T035 parallel audits; T036–T039 validation sequential; T040 optional

---

## Parallel Example: User Story 1 (after Foundational)

```bash
# Graph path
Task: "Prefer load_knowledge_graph(GRAPH_PICKLE_PATH); block silent JSONL rebuild under Colab-safe"

# Gates + caps (can parallel once config flags exist)
Task: "Gate export_payloads_to_csv / cache export / benchmark / graph-guided behind RUN_* flags"
Task: "Apply Colab-safe TOP_K/TOP_N/HYBRID_MAX_CONTEXT caps + capped reporting"

# Then demo + messaging
Task: "SessionOutcomeLabel hybrid_colab_safe_success_pickle vs vector_only"
Task: "One sample hybrid query demo under Colab-safe"
Task: "Warn before cold payload_cache.sqlite rebuild"
```

---

## Parallel Example: Diagnostics + Degradation (after US1 graph skip path)

```bash
Task: "Preflight LoadPlan cell (US2)"
Task: "MemorySnapshot around major loads (US2)"
Task: "vector_only success label without graph (US3)"
Task: "hybrid_unavailable clear failure (US3)"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (inventory + outline)
2. Complete Phase 2: Foundational (profile, caps, load plan, memory, graph source mode, hybrid guard)
3. Complete Phase 3: User Story 1 (pickle graph load, heavy gates, caps, success labels, hybrid demo, cache warning)
4. Complete Phase 4: User Story 2 (preflight execution, memory/resident prints, no-silent-rebuild messaging)
5. **STOP and VALIDATE**: quickstart V2 + V3 + V4 + V5 (policy); optional ~12GB for SC-002
6. Demo: Colab-safe Run-all through hybrid smoke without heavy exports

### Incremental Delivery

1. Setup + Foundational → profile and diagnostics ready
2. Add US1 → MVP Colab-safe hybrid via pickle (SC-002, SC-003, SC-005, SC-006)
3. Add US2 → load plan / memory visibility (FR-009, FR-010)
4. Add US3 → vector-only degradation + clear hybrid failure (SC-001, SC-004)
5. Add US4 → staging + cleanup (SC-007)
6. Add US5 → docs packs/workflow sync (SC-008, SC-010)
7. Polish → full quickstart V1–V12 + optional live Colab

### Suggested MVP Task Cut Line

T001–T020 (Setup + Foundational + US1 + US2). US3/US4/US5 and full polish follow without blocking first Colab-safe hybrid demo.

### Parallel Team Strategy

With multiple developers after Foundational:

- Developer A: US1 graph pickle load + hybrid demo + success labels
- Developer B: US1 heavy cell gates + US4 staging/cleanup
- Developer C: US2 preflight/memory prints + US3 vector-only labeling

Integrate in notebook run order without breaking existing FAISS/filter/hybrid/generation sections from 001/003.

---

## Requirements Traceability (summary)

| Requirement | Primary tasks |
| --- | --- |
| FR-001 Colab-safe profile | T004, T003 |
| FR-002 setup + sample query on ~12GB defaults | T010–T015, T021, T038–T039 |
| FR-003 prefer portable graph pickle | T005, T010, T017, SC-005 |
| FR-004 no default JSONL rebuild; opt-in + warn | T005, T010, T020, T024 |
| FR-005 vector usable; hybrid unavailable labeled | T009, T021–T023 |
| FR-006 hybrid without graph fails clearly | T009, T023 |
| FR-007 heavy optional cells off by default | T004, T012, T026 |
| FR-008 conservative caps + capped report | T004, T013 |
| FR-009 load plan / preflight | T006, T017, T019 |
| FR-010 memory signals optional | T007, T018 |
| FR-011 staged execution | T025, T021, T028 |
| FR-012 cleanup/release helper | T027 |
| FR-013 no silent embedder swap | T004, T035 |
| FR-014 identities + citation safety | T032 |
| FR-015 no secrets; read-only sources | T033, T016 |
| FR-016 overlays optional | T011, T038 (V12) |
| FR-017 document operator workflow | T003, T029–T031 |
| FR-018 unconstrained profile remains | T004, T030 |
| FR-019 Run-all skips opt-in heavy | T012, T026 |
| FR-020 payload cache rebuild warning | T016 |
| FR-021 graph-guided secondary off Colab-safe | T004, T012 |
| FR-022 CPU-only valid | T034 |
| FR-023 success labels distinct | T014, T022, T023 |
| SC-001 vector-only ~12GB | T021–T022, T039 |
| SC-002 hybrid pickle ~12GB | T010–T015, T039 |
| SC-003 Run-all skips heavy | T012, T026 |
| SC-004 vector usable; hybrid clear fail | T021–T023 |
| SC-005 pickle over rebuild | T005, T010, T017 |
| SC-006 no silent JSONL rebuild | T010, T020 |
| SC-007 staged documented steps | T025, T028 |
| SC-008 artifact packs documented | T029, T031 |
| SC-009 citation identities | T032 |
| SC-010 unconstrained fuller demos | T030 |

---

## Notes

- **[P]** tasks = different cells/docs/helpers with no unfinished dependency
- **[USn]** label maps task to user story for traceability
- **Primary surface**: adapt [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) in place (research R1) — no separate primary Colab product notebook required
- Prefer notebook-local helpers; extract tiny pure module only if branching worth unit tests (research R11)
- Reuse 004 pickle APIs; do not reimplement pickle format or JSONL builder
- Preserve 003 hybrid semantics and `require_graph_for_hybrid()` no-silent-fallback contract
- Success bar is **default Colab-safe path**, not every optional cell combined
- Policy checks (graph mode, gates, labels) can validate locally; true RAM-fit SC-001/SC-002 confirm on Colab-class hardware when available
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Constitution: citation-grounded evidence (I); preserve `chunk_id → parent_unit_id → id_str` (II); load plan + no silent hybrid/JSONL fallback (III); overlays optional, stubs non-citable (IV); orchestrate existing modules (V); notebook enables demos, not judged eval replacement (VI)
