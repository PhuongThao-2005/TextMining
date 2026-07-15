import json
from pathlib import Path

nb = json.loads(Path("notebooks/faiss_retrieval_ready.ipynb").read_text(encoding="utf-8"))
for i in [5, 11, 12]:
    s = "".join(nb["cells"][i].get("source", []))
    Path(f"_cell{i}.txt").write_text(s, encoding="utf-8")
    print("cell", i, "chars", len(s))
    print("  build_graph():", "build_graph()" in s)
    print("  load_knowledge_graph:", "load_knowledge_graph" in s)
    print("  KG_PICKLE_PATH:", "KG_PICKLE_PATH" in s)
    print("  Graph load (gpickle):", "Graph load (gpickle)" in s)
    print("  Overlay join:", "Overlay join" in s)
    print("  ALLOW_GRAPH_JSONL_REBUILD:", "ALLOW_GRAPH_JSONL_REBUILD" in s)

# ensure no default direct build path remains as primary
full = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
print("\nfull notebook checks:")
print("  kg_facade.build_graph() count:", full.count("kg_facade.build_graph()"))
print("  facade.build_graph() count:", full.count(".build_graph()"))
print("  load_knowledge_graph count:", full.count("load_knowledge_graph"))
print("  KG_PICKLE_PATH count:", full.count("KG_PICKLE_PATH"))
