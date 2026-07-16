# Phase 0 Research: Colab-Safe Full Pipeline Memory Fit

## R1: Primary surface remains the existing full-pipeline notebook

**Decision**: Adapt [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) in place. Do **not** create separate primary Colab product notebook for this feature. Thin companion notebook allowed later only if implementation proves main notebook cannot host both profiles cleanly; not required by spec.

**Rationale**: Spec Assumptions and FR-001/FR-018 treat current hybrid notebook as demonstration surface. Features `001` and `003` already established that notebook as full vector → hybrid → generation path. Duplicating forks config, hybrid helpers, operator docs.

**Alternatives considered**:
- New `notebooks/faiss_retrieval_colab.ipynb` only — rejected as primary deliverable: diverge from hybrid integration already in main notebook, double maintenance.
- Extract full `src/colab/` runtime package — deferred: most behavior is orchestration/policy around existing modules; notebook-local helpers plus optional tiny pure helpers enough for v1.

## R2: Colab-safe vs unconstrained profiles (explicit mode switch)

**Decision**: Introduce explicit notebook profile switch near top config cell:

```text
RUNTIME_PROFILE = "colab_safe" | "unconstrained"
# convenience aliases:
COLAB_SAFE = True/False  # True when RUNTIME_PROFILE == "colab_safe"
```

**Colab-safe defaults** (target ~12GB hosted runtime):
- Prefer portable structural graph pickle over JSONL rebuild.
- Forbid silent full v2 JSONL graph rebuild; rebuild only with explicit opt-in flag.
- Gate heavy optional cells behind opt-in flags (default off under Colab-safe).
- Use conservative retrieval/expansion caps.
- Keep graph-guided pre-filter demo off.
- Keep pure vector path usable when hybrid cannot load.
- Print load plan + best-effort memory diagnostics.

**Unconstrained defaults** (local / high-RAM):
- Preserve today’s fuller demo behavior where practical (optional exports, larger samples, optional JSONL rebuild).
- Still may prefer pickle when present (faster), but may allow JSONL rebuild without Colab warning gate when user opts into rebuild.

**Rationale**: FR-001, FR-007, FR-018, FR-019, SC-003, SC-010. Free Colab is success bar for defaults; higher-RAM machines must not permanently lose full demos.

**Alternatives considered**:
- Auto-detect Colab only via `google.colab` import and hard-force safe mode — rejected as sole control: useful as *suggestion*, but operators must force either profile on any host.
- Environment-variable-only profile — acceptable as override, but notebook-visible flags required for demo transparency (US2).

## R3: Graph load policy — pickle first, never silent JSONL rebuild under Colab-safe

**Decision**: Replace current “if structural JSONL present → `build_graph()`” path with explicit source-mode policy:

| Priority under Colab-safe | Condition | Action |
| --- | --- | --- |
| 1 | `GRAPH_PICKLE_PATH` exists and is readable | `load_knowledge_graph` / `KnowledgeGraphFacade.load_graph` |
| 2 | Pickle missing, JSONL present, `ALLOW_JSONL_GRAPH_REBUILD=False` (default Colab-safe) | Skip hybrid structural load; mark hybrid unavailable; keep vector-only |
| 3 | Pickle missing, JSONL present, `ALLOW_JSONL_GRAPH_REBUILD=True` | Warn that rebuild may exceed 12GB; then `build_graph()` |
| 4 | Neither pickle nor structural JSONL | Hybrid unavailable; vector-only |

Default pickle path: `PROJECT_ROOT / "data" / "graph" / "knowledge_graph.gpickle"` (override for Colab `/content/...` or Drive mounts).

Use existing feature `004` APIs:
- [`src/knowledge_graph/persist.py`](../../src/knowledge_graph/persist.py) — `load_knowledge_graph`
- [`src/knowledge_graph/facade.py`](../../src/knowledge_graph/facade.py) — `load_graph`, `build_graph`

Do **not** auto-fallback from failed/missing pickle request into JSONL rebuild when user asked for pickle load (align with 004 FR-016). Under Colab-safe, even “no pickle, JSONL present” case requires explicit rebuild opt-in.

**Rationale**: FR-003, FR-004, FR-005, SC-002, SC-005, SC-006. Current notebook cell 12 always builds from full v2 JSONL when files exist — primary OOM driver on 12GB.

**Alternatives considered**:
- Always rebuild from JSONL in notebook (status quo) — rejected: does not fit free Colab.
- Require pickle always, remove JSONL path entirely — rejected: unconstrained/local rebuild remains useful when pickle stale or absent (FR-018).
- Lazy seed-driven subgraph load — rejected for this feature: new library contract, not required if pickle load fits.

## R4: Major RAM consumers and what Colab-safe can actually control

**Decision**: Treat following as ordered RAM budget problem; address only policy/staging levers in this feature (not silent embedder swap):

| Component | Observed / expected cost class | Colab-safe control |
| --- | --- | --- |
| FAISS `index.faiss` | On-disk ~6GB class in current artifact listing; process residency depends on FAISS load/mmap behavior | Required for vector path; preflight size; no alternate index by default |
| `payloads.jsonl` | On-disk ~5GB class | Prefer prebuilt `payload_cache.sqlite`; avoid full JSONL materialization; warn before cold cache rebuild |
| `payload_cache.sqlite` | Derived; much safer than loading all payloads into Python lists | Prefer present+fresh cache (existing store behavior) |
| Embedder `intfloat/multilingual-e5-large` | ~2–3GB+ weights/runtime | Keep model identity matching FAISS; fail clearly if load fails; no silent smaller model |
| Structural graph (JSONL rebuild) | Full-corpus parse + in-memory `KnowledgeGraph` — high peak | Prefer pickle load; block default JSONL rebuild under Colab-safe |
| Structural graph (pickle load) | Single-file restore of structural graph | Preferred hybrid path |
| Overlay join | Additional dicts from validity/authority JSONL | Optional; never required for structural hybrid success |
| Optional CSV export / full payload dumps | Can allocate multi-GB temporary tables | Opt-in only under Colab-safe; default skip |
| Benchmark multi-question loops | Repeated retrieve/generate | Opt-in; keep sample small when enabled |
| Remote generation | Negligible local model RAM | Keep remote OpenAI-compatible API assumption |

**Rationale**: Spec Assumptions and Edge Cases. “Fit in 12GB” is for **default Colab-safe path**, not every optional cell combined (SC-001/SC-002 vs Edge Case on full opt-in).

**Alternatives considered**:
- Switch default embedder to smaller model on Colab — rejected by FR-013 unless user supplies matching alternate index.
- Host local LLM in same runtime — out of scope (spec Edge Cases / Assumptions).
- Rebuild FAISS to smaller index inside this feature — out of scope; notebook consumes existing index.

## R5: Load plan / preflight and memory diagnostics

**Decision**: Add notebook **load plan** step before/at major loads that prints:

1. Profile in effect (`colab_safe` / `unconstrained`).
2. Artifact inventory with present/missing + approximate on-disk sizes when available:
   - FAISS: `index.faiss`, `payloads.jsonl`, `id_map.json`, `payload_cache.sqlite`
   - Graph: pickle path; structural JSONL set; overlay JSONL set
3. Planned actions per component: `load` / `defer` / `skip` / `opt_in_required`.
4. Graph source mode: `pickle` | `jsonl_rebuild` | `unavailable`.
5. After major loads, **resident component snapshot**: store, embedder, graph, overlays, export frames.
6. Best-effort memory signals when available:
   - Prefer `psutil` if installed (optional).
   - Fallback: `/proc/self/status` VmRSS on Linux; macOS `resource.getrusage`; Colab `psutil` if present.
   - If none available, print “memory API unavailable” and continue (FR-010).

**Rationale**: US2, FR-009, FR-010, SC-005. Silent full loads are current failure mode.

**Alternatives considered**:
- Require `psutil` as hard dependency — rejected: absence must not block retrieval.
- Only print file existence without sizes/plan — rejected: insufficient to decide whether continue on 12GB.

## R6: Staged execution and cleanup

**Decision**: Document and implement staged cell order under Colab-safe:

```text
Stage A: env + config + profile + load plan
Stage B: FAISS + embedder + vector smoke query
Stage C: structural graph (pickle preferred) + optional overlays + hybrid smoke
Stage D: optional generation
Stage E: opt-in heavy demos (CSV export, cache download, large benchmark, graph-guided, multi-mode stress)
```

Requirements:
- Vector queries must work after Stage B without Stage C (FR-011, US3, US4).
- Hybrid becomes available only after successful Stage C.
- Default “Run all” under Colab-safe must not execute Stage E bodies unless flags true (FR-007, FR-019, SC-003).
- Provide best-effort `release_optional_objects(...)` / cleanup helper that drops references user selects (export frames, comparison tables, optionally `kg_graph` / overlays) and calls `gc.collect()` (FR-012). Not OS hard guarantee.

**Rationale**: Peak simultaneous residency of embedder + FAISS + full graph + large frames is practical OOM pattern even when each piece might fit alone.

**Alternatives considered**:
- Force kernel restart between stages — rejected as default UX; allow optional restart guidance only if user unloads aggressively.
- Auto-unload graph after each hybrid query — rejected: makes demos awkward; not required if caps stay conservative.

## R7: Heavy optional cell gating (current notebook hotspots)

**Decision**: Gate these existing eager or heavy paths behind opt-in flags (defaults **False** under Colab-safe, may remain available under unconstrained):

| Cell / behavior (current) | Flag (planned) | Colab-safe default |
| --- | --- | --- |
| `export_payloads_to_csv()` auto-call (cell ~15) | `RUN_PAYLOAD_CSV_EXPORT` | False |
| `export_payload_cache_sqlite()` auto-call (cell ~17) | `RUN_PAYLOAD_CACHE_EXPORT` | False |
| Multi-profile comparison loops / local expansion demos that re-query repeatedly | Keep small; optional `RUN_FILTER_PROFILE_COMPARISON` if needed | Prefer keep lightweight or skip large loops |
| Hybrid mode comparison + demos | Keep single-query demos; optional large loops off | Single sample OK when hybrid loaded |
| Graph-guided pre-filter demo | `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` (already exists) | False |
| `run_benchmark_sample(...)` | `RUN_BENCHMARK_SAMPLE` | False (definition OK; no auto-run — already mostly commented) |
| Full JSONL graph rebuild | `ALLOW_JSONL_GRAPH_REBUILD` | False |

Implementation pattern: define functions always; execute demo/export bodies only when flag true. “Run all” then safe for default path.

**Rationale**: FR-007, FR-019, SC-003. Inspection shows CSV export and sqlite export currently **call themselves** at end of their cells — top-to-bottom RAM/disk traps on Colab.

**Alternatives considered**:
- Delete optional export cells — rejected: still useful unconstrained (FR-018).
- Move exports to separate notebook — unnecessary if flags gate execution.

## R8: Conservative caps for Colab-safe

**Decision**: Document Colab-safe default caps (configurable):

| Knob | Current notebook | Colab-safe default | Notes |
| --- | --- | --- | --- |
| `TOP_K` | 30 | 20 | Fewer FAISS candidates |
| `TOP_N` | 10 | 5–8 | Smaller seed/result sets |
| `HYBRID_MAX_HOP` | 1 | 1 | Keep single-hop |
| `HYBRID_MAX_CONTEXT` | 12 | 8 | Smaller expansion context |
| `BENCHMARK_SAMPLE_SIZE` | 10 | 3–5 when enabled | Only if opt-in |
| `ENABLE_GRAPH_GUIDED_PREFILTER_DEMO` | False | False | Secondary path |
| `LOCAL_EXPAND_UNITS` / `EXPAND_UNITS` | False | False | Avoid conflating mechanisms; also reduces payload scroll work |

When expansion hits `max_context`, continue reporting `capped=True` (already in hybrid helper) (FR-008).

Unconstrained profile may keep current higher demo-friendly values.

**Rationale**: FR-008 and Edge Case on peak expansion memory. Caps are user-visible controls, not hidden magic.

## R9: Vector-only degradation and hybrid labeling

**Decision**: Preserve and strengthen existing no-silent-fallback contract from feature `003`:

1. Pure vector retrieval remains usable when graph is skipped/unavailable.
2. Results/mode labels:
   - `vector_only` — graph not used
   - `hybrid_expanded` — graph loaded and expansion path used
   - `hybrid_unavailable` / clear error — hybrid requested without graph
3. Success messaging MUST distinguish (FR-023):
   - vector-only Colab-safe success
   - hybrid Colab-safe success with pickle-loaded graph
   - hybrid unavailable due to RAM/policy/artifacts
4. `require_graph_for_hybrid()` remains hard guard for hybrid-labeled paths (`run_hybrid_retrieve`, hybrid `ask()`, graph-guided demo).

**Rationale**: FR-005, FR-006, FR-023, SC-004; Constitution “No silent fallback.”

## R10: Payload cache rebuild policy on Colab

**Decision**: Keep using [`SQLitePayloadFaissVectorStore`](../../src/retrieval/sqlite_faiss_store.py) which rebuilds stale/missing `payload_cache.sqlite` from `payloads.jsonl`. Under Colab-safe:

1. Preflight reports cache present/fresh/missing/stale and sizes.
2. If rebuild will run, print explicit warning that cold rebuild can be costly on Colab (RAM/disk/time).
3. Prefer shipping prebuilt fresh cache in Colab artifact pack (FR-020, Assumptions).
4. Do not invent new store; only improve messaging/gating around existing behavior.

**Rationale**: FR-020 and Edge Cases. Silent multi-GB cache rebuilds are Colab footgun even when FAISS itself loads.

## R11: Where new logic lives

**Decision**:
- **Primary**: notebook orchestration cells in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) (profile flags, load plan, pickle-vs-rebuild graph load, opt-in gates, staged docs, cleanup helper, success labels).
- **Optional extract** (only if helpers grow non-trivial branching worth unit tests): small pure module e.g. `src/retrieval/colab_runtime.py` or `src/utils/runtime_profile.py` for:
  - profile resolution
  - artifact size inventory
  - graph source mode decision
  - memory snapshot helper
- **No new hybrid retrieval algorithm** and no changes to embedding model identity by default.
- **Reuse** 004 pickle load APIs; do not reimplement pickle format.
- **Patch script**: optionally extend [`scripts/_patch_faiss_hybrid_notebook.py`](../../scripts/_patch_faiss_hybrid_notebook.py) or add sibling patcher for idempotent notebook updates — acceptable implementation tactic, not user-facing product surface.
- **Tests**: no mandatory new unit-test package if logic stays notebook-local; if pure helpers extracted, add focused unit tests. Validation primarily quickstart scenarios on constrained RAM (or simulated policy checks).

**Rationale**: Matches 003’s “thin orchestration over existing modules” and Constitution V (modular/testable when logic is real). Feature is mostly policy and packaging.

**Alternatives considered**:
- Large new `src/hybrid_runtime/` package — rejected as overscoped for notebook policy.
- Change FAISS store to always mmap / change embedder internals — out of scope unless tiny safe improvement obviously necessary during implement; prefer policy first.

## R12: Operator artifact packs (documentation contract)

**Decision**: Document two minimal packs:

### Vector-only Colab-safe pack
- Project code (`src/` importable)
- `data/faiss_index/index.faiss`
- `data/faiss_index/payloads.jsonl` (or ensure cache can be built offline beforehand)
- Prefer also: `data/faiss_index/payload_cache.sqlite` (fresh)
- Optional: `id_map.json`

### Hybrid Colab-safe pack
- Everything in vector-only pack, plus:
- `data/graph/knowledge_graph.gpickle` (built locally via `scripts/build_kg_pickle.py`)
- Optional overlays: `validity_timeline.jsonl`, `authority_index.jsonl`
- Do **not** require full structural v2 JSONL on Colab when pickle is present

### Avoid on 12GB by default
- Full structural JSONL rebuild in-notebook
- Full payload CSV export (`limit=None`)
- Large benchmark samples with generation
- Enabling every optional demo simultaneously
- Local in-process LLM

**Rationale**: US5, FR-017, SC-008. RAM fit is packaging + policy.

## R13: Contracts directory and agent context

**Decision**:
- No `contracts/` HTTP/API directory — in-process notebook/profile contracts only, documented in data-model + quickstart.
- After planning artifacts written, update agent context only if project’s Speckit setup provides update script; otherwise report generated files and stop after Phase 1 (per workflow).

**Rationale**: Same as 003/004 for non-service features.

## Research outcome

All Phase 0 questions resolved for planning:

| Topic | Resolution |
| --- | --- |
| Target surface | Existing `faiss_retrieval_ready.ipynb` |
| Profile model | `colab_safe` vs `unconstrained` |
| Graph load | Pickle preferred; JSONL rebuild opt-in under Colab-safe |
| Heavy cells | Opt-in flags; no eager export/benchmark under Colab-safe Run-all |
| Caps | Conservative TOP_K/TOP_N/max_context defaults for Colab-safe |
| Diagnostics | Load plan + best-effort memory signals |
| Staging | Vector → graph → generate → opt-in heavy demos |
| Degradation | Vector-only labeled; hybrid never silent |
| Embedder | No silent model swap |
| New libraries | Prefer notebook-local; optional tiny pure helper module |
| Artifact packs | Documented vector-only vs hybrid Colab packs |

No remaining NEEDS CLARIFICATION blockers for Phase 1 design.
