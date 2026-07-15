import json
from pathlib import Path

nb_path = Path("notebooks/faiss_retrieval_ready.ipynb")
nb = json.loads(nb_path.read_text(encoding="utf-8"))

old = """data/v2/             # required for hybrid graph path
  documents.jsonl, provisions.jsonl, chunks.jsonl, edges.jsonl, external_stubs.jsonl
  validity_timeline.jsonl, authority_index.jsonl   # optional overlays
```
"""

new = """data/graph/
  knowledge_graph.gpickle   # preferred structural graph for hybrid path

data/v2/             # optional overlays; JSONL rebuild only if ALLOW_GRAPH_JSONL_REBUILD
  documents.jsonl, provisions.jsonl, chunks.jsonl, edges.jsonl, external_stubs.jsonl
  validity_timeline.jsonl, authority_index.jsonl   # optional overlays
```
"""

changed = 0
for cell in nb["cells"]:
    src = "".join(cell.get("source", []))
    if old in src:
        src = src.replace(old, new)
        # also mention build script if not present
        if "build_kg_pickle.py" not in src and "Run cells top to bottom" in src:
            src = src.replace(
                "Run cells top to bottom.",
                "Build the pickle once with `python scripts/build_kg_pickle.py` (default output `data/graph/knowledge_graph.gpickle`), then run cells top to bottom.",
            )
        cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + (
            [src.split("\n")[-1] + "\n"] if src.split("\n")[-1] else []
        )
        changed += 1

nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("markdown cells updated:", changed)

# patch script setup markdown if still old
patch = Path("scripts/_patch_faiss_hybrid_notebook.py")
t = patch.read_text(encoding="utf-8")
if old in t:
    t = t.replace(old, new)
    if "build_kg_pickle.py" not in t.split("HYBRID_IMPORTS")[0] and "Run cells top to bottom." in t:
        t = t.replace(
            "Run cells top to bottom.",
            "Build the pickle once with `python scripts/build_kg_pickle.py` (default output `data/graph/knowledge_graph.gpickle`), then run cells top to bottom.",
            1,
        )
    patch.write_text(t, encoding="utf-8")
    print("patch script markdown updated")
else:
    print("patch script markdown already updated or different")
