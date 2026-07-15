"""Patch notebooks/full_pipeline.ipynb for RAM mitigations + IVFPQ notes.

Changes:
- Config: LAZY_EMBEDDER, LAZY_GRAPH_LOAD, FAISS_NPROBE, memory flags
- Cell 11: lazy embedder + memory probe after FAISS load
- Cell 15: defer graph load behind ensure_hybrid_graph() when LAZY_GRAPH_LOAD
- Intro markdown: mention IVFPQ rebuild + RAM tips
- Install cell: optional psutil
"""
from __future__ import annotations

import json
from pathlib import Path

NB_PATH = Path("notebooks/full_pipeline.ipynb")
nb = json.loads(NB_PATH.read_text(encoding="utf-8"))


def src_of(i: int) -> str:
    return "".join(nb["cells"][i].get("source", []))


def set_src(i: int, text: str) -> None:
    # Jupyter stores source as list of lines ending with \n (except maybe last)
    if not text.endswith("\n"):
        text = text + "\n"
    lines = text.splitlines(keepends=True)
    nb["cells"][i]["source"] = lines


# ---------------------------------------------------------------------------
# Cell 0 — intro markdown: RAM / IVFPQ notes
# ---------------------------------------------------------------------------
intro = src_of(0)
if "IVFPQ" not in intro:
    intro = intro.rstrip() + """

---

### Colab RAM notes (hybrid retained)

Peak RSS on free Colab is dominated by three residents:

1. **FAISS** — exact `IndexFlatIP` is ~6 GB for ~1.5M×1024-d float32. Prefer a prebuilt **IVFPQ** `index.faiss` (rebuild once with [`scripts/rebuild_faiss_ivfpq.py`](../scripts/rebuild_faiss_ivfpq.py); payloads/SQLite unchanged).
2. **Embedder** — `multilingual-e5-large` is ~2–3 GB. This notebook uses a **lazy** embedder (`LAZY_EMBEDDER=True`) so the model loads on first query, not at store load.
3. **Knowledge graph** — structural `.gpickle` is multi-GB. Hybrid stays the default, but `LAZY_GRAPH_LOAD=True` defers gpickle + overlay join until the first hybrid call.

Use the memory probe cells (`print_memory`) after FAISS / embedder / graph to verify budgets. Hybrid still fails clearly if the graph is missing when hybrid is requested.
"""
    set_src(0, intro)

# ---------------------------------------------------------------------------
# Cell 4 — optional deps
# ---------------------------------------------------------------------------
install = src_of(4)
if "psutil" not in install:
    set_src(
        4,
        """# Optional: install runtime dependencies if your environment does not have them yet.
# Uncomment and run once if needed.
%pip install -q faiss-cpu sentence-transformers pandas openai psutil
""",
    )

# ---------------------------------------------------------------------------
# Cell 7 — config flags
# ---------------------------------------------------------------------------
config = src_of(7)
if "LAZY_EMBEDDER" not in config:
    config = config.replace(
        "GRAPH_GUIDED_MAX_DEPTH = 3\n",
        """GRAPH_GUIDED_MAX_DEPTH = 3

# --- RAM / Colab controls (hybrid retained) ---
# Lazy embedder: defer multilingual-e5-large (~2-3GB) until first encode.
LAZY_EMBEDDER = True
# Lazy graph: defer gpickle + overlay join until first hybrid call.
# Hybrid remains the default pipeline; first hybrid request pays the load cost.
LAZY_GRAPH_LOAD = True
# IVF search probes when index.faiss is IndexIVFPQ (ignored for Flat).
FAISS_NPROBE = 32
# Optional heavy exports (not present in this notebook; keep False if added).
RUN_EXPORTS = False
""",
    )
    config = config.replace(
        "print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)\n",
        """print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
print('LAZY_EMBEDDER:', LAZY_EMBEDDER)
print('LAZY_GRAPH_LOAD:', LAZY_GRAPH_LOAD)
print('FAISS_NPROBE:', FAISS_NPROBE)
print('RUN_EXPORTS:', RUN_EXPORTS)
""",
    )
    set_src(7, config)

# ---------------------------------------------------------------------------
# Cell 11 — store + lazy embedder + memory probe
# ---------------------------------------------------------------------------
set_src(
    11,
    '''if missing:
    raise FileNotFoundError('Download index.faiss and payloads.jsonl before running this cell.')

from retrieval.config import VectorIndexConfig
from retrieval.embeddings import LazySentenceTransformerEmbedder, SentenceTransformerEmbedder
from retrieval.memory_utils import print_memory
from retrieval.retriever import VectorRetriever
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore

load_t0 = time.perf_counter()
config = VectorIndexConfig(
    embedding_model=EMBEDDING_MODEL,
    top_k=TOP_K,
    top_n=TOP_N,
    score_threshold=SCORE_THRESHOLD,
    expand_units=EXPAND_UNITS,
)

print_memory('before_faiss_load')
store = SQLitePayloadFaissVectorStore.load(INDEX_DIR, nprobe=FAISS_NPROBE)
print_memory('after_faiss_load')

if LAZY_EMBEDDER:
    embedder = LazySentenceTransformerEmbedder(
        EMBEDDING_MODEL,
        query_prefix=config.query_prefix,
        passage_prefix=config.passage_prefix,
        expected_dimension=1024,
    )
    print('Embedder: LazySentenceTransformerEmbedder (loads on first query)')
else:
    embedder = SentenceTransformerEmbedder(
        EMBEDDING_MODEL,
        query_prefix=config.query_prefix,
        passage_prefix=config.passage_prefix,
    )
    print_memory('after_embedder_load')

retriever = VectorRetriever(config=config, embedder=embedder, store=store)

print(f'Vector retriever ready in {time.perf_counter() - load_t0:.2f}s')
print(f'Loaded FAISS vectors: {store.total_vectors:,}')
print(f'Embedding dimension (declared): {embedder.dimension}')
print('Store class:', type(store).__module__ + '.' + type(store).__name__)
print('FAISS class:', type(store.index).__name__)
if hasattr(store.index, 'nprobe'):
    print('FAISS nprobe:', store.index.nprobe)

# Vector-only retriever (graph_expansion=None). Hybrid retriever is wired after graph load.
hybrid_retriever = None
graph_expansion = None
''',
)

# ---------------------------------------------------------------------------
# Cell 15 — lazy graph load (hybrid retained)
# ---------------------------------------------------------------------------
# Keep helpers/preflight, but wrap the actual load in ensure_hybrid_graph().
cell15 = r'''# ### HYBRID_GRAPH_INTEGRATION - preflight, gpickle load (preferred), overlays, expansion wire, guard
# RAM: when LAZY_GRAPH_LOAD=True, structural gpickle + overlays load on first hybrid call.


@dataclass
class GraphLoadStatus:
    structural_ready: bool = False
    overlays_ready: bool = False
    missing_structural_files: list[str] = field(default_factory=list)
    missing_overlay_files: list[str] = field(default_factory=list)
    pickle_path: str | None = None
    load_source: str | None = None  # 'gpickle' | 'jsonl_rebuild'
    format_version: int | None = None
    created_at_utc: str | None = None
    source_data_dir: str | None = None
    build_stats: Any = None
    build_warnings: tuple[str, ...] = ()
    as_of_date: str | None = None
    overlay_coverage: dict[str, int] | None = None
    error: str | None = None
    build_duration_s: float | None = None
    loaded: bool = False  # True after ensure_hybrid_graph() actually materializes kg_graph


def preflight_graph_sources(v2_dir: Path, pickle_path: Path) -> GraphLoadStatus:
    """Preflight pickle + optional overlay/JSONL sources.

    Structural readiness for normal notebook use is driven by the portable
    `.gpickle` artifact. JSONL structural files are only required when
    ALLOW_GRAPH_JSONL_REBUILD is True and the pickle is missing.
    """
    paths = GraphLoaderPaths(data_dir=v2_dir)
    missing_structural = [str(p) for p in paths.required_paths() if not p.exists()]
    overlay_names = ('validity_timeline.jsonl', 'authority_index.jsonl')
    missing_overlay = [str(v2_dir / name) for name in overlay_names if not (v2_dir / name).exists()]
    pickle_ok = pickle_path.is_file()

    # Prefer pickle; do not require JSONL for structural_ready in default mode.
    if pickle_ok:
        structural_ready = True
    elif ALLOW_GRAPH_JSONL_REBUILD and not missing_structural:
        structural_ready = True
    else:
        structural_ready = False

    status = GraphLoadStatus(
        structural_ready=structural_ready,
        overlays_ready=not missing_overlay,
        missing_structural_files=missing_structural,
        missing_overlay_files=missing_overlay,
        pickle_path=str(pickle_path),
    )

    print('=== Graph preflight ===')
    print('V2_DATA_DIR:', v2_dir)
    print('KG_PICKLE_PATH:', pickle_path)
    print(f'  [{"OK" if pickle_ok else "MISSING"}] {pickle_path}')
    print('ALLOW_GRAPH_JSONL_REBUILD:', ALLOW_GRAPH_JSONL_REBUILD)
    print('LAZY_GRAPH_LOAD:', LAZY_GRAPH_LOAD)
    print('Structural JSONL files (only needed for rebuild fallback):')
    for p in paths.required_paths():
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')
    print('Overlay files (optional, still from JSONL after structural load):')
    for name in overlay_names:
        p = v2_dir / name
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')

    if not pickle_ok:
        print('Pickle MISSING - notebook will not rebuild from JSONL unless ALLOW_GRAPH_JSONL_REBUILD=True.')
        print('  Build once with: python scripts/build_kg_pickle.py --data-dir data/v2 --output data/graph/knowledge_graph.gpickle')
    if missing_overlay:
        print('Overlays unavailable (currency/authority labeled unavailable if structural graph loads).')
        for m in missing_overlay:
            print(' -', m)
    if not structural_ready:
        print('Structural graph UNAVAILABLE. Pure vector profiles remain usable.')
        if not pickle_ok:
            print(' - missing pickle:', pickle_path)
        if ALLOW_GRAPH_JSONL_REBUILD and missing_structural:
            print('Missing structural JSONL files for rebuild:')
            for m in missing_structural:
                print(' -', m)
    return status


def _stat_value(stats: Any, name: str, default: Any = 'n/a') -> Any:
    if stats is None:
        return default
    if isinstance(stats, dict):
        return stats.get(name, default)
    return getattr(stats, name, default)


def print_graph_stats(stats: Any, warnings: tuple[str, ...] | list[str] = (), *, title: str = 'Graph Statistics') -> None:
    print(f'[{title}]')
    print(f'  documents:           {_stat_value(stats, "document_count")}')
    print(f'  external_stubs:      {_stat_value(stats, "external_stub_count")}')
    print(f'  provisions:          {_stat_value(stats, "provision_count")}')
    print(f'  chunks:              {_stat_value(stats, "chunk_count")}')
    print(f'  document_edges:      {_stat_value(stats, "document_edge_count")}')
    print(f'  verified_edges:      {_stat_value(stats, "verified_document_edge_count")}')
    print(f'  unverified_edges:    {_stat_value(stats, "unverified_document_edge_count")}')
    print(f'  structural_edges:    {_stat_value(stats, "structural_edge_count")}')
    orphan_p = _stat_value(stats, 'orphan_provision_count', None)
    orphan_c = _stat_value(stats, 'orphan_chunk_count', None)
    if orphan_p is not None:
        print(f'  orphan_provisions:   {orphan_p}')
    if orphan_c is not None:
        print(f'  orphan_chunks:       {orphan_c}')
    if warnings:
        print('Warnings:')
        for w in list(warnings)[:20]:
            print(' -', w)


def load_structural_graph_from_pickle(pickle_path: Path):
    """Load structural KnowledgeGraph from trusted project .gpickle (no JSONL rebuild)."""
    load_t0 = time.perf_counter()
    loaded = load_knowledge_graph(pickle_path)
    duration = time.perf_counter() - load_t0
    return loaded, duration


def rebuild_structural_graph_from_jsonl(v2_dir: Path):
    """Fallback only: parse v2 JSONL and build in-memory graph."""
    kg_paths = GraphLoaderPaths(data_dir=v2_dir)
    facade = KnowledgeGraphFacade(paths=kg_paths)
    build_t0 = time.perf_counter()
    build_result = facade.build_graph()
    duration = time.perf_counter() - build_t0
    return facade, build_result, duration


def _join_overlays_streaming(kg_facade, kg_graph, v2_dir: Path, as_of: str):
    """Join overlays without holding both raw JSONL lists and the bundle longer than needed.

    Streams parse generators into the joiner; still materializes the final
    OverlayBundle (required for O(1) per-document lookup during hybrid).
    """
    validity_path = v2_dir / 'validity_timeline.jsonl'
    authority_path = v2_dir / 'authority_index.jsonl'
    # Generators — OverlayJoiner.index_* materializes internally once.
    validity_events = parse_validity_event_rows(read_jsonl(validity_path))
    authority_entries = parse_authority_index_rows(read_jsonl(authority_path))
    bundle = kg_facade.build_overlay_bundle(
        documents=kg_graph.documents.values(),
        validity_events=validity_events,
        authority_entries=authority_entries,
        as_of_date=as_of,
    )
    return bundle


def materialize_hybrid_graph() -> None:
    """Actually load gpickle + overlays + wire hybrid_retriever (idempotent)."""
    global kg_facade, kg_graph, kg_build_result, kg_load_result
    global overlay_bundle, graph_expansion, hybrid_retriever, document_overlays
    global graph_load_status

    if graph_load_status.loaded and kg_graph is not None and graph_expansion is not None:
        return

    if not graph_load_status.structural_ready:
        raise RuntimeError(
            'Cannot materialize hybrid graph: structural sources unavailable. '
            f'Detail: {graph_load_status.error or graph_load_status.pickle_path}'
        )

    try:
        from retrieval.memory_utils import print_memory

        print_memory('before_graph_load')
        pickle_path = Path(graph_load_status.pickle_path or KG_PICKLE_PATH)
        if pickle_path.is_file():
            print('\n=== Graph load (gpickle) ===')
            print('Using portable structural pickle - not rebuilding from JSONL.')
            kg_load_result, duration = load_structural_graph_from_pickle(pickle_path)
            kg_graph = kg_load_result.graph
            stats = kg_load_result.stats
            warnings = tuple(kg_load_result.warnings or ())
            kg_facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=V2_DATA_DIR))
            graph_load_status.load_source = 'gpickle'
            graph_load_status.format_version = kg_load_result.format_version
            graph_load_status.created_at_utc = kg_load_result.created_at_utc
            graph_load_status.source_data_dir = kg_load_result.source_data_dir
            graph_load_status.build_stats = stats
            graph_load_status.build_warnings = warnings
            graph_load_status.build_duration_s = duration
            graph_load_status.structural_ready = True
            print(f'Knowledge graph loaded from gpickle in {duration:.2f}s')
            print(f'  path: {kg_load_result.path}')
            print(f'  format_version: {kg_load_result.format_version}')
            print(f'  created_at_utc: {kg_load_result.created_at_utc}')
            print(f'  source_data_dir: {kg_load_result.source_data_dir}')
            if stats is None:
                stats = GraphBuildStats(
                    document_count=len(kg_graph.documents),
                    external_stub_count=len(kg_graph.external_stubs),
                    provision_count=len(kg_graph.provisions),
                    chunk_count=len(kg_graph.chunks),
                    document_edge_count=len(kg_graph.document_edges),
                    verified_document_edge_count=len(kg_graph.verified_document_edges),
                    unverified_document_edge_count=(
                        len(kg_graph.document_edges) - len(kg_graph.verified_document_edges)
                    ),
                    structural_edge_count=len(kg_graph.structural_edges),
                    orphan_provision_count=0,
                    orphan_chunk_count=0,
                    missing_external_stub_count=0,
                    structural_edge_counts={},
                    edge_group_counts={},
                )
                graph_load_status.build_stats = stats
            print_graph_stats(stats, warnings, title='Loaded Graph Statistics')
        elif ALLOW_GRAPH_JSONL_REBUILD:
            print('\n=== Graph build (JSONL rebuild fallback) ===')
            print('Pickle missing and ALLOW_GRAPH_JSONL_REBUILD=True - building from structural JSONL.')
            kg_facade, kg_build_result, duration = rebuild_structural_graph_from_jsonl(V2_DATA_DIR)
            kg_graph = kg_build_result.graph
            stats = kg_build_result.stats
            warnings = tuple(kg_build_result.warnings or ())
            graph_load_status.load_source = 'jsonl_rebuild'
            graph_load_status.build_stats = stats
            graph_load_status.build_warnings = warnings
            graph_load_status.build_duration_s = duration
            graph_load_status.structural_ready = True
            print(f'Knowledge graph built from JSONL in {duration:.2f}s')
            print_graph_stats(stats, warnings, title='Build Statistics')
        else:
            raise RuntimeError(
                f'Structural graph pickle not found at {pickle_path}. '
                'Build it with scripts/build_kg_pickle.py or set ALLOW_GRAPH_JSONL_REBUILD=True.'
            )

        # Overlays remain dynamic/optional after structural load (not in pickle).
        if not graph_load_status.missing_overlay_files:
            print('\n=== Overlay join ===')
            if kg_facade is None:
                kg_facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=V2_DATA_DIR))
            overlay_bundle = _join_overlays_streaming(kg_facade, kg_graph, V2_DATA_DIR, AS_OF_DATE)
            document_overlays = dict(overlay_bundle.document_overlays)
            graph_load_status.overlays_ready = True
            graph_load_status.as_of_date = AS_OF_DATE
            currency_hist: dict[str, int] = {}
            for ov in document_overlays.values():
                currency_hist[ov.currency_status] = currency_hist.get(ov.currency_status, 0) + 1
            # Avoid second full materialization of validity/authority lists for counts.
            graph_load_status.overlay_coverage = {
                'docs_with_overlay': len(document_overlays),
                **{f'currency_{k}': v for k, v in sorted(currency_hist.items())},
            }
            print(f'Overlay bundle for as_of_date={AS_OF_DATE}')
            print(f'  docs_with_overlay: {len(document_overlays):,}')
            print('  currency histogram (sample keys):', dict(list(currency_hist.items())[:8]))
        else:
            graph_load_status.overlays_ready = False
            print('\nOverlays MISSING - structural expansion allowed; currency/authority labeled unavailable.')

        graph_expansion = GraphExpansion(kg_graph)
        hybrid_retriever = VectorRetriever(
            config=config,
            embedder=embedder,
            store=store,
            graph_expansion=graph_expansion,
        )
        graph_load_status.loaded = True
        graph_load_status.error = None
        print_memory('after_graph_load')
        print('\nGraphExpansion wired. hybrid_retriever has graph_expansion; vector-only retriever remains graph_expansion=None.')
        print('Label reminder: graph_expansion ≠ local_expand_units')
        print('load_source:', graph_load_status.load_source)
    except (GraphPickleNotFoundError, GraphPickleCorruptError, GraphPickleIncompatibleError) as exc:
        graph_load_status.structural_ready = False
        graph_load_status.loaded = False
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph pickle load FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
        print('Build/fix pickle with: python scripts/build_kg_pickle.py --data-dir data/v2 --output data/graph/knowledge_graph.gpickle')
        raise
    except Exception as exc:
        graph_load_status.structural_ready = False
        graph_load_status.loaded = False
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph load/build FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
        raise


def ensure_hybrid_graph() -> None:
    """Ensure graph is loaded when hybrid is needed (lazy or eager)."""
    if graph_load_status.loaded and kg_graph is not None and graph_expansion is not None:
        return
    materialize_hybrid_graph()


graph_load_status = preflight_graph_sources(V2_DATA_DIR, KG_PICKLE_PATH)
kg_facade: KnowledgeGraphFacade | None = None
kg_graph = None
kg_build_result = None
kg_load_result = None
overlay_bundle: OverlayBundle | None = None
graph_expansion: GraphExpansion | None = None
hybrid_retriever: VectorRetriever | None = None
document_overlays: dict[str, DocumentOverlay] = {}

if graph_load_status.structural_ready and not LAZY_GRAPH_LOAD:
    print('LAZY_GRAPH_LOAD=False — loading hybrid graph eagerly.')
    try:
        materialize_hybrid_graph()
    except Exception:
        pass  # errors already recorded on graph_load_status
elif graph_load_status.structural_ready and LAZY_GRAPH_LOAD:
    print('LAZY_GRAPH_LOAD=True — deferring gpickle/overlay load until first hybrid call.')
    print('Hybrid remains the default pipeline; ensure_hybrid_graph() runs inside hybrid helpers.')
else:
    print('Skipping graph load (pickle missing and JSONL rebuild disabled or unavailable).')


def require_graph_for_hybrid(action: str = 'hybrid expansion') -> None:
    """Fail clearly if hybrid is requested without a loaded graph (FR-015)."""
    # Lazy path: attempt load once when hybrid is actually requested.
    if (
        graph_load_status.structural_ready
        and (not graph_load_status.loaded or kg_graph is None or graph_expansion is None)
    ):
        try:
            ensure_hybrid_graph()
        except Exception as exc:
            # ensure_hybrid_graph already stamped graph_load_status.error
            pass

    if not graph_load_status.structural_ready or kg_graph is None or graph_expansion is None:
        missing = []
        if graph_load_status.pickle_path and not Path(graph_load_status.pickle_path).is_file():
            missing.append(f'missing pickle: {graph_load_status.pickle_path}')
        if graph_load_status.missing_structural_files:
            missing.extend(graph_load_status.missing_structural_files)
        if not missing:
            missing = ['(structural graph not loaded)']
        detail = graph_load_status.error or '; '.join(missing)
        raise RuntimeError(
            f"Cannot run {action}: knowledge graph unavailable. "
            f"Do not silently fall back to vector-only under a hybrid label. Detail: {detail}"
        )


print('\nGraphLoadStatus:')
print('  structural_ready:', graph_load_status.structural_ready)
print('  loaded:', graph_load_status.loaded)
print('  load_source:', graph_load_status.load_source)
print('  pickle_path:', graph_load_status.pickle_path)
print('  overlays_ready:', graph_load_status.overlays_ready)
print('  error:', graph_load_status.error)
'''
set_src(15, cell15)

# ---------------------------------------------------------------------------
# Cell 16 — ensure hybrid helpers call require_graph (already does via do_expand)
# Patch run_hybrid_retrieve to call require_graph_for_hybrid / ensure when expanding
# ---------------------------------------------------------------------------
cell16 = src_of(16)
if "ensure_hybrid_graph" not in cell16 and "require_graph_for_hybrid" in cell16:
    # Inject ensure at start of expansion branch if missing — require_graph already covers it
    pass
if "require_graph_for_hybrid(" in cell16:
    # ensure require is called when do_expand — check existing pattern
    if "if do_expand:" in cell16 and "require_graph_for_hybrid" not in cell16.split("if do_expand:")[1][:400]:
        cell16 = cell16.replace(
            "if do_expand:",
            "if do_expand:\n        require_graph_for_hybrid('hybrid expansion')",
            1,
        )
        set_src(16, cell16)

# Also soft-patch: when ENABLE_HYBRID and comparing, require_graph is used later.
# Force warm path: after defining run_hybrid, demos already call require via hybrid.

# ---------------------------------------------------------------------------
# Cell 24 demos — if they check structural_ready without loading, require_graph
# will load. Good.
# ---------------------------------------------------------------------------

# Add a small markdown note before hybrid section if not present
# Done.

NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Patched", NB_PATH)
print("cells", len(nb["cells"]))
# quick verify
for i in (0, 4, 7, 11, 15):
    s = "".join(nb["cells"][i]["source"])
    print(f"cell {i}: LAZY_EMBEDDER={('LAZY_EMBEDDER' in s)} LAZY_GRAPH={('LAZY_GRAPH' in s)} len={len(s)}")
