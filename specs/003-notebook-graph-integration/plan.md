# Implementation Plan: Notebook Graph Module Integration

**Branch**: `003-notebook-graph-integration` | **Date**: 2026-07-15 | **Spec**: [`specs/003-notebook-graph-integration/spec.md`](spec.md)

**Input**: Feature specification from [`specs/003-notebook-graph-integration/spec.md`](spec.md)

## Summary

Extend the existing top-to-bottom-runnable notebook [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) so it demonstrates the project's primary hybrid pipeline:

```text
query → embed → vector seed retrieval → graph expansion + validity/authority overlays → optional LLM generation
```

The notebook already loads FAISS, runs vector filter profiles, and generates answers via `src/generation/reasoning_client.py`. It currently constructs `VectorRetriever` **without** a graph expansion service and explicitly says `graph_guided` is not exercised. This feature wires the existing knowledge-graph module (`KnowledgeGraphFacade`, `GraphExpansion`, overlays, optional `GraphGuidedFilter`) into that notebook as orchestration only — no new library package, no reimplementation of graph/retrieval logic.

Secondary path: optional graph-guided pre-filter demo (whitelist-before-vector-search) remains available and must surface empty-filter warnings, but is not the default full-pipeline story.

## Technical Context

**Language/Version**: Python 3.11+ / 3.13-compatible Jupyter kernel (`ipykernel`), consistent with `src/` and prior notebook features.

**Primary Dependencies**: Existing project modules only — `knowledge_graph` (facade, expansion, overlays, context), `retrieval` (FAISS/SQLite store, `VectorRetriever`, embedder, config), `generation.reasoning_client`. Runtime deps already used by the notebook: `faiss-cpu`, `sentence-transformers`, `pandas`, `openai`. No new third-party dependency.

**Storage**: Read-only access to:
- `data/faiss_index/` (`index.faiss`, `payloads.jsonl`, optional `id_map.json` / `payload_cache.sqlite`)
- `data/v2/` structural graph sources (`documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `external_stubs.jsonl`)
- optional overlay sources (`validity_timeline.jsonl`, `authority_index.jsonl`)

No mutation of source dataset/index artifacts (FR-019). Optional existing payload-cache rebuild behavior from feature `001` remains unchanged and is FAISS-local, not a graph write.

**Testing**: No new mandatory unit-test module. Rely on existing `tests/knowledge_graph/*`, retrieval tests, and notebook quickstart validation scenarios. Dedicated graph verification remains [`scripts/verify_kg.py`](../../scripts/verify_kg.py); judged evaluation remains [`scripts/evaluate_e2e.py`](../../scripts/evaluate_e2e.py).

**Target Platform**: Local developer machine or hosted notebook environment; CPU-capable. Runnable from project root or `notebooks/` via existing root-resolution pattern (FR-016).

**Project Type**: Single project — notebook integration over existing modules. No frontend/backend split, no new service boundary.

**Performance Goals**: Notebook must remain usable as a demo. Full in-memory graph build may be heavy (same class of cost as `verify_kg.py`); report build duration and stats. Hybrid query path must respect configured caps (`top_n`, expansion `max_hop` / `max_context`) and show truncation when capping occurs. No new hard latency SLA beyond existing retrieval/generation behavior.

**Constraints**:
- Primary path is vector-first hybrid expansion, not graph whitelist first (FR-001).
- Hybrid mode requested while graph unavailable MUST fail clearly (FR-015); never silent vector-only under a hybrid label.
- Distinguish graph expansion from local `expand_units` (FR-018).
- External stubs / non-citation-safe nodes are never citation-ready evidence (FR-013).
- Secrets never hardcoded; FAISS/graph inputs read-only (FR-019).
- Pure vector-only profiles (`current_law`, `broad`, `historical`) remain fully usable without a successful graph load (FR-010).

**Scale/Scope**: One existing notebook extended in place; notebook-local orchestration helpers only; covers FR-001–FR-022 and SC-001–SC-007. No Neo4j, no new evaluation harness, no new `src/` package.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Yes | Expanded evidence remains grounded in retrieved/scroll-fetched chunk text with citation metadata; generation still consumes CONTEXT only via existing reasoning client. Empty evidence skips generation explicitly (FR-014). Stubs are non-citable (FR-013). |
| II. Shared Identity Across Dataset, Vector, and Graph | Yes — core | End-to-end displays keep `chunk_id → parent_unit_id → id_str` (FR-012, SC-006). Expansion resolves through graph chunk/provision/document maps using those same keys. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Yes — core | Preflight lists missing graph files (FR-003); expansion warnings (missing seeds/parents) are printed (US2); empty graph-guided filters warn and do not silently unfilter (FR-020, SC-007); hybrid-without-graph fails clearly (FR-015). |
| IV. Legal Correctness Over Convenience | Yes | Overlays join at query time for configurable `as_of_date`; missing overlays are labeled rather than inventing currency/authority (Edge Cases). Unverified edges remain a graph-module concern; notebook does not treat stubs or unverified overlays as binding current law. |
| V. Modular, Testable, Reported Pipelines | Yes | Notebook orchestrates existing modules with clear contracts (`GraphBuildStats`, `ExpansionResult`, `DocumentOverlay`, `GraphGuidedFilter`, `RetrievalResult`, `GenerationOutcome`) instead of reimplementing graph logic (FR-002). Build stats and diagnostics provide smoke-check reporting (FR-004/FR-005). |
| VI. Retrieval Quality and Evaluation Are Product Requirements | Partial | Notebook is a demonstration/validation surface (FR-017), not a replacement for `verify_kg.py` or `evaluate_e2e.py`. It preserves evaluation-friendly identities and mode labels so judged pipelines can still be run separately. |

**Result**: PASS. No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/003-notebook-graph-integration/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created here)
```

No `contracts/` directory: this feature has no API/service boundary — it orchestrates existing in-process modules inside a notebook.

### Source Code (repository root)

```text
src/
├── knowledge_graph/                 # EXISTING — integration surface (unchanged by default)
│   ├── facade.py                    # KnowledgeGraphFacade build/traverse/overlay/filter
│   ├── expansion.py                 # GraphExpansion.expand(seed_chunk_ids, ...)
│   ├── expansion_schema.py          # ExpansionResult / ExpansionStep
│   ├── overlay.py / overlay_schema.py
│   ├── context.py / context_schema.py  # GraphGuidedFilter, EvidenceContext
│   ├── loader.py                    # GraphLoaderPaths.required_paths / validate
│   └── builder.py                   # GraphBuildResult / GraphBuildStats / KnowledgeGraph
│
├── retrieval/                       # EXISTING — already accepts graph hooks
│   ├── retriever.py                 # VectorRetriever(graph_expansion=..., graph_guided_filter=...)
│   ├── schema.py                    # RetrievedChunk / RetrievalResult
│   ├── sqlite_faiss_store.py        # payload lookup / scroll for expanded chunk ids
│   └── ...
│
└── generation/
    └── reasoning_client.py          # EXISTING — format_context_for_prompt / generate_answer

notebooks/
└── faiss_retrieval_ready.ipynb      # EXTENDED (primary deliverable)
                                      # - config: hybrid flags, as_of_date, expansion caps
                                      # - graph preflight + load + overlay join + stats
                                      # - wire GraphExpansion into retriever
                                      # - hybrid search diagnostics (seed vs expanded)
                                      # - vector-only vs hybrid comparison
                                      # - optional graph-guided pre-filter demo
                                      # - ask() default full pipeline uses hybrid evidence when enabled

scripts/
├── verify_kg.py                     # EXISTING authoritative graph verification (unchanged)
└── evaluate_e2e.py                  # EXISTING judged evaluation (unchanged)

tests/
└── knowledge_graph/                 # EXISTING — no required new tests for this feature
```

**Structure Decision**: Single-project notebook integration (Speckit Option 1 style, no frontend/backend split). Unlike `001` and `002`, this feature does **not** extract a new `src/` module: the graph and retrieval contracts already exist and are unit-tested. The notebook becomes the hybrid demonstration surface by importing those modules, matching FR-002/SC-001 and research.md R2. Dedicated verification/evaluation scripts remain authoritative outside the notebook (FR-017).

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
