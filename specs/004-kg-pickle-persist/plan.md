# Implementation Plan: Structural Knowledge Graph Pickle Artifact

**Branch**: `004-kg-pickle-persist` | **Date**: 2026-07-15 | **Spec**: [`specs/004-kg-pickle-persist/spec.md`](spec.md)

**Input**: Feature specification from [`specs/004-kg-pickle-persist/spec.md`](spec.md)

## Summary

Add a **fast-prototype persistence path** for the existing in-memory structural knowledge graph:

```text
data/v2 structural JSONL
  → KnowledgeGraphFacade.build_graph()
  → versioned GraphPickleEnvelope
  → data/graph/knowledge_graph.gpickle
  → load in Colab / other session
  → GraphExpansion / GraphTraversal / optional dynamic overlays
```

The artifact is a portable structural graph pickle (`.gpickle`) containing only the `KnowledgeGraph` (nodes, edges, adjacency/reading-order maps) plus lightweight metadata. Validity/authority overlays are **not** frozen into the file. Neo4j remains out of scope.

Implementation is library-first (`src/knowledge_graph/persist.py` + thin facade wrappers), with an operator script (`scripts/build_kg_pickle.py`) for local build before Colab transfer, plus unit tests on fixture-scale graphs.

## Technical Context

**Language/Version**: Python 3.11+ (project notebook/src compatibility; 3.13-capable).

**Primary Dependencies**: Existing `knowledge_graph` module only. Serialization via stdlib `pickle`. No NetworkX, joblib, dill, or Neo4j required for this feature.

**Storage**:
- **Read (build)**: `data/v2/{documents,provisions,chunks,edges,external_stubs}.jsonl`
- **Write (build)**: `data/graph/knowledge_graph.gpickle` (configurable)
- **Read (load)**: the `.gpickle` artifact only (structural JSONL not required)
- **Optional after load**: overlay JSONL if user also provides them

**Testing**: `pytest` under `tests/knowledge_graph/` using existing mock dataset fixtures (`conftest.py`). Round-trip, missing-input, corrupt/incompatible load, and atomic-replace behaviors.

**Target Platform**: Local developer machine for build; Colab or local notebook/runtime for load. CPU-only. Trusted artifacts only (pickle trust boundary documented).

**Project Type**: Single project library + CLI script inside existing `L_RAG` package layout. No frontend/backend split.

**Performance Goals**:
- Avoid re-parsing multi-hundred-k JSONL rows on every Colab session when a pickle exists.
- Report build duration, core counts, and output byte size after save.
- Load path should restore a usable `KnowledgeGraph` without rebuilding from sources.
- No new hard latency SLA; success is “build once, reload fast for prototype.”

**Constraints**:
- Structural graph only; overlays stay dynamic (FR-003, US3).
- No silent JSONL rebuild when pickle load is requested (FR-016).
- No success-claimed partial artifact on failed build (FR-008).
- Preserve `chunk_id → parent_unit_id → id_str` and stub non-citability (FR-011/FR-012).
- Quarantine files never ingested (FR-013).
- No Neo4j requirement (FR-018).
- Pickle load only from trusted project-built files (research R10).

**Scale/Scope**: Full-corpus operator builds may be large (same class as `verify_kg.py`: ~150k documents / ~880k edges). CI tests use small fixtures only. Feature covers FR-001–FR-018 and SC-001–SC-007.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Yes | Snapshot preserves citation-safe structure; external stubs remain non-citable; no answer generation claims added by persistence itself. |
| II. Shared Identity Across Dataset, Vector, and Graph | Yes — core | Round-trip MUST preserve `id_str` / `unit_id` / `chunk_id` and containment maps so expansion/traversal still resolve chunk → provision → document. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Yes — core | Build reports counts/warnings; missing sources listed; failed builds do not claim success; load validates envelope version; no silent empty graph; no silent rebuild fallback. |
| IV. Legal Correctness Over Convenience | Yes | Unverified edges remain stored as today but verified-only consumers still use `verified_document_edges` after load; overlays not frozen into a false permanent currency state. |
| V. Modular, Testable, Reported Pipelines | Yes | Pure save/load module + script + tests + build report (counts, size, path). Existing builder/facade remain source of graph construction. |
| VI. Retrieval Quality and Evaluation Are Product Requirements | Partial | Persistence enables faster prototype hybrid demos; does not replace evaluation harnesses. Identities needed for evaluation remain intact. |

**Result**: PASS. No violations requiring Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/004-kg-pickle-persist/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 artifact/envelope model
├── quickstart.md        # Phase 1 operator + Colab validation
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit.tasks) — NOT created here
```

No separate `contracts/` HTTP API directory: contracts are in-process Python function signatures documented in research/data-model/quickstart.

### Source Code (repository root)

```text
src/knowledge_graph/
├── builder.py                 # EXISTING — KnowledgeGraph / GraphBuildStats / GraphBuildResult
├── facade.py                  # EXTEND — thin build_and_save_graph / load_graph wrappers
├── loader.py                  # EXISTING — GraphLoaderPaths preflight
├── expansion.py               # EXISTING consumer after load
├── traversal.py               # EXISTING consumer after load
├── overlay.py                 # EXISTING optional post-load join (unchanged)
├── persist.py                 # NEW — envelope + save/load + atomic write
├── __init__.py                # EXTEND — export persist helpers / result types
└── ...

scripts/
├── build_kg_pickle.py         # NEW — CLI: preflight → build → save → report
└── verify_kg.py               # EXISTING — full-corpus verification (unchanged by default)

tests/knowledge_graph/
├── conftest.py                # EXISTING fixtures / mock_dataset_dir
├── test_persist.py            # NEW — round-trip, failures, compatibility
└── test_facade.py             # EXTEND optional — facade save/load wrappers

data/graph/                    # NEW derived artifact directory (gitignored if large)
└── knowledge_graph.gpickle    # DEFAULT output (generated, not source-of-truth)
```

**Structure Decision**: Keep persistence inside the existing knowledge-graph package (Speckit single-project layout). The script is an operator entrypoint only; library functions are the testable contract. Derived artifacts live under `data/graph/`, separate from source `data/v2/`.

## Implementation Outline (for tasks phase)

1. Add envelope + `save_knowledge_graph` / `load_knowledge_graph` in `persist.py` with atomic replace and validation errors.
2. Export public types/functions from `__init__.py`.
3. Add facade convenience wrappers that call existing `build_graph()` then save, or load envelope.
4. Add `scripts/build_kg_pickle.py` with `--data-dir` / `--output` / optional `--force`.
5. Add `tests/knowledge_graph/test_persist.py` for round-trip and failure modes.
6. Document Colab load snippet in quickstart; ensure `.gitignore` ignores large generated pickle if appropriate.
7. Manual smoke: build from real `data/v2` when available; load without JSONL; run one expansion/traversal check.

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
