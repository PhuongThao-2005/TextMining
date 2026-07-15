# Tasks: Structural Knowledge Graph Pickle Artifact

**Input**: Design documents from `/specs/004-kg-pickle-persist/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: **Required** — plan.md and research R8 require unit/integration tests under [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) using existing `mock_dataset_dir` / `tmp_path` fixtures. Cover round-trip, missing inputs, corrupt/incompatible load, atomic replace, and overlays-not-required. Full-corpus build is operator smoke only (not CI).

**Organization**: Tasks grouped by user story. Library-first (`persist.py` + facade wrappers); operator script is thin CLI over library. No Neo4j, no FAISS packaging, no silent JSONL rebuild on load.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependency)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project under `L_RAG/`: `src/`, `scripts/`, `tests/` at repository root (per plan.md)
- Paths below relative to `L_RAG/`
- Primary library deliverable: [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py)
- Operator entrypoint: [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py)
- Default artifact: `data/graph/knowledge_graph.gpickle` (derived; covered by existing `data/` gitignore)
- Read/import only (do not reimplement builder/loader): [`src/knowledge_graph/builder.py`](../../src/knowledge_graph/builder.py), [`src/knowledge_graph/loader.py`](../../src/knowledge_graph/loader.py), [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create empty module/test/script shells so later tasks share stable paths

- [x] T001 Create stub [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) with module docstring only (portable structural graph pickle; stdlib `pickle`; trusted artifacts only; no NetworkX)
- [x] T002 [P] Create placeholder [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) with module docstring / import scaffolding only
- [x] T003 [P] Create stub [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py) with module docstring + `PROJECT_ROOT` / `sys.path` insert pattern mirroring [`scripts/verify_kg.py`](../../scripts/verify_kg.py)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Envelope types, pure save/load, atomic write, package exports — **must complete before any user-story build/load path claims success**

**⚠️ CRITICAL**: No US1–US4 work should treat envelope/version validation or atomic write as optional

- [x] T004 Implement frozen dataclasses in [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) per [`data-model.md`](data-model.md) §3: `GraphPickleEnvelope` (`format_name`, `format_version`, `created_at_utc`, `source_data_dir`, `stats`, `warnings`, `graph`), `GraphPickleArtifactInfo` (`path`, `format_version`, `byte_size`, `created_at_utc`, `stats`), `GraphPickleLoadResult` (`graph`, `format_version`, `created_at_utc`, `source_data_dir`, `stats`, `warnings`, `path`)
- [x] T005 Implement constants + error types in [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py): `FORMAT_NAME = "g-lrag-knowledge-graph"`, `FORMAT_VERSION = 1`, supported versions set, and clear exception types/messages for missing file, corrupt/unreadable pickle, incompatible format/version (FR-009, FR-017, research R3)
- [x] T006 Implement `save_knowledge_graph(graph, path, *, stats=None, warnings=(), source_data_dir=None) -> GraphPickleArtifactInfo` in [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py): wrap `KnowledgeGraph` in envelope; create parent dirs; write temp in same directory then `os.replace` final path; return path/size/version/stats; on serialize failure clean temp and leave prior final artifact intact (FR-002, FR-008, FR-010, FR-017, research R6)
- [x] T007 Implement `load_knowledge_graph(path) -> GraphPickleLoadResult` in [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py): open + unpickle; require `format_name` + supported `format_version`; require `graph` is `KnowledgeGraph`; return load result; never return empty silent graph; never rebuild from JSONL (FR-004, FR-009, FR-016, SC-006)
- [x] T008 Export public persist surface from [`src/knowledge_graph/__init__.py`](../../src/knowledge_graph/__init__.py): at least `save_knowledge_graph`, `load_knowledge_graph`, `GraphPickleEnvelope`, `GraphPickleArtifactInfo`, `GraphPickleLoadResult` (and any public error types)
- [x] T009 Add thin facade wrappers on [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py): `build_and_save_graph(output_path, ...)` → existing `build_graph()` then `save_knowledge_graph`; `load_graph(path)` → `load_knowledge_graph` (return graph + metadata without auto-overlays or JSONL fallback) (research R4)

**Checkpoint**: Foundation ready — importable save/load; envelope versioned; atomic write; facade wrappers present; no user-story CLI required yet

---

## Phase 3: User Story 1 - Build a portable structural graph file once (Priority: P1) 🎯 MVP

**Goal**: Operator can build structural KG from v2 JSONL and write one `.gpickle` with reconcilable counts report

**Independent Test**: With structural sources present (fixture or real `data/v2`), run build/save path; confirm artifact exists, counts printed, missing sources fail without success artifact (SC-001, SC-005; quickstart V1)

### Tests for User Story 1

> Write these tests FIRST against `mock_dataset_dir` / `tmp_path`; ensure they FAIL before save/CLI implementation lands

- [x] T010 [P] [US1] Unit tests: fixture graph → `save_knowledge_graph` writes file under `tmp_path`, returns `GraphPickleArtifactInfo` with `byte_size > 0` and `format_version == 1` in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-001, FR-017)
- [x] T011 [P] [US1] Unit tests: missing structural inputs via `GraphLoaderPaths` / facade build-and-save fail with explicit missing-path list and do **not** create final success artifact in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-006, FR-008, SC-005)
- [x] T012 [P] [US1] Unit tests: save creates missing parent output directory (or documents/assert explicit failure) in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (Edge Cases, FR-010)

### Implementation for User Story 1

- [x] T013 [US1] Implement operator CLI in [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py): argparse `--data-dir` (default `data/v2`), `--output` (default `data/graph/knowledge_graph.gpickle`), optional `--force`; preflight via `GraphLoaderPaths.required_paths()` / `validate()`; `KnowledgeGraphFacade(paths=...).build_graph()`; `save_knowledge_graph(...)`; print duration, core counts (documents, external stubs, provisions, chunks, document edges, verified vs unverified, structural edges), warning count, output path, byte size; non-zero exit on failure (FR-001, FR-006, FR-007, FR-014, SC-001)
- [x] T014 [US1] Ensure saved payload is structural only: envelope graph fields match `KnowledgeGraph` (nodes, document/verified/structural edges, adjacency/reading-order maps); **no** `OverlayBundle` / validity / authority in pickle (FR-002, FR-003)
- [x] T015 [US1] Confirm quarantine files never appear in loader inputs (rely on existing `GraphLoaderPaths` five-file contract; assert in test or script comments) (FR-013)

**Checkpoint**: User Story 1 independently runnable as MVP — script build + fixture tests green

---

## Phase 4: User Story 2 - Load graph pickle without rebuilding (Priority: P1)

**Goal**: Load restores usable structural `KnowledgeGraph` for expansion/traversal without structural JSONL present

**Independent Test**: Load pickle in process without reading `data/v2` structural files; counts match metadata; sample `chunk_id → parent_unit_id → id_str` resolves; consumers accept graph (SC-002, SC-003; quickstart V2)

### Tests for User Story 2

- [x] T016 [P] [US2] Unit tests: round-trip save → load restores core counts and sample identities (`chunk_id` → `parent_unit_id` → `id_str`) plus adjacency maps usable in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-004, FR-005, FR-011, SC-002, SC-003)
- [x] T017 [P] [US2] Unit tests: missing pickle path raises clear file-not-found; corrupt bytes raise clear unreadable/corrupt error; wrong `format_name` / unknown `format_version` raise clear incompatible-artifact error — never empty success graph in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-009, SC-006)
- [x] T018 [P] [US2] Unit tests: loaded graph usable by `GraphExpansion(graph)` and/or facade `traverse(...)` smoke on fixture ids in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-005)
- [x] T019 [P] [US2] Unit tests: external stubs remain `citation_safe is False` after load; verified vs full document edge sets remain distinct in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-012)

### Implementation for User Story 2

- [x] T020 [US2] Harden load validation messages in [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) so Colab/operators get actionable errors (missing / corrupt / incompatible) without JSONL fallback (FR-004, FR-009, FR-016)
- [x] T021 [US2] Optional facade wrapper tests or light extension in [`tests/knowledge_graph/test_facade.py`](../../tests/knowledge_graph/test_facade.py): `build_and_save_graph` + `load_graph` round-trip on `mock_dataset_dir` (research R8 optional)
- [x] T022 [US2] Document load contract smoke checks (counts vs metadata; identity walk) remain as in [`quickstart.md`](quickstart.md) §3 — no silent empty graph (SC-002, SC-003)

**Checkpoint**: US1 + US2 — build once, load anywhere with project code; consumers work

---

## Phase 5: User Story 3 - Keep overlays dynamic and optional after pickle load (Priority: P2)

**Goal**: Structural load never requires overlays; when overlay files present, join dynamically without mutating pickle

**Independent Test**: Load pickle without overlay files → expansion works; with overlay files → `build_overlay_bundle` works on loaded `graph.documents` (SC-004; quickstart V3)

### Tests for User Story 3

- [x] T023 [P] [US3] Unit tests: load succeeds with no overlay files in environment; envelope/graph contain no overlay types in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-003, SC-004)
- [x] T024 [P] [US3] Unit tests: after load, `KnowledgeGraphFacade.build_overlay_bundle(...)` joins fixture validity/authority events onto loaded documents without rebuilding structural pickle in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (US3 scenarios 2–3)

### Implementation for User Story 3

- [x] T025 [US3] Ensure facade `load_graph` / `load_knowledge_graph` never auto-call overlay join; overlays remain explicit post-load step (document in facade/persist docstrings) (FR-003, FR-016)
- [x] T026 [US3] Align operator/docs path with quickstart §4: optional overlay join example after structural load only (FR-015)

**Checkpoint**: Structural pickle independent of overlays; dynamic join still available

---

## Phase 6: User Story 4 - Rebuild and replace the artifact when sources change (Priority: P3)

**Goal**: Explicit rebuild to same path replaces previous artifact after successful write only

**Independent Test**: Save twice to same path; second successful build replaces file; failed rebuild leaves previous final artifact intact (US4; quickstart V4)

### Tests for User Story 4

- [x] T027 [P] [US4] Unit tests: two successful saves to same path — final file is second write (mtime/size or embedded `created_at_utc` / stats change) in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-008, US4)
- [x] T028 [P] [US4] Unit tests: after successful first save, forced serialize/build failure path does not replace final artifact with partial temp (best-effort temp cleanup) in [`tests/knowledge_graph/test_persist.py`](../../tests/knowledge_graph/test_persist.py) (FR-008, research R6)

### Implementation for User Story 4

- [x] T029 [US4] Wire CLI rebuild behavior in [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py): same `--output` replaces only after full successful build+save; optional `--force` if implemented for “overwrite existing” messaging without silent skip (FR-010, FR-016)
- [x] T030 [US4] Confirm rebuild remains explicit user action — no `load_or_build` silent JSONL fallback API in v1 (FR-016, research R7)

**Checkpoint**: Explicit replace-on-rebuild; no partial success artifact

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Package hygiene, trust docs, quickstart acceptance, regression

- [x] T031 [P] Confirm [`L_RAG/.gitignore`](../../.gitignore) already ignores `data/` (covers `data/graph/*.gpickle`); add explicit `*.gpickle` or `data/graph/` only if project later un-ignores `data/` subsets
- [x] T032 [P] Module docstring / quickstart trust note: load only project-built trusted pickles (research R10); Colab needs project `src/` (or package) importable for class unpickle (FR-015)
- [x] T033 [P] Sanity-check [`specs/004-kg-pickle-persist/quickstart.md`](quickstart.md) CLI flags, import paths (`load_knowledge_graph`), and default output match implementation (docs-only if drift)
- [x] T034 Run unit suite: `python -m pytest tests/knowledge_graph/test_persist.py -q` (and full `tests/knowledge_graph -q` regression) — expect green
- [x] T035 Execute quickstart validation narrative V1–V5 when fixture/real data available: build artifact; load without JSONL; overlays optional; explicit rebuild; bad load inputs (SC-001–SC-007)
- [x] T036 Optional operator smoke (when `data/v2` present): `python scripts/build_kg_pickle.py --data-dir data/v2 --output data/graph/knowledge_graph.gpickle` then load smoke snippet from quickstart §7 — not a CI blocker

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP build/save path
- **User Story 2 (Phase 4)**: Depends on Foundational + save path (round-trip needs T006); load validation can start once T007 exists
- **User Story 3 (Phase 5)**: Depends on US2 load restoring a real `KnowledgeGraph`
- **User Story 4 (Phase 6)**: Depends on save atomic-write behavior (Phase 2); CLI rebuild after US1 script exists
- **Polish (Phase 7)**: Depends on desired user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 only — core build → pickle MVP
- **User Story 2 (P1)**: After save exists; co-equal P1 with US1 for “portable artifact useful”
- **User Story 3 (P2)**: After load works; tests overlay independence
- **User Story 4 (P3)**: After save/replace semantics; not required for first Colab load demo

### Within Each User Story

- Tests first (where listed) against failing stubs
- Library behavior before CLI polish
- Story independently demoable before treating next priority as required for MVP

### Parallel Opportunities

- Phase 1: T002 and T003 parallel after T001
- Phase 2: T004–T005 types/constants first; T006 save then T007 load; T008/T009 after save/load signatures stable
- Phase 3: T010–T012 tests parallel; then T013–T015 implementation
- Phase 4: T016–T019 tests parallel; T020–T022 after load solid
- Phase 5: T023–T024 parallel; T025–T026 docs/guards
- Phase 6: T027–T028 parallel; T029–T030 CLI/API policy
- Phase 7: T031–T033 parallel; T034–T036 validation sequential

---

## Parallel Example: User Story 1

```bash
# After Phase 2 save_knowledge_graph exists:
Task: "test save writes GraphPickleArtifactInfo under tmp_path"
Task: "test missing structural inputs fail with no final artifact"
Task: "test parent output dir created"

# Then operator surface:
Task: "scripts/build_kg_pickle.py CLI preflight → build → save → report"
```

---

## Parallel Example: User Story 2 (after save)

```bash
Task: "round-trip identity + counts tests"
Task: "missing/corrupt/incompatible load error tests"
Task: "GraphExpansion / traverse smoke on loaded graph"
Task: "external stub citation_safe + verified edge set tests"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 Setup
2. Complete Phase 2 Foundational (envelope + save/load + exports + facade wrappers)
3. Complete Phase 3 US1 tests + CLI build
4. Complete Phase 4 US2 load/round-trip tests + validation hardening
5. **STOP and validate**: fixture round-trip green; optional real `data/v2` build if available
6. Deploy/demo: transfer `.gpickle` → Colab load snippet from quickstart

### Incremental Delivery

1. Setup + Foundational → library importable
2. US1 → operator can produce artifact (SC-001/SC-005)
3. US2 → Colab/session load without JSONL (SC-002/SC-003/SC-006)
4. US3 → overlay independence proven (SC-004)
5. US4 → safe explicit rebuild (FR-008)
6. Polish → quickstart V1–V5 + regression

### Suggested MVP Task Cut Line

T001–T022 (Setup + Foundational + US1 + US2). US3/US4 and full polish can follow without blocking first portable Colab load.

---

## Notes

- [P] tasks = different files / no unfinished dependency
- [Story] label maps task to user story for traceability
- Each user story independently testable at its checkpoint
- Commit after each task or logical group
- Avoid: NetworkX, Neo4j, freezing overlays, silent JSONL rebuild on load, success-claimed partial pickle
- Trust boundary: pickle load only for project-built artifacts (research R10)
- Full-corpus operator smoke optional; CI stays fixture-scale
