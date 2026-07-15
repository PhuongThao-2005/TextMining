# 2026-07-15 — FAISS IVFPQ rebuild + Colab RAM mitigations

## Problem

`notebooks/full_pipeline.ipynb` (and the sibling FAISS retrieval notebook) peaked around **~12 GB RSS** on Colab when hybrid mode was enabled:

| Resident | Approx. size | Notes |
| --- | --- | --- |
| `IndexFlatIP` FAISS | ~6 GB | 1.5M × 1024 float32 |
| `multilingual-e5-large` | ~2–3 GB | eager `SentenceTransformer` load |
| Structural KG `.gpickle` + overlays | multi-GB | full in-memory graph |

SQLite payload cache was already disk-backed and not the main offender.

## Changes

### 1. Compressed FAISS rebuild (IVFPQ)

- New helpers: [`src/retrieval/faiss_index_types.py`](../../src/retrieval/faiss_index_types.py)
  - `FaissIndexConfig`, `create_empty_index`, `train_and_add_ivfpq`, `rebuild_index_to_ivfpq`
- [`FaissVectorStore`](../../src/retrieval/faiss_store.py) accepts `index_config`; buffers vectors for IVFPQ until `save()` / `finalize_ivfpq()`; writes `index_type.json`
- [`SQLitePayloadFaissVectorStore.load`](../../src/retrieval/sqlite_faiss_store.py) applies `nprobe` for IVF indexes
- CLI rebuild: [`scripts/rebuild_faiss_ivfpq.py`](../../scripts/rebuild_faiss_ivfpq.py)
- Build path: `--faiss-index-type ivfpq` on [`src/retrieval/build_vector_db.py`](../../src/retrieval/build_vector_db.py)

**One-time Colab/server rebuild (payloads unchanged):**

```bash
python scripts/rebuild_faiss_ivfpq.py \
  --source-dir /path/to/faiss_index \
  --dest-dir /path/to/faiss_index_ivfpq \
  --copy-sidecar \
  --nlist 4096 --m 64 --nprobe 32
```

Then point notebook `INDEX_DIR` at the dest directory.

Expected: `index.faiss` drops from multi-GB to hundreds of MB (exact ratio depends on `m` / `nbits`). Recall is approximate; raise `nprobe` if needed.

### 2. Medium-term notebook / code RAM controls (hybrid retained)

- [`LazySentenceTransformerEmbedder`](../../src/retrieval/embeddings.py) — defers e5-large until first encode
- [`memory_utils.print_memory`](../../src/retrieval/memory_utils.py) — RSS probe (`psutil` optional)
- [`notebooks/full_pipeline.ipynb`](../../notebooks/full_pipeline.ipynb):
  - `LAZY_EMBEDDER = True` (default)
  - `LAZY_GRAPH_LOAD = True` (default) — preflight only; gpickle + overlays load on first hybrid call via `ensure_hybrid_graph()` / `require_graph_for_hybrid`
  - `FAISS_NPROBE`, `RUN_EXPORTS = False`
  - Memory probes after FAISS / graph load
  - Hybrid remains the default pipeline; missing graph still fails clearly under a hybrid label (FR-015)

### 3. Tests

- [`tests/retrieval/test_faiss_ivfpq.py`](../../tests/retrieval/test_faiss_ivfpq.py)
- [`tests/retrieval/test_memory_and_lazy_embedder.py`](../../tests/retrieval/test_memory_and_lazy_embedder.py)

## Non-goals

- Did not drop hybrid mode
- Did not change payload SQLite schema
- Did not shard the in-memory knowledge graph (structural multi-GB limit remains; lazy load only defers it)
