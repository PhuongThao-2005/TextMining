# Feature Specification: Colab-Safe Full Pipeline Memory Fit

**Feature Branch**: `005-colab-ram-fit`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "Current notebook for full pipeline 'L_RAG/notebooks/faiss_retrieval_ready.ipynb' is causing trouble for Colab runtime since it doesn't fit 12GB RAM. I want to address this issue."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the full hybrid demo on a 12GB Colab runtime (Priority: P1)

Project member opens full-pipeline notebook in Google Colab (or equivalent ~12GB RAM hosted notebook), mounts or uploads required artifacts, runs cells top to bottom with Colab-safe config, completes at least one hybrid legal query (vector seed → graph expansion/overlays when available → optional generation) without runtime killed for exceeding memory.

**Why this priority**: Notebook is primary end-to-end demonstration. If it cannot finish on common free Colab RAM budget, hybrid pipeline cannot be shown or validated in environment where demos expected to run.

**Independent Test**: On runtime with approximately 12GB RAM available to notebook process, load Colab-safe configuration, complete setup for vector retrieval and graph expansion (using portable graph artifact when present), run one sample hybrid query, confirm completion without out-of-memory kill and with labeled hybrid (or clear hybrid-unavailable) results.

**Acceptance Scenarios**:

1. **Given** required FAISS artifacts and structural graph source suitable for Colab (portable graph pickle preferred; full JSONL rebuild only if explicitly allowed), **When** user runs setup with Colab-safe profile enabled, **Then** notebook loads vector retrieval and structural graph consumers and reports setup completed under Colab-safe path.
2. **Given** setup succeeded on ~12GB runtime, **When** user runs one sample hybrid query, **Then** notebook returns seed and/or expanded evidence without session terminated for memory exhaustion.
3. **Given** generator credentials configured, **When** user runs full pipeline helper after Colab-safe setup, **Then** generation may run on retrieved evidence; if generation skipped, notebook still returns retrieval/expansion results without failing session.
4. **Given** Colab-safe profile enabled, **When** optional heavy demonstration cells would allocate large temporary structures (full payload CSV dumps, large multi-query comparison loops, redundant full-graph rebuilds), **Then** those cells disabled by default or require explicit opt-in so top-to-bottom runs stay within RAM budget.

---

### User Story 2 - See memory pressure and choose a safe load path (Priority: P1)

Project member wants to know, before or during load, which heavy components being loaded (vector index, embedding model, structural graph, overlays, optional exports) and whether session is on Colab-safe path, so they can avoid accidental full-corpus rebuilds or redundant large allocations that push runtime over 12GB.

**Why this priority**: Silent full loads currently make Colab unusable. Visibility and explicit safe path required to prevent repeated OOM failures.

**Independent Test**: Run preflight/setup cells and confirm notebook prints component load plan (what will load, what deferred/skipped, graph source mode: pickle vs JSONL rebuild), plus basic memory or size signals sufficient to decide whether to continue.

**Acceptance Scenarios**:

1. **Given** artifacts present, **When** user runs preflight under Colab-safe mode, **Then** notebook lists required/optional artifacts, approximate on-disk sizes when available, and which load path used for structural graph (portable pickle vs full source rebuild).
2. **Given** portable structural graph artifact available, **When** Colab-safe setup runs, **Then** notebook prefers loading that artifact over rebuilding structural graph from full v2 JSONL sources.
3. **Given** only full structural JSONL sources available and no portable graph artifact present, **When** Colab-safe setup runs, **Then** notebook either (a) warns full rebuild may exceed 12GB and requires explicit opt-in before rebuild, or (b) keeps pure vector retrieval usable and marks hybrid unavailable without killing session.
4. **Given** setup in progress or complete, **When** user inspects diagnostics, **Then** notebook reports which major components resident (vector store, embedder, structural graph, overlays) so memory ownership visible.

---

### User Story 3 - Keep pure vector retrieval usable when hybrid is too heavy (Priority: P2)

Project member on constrained Colab runtime may only need vector search and optional generation. They can run vector-only path that skips structural graph load entirely, still answers legal queries with citation-ready chunks, never claims hybrid expansion occurred.

**Why this priority**: Vector-only remains valuable when graph load would exceed RAM. Graceful degradation must be explicit and labeled.

**Independent Test**: Enable Colab-safe vector-only mode (or hybrid disabled), run sample query, confirm retrieval works without loading structural graph, with mode labeled `vector_only`.

**Acceptance Scenarios**:

1. **Given** FAISS artifacts present and hybrid/graph load disabled or skipped for RAM reasons, **When** user runs sample query, **Then** pure vector retrieval completes and results labeled as vector-only.
2. **Given** hybrid mode requested but structural graph cannot be loaded under Colab-safe policy, **When** user invokes hybrid full-pipeline helper, **Then** notebook fails clearly or refuses hybrid label — it MUST NOT silently return vector-only results under hybrid name.
3. **Given** vector-only Colab-safe mode, **When** optional graph diagnostics cells run, **Then** they report graph unavailable/skipped rather than attempting full rebuild by default.

---

### User Story 4 - Stage the pipeline so peak RAM stays bounded (Priority: P2)

Project member can run notebook in stages—environment and config, vector load and smoke query, then graph load and hybrid query, then optional generation—so peak simultaneous residency reduced compared with loading every heavy component and every demo cell at once.

**Why this priority**: Even with efficient artifacts, loading embedder + FAISS + full graph + large intermediate tables together can exceed 12GB. Staging is user-visible control for peak memory.

**Independent Test**: Follow documented staged order on constrained runtime; confirm each stage can complete and later stages optional; confirm default Colab-safe top-to-bottom order does not eagerly run heavy optional export/benchmark cells.

**Acceptance Scenarios**:

1. **Given** Colab-safe mode, **When** user completes vector setup only, **Then** they can run vector queries without having loaded structural graph.
2. **Given** vector setup complete, **When** user loads structural graph in later stage, **Then** hybrid expansion becomes available without requiring kernel restart solely because of staging (unless user explicitly freed memory).
3. **Given** Colab-safe defaults, **When** user runs all non-optional cells top to bottom, **Then** heavy optional export cells (full payload CSV, bulk cache downloads) and large multi-run benchmarks not executed unless explicitly enabled.
4. **Given** user no longer needs heavy component for subsequent cells, **When** documented release/cleanup step available, **Then** notebook can drop references to that component and encourage garbage collection so later stages have more headroom (best-effort; not hard OS guarantee).

---

### User Story 5 - Document the Colab artifact pack and operator workflow (Priority: P3)

Project member preparing Colab demo knows exactly which files to build locally, which to upload/mount, and which notebook settings to use so 12GB session viable—without guessing whether to ship full v2 JSONL, only graph pickle, FAISS files, or overlays.

**Why this priority**: RAM fit is as much artifact-packaging problem as notebook-code problem. Clear workflow prevents failed sessions.

**Independent Test**: New operator following feature’s documented Colab workflow can list minimal artifact set, preferred graph load path, and Colab-safe config flags without reading implementation source.

**Acceptance Scenarios**:

1. **Given** documentation for this feature, **When** user prepares Colab inputs, **Then** they can identify minimal required set for vector-only vs hybrid Colab-safe runs.
2. **Given** structural graph pickle feature exists in project, **When** user prepares hybrid Colab inputs, **Then** workflow prefers portable structural graph artifact plus FAISS artifacts, with overlay files optional.
3. **Given** machine with more RAM, **When** user wants full unconstrained demos (exports, large benchmarks, JSONL rebuild), **Then** documentation describes how to opt out of Colab-safe defaults without breaking notebook’s non-Colab use.

---

### Edge Cases

- What happens when free Colab RAM already reduced by other notebooks/processes in same runtime? Notebook MUST still apply Colab-safe defaults and SHOULD surface available/process memory signals when environment exposes them, but MUST NOT promise hard OS-level reservation.
- What happens when `payload_cache.sqlite` missing and rebuilding from `payloads.jsonl` would spike memory/disk? Colab-safe mode MUST prefer prebuilt cache when present, and MUST warn before cold full-cache rebuild; rebuild may proceed only with clear progress messaging (existing staleness behavior may remain, but must not be silent about cost).
- What happens when portable graph pickle missing but full v2 JSONL present? Colab-safe mode MUST NOT silently start full-corpus graph rebuild as if cheap; it MUST warn and require explicit opt-in or skip hybrid.
- What happens when only graph pickle present but FAISS artifacts missing? Vector and hybrid seed retrieval MUST fail preflight clearly; graph-only smoke out of scope for this notebook’s primary path.
- What happens when overlays huge or missing? Structural hybrid expansion MUST remain possible without overlays; overlay join remains optional and MUST NOT be required to declare Colab-safe hybrid retrieval successful.
- What happens when user enables every optional demo (CSV export of many payload rows, large benchmark sample, graph-guided demo, hybrid comparison, generation) on 12GB? Notebook MUST document that full opt-in may exceed 12GB; Colab-safe success criteria apply to default path, not every optional cell combined.
- What happens when embedding model download/load alone approaches RAM budget? Notebook MUST fail clearly if embedder cannot load; it MUST NOT switch to different embedding model that would make FAISS scores invalid unless user explicitly opts into separately built index for that model.
- What happens if generation uses local in-process model instead of remote API? Local in-process LLMs out of scope for Colab-safe guarantees; generation assumed remote/OpenAI-compatible API as in existing notebook.
- What happens on local machines with ≥16–32GB RAM? Non-Colab / unconstrained profile MUST remain available so existing full demos not permanently crippled by Colab defaults.
- What happens if peak memory briefly spikes during single query expansion? Expansion caps (`top_k`/`top_n`/max hop/max context) MUST remain configurable and Colab-safe defaults MUST use conservative caps; truncation MUST be reported when capping occurs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Full-pipeline notebook MUST provide explicit **Colab-safe profile** (configuration flags and/or documented mode) targeting approximately **12GB RAM** hosted notebook runtimes.
- **FR-002**: With Colab-safe defaults, user MUST be able to complete setup plus at least one sample retrieval query on ~12GB runtime without requiring higher-RAM runtime class for default path.
- **FR-003**: Colab-safe mode MUST prefer loading **portable structural graph artifact** (project graph pickle) over rebuilding structural graph from full v2 JSONL sources when pickle present.
- **FR-004**: Colab-safe mode MUST NOT perform full structural JSONL graph rebuild by default; if rebuild offered, notebook MUST require explicit opt-in and MUST warn that rebuild may exceed 12GB RAM.
- **FR-005**: When hybrid cannot be loaded under Colab-safe policy, pure vector retrieval MUST remain usable and hybrid MUST be labeled unavailable (no silent hybrid labeling).
- **FR-006**: Hybrid requests without loaded structural graph MUST fail clearly (same no-silent-fallback rule as existing hybrid notebook contract).
- **FR-007**: Colab-safe defaults MUST disable or skip heavy optional cells by default, including full/large payload CSV export, bulk nonessential downloads, and large multi-question benchmark loops, unless user sets explicit opt-in flag.
- **FR-008**: Colab-safe defaults MUST use conservative retrieval/expansion caps suitable for constrained RAM (configurable; documented defaults), and MUST report when expansion context capped.
- **FR-009**: Notebook MUST present **load plan / preflight** under Colab-safe mode listing major components (FAISS index, payload cache, embedder, structural graph source mode, overlays, generator) and whether each will load, defer, or skip.
- **FR-010**: Notebook SHOULD report process or system memory signals when runtime exposes them (for example available RAM / process RSS before and after major loads) to help user see pressure; absence of such APIs MUST NOT block retrieval.
- **FR-011**: Notebook MUST support **staged execution**: vector path runnable before graph load; graph/hybrid load as explicit subsequent stage; generation optional.
- **FR-012**: Notebook SHOULD provide best-effort cleanup/release helper to drop large optional objects (for example export tables, intermediate demo frames, or graph instance user chooses to unload) and trigger garbage collection between stages.
- **FR-013**: Colab-safe mode MUST NOT change embedding model identity by default in way that invalidates existing FAISS index; any alternate embedder/index pairing requires explicit user configuration and matching artifacts.
- **FR-014**: Colab-safe mode MUST preserve shared legal identities end-to-end (`chunk_id` → `parent_unit_id` → `id_str`) and citation-safety rules (external stubs / non-citation-safe nodes never presented as citation-ready).
- **FR-015**: Colab-safe mode MUST NOT hardcode secrets, MUST NOT mutate source FAISS/v2 artifacts except existing allowed cache rebuild behavior, and MUST keep generator credentials environment-based.
- **FR-016**: Overlay join remains optional after structural graph load; missing overlays MUST NOT block Colab-safe structural hybrid expansion.
- **FR-017**: Feature MUST document Colab operator workflow: which artifacts to prepare locally, preferred transfer set for vector-only vs hybrid, Colab-safe flags, staged run order, and what to avoid on 12GB.
- **FR-018**: Non-Colab / unconstrained profile MUST remain available so higher-RAM environments can still run fuller demos (exports, larger benchmarks, optional JSONL rebuild) without removing those capabilities from project.
- **FR-019**: Default top-to-bottom execution under Colab-safe profile MUST be defined so “Run all” does not eagerly execute opt-in-only heavy cells.
- **FR-020**: When payload SQLite cache present and fresh, Colab-safe mode MUST reuse it; when missing/stale, notebook MUST warn that cache rebuild can be costly on Colab before rebuilding.
- **FR-021**: Existing hybrid semantics remain: primary path is vector-first then graph expansion/overlays; graph-guided pre-filter stays secondary and MUST stay off by default under Colab-safe mode.
- **FR-022**: Feature MUST NOT require GPU for Colab-safe success; CPU-only FAISS and embedding load paths remain valid.
- **FR-023**: Success messaging MUST distinguish (a) vector-only Colab-safe success, (b) hybrid Colab-safe success with pickle-loaded graph, and (c) hybrid unavailable due to RAM/policy/artifacts — never conflate these outcomes.

### Key Entities

- **Colab-safe profile**: Named notebook configuration targeting ~12GB RAM hosted runtimes (flags, caps, default cell enablement, graph load policy).
- **Unconstrained profile**: Higher-RAM / local configuration preserving fuller demos and optional expensive operations.
- **Load plan**: Preflight summary of which major components will load, skip, or require opt-in, including graph source mode.
- **Portable structural graph artifact**: Single-file structural knowledge graph snapshot (project graph pickle) preferred for Colab hybrid load.
- **FAISS retrieval artifacts**: `index.faiss`, `payloads.jsonl`, optional `id_map.json` and `payload_cache.sqlite` under configured index directory.
- **Overlay sources (optional)**: Validity timeline and authority index joined dynamically after structural load.
- **Staged pipeline session**: User-visible order of vector setup → optional graph setup → query/hybrid → optional generation, with optional cleanup between stages.
- **Memory diagnostic snapshot**: Best-effort report of available/process memory and/or artifact sizes around major load points.
- **Heavy optional demo**: Cells that can allocate large temporary data (full CSV export, large benchmark sample, multi-mode stress loops) gated behind opt-in flags.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On ~12GB RAM Colab-class runtime, user following Colab-safe defaults can complete environment setup, vector load (with fresh payload cache when provided), and one sample vector query without runtime killed for memory exhaustion.
- **SC-002**: On ~12GB RAM Colab-class runtime, when portable structural graph artifact and FAISS artifacts present, user can complete hybrid setup via pickle load (not full JSONL rebuild) and one sample hybrid query without runtime killed for memory exhaustion.
- **SC-003**: 100% of default Colab-safe “Run all” executions skip opt-in-only heavy export/large-benchmark cells unless user enabled those flags before running.
- **SC-004**: 100% of Colab-safe sessions that lack loadable structural graph still allow pure vector retrieval, and 100% of hybrid-labeled attempts without graph fail clearly rather than silently degrading.
- **SC-005**: 100% of Colab-safe preflight runs that detect portable graph artifact select pickle load over JSONL rebuild by default.
- **SC-006**: 100% of attempted full JSONL graph rebuilds under Colab-safe policy either require explicit opt-in after warning or are refused with hybrid marked unavailable.
- **SC-007**: User can complete staged run (vector-only smoke, then optional graph load, then hybrid query) using only documented notebook steps, without undocumented manual source edits.
- **SC-008**: Documentation lists distinct minimal artifact packs for (1) vector-only Colab-safe and (2) hybrid Colab-safe, and new operator can identify them in one reading of feature quickstart/workflow section once written in planning.
- **SC-009**: Citation-ready results under Colab-safe mode continue to expose `chunk_id`, parent provision identity, and document `id_str` for sampled hits; non-citation-safe stubs not presented as citable evidence.
- **SC-010**: Unconstrained/local profile remains capable of running previously available fuller demos (optional exports and larger samples) when user disables Colab-safe defaults on machine with sufficient RAM.

## Assumptions

- Target constraint is common free **Google Colab ~12GB RAM** runtime (or equivalent hosted notebook). High-RAM Colab / local machines supported via unconstrained profile but not success bar for Colab-safe defaults.
- Primary notebook remains [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb); this feature adapts that full pipeline for constrained RAM rather than inventing separate product surface (thin companion notebook allowed later if planning justifies it, but not required by this spec).
- Major RAM consumers in current full pipeline are combination of: FAISS index residency, embedding model weights (`intfloat/multilingual-e5-large` by default), in-memory structural knowledge graph (especially when built from full v2 JSONL), overlay materialization, and optional large notebook exports/benchmarks.
- Feature `004-kg-pickle-persist` (portable structural graph pickle) is preferred Colab graph input; this feature **consumes** that artifact for RAM-safe hybrid load and does not replace pickle build/save semantics.
- Embedding model must remain compatible with FAISS index in use; Colab-safe work focuses on load policy, staging, caps, optional-cell gating, and graph source choice—not on silently swapping to smaller incompatible embedder.
- Answer generation continues to use remote OpenAI-compatible API; hosting local LLM in same 12GB runtime out of scope for Colab-safe guarantees.
- Payload SQLite cache, when prebuilt and fresh, is part of recommended Colab artifact pack to avoid cold rebuild spikes.
- “Fit in 12GB” means default Colab-safe path completes without OOM kill for stated scenarios; it does not mean every optional cell can be enabled simultaneously.
- Existing constitution rules still apply: no silent hybrid fallback, shared identities, citation safety, read-only source artifacts (except allowed cache rebuild), modular reported pipelines.
- GPU is optional; Colab-safe success defined for CPU-capable runtimes.
- Exact byte-level budgets per component may be refined during planning/research; specification fixes user-visible outcomes and policies above.
