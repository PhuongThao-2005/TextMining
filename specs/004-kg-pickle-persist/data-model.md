# Phase 1 Data Model: Structural Knowledge Graph Pickle Artifact

This feature introduces one new **derived on-disk artifact** (the structural graph pickle) and small in-process envelope/result types for save/load. It does **not** change the v2 JSONL source contracts.

## 1. Source entities (read-only at build time)

| Entity | Location | Role |
| --- | --- | --- |
| Documents | `data/v2/documents.jsonl` | `Document` nodes |
| External stubs | `data/v2/external_stubs.jsonl` | Non-citable external targets |
| Provisions | `data/v2/provisions.jsonl` | Citation units |
| Chunks | `data/v2/chunks.jsonl` | Retrieval pointer nodes |
| Edges | `data/v2/edges.jsonl` | Cross-document relationships |

Loaded via existing [`GraphLoaderPaths`](../../src/knowledge_graph/loader.py) / [`KnowledgeGraphFacade.build_graph()`](../../src/knowledge_graph/facade.py).

Quarantine files are never inputs.

### Optional after load (not inside pickle)

| Entity | Location | Role |
| --- | --- | --- |
| Validity timeline | `data/v2/validity_timeline.jsonl` | Dynamic currency overlay |
| Authority index | `data/v2/authority_index.jsonl` | Dynamic authority overlay |

## 2. Existing structural graph entity (payload)

From [`src/knowledge_graph/builder.py`](../../src/knowledge_graph/builder.py):

```text
KnowledgeGraph
  documents: dict[str, DocumentNode]              # key = id_str
  external_stubs: dict[str, ExternalStubNode]     # key = id_str
  provisions: dict[str, ProvisionNode]            # key = unit_id
  chunks: dict[str, ChunkNode]                    # key = chunk_id
  document_edges: tuple[GraphEdge, ...]
  verified_document_edges: tuple[GraphEdge, ...]
  structural_edges: tuple[StructuralEdge, ...]
  document_to_provisions: dict[str, tuple[str, ...]]
  provision_to_chunks: dict[str, tuple[str, ...]]
  provision_next: dict[str, str]
  chunk_next: dict[str, str]
```

### Shared legal identity (must survive round-trip)

```text
chunk_id  →  parent_unit_id  →  id_str
(chunk)      (provision)        (document)
```

Also preserved:

- External stubs remain `citation_safe = false`
- Verified vs full document edge sets remain distinct
- Reading-order maps `chunk_next` / `provision_next` remain usable by expansion/traversal

### Node field sources (unchanged)

- `DocumentNode`, `ExternalStubNode`, `ProvisionNode`, `ChunkNode` from parser/schema modules
- `GraphEdge` from edge schema
- `StructuralEdge` from builder

Overlays (`DocumentOverlay`, `OverlayBundle`) are **not** part of this artifact.

## 3. New on-disk artifact

### `knowledge_graph.gpickle` (default path `data/graph/knowledge_graph.gpickle`)

| Field | Description |
| --- | --- |
| Format | Python pickle of `GraphPickleEnvelope` |
| Extension | `.gpickle` (portable graph pickle; not NetworkX-specific) |
| Contents | Structural graph + metadata only |
| Mutability | Replaced only by explicit rebuild/save |
| Consumers | Colab/local loaders, expansion/traversal after load |

### Envelope schema

```text
GraphPickleEnvelope
  format_name: str                 # constant "g-lrag-knowledge-graph"
  format_version: int              # start at 1
  created_at_utc: str              # ISO-8601 UTC
  source_data_dir: str | None      # optional path label used at build
  stats: GraphBuildStats | None    # preferred: full build stats object
  warnings: tuple[str, ...]        # build warnings snapshot
  graph: KnowledgeGraph            # required payload
```

If storing `GraphBuildStats` directly is inconvenient for a future format, a dict of core counts is acceptable as long as load can still smoke-check:

```text
document_count
external_stub_count
provision_count
chunk_count
document_edge_count
verified_document_edge_count
unverified_document_edge_count
structural_edge_count
```

### Artifact info returned by save

```text
GraphPickleArtifactInfo
  path: Path
  format_version: int
  byte_size: int
  created_at_utc: str
  stats: GraphBuildStats | count dict
```

### Load result

```text
GraphPickleLoadResult
  graph: KnowledgeGraph
  format_version: int
  created_at_utc: str | None
  source_data_dir: str | None
  stats: GraphBuildStats | count dict | None
  warnings: tuple[str, ...]
  path: Path
```

## 4. Build / load flow entities

### Build path

```text
v2 structural JSONL
  → GraphLoader / parsers
  → GraphBuilder
  → KnowledgeGraph (+ GraphBuildStats, warnings)
  → GraphPickleEnvelope
  → atomic write → knowledge_graph.gpickle
```

### Load path

```text
knowledge_graph.gpickle
  → unpickle envelope
  → validate format_name / format_version / graph type
  → KnowledgeGraph
  → GraphExpansion / GraphTraversal / optional OverlayJoiner
```

### Failure entities (explicit)

| Condition | Behavior |
| --- | --- |
| Missing structural sources | Fail before write; list missing paths |
| Build exception | Fail; no final artifact |
| Serialize failure | Fail; temp file cleaned; previous final artifact left intact if present |
| Missing pickle on load | Clear file-not-found error |
| Corrupt pickle | Clear unreadable/corrupt error |
| Unknown format/version | Clear incompatible-artifact error |
| Empty silent graph | Forbidden |

## 5. Relationships to existing module entities

```text
GraphBuildResult.graph  ──save──▶  GraphPickleEnvelope.graph
GraphBuildResult.stats  ──save──▶  GraphPickleEnvelope.stats
GraphBuildResult.warnings ──save─▶ GraphPickleEnvelope.warnings

GraphPickleLoadResult.graph ──▶ GraphExpansion(graph)
GraphPickleLoadResult.graph ──▶ GraphTraversal(graph)
GraphPickleLoadResult.graph.documents ──optional──▶ OverlayJoiner (if overlay files present)
```

## 6. Out of model (this feature)

- Neo4j nodes/relationships
- FAISS index packaging
- Frozen overlay snapshots
- Quarantine ingestion
- New legal identity scheme
