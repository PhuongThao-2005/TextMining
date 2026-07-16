# Feature Specification: Standalone GraphTraversal Explorer Section

**Feature Branch**: `007-graph-traversal-explorer`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "I want the GraphTraversal in the 'L_RAG/notebooks/faiss_retrieval_ready.ipynb' please." — clarified as: "Promote GraphTraversal to a first-class, standalone interactive section (not just a demo) where users can pick a start node and traversal mode and get results directly, independent of the hybrid pipeline."

## Clarifications

### Session 2026-07-16

- Q: Does `GraphTraversal` already exist in the notebook? → A: Yes, wired at §4.4 as a secondary, gated demo (`run_traversal_modes_demo` / `run_evidence_context_demo`, run only via `run_full_graph_module_demo` when `ENABLE_FULL_GRAPH_MODULE_DEMO=True`) alongside `GraphExpansion` (documented as the primary hybrid path).
- Q: What should change? → A: Promote `GraphTraversal` to a first-class, standalone, interactive section where a user picks a start node (`id_str`) and traversal mode directly and sees results immediately — independent of vector retrieval / hybrid pipeline readiness. The existing gated demo functions may remain for the bundled inventory demo, but this feature adds a separate, prominent, self-sufficient section.
- Q: Must the new section adhere to `docs/spec/GRAPH_MODULE.md`? → A: Yes. All traversal modes, semantics, defaults, and API usage MUST match `docs/spec/GRAPH_MODULE.md` §6 (Traversal) and §11 (Public APIs) exactly; the section is a UI/interaction layer over the existing spec-compliant `GraphTraversal`/`KnowledgeGraphFacade.traverse` implementation, not a reinterpretation of traversal semantics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a single graph traversal query independent of the hybrid pipeline (Priority: P1)

A notebook user who has only run Stage A (config/preflight) and Stage C's structural graph load wants to directly explore the knowledge graph: pick a start node `id_str`, a traversal mode (`basis`, `guidance`, `validity`, `structure`, `neighbors`), and a `max_depth`, then see the traversal result (visited nodes, visited edges, paths) — without running Stage B (vector index / FAISS), building `hybrid_retriever`, or enabling `ENABLE_FULL_GRAPH_MODULE_DEMO`.

**Why this priority**: This is the core ask — GraphTraversal must be usable on its own merit, not buried behind vector retrieval or hybrid-pipeline prerequisites. Without this, GraphTraversal remains a secondary, hard-to-reach capability.

**Independent Test**: With only the structural graph loaded (Stage C success; `graph_load_status.structural_ready is True`), and without running any Stage B vector-index or hybrid-retriever cells, run the new standalone traversal section with a valid start `id_str` and a chosen mode, and confirm it prints/returns visited node count, visited edge list (src/dst/rel_type), and path list for that mode.

**Acceptance Scenarios**:

1. **Given** Stage C has loaded the structural graph (`kg_graph`, `kg_facade` available, `graph_load_status.structural_ready is True`) and Stage B/hybrid cells have not been run, **When** the user runs the standalone traversal section with a valid start `id_str`, a supported mode, and a `max_depth`, **Then** the section executes the traversal directly via `GraphTraversal`/`kg_facade` and displays visited node IDs, visited edges, and paths for that mode.
2. **Given** the standalone section has already produced a `kg_traversal` (or equivalent) handle from Stage C, **When** the user changes the start `id_str`, mode, or `max_depth` and reruns only the traversal section, **Then** the section reuses the existing graph/facade handles without requiring Stage C to reload or Stage B/hybrid cells to run.
3. **Given** `ENABLE_FULL_GRAPH_MODULE_DEMO` is `False` and the bundled full-graph-module demo has not run, **When** the user runs the standalone traversal section, **Then** traversal still executes and produces results (the section does not depend on that flag or on `run_full_graph_module_demo`).

---

### User Story 2 - Get a clear, non-crashing response for invalid inputs (Priority: P2)

A user enters a start `id_str` that does not exist in the loaded graph, or a mode string outside the five supported modes, and expects a clear, immediate message rather than a raw traceback or silent wrong result.

**Why this priority**: Interactive, first-class sections are used by hand; unclear failures make the feature feel fragile and undermine trust in results from valid runs. Depends on US1 existing.

**Independent Test**: With the structural graph loaded, run the traversal section with (a) a start `id_str` absent from `kg_graph` and (b) a mode string not in `{basis, guidance, validity, structure, neighbors}`, and confirm each case reports a clear, specific message and does not raise an unhandled exception.

**Acceptance Scenarios**:

1. **Given** the structural graph is loaded, **When** the user supplies a start `id_str` not present among `kg_graph.documents`, `kg_graph.provisions`, or `kg_graph.chunks`, **Then** the section reports that the start node was not found (naming the id_str) instead of raising an unhandled exception or silently returning an empty result with no explanation.
2. **Given** the structural graph is loaded, **When** the user supplies a mode value outside the five supported modes, **Then** the section rejects the input with a message listing the supported modes, and does not silently fall back to a default mode.
3. **Given** a valid start `id_str` and mode combination produces zero visited edges (e.g., an isolated node), **When** the traversal completes, **Then** the section reports the empty result explicitly (e.g., "0 edges visited") rather than treating it as an error.

---

### User Story 3 - Compare traversal modes for the same start node (Priority: P3)

A user wants to quickly see how different traversal modes behave from the same start node, to understand the graph's structure and verified relationships around a document/provision/chunk of interest.

**Why this priority**: Useful for exploration and report/demo material, but not required for the minimum standalone capability delivered by US1. Depends on US1.

**Independent Test**: With the structural graph loaded, run the section's multi-mode comparison for one start `id_str` across all five modes and confirm a per-mode summary (visited count, edge count, path count) is displayed for each mode without re-entering the start `id_str` five times.

**Acceptance Scenarios**:

1. **Given** a valid start `id_str`, **When** the user requests a comparison across all supported modes, **Then** the section runs all five modes for that start node and displays a per-mode summary table or listing.
2. **Given** the comparison has run, **When** a mode is not applicable to the given start node type (e.g., `structure` mode on an `id_str` absent from documents/provisions/chunks), **Then** that mode's row explicitly shows an empty/not-applicable result rather than omitting the mode or erroring the whole comparison.

---

### Edge Cases

- What happens when the structural graph has not been loaded yet (Stage C not run or failed)? The section MUST guard against this with a clear message (e.g., "run Stage C graph load first") and MUST NOT attempt to construct a traversal service against a missing/`None` `kg_graph`.
- What happens when the start `id_str` exists in the graph but has no outgoing verified edges of the requested relationship group (`basis`/`guidance`/`validity`/`neighbors`)? The section MUST return and display an explicit empty result (visited_ids containing only the start id, zero edges, zero paths), not an error.
- What happens when mode is `structure` and the start `id_str` is a chunk rather than a document or provision? The section MUST use `GraphTraversal.traverse_structure`'s chunk-aware branch (parent provision + sibling chunks) and MUST NOT require the user to specify the node "type" separately.
- What happens when `max_depth` is `0` or negative? The section MUST handle this the same way `GraphTraversal` does (depth-capped empty-edge result containing only the start id) rather than raising an exception, and SHOULD state that a non-positive depth yields no traversal steps.
- What happens when `max_depth` is unusually large (e.g., 20+) on a large graph? The section SHOULD warn about potential slow/heavy results consistent with the notebook's Colab-safe run posture (see `005-colab-ram-fit`), without hard-blocking a user-chosen value.
- What happens when the user runs the standalone section before Stage A config has set `GRAPH_GUIDED_START_ID`/mode defaults? The section MUST work with its own explicit start/mode/depth inputs and MUST NOT require those Stage A graph-guided-prefilter config variables to be set.
- What happens if `run_full_graph_module_demo` / `ENABLE_FULL_GRAPH_MODULE_DEMO` later runs in the same session? The standalone section's independent results MUST remain valid and MUST NOT be silently overwritten or invalidated by that separate demo path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The notebook MUST provide a standalone, clearly headed section dedicated to interactive `GraphTraversal` exploration, distinguishable from the existing bundled "Full Graph Module surface demos" (§4.4) and from any hybrid-pipeline section.
- **FR-002**: The standalone section MUST be runnable — and MUST produce traversal results — using only the Stage C structural graph load as a prerequisite. It MUST NOT require Stage B vector index construction, `hybrid_retriever`/`GraphExpansion` construction, or `ENABLE_FULL_GRAPH_MODULE_DEMO=True`.
- **FR-003**: The section MUST expose three user-configurable inputs for a single traversal run: start node `id_str`, traversal mode (one of `basis`, `guidance`, `validity`, `structure`, `neighbors` — the exact five modes defined in `docs/spec/GRAPH_MODULE.md` §6), and `max_depth` (integer).
- **FR-004**: On execution, the section MUST invoke `GraphTraversal` directly through the `KnowledgeGraphFacade` public API exactly as defined in `docs/spec/GRAPH_MODULE.md` §11 (`traverse(graph, start_id, mode, max_depth) -> TraversalResult`, or `build_traversal(graph)` followed by the service's own `.traverse(...)`), using the chosen inputs, and MUST display: visited node count and IDs, visited edges (source id, destination id, relationship type), and path count with each path's step sequence. The section MUST NOT reimplement traversal logic or bypass the facade/service API.
- **FR-005**: The section MUST validate that the start `id_str` exists in the loaded graph (`kg_graph.documents`, `kg_graph.provisions`, or `kg_graph.chunks`) before or as part of traversal, and MUST report a clear, specific "start node not found" message when it does not, without raising an unhandled exception.
- **FR-006**: The section MUST validate the mode value against the five supported modes and MUST reject unsupported values with a message listing the valid modes, rather than silently defaulting to a mode.
- **FR-007**: The section MUST guard against a missing/unready structural graph with a dedicated check (independent of hybrid-specific guard wording) and MUST report that Stage C graph load has not completed successfully when triggered before graph readiness.
- **FR-008**: The section MUST allow repeated runs with different start `id_str`, mode, or `max_depth` values without re-running Stage C's graph load, by reusing already-constructed `kg_graph`/`kg_facade` (and a `GraphTraversal` handle) from the session.
- **FR-009**: The section's availability and correctness MUST NOT depend on the state (enabled/disabled, success/failure) of `ENABLE_FULL_GRAPH_MODULE_DEMO`, `run_full_graph_module_demo`, or `GraphExpansion`/hybrid retriever construction.
- **FR-010**: Traversal results MUST be presented in the notebook output in a human-readable form (e.g., formatted print output or tabular display), not solely as an unrendered Python object reference.
- **FR-011**: Existing bundled demo functions (`run_traversal_modes_demo`, `run_evidence_context_demo`, `run_full_graph_module_demo`) MAY remain in the notebook for the bundled full-graph-module inventory demo; this feature adds a separate, first-class section rather than requiring their removal.
- **FR-012**: The section SHOULD offer a small set of default values (start `id_str`, mode, `max_depth`) analogous to the existing `GRAPH_GUIDED_*` config pattern, but these defaults MUST be overridable inline in the section without editing the Stage A config cell. Displayed/pre-filled `max_depth` defaults MUST match `GraphTraversal`'s own per-mode defaults (3 for `basis`/`guidance`/`validity`/`structure`; 1 for `neighbors`, per `docs/spec/GRAPH_MODULE.md` §6 and the implementation) rather than an invented single global default.
- **FR-013**: The section SHOULD note the Colab-safe performance posture (per `005-colab-ram-fit`) when a user selects a large `max_depth`, without hard-blocking the value.
- **FR-014**: The section's on-screen labeling MUST make clear that its results come from `GraphTraversal` directly and are independent of any hybrid/GraphExpansion-fused results shown elsewhere in the notebook.
- **FR-015**: The section MUST NOT traverse or present unverified cross-document edges (e.g., edge groups where `direction_verified == False`, such as unverified `validity`/`suspension` groups) as if they were verified path results, consistent with `docs/spec/GRAPH_MODULE.md` §6's integrity constraint that `GraphTraversal` only follows verified relationships; this is inherited automatically by delegating to the existing `GraphTraversal` implementation (FR-004) and MUST NOT be re-derived or loosened by the new section.
- **FR-016**: Any textual description of a traversal mode shown to the user (e.g., help text, tooltips, or comparison labels) MUST match the mode semantics defined in `docs/spec/GRAPH_MODULE.md` §6 (see Key Entities below for the exact per-mode semantics) rather than inventing alternate descriptions.

### Key Entities

- **Start node (`id_str`)**: The document, provision, or chunk identifier the user chooses as the traversal origin; must be present in the loaded `KnowledgeGraph` for the traversal to yield non-trivial results.
- **Traversal mode**: One of the five modes defined in `docs/spec/GRAPH_MODULE.md` §6 (`TraversalMode`), each selecting a specific verified relationship group or structural hierarchy:
  - `basis` — follows verified `BASED_ON` edges (default `max_depth` 3).
  - `guidance` — explores implementing Circulars/Decrees mapped to general Laws (default `max_depth` 3).
  - `validity` — traces replacements and amendments to map document lineage (default `max_depth` 3).
  - `structure` — walks internal containment hierarchies (Document → Provision → Chunk; default `max_depth` 3).
  - `neighbors` — returns all outgoing verified cross-document links (default `max_depth` 1).
- **TraversalResult**: The output object (`start_id`, `mode`, `max_depth`, `visited_ids`, `visited_edges`, `paths`) that the section must render for the user, per `docs/spec/GRAPH_MODULE.md` §11.
- **TraversalStep / TraversalPath**: The edge-level (`src_id`, `dst_id`, `rel_type`, `provenance`) and path-level (`start_id`, `end_id`, ordered `steps`) records composing a `TraversalResult`, used for the detailed display.
- **GraphTraversal handle**: The live service instance (`kg_facade.build_traversal(kg_graph)`) reused across repeated runs of the standalone section within a session; only traverses cross-document edges where `direction_verified == True` per §6.
- **Structural graph readiness**: The Stage C precondition (`graph_load_status.structural_ready`, `kg_graph`, `kg_facade` populated) that this section depends on, independent of vector/hybrid readiness.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a traversal result from the standalone section immediately after Stage C completes, without running any Stage B vector-index or hybrid-retriever cell in the same session.
- **SC-002**: All five supported traversal modes are selectable from the standalone section and each produces either a populated result or an explicit empty-result message (no unhandled errors) for a valid start `id_str`.
- **SC-003**: Given an invalid start `id_str` or an unsupported mode value, the section returns a clear, specific message (not a raw traceback) within the same cell execution.
- **SC-004**: Re-running the section with a different start `id_str`/mode/`max_depth` after an initial run completes without re-executing Stage C's graph-load cell.
- **SC-005**: The standalone section's results are visually and textually distinguishable from the hybrid/GraphExpansion-oriented sections elsewhere in the notebook.

## Assumptions

- The Stage C structural graph load (already implemented) continues to populate `kg_graph`, `kg_facade`, and `graph_load_status.structural_ready = True`; this feature builds on that existing state rather than reimplementing graph loading.
- "Start node" means a document/provision/chunk `id_str` (or `unit_id`) recognized by the loaded `KnowledgeGraph`, matching `GraphTraversal.traverse_structure`'s existing dispatch on `graph.documents` / `graph.provisions` / `graph.chunks` membership.
- The existing bundled demo functions (`run_traversal_modes_demo`, `run_evidence_context_demo`, `run_full_graph_module_demo`) may be kept as-is, refactored to share helpers with the new section, or left untouched; the design/implementation phase decides the exact code-sharing approach as long as the new section meets FR-001–FR-014 independently.
- This feature is scoped to `L_RAG/notebooks/faiss_retrieval_ready.ipynb` only; `L_RAG/notebooks/retrieval_eval.ipynb` (the separate evaluation notebook, spec `006-retrieval-eval-notebook`) is out of scope.
- No new persisted artifacts (files on disk) are required; this is an in-notebook, session-scoped interactive exploration feature.
- The section is intended for manual/interactive use (a human choosing inputs and reading output); it is not required to run unattended as part of an automated "run all cells" pass, though it must not error out if executed with its documented default inputs during a run-all.
