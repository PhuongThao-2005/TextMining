"""Sync scripts/_patch_faiss_hybrid_notebook.py with gpickle-first notebook behavior."""

from __future__ import annotations

from pathlib import Path

PATCH_PATH = Path("scripts/_patch_faiss_hybrid_notebook.py")
text = PATCH_PATH.read_text(encoding="utf-8")

# --- CONFIG ---
config_old = """# Graph + overlay sources (structural graph under data/v2)
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'

# Must match the embedding model used to build index.faiss."""

config_new = """# Graph + overlay sources (structural graph under data/v2)
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'
# Preferred structural graph artifact (built via scripts/build_kg_pickle.py)
KG_PICKLE_PATH = PROJECT_ROOT / 'data' / 'graph' / 'knowledge_graph.gpickle'
# Keep False for normal notebook use: load pickle only (no JSONL rebuild).
ALLOW_GRAPH_JSONL_REBUILD = False

# Must match the embedding model used to build index.faiss."""

if "KG_PICKLE_PATH = PROJECT_ROOT" not in text:
    if config_old not in text:
        raise SystemExit("CONFIG insert anchor not found")
    text = text.replace(config_old, config_new, 1)
    print("updated CONFIG paths")
else:
    print("CONFIG already has KG_PICKLE_PATH")

config_print_old = """print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
INDEX_DIR
'''
"""

config_print_new = """print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('KG_PICKLE_PATH:', KG_PICKLE_PATH)
print('ALLOW_GRAPH_JSONL_REBUILD:', ALLOW_GRAPH_JSONL_REBUILD)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
INDEX_DIR
'''
"""

if "print('KG_PICKLE_PATH:'" not in text:
    if config_print_old not in text:
        raise SystemExit("CONFIG print anchor not found")
    text = text.replace(config_print_old, config_print_new, 1)
    print("updated CONFIG prints")
else:
    print("CONFIG prints already include KG_PICKLE_PATH")

# --- IMPORTS ---
imports_old = """from knowledge_graph import (
    GraphExpansion,
    GraphLoaderPaths,
    KnowledgeGraphFacade,
    QueryConstraints,
    parse_authority_index_rows,
    parse_validity_event_rows,
)
"""

imports_new = """from knowledge_graph import (
    GraphBuildStats,
    GraphExpansion,
    GraphLoaderPaths,
    GraphPickleCorruptError,
    GraphPickleIncompatibleError,
    GraphPickleNotFoundError,
    KnowledgeGraphFacade,
    QueryConstraints,
    load_knowledge_graph,
    parse_authority_index_rows,
    parse_validity_event_rows,
)
"""

if "load_knowledge_graph," not in text:
    if imports_old not in text:
        raise SystemExit("IMPORTS anchor not found")
    text = text.replace(imports_old, imports_new, 1)
    print("updated HYBRID_IMPORTS")
else:
    print("HYBRID_IMPORTS already has load_knowledge_graph")

# --- PREFLIGHT/BUILD cell body ---
# Extract the new cell source from the notebook itself so the patcher stays in sync.
import json

nb = json.loads(Path("notebooks/faiss_retrieval_ready.ipynb").read_text(encoding="utf-8"))
cell12 = "".join(nb["cells"][12].get("source", []))
if "Graph load (gpickle)" not in cell12:
    raise SystemExit("notebook cell 12 is not gpickle-first")

# Normalize any residual non-ascii dashes in notebook cell before embedding
cell12 = (
    cell12.replace("\u2014", "-")
    .replace("\u2013", "-")
    .replace("\u2192", "->")
)

# The patcher stores these as Python triple-quoted strings with escaped newlines
# in some places historically used '\\n' for print statements. Our notebook source
# uses real newlines and normal '\n' escapes inside the code. We embed as a raw
# triple-quoted string.

start_marker = "HYBRID_PREFLIGHT_BUILD = '''"
end_marker = "'''\n\nHYBRID_HELPER = '''"

start = text.find(start_marker)
if start < 0:
    raise SystemExit("HYBRID_PREFLIGHT_BUILD start not found")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("HYBRID_PREFLIGHT_BUILD end not found")

# Ensure cell content ends with a newline for the closing '''
if not cell12.endswith("\n"):
    cell12 = cell12 + "\n"

# Escape any accidental triple quotes
if "'''" in cell12:
    raise SystemExit("cell12 contains triple quotes; cannot embed in ''' string")

new_block = start_marker + cell12 + end_marker
text = text[:start] + new_block + text[end + len(end_marker) :]
print("replaced HYBRID_PREFLIGHT_BUILD with notebook gpickle-first cell")

# Also update outline markdown lightly if it still says build_graph only
old_outline_line = "5. **Graph build** — `KnowledgeGraphFacade` → `build_graph()` → print stats (FR-004)."
# This may not be in the patcher; ignore if absent.

# Update data/v2 note in setup markdown if present
old_data_note = """data/v2/             # required for hybrid graph path
  documents.jsonl, provisions.jsonl, chunks.jsonl, edges.jsonl, external_stubs.jsonl
  validity_timeline.jsonl, authority_index.jsonl   # optional overlays
```
"""
new_data_note = """data/graph/
  knowledge_graph.gpickle   # preferred structural graph for hybrid path

data/v2/             # optional overlays; JSONL rebuild only if ALLOW_GRAPH_JSONL_REBUILD
  documents.jsonl, provisions.jsonl, chunks.jsonl, edges.jsonl, external_stubs.jsonl
  validity_timeline.jsonl, authority_index.jsonl   # optional overlays
```
"""
if old_data_note in text and "knowledge_graph.gpickle" not in text.split("HYBRID_IMPORTS")[0]:
    text = text.replace(old_data_note, new_data_note, 1)
    print("updated setup data note for gpickle")
elif "knowledge_graph.gpickle" in text:
    print("setup data note already mentions gpickle or already patched")
else:
    print("setup data note anchor not found (ok if markdown differs)")

PATCH_PATH.write_text(text, encoding="utf-8")
print("wrote", PATCH_PATH)

# Also rewrite notebook cell 12 with ASCII-safe dashes to avoid encoding glitches
nb["cells"][12]["source"] = [line + "\n" for line in cell12.split("\n")[:-1]] + (
    [cell12.split("\n")[-1] + "\n"] if cell12.split("\n")[-1] else []
)
Path("notebooks/faiss_retrieval_ready.ipynb").write_text(
    json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
)
print("rewrote notebook cell 12 with ASCII-safe punctuation")
