# Feature Specification: Notebook Graph Module Integration

**Feature Branch**: `003-notebook-graph-integration`

**Created**: 2026-07-15

**Updated**: 2026-07-15 — corrected primary hybrid pipeline to vector-first, then graph expansion with overlays, then generation

**Status**: Draft

**Input**: User description: "Integrate the graph module into the full pipeline in 'L_RAG/notebooks/faiss_retrieval_ready.ipynb'"

**Clarification**: The primary full pipeline is:

```text
query
  → embed
  → vector search (seed chunks)
  → resolve chunk → provision → document
  → graph expansion + validity/authority overlays
  → fused evidence context
  → LLM answer + reasoning
```

Graph-guided pre-filtering of vector search (whitelist-before-search) is an optional secondary mode, not the primary notebook path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the hybrid retrieve → expand → generate pipeline in one notebook (Priority: P1)

A project member opens the existing FAISS retrieval notebook, loads the vector store as today, also loads the knowledge graph and overlays, then runs a legal question through the full hybrid path: embed the query, retrieve seed chunks from the vector index, expand those seeds through the graph (chunk → provision → document, reading-order neighbors, related structure), attach validity/authority overlay signals, and optionally feed the expanded evidence to the generator for a reasoned answer.

**Why this priority**: This is the core hybrid architecture the project claims. The notebook already does vector retrieval and generation; without post-retrieval graph expansion and overlays, it does not demonstrate the full pipeline.

**Independent Test**: With FAISS artifacts and v2 graph sources available, run the notebook through one sample question end to end and confirm the output shows (1) seed vector hits, (2) graph-expanded context and/or overlay-enriched diagnostics, and (3) optional generated answer/reasoning grounded in the expanded evidence.

**Acceptance Scenarios**:

1. **Given** FAISS index artifacts and required v2 graph source artifacts are present, **When** the user runs setup cells, **Then** the notebook loads the vector retriever, builds the in-memory knowledge graph, joins overlays for a configured as-of date, and wires graph expansion into the retrieval/full-pipeline path.
2. **Given** the hybrid path is enabled, **When** the user runs a sample query, **Then** the notebook embeds the query, retrieves seed chunks via vector search, expands them with the graph module, and displays both seed results and expanded evidence with shared legal identities (`chunk_id`, `parent_unit_id`, `id_str`).
3. **Given** generator credentials are configured, **When** the user runs the full pipeline helper, **Then** the expanded evidence context is passed to the generator and the notebook shows answer and reasoning as distinct sections.
4. **Given** generator credentials are not configured, **When** the user runs the full pipeline helper, **Then** the notebook still completes hybrid retrieval + expansion and returns retrieval-only output without failing.

---

### User Story 2 - Inspect seed hits, graph expansion, and overlay signals (Priority: P2)

A project member wants to understand what the hybrid pipeline did after vector search: which seed chunks were found, how they mapped to provisions/documents, what neighboring or related context the graph added, and what validity/authority overlay status applies to those documents.

**Why this priority**: Hybrid retrieval is only trustworthy if intermediate legal structure is visible. Silent expansion would hide why extra context entered the prompt.

**Independent Test**: After one hybrid query, confirm the notebook prints or tabulates seed chunk ids, expanded chunk ids (or counts), at least one provision/document linkage, overlay fields for a sample document (currency/authority when available), and any expansion warnings.

**Acceptance Scenarios**:

1. **Given** a successful hybrid query with at least one seed hit, **When** diagnostics are shown, **Then** the user can see seed vs expanded context sizes and a sample of expanded chunk/provision/document identities.
2. **Given** overlays were loaded, **When** diagnostics are shown, **Then** the notebook reports overlay coverage and can display currency/authority signals for at least one document involved in the result.
3. **Given** expansion finds missing seeds or missing parents, **When** diagnostics are shown, **Then** warnings are surfaced explicitly rather than dropped.

---

### User Story 3 - Compare vector-only vs hybrid expanded retrieval (Priority: P2)

A project member wants to compare the same question with vector-only retrieval (current notebook behavior) versus hybrid retrieval that applies graph expansion and overlay-aware context assembly, so they can see how graph integration changes the evidence set before generation.

**Why this priority**: Side-by-side comparison proves the integration changed behavior, not just imported unused graph code.

**Independent Test**: Run one fixed query in vector-only mode and hybrid-expanded mode; confirm the notebook reports result counts, whether expansion ran, and sample citation differences or expansion deltas.

**Acceptance Scenarios**:

1. **Given** a fixed query, **When** the user runs vector-only and hybrid-expanded modes, **Then** the notebook labels each mode clearly and reports candidate/result counts for both.
2. **Given** hybrid expansion adds context, **When** comparison runs, **Then** the notebook shows that expanded evidence includes seed hits plus additional graph-derived neighbors/context (or explicitly reports that expansion added nothing).
3. **Given** the graph is unavailable, **When** the user requests hybrid mode, **Then** the notebook fails clearly or falls back only with an explicit warning — never silently pretending hybrid expansion occurred.

---

### User Story 4 - Optional graph-guided pre-filter remains available (Priority: P3)

A project member may still want to demonstrate the secondary pattern where the graph builds a document whitelist first and vector search is constrained to that set. This remains available, but it is not the default full-pipeline path.

**Why this priority**: The retrieval module already supports graph-guided filters, and the current notebook labels that path as not exercised. Supporting it completes module coverage without redefining the primary hybrid flow.

**Independent Test**: With graph and overlays loaded, run one query under graph-guided pre-filter mode and confirm the profile/whitelist diagnostics and empty-filter warning behavior are explicit.

**Acceptance Scenarios**:

1. **Given** graph and overlays are loaded, **When** the user runs graph-guided pre-filter retrieval, **Then** the notebook builds a whitelist, applies it as a hard vector filter, and displays whitelist size and empty-filter status.
2. **Given** the whitelist is empty, **When** graph-guided pre-filter runs, **Then** the notebook surfaces an empty-filter warning and does not silently search the full corpus under a graph-guided label.

---

### Edge Cases

- What happens when v2 graph source files are missing? The notebook MUST preflight required graph inputs, report missing files, and keep pure vector retrieval + generation usable.
- What happens when vector search returns zero seed chunks? The notebook MUST skip graph expansion and generation, record empty context, and not invent graph neighbors.
- What happens when seed chunks cannot be resolved in the graph (unknown `chunk_id` / missing parent provision)? Expansion MUST warn and continue with whatever valid seeds remain.
- What happens when overlay files are missing but the structural graph exists? The notebook MUST still allow structural expansion, clearly label that currency/authority overlays are unavailable, and avoid claiming authoritative validity reasoning.
- What happens when graph expansion returns only the original seeds (no extra neighbors)? The notebook MUST report expansion ran with zero added context, not treat that as failure.
- What happens if the user enables hybrid mode before the graph is loaded? The notebook MUST fail clearly rather than silently running vector-only under a hybrid label.
- What happens when expanded context becomes very large? The notebook MUST respect configured caps (top_n / max expansion context) and show that truncation/capping occurred when relevant.
- What happens when generation is configured but hybrid retrieval/expansion yields no usable text? Generation MUST be skipped with an explicit empty-context message.
- What happens for external stubs or non-citation-safe nodes encountered during expansion/traversal? They MUST NOT be presented as citation-ready evidence.
- What happens to existing `expand_units` local same-provision expansion? Hybrid graph expansion MUST be labeled distinctly from local payload expansion so users can tell which mechanism produced extra chunks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The notebook MUST implement the primary hybrid pipeline as: embed query → vector retrieve seed chunks → resolve chunk/provision/document identities → graph-expand with overlays → assemble evidence → optional LLM generation.
- **FR-002**: The notebook MUST load the project's existing knowledge-graph module (build graph, overlays, expansion) rather than re-implementing graph logic in notebook-local code beyond orchestration/helpers.
- **FR-003**: The notebook MUST preflight required graph source artifacts and report exactly which files are missing before attempting graph build.
- **FR-004**: The notebook MUST report graph build statistics sufficient for a smoke check (documents, provisions, chunks, document edges, verified vs unverified edges when available).
- **FR-005**: The notebook MUST load validity-timeline and authority-index overlays when present, join them for a user-configurable as-of date, and report overlay coverage.
- **FR-006**: The notebook MUST wire graph expansion into the retrieval path so seed vector hits can be expanded into reading-order / structurally related context before final evidence display and generation.
- **FR-007**: The notebook MUST display, for at least one demo query, seed retrieval results and post-expansion evidence as distinguishable stages (seed set vs expanded set, or equivalent diagnostics).
- **FR-008**: The notebook MUST attach or display overlay-derived validity/authority signals for documents involved in the expanded evidence when overlays are available.
- **FR-009**: The notebook MUST pass the expanded evidence context (not only raw unexpanded seeds, when expansion is enabled) into the existing generation step.
- **FR-010**: The notebook MUST keep pure vector-only retrieval and the existing non-graph filter profiles (`current_law`, `broad`, `historical`) fully usable without a successful graph load.
- **FR-011**: The notebook MUST provide a comparison for the same query between vector-only mode and hybrid expanded mode, reporting counts and whether expansion added context.
- **FR-012**: The notebook MUST preserve shared legal identity end-to-end: `chunk_id` → `parent_unit_id` → `id_str` on displayed evidence.
- **FR-013**: The notebook MUST treat external stubs and non-citation-safe nodes as non-citable in graph-facing displays.
- **FR-014**: The notebook MUST skip generation when no usable evidence remains after retrieval/expansion, and MUST record that skip explicitly.
- **FR-015**: The notebook MUST fail clearly if hybrid expansion mode is requested while the graph is unavailable, rather than silently running vector-only under a hybrid label.
- **FR-016**: The notebook MUST remain runnable from project root or `notebooks/`, resolving data paths relative to the detected project root.
- **FR-017**: The notebook MUST document that this is a hybrid pipeline demonstration layered on existing modules, not a replacement for dedicated graph verification or judged evaluation scripts.
- **FR-018**: The notebook MUST distinguish graph expansion from local vector `expand_units` same-provision expansion in user-facing labels/diagnostics.
- **FR-019**: The notebook MUST NOT hardcode secrets or mutate source dataset/index artifacts; graph and FAISS inputs are read-only.
- **FR-020**: The notebook SHOULD also support optional graph-guided pre-filter retrieval (whitelist-before-vector-search) as a secondary demo path, with explicit empty-filter handling and no silent fallback to unfiltered search.
- **FR-021**: The notebook MUST allow user-configurable hybrid settings near the top configuration cells, including as-of date, whether hybrid expansion is enabled, expansion hop/context caps when exposed, default vector filter profile, and whether generation uses hybrid evidence.
- **FR-022**: The notebook MUST update the full-pipeline helper (`ask()`-style flow) so the default “full pipeline” demonstration can run vector retrieval → graph expansion/overlays → generation when the graph is loaded.

### Key Entities

- **Seed retrieval result**: Citation-ready chunks returned by vector search for the embedded query before graph expansion.
- **Graph expansion result**: Ordered/related context derived from seed chunk ids via the knowledge graph (provision windows, reading-order neighbors, structural links), including warnings.
- **Document overlay**: Query-time validity/currency and authority information joined onto documents for an as-of date and used to explain or constrain evidence.
- **Hybrid evidence context**: The fused set of seed + expanded chunks (and overlay signals) assembled for display and LLM grounding.
- **Generated answer**: Final answer plus reasoning/thinking trace produced from hybrid evidence, or an explicit skip/error state.
- **Optional graph-guided filter**: Secondary document whitelist used to hard-filter vector search when the pre-filter mode is chosen.
- **Pipeline configuration**: User-tunable settings for vector retrieval, hybrid expansion, overlays/as-of date, and generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with FAISS artifacts and required graph inputs can run one sample question through embed → vector retrieve → graph expand/overlays → optional generate without unhandled exceptions and without writing new library modules by hand.
- **SC-002**: For at least one successful demo query with seed hits, the notebook shows both seed retrieval output and post-expansion evidence diagnostics (counts and sample identities).
- **SC-003**: When hybrid expansion is enabled and the graph is loaded, 100% of full-pipeline demo runs either pass expanded evidence to generation or explicitly report why generation was skipped (empty seeds, expansion produced no usable text, generator not configured).
- **SC-004**: A user can compare vector-only vs hybrid-expanded results for the same query in one session and see distinct mode labels plus result/expansion counts.
- **SC-005**: Existing non-graph notebook flows remain runnable when graph inputs are missing; hybrid features are skipped or clearly disabled rather than breaking the whole notebook.
- **SC-006**: 100% of displayed hybrid evidence rows retain enough identity metadata for a user to trace `chunk → provision → document` without leaving the notebook.
- **SC-007**: If the optional graph-guided pre-filter path is exercised and yields an empty whitelist, the notebook surfaces an empty-filter warning in 100% of such cases and does not silently return unfiltered hits under a graph-guided label.

## Assumptions

- The target notebook is existing `notebooks/faiss_retrieval_ready.ipynb`; this feature extends that notebook rather than creating a separate primary deliverable.
- Primary architecture for this feature is **vector-first hybrid retrieval**: semantic seed retrieval first, then graph expansion and overlay enrichment, then generation.
- Optional **graph-guided pre-filter** (graph whitelist before vector search) remains supported as a secondary demonstration because the retrieval module already exposes it, but it is not the default full-pipeline story.
- Graph construction, expansion, traversal, overlay join, and filter APIs already exist under `src/knowledge_graph/` and are the integration surface.
- Vector retrieval already accepts optional graph expansion and optional graph-guided filters under `src/retrieval/`; the notebook orchestrates those contracts.
- Required inputs remain FAISS artifacts under `data/faiss_index/` plus v2 graph sources under `data/v2/` (structural files for build; validity timeline and authority index for overlays).
- Local `expand_units` without a graph remains available as fallback behavior; when a graph expansion service is wired, that path is preferred for hybrid demos and must be labeled clearly.
- Dedicated tools such as `scripts/verify_kg.py` and `scripts/evaluate_e2e.py` remain authoritative for full graph verification and judged evaluation; this notebook is a demonstration/validation surface.
- Generation remains an optional thin demonstration layer that consumes hybrid evidence; it does not add automated answer judging.
