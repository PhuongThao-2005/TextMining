# Phase 0 Research: Notebook Graph Module Integration

## R1: Primary hybrid path — vector-first expand, not graph whitelist first

**Decision**: Make the notebook's default full pipeline:

```text
query → embed → vector seed search → graph expansion (+ overlays) → optional generation
```

Keep graph-guided pre-filter (`GraphGuidedFilter` whitelist before vector search) as an optional secondary demo only.

**Rationale**: Spec FR-001 / User Story 1 explicitly corrected the primary path to vector-first. The retrieval module already supports both contracts: `GraphExpansion` on seed hits ([`src/retrieval/retriever.py`](../../src/retrieval/retriever.py)) and `graph_guided_filter` / `id_str_filter` as a hard whitelist. The notebook currently prints that `graph_guided` is not exercised and constructs `VectorRetriever` without a `graph_expansion` service. Aligning the notebook with vector-first matches the corrected architecture and the existing module split in [`docs/spec/GRAPH_MODULE.md`](../../docs/spec/GRAPH_MODULE.md) §10 and [`docs/spec/RETRIEVE_MODULE.md`](../../docs/spec/RETRIEVE_MODULE.md) §11–13.

**Alternatives considered**:
- Default to graph-guided pre-filter (whitelist-before-search) — rejected: contradicts the corrected primary pipeline and would hide semantic seed retrieval behind a document whitelist that is harder to demo and easier to empty.
- Invent a third fused ranker inside the notebook — rejected: out of scope; fusion already means seed + expanded evidence assembly before generation, not a new ranking library.

## R2: Where new logic lives — thin notebook orchestration over existing modules

**Decision**: Do **not** create a new `src/` package for this feature. Extend [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) as a thin orchestration layer that imports:

- `knowledge_graph.KnowledgeGraphFacade`, `GraphExpansion`, overlay parsers/joiners, `GraphGuidedFilter`
- existing `retrieval.VectorRetriever`, store, embedder, config
- existing `generation.reasoning_client` helpers

Add only notebook-local helper functions for preflight, diagnostics, seed-vs-expanded comparison, and `ask()` wiring.

**Rationale**: FR-002 and SC-001 require using the project's knowledge-graph module rather than re-implementing graph logic, and SC-001 says a user can run the demo "without writing new library modules by hand." Graph build, expansion, overlays, and graph-guided filters already exist under `src/knowledge_graph/`; retrieval already accepts `graph_expansion` and `graph_guided_filter`. Unlike features `001` and `002`, there is no untested notebook-only algorithm that must be extracted for Constitution Principle V — the testable logic already has unit tests under `tests/knowledge_graph/` and is exercised by [`scripts/verify_kg.py`](../../scripts/verify_kg.py).

**Alternatives considered**:
- Extract a new `src/hybrid/` or `src/notebooks/` helper package — rejected as overscoped for a demonstration notebook that only wires existing contracts; would add maintenance surface without new legal/retrieval behavior.
- Inline reimplementation of expansion/overlay join in notebook cells — rejected by FR-002 and Constitution Principles II–V.

## R3: How to show seed hits vs graph-expanded evidence

**Decision**: Implement a notebook hybrid helper that always preserves two stages:

1. **Seed stage**: vector retrieve with `expand_units=False` (or an explicit seed-only pass) to capture seed `chunk_id` / counts / sample rows.
2. **Expansion stage**: when hybrid is enabled and graph is loaded, call `GraphExpansion.expand(seed_chunk_ids, max_hop=..., max_context=...)`, resolve expanded chunk payloads via store `scroll`, attach document overlays by `id_str`, and label the result as graph expansion (not local `expand_units`).

Wire `VectorRetriever(..., graph_expansion=GraphExpansion(graph))` so normal hybrid retrieval can also use the module path when `expand_units=True`, but keep diagnostics driven by the explicit two-stage helper so seed vs expanded never collapses into one opaque list.

**Rationale**: FR-007/FR-011/FR-018 and User Story 2 require distinguishable seed vs expanded stages and clear labeling versus local same-provision expansion. `VectorRetriever.retrieve()` currently returns only final chunks; it does not expose expansion warnings or seed-only sets. A notebook two-stage helper reuses module APIs without changing the retrieval library contract in this feature.

**Alternatives considered**:
- Only toggle `expand_units=True/False` on one retriever and infer expansion from result-count deltas — rejected as insufficient: counts alone do not show provision/document linkage, expansion warnings, or overlay fields (US2).
- Change `RetrievalResult` schema now to carry expansion metadata — deferred: useful later, but out of scope for a notebook integration feature that must not become a retrieval-module redesign.

## R4: Graph load, preflight, and missing-input behavior

**Decision**: Mirror [`scripts/verify_kg.py`](../../scripts/verify_kg.py) and the facade contract:

1. Preflight required structural inputs via `GraphLoaderPaths.required_paths()` under `data/v2/` (`documents`, `provisions`, `chunks`, `edges`, `external_stubs`).
2. Preflight optional overlay inputs separately (`validity_timeline.jsonl`, `authority_index.jsonl`).
3. On structural success: `KnowledgeGraphFacade(paths=...).build_graph()`, print `GraphBuildStats`, construct `GraphExpansion(graph)`.
4. On overlay success: parse validity/authority rows and `build_overlay_bundle(..., as_of_date=AS_OF_DATE)`.
5. On structural failure: keep pure vector retrieval + generation usable; set hybrid flags unavailable and fail clearly if hybrid mode is requested (FR-015).
6. On overlay-only failure: allow structural expansion, label overlays unavailable, do not claim authoritative currency reasoning (Edge Cases).

**Rationale**: FR-003–FR-005 and Edge Cases require explicit missing-file reporting, smoke-check stats, and non-silent degradation. The facade/loader already validate structural paths; overlays are intentionally separate from graph build in the module design.

**Alternatives considered**:
- Hard-require overlays before any hybrid demo — rejected: structural expansion remains useful without currency/authority joins.
- Silently fall back to vector-only when hybrid is requested but graph missing — rejected by FR-015 and Constitution Principle III / workflow gate "No silent fallback."

## R5: Full-corpus in-memory graph build for the notebook

**Decision**: Build the full in-memory graph the same way `verify_kg.py` does (`facade.build_graph()` over complete v2 sources). Report build duration and node/edge counts. Do not invent a notebook-only subgraph cache in this feature.

**Rationale**: Expansion needs chunk→provision→document adjacency and reading-order links that the builder materializes from the full structural sources. The project already accepts full-graph verification as an operational path. Spec Assumptions state graph construction APIs under `src/knowledge_graph/` are the integration surface; no alternate partial-load API is specified for the notebook.

**Alternatives considered**:
- Seed-driven lazy subgraph load from JSONL — rejected for this feature: would require new library work, change loader contracts, and is not needed to satisfy the demo FRs if the full graph can be built as in verification.
- Skip loading `chunks.jsonl` and expand only via vector-store payloads — rejected: that reverts to local `expand_units` and fails FR-002/FR-006's graph-module integration requirement.

## R6: Overlay attachment and citation safety in displays

**Decision**: After hybrid evidence is assembled, join `DocumentOverlay` by each evidence row's `id_str` when overlays are loaded. Display currency/authority fields as diagnostics, not as silent rank rewrites of vector payloads. Treat external stubs / non-citation-safe nodes as non-citable in graph-facing displays (never present stub text as citation-ready evidence).

**Rationale**: FR-008/FR-013 and Constitution Principles I/IV require validity/authority to remain explicit overlay signals and forbid presenting stubs as citable law. Overlays are query-time joins (`as_of_date`), not graph-node mutations — matching [`OverlayJoiner`](../../src/knowledge_graph/overlay.py) design.

**Alternatives considered**:
- Overwrite `RetrievedChunk.validity_group` / `legal_authority_rank` with overlay values in place — rejected: blurs payload-vs-overlay provenance and makes debugging harder.
- Hide overlay gaps — rejected by Edge Cases and Principle III.

## R7: Optional graph-guided pre-filter demo path

**Decision**: Keep a clearly labeled secondary cell/helper that:

1. Chooses a start document id (from config or from a seed hit's `id_str`).
2. Runs `facade.traverse(graph, start_id, mode=..., max_depth=...)`.
3. Builds `GraphGuidedFilter` via `build_graph_guided_filter(...)`.
4. Calls `VectorRetriever.retrieve(..., graph_guided_filter=guided_filter)`.
5. Prints whitelist size and `empty_filter_warning`; never relabels an unfiltered search as graph-guided.

**Rationale**: FR-020 / User Story 4 require module coverage for the already-supported secondary path without redefining the primary story. `VectorRetriever` already returns empty results with `empty_filter_warning=True` when the whitelist is empty — the notebook must surface that warning explicitly.

**Alternatives considered**:
- Omit pre-filter entirely — rejected: FR-020 is SHOULD-level but US4 acceptance scenarios are part of the feature; cheap to demo once the graph is loaded.
- Make pre-filter the default `ask()` path — rejected by R1/spec correction.

## R8: Updating `ask()` and generation handoff

**Decision**: Extend the existing notebook `ask()` so that when hybrid expansion is enabled and the graph is loaded, generation receives the expanded evidence context (formatted through the existing `format_context_for_prompt` / `generate_answer` path). If generator credentials are missing, still return hybrid retrieval/expansion output. If no usable evidence remains, skip generation with an explicit empty-context message (existing `GenerationOutcome.skipped_empty_context` behavior).

**Rationale**: FR-009/FR-014/FR-022 and US1 scenarios 3–4 require expanded evidence to feed generation when available, without making generation mandatory.

**Alternatives considered**:
- Separate `ask_hybrid()` only, leave `ask()` vector-only — rejected: FR-022 says the default full-pipeline demonstration should run vector → graph expand/overlays → generation when the graph is loaded.
- Bypass `reasoning_client` and inline a new prompt — rejected: generation stack was just modularized in feature `001`; reuse it.

## R9: Local `expand_units` vs graph expansion labeling

**Decision**: In all user-facing prints/tables:

- Label local payload-window expansion as `local_expand_units` / "local same-provision expansion".
- Label graph-backed expansion as `graph_expansion` / "graph expansion (reading-order / structural)".
- When hybrid mode uses `GraphExpansion`, prefer that path and state it explicitly; do not imply local expansion ran.

**Rationale**: FR-018 and Edge Cases require users to tell which mechanism produced extra chunks. The retriever already branches on `self.graph_expansion is None`; the notebook must make that branch visible.

## R10: Contracts directory and test scope

**Decision**: No `contracts/` directory. No mandatory new unit-test module for this feature. Validation is notebook quickstart scenarios plus reuse of existing graph/retrieval tests. Optional lightweight pure helpers may stay notebook-local; if any helper later grows non-trivial branching, extract in a follow-up.

**Rationale**: Same stance as features `001`/`002` for non-API notebook work: no network-facing contract. SC-001 emphasizes running the demo without new library modules. Graph/retrieval correctness is already covered by `tests/knowledge_graph/*` and retrieval tests; this feature is integration/orchestration.

**Alternatives considered**:
- Add `tests/notebooks/` kernel tests — rejected as out of current tooling and scope; quickstart manual validation is the established pattern for notebook features here.
