#!/usr/bin/env python3
"""Idempotent Colab-safe patcher for notebooks/faiss_retrieval_ready.ipynb (feature 005).

Applies RUNTIME_PROFILE / load-plan / pickle-prefer graph load / heavy-cell gates /
staging docs / cleanup helper / success labels. Reuses 003 hybrid helpers where intact.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "faiss_retrieval_ready.ipynb"
MARKER = "COLAB_SAFE_RAM_FIT"
HYBRID_MARKER = "HYBRID_GRAPH_INTEGRATION"


def _id() -> str:
    return uuid.uuid4().hex[:8]


def cell_text(cell: dict) -> str:
    return "".join(cell.get("source", []))


def set_source(cell: dict, source: str) -> None:
    text = source if source.endswith("\n") else source + "\n"
    lines = text.split("\n")
    src_lines = []
    for i, line in enumerate(lines):
        if i == len(lines) - 1 and line == "":
            break
        src_lines.append(line + "\n")
    cell["source"] = src_lines
    if cell.get("cell_type") == "code":
        cell["outputs"] = []
        cell["execution_count"] = None


def md(source: str) -> dict:
    text = source if source.endswith("\n") else source + "\n"
    lines = text.split("\n")
    src_lines = []
    for i, line in enumerate(lines):
        if i == len(lines) - 1 and line == "":
            break
        src_lines.append(line + "\n")
    return {
        "cell_type": "markdown",
        "id": _id(),
        "metadata": {"tags": [MARKER]},
        "source": src_lines,
    }


def code(source: str) -> dict:
    text = source if source.endswith("\n") else source + "\n"
    lines = text.split("\n")
    src_lines = []
    for i, line in enumerate(lines):
        if i == len(lines) - 1 and line == "":
            break
        src_lines.append(line + "\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": _id(),
        "metadata": {"tags": [MARKER]},
        "outputs": [],
        "source": src_lines,
    }


def is_marker_cell(cell: dict, marker: str = MARKER) -> bool:
    tags = cell.get("metadata", {}).get("tags") or []
    if marker in tags:
        return True
    return marker in cell_text(cell)


INTRO = """# FAISS Vector Retrieval + Hybrid Graph Notebook (Colab-safe ready)

This notebook runs retrieval after `index.faiss` and `payloads.jsonl` are available, and (when a structural graph is loadable) demonstrates the **primary hybrid pipeline**:

```text
query → embed → vector seed retrieval → graph expansion + validity/authority overlays → optional LLM generation
```

## Runtime profiles (feature 005)

| Profile | Target | Defaults |
| --- | --- | --- |
| **`colab_safe`** (default) | ~12GB hosted notebook (free Colab) | Prefer graph **pickle**; no silent JSONL rebuild; heavy exports/benchmarks **off**; conservative `TOP_K`/`TOP_N`/`HYBRID_MAX_CONTEXT` |
| **`unconstrained`** | Local / high-RAM | Fuller demos; optional JSONL rebuild; optional CSV/cache export |

Set near the config cell:

```python
RUNTIME_PROFILE = "colab_safe"   # or "unconstrained"
```

## Staged run order (Colab-safe)

```text
Stage A  config + profile + load plan / preflight
Stage B  FAISS + embedder + vector smoke query
Stage C  structural graph (pickle preferred) + optional overlays + hybrid smoke
Stage D  optional remote generation
Stage E  opt-in heavy demos only (CSV export, cache export, large benchmark, graph-guided)
```

Rules:
1. After **Stage B**, pure vector queries work **without** loading the graph.
2. Hybrid-labeled helpers work only after successful **Stage C**.
3. Default Colab-safe **Run all** does **not** execute Stage E bodies unless opt-in flags are true.
4. Hybrid is **never** silently labeled when only vector retrieval ran.

## Artifact packs

**Vector-only Colab pack:** `data/faiss_index/{index.faiss,payloads.jsonl,payload_cache.sqlite?}`

**Hybrid Colab pack:** vector pack + `data/graph/knowledge_graph.gpickle` (build locally via `scripts/build_kg_pickle.py`). Overlays optional. Full structural v2 JSONL **not** required on Colab when pickle is present.

Operator guide: [`specs/005-colab-ram-fit/quickstart.md`](../specs/005-colab-ram-fit/quickstart.md)

**Architecture**
- Store: [`SQLitePayloadFaissVectorStore`](../src/retrieval/sqlite_faiss_store.py) — FAISS + rebuild-if-stale `payload_cache.sqlite`
- Retrieval: [`VectorRetriever`](../src/retrieval/retriever.py)
- Knowledge graph: [`KnowledgeGraphFacade`](../src/knowledge_graph/facade.py), pickle load ([`load_knowledge_graph`](../src/knowledge_graph/persist.py)), [`GraphExpansion`](../src/knowledge_graph/expansion.py)
- Colab helpers: [`retrieval.colab_runtime`](../src/retrieval/colab_runtime.py)
- Generation: remote OpenAI-compatible API only for Colab-safe RAM guarantees

**Primary vs secondary graph paths**
- **Primary:** vector-first hybrid expansion
- **Secondary (off under Colab-safe):** graph-guided pre-filter

Pure vector profiles remain usable if the graph is missing. Hybrid mode fails clearly when the graph is unavailable rather than silently falling back under a hybrid label.

**Note:** Demonstration notebook — not a replacement for [`scripts/verify_kg.py`](../scripts/verify_kg.py) or [`scripts/evaluate_e2e.py`](../scripts/evaluate_e2e.py).
"""

CONFIG = '''# === Stage A: paths + runtime profile (005-colab-ram-fit) ===
# Directory containing index.faiss + payloads.jsonl (+ optional id_map.json)
INDEX_DIR = PROJECT_ROOT / 'data' / 'faiss_index'

# Graph sources
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'
GRAPH_PICKLE_PATH = PROJECT_ROOT / 'data' / 'graph' / 'knowledge_graph.gpickle'

# Runtime profile: "colab_safe" (~12GB) | "unconstrained" (local/high-RAM)
RUNTIME_PROFILE = 'colab_safe'

# Must match the embedding model used to build index.faiss.
# Alias EMBEDDING_MODEL_NAME kept for plan/quickstart naming parity.
EMBEDDING_MODEL = 'intfloat/multilingual-e5-large'
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL

# Embedder device only (query encoding). FAISS search stays on CPU (faiss-cpu).
# 'auto' = cuda if available else cpu; or force 'cuda' / 'cpu' / 'mps'.
EMBEDDER_DEVICE = 'auto'

# --- Profile resolution (conservative caps under colab_safe) ---
from retrieval.colab_runtime import (
    CleanupRequest,
    ResidentComponentSnapshot,
    apply_cleanup,
    build_load_plan,
    capture_memory_snapshot,
    decide_graph_source_mode,
    format_load_plan,
    format_resident_snapshot,
    format_session_outcome,
    payload_cache_rebuild_warning,
    resolve_runtime_profile,
    session_outcome_label,
)

# Optional explicit overrides (None → profile defaults)
_ALLOW_JSONL_GRAPH_REBUILD = False  # Colab-safe default; set True only after RAM warning
_RUN_PAYLOAD_CSV_EXPORT = None      # None → False under colab_safe, True under unconstrained
_RUN_PAYLOAD_CACHE_EXPORT = None
_RUN_BENCHMARK_SAMPLE = False
_RUN_FILTER_PROFILE_COMPARISON = None
_ENABLE_GRAPH_GUIDED_PREFILTER_DEMO = False

runtime_profile = resolve_runtime_profile(
    RUNTIME_PROFILE,
    project_root=PROJECT_ROOT,
    graph_pickle_path=GRAPH_PICKLE_PATH,
    v2_data_dir=V2_DATA_DIR,
    embedding_model=EMBEDDING_MODEL,
    allow_jsonl_graph_rebuild=_ALLOW_JSONL_GRAPH_REBUILD,
    enable_graph_guided_prefilter_demo=_ENABLE_GRAPH_GUIDED_PREFILTER_DEMO,
    run_payload_csv_export=_RUN_PAYLOAD_CSV_EXPORT,
    run_payload_cache_export=_RUN_PAYLOAD_CACHE_EXPORT,
    run_benchmark_sample=_RUN_BENCHMARK_SAMPLE,
    run_filter_profile_comparison=_RUN_FILTER_PROFILE_COMPARISON,
)

COLAB_SAFE = runtime_profile.colab_safe
ALLOW_JSONL_GRAPH_REBUILD = runtime_profile.allow_jsonl_graph_rebuild
TOP_K = runtime_profile.top_k
TOP_N = runtime_profile.top_n
SCORE_THRESHOLD = runtime_profile.score_threshold
HYBRID_MAX_HOP = runtime_profile.hybrid_max_hop
HYBRID_MAX_CONTEXT = runtime_profile.hybrid_max_context
EXPAND_UNITS = runtime_profile.local_expand_units
LOCAL_EXPAND_UNITS = EXPAND_UNITS
DEFAULT_FILTER_PROFILE = 'broad'  # current_law | broad | historical (non-graph)
FILTER_PROFILE = DEFAULT_FILTER_PROFILE
BENCHMARK_SAMPLE_SIZE = runtime_profile.benchmark_sample_size

# Hybrid graph settings
ENABLE_HYBRID_EXPANSION = runtime_profile.enable_hybrid_expansion
AS_OF_DATE = '2026-07-13'
USE_HYBRID_EVIDENCE_FOR_GENERATION = runtime_profile.use_hybrid_evidence_for_generation
ENABLE_GRAPH_GUIDED_PREFILTER_DEMO = runtime_profile.enable_graph_guided_prefilter_demo
GRAPH_GUIDED_START_ID = ''  # optional document id_str; empty → take from first seed hit
GRAPH_GUIDED_TRAVERSAL_MODE = 'basis'
GRAPH_GUIDED_MAX_DEPTH = 2

# Heavy optional Stage E gates (default False under colab_safe)
RUN_PAYLOAD_CSV_EXPORT = runtime_profile.run_payload_csv_export
RUN_PAYLOAD_CACHE_EXPORT = runtime_profile.run_payload_cache_export
RUN_BENCHMARK_SAMPLE = runtime_profile.run_benchmark_sample
RUN_FILTER_PROFILE_COMPARISON = runtime_profile.run_filter_profile_comparison
PAYLOAD_CSV_EXPORT_LIMIT = runtime_profile.payload_csv_export_limit

print('RUNTIME_PROFILE:', RUNTIME_PROFILE, '| COLAB_SAFE:', COLAB_SAFE)
print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('GRAPH_PICKLE_PATH:', GRAPH_PICKLE_PATH)
print('ALLOW_JSONL_GRAPH_REBUILD:', ALLOW_JSONL_GRAPH_REBUILD)
print('TOP_K/TOP_N/HYBRID_MAX_CONTEXT:', TOP_K, TOP_N, HYBRID_MAX_CONTEXT)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
print(
    'Heavy gates CSV/CACHE/BENCH/FILTER:',
    RUN_PAYLOAD_CSV_EXPORT,
    RUN_PAYLOAD_CACHE_EXPORT,
    RUN_BENCHMARK_SAMPLE,
    RUN_FILTER_PROFILE_COMPARISON,
)
INDEX_DIR
'''

PREFLIGHT_LOAD_PLAN = '''# ### COLAB_SAFE_RAM_FIT — Stage A load plan + memory preflight
phase_t0 = time.perf_counter()
required_files = [INDEX_DIR / 'index.faiss', INDEX_DIR / 'payloads.jsonl']
optional_files = [INDEX_DIR / 'id_map.json', INDEX_DIR / 'payload_cache.sqlite']

missing = [p for p in required_files if not p.exists()]
if missing:
    print('Downloads are not ready yet. Missing:')
    for p in missing:
        print(' -', p)
else:
    print('Required FAISS files found.')
    for p in required_files + optional_files:
        if p.exists():
            print(f'{p.name}: {p.stat().st_size / 1024 / 1024:.2f} MB')
        else:
            print(f'{p.name}: MISSING')

mem_preflight = capture_memory_snapshot(note='preflight')
load_plan = build_load_plan(runtime_profile, index_dir=INDEX_DIR, memory_before=mem_preflight)
print(format_load_plan(load_plan))
print(f'Preflight cell finished in {time.perf_counter() - phase_t0:.2f}s')
'''

VECTOR_LOAD = '''# === Stage B: load FAISS store + embedder + vector retriever ===
if missing:
    raise FileNotFoundError('Download index.faiss and payloads.jsonl before running this cell.')

from retrieval.config import VectorIndexConfig
from retrieval.embeddings import SentenceTransformerEmbedder
from retrieval.retriever import VectorRetriever
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore

# FR-020: warn before costly cold payload cache rebuild on Colab
_cache_warn = payload_cache_rebuild_warning(INDEX_DIR)
if _cache_warn:
    print(_cache_warn)

load_t0 = time.perf_counter()
mem_before_vector = capture_memory_snapshot(note='before_vector_load')
print(mem_before_vector.format_line())

config = VectorIndexConfig(
    embedding_model=EMBEDDING_MODEL,
    top_k=TOP_K,
    top_n=TOP_N,
    score_threshold=SCORE_THRESHOLD,
    expand_units=EXPAND_UNITS,
)

store = SQLitePayloadFaissVectorStore.load(INDEX_DIR)

# Resolve embedder device (GPU for model weights/encoding only; FAISS remains CPU).
_requested_device = str(globals().get('EMBEDDER_DEVICE', 'auto')).strip().lower()
if _requested_device in ('', 'auto'):
    _resolved_device = 'cpu'
    try:
        import torch
        if torch.cuda.is_available():
            _resolved_device = 'cuda'
        elif getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
            _resolved_device = 'mps'
    except Exception:
        _resolved_device = 'cpu'
else:
    _resolved_device = _requested_device

if _resolved_device == 'cuda':
    try:
        import torch
        if not torch.cuda.is_available():
            print('EMBEDDER_DEVICE=cuda requested but CUDA unavailable; falling back to cpu')
            _resolved_device = 'cpu'
    except Exception as exc:
        print(f'CUDA check failed ({exc}); falling back to cpu')
        _resolved_device = 'cpu'

embedder = SentenceTransformerEmbedder(
    EMBEDDING_MODEL,
    query_prefix=config.query_prefix,
    passage_prefix=config.passage_prefix,
    device=_resolved_device,
)
retriever = VectorRetriever(config=config, embedder=embedder, store=store)

print(f'Vector retriever ready in {time.perf_counter() - load_t0:.2f}s')
print(f'Loaded FAISS vectors: {store.total_vectors:,}')
print(f'Embedding dimension: {embedder.dimension}')
print(f'Embedder device: {_resolved_device} (requested={_requested_device})')
print('FAISS backend: CPU (faiss-cpu / Index search on host RAM)')
print('Store class:', type(store).__module__ + '.' + type(store).__name__)
print('CPU-only path valid for Colab-safe success (FR-022); GPU optional for embedder only.')
if _resolved_device == 'cuda':
    try:
        import torch
        print(f'CUDA device: {torch.cuda.get_device_name(0)}')
    except Exception:
        pass

# Vector-only retriever (graph_expansion=None). Hybrid retriever is wired after graph load.
hybrid_retriever = None
graph_expansion = None

mem_after_vector = capture_memory_snapshot(note='after_vector_load')
print(mem_after_vector.format_line())
print(
    format_resident_snapshot(
        ResidentComponentSnapshot(
            store_loaded=store is not None,
            embedder_loaded=embedder is not None,
            structural_graph_loaded=False,
            graph_source_mode=None,
            overlays_loaded=False,
            hybrid_retriever_ready=False,
            generator_configured=False,
            optional_frames_held=[],
        )
    )
)
print('Stage B complete: pure vector queries are usable without Stage C graph load.')
print(
    format_session_outcome(
        session_outcome_label(
            colab_safe=COLAB_SAFE,
            structural_ready=False,
            loaded_from_pickle=False,
            hybrid_used=False,
            vector_ok=True,
        )
    )
)
'''

HYBRID_IMPORTS = '''# ### HYBRID_GRAPH_INTEGRATION — intended import surface (FR-002)
# ### COLAB_SAFE_RAM_FIT — pickle load surface (004)
from dataclasses import dataclass, field
from typing import Any, Literal

from knowledge_graph import (
    GraphExpansion,
    GraphLoaderPaths,
    KnowledgeGraphFacade,
    QueryConstraints,
    load_knowledge_graph,
    parse_authority_index_rows,
    parse_validity_event_rows,
)
from knowledge_graph.context_schema import GraphGuidedFilter
from knowledge_graph.expansion_schema import ExpansionResult
from knowledge_graph.overlay import OverlayBundle
from knowledge_graph.overlay_schema import DocumentOverlay
from knowledge_graph.persist import GraphPickleLoadResult
from retrieval.io_utils import read_jsonl
from retrieval.schema import RetrievedChunk, RetrievalResult
from retrieval.stores import SearchHit

print('Hybrid import surface ready: KnowledgeGraphFacade, load_knowledge_graph, GraphExpansion, overlays')
'''

HYBRID_PREFLIGHT_BUILD = '''# ### HYBRID_GRAPH_INTEGRATION — preflight, pickle-prefer load, overlays, expansion wire, guard
# ### COLAB_SAFE_RAM_FIT — Stage C graph load policy (FR-003/FR-004)


@dataclass
class GraphLoadStatus:
    structural_ready: bool = False
    overlays_ready: bool = False
    missing_structural_files: list[str] = field(default_factory=list)
    missing_overlay_files: list[str] = field(default_factory=list)
    build_stats: Any = None
    build_warnings: tuple[str, ...] = ()
    as_of_date: str | None = None
    overlay_coverage: dict[str, int] | None = None
    error: str | None = None
    build_duration_s: float | None = None
    # 005 extensions
    graph_source_mode: Literal['pickle', 'jsonl_rebuild', 'unavailable'] = 'unavailable'
    pickle_path: str | None = None
    loaded_from_pickle: bool = False
    rebuild_opt_in_required: bool = False
    rebuild_warning_emitted: bool = False


def preflight_graph_sources(
    v2_dir: Path,
    *,
    pickle_path: Path | None = None,
    colab_safe: bool = True,
    allow_jsonl_rebuild: bool = False,
) -> GraphLoadStatus:
    """Inventory structural/overlay files + decide graph source mode (FR-003/FR-004)."""
    paths = GraphLoaderPaths(data_dir=v2_dir)
    missing_structural = [str(p) for p in paths.required_paths() if not p.exists()]
    overlay_names = ('validity_timeline.jsonl', 'authority_index.jsonl')
    missing_overlay = [str(v2_dir / name) for name in overlay_names if not (v2_dir / name).exists()]

    decision = decide_graph_source_mode(
        pickle_path=pickle_path or GRAPH_PICKLE_PATH,
        v2_data_dir=v2_dir,
        colab_safe=colab_safe,
        allow_jsonl_graph_rebuild=allow_jsonl_rebuild,
        prefer_graph_pickle=True,
    )

    status = GraphLoadStatus(
        structural_ready=False,  # set True only after successful load
        overlays_ready=not missing_overlay,
        missing_structural_files=missing_structural,
        missing_overlay_files=missing_overlay,
        graph_source_mode=decision.mode,
        pickle_path=str(decision.pickle_path) if decision.pickle_path else None,
        loaded_from_pickle=False,
        rebuild_opt_in_required=decision.rebuild_opt_in_required,
        rebuild_warning_emitted=bool(decision.rebuild_warning),
    )

    print('=== Graph preflight (Colab-safe policy) ===')
    print('V2_DATA_DIR:', v2_dir)
    print('GRAPH_PICKLE_PATH:', pickle_path or GRAPH_PICKLE_PATH)
    print('graph_source_mode:', decision.mode)
    print('pickle present:', decision.pickle_present)
    print('jsonl structural ready:', decision.jsonl_structural_ready)
    print('rebuild_opt_in_required:', decision.rebuild_opt_in_required)
    if decision.rebuild_warning:
        print('WARNING:', decision.rebuild_warning)
        status.rebuild_warning_emitted = True

    print('Structural JSONL files:')
    for p in paths.required_paths():
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')
    print('Overlay files (optional):')
    for name in overlay_names:
        p = v2_dir / name
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')

    if decision.mode == 'unavailable':
        print('Structural graph UNAVAILABLE under current policy. Pure vector profiles remain usable.')
        print('Detail:', decision.detail)
        if decision.missing_structural_jsonl:
            print('Missing structural JSONL:')
            for m in decision.missing_structural_jsonl:
                print(' -', m)
    if missing_overlay:
        print('Overlays unavailable (currency/authority labeled unavailable if structural graph loads).')
        for m in missing_overlay:
            print(' -', m)
    return status


graph_load_status = preflight_graph_sources(
    V2_DATA_DIR,
    pickle_path=GRAPH_PICKLE_PATH,
    colab_safe=COLAB_SAFE,
    allow_jsonl_rebuild=ALLOW_JSONL_GRAPH_REBUILD,
)
kg_facade: KnowledgeGraphFacade | None = None
kg_graph = None
kg_build_result = None
kg_pickle_result: GraphPickleLoadResult | None = None
overlay_bundle: OverlayBundle | None = None
graph_expansion: GraphExpansion | None = None
hybrid_retriever: VectorRetriever | None = None
document_overlays: dict[str, DocumentOverlay] = {}

mem_before_graph = capture_memory_snapshot(note='before_graph_load')
print(mem_before_graph.format_line())

if graph_load_status.graph_source_mode == 'pickle':
    try:
        print('\\n=== Graph load (portable pickle preferred) ===')
        kg_paths = GraphLoaderPaths(data_dir=V2_DATA_DIR)
        kg_facade = KnowledgeGraphFacade(paths=kg_paths)
        build_t0 = time.perf_counter()
        kg_pickle_result = load_knowledge_graph(GRAPH_PICKLE_PATH)
        duration = time.perf_counter() - build_t0
        kg_graph = kg_pickle_result.graph
        stats = kg_pickle_result.stats
        graph_load_status.build_stats = stats
        graph_load_status.build_warnings = tuple(kg_pickle_result.warnings or ())
        graph_load_status.build_duration_s = duration
        graph_load_status.structural_ready = True
        graph_load_status.loaded_from_pickle = True
        graph_load_status.graph_source_mode = 'pickle'
        graph_load_status.pickle_path = str(GRAPH_PICKLE_PATH)
        print(f'Knowledge graph loaded from pickle in {duration:.2f}s')
        print('format_version:', kg_pickle_result.format_version)
        if stats is not None:
            print('[Pickle / build statistics]')
            for attr in (
                'document_count',
                'external_stub_count',
                'provision_count',
                'chunk_count',
                'document_edge_count',
                'verified_document_edge_count',
                'unverified_document_edge_count',
                'structural_edge_count',
                'orphan_provision_count',
                'orphan_chunk_count',
            ):
                if hasattr(stats, attr):
                    print(f'  {attr}: {getattr(stats, attr):,}')
                elif isinstance(stats, dict) and attr in stats:
                    print(f'  {attr}: {stats[attr]:,}')
        if kg_pickle_result.warnings:
            print('Load warnings:')
            for w in list(kg_pickle_result.warnings)[:20]:
                print(' -', w)

        # Overlays (optional — never required for structural hybrid success)
        if not graph_load_status.missing_overlay_files:
            print('\\n=== Overlay join ===')
            validity_path = V2_DATA_DIR / 'validity_timeline.jsonl'
            authority_path = V2_DATA_DIR / 'authority_index.jsonl'
            validity_events = list(parse_validity_event_rows(read_jsonl(validity_path)))
            authority_entries = list(parse_authority_index_rows(read_jsonl(authority_path)))
            overlay_bundle = kg_facade.build_overlay_bundle(
                documents=kg_graph.documents.values(),
                validity_events=validity_events,
                authority_entries=authority_entries,
                as_of_date=AS_OF_DATE,
            )
            document_overlays = dict(overlay_bundle.document_overlays)
            graph_load_status.overlays_ready = True
            graph_load_status.as_of_date = AS_OF_DATE
            currency_hist: dict[str, int] = {}
            for ov in document_overlays.values():
                currency_hist[ov.currency_status] = currency_hist.get(ov.currency_status, 0) + 1
            graph_load_status.overlay_coverage = currency_hist
            print(f'Overlays joined for {len(document_overlays):,} documents (as_of={AS_OF_DATE})')
            print('currency_status histogram:', currency_hist)
        else:
            graph_load_status.overlays_ready = False
            print('Overlays MISSING — structural expansion allowed; currency/authority labeled unavailable.')

        graph_expansion = GraphExpansion(kg_graph)
        hybrid_retriever = VectorRetriever(
            config=config,
            embedder=embedder,
            store=store,
            graph_expansion=graph_expansion,
        )
        print('\\nGraphExpansion wired. hybrid_retriever has graph_expansion; vector-only retriever remains graph_expansion=None.')
        print('Label reminder: graph_expansion ≠ local_expand_units')
    except Exception as exc:
        graph_load_status.structural_ready = False
        graph_load_status.loaded_from_pickle = False
        graph_load_status.graph_source_mode = 'unavailable'
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph pickle load FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')

elif graph_load_status.graph_source_mode == 'jsonl_rebuild':
    try:
        print('\\n=== Graph build (JSONL rebuild — opt-in / unconstrained) ===')
        if COLAB_SAFE:
            print(
                'WARNING: Full structural JSONL rebuild may exceed ~12GB RAM. '
                'ALLOW_JSONL_GRAPH_REBUILD=True acknowledged.'
            )
            graph_load_status.rebuild_warning_emitted = True
        kg_paths = GraphLoaderPaths(data_dir=V2_DATA_DIR)
        kg_facade = KnowledgeGraphFacade(paths=kg_paths)
        build_t0 = time.perf_counter()
        kg_build_result = kg_facade.build_graph()
        duration = time.perf_counter() - build_t0
        kg_graph = kg_build_result.graph
        stats = kg_build_result.stats
        graph_load_status.build_stats = stats
        graph_load_status.build_warnings = tuple(kg_build_result.warnings or ())
        graph_load_status.build_duration_s = duration
        graph_load_status.structural_ready = True
        graph_load_status.loaded_from_pickle = False
        graph_load_status.graph_source_mode = 'jsonl_rebuild'
        print(f'Knowledge graph built from JSONL in {duration:.2f}s')
        print('[Build Statistics]')
        print(f'  documents:           {stats.document_count:,}')
        print(f'  external_stubs:      {stats.external_stub_count:,}')
        print(f'  provisions:          {stats.provision_count:,}')
        print(f'  chunks:              {stats.chunk_count:,}')
        print(f'  document_edges:      {stats.document_edge_count:,}')
        print(f'  verified_edges:      {stats.verified_document_edge_count:,}')
        print(f'  unverified_edges:    {stats.unverified_document_edge_count:,}')
        print(f'  structural_edges:    {stats.structural_edge_count:,}')
        print(f'  orphan_provisions:   {stats.orphan_provision_count}')
        print(f'  orphan_chunks:       {stats.orphan_chunk_count}')
        if kg_build_result.warnings:
            print('Build warnings:')
            for w in kg_build_result.warnings[:20]:
                print(' -', w)

        if not graph_load_status.missing_overlay_files:
            print('\\n=== Overlay join ===')
            validity_path = V2_DATA_DIR / 'validity_timeline.jsonl'
            authority_path = V2_DATA_DIR / 'authority_index.jsonl'
            validity_events = list(parse_validity_event_rows(read_jsonl(validity_path)))
            authority_entries = list(parse_authority_index_rows(read_jsonl(authority_path)))
            overlay_bundle = kg_facade.build_overlay_bundle(
                documents=kg_graph.documents.values(),
                validity_events=validity_events,
                authority_entries=authority_entries,
                as_of_date=AS_OF_DATE,
            )
            document_overlays = dict(overlay_bundle.document_overlays)
            graph_load_status.overlays_ready = True
            graph_load_status.as_of_date = AS_OF_DATE
            currency_hist = {}
            for ov in document_overlays.values():
                currency_hist[ov.currency_status] = currency_hist.get(ov.currency_status, 0) + 1
            graph_load_status.overlay_coverage = currency_hist
            print(f'Overlays joined for {len(document_overlays):,} documents (as_of={AS_OF_DATE})')
            print('currency_status histogram:', currency_hist)
        else:
            graph_load_status.overlays_ready = False
            print('Overlays MISSING — structural expansion allowed; currency/authority labeled unavailable.')

        graph_expansion = GraphExpansion(kg_graph)
        hybrid_retriever = VectorRetriever(
            config=config,
            embedder=embedder,
            store=store,
            graph_expansion=graph_expansion,
        )
        print('\\nGraphExpansion wired after JSONL rebuild.')
    except Exception as exc:
        graph_load_status.structural_ready = False
        graph_load_status.loaded_from_pickle = False
        graph_load_status.graph_source_mode = 'unavailable'
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph JSONL rebuild FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
else:
    print('Skipping graph load (pickle missing and/or JSONL rebuild not permitted under Colab-safe).')
    print('Hybrid labeled path unavailable; pure vector retrieval remains usable.')
    if graph_load_status.rebuild_opt_in_required:
        print('To rebuild from JSONL: set ALLOW_JSONL_GRAPH_REBUILD=True (may exceed 12GB) and re-run this cell.')


def require_graph_for_hybrid(action: str = 'hybrid expansion') -> None:
    """Fail clearly if hybrid is requested without a loaded graph (FR-006 / no silent fallback)."""
    if not graph_load_status.structural_ready or kg_graph is None or graph_expansion is None:
        missing = graph_load_status.missing_structural_files or ['(structural graph not loaded)']
        detail = graph_load_status.error or graph_load_status.graph_source_mode or '; '.join(missing)
        raise RuntimeError(
            f"Cannot run {action}: knowledge graph unavailable (hybrid_unavailable). "
            f"Do not silently fall back to vector-only under a hybrid label. "
            f"graph_source_mode={graph_load_status.graph_source_mode}. Detail: {detail}"
        )


mem_after_graph = capture_memory_snapshot(note='after_graph_load')
print(mem_after_graph.format_line())
print('\\nGraphLoadStatus:')
print('  structural_ready:', graph_load_status.structural_ready)
print('  overlays_ready:', graph_load_status.overlays_ready)
print('  graph_source_mode:', graph_load_status.graph_source_mode)
print('  loaded_from_pickle:', graph_load_status.loaded_from_pickle)
print('  pickle_path:', graph_load_status.pickle_path)
print('  rebuild_opt_in_required:', graph_load_status.rebuild_opt_in_required)
print('  error:', graph_load_status.error)
print(
    format_resident_snapshot(
        ResidentComponentSnapshot(
            store_loaded='store' in globals() and store is not None,
            embedder_loaded='embedder' in globals() and embedder is not None,
            structural_graph_loaded=bool(graph_load_status.structural_ready and kg_graph is not None),
            graph_source_mode=graph_load_status.graph_source_mode,
            overlays_loaded=bool(graph_load_status.overlays_ready),
            hybrid_retriever_ready=hybrid_retriever is not None,
            generator_configured=bool(globals().get('generator')),
            optional_frames_held=[],
        )
    )
)
if graph_load_status.structural_ready and graph_load_status.loaded_from_pickle:
    print(
        format_session_outcome(
            'hybrid_colab_safe_success_pickle'
            if COLAB_SAFE
            else 'unconstrained_success',
            detail='Graph loaded; run hybrid smoke/demo next.',
        )
    )
elif not graph_load_status.structural_ready:
    print(format_session_outcome('hybrid_unavailable', detail='Vector-only remains usable.'))
'''

HYBRID_MD = """## 4.3 Hybrid graph integration (vector-first) — Stage C

Primary hybrid path (default full pipeline when graph loads):

```text
query → embed → vector seed retrieve → resolve chunk→provision→document
      → GraphExpansion + validity/authority overlays → fused evidence → optional LLM
```

**Colab-safe graph source policy**
1. Prefer `data/graph/knowledge_graph.gpickle` via `load_knowledge_graph`
2. JSONL rebuild only if `ALLOW_JSONL_GRAPH_REBUILD=True` (warns under Colab-safe)
3. Else hybrid unavailable; pure vector remains usable

Secondary path (optional only, **off** under Colab-safe): graph-guided pre-filter whitelist before vector search.

This section orchestrates existing modules under `src/knowledge_graph/` and `src/retrieval/` — it does **not** reimplement graph logic.
"""

CLEANUP_CELL = '''# ### COLAB_SAFE_RAM_FIT — best-effort cleanup / release helper (FR-012)


def release_optional_objects(
    *,
    drop_export_frames: bool = True,
    drop_comparison_records: bool = True,
    unload_overlays: bool = False,
    unload_structural_graph: bool = False,
    run_gc: bool = True,
) -> list[str]:
    """Drop optional heavy notebook objects. Not an OS memory reservation.

    If unload_structural_graph=True, hybrid becomes unavailable until Stage C reloads.
    """
    req = CleanupRequest(
        drop_export_frames=drop_export_frames,
        drop_comparison_records=drop_comparison_records,
        unload_overlays=unload_overlays,
        unload_structural_graph=unload_structural_graph,
        run_gc=run_gc,
    )
    actions = apply_cleanup(globals(), req)
    print('Cleanup actions:')
    for a in actions:
        print(' -', a)
    print(
        format_resident_snapshot(
            ResidentComponentSnapshot(
                store_loaded='store' in globals() and store is not None,
                embedder_loaded='embedder' in globals() and embedder is not None,
                structural_graph_loaded=bool(
                    globals().get('graph_load_status')
                    and graph_load_status.structural_ready
                    and globals().get('kg_graph') is not None
                ),
                graph_source_mode=getattr(globals().get('graph_load_status'), 'graph_source_mode', None),
                overlays_loaded=bool(getattr(globals().get('graph_load_status'), 'overlays_ready', False)),
                hybrid_retriever_ready=globals().get('hybrid_retriever') is not None,
                generator_configured=bool(globals().get('generator')),
                optional_frames_held=[],
            )
        )
    )
    return actions


print('release_optional_objects() defined. Example:')
print('  release_optional_objects()  # drop export/comparison frames + gc')
print('  release_optional_objects(unload_structural_graph=True)  # hybrid unavailable until reload')
'''


def _patch_export_csv(text: str) -> str:
    if "RUN_PAYLOAD_CSV_EXPORT" in text and "if RUN_PAYLOAD_CSV_EXPORT" in text:
        return text
    # Replace bare auto-call
    text = re.sub(
        r"\nexport_payloads_to_csv\(\)\s*\n?",
        "\n# Stage E opt-in: skip under Colab-safe Run-all unless flag True\n"
        "if RUN_PAYLOAD_CSV_EXPORT:\n"
        "    export_payloads_to_csv(limit=PAYLOAD_CSV_EXPORT_LIMIT)\n"
        "    _ = capture_memory_snapshot(note='after_payload_csv_export')\n"
        "    print(_.format_line())\n"
        "else:\n"
        "    print('RUN_PAYLOAD_CSV_EXPORT=False — skipped payload CSV export (Colab-safe default).')\n"
        "    print('Call export_payloads_to_csv(limit=PAYLOAD_CSV_EXPORT_LIMIT) manually if needed.')\n",
        text,
        count=1,
    )
    return text


def _patch_export_cache(text: str) -> str:
    if "RUN_PAYLOAD_CACHE_EXPORT" in text and "if RUN_PAYLOAD_CACHE_EXPORT" in text:
        return text
    text = re.sub(
        r"\nexport_payload_cache_sqlite\(\)\s*\n?",
        "\n# Stage E opt-in: skip under Colab-safe Run-all unless flag True\n"
        "if RUN_PAYLOAD_CACHE_EXPORT:\n"
        "    export_payload_cache_sqlite()\n"
        "    _ = capture_memory_snapshot(note='after_payload_cache_export')\n"
        "    print(_.format_line())\n"
        "else:\n"
        "    print('RUN_PAYLOAD_CACHE_EXPORT=False — skipped payload_cache.sqlite export (Colab-safe default).')\n"
        "    print('Call export_payload_cache_sqlite() manually if needed.')\n",
        text,
        count=1,
    )
    return text


def _patch_benchmark(text: str) -> str:
    if "RUN_BENCHMARK_SAMPLE" in text and "if RUN_BENCHMARK_SAMPLE" in text:
        return text
    # Keep function; ensure no auto-run and print gate
    if "run_benchmark_sample() defined" in text:
        text = re.sub(
            r"# Uncomment to run.*\n# benchmark_summary = run_benchmark_sample.*\n"
            r"print\('run_benchmark_sample\(\) defined\..*\)\n?",
            "# Stage E: never auto-run under Colab-safe unless RUN_BENCHMARK_SAMPLE=True\n"
            "if RUN_BENCHMARK_SAMPLE:\n"
            "    benchmark_summary = run_benchmark_sample(\n"
            "        sample_size=BENCHMARK_SAMPLE_SIZE, run_generation=False\n"
            "    )\n"
            "else:\n"
            "    print(\n"
            "        'RUN_BENCHMARK_SAMPLE=False — skipped auto benchmark '\n"
            "        f'(Colab-safe default). Function ready; size would be {BENCHMARK_SAMPLE_SIZE}.'\n"
            "    )\n"
            "    print('Example: benchmark_summary = run_benchmark_sample(sample_size=BENCHMARK_SAMPLE_SIZE)')\n",
            text,
            count=1,
            flags=re.S,
        )
        if "RUN_BENCHMARK_SAMPLE" not in text:
            text = text.rstrip() + (
                "\n\n# Stage E gate\n"
                "if RUN_BENCHMARK_SAMPLE:\n"
                "    benchmark_summary = run_benchmark_sample(sample_size=BENCHMARK_SAMPLE_SIZE, run_generation=False)\n"
                "else:\n"
                "    print('RUN_BENCHMARK_SAMPLE=False — skipped auto benchmark (Colab-safe default).')\n"
            )
    return text


def _patch_query_demo(text: str) -> str:
    """Gate heavy filter-profile comparison loops under Colab-safe."""
    if "RUN_FILTER_PROFILE_COMPARISON" in text:
        return text
    # Common pattern: loop over profiles — wrap guidance at end if comparison present
    if "Filter profile comparison" in text or "for profile" in text.lower():
        text = text.rstrip() + (
            "\n\n# Colab-safe: large multi-profile loops are opt-in Stage E\n"
            "if not RUN_FILTER_PROFILE_COMPARISON:\n"
            "    print('RUN_FILTER_PROFILE_COMPARISON=False — keep vector smoke lightweight under Colab-safe.')\n"
        )
    return text


def _patch_hybrid_demo(text: str) -> str:
    """Ensure hybrid demo reports session outcome labels."""
    if "session_outcome_label" in text and "hybrid_colab_safe_success_pickle" in text:
        return text
    suffix = '''

# --- Session outcome labels (FR-023) after hybrid demo ---
if hybrid_ctx is not None and getattr(hybrid_ctx, 'mode', None) == 'hybrid_expanded':
    print(
        format_session_outcome(
            session_outcome_label(
                colab_safe=COLAB_SAFE,
                structural_ready=graph_load_status.structural_ready,
                loaded_from_pickle=graph_load_status.loaded_from_pickle,
                hybrid_used=True,
                vector_ok=True,
            )
        )
    )
elif ENABLE_HYBRID_EXPANSION and not graph_load_status.structural_ready:
    print(
        format_session_outcome(
            'hybrid_unavailable',
            detail='Hybrid demo requested graph; vector_only path still OK.',
        )
    )
else:
    print(
        format_session_outcome(
            session_outcome_label(
                colab_safe=COLAB_SAFE,
                structural_ready=graph_load_status.structural_ready,
                loaded_from_pickle=getattr(graph_load_status, 'loaded_from_pickle', False),
                hybrid_used=False,
                vector_ok=True,
            )
        )
    )
'''
    if "Running hybrid demo query when enabled" in text:
        return text.rstrip() + "\n" + suffix
    return text


def main() -> None:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = nb["cells"]

    # Drop previous 005-tagged cells (idempotent re-run); keep 003 hybrid cells for in-place rewrite
    cells = [c for c in cells if not is_marker_cell(c, MARKER)]

    # 1) Intro
    if cells and cells[0].get("cell_type") == "markdown":
        set_source(cells[0], INTRO)

    # 2) Config cell
    for c in cells:
        if c.get("cell_type") == "code" and "INDEX_DIR = PROJECT_ROOT" in cell_text(c) and "TOP_K" in cell_text(c):
            set_source(c, CONFIG)
            break

    # 3) Preflight cell (Stage A load plan)
    for c in cells:
        if c.get("cell_type") == "code" and "required_files" in cell_text(c) and "index.faiss" in cell_text(c):
            set_source(c, PREFLIGHT_LOAD_PLAN)
            break

    # 4) Vector load (Stage B)
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "SQLitePayloadFaissVectorStore.load" in text and "retriever = VectorRetriever" in text:
            set_source(c, VECTOR_LOAD)
            break

    # 5) Hybrid markdown outline
    for c in cells:
        if c.get("cell_type") == "markdown" and "Hybrid graph integration" in cell_text(c):
            set_source(c, HYBRID_MD)
            break

    # 6) Hybrid imports
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "intended import surface" in text:
            set_source(c, HYBRID_IMPORTS)
            break

    # 7) Graph load (pickle prefer)
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "class GraphLoadStatus" in text and "require_graph_for_hybrid" in text:
            set_source(c, HYBRID_PREFLIGHT_BUILD)
            break

    # 8) Gate CSV export
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "def export_payloads_to_csv" in text:
            set_source(c, _patch_export_csv(text))
            break

    # 9) Gate cache export
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "def export_payload_cache_sqlite" in text:
            set_source(c, _patch_export_cache(text))
            break

    # 10) Query demo gate
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "Filter profile comparison" in text:
            set_source(c, _patch_query_demo(text))
            break

    # 11) Hybrid demo labels
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "show_hybrid_diagnostics" in text and "Running hybrid demo" in text:
            set_source(c, _patch_hybrid_demo(text))
            break

    # 12) Benchmark gate
    for c in cells:
        text = cell_text(c)
        if c.get("cell_type") == "code" and "def run_benchmark_sample" in text:
            set_source(c, _patch_benchmark(text))
            break

    # 13) Insert cleanup helper before generator section if not present
    has_cleanup = any("release_optional_objects" in cell_text(c) for c in cells)
    if not has_cleanup:
        insert_at = None
        for i, c in enumerate(cells):
            if c.get("cell_type") == "markdown" and "Configure the answer generator" in cell_text(c):
                insert_at = i
                break
        if insert_at is None:
            # before full pipeline / ask
            for i, c in enumerate(cells):
                if c.get("cell_type") == "code" and cell_text(c).lstrip().startswith("def ask("):
                    insert_at = i
                    break
        if insert_at is not None:
            block = [
                md(
                    "## 7.1 Optional cleanup between stages (best-effort)\n\n"
                    "Drop export frames or unload the structural graph to free headroom before "
                    "generation or after heavy demos. Not an OS hard memory reservation.\n\n"
                    "If the graph is unloaded, hybrid becomes unavailable until Stage C reloads."
                ),
                code(CLEANUP_CELL),
            ]
            cells = cells[:insert_at] + block + cells[insert_at:]

    # 14) Stage labels on key markdown headers
    stage_map = {
        "## 1. Environment setup": "## 1. Environment setup (before Stage A)",
        "## 2. Configure artifact paths": "## 2. Configure artifact paths and retrieval settings (Stage A)",
        "## 3. Preflight": "## 3. Preflight + load plan (Stage A)",
        "## 4. Load the FAISS": "## 4. Load the FAISS store and build retriever (Stage B)",
        "## 4.1 Optional: export payload cache to CSV": "## 4.1 Optional: export payload cache to CSV (Stage E — opt-in)",
        "## 4.2 Optional: download / export payload_cache.sqlite": "## 4.2 Optional: download / export payload_cache.sqlite (Stage E — opt-in)",
        "## 6. Run a query": "## 6. Run a query (Stage B vector smoke)",
        "## 6.1 Hybrid expansion demo": "## 6.1 Hybrid expansion demo (Stage C smoke)",
        "## 8. Configure the answer generator": "## 8. Configure the answer generator (Stage D — optional)",
        "## 10. Full RAG pipeline": "## 10. Full RAG pipeline: retrieve + generate (Stage D)",
        "## 11. Optional: run the full pipeline over a benchmark": "## 11. Optional benchmark sample (Stage E — opt-in)",
    }
    for c in cells:
        if c.get("cell_type") != "markdown":
            continue
        text = cell_text(c)
        for old, new in stage_map.items():
            if text.lstrip().startswith(old):
                set_source(c, text.replace(old, new, 1))
                break

    nb["cells"] = cells
    NOTEBOOK_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Patched {NOTEBOOK_PATH} — cells now: {len(cells)}")


if __name__ == "__main__":
    main()
