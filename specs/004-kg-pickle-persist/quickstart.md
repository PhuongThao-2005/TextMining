# Quickstart: Structural Knowledge Graph Pickle Artifact

Operator and Colab validation guide for feature `004-kg-pickle-persist`. This is not the implementation — see [`plan.md`](plan.md), [`data-model.md`](data-model.md), [`research.md`](research.md). Tasks belong in `tasks.md` via `/speckit.tasks`.

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ | Same env as `src/` |
| Project package path | `src/` on `PYTHONPATH` / `sys.path` (repo already uses this for tests/scripts) |
| Structural v2 sources (build machine) | `data/v2/documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `external_stubs.jsonl` |
| Overlay sources | Optional; only if you want dynamic overlays after load |
| Colab/runtime | Ability to upload/mount one `.gpickle` and import project `knowledge_graph` code |
| Trust | Load only project-built pickle files |

### Expected layout after build

```text
data/v2/                         # sources (build machine)
  documents.jsonl
  provisions.jsonl
  chunks.jsonl
  edges.jsonl
  external_stubs.jsonl
  validity_timeline.jsonl        # optional, not in pickle
  authority_index.jsonl          # optional, not in pickle

data/graph/
  knowledge_graph.gpickle        # derived portable artifact
```

## 1) Local build (once, or when sources change)

From project root (`L_RAG/`):

```bash
# Fixture / unit tests after implementation
python -m pytest tests/knowledge_graph/test_persist.py -q

# Full-corpus build (paths may be adjusted by CLI defaults)
python scripts/build_kg_pickle.py \
  --data-dir data/v2 \
  --output data/graph/knowledge_graph.gpickle
```

### Expected build output (smoke)

The script should print at least:

- build duration
- document / external stub / provision / chunk counts
- document edge count and verified vs unverified when available
- structural edge count
- non-fatal warning count (if any)
- output path
- artifact byte size

### Failure cases to confirm

| Case | Expected |
| --- | --- |
| Missing structural JSONL | Non-zero exit / clear missing-file list; no success-claimed pickle |
| Output parent missing | Parent directory created, or clear failure before success claim |
| Rebuild same path | New successful write replaces previous artifact |

## 2) Transfer to Colab

1. Copy only `knowledge_graph.gpickle` (plus optional overlay JSONL if desired).
2. Upload to Colab (`/content/...`) or mount Drive.
3. Ensure the G-LRAG `src/` tree (or installed package) is importable in the Colab runtime so typed graph classes can unpickle.

> Pickle restores Python objects defined by this project. Loading requires compatible `knowledge_graph` class definitions — not the JSONL sources.

## 3) Load in Colab / notebook (no structural JSONL required)

```python
from pathlib import Path
from knowledge_graph import load_knowledge_graph, GraphExpansion

PICKLE_PATH = Path("/content/knowledge_graph.gpickle")  # or Drive path

loaded = load_knowledge_graph(PICKLE_PATH)
graph = loaded.graph

print("format_version:", loaded.format_version)
print("documents:", len(graph.documents))
print("provisions:", len(graph.provisions))
print("chunks:", len(graph.chunks))
print("document_edges:", len(graph.document_edges))
print("verified_edges:", len(graph.verified_document_edges))

# Structural consumer smoke check
expansion = GraphExpansion(graph)
# pick any known chunk_id from graph.chunks when exploring
# result = expansion.expand(seed_chunk_ids=[some_chunk_id], max_hop=1, max_context=8)
```

### Load failure cases to confirm

| Case | Expected |
| --- | --- |
| Missing file | Clear file-not-found error |
| Corrupt file | Clear unreadable/corrupt error |
| Wrong/unknown envelope version | Clear incompatible-artifact error |
| No silent empty graph | Must not return an empty success object on failure |

## 4) Optional overlays after load

Overlays are **not** inside the pickle. If you also have overlay files in the runtime:

```python
from retrieval.io_utils import read_jsonl
from knowledge_graph import (
    KnowledgeGraphFacade,
    parse_validity_event_rows,
    parse_authority_index_rows,
)

facade = KnowledgeGraphFacade()
events = list(parse_validity_event_rows(read_jsonl(Path("validity_timeline.jsonl"))))
authority = list(parse_authority_index_rows(read_jsonl(Path("authority_index.jsonl"))))

overlay_bundle = facade.build_overlay_bundle(
    documents=graph.documents.values(),
    validity_events=events,
    authority_entries=authority,
    as_of_date="2026-07-13",
)
print("overlay docs:", len(overlay_bundle.document_overlays))
```

If overlay files are absent, structural load and expansion still work; simply do not claim currency/authority reasoning.

## 5) Validation scenarios

### V1 — Build portable artifact (US1, SC-001/SC-005)

**Given** structural v2 sources present.

**When** `scripts/build_kg_pickle.py` runs.

**Then** `data/graph/knowledge_graph.gpickle` exists, counts are printed, and exit status indicates success.

### V2 — Load without JSONL (US2, SC-002/SC-003)

**Given** only the pickle file + project code in a clean session (no `data/v2` structural files).

**When** `load_knowledge_graph(path)` runs.

**Then** graph counts match saved metadata/smoke expectations and identity maps resolve for sample ids (`chunk → provision → document`).

### V3 — Overlays optional (US3, SC-004)

**Given** pickle loaded and no overlay files.

**When** structural expansion/traversal is used.

**Then** operations succeed and system does not claim overlays loaded.

### V4 — Explicit rebuild (US4)

**Given** an existing pickle.

**When** build is rerun successfully to the same path.

**Then** the artifact is replaced and reported counts reflect the current sources.

### V5 — Bad load inputs (Edge Cases, SC-006)

**Given** missing/corrupt/incompatible pickle.

**When** load is attempted.

**Then** an explicit error is raised; no empty silent graph.

## 6) Out of scope checks (do not require for acceptance)

- Neo4j write/read
- FAISS packaging
- Automatic rebuild-from-JSONL when pickle path is requested
- Judged e2e answer evaluation

## 7) Suggested acceptance command set (post-implement)

```bash
# Unit/integration
python -m pytest tests/knowledge_graph/test_persist.py -q

# Optional full-corpus operator smoke (when data/v2 available)
python scripts/build_kg_pickle.py --data-dir data/v2 --output data/graph/knowledge_graph.gpickle

# Load smoke without depending on JSONL in the same process
python - <<'PY'
from pathlib import Path
from knowledge_graph import load_knowledge_graph
loaded = load_knowledge_graph(Path("data/graph/knowledge_graph.gpickle"))
g = loaded.graph
assert g.documents and g.chunks
print("ok", len(g.documents), len(g.chunks), loaded.path)
PY
```
