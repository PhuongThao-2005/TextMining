# Tasks: EDA Notebook for Dataset v2

**Input**: Design documents from `/specs/002-eda-v2-dataset-notebook/`

**Prerequisites**: [`plan.md`](plan.md) (required), [`spec.md`](spec.md) (required for user stories), [`research.md`](research.md), [`data-model.md`](data-model.md), [`quickstart.md`](quickstart.md)

**Tests**: Included — plan.md and quickstart.md V5 explicitly require unit tests for `src/eda/dataset_v2.py` under `tests/eda/test_dataset_v2.py` (synthetic fixtures only; never the multi-GB corpus).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/`, `notebooks/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create package/test layout and notebook shell so later phases have a stable place to land code

- [ ] T001 Create `src/eda/` package with empty [`src/eda/__init__.py`](../../src/eda/__init__.py) and stub [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) (module docstring only)
- [ ] T002 [P] Create `tests/eda/` package with empty [`tests/eda/__init__.py`](../../tests/eda/__init__.py) and placeholder [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T003 [P] Create thin notebook shell [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb) with markdown title/outline sections matching quickstart run order (Environment, Config, Preflight, Documents, Edges, Text/Structure, Validity, Authority, Reconciliation, Quality) and no analysis logic yet

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared pure helpers and result types every user story calls — streaming I/O, path resolution, missing-value coercion, preflight discovery, and config wiring

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Implement result dataclasses in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py): `PreflightResult`, `StreamCountResult`, `ReservoirSample`, `ReconciliationCheck`, `TagTally`, `VocabCoverage` per [`data-model.md`](data-model.md)
- [ ] T005 Implement `resolve_project_root() -> Path` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) using R4 (cwd has `src/` else parent) for FR-013
- [ ] T006 [P] Implement `coerce_category(value: Any) -> str` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) per R6 (`None` → `"(missing)"`; pass through `"MISSING"`/`"UNMAPPED"`; else `str(value)`)
- [ ] T007 Implement internal line-streaming JSONL reader in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) that yields parsed dicts, skips malformed lines, and exposes a skip counter (FR-014; mirror `read_jsonl` pattern from research R1 without requiring full in-memory load)
- [ ] T008 Implement `preflight(project_root: Path) -> PreflightResult` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) checking all FR-001 artifacts under `data/v2/` (JSONL files, `reconciliation_report.md`, `vocabularies/*.json`) plus presence flags for untracked raw files used later
- [ ] T009 Implement `stream_count(path: Path, category_fields: list[str], coerce_missing: bool = True) -> StreamCountResult` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) for total rows, malformed-line count, and per-field `Counter`s (FR-003/004/006/007/011 pattern)
- [ ] T010 Implement `reservoir_sample(path: Path, sample_size: int, seed: int, predicate: Callable[[dict], bool] | None = None) -> ReservoirSample` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) (Algorithm R, R2) including `rows_seen` for FR-002/FR-005
- [ ] T011 Implement `lookup_by_key(path: Path, key_field: str, key_value: str) -> dict | None` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) for on-demand single-row resolution of sampled chunk/provision rows (data-model §3, Principle I)
- [ ] T012 Wire notebook config cell in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): put `src/` on `sys.path`, call `resolve_project_root()`, set `DATASET_ROOT`, `UNTRACKED_ROOT`, `SAMPLE_SIZE` (default 5000), `SAMPLE_SEED` (default 42), `STREAM_SIZE_THRESHOLD_BYTES` (FR-012/FR-013)
- [ ] T013 Add preflight cell in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb) calling `preflight(...)` and displaying present/missing table; skip only dependent sections when files are missing (FR-001, FR-014)

**Checkpoint**: Foundation ready — `src/eda/dataset_v2.py` exposes shared helpers; notebook can resolve paths and report missing artifacts without crashing

---

## Phase 3: User Story 1 - Full-corpus statistical overview (Priority: P1) 🎯 MVP

**Goal**: One top-to-bottom runnable overview of documents, edges, text/structure, validity timeline, and authority index without loading multi-GB files into memory

**Independent Test**: With `data/v2/` populated, run notebook cells through Authority; confirm summary tables/plots for documents, edges, text_provenance/provisions/chunks, validity, authority; no unhandled exception; chunks/provisions use stream/sample only (SC-001, SC-003, SC-004 partial)

### Tests for User Story 1

> Write these tests FIRST against synthetic `tmp_path` fixtures; ensure they FAIL before implementation fills behavior

- [ ] T014 [P] [US1] Unit tests for `coerce_category` (`None` / `"MISSING"` / `"UNMAPPED"` / normal values) in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T015 [P] [US1] Unit tests for streaming counts + malformed-line skip count via `stream_count` in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T016 [P] [US1] Unit tests for `reservoir_sample` determinism (fixed seed → identical sample) and sample size bounds in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T017 [P] [US1] Unit tests for `preflight` present/missing reporting and `resolve_project_root` fallback behavior in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T018 [P] [US1] Unit tests for `lookup_by_key` first-match / not-found behavior in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)

### Implementation for User Story 1

- [ ] T019 [US1] Documents section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): use `stream_count` on `documents.jsonl` for total + distributions of `legal_authority_rank`, `loai_van_ban`, `validity_group`, `currency_hint`, `scope.code`, `legal_field.code`, `issuing_authority.code`, and `issue_year` histogram; pair every plot with a table (FR-003, FR-015, R5)
- [ ] T020 [US1] Edges section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): total count + distributions of `rel_canonical`/`rel_group`, `direction_verified` true/false proportion, `external_target` proportion (FR-004)
- [ ] T021 [US1] Text/structure section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): `text_provenance` distributions (`text_status`, `content_row_count`, `structuring_status`); stream aggregates for provisions/chunks (counts, provisions-per-doc / chunks-per-provision summary stats); reservoir sample for `chunk_text` length distribution; print `seed`, `sample_size`, `rows_seen`; resolve sample rows to `id_str` via `lookup_by_key` (FR-002, FR-005, Principle I)
- [ ] T022 [US1] Validity timeline section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): total events, `event_type` distribution, `direction_verified` split with explicit label that `false` is pending sign-off / not production-ready (FR-006)
- [ ] T023 [US1] Authority index section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): full `loai_van_ban → legal_authority_rank` table; cross-check distinct `loai_van_ban` from documents and flag unranked/`99` fallbacks (FR-007)
- [ ] T024 [US1] Harden US1 notebook sections for missing files / empty counters: skip or flag section, never crash whole run; never plot raw high-cardinality IDs (`id_str`, `edge_id`, `chunk_id`) (FR-014, FR-015)

**Checkpoint**: User Story 1 is independently runnable as MVP overview (preflight → documents → edges → text/structure → validity → authority)

---

## Phase 4: User Story 2 - Validate outputs against reconciliation report (Priority: P2)

**Goal**: Independently recompute `raw == final + quarantine` for documents and edges and compare to `reconciliation_report.md`, reporting PASS/FAIL with both number sources

**Independent Test**: Run reconciliation section; for documents and edges report three counts, `identity_holds`, `matches_report`, and any deltas vs report (SC-002; quickstart V2)

### Tests for User Story 2

- [ ] T025 [P] [US2] Unit tests for `reconcile` PASS path (identity holds + matches parsed report) in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T026 [P] [US2] Unit tests for `reconcile` FAIL path (broken identity and/or report mismatch / unparseable report) in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)

### Implementation for User Story 2

- [ ] T027 [US2] Implement report-count parser (regex over identity rows for documents/edges) and `reconcile(raw_path, final_path, quarantine_path, report_path, label) -> ReconciliationCheck` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) per R7 and data-model (FR-008)
- [ ] T028 [US2] Reconciliation section in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): call `reconcile` for documents (`metadata.jsonl` / `documents.jsonl` / `documents_quarantine.jsonl`) and edges (`relationships.jsonl` / `edges.jsonl` / `edges_quarantine.jsonl`); display PASS/FAIL, recomputed triples, report triples, and explicit deltas when mismatched (FR-008, FR-014 if raw/report missing)
- [ ] T029 [US2] Cross-link validity verified/unverified counts in notebook with reconciliation narrative (reference report P1 / Dataset_SPEC_v2 §8.2) without treating unverified as production-ready (FR-006 acceptance in US2)

**Checkpoint**: User Stories 1 and 2 both work independently; reconciliation can be demoed without quality drilldown

---

## Phase 5: User Story 3 - Drill into data-quality issues (Priority: P3)

**Goal**: Actionable quality gaps — quarantine multi-tag reasons, text_status/html flags, external stubs, controlled-vocabulary UNMAPPED/MISSING coverage

**Independent Test**: Run quality section; ranked quarantine/edge tags with separate row vs tag tallies; text_status/html percentages; stub counts + `referenced_by_edge_count` distribution; per-facet UNMAPPED/MISSING % (SC-005; quickstart V3)

### Tests for User Story 3

- [ ] T030 [P] [US3] Unit tests for `tally_tags` multi-tag accounting (row_count authoritative; one row with N tags increments N counters without double-counting rows) in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)
- [ ] T031 [P] [US3] Unit tests for `vocab_coverage` UNMAPPED/MISSING percentages per facet in [`tests/eda/test_dataset_v2.py`](../../tests/eda/test_dataset_v2.py)

### Implementation for User Story 3

- [ ] T032 [US3] Implement `tally_tags(path: Path, tag_field: str) -> TagTally` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) for list-valued reason/flag fields (FR-009, R8, Dataset_SPEC_v2 §9)
- [ ] T033 [US3] Implement `vocab_coverage(documents_path: Path, facet: str) -> VocabCoverage` in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py) for facets `issuing_authority`, `legal_field`, `sector`, `scope` (FR-011)
- [ ] T034 [US3] Quality drilldown — quarantine reasons in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): ranked `exclusion_reasons` for documents quarantine and `edge_quality_flags`/`exclusion_reasons` for edges quarantine using `tally_tags`; show row_count separate from tag_counts (FR-009)
- [ ] T035 [US3] Quality drilldown — text provenance flags in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): count/percentage per `text_status` and per `html_quality_flags` (FR-005/US3 acceptance)
- [ ] T036 [US3] Quality drilldown — external stubs in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): distinct `id_str` count, `citation_safe=false` exposure, `referenced_by_edge_count` distribution (FR-010)
- [ ] T037 [US3] Quality drilldown — vocab coverage tables in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): call `vocab_coverage` for all four facets; report exact UNMAPPED/MISSING % (FR-011, SC-005); if vocab JSON missing, report unmapped-but-referenced codes without failing silently (edge case)

**Checkpoint**: All three user stories independently functional; full notebook path covers FR-001–FR-015 for planned scope

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, packaging polish, and acceptance checklist from quickstart

- [ ] T038 [P] Export public API from [`src/eda/__init__.py`](../../src/eda/__init__.py) (`preflight`, `stream_count`, `reservoir_sample`, `reconcile`, `tally_tags`, `vocab_coverage`, `resolve_project_root`, `coerce_category`, `lookup_by_key`, result dataclasses)
- [ ] T039 Run `python -m pytest tests/eda/ -q` and fix any failures until green (quickstart V5)
- [ ] T040 Validate notebook run-order narrative and section guards in [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb): every plot paired with table; sample metadata printed; Vietnamese labels via tables even if plot glyphs fail (FR-015, R5); confirm no whole-file load of `chunks.jsonl`/`provisions.jsonl` (SC-003)
- [ ] T041 Execute quickstart acceptance checklist items that are automatable (preflight missing-file path with a renamed optional file conceptually documented; reconciliation PASS/FAIL display; unit tests) and update any residual gaps in notebook markdown only if needed for SC-001–SC-005 clarity
- [ ] T042 [P] Sanity-check [`specs/002-eda-v2-dataset-notebook/quickstart.md`](quickstart.md) paths still match implemented module/notebook/test locations (docs-only; no behavior change)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP path
- **User Story 2 (Phase 4)**: Depends on Foundational; notebook sections may sit after US1 cells but logic/tests are independent
- **User Story 3 (Phase 5)**: Depends on Foundational; independent of US2 module APIs except shared streaming helpers
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 only — no dependency on US2/US3
- **User Story 2 (P2)**: After Phase 2 — uses `reconcile` + raw/final/quarantine paths; independent of quality drilldown
- **User Story 3 (P3)**: After Phase 2 — uses `tally_tags` / `vocab_coverage`; independent of reconciliation

### Within Each User Story

- Tests (T014–T018, T025–T026, T030–T031) should be written to fail first, then pass as implementation lands
- Module helpers before notebook cells that call them
- Story complete and independently testable before treating next priority as required for MVP

### Parallel Opportunities

- Phase 1: T002 and T003 can run in parallel after/with T001 package path
- Phase 2: T006 can parallelize with T005 once T004 exists; T014–T018 tests can be drafted while notebook US1 cells are written once helpers stabilize
- Phase 3: T014–T018 tests are parallel; T019–T023 notebook sections are sequential in run order but can be authored in parallel if helpers are done
- Phase 4: T025/T026 parallel; T027 then T028/T029
- Phase 5: T030/T031 parallel; T032/T033 can be parallel after tests sketched; T034–T037 sequential in notebook narrative
- Phase 6: T038 and T042 parallel; T039–T041 sequential validation

---

## Parallel Example: User Story 1

```bash
# After Phase 2 helpers exist, launch US1 unit tests together:
Task: "Unit tests for coerce_category in tests/eda/test_dataset_v2.py"
Task: "Unit tests for stream_count malformed-line skip in tests/eda/test_dataset_v2.py"
Task: "Unit tests for reservoir_sample determinism in tests/eda/test_dataset_v2.py"
Task: "Unit tests for preflight / resolve_project_root in tests/eda/test_dataset_v2.py"
Task: "Unit tests for lookup_by_key in tests/eda/test_dataset_v2.py"

# Then implement notebook sections (prefer documents → edges → text → validity → authority):
Task: "Documents section in notebooks/eda_v2_dataset.ipynb"
Task: "Edges section in notebooks/eda_v2_dataset.ipynb"
```

---

## Parallel Example: User Story 3

```bash
# Tests in parallel:
Task: "Unit tests for tally_tags multi-tag accounting in tests/eda/test_dataset_v2.py"
Task: "Unit tests for vocab_coverage percentages in tests/eda/test_dataset_v2.py"

# Module helpers in parallel after tests sketched:
Task: "Implement tally_tags in src/eda/dataset_v2.py"
Task: "Implement vocab_coverage in src/eda/dataset_v2.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)  
3. Complete Phase 3: User Story 1 (tests + overview sections)  
4. **STOP and VALIDATE**: Run preflight → documents/edges/text/validity/authority; `pytest tests/eda/ -q` for US1 coverage  
5. Demo MVP overview notebook  

### Incremental Delivery

1. Setup + Foundational → foundation ready  
2. Add US1 → independent overview MVP  
3. Add US2 → reconciliation gate (SC-002)  
4. Add US3 → quality backlog inputs (SC-005)  
5. Polish → full quickstart acceptance  

### Parallel Team Strategy

With multiple developers after Foundational:

- Developer A: US1 notebook sections + related tests  
- Developer B: US2 `reconcile` + notebook section + tests  
- Developer C: US3 `tally_tags` / `vocab_coverage` + quality cells + tests  

Integrate in notebook run order without breaking earlier sections (FR-014).

---

## Requirements Traceability (summary)

| Requirement | Primary tasks |
| --- | --- |
| FR-001 preflight | T008, T013 |
| FR-002 stream/sample large files | T007, T009, T010, T021 |
| FR-003 documents overview | T019 |
| FR-004 edges overview | T020 |
| FR-005 text/structure | T021, T035 |
| FR-006 validity + pending sign-off | T022, T029 |
| FR-007 authority index | T023 |
| FR-008 reconciliation identities | T027, T028 |
| FR-009 quarantine multi-tag reasons | T032, T034 |
| FR-010 external stubs | T036 |
| FR-011 vocab coverage | T033, T037 |
| FR-012 config cell | T012 |
| FR-013 project root resolution | T005, T012 |
| FR-014 skip/flag missing/malformed | T007, T013, T024, T028 |
| FR-015 human labels / no raw ID plots | T019, T024, T040 |
| SC-001–SC-005 | Phase 3–6 validation (T039–T041) |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks  
- [USn] label maps task to user story for traceability  
- Do **not** point unit tests at real multi-GB `data/v2/chunks.jsonl` or `provisions.jsonl`  
- Notebook remains thin orchestration; heavy logic stays in [`src/eda/dataset_v2.py`](../../src/eda/dataset_v2.py)  
- Commit after each task or logical group  
- Stop at any checkpoint to validate the story independently  
