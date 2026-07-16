# Implementation Plan: Colab-Safe Full Pipeline Memory Fit

**Branch**: `005-colab-ram-fit` | **Date**: 2026-07-16 | **Spec**: [`specs/005-colab-ram-fit/spec.md`](spec.md)

**Input**: Feature specification from [`specs/005-colab-ram-fit/spec.md`](spec.md)

## Summary

Adapt full-pipeline notebook [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) so **Colab-safe profile** can complete vector retrieval and (when artifacts allow) hybrid expansion on **~12GB RAM** hosted runtime without OOM kills.

```text
Local build once:
  FAISS artifacts + payload_cache.sqlite
  scripts/build_kg_pickle.py → data/graph/knowledge_graph.gpickle

Colab-safe session:
  load plan / memory diagnostics
  → FAISS + embedder + vector smoke
  → structural graph via pickle (preferred) OR skip hybrid
  → optional overlays
  → one hybrid query (if graph loaded)
  → optional remote generation
  → heavy exports/benchmarks only with explicit opt-in
```

Feature is **policy + packaging + notebook orchestration**:

- Prefer feature `004` portable structural graph pickle over full v2 JSONL rebuild.
- Gate heavy optional cells (CSV export, cache download, large benchmarks, JSONL rebuild).
- Stage pipeline so peak residency bounded.
- Keep pure vector-only usable; **never** silently label vector results as hybrid.
- Keep unconstrained/local profile for fuller demos on higher-RAM machines.

No new hybrid ranking algorithm, no silent embedder swap, no local in-process LLM requirement.

## Technical Context

**Language/Version**: Python 3.11+ / 3.13-compatible Jupyter kernel (`ipykernel`), consistent with existing notebook/`src/` stack.

**Primary Dependencies**: Existing project modules only:

- `retrieval` — `SQLitePayloadFaissVectorStore`, `VectorRetriever`, `SentenceTransformerEmbedder`, `VectorIndexConfig`
- `knowledge_graph` — `KnowledgeGraphFacade`, `GraphExpansion`, overlays, **`load_knowledge_graph` / `facade.load_graph`** (feature 004)
- `generation.reasoning_client` — remote OpenAI-compatible generation

Runtime deps already used by notebook: `faiss-cpu`, `sentence-transformers`, `pandas`/`csv` for optional exports, `openai`. Optional diagnostics: `psutil` if present (not hard-required). No new required third-party dependency for Colab-safe success.

**Storage** (read-only sources + allowed derived cache):

- **Required vector path**: `data/faiss_index/index.faiss`, `payloads.jsonl`; prefer prebuilt `payload_cache.sqlite`; optional `id_map.json`
- **Preferred hybrid path**: `data/graph/knowledge_graph.gpickle` (or Colab upload path)
- **Optional overlays**: `validity_timeline.jsonl`, `authority_index.jsonl`
- **Optional unconstrained rebuild inputs**: full structural `data/v2/*.jsonl`
- **Allowed mutation**: existing payload-cache rebuild behavior only; no mutation of source FAISS/v2 artifacts beyond that

**Testing**:

- Primary validation: quickstart scenarios on Colab-class RAM (or policy simulation when 12GB hardware unavailable)
- If pure helpers extracted from notebook, add focused unit tests under `tests/`
- No mandatory new judged evaluation harness; reuse existing retrieval/graph tests for underlying modules

**Target Platform**: Google Colab free ~12GB RAM (or equivalent hosted notebook) for Colab-safe success; local/high-RAM for unconstrained profile. CPU-only valid (FR-022). GPU optional.

**Project Type**: Single-project notebook integration over existing modules. No frontend/backend split, no new service boundary.

**Performance Goals**:

- Default Colab-safe path completes setup + at least one sample vector query without OOM (SC-001)
- With pickle + FAISS present, completes hybrid setup via pickle load + one hybrid query without OOM (SC-002)
- Prefer pickle load latency over full-corpus JSONL rebuild
- Report load plan, artifact sizes, best-effort memory/RSS around major loads
- No new hard latency SLA beyond “demo usable”

**Constraints**:

- ~12GB RAM success bar for Colab-safe defaults (not every optional cell combined)
- No silent hybrid fallback (FR-005/FR-006/FR-023)
- No silent full JSONL graph rebuild under Colab-safe (FR-003/FR-004)
- No default embedder identity change that invalidates FAISS (FR-013)
- Preserve `chunk_id → parent_unit_id → id_str` and citation safety (FR-014)
- Secrets stay environment-based (FR-015)
- Graph-guided pre-filter remains secondary and off by default under Colab-safe (FR-021)
- Unconstrained profile must remain available (FR-018)

**Scale/Scope**: One notebook adapted in place; optional tiny pure helper module; documentation of artifact packs and staged workflow; covers FR-001–FR-023 and SC-001–SC-010. Does not rebuild FAISS, does not host local LLMs, does not replace `verify_kg.py` / `evaluate_e2e.py`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Yes | Colab-safe path still surfaces citation-ready chunk/provision/document identities; stubs remain non-citable; generation still grounded in retrieved/expanded evidence or explicitly skipped. |
| II. Shared Identity Across Dataset, Vector, and Graph | Yes — core | Pickle load + vector payloads preserve `chunk_id → parent_unit_id → id_str` (FR-014, SC-009). No new opaque IDs. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Yes — core | Load plan lists present/missing artifacts and graph source mode; cache rebuild warned; hybrid unavailable is explicit; no silent vector-as-hybrid; no silent JSONL rebuild under Colab-safe. |
| IV. Legal Correctness Over Convenience | Yes | Overlays remain optional dynamic joins; missing overlays do not invent currency/authority; stubs not presented as citation-ready. |
| V. Modular, Testable, Reported Pipelines | Yes | Reuses retrieval/graph/generation modules; notebook orchestrates profiles/staging; optional pure helpers can be unit-tested; preflight/load reports provide operator visibility. |
| VI. Retrieval Quality and Evaluation Are Product Requirements | Partial | Feature enables demos/validation on constrained RAM; does not replace evaluation scripts. Conservative caps may reduce context breadth on Colab-safe — acceptable and labeled, with unconstrained profile retaining fuller demos. |

**Result**: PASS. No violations requiring Complexity Tracking entries.

### Post-design re-check

Phase 1 entities (`RuntimeProfile`, `LoadPlan`, graph source mode, staged session, opt-in gates) are policy/orchestration shapes over existing modules. Strengthen Principle III (visibility, no silent fallback) without weakening identity or citation rules. Gate remains **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/005-colab-ram-fit/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 runtime/profile entities
├── quickstart.md        # Phase 1 operator + Colab validation
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit.tasks) — NOT created here
```

No separate `contracts/` directory: contracts are notebook config flags, load-plan fields, existing in-process module APIs documented in research/data-model/quickstart.

### Source Code (repository root)

```text
notebooks/
└── faiss_retrieval_ready.ipynb   # PRIMARY DELIVERABLE — EXTEND
                                  # - RUNTIME_PROFILE / COLAB_SAFE flags
                                  # - conservative caps when Colab-safe
                                  # - load plan + memory diagnostics
                                  # - graph load: pickle preferred; JSONL rebuild opt-in
                                  # - staged vector → graph → generate
                                  # - opt-in gates for CSV export, cache download,
                                  #   large benchmark, graph-guided, JSONL rebuild
                                  # - cleanup/release helper
                                  # - success labels: vector_only / hybrid_pickle / hybrid_unavailable

src/
├── knowledge_graph/              # EXISTING — consume pickle load APIs (004)
│   ├── persist.py                # load_knowledge_graph
│   ├── facade.py                 # load_graph / build_graph
│   ├── expansion.py
│   └── overlay.py
├── retrieval/                    # EXISTING — FAISS + SQLite payload cache
│   ├── sqlite_faiss_store.py
│   ├── retriever.py
│   ├── embeddings.py
│   └── config.py
│   # OPTIONAL NEW (only if extracted): colab_runtime.py / runtime_profile helpers
└── generation/
    └── reasoning_client.py       # EXISTING remote generator

scripts/
├── build_kg_pickle.py            # EXISTING (004) — local pickle build for Colab pack
├── _patch_faiss_hybrid_notebook.py  # EXISTING optional patcher pattern; may extend
└── verify_kg.py / evaluate_e2e.py   # UNCHANGED authoritative tools

tests/
└── (optional) unit tests only if pure helpers extracted from notebook
```

**Structure Decision**: Single-project notebook adaptation (Speckit Option 1 style). Same stance as feature `003`: orchestration over existing modules. Feature `004` supplies portable graph artifact this feature consumes. Prefer notebook-local helpers; extract tiny pure module only if branching worth unit testing.

## Implementation Outline (for tasks phase)

1. Add top-level `RUNTIME_PROFILE` / `COLAB_SAFE` and related opt-in flags + conservative cap defaults.
2. Add load-plan / preflight printer (artifact inventory, sizes, planned load/skip/defer, graph source mode).
3. Add best-effort memory snapshot helper (optional `psutil` / platform fallbacks).
4. Change graph load cell to prefer `load_knowledge_graph(GRAPH_PICKLE_PATH)`; require `ALLOW_JSONL_GRAPH_REBUILD` under Colab-safe for JSONL rebuild; wire `GraphExpansion` as today when graph ready.
5. Gate eager optional cells (`export_payloads_to_csv()`, `export_payload_cache_sqlite()`, benchmark auto-runs, heavy loops) behind flags so Colab-safe “Run all” skips them.
6. Ensure staged usability: vector smoke before graph load; hybrid only after graph stage; generation optional.
7. Add cleanup/release helper and success-mode messaging (`vector_only` vs hybrid pickle success vs hybrid unavailable).
8. Preserve `require_graph_for_hybrid()` no-silent-fallback behavior for hybrid-labeled paths.
9. Update intro markdown + quickstart artifact packs / staged operator workflow.
10. Manual validation against quickstart scenarios (policy checks locally; RAM fit on Colab-class runtime when available).

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
