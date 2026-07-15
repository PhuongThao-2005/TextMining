# Feature Specification: Structural Knowledge Graph Pickle Artifact

**Feature Branch**: `004-kg-pickle-persist`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "I want to build the KG in the format of pickle file for fast prototype." Clarification: structural `KnowledgeGraph` only (nodes, edges, adjacency maps); overlays stay dynamic at query time; primary deliverable is a portable graph pickle (`gpickle`) for Colab use after local build.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a portable structural graph file once (Priority: P1)

A project member builds the structural knowledge graph from the existing v2 JSONL sources on a machine that has `data/v2/`, then saves a single portable graph pickle artifact (`.gpickle`) that can be copied elsewhere without shipping the full set of graph source JSONL files.

**Why this priority**: Rebuilding from large v2 sources every Colab/session start is slow and friction-heavy. A one-shot portable artifact is the core value of this feature.

**Independent Test**: With required v2 structural sources present, run the build/save path and confirm a graph pickle file is written with reconcilable node/edge counts and a clear success report.

**Acceptance Scenarios**:

1. **Given** the required structural v2 sources are present (`documents`, `provisions`, `chunks`, `edges`, `external_stubs`), **When** the user runs the graph pickle build path, **Then** the system constructs the structural knowledge graph and writes a single portable graph pickle artifact to a configured output path.
2. **Given** the build succeeds, **When** the user inspects the build report/output, **Then** the system reports core structural counts (documents, external stubs, provisions, chunks, document edges, verified vs unverified edges when available, structural edges) and any non-fatal warnings.
3. **Given** one or more required structural source files are missing, **When** the user runs the build path, **Then** the system reports the missing files and does not write a partial/corrupt graph pickle as if successful.

---

### User Story 2 - Load the graph pickle in Colab or another session without rebuilding (Priority: P1)

A project member uploads or mounts the graph pickle in Colab (or another environment) and loads the structural knowledge graph directly, then uses the existing graph consumers (expansion, traversal, optional later overlay join) without re-reading the original v2 JSONL graph sources.

**Why this priority**: The artifact is only useful if load is simple, reliable, and restores a graph usable by the existing module contracts.

**Independent Test**: In a session that has the graph pickle but not the original structural JSONL sources, load the artifact and confirm the restored graph exposes the expected structural maps and can answer a simple smoke check (counts + one known identity lookup or adjacency walk).

**Acceptance Scenarios**:

1. **Given** a valid graph pickle artifact is available, **When** the user loads it, **Then** the system restores a structural knowledge graph with the same core node/edge counts that were reported at build time (within the saved metadata/report).
2. **Given** the graph was loaded from pickle, **When** the user runs a basic structural operation supported by the existing graph module (for example, look up a document/provision/chunk identity or expand from a known seed when consumers are available), **Then** the operation works without requiring the original structural JSONL files.
3. **Given** the pickle file is missing, unreadable, or not a supported graph artifact, **When** the user attempts to load it, **Then** the system fails clearly with an actionable error and does not silently fall back to an empty graph.

---

### User Story 3 - Keep overlays dynamic and optional after pickle load (Priority: P2)

A project member loads the structural graph from pickle and, if validity/authority source files are available in that environment, joins overlays at query time for a chosen as-of date. If overlay files are not present (common in a minimal Colab drop), structural graph use still works and overlay-dependent behavior is clearly unavailable.

**Why this priority**: Overlays are date-sensitive and intentionally separate from the structural graph. Baking them into the pickle would freeze a single as-of view and break the project's dynamic overlay model.

**Independent Test**: Load the structural pickle without overlay files and confirm structural operations work; when overlay files are present, join them independently and confirm currency/authority signals appear without mutating the loaded structural graph.

**Acceptance Scenarios**:

1. **Given** only the structural graph pickle is present, **When** the user loads it, **Then** structural graph operations remain available and the system does not claim overlays were loaded.
2. **Given** the structural graph is loaded from pickle and overlay sources are also available, **When** the user joins overlays for an as-of date, **Then** overlay signals are attached dynamically without requiring a rebuild of the structural pickle.
3. **Given** the structural graph pickle was built earlier, **When** overlay sources later change, **Then** the user can rejoin overlays without rebuilding the structural pickle.

---

### User Story 4 - Rebuild and replace the artifact when sources change (Priority: P3)

A project member updates v2 structural sources and rebuilds the graph pickle, replacing the previous artifact so Colab/demo environments can pick up the new structural snapshot deliberately.

**Why this priority**: Source drift will happen; rebuild must be explicit and auditable rather than automatic silent mutation of an existing demo file.

**Independent Test**: Run build twice to the same output path (or a new versioned path) and confirm the latest successful build is the one loaded, with counts/report reflecting the current sources.

**Acceptance Scenarios**:

1. **Given** structural sources have changed, **When** the user reruns the build/save path, **Then** a new successful graph pickle is written and the build report reflects the new counts.
2. **Given** an existing pickle is present at the output path, **When** rebuild succeeds, **Then** the artifact is replaced intentionally (or written to a user-selected path) rather than creating an ambiguous mix of old and new state.

---

### Edge Cases

- What happens when required structural v2 sources are missing? Build MUST fail with an explicit missing-file list and MUST NOT write a success-marked incomplete pickle.
- What happens when the output directory does not exist? The build path MUST create it or fail clearly before claiming success.
- What happens when the pickle cannot be loaded because of an incompatible saved shape/version? Load MUST fail with a clear incompatibility/corruption message rather than returning a partially usable object.
- What happens when the environment has the pickle but not overlay files? Structural load MUST succeed; overlay-dependent features remain optional and explicitly unavailable.
- What happens if a user expects Neo4j persistence from this feature? This feature does NOT deliver Neo4j; it delivers a local portable structural graph snapshot for fast prototype/Colab use.
- What happens if quarantine files are present? They MUST remain excluded from graph construction, consistent with existing graph source policy.
- What happens if unverified document edges exist? They MUST still be preserved in the structural graph snapshot according to current builder behavior, while verified-only consumers continue to use only verified edges after load.
- What happens if the pickle file is extremely large for Colab upload? The feature MUST document the intended single-file artifact and expected use (upload/mount/load), and SHOULD report artifact size after build so the user can decide transfer strategy.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a build path that constructs the structural knowledge graph from the existing v2 structural sources and saves it as a single portable graph pickle artifact (`.gpickle` or equivalent graph-pickle file).
- **FR-002**: The saved artifact MUST contain the structural knowledge graph only: document/external-stub/provision/chunk nodes, document edges, structural edges, and the adjacency/reading-order maps needed by existing structural consumers.
- **FR-003**: The saved artifact MUST NOT freeze validity/authority overlays into the structural graph; overlays remain dynamic and optional at query/load time.
- **FR-004**: The system MUST provide a load path that restores the structural knowledge graph from the graph pickle without requiring the original structural JSONL files to be present in the target environment.
- **FR-005**: After load, the restored graph MUST be usable by the existing structural graph consumers (at minimum identity maps and the current expansion/traversal contracts that already consume the in-memory structural graph).
- **FR-006**: Build MUST preflight required structural source files and report exactly which inputs are missing on failure.
- **FR-007**: Build MUST report structural counts sufficient for smoke reconciliation (documents, external stubs, provisions, chunks, document edges, verified vs unverified document edges when available, structural edges) plus non-fatal warnings.
- **FR-008**: Build MUST write the artifact only after a successful structural build; failed builds MUST NOT leave behind a success-claimed usable artifact.
- **FR-009**: Load MUST validate that the file is a supported structural graph artifact and fail clearly on missing, corrupt, or incompatible files.
- **FR-010**: The feature MUST support a configurable output/input path so users can place the artifact where Colab upload/mount workflows expect it.
- **FR-011**: The feature MUST preserve shared legal identities end-to-end in the saved graph: `id_str`, `unit_id`, `chunk_id`, and the containment joins needed for `chunk → provision → document`.
- **FR-012**: External stubs MUST remain non-citation-safe in the restored graph.
- **FR-013**: Quarantine artifacts MUST NOT be ingested into the graph pickle.
- **FR-014**: The feature MUST provide an operator-facing way to build the artifact (script and/or documented command entrypoint) suitable for local generation before Colab transfer.
- **FR-015**: The feature MUST document the Colab/prototype workflow: build locally from `data/v2/` → obtain graph pickle → transfer to Colab → load structural graph → optionally join overlays if those files are also available.
- **FR-016**: Rebuild MUST be an explicit user action; the system MUST NOT silently rebuild from JSONL when a pickle load was requested.
- **FR-017**: The feature SHOULD record lightweight artifact metadata with the pickle (or sidecar) such as creation time, source data directory label, schema/format version, and core counts to make load-time compatibility checks and debugging easier.
- **FR-018**: This feature MUST NOT require Neo4j or any remote graph database for the prototype path.

### Key Entities

- **Structural knowledge graph**: In-memory graph of documents, external stubs, provisions, chunks, cross-document edges, structural edges, and adjacency/reading-order maps, without validity/authority overlays.
- **Graph pickle artifact (gpickle)**: Single portable file snapshot of the structural knowledge graph intended for fast reload and Colab transfer.
- **Build report**: Counts, warnings, output path, and success/failure status produced when creating the artifact.
- **Artifact metadata**: Lightweight provenance for the pickle (format/schema version, counts, build stamp) used for smoke checks and compatibility messaging.
- **Overlay sources (optional, not in pickle)**: Validity timeline and authority index files joined dynamically after structural load when present.
- **Target runtime environment**: Local machine for build; Colab or similar notebook runtime for load-and-use prototype sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with required structural v2 sources can produce one graph pickle artifact in a single build action and receive a success report with core structural counts.
- **SC-002**: A user can load that artifact in an environment without the original structural JSONL files and obtain a usable structural knowledge graph.
- **SC-003**: 100% of successful load tests restore document/provision/chunk identity maps sufficiently to resolve `chunk → provision → document` for sampled existing ids from the saved graph.
- **SC-004**: Overlay absence never blocks structural pickle load; overlay presence is never required to declare the structural artifact successful.
- **SC-005**: 100% of failed builds caused by missing structural inputs report the missing files and do not present a successful artifact path.
- **SC-006**: 100% of failed loads caused by missing/corrupt/incompatible artifacts surface an explicit error rather than an empty silent graph.
- **SC-007**: A user following the documented Colab workflow can transfer only the graph pickle (plus whatever optional overlay files they choose) and run structural graph smoke checks without rebuilding from full v2 JSONL in Colab.

## Assumptions

- The existing in-memory structural graph produced by the knowledge-graph module is the source of truth for what gets pickled; this feature snapshots that structural graph rather than inventing a new legal graph model.
- “gpickle” in this feature means a portable graph pickle artifact for the structural KG (file intended for graph reload/prototype transfer). It does not imply Neo4j export, and it does not require introducing a separate graph-database product.
- Validity/authority overlays remain intentionally out of the structural pickle because they are as-of-date dependent and already designed as dynamic joins.
- Required build inputs are the existing structural v2 sources used by the current graph loader/builder: documents, provisions, chunks, edges, and external stubs under the configured v2 data directory.
- Neo4j persistence remains out of scope and is a later milestone if still desired; this feature is the fast-prototype persistence path.
- Colab use assumes the user can upload/mount a single artifact file and install/import the project’s knowledge-graph code (or a minimal compatible loader surface) in that environment.
- Existing consumers such as expansion, traversal, and notebook hybrid orchestration should be able to accept a loaded structural graph the same way they accept a freshly built in-memory graph.
- Full judged evaluation, answer generation, and FAISS index packaging are out of scope for this feature except as downstream consumers of the loaded graph.
- Artifact naming/default location can be conventional (for example under a project data graph directory) as long as the path is configurable for Colab transfer workflows.
