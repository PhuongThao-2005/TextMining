"""Dump full_pipeline notebook cell index and key sources."""
from __future__ import annotations

import json
from pathlib import Path

NB = Path("notebooks/full_pipeline.ipynb")
nb = json.loads(NB.read_text(encoding="utf-8"))

index_lines = [f"n_cells={len(nb['cells'])}"]
for i, cell in enumerate(nb["cells"]):
    src = "".join(cell.get("source", []))
    head = (src.strip().splitlines() or [""])[0][:140]
    index_lines.append(f"{i:02d}|{cell['cell_type'][:4]}|{head}")

Path("_nb_cells_index.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

# Dump cells that matter for RAM / hybrid wiring
keywords = (
    "INDEX_DIR",
    "ENABLE_HYBRID",
    "SentenceTransformer",
    "SQLitePayload",
    "load_knowledge",
    "gpickle",
    "run_hybrid",
    "embedder",
    "ALLOW_GRAPH",
    "KG_PICKLE",
)
for i, cell in enumerate(nb["cells"]):
    src = "".join(cell.get("source", []))
    if any(k in src for k in keywords) or i in {0, 1, 2, 3, 4, 5}:
        Path(f"_cell{i:02d}.txt").write_text(src, encoding="utf-8")

print(f"dumped {len(nb['cells'])} cells")
