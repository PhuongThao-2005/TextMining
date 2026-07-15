"""Patch faiss_retrieval_ready.ipynb to load structural KG from .gpickle by default."""

from __future__ import annotations

import json
from pathlib import Path

NB_PATH = Path("notebooks/faiss_retrieval_ready.ipynb")

CONFIG_OLD = """# Graph + overlay sources (structural graph under data/v2)
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'

# Must match the embedding model used to build index.faiss."""

CONFIG_NEW = """# Graph + overlay sources (structural graph under data/v2)
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'
# Preferred structural graph artifact (built via scripts/build_kg_pickle.py)
KG_PICKLE_PATH = PROJECT_ROOT / 'data' / 'graph' / 'knowledge_graph.gpickle'
# Keep False for normal notebook use: load pickle only (no JSONL rebuild).
ALLOW_GRAPH_JSONL_REBUILD = False

# Must match the embedding model used to build index.faiss."""

CONFIG_PRINT_OLD = """print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
INDEX_DIR
"""

CONFIG_PRINT_NEW = """print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('KG_PICKLE_PATH:', KG_PICKLE_PATH)
print('ALLOW_GRAPH_JSONL_REBUILD:', ALLOW_GRAPH_JSONL_REBUILD)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
INDEX_DIR
"""

IMPORTS_OLD = """from knowledge_graph import (
    GraphExpansion,
    GraphLoaderPaths,
    KnowledgeGraphFacade,
    QueryConstraints,
    parse_authority_index_rows,
    parse_validity_event_rows,
)
"""

IMPORTS_NEW = """from knowledge_graph import (
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

CELL12_NEW = r'''# ### HYBRID_GRAPH_INTEGRATION — preflight, gpickle load (preferred), overlays, expansion wire, guard


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
        print('Pickle MISSING — notebook will not rebuild from JSONL unless ALLOW_GRAPH_JSONL_REBUILD=True.')
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


graph_load_status = preflight_graph_sources(V2_DATA_DIR, KG_PICKLE_PATH)
kg_facade: KnowledgeGraphFacade | None = None
kg_graph = None
kg_build_result = None
kg_load_result = None
overlay_bundle: OverlayBundle | None = None
graph_expansion: GraphExpansion | None = None
hybrid_retriever: VectorRetriever | None = None
document_overlays: dict[str, DocumentOverlay] = {}

if graph_load_status.structural_ready:
    try:
        pickle_path = Path(graph_load_status.pickle_path or KG_PICKLE_PATH)
        if pickle_path.is_file():
            print('\n=== Graph load (gpickle) ===')
            print('Using portable structural pickle — not rebuilding from JSONL.')
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
            # Prefer envelope stats; if absent, fall back to live graph counts.
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
            print('Pickle missing and ALLOW_GRAPH_JSONL_REBUILD=True — building from structural JSONL.')
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
            validity_path = V2_DATA_DIR / 'validity_timeline.jsonl'
            authority_path = V2_DATA_DIR / 'authority_index.jsonl'
            validity_events = list(parse_validity_event_rows(read_jsonl(validity_path)))
            authority_entries = list(parse_authority_index_rows(read_jsonl(authority_path)))
            if kg_facade is None:
                kg_facade = KnowledgeGraphFacade(paths=GraphLoaderPaths(data_dir=V2_DATA_DIR))
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
            graph_load_status.overlay_coverage = {
                'docs_with_overlay': len(document_overlays),
                'validity_events': len(validity_events),
                'authority_entries': len(authority_entries),
                **{f'currency_{k}': v for k, v in sorted(currency_hist.items())},
            }
            print(f'Overlay bundle for as_of_date={AS_OF_DATE}')
            print(f'  docs_with_overlay: {len(document_overlays):,}')
            print(f'  validity_events:   {len(validity_events):,}')
            print(f'  authority_entries: {len(authority_entries):,}')
            print('  currency histogram (sample keys):', dict(list(currency_hist.items())[:8]))
        else:
            graph_load_status.overlays_ready = False
            print('\nOverlays MISSING — structural expansion allowed; currency/authority labeled unavailable.')

        # Expansion wiring
        graph_expansion = GraphExpansion(kg_graph)
        hybrid_retriever = VectorRetriever(
            config=config,
            embedder=embedder,
            store=store,
            graph_expansion=graph_expansion,
        )
        print('\nGraphExpansion wired. hybrid_retriever has graph_expansion; vector-only retriever remains graph_expansion=None.')
        print('Label reminder: graph_expansion ≠ local_expand_units')
        print('load_source:', graph_load_status.load_source)
    except (GraphPickleNotFoundError, GraphPickleCorruptError, GraphPickleIncompatibleError) as exc:
        graph_load_status.structural_ready = False
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph pickle load FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
        print('Build/fix pickle with: python scripts/build_kg_pickle.py --data-dir data/v2 --output data/graph/knowledge_graph.gpickle')
    except Exception as exc:
        graph_load_status.structural_ready = False
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph load/build FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
else:
    print('Skipping graph load (pickle missing and JSONL rebuild disabled or unavailable).')


def require_graph_for_hybrid(action: str = 'hybrid expansion') -> None:
    """Fail clearly if hybrid is requested without a loaded graph (FR-015)."""
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
print('  load_source:', graph_load_status.load_source)
print('  pickle_path:', graph_load_status.pickle_path)
print('  overlays_ready:', graph_load_status.overlays_ready)
print('  error:', graph_load_status.error)
'''


def source_to_lines(text: str) -> list[str]:
    if not text.endswith("\n"):
        text = text + "\n"
    lines = text.splitlines(keepends=True)
    return lines


def main() -> None:
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    changed = []

    # Cell 5: config
    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))
        if "V2_DATA_DIR = PROJECT_ROOT" in src and "INDEX_DIR" in src:
            if "KG_PICKLE_PATH" not in src:
                if CONFIG_OLD not in src:
                    raise SystemExit(f"cell {i}: config block not found for KG_PICKLE_PATH insert")
                src = src.replace(CONFIG_OLD, CONFIG_NEW)
                changed.append(f"cell {i}: added KG_PICKLE_PATH / ALLOW_GRAPH_JSONL_REBUILD")
            if "print('KG_PICKLE_PATH:'" not in src:
                if CONFIG_PRINT_OLD not in src:
                    raise SystemExit(f"cell {i}: config print block not found")
                src = src.replace(CONFIG_PRINT_OLD, CONFIG_PRINT_NEW)
                changed.append(f"cell {i}: print KG_PICKLE_PATH")
            cell["source"] = source_to_lines(src)

        if "intended import surface" in src and "from knowledge_graph import" in src:
            if "load_knowledge_graph" not in src:
                if IMPORTS_OLD not in src:
                    raise SystemExit(f"cell {i}: import block not found")
                src = src.replace(IMPORTS_OLD, IMPORTS_NEW)
                cell["source"] = source_to_lines(src)
                changed.append(f"cell {i}: imports for load_knowledge_graph / pickle errors")

        if "HYBRID_GRAPH_INTEGRATION — preflight, build, overlays" in src or (
            "class GraphLoadStatus" in src and "def preflight_graph_sources" in src and "build_graph()" in src
        ):
            cell["source"] = source_to_lines(CELL12_NEW)
            changed.append(f"cell {i}: replaced graph build with gpickle-first load")

    if not any("gpickle-first" in c or "load_knowledge_graph" in c for c in changed):
        # still ok if already patched
        joined = "\n".join("".join(c.get("source", [])) for c in nb["cells"])
        if "load_knowledge_graph" in joined and "KG_PICKLE_PATH" in joined and "build_graph()" not in joined.split("Graph load")[0]:
            print("Notebook already appears patched; writing verification only.")
        elif not changed:
            raise SystemExit("No target cells patched — inspect notebook structure.")

    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Patched:", NB_PATH)
    for line in changed:
        print(" -", line)

    # verify
    nb2 = json.loads(NB_PATH.read_text(encoding="utf-8"))
    full = "\n".join("".join(c.get("source", [])) for c in nb2["cells"])
    checks = {
        "KG_PICKLE_PATH defined": "KG_PICKLE_PATH = PROJECT_ROOT" in full,
        "ALLOW_GRAPH_JSONL_REBUILD defined": "ALLOW_GRAPH_JSONL_REBUILD = False" in full,
        "load_knowledge_graph imported": "load_knowledge_graph" in full,
        "gpickle load section": "Graph load (gpickle)" in full,
        "no default build_graph call": "kg_facade.build_graph()" not in full or "ALLOW_GRAPH_JSONL_REBUILD" in full,
        "rebuild helper only": "rebuild_structural_graph_from_jsonl" in full,
        "overlay join retained": "Overlay join" in full,
    }
    for name, ok in checks.items():
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
    if not all(checks.values()):
        raise SystemExit("Verification failed")


if __name__ == "__main__":
    main()
