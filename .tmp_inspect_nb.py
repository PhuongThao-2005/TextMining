import json
from pathlib import Path

nb = json.loads(Path("notebooks/faiss_retrieval_ready.ipynb").read_text(encoding="utf-8"))
out = []
for i, c in enumerate(nb["cells"]):
    s = "".join(c.get("source", []))
    keys = [
        "class GraphLoadStatus",
        "V2_DATA_DIR =",
        "from knowledge_graph",
        "ENABLE_HYBRID_EXPANSION",
        "Graph build",
        "gpickle",
        "load_knowledge_graph",
        "preflight_graph_sources",
    ]
    if any(k in s for k in keys):
        out.append(f"CELL {i} type={c['cell_type']}\n{s}\n=====END=====\n")

Path("_nb_graph_cells.txt").write_text("\n".join(out), encoding="utf-8")
print("wrote", len(out), "cells")
print("total chars", sum(len(x) for x in out))

graph_dir = Path("data/graph")
print("graph_dir exists", graph_dir.exists())
if graph_dir.exists():
    for p in sorted(graph_dir.iterdir()):
        print(p.name, p.stat().st_size if p.is_file() else "DIR")
print("default pickle exists", Path("data/graph/knowledge_graph.gpickle").exists())
