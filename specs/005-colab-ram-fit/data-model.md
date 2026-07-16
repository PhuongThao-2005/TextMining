# Phase 1 Data Model: Colab-Safe Full Pipeline Memory Fit

Feature adds **no new source-of-truth dataset files**. Adds notebook-facing runtime/profile entities, load-plan diagnostic model, explicit graph-source / stage policies over existing FAISS, pickle, v2 artifacts.

## 1. Source and derived artifacts (read / prefer)

| Entity | Default location | Role under Colab-safe |
| --- | --- | --- |
| FAISS index | `data/faiss_index/index.faiss` | Required for vector seed retrieval |
| Payloads JSONL | `data/faiss_index/payloads.jsonl` | Source of truth for payload cache rebuild |
| Payload SQLite cache | `data/faiss_index/payload_cache.sqlite` | Preferred derived cache; avoid cold rebuild when fresh |
| ID map | `data/faiss_index/id_map.json` | Optional |
| Structural graph pickle | `data/graph/knowledge_graph.gpickle` | **Preferred** hybrid structural graph source |
| Structural v2 JSONL | `data/v2/{documents,provisions,chunks,edges,external_stubs}.jsonl` | Rebuild source only with explicit opt-in under Colab-safe |
| Validity timeline | `data/v2/validity_timeline.jsonl` (or upload path) | Optional overlay |
| Authority index | `data/v2/authority_index.jsonl` (or upload path) | Optional overlay |
| Benchmark QA | `data/benchmark/qa_final.jsonl` | Optional; opt-in sample only |

Paths configurable for Colab (`/content/...`, Drive mounts).

### Shared legal identity (must not be lost)

```text
chunk_id  →  parent_unit_id  →  id_str
(chunk)      (provision)        (document)
```

Citation safety: external stubs / non-citation-safe nodes never presented as citation-ready evidence (FR-014, SC-009).

## 2. Existing module entities consumed (unchanged contracts)

### Vector path

```text
VectorIndexConfig
SentenceTransformerEmbedder
SQLitePayloadFaissVectorStore  # payload_cache.sqlite rebuild-if-stale
VectorRetriever
RetrievedChunk / RetrievalResult
```

### Graph path (004 + 003)

```text
GraphPickleLoadResult          # persist.load_knowledge_graph / facade.load_graph
  graph: KnowledgeGraph
  format_version, stats, warnings, path, ...

KnowledgeGraph                 # structural only; no overlays inside pickle
GraphExpansion / ExpansionResult
OverlayBundle / DocumentOverlay
GraphLoadStatus                # from 003 notebook orchestration (extended below)
HybridEvidenceContext          # from 003; mode labels extended for Colab messaging
```

### Generation

```text
GeneratorConfig / GenerationOutcome  # remote API; local in-process LLM out of scope
```

## 3. New / extended notebook-facing entities

May be notebook-local dataclasses/TypedDicts or tiny optional pure helper module. **Not** new on-disk source schemas.

### 3.1 `RuntimeProfile`

Named config targeting host RAM class.

```text
RuntimeProfile
  name: "colab_safe" | "unconstrained"
  colab_safe: bool

  # graph policy
  prefer_graph_pickle: bool                 # True for both; enforced hard under colab_safe
  allow_jsonl_graph_rebuild: bool           # default False under colab_safe
  graph_pickle_path: Path
  v2_data_dir: Path

  # retrieval caps
  top_k: int
  top_n: int
  hybrid_max_hop: int
  hybrid_max_context: int
  score_threshold: float
  embedding_model: str                      # must match FAISS index unless user overrides both

  # feature switches
  enable_hybrid_expansion: bool
  enable_graph_guided_prefilter_demo: bool  # default False under colab_safe
  use_hybrid_evidence_for_generation: bool
  local_expand_units: bool                  # default False for hybrid demos

  # heavy optional gates (default False under colab_safe)
  run_payload_csv_export: bool
  run_payload_cache_export: bool
  run_benchmark_sample: bool
  run_filter_profile_comparison: bool       # optional; keep small if True
  benchmark_sample_size: int
  payload_csv_export_limit: int | None      # prefer finite limit even when enabled
```

#### Suggested Colab-safe defaults

| Field | Colab-safe default | Unconstrained default (illustrative) |
| --- | --- | --- |
| `name` | `colab_safe` | `unconstrained` |
| `allow_jsonl_graph_rebuild` | `False` | `True` or user choice |
| `top_k` | `20` | `30` (current) |
| `top_n` | `5`–`8` | `10` |
| `hybrid_max_hop` | `1` | `1`–`2` |
| `hybrid_max_context` | `8` | `12` |
| `enable_graph_guided_prefilter_demo` | `False` | user choice |
| heavy `run_*` flags | `False` | may be `True` for local demos |
| `embedding_model` | `intfloat/multilingual-e5-large` | same unless matching alternate index provided |

### 3.2 `ArtifactPresence` / inventory row

```text
ArtifactPresence
  key: str                    # e.g. "index.faiss", "knowledge_graph.gpickle"
  path: Path
  required_for: list[str]     # ["vector"], ["hybrid_structural"], ["overlay"], ...
  present: bool
  byte_size: int | None
  notes: str                  # e.g. "fresh cache", "stale cache", "optional"
```

### 3.3 `GraphSourceMode`

```text
GraphSourceMode = "pickle" | "jsonl_rebuild" | "unavailable"
```

Decision rules under Colab-safe (research R3):

1. Pickle present → `"pickle"`
2. Pickle missing + JSONL present + `allow_jsonl_graph_rebuild` → `"jsonl_rebuild"` (after warning)
3. Else → `"unavailable"`

### 3.4 `ComponentLoadAction`

```text
ComponentLoadAction
  component: str   # faiss_index | payload_cache | embedder | structural_graph | overlays | generator
  action: "load" | "reuse" | "defer" | "skip" | "opt_in_required" | "warn_rebuild"
  detail: str
```

### 3.5 `LoadPlan`

Preflight summary before/at major loads (FR-009, US2).

```text
LoadPlan
  profile: RuntimeProfile.name
  artifacts: list[ArtifactPresence]
  actions: list[ComponentLoadAction]
  graph_source_mode: GraphSourceMode
  hybrid_expected: bool                 # True only if graph will load
  warnings: list[str]
  memory_before: MemorySnapshot | None
```

### 3.6 `MemorySnapshot`

Best-effort; absence must not block retrieval (FR-010).

```text
MemorySnapshot
  source: str                 # psutil | resource | procfs | unavailable
  process_rss_bytes: int | None
  available_system_bytes: int | None
  note: str
```

Capture around: preflight, after FAISS/embedder load, after graph load, after heavy optional cells if run.

### 3.7 `ResidentComponentSnapshot`

```text
ResidentComponentSnapshot
  store_loaded: bool
  embedder_loaded: bool
  structural_graph_loaded: bool
  graph_source_mode: GraphSourceMode | None
  overlays_loaded: bool
  hybrid_retriever_ready: bool
  generator_configured: bool
  optional_frames_held: list[str]   # e.g. export dataframes, comparison tables
```

### 3.8 Extended `GraphLoadStatus` (from 003)

Add fields for Colab policy visibility:

```text
GraphLoadStatus  # extended
  structural_ready: bool
  overlays_ready: bool
  missing_structural_files: list[str]
  missing_overlay_files: list[str]
  build_stats: GraphBuildStats | dict | None
  build_warnings: tuple[str, ...]
  as_of_date: str | None
  overlay_coverage: dict[str, int] | None
  error: str | None

  # NEW for 005
  graph_source_mode: GraphSourceMode
  pickle_path: str | None
  loaded_from_pickle: bool
  rebuild_opt_in_required: bool
  rebuild_warning_emitted: bool
```

### 3.9 `PipelineStage`

```text
PipelineStage = (
  "config_preflight"
  | "vector_load"
  | "vector_smoke"
  | "graph_load"
  | "hybrid_smoke"
  | "generation"
  | "heavy_optional"
)
```

Staged session rules:

- `vector_smoke` allowed without `graph_load`
- `hybrid_smoke` / hybrid-labeled `ask()` require `structural_ready`
- `heavy_optional` executes only when corresponding opt-in flags true
- Default Colab-safe top-to-bottom run executes stages through optional generation setup, **not** heavy optional bodies

### 3.10 `SessionOutcomeLabel` (success messaging FR-023)

```text
SessionOutcomeLabel =
  "vector_only_colab_safe_success"
  | "hybrid_colab_safe_success_pickle"
  | "hybrid_unavailable"
  | "unconstrained_success"          # optional label when not in colab_safe
  | "failed_preflight"
  | "failed_oom_or_runtime"          # observational; not a promised catch-all
```

Rules:

- Hybrid success label requires structural graph actually loaded + hybrid path used.
- Vector-only success must not use hybrid wording.
- Hybrid requested without graph → clear failure / `hybrid_unavailable`, never silent vector under hybrid name.

### 3.11 `CleanupRequest` / release helper

```text
CleanupRequest
  drop_export_frames: bool = True
  drop_comparison_records: bool = True
  unload_overlays: bool = False
  unload_structural_graph: bool = False   # makes hybrid unavailable until reload
  run_gc: bool = True
```

Best-effort only; not OS memory reservation guarantee (FR-012, Edge Cases).

## 4. Mode labels for retrieval results (preserve 003 semantics)

| Label | Meaning |
| --- | --- |
| `vector_only` | No graph expansion used |
| `hybrid_seed` | Seeds retrieved as stage-1 of hybrid helper |
| `hybrid_expanded` | Graph expansion path used |
| `graph_guided_prefilter` | Secondary whitelist-before-search demo |
| `local_expand_units` | Payload same-provision expansion (not graph) |

Colab-safe invents no new retrieval semantics; adds **session outcome** labels + load policy around these modes.

## 5. Validation rules (from FRs)

1. Colab-safe MUST prefer pickle when present (FR-003, SC-005).
2. Colab-safe MUST NOT JSONL-rebuild by default; opt-in + warning or skip hybrid (FR-004, SC-006).
3. Missing graph ⇒ vector-only usable; hybrid-labeled calls fail clearly (FR-005, FR-006, SC-004).
4. Heavy optional cells default off under Colab-safe Run-all (FR-007, FR-019, SC-003).
5. Caps configurable; truncation reported (FR-008).
6. Load plan required under Colab-safe (FR-009).
7. Memory APIs optional (FR-010).
8. Staging supported (FR-011); cleanup best-effort (FR-012).
9. Embedder identity stable vs FAISS by default (FR-013).
10. Identities + citation safety preserved (FR-014, SC-009).
11. No hardcoded secrets; sources read-only except allowed cache rebuild (FR-015, FR-020).
12. Overlays optional (FR-016).
13. Unconstrained profile remains available (FR-018, SC-010).
14. Graph-guided secondary and off by default under Colab-safe (FR-021).
15. CPU-only success valid (FR-022).
16. Success messages distinguish vector-only vs hybrid-pickle vs hybrid-unavailable (FR-023).

## 6. State transitions (graph availability)

```text
[start]
  → preflight LoadPlan
  → vector components load (store/embedder)
  → GraphSourceMode decision
       ├─ pickle → load_knowledge_graph → structural_ready=True, loaded_from_pickle=True
       ├─ jsonl_rebuild (opt-in) → build_graph → structural_ready=True, loaded_from_pickle=False
       └─ unavailable → structural_ready=False, hybrid_unavailable
  → optional overlays join
  → hybrid queries allowed only if structural_ready
  → optional cleanup may set structural_ready=False again if user unloads graph
```

## 7. Out of scope entities

- New FAISS index formats or alternate default embedding models
- Local in-process LLM weights as Colab-safe generation
- Neo4j or other graph DB persistence
- Automatic silent rebuild-from-JSONL when pickle path was requested
- Guaranteed OS-level memory reservation / cgroup control
