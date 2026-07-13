# G-LRAG Knowledge Graph Module

This package implements the Knowledge Graph module for G-LRAG v2, enabling structural traversal, context expansion, and dynamic validity/precedence overlays.

---

## 1. Quick Start

Ensure your v2 dataset is compiled under `data/v2/`.

### Run Verification Script
To build the graph, load overlays, and run tests, execute:
```bash
python scripts/verify_kg.py
```

---

## 2. Architecture

The package follows a decoupled, service-oriented design to isolate data loading, graph building, path traversals, overlays, and query constraints.

```text
 (JSONL files) ──▶ GraphLoader ──▶ Parser / EdgeParser ──▶ GraphBuilder
                                                              │
                                                              ▼
 ContextBuilder ◀── OverlayJoiner ◀── GraphTraversal ◀── KnowledgeGraph
       │
       ▼
 (id_str filter) ──▶ VectorRetriever (src/retrieval/)
```

* **In-Memory Graph:** Graph nodes and structural containment are assembled and validated in-memory, ensuring low latency.
* **Separated Overlays:** Validity dates and rankings are joined dynamically at query time and are never stored in graph nodes.
* **Verified-Only Traversals:** Circular path logic is avoided by only traversing cross-document edges where `direction_verified == True`.

---

## 3. Folder Structure

- [builder.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/builder.py): Materializes `DOCUMENT_HAS_PROVISION`, `PROVISION_HAS_CHUNK`, `CHUNK_NEXT`, and `PROVISION_NEXT` edges.
- [parser.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/parser.py): Translates records to typed nodes.
- [edge_parser.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/edge_parser.py): Normalizes edge direction and checks verification flags.
- [traversal.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/traversal.py): BFS engine for path queries.
- [expansion.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/expansion.py): Slides window of sibling chunks and walks provision chains to preserve reading order.
- [overlay.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/overlay.py): Chronologically folds validity events and resolves rank tie-breakers.
- [context.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/context.py): Resolves constraints and overlays to build whitelists.
- [facade.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/facade.py): Unified entry point.
- [utils.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/utils.py): Consolidated JSON conversions and quality flag helper utilities.
- [schema.py](file:///d:/HK3_3/Text%20Mining/TextMining/src/knowledge_graph/schema.py): Core node dataclass definitions.

---

## 4. Usage

The `KnowledgeGraphFacade` is the public entry point.

### Basic Steps
1. **Instantiation:** Create the facade instance.
2. **Build Graph:** Invoke `build_graph()` to parse inputs and construct the graph.
3. **Load Overlays:** Stream validity timeline and authority indexes, and call `build_overlay_bundle()`.
4. **Traverse Paths:** Query paths by invoking `traverse()`.
5. **Get Filters:** Generate whitelists using `build_graph_guided_filter()`.

---

## 5. Example

```python
from pathlib import Path
from retrieval.io_utils import read_jsonl
from knowledge_graph import (
    KnowledgeGraphFacade,
    parse_validity_event_rows,
    parse_authority_index_rows,
    QueryConstraints
)

# Initialize facade
facade = KnowledgeGraphFacade()

# 1. Build structural graph
build_result = facade.build_graph()
graph = build_result.graph
print(f"Loaded {build_result.stats.document_count} documents.")

# 2. Load overlays
data_dir = Path("data/v2")
events = list(parse_validity_event_rows(read_jsonl(data_dir / "validity_timeline.jsonl")))
entries = list(parse_authority_index_rows(read_jsonl(data_dir / "authority_index.jsonl")))

# 3. Dynamic Overlay Join
overlay_bundle = facade.build_overlay_bundle(
    documents=graph.documents.values(),
    validity_events=events,
    authority_entries=entries,
    as_of_date="2026-07-13"
)

# 4. Traverse & Filter
traversal = facade.traverse(graph, start_id="4260", mode="basis", max_depth=3)
constraints = QueryConstraints(validity_groups=("active", "partial"))
guided_filter = facade.build_graph_guided_filter(
    graph=graph,
    traversal=traversal,
    overlays=overlay_bundle.document_overlays,
    filter_profile="current_law",
    constraints=constraints
)

print(f"Whitelist document IDs to filter vector search: {guided_filter.id_strs}")
```
