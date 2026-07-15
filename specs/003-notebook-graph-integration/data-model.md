# Phase 1 Data Model: Notebook Graph Module Integration

This feature reads existing FAISS and v2 graph artifacts and assembles in-memory hybrid evidence for notebook display/generation. It introduces **no new on-disk source-of-truth files**. Entities below restate the integration contracts the notebook must preserve and the notebook-facing result shapes used for diagnostics.

## 1. Source entities (read-only)

| Entity | Location | Role in this feature |
| --- | --- | --- |
| FAISS index artifacts | `data/faiss_index/index.faiss`, `payloads.jsonl`, optional `id_map.json` / `payload_cache.sqlite` | Vector seed retrieval and payload scroll for expanded chunk IDs |
| Structural graph sources | `data/v2/documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `external_stubs.jsonl` | Required for `KnowledgeGraphFacade.build_graph()` |
| Validity timeline | `data/v2/validity_timeline.jsonl` | Optional overlay input for currency status as-of a date |
| Authority index | `data/v2/authority_index.jsonl` | Optional overlay input for legal authority rank |
| Benchmark QA (optional) | `data/benchmark/qa_final.jsonl` | Unchanged optional batch path; not required for hybrid demo |

### Shared legal identity (must not be lost)

```text
chunk_id  →  parent_unit_id  →  id_str
(chunk)      (provision)        (document)
```

Every displayed hybrid evidence row MUST retain enough of these fields for a user to trace chunk → provision → document inside the notebook (FR-012, SC-006).

## 2. Existing module entities the notebook consumes

### Graph build

From [`src/knowledge_graph/builder.py`](../../src/knowledge_graph/builder.py):

```text
GraphBuildResult
  graph: KnowledgeGraph
  stats: GraphBuildStats
  warnings: tuple[str, ...]

GraphBuildStats
  document_count
  external_stub_count
  provision_count
  chunk_count
  document_edge_count
  verified_document_edge_count
  unverified_document_edge_count
  structural_edge_count
  orphan_provision_count
  orphan_chunk_count
  ...
```

Notebook smoke check prints at least: documents, provisions, chunks, document edges, verified vs unverified edges (FR-004).

### Expansion

From [`src/knowledge_graph/expansion_schema.py`](../../src/knowledge_graph/expansion_schema.py):

```text
ExpansionResult
  seed_chunk_ids: tuple[str, ...]
  max_hop: int
  max_context: int | None
  expanded_node_ids: tuple[str, ...]
  traversed_edges: tuple[ExpansionStep, ...]
  ordered_context_chunks: tuple[str, ...]
  warnings: tuple[str, ...]
```

### Overlays

From [`src/knowledge_graph/overlay_schema.py`](../../src/knowledge_graph/overlay_schema.py) / [`overlay.py`](../../src/knowledge_graph/overlay.py):

```text
DocumentOverlay
  id_str
  currency_status
  currency_status_as_of
  legal_authority_rank
  authority_rank_source
  validity_events
  authority_candidates

OverlayBundle
  document_overlays: dict[str, DocumentOverlay]
  validity_by_id
  authority_index
```

### Graph-guided filter (secondary path)

From [`src/knowledge_graph/context_schema.py`](../../src/knowledge_graph/context_schema.py):

```text
GraphGuidedFilter
  id_strs: tuple[str, ...]
  empty_filter_warning: bool
  filter_profile: str
  reason: str = ""
```

### Retrieval / generation (existing)

```text
RetrievedChunk
  chunk_id, chunk_text, citation_*, title, unit_type,
  validity_group, legal_authority_rank, scores,
  id_str, parent_unit_id, metadata

RetrievalResult
  chunks, total_candidates, filter_profile_used, empty_filter_warning

GenerationOutcome
  qa_id, parsed, skipped_empty_context, error
```

## 3. Notebook-facing hybrid entities (orchestration shapes)

These are **notebook-local** dataclasses or TypedDict-style records (not required new `src/` modules). They exist so cells can display seed vs expanded stages without changing `RetrievalResult`.

### `PipelineConfig` (config cell)

Restates Key Entity "Pipeline configuration":

```text
PipelineConfig / notebook config vars
  INDEX_DIR
  V2_DATA_DIR
  EMBEDDING_MODEL / TOP_K / TOP_N / SCORE_THRESHOLD
  DEFAULT_FILTER_PROFILE          # current_law | broad | historical
  ENABLE_HYBRID_EXPANSION         # bool, default True when graph loads
  HYBRID_MAX_HOP                  # graph expansion hop budget
  HYBRID_MAX_CONTEXT              # cap on ordered context chunks
  AS_OF_DATE                      # overlay join date, e.g. YYYY-MM-DD
  USE_HYBRID_EVIDENCE_FOR_GENERATION  # bool
  ENABLE_GRAPH_GUIDED_PREFILTER_DEMO  # secondary path switch
  LOCAL_EXPAND_UNITS              # existing expand_units fallback / comparison
```

### `GraphLoadStatus`

```text
GraphLoadStatus
  structural_ready: bool
  overlays_ready: bool
  missing_structural_files: list[str]
  missing_overlay_files: list[str]
  build_stats: GraphBuildStats | None
  build_warnings: tuple[str, ...]
  as_of_date: str | None
  overlay_coverage: dict[str, int] | None   # e.g. docs_with_overlay, currency histogram sample
  error: str | None
```

Backs FR-003–FR-005 and Edge Cases for missing structural vs overlay files.

### `SeedRetrievalView`

```text
SeedRetrievalView
  query: str
  filter_profile: str
  total_candidates: int
  seed_chunks: list[RetrievedChunk]     # vector hits before graph expansion
  seed_chunk_ids: list[str]
  mode_label: "vector_only" | "hybrid_seed"
```

### `GraphExpansionView`

```text
GraphExpansionView
  expansion: ExpansionResult | None
  expanded_chunk_ids: list[str]
  added_chunk_ids: list[str]            # expanded - seed
  resolved_chunks: list[RetrievedChunk] # payloads scrolled from store
  warnings: list[str]
  capped: bool                          # True if max_context truncated
  mechanism_label: "graph_expansion"    # never "local_expand_units"
```

### `HybridEvidenceContext`

Fused notebook evidence object for display + generation handoff (Key Entity "Hybrid evidence context"):

```text
HybridEvidenceContext
  query: str
  mode: "vector_only" | "hybrid_expanded" | "graph_guided_prefilter"
  seed: SeedRetrievalView
  expansion: GraphExpansionView | None
  evidence_chunks: list[RetrievedChunk]  # final ordered/fused list passed to generator
  document_overlays: dict[str, DocumentOverlay]  # subset for involved id_strs
  overlay_available: bool
  expansion_added_context: bool
  diagnostics: list[str]                 # human-readable stage notes / warnings
```

Rules:
- When hybrid expansion is enabled and graph is loaded, `evidence_chunks` MUST prefer expanded context (FR-009), not only unexpanded seeds.
- When expansion adds nothing, still set `expansion` with zero-added diagnostics (Edge Cases) — not a hard failure.
- When seed set is empty, skip expansion and generation; record empty context (Edge Cases / FR-014).

### `ModeComparisonRecord`

For US3 / FR-011:

```text
ModeComparisonRecord
  query: str
  vector_only_count: int
  hybrid_count: int
  expansion_ran: bool
  added_context_count: int
  sample_vector_only_ids: list[str]
  sample_hybrid_ids: list[str]
  notes: list[str]
```

### `GraphGuidedDemoResult` (secondary)

```text
GraphGuidedDemoResult
  start_id: str
  traversal_mode: str
  whitelist_size: int
  empty_filter_warning: bool
  filter_reason: str
  retrieval: RetrievalResult | None
```

Empty whitelist MUST keep `empty_filter_warning=True` and MUST NOT present unfiltered hits under a graph-guided label (FR-020, SC-007).

## 4. Relationships and pipeline mapping

```text
User query
  │
  ├─(vector seed)─▶ SeedRetrievalView.seed_chunks
  │                    │
  │                    ├ chunk_id ──▶ GraphExpansion.expand ──▶ ExpansionResult
  │                    │                                         │
  │                    │                                         ├ ordered_context_chunks
  │                    │                                         └ warnings
  │                    │                                         │
  │                    │                                         ▼
  │                    └──────── store.scroll(chunk_id in ...) ──▶ resolved chunks
  │
  ├─(overlay join)─▶ DocumentOverlay by evidence id_str
  │
  ├─(fuse)─▶ HybridEvidenceContext.evidence_chunks (+ diagnostics)
  │
  └─(optional)─▶ format_context_for_prompt → GeneratorClient → GenerationOutcome
```

Secondary branch:

```text
start id_str ─▶ GraphTraversal ─▶ GraphGuidedFilter ─▶ VectorRetriever(graph_guided_filter=...)
```

## 5. Display / citation rules

| Situation | Required notebook behavior |
| --- | --- |
| Hybrid evidence row | Show `chunk_id`, `parent_unit_id`, `id_str` (and citation label/title when present) |
| Overlay available | Show currency/authority for at least one involved document |
| Overlay missing | Label overlays unavailable; still allow structural expansion |
| External stub / non-citation-safe | Do not present as citation-ready evidence |
| Local `expand_units` vs graph expansion | Distinct labels in diagnostics |
| Generation with empty usable text | Skip with explicit empty-context message |

## 6. State machine for hybrid availability

```text
graph not loaded
  ├─ vector-only modes: allowed
  └─ hybrid expansion / hybrid ask: explicit failure (FR-015)

graph loaded, overlays missing
  ├─ structural expansion: allowed
  └─ currency/authority claims: disabled / labeled unavailable

graph + overlays loaded
  └─ full hybrid path + optional graph-guided pre-filter demo
```
