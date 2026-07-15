# Phase 0 Research: Structural Knowledge Graph Pickle Artifact

## R1: What “gpickle” means in this project

**Decision**: Deliver a portable **structural graph pickle** file with default extension `.gpickle`. Implement it with Python’s standard `pickle` module serializing a **versioned envelope** whose payload is the existing in-memory `KnowledgeGraph` dataclass (plus lightweight metadata). Do **not** introduce NetworkX or NetworkX `write_gpickle` / `read_gpickle`.

**Rationale**: The current graph is a typed in-memory model (`KnowledgeGraph` in [`src/knowledge_graph/builder.py`](../../src/knowledge_graph/builder.py)), not a NetworkX graph. There is no NetworkX dependency in the repo. User intent is a single transferable file for Colab reload after local build, not a Neo4j dump and not a NetworkX-specific format. Using stdlib pickle keeps the prototype path dependency-free and preserves exact node/edge dataclasses used by expansion/traversal.

**Alternatives considered**:
- NetworkX conversion + `nx.write_gpickle` — rejected: adds a new dependency, loses typed dataclass contracts unless a full round-trip mapper is built, and does not match existing consumers (`GraphExpansion`, `GraphTraversal`) which expect `KnowledgeGraph`.
- Joblib / dill — rejected: extra dependency; stdlib pickle is enough for frozen dataclasses/tuples/dicts used by the graph module.
- MessagePack/JSON export of the full graph — rejected for this feature: larger engineering cost and slower for a “fast prototype” path; can be revisited if cross-language load becomes a requirement.
- Neo4j dump — rejected: explicitly out of scope; still a later milestone.

## R2: Artifact contents — structural graph only

**Decision**: Persist only the structural `KnowledgeGraph`:

- `documents`, `external_stubs`, `provisions`, `chunks`
- `document_edges`, `verified_document_edges`, `structural_edges`
- `document_to_provisions`, `provision_to_chunks`, `provision_next`, `chunk_next`

Do **not** pickle `OverlayBundle` / validity timeline / authority index. Overlays remain optional dynamic joins after load.

**Rationale**: Matches locked product decision and existing module design ([`docs/spec/GRAPH_MODULE.md`](../../docs/spec/GRAPH_MODULE.md)): overlays are as-of-date dependent and must not freeze a single currency view into the structural snapshot (spec FR-003, US3).

**Alternatives considered**:
- Bundle overlays for a fixed as-of date into the same file — rejected: breaks dynamic overlay model and forces rebuild for date changes.
- Save only adjacency maps without node payloads — rejected: Colab consumers need node fields for identity/citation diagnostics and traversal context.

## R3: Envelope format and compatibility

**Decision**: Save a small versioned envelope, not a bare `KnowledgeGraph` object:

```text
GraphPickleEnvelope
  format_name: "g-lrag-knowledge-graph"
  format_version: 1
  created_at_utc: ISO-8601 string
  source_data_dir: string | None
  stats: GraphBuildStats | dict of core counts
  warnings: tuple[str, ...] | empty
  graph: KnowledgeGraph
```

On load:
1. Unpickle the object.
2. Require `format_name` + supported `format_version`.
3. Require `graph` to be a `KnowledgeGraph` (or reconstruct from a documented dict shape if a future version needs it).
4. Fail clearly on missing/corrupt/incompatible files (no empty silent graph).

Default pickle protocol: highest available protocol safe for Python 3.11+ targets used by the project (prefer `pickle.HIGHEST_PROTOCOL`).

**Rationale**: FR-009/FR-017 and SC-006 need load-time validation and smoke metadata. A bare pickle of an arbitrary object is harder to diagnose when Colab and local code drift.

**Alternatives considered**:
- Sidecar JSON only for metadata — acceptable later, but embedding metadata in the envelope is simpler for single-file Colab upload (one file to transfer).
- Multiple format versions in v1 — rejected: start at version `1` only; reject unknown versions with a clear message.

## R4: Where code lives — library + operator script

**Decision**:

1. **Library module**: add [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) with pure functions:
   - `save_knowledge_graph(graph, path, *, stats=None, warnings=(), source_data_dir=None) -> GraphPickleArtifactInfo`
   - `load_knowledge_graph(path) -> GraphPickleLoadResult` (graph + metadata/stats)
   - path helpers / atomic write
2. **Facade convenience** (thin wrappers on `KnowledgeGraphFacade`):
   - `build_and_save_graph(path, ...)` → build from configured loader paths then save
   - `load_graph(path)` → load envelope and return graph (and metadata)
3. **Operator script**: [`scripts/build_kg_pickle.py`](../../scripts/build_kg_pickle.py)
   - CLI args: `--data-dir`, `--output`, optional `--force`
   - preflight structural sources, build, save, print counts + file size
4. **Exports**: re-export save/load helpers from [`src/knowledge_graph/__init__.py`](../../src/knowledge_graph/__init__.py).

**Rationale**: Spec requires both an operator-facing build path (FR-014) and a load path usable in Colab (FR-004/FR-005). Library functions keep the path unit-testable (Constitution V). Script mirrors `verify_kg.py` operational style without turning the notebook into the build system.

**Alternatives considered**:
- Script-only with no library API — rejected: Colab load would copy ad hoc unpickle code; harder to test and version.
- Notebook-only save cell — rejected: primary user story is local build then transfer; a script is the right operator surface.
- New top-level package `src/graph_store/` — rejected: persistence belongs with the knowledge-graph module that owns `KnowledgeGraph`.

## R5: Default artifact location and naming

**Decision**:

| Item | Default |
| --- | --- |
| Directory | `data/graph/` (created on save if missing) |
| Filename | `knowledge_graph.gpickle` |
| Full default path | `data/graph/knowledge_graph.gpickle` |

CLI and library always allow override. Document that Colab users upload/mount this single file (path may become `/content/...` or Drive path).

**Rationale**: Keeps graph artifacts separate from raw `data/v2/` JSONL and from `data/faiss_index/`. Configurable path satisfies FR-010.

**Alternatives considered**:
- Write into `data/v2/` — rejected: v2 is the source contract; derived artifacts should not be mixed into source inputs.
- `data/kg/kg.pkl` — acceptable alternative naming; `.gpickle` was chosen to match the user’s requested artifact name/semantics.

## R6: Atomic write and failed-build behavior

**Decision**:

1. Build graph fully in memory first via existing `KnowledgeGraphFacade.build_graph()` / `GraphBuilder`.
2. Only after successful build, serialize to a temporary file in the same directory (`*.gpickle.tmp` or `tempfile.NamedTemporaryFile`).
3. `os.replace` into the final path (atomic on the same filesystem).
4. On preflight/build/serialize failure: do not leave a success-claimed final artifact; clean up temp file best-effort.
5. Rebuild with the same output path replaces the previous artifact intentionally after successful write.

**Rationale**: FR-008/US4 require no partial success artifact and explicit replace-on-rebuild.

**Alternatives considered**:
- Write directly to final path — rejected: crash mid-dump can corrupt the only Colab artifact.
- Keep `.bak` automatically — optional nicety; not required for v1 (user can copy before rebuild).

## R7: Load contract for Colab / consumers

**Decision**: After `load_knowledge_graph(path)`:

- Return the restored `KnowledgeGraph` usable by:
  - `GraphExpansion(graph)`
  - `GraphTraversal(graph)` / `KnowledgeGraphFacade.traverse(...)`
  - any notebook/script that already accepts a built graph
- Do **not** auto-load overlays.
- Do **not** auto-fallback to JSONL rebuild when pickle load was requested (FR-016).
- Provide a tiny smoke helper or documented checks: node counts from metadata vs `len(graph.documents)` etc., and identity walk `chunk_id → parent_unit_id → id_str` for a sample id when available.

**Rationale**: FR-004/FR-005/SC-002/SC-003. Colab workflow is load snapshot fast; overlays remain optional if the user also uploaded those JSONL files.

**Alternatives considered**:
- `load_or_build(path, data_dir)` convenience — useful later but dangerous if it silently rebuilds when path missing while user thought they loaded a snapshot; keep explicit separate APIs in v1.
- Ship a minimal pure-pickle loader with no project imports — rejected for v1: unpickling typed graph objects requires the same class definitions (`KnowledgeGraph`, node dataclasses). Colab must have project `src/` on path (or installed package). Document this prerequisite.

## R8: Testing strategy

**Decision**: Add unit/integration tests under `tests/knowledge_graph/`:

1. Round-trip: build small fixture graph (existing `mock_dataset_dir` / conftest) → save → load → compare core counts and a few identities/adjacencies.
2. Missing output parent dir created (or explicit behavior asserted).
3. Missing input sources: build-and-save fails with missing paths; no final artifact.
4. Corrupt/incompatible file: load raises clear error.
5. Overlays not required for load success.
6. Optional: facade `build_and_save` / `load_graph` wrappers.

Use temporary directories; do not write into real `data/` during tests.

**Rationale**: Constitution V and FR/SC coverage. Fixture-scale tests avoid depending on full 150k-document corpus in CI.

**Alternatives considered**:
- Script-only manual validation — insufficient for regression on envelope/version checks.
- Full-corpus pickle in CI — too heavy; keep full-corpus as operator quickstart validation only.

## R9: Relationship to existing scripts and Neo4j

**Decision**:

- [`scripts/verify_kg.py`](../../scripts/verify_kg.py) remains authoritative for full-corpus reconciliation checks; optionally later it can load from pickle, but that is not required for this feature.
- New script focuses on **build → save pickle → print size/stats**.
- Neo4j adapter remains future work; this pickle path is the fast-prototype persistence milestone called out in handoff/report docs.

**Rationale**: Spec Assumptions and project reports already defer Neo4j; pickle closes the “no persistence” gap for Colab demos without waiting on graph DB ops.

## R10: Security / environment notes

**Decision**: Document that pickle load executes Python object reconstruction and should only be used with **trusted artifacts** built by this project. Do not load untrusted `.gpickle` files from unknown sources.

**Rationale**: Standard pickle safety constraint; acceptable for private research artifacts transferred by the same team into Colab.

**Alternatives considered**:
- Restrictive allowlisted unpickler — possible hardening later; not required to satisfy the prototype feature if trust boundary is documented.

## Research outcome

All Phase 0 questions resolved. No remaining NEEDS CLARIFICATION blockers for planning.
