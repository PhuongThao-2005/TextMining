# Quickstart: Colab-Safe Full Pipeline Memory Fit

Operator + Colab validation guide for feature `005-colab-ram-fit`. **Not** implementation — see [`plan.md`](plan.md), [`data-model.md`](data-model.md), [`research.md`](research.md). Tasks belong in `tasks.md` via `/speckit.tasks`.

Primary surface: [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb).

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ Jupyter kernel | Same env as `src/` |
| Packages | `faiss-cpu`, `sentence-transformers`, `pandas`, `openai` (existing notebook install cell); optional `psutil` for richer memory diagnostics |
| Project code | `src/` importable (`sys.path` / package install) so FAISS + graph pickle types load |
| Target runtime (success bar) | ~12GB RAM hosted notebook (e.g. free Google Colab) for **Colab-safe** defaults |
| Higher-RAM host | Supported via **unconstrained** profile for fuller demos |
| Generator credentials (optional) | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME` — remote API only; local in-process LLM out of scope for Colab-safe guarantees |
| Trust | Load only project-built graph pickle files |

## Artifact packs (prepare locally, transfer to Colab)

### A) Vector-only Colab-safe pack (minimal)

```text
src/                                 # project code (or installed package)
data/faiss_index/
  index.faiss                        # required
  payloads.jsonl                     # required (cache rebuild source)
  payload_cache.sqlite               # strongly preferred, prebuilt + fresh
  id_map.json                        # optional
```

Use when only need pure vector retrieval (+ optional remote generation).

### B) Hybrid Colab-safe pack (preferred for demos)

Everything in **A**, plus:

```text
data/graph/
  knowledge_graph.gpickle            # preferred structural graph (feature 004)

# optional overlays (not required for structural hybrid success)
data/v2/                             # or Colab upload paths
  validity_timeline.jsonl
  authority_index.jsonl
```

**Do not require** full structural v2 JSONL on Colab when pickle present.

### C) Avoid on ~12GB by default

| Avoid | Why |
| --- | --- |
| Full structural JSONL rebuild in-notebook | High peak RAM; Colab-safe requires opt-in |
| Full payload CSV export (`limit=None`) | Multi-GB temporary frames |
| Large benchmark samples with generation | Repeated retrieve/generate pressure |
| Enabling every optional demo at once | Success bar is default path, not full opt-in |
| Local in-process LLM | Out of scope for Colab-safe RAM guarantees |
| Silent / accidental cold `payload_cache.sqlite` rebuild without prebuilt cache | Costly on Colab; ship fresh cache when possible |

### Local prep once (build machine)

From project root (`L_RAG/`):

```bash
# 1) FAISS index already built (existing pipeline)
# Ensure payload cache exists under the index dir when possible:
#   data/faiss_index/payload_cache.sqlite

# 2) Portable structural graph for hybrid Colab
python scripts/build_kg_pickle.py \
  --data-dir data/v2 \
  --output data/graph/knowledge_graph.gpickle
```

Transfer packs via Drive mount, zip upload, or equivalent. On Colab, point notebook paths at `/content/...` or Drive locations.

## Config flags (after implementation)

Set near top config cell of [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb):

| Parameter | Colab-safe default | Purpose |
| --- | --- | --- |
| `RUNTIME_PROFILE` | `"colab_safe"` | Named profile (`"colab_safe"` \| `"unconstrained"`) |
| `COLAB_SAFE` | `True` | Convenience alias when profile is Colab-safe |
| `GRAPH_PICKLE_PATH` | `{root}/data/graph/knowledge_graph.gpickle` | Preferred hybrid graph source |
| `ALLOW_JSONL_GRAPH_REBUILD` | `False` | Must stay False for default Colab-safe; warn + opt-in only |
| `ENABLE_HYBRID_EXPANSION` | `True` (if pickle present) | Hybrid path intent; still requires loaded graph |
| `TOP_K` | `20` | Conservative FAISS candidates |
| `TOP_N` | `5`–`8` | Smaller result/seed set |
| `HYBRID_MAX_HOP` | `1` | Single-hop expansion |
| `HYBRID_MAX_CONTEXT` | `8` | Cap expanded context; report when capped |
| `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` | `False` | Secondary path off |
| `LOCAL_EXPAND_UNITS` / `EXPAND_UNITS` | `False` | Avoid conflating local vs graph expansion |
| `RUN_PAYLOAD_CSV_EXPORT` | `False` | Gate full/large CSV dump |
| `RUN_PAYLOAD_CACHE_EXPORT` | `False` | Gate bulk cache export/download cell |
| `RUN_BENCHMARK_SAMPLE` | `False` | Gate multi-question benchmark auto-run |
| `BENCHMARK_SAMPLE_SIZE` | `3`–`5` when enabled | Keep small if opt-in |
| `EMBEDDING_MODEL` | model matching FAISS index | **No silent swap** that invalidates scores |

### Unconstrained profile (local / high-RAM)

```text
RUNTIME_PROFILE = "unconstrained"
COLAB_SAFE = False
# Optionally enable exports, larger TOP_K/TOP_N, JSONL rebuild, larger samples
```

Unconstrained must remain available so fuller demos not permanently removed (SC-010).

## Staged run order (Colab-safe)

```text
Stage A  config + profile + load plan / preflight
Stage B  FAISS + embedder + vector smoke query
Stage C  structural graph (pickle preferred) + optional overlays + hybrid smoke
Stage D  optional remote generation
Stage E  opt-in heavy demos only (CSV export, cache export, large benchmark, graph-guided, stress loops)
```

Rules:

1. After **Stage B**, pure vector queries work **without** loading graph.
2. Hybrid-labeled helpers available only after successful **Stage C**.
3. Default Colab-safe **Run all** must not execute Stage E bodies unless opt-in flags true.
4. Optional cleanup/release helper may drop export frames or unload graph (best-effort `gc.collect()`).

### What preflight / load plan should show

- Profile in effect (`colab_safe` / `unconstrained`)
- Artifact inventory: present/missing + approximate on-disk sizes
- Planned actions: load / defer / skip / opt_in_required / warn_rebuild
- Graph source mode: `pickle` | `jsonl_rebuild` | `unavailable`
- Best-effort memory snapshot when APIs exist (optional `psutil` / platform fallbacks)
- After loads: resident components (store, embedder, graph, overlays)

### Graph source decision (Colab-safe)

| Priority | Condition | Action |
| --- | --- | --- |
| 1 | Pickle present and readable | `load_knowledge_graph` / `facade.load_graph` |
| 2 | Pickle missing, JSONL present, `ALLOW_JSONL_GRAPH_REBUILD=False` | Skip hybrid; mark unavailable; keep vector-only |
| 3 | Pickle missing, JSONL present, opt-in True | **Warn** rebuild may exceed 12GB; then `build_graph()` |
| 4 | Neither pickle nor structural JSONL | Hybrid unavailable; vector-only |

## Success labels (must not conflate)

| Label | Meaning |
| --- | --- |
| `vector_only` / `vector_only_colab_safe_success` | Graph not used; pure vector path OK |
| `hybrid_expanded` / `hybrid_colab_safe_success_pickle` | Structural graph loaded (preferably pickle) and hybrid path used |
| `hybrid_unavailable` | Hybrid requested or intended but graph not loaded (policy/artifacts/RAM) |
| Clear error on hybrid-labeled call without graph | **Never** silent vector results under a hybrid name |

## Validation scenarios

### V1 — Vector-only Colab-safe smoke (US3, SC-001, SC-004)

**Given** vector-only pack (FAISS + preferred cache), `RUNTIME_PROFILE="colab_safe"`, hybrid/graph skipped or graph absent.

**When** Stages A–B run and one sample vector query executes.

**Then**:

- setup completes without OOM kill on ~12GB
- results labeled `vector_only`
- graph not required
- no hybrid wording for result mode

### V2 — Hybrid Colab-safe via pickle (US1, SC-002, SC-005)

**Given** hybrid pack: FAISS artifacts + `knowledge_graph.gpickle`, Colab-safe defaults, `ALLOW_JSONL_GRAPH_REBUILD=False`.

**When** Stages A–C run (pickle load, not JSONL rebuild) and one sample hybrid query runs.

**Then**:

- load plan reports graph source mode `pickle`
- hybrid setup completes without OOM kill on ~12GB
- seed and/or expanded evidence returned with hybrid labels
- session success can be described as hybrid Colab-safe with pickle

### V3 — Run-all skips heavy opt-in cells (US1.4, US4, SC-003)

**Given** Colab-safe defaults with all `RUN_*` heavy flags `False`.

**When** user runs all non-optional cells top to bottom (“Run all”).

**Then**:

- payload CSV export body does not execute
- payload cache bulk export body does not execute
- large benchmark sample does not auto-run
- graph-guided demo stays off
- vector and (if pickle present) hybrid smoke still reachable

### V4 — Load plan and pickle preference (US2, FR-009, SC-005)

**Given** both pickle and structural JSONL present.

**When** Colab-safe preflight runs.

**Then**:

- inventory lists FAISS, cache, pickle, JSONL, overlays with presence/sizes when available
- planned graph source is `pickle` (not rebuild)
- diagnostics show which components will load/skip/defer

### V5 — No silent JSONL rebuild (US2, Edge Cases, SC-006)

**Given** pickle missing, structural JSONL present, Colab-safe, `ALLOW_JSONL_GRAPH_REBUILD=False`.

**When** graph/hybrid setup runs.

**Then**:

- notebook does **not** silently start full JSONL rebuild
- hybrid marked unavailable **or** rebuild refused until explicit opt-in after warning
- pure vector retrieval remains usable

### V6 — Hybrid request without graph fails clearly (US3, SC-004)

**Given** graph unavailable/skipped under Colab-safe policy.

**When** pure vector query runs — **then** it succeeds as `vector_only`.

**When** hybrid-labeled helper / hybrid `ask()` is requested — **then** clear failure / `hybrid_unavailable` (not silent vector under hybrid name).

### V7 — Staged execution (US4, SC-007)

**Given** documented notebook steps only (no source edits).

**When** operator runs Stage B, then later Stage C, then hybrid query.

**Then**:

- vector smoke works before graph load
- hybrid becomes available after pickle load without requiring undocumented steps
- optional generation remains optional (Stage D)

### V8 — Artifact packs documented (US5, SC-008)

**Given** this quickstart only.

**When** a new operator prepares Colab inputs.

**Then** they can list:

1. minimal vector-only pack
2. hybrid pack (FAISS + pickle; overlays optional; full JSONL not required when pickle present)
3. Colab-safe flags and what to avoid on 12GB

### V9 — Citation identities preserved (SC-009)

**Given** Colab-safe vector or hybrid success path.

**When** sample hits are displayed.

**Then**:

- citation-ready rows expose `chunk_id`, parent provision identity, document `id_str`
- external stubs / non-citation-safe nodes are not presented as citable evidence

### V10 — Unconstrained fuller demos still available (US5, SC-010)

**Given** machine with sufficient RAM and `RUNTIME_PROFILE="unconstrained"`.

**When** user enables optional exports / larger samples / optional JSONL rebuild per docs.

**Then** those capabilities remain reachable; Colab-safe defaults did not permanently remove them.

### V11 — Payload cache rebuild messaging (FR-020)

**Given** missing or stale `payload_cache.sqlite` with `payloads.jsonl` present.

**When** vector store load runs under Colab-safe.

**Then** notebook warns that cold cache rebuild can be costly before rebuild proceeds (progress messaging acceptable; must not be silent about cost).

### V12 — Overlays optional (FR-016)

**Given** pickle-loaded structural graph, overlay files missing.

**When** hybrid expansion runs.

**Then** structural hybrid still succeeds; overlays labeled unavailable; no false currency/authority claims.

## Optional generation

```bash
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY="sk-..."
export LLM_MODEL_NAME="your-model-name"
```

If credentials absent, retrieval/hybrid still completes; generation skip reason explicit. Generation remote only for Colab-safe guarantees.

## Cleanup between stages (best-effort)

After heavy optional cells or when freeing headroom:

1. Drop large export/comparison frames.
2. Optionally unload overlays or structural graph (hybrid becomes unavailable until reload).
3. Call garbage collection helper if provided.

Not an OS hard memory reservation.

## Out of scope checks (do not require for acceptance)

- Guaranteed OS-level cgroup/RAM reservation
- Local in-process LLM on 12GB
- Silent embedder swap to a smaller model without a matching index
- Replacing `verify_kg.py` / `evaluate_e2e.py`
- Neo4j persistence
- Every optional cell enabled simultaneously on free Colab

## Suggested acceptance checklist (post-implement)

```text
[ ] Colab-safe config + load plan cells exist and print graph source mode
[ ] Default Run-all skips CSV export, cache export, large benchmark, graph-guided
[ ] With FAISS only: vector smoke OK, labeled vector_only
[ ] With FAISS + gpickle: hybrid smoke via pickle, no JSONL rebuild
[ ] Without pickle, JSONL present, opt-in False: no silent rebuild; hybrid unavailable or refused
[ ] Hybrid helper without graph: clear failure (no silent hybrid label)
[ ] Sample hits show chunk_id / parent_unit_id / id_str when citation-ready
[ ] Unconstrained profile can re-enable fuller demos on high-RAM host
[ ] Optional: live ~12GB Colab run for SC-001 and SC-002 when hardware available
```

Policy checks (graph mode, gates, labels) can validate locally even when true 12GB Colab session unavailable; RAM-fit SC-001/SC-002 should confirm on Colab-class hardware when possible.
