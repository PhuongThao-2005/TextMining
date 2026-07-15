# Implementation Plan: EDA Notebook for Dataset v2

**Branch**: `002-eda-v2-dataset-notebook` | **Date**: 2026-07-15 | **Spec**: [`specs/002-eda-v2-dataset-notebook/spec.md`](spec.md)

**Input**: Feature specification from [`specs/002-eda-v2-dataset-notebook/spec.md`](spec.md)

## Summary

Build a single, top-to-bottom-runnable Jupyter notebook (`notebooks/eda_v2_dataset.ipynb`) that gives a full statistical overview, reconciliation cross-check, and data-quality drilldown across all four layers of `data/v2/` (`documents.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `text_provenance.jsonl`, `validity_timeline.jsonl`, `authority_index.jsonl`, the two `*_quarantine.jsonl` files, `reconciliation_report.md`, and `vocabularies/*.json`). The notebook must never fully load the ~2.6 GB `chunks.jsonl` or ~1.8 GB `provisions.jsonl` into memory; it must stream them line-by-line for full-corpus aggregates and use seeded reservoir sampling for any record-level inspection.

Technical approach: extract the reusable, testable logic (streaming JSONL aggregation, reservoir sampling, reconciliation-identity checks, multi-tag reason tallying, preflight file discovery) into a small new module `src/eda/dataset_v2.py`, mirroring how [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) is a thin orchestration layer over `src/retrieval/`. The notebook itself only configures parameters and calls into this module, keeping cells short and the heavy logic unit-testable under `tests/eda/`.

## Technical Context

**Language/Version**: Python 3.11 (Jupyter notebook via `ipykernel`), consistent with the rest of `src/`.

**Primary Dependencies**: `pandas` 2.3.2, `matplotlib` 3.10.6, `numpy` 2.2.6 — all already present in the environment (verified via `python -c "import pandas, matplotlib, numpy"`). No new dependency is required.

**Storage**: Read-only access to `data/v2/*.jsonl`, `data/v2/vocabularies/*.json`, `data/v2/reconciliation_report.md`, and `data/untracked_data/metadata.jsonl` / `relationships.jsonl`. No writes to these paths (Assumptions, spec.md).

**Testing**: `pytest` (already configured via `pyproject.toml` `[tool.pytest.ini_options]`, `pythonpath = ["src"]`). New unit tests under `tests/eda/test_dataset_v2.py` cover the extracted streaming/sampling/reconciliation helpers against small synthetic JSONL fixtures (not the real multi-GB files).

**Target Platform**: Local developer machine (Windows/Linux), CPU only, run via Jupyter/VS Code notebook kernel from either the project root or `notebooks/`.

**Project Type**: Single project — a notebook plus one small supporting library module and its tests. No frontend/backend split.

**Performance Goals**: Full run over the current `data/v2/` corpus (151,624 documents, 883,256 edges, ~1.39M provisions, ~1.51M chunks) must complete without loading `chunks.jsonl` (2.6 GB) or `provisions.jsonl` (1.8 GB) fully into memory; streaming passes are I/O-bound and expected to take longer than a typical lightweight EDA notebook (Assumptions, spec.md) — no hard latency budget, but peak process memory during those two files' aggregation passes should stay in the tens-of-MB range (bounded by counters/accumulators, not row count).

**Constraints**: No new heavyweight visualization dependency; Vietnamese labels must render without requiring a non-default font (fallback: always pair a plot with its underlying table); must not crash on missing files, malformed JSON lines, or `None`/`"MISSING"`/`"UNMAPPED"` category values; must not plot raw high-cardinality identifiers (`id_str`, `edge_id`, `chunk_id`).

**Scale/Scope**: 11 JSONL artifacts + 1 markdown report + 4 vocabulary JSON files, spanning ~194 MB (`documents.jsonl`) to ~2.64 GB (`chunks.jsonl`); three prioritized user stories (P1 overview, P2 reconciliation, P3 quality drilldown) covering FR-001–FR-015 and SC-001–SC-005.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Partial | The notebook doesn't generate answers, but every chunk/provision-level summary must still resolve `chunk_id → parent_unit_id → id_str` when displaying examples (FR-005, FR-015). Design honors this: sampled chunk/provision rows are always joined back to their `id_str`/citation label before display, never shown as bare identifiers. |
| II. Shared Identity Across Dataset, Vector, and Graph | Yes | All cross-file joins (chunks→provisions, documents↔quarantine, edges↔stubs) use the canonical `id_str`/`unit_id`/`chunk_id` keys already in the files; the notebook introduces no new IDs. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Yes — core of this feature | US2 (FR-008) independently recomputes `raw == final + quarantine` for documents and edges; US3 (FR-009) tallies quarantine/edge-quality reasons as tags without double-counting rows, per §9 of Dataset_SPEC_v2. Missing files or unparseable lines are reported and skipped (FR-014), never silently dropped. |
| IV. Legal Correctness Over Convenience | Yes | FR-006 explicitly labels the `direction_verified = false` majority in `validity_timeline.jsonl` as pending sign-off, not production-ready, matching the constitution's rule that graph/validity builders must not treat unverified direction as usable. The notebook is read-only and doesn't build/consume the graph, so it only has to *report* this correctly, which it does. |
| V. Modular, Testable, Reported Pipelines | Yes — drives the design | Streaming/sampling/reconciliation logic is extracted into `src/eda/dataset_v2.py` with unit tests (`tests/eda/test_dataset_v2.py`) rather than left as untestable inline notebook code, matching "Modules MUST expose clear contracts... tests." |
| VI. Retrieval Quality and Evaluation Are Product Requirements | N/A | This feature is dataset EDA, not retrieval or generation; it does not touch retrieval quality metrics. Explicitly out of scope per spec.md Assumptions (vector index and knowledge graph EDA are covered elsewhere). |

**Result**: PASS. No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/002-eda-v2-dataset-notebook/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created here)
```

No `contracts/` directory: this feature has no API/service boundary — it is a notebook plus a local helper module, not a network-facing contract.

### Source Code (repository root)

```text
src/
└── eda/
    ├── __init__.py
    └── dataset_v2.py        # preflight discovery, streaming JSONL aggregation,
                              # reservoir sampling, reconciliation-identity checks,
                              # multi-tag reason tallying, project-root resolution —
                              # pure functions, no notebook-only state, no I/O side
                              # effects beyond reading data/v2 & data/untracked_data.

notebooks/
└── eda_v2_dataset.ipynb     # Thin orchestration notebook: config cell, preflight
                              # cell, one section per artifact (documents, edges,
                              # text/structure, validity, authority, reconciliation,
                              # quality drilldown), each calling into src/eda/dataset_v2.py.

tests/
└── eda/
    ├── __init__.py
    └── test_dataset_v2.py   # Unit tests against small synthetic JSONL fixtures
                              # (tmp_path-based), not the real multi-GB files:
                              # streaming counts, reservoir-sample determinism/seed,
                              # reconciliation PASS/FAIL, multi-tag tally correctness,
                              # malformed-line skip-and-count behavior.
```

**Structure Decision**: Single project, option 1 style (no frontend/backend split). This follows the precedent set by `001-faiss-retrieval-notebook`, which pairs a thin notebook with the pre-existing `src/retrieval/` module; here there is no pre-existing EDA module, so a small new `src/eda/` package is created to hold the only logic in this feature that benefits from unit testing (streaming/sampling/reconciliation correctness). Everything else (table/plot rendering, cell narrative) stays in the notebook itself, since notebook display code is not meaningfully unit-testable and duplicating that effort would violate default-to-action scoping.

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
