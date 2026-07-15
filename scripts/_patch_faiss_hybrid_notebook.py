#!/usr/bin/env python3
"""One-shot patcher: integrate hybrid graph pipeline into faiss_retrieval_ready.ipynb.

Idempotent for re-runs: replaces previously inserted hybrid cells marked with
HYBRID_GRAPH_INTEGRATION markers.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "faiss_retrieval_ready.ipynb"
MARKER = "HYBRID_GRAPH_INTEGRATION"


def _id() -> str:
    return uuid.uuid4().hex[:8]


def md(source: str) -> dict:
    text = source if source.endswith("\n") else source + "\n"
    return {
        "cell_type": "markdown",
        "id": _id(),
        "metadata": {"tags": [MARKER]},
        "source": [line + "\n" for line in text.split("\n")[:-1]] + ([text.split("\n")[-1] + "\n"] if text.split("\n")[-1] else []),
    }


def code(source: str) -> dict:
    text = source if source.endswith("\n") else source + "\n"
    lines = text.split("\n")
    # rebuild as notebook source lines
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


def cell_text(cell: dict) -> str:
    return "".join(cell.get("source", []))


def is_hybrid_cell(cell: dict) -> bool:
    tags = cell.get("metadata", {}).get("tags") or []
    if MARKER in tags:
        return True
    text = cell_text(cell)
    return "### HYBRID_GRAPH_INTEGRATION" in text or "HYBRID_GRAPH_INTEGRATION" in text and "003-notebook-graph" in text


INTRO = """# FAISS Vector Retrieval + Hybrid Graph Notebook

This notebook runs retrieval after `index.faiss` and `payloads.jsonl` are available, and (when v2 graph sources are present) demonstrates the **primary hybrid pipeline**:

```text
query → embed → vector seed retrieval → graph expansion + validity/authority overlays → optional LLM generation
```

**Architecture**
- Store: [`SQLitePayloadFaissVectorStore`](../src/retrieval/sqlite_faiss_store.py) — FAISS + rebuild-if-stale `payload_cache.sqlite`
- Retrieval: [`VectorRetriever`](../src/retrieval/retriever.py) — seed search; optional graph expansion / graph-guided filter
- Knowledge graph: [`KnowledgeGraphFacade`](../src/knowledge_graph/facade.py), [`GraphExpansion`](../src/knowledge_graph/expansion.py), overlays
- Generation: [`generation.reasoning_client`](../src/generation/reasoning_client.py) — OpenAI-compatible client with three-way reasoning parse

**Primary vs secondary graph paths**
- **Primary (default full pipeline):** vector-first hybrid expansion (seed hits → graph expand → overlays → generate)
- **Secondary (optional demo):** graph-guided pre-filter (document whitelist before vector search) — not the default `ask()` path

Expected layouts:

```text
data/faiss_index/
  index.faiss
  payloads.jsonl
  id_map.json        # optional
  payload_cache.sqlite  # built automatically on first load

data/v2/             # required for hybrid graph path
  documents.jsonl, provisions.jsonl, chunks.jsonl, edges.jsonl, external_stubs.jsonl
  validity_timeline.jsonl, authority_index.jsonl   # optional overlays
```

Run cells top to bottom. Pure vector profiles (`current_law`, `broad`, `historical`) remain usable if the graph is missing. Hybrid mode fails clearly when the graph is unavailable rather than silently falling back under a hybrid label.

**Note:** This notebook is a hybrid **demonstration** layered on existing modules — not a replacement for dedicated graph verification ([`scripts/verify_kg.py`](../scripts/verify_kg.py)) or judged evaluation ([`scripts/evaluate_e2e.py`](../scripts/evaluate_e2e.py)).
"""

CONFIG = '''# Directory containing index.faiss + payloads.jsonl (+ optional id_map.json)
INDEX_DIR = PROJECT_ROOT / 'data' / 'faiss_index'

# Graph + overlay sources (structural graph under data/v2)
V2_DATA_DIR = PROJECT_ROOT / 'data' / 'v2'

# Must match the embedding model used to build index.faiss.
# Alias EMBEDDING_MODEL_NAME kept for plan/quickstart naming parity.
EMBEDDING_MODEL = 'intfloat/multilingual-e5-large'
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL

TOP_K = 30                 # candidates pulled from FAISS before reranking/dedup
TOP_N = 10                 # final chunks returned
SCORE_THRESHOLD = 0.30
# Local same-provision expansion (payload-window). Prefer False when demoing graph expansion.
EXPAND_UNITS = False
LOCAL_EXPAND_UNITS = EXPAND_UNITS  # alias: local_expand_units mechanism label
DEFAULT_FILTER_PROFILE = 'broad'  # current_law | broad | historical (non-graph)
FILTER_PROFILE = DEFAULT_FILTER_PROFILE
BENCHMARK_SAMPLE_SIZE = 10

# --- Hybrid graph settings (003-notebook-graph-integration / FR-021) ---
ENABLE_HYBRID_EXPANSION = True
HYBRID_MAX_HOP = 1
HYBRID_MAX_CONTEXT = 12
AS_OF_DATE = '2026-07-13'
USE_HYBRID_EVIDENCE_FOR_GENERATION = True
ENABLE_GRAPH_GUIDED_PREFILTER_DEMO = False  # secondary whitelist-before-search path
GRAPH_GUIDED_START_ID = ''  # optional document id_str; empty → take from first seed hit
GRAPH_GUIDED_TRAVERSAL_MODE = 'basis'
GRAPH_GUIDED_MAX_DEPTH = 2

print('INDEX_DIR:', INDEX_DIR)
print('V2_DATA_DIR:', V2_DATA_DIR)
print('ENABLE_HYBRID_EXPANSION:', ENABLE_HYBRID_EXPANSION)
print('USE_HYBRID_EVIDENCE_FOR_GENERATION:', USE_HYBRID_EVIDENCE_FOR_GENERATION)
print('LOCAL_EXPAND_UNITS / EXPAND_UNITS:', LOCAL_EXPAND_UNITS)
print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)
INDEX_DIR
'''

SEARCH_HELPER = '''def search(
    query: str,
    top_n: int = TOP_N,
    filter_profile: str = FILTER_PROFILE,
    score_threshold: float | None = SCORE_THRESHOLD,
    expand_units: bool | None = None,
    graph_guided_filter=None,
    use_hybrid_retriever: bool = False,
):
    """Run VectorRetriever and return (display_rows, RetrievalResult).

    filter_profile: 'current_law' | 'broad' | 'historical' | 'graph_guided' (via graph_guided_filter)

    Expansion labeling:
    - expand_units=True with graph_expansion wired → mechanism is graph expansion (module path)
    - expand_units=True without graph_expansion → local_expand_units (payload same-provision)
    Prefer the two-stage hybrid helper for seed vs expanded diagnostics.
    """
    active = hybrid_retriever if (use_hybrid_retriever and hybrid_retriever is not None) else retriever

    if filter_profile == 'graph_guided' and graph_guided_filter is None:
        print(
            'graph_guided requested without GraphGuidedFilter. '
            'Use the optional graph-guided pre-filter demo, or pass graph_guided_filter=... '
            'Falling back to broad (pure vector).'
        )
        filter_profile = 'broad'

    search_t0 = time.perf_counter()
    result = active.retrieve(
        query,
        top_n=top_n,
        filter_profile=filter_profile if graph_guided_filter is None else 'graph_guided',
        score_threshold=score_threshold,
        expand_units=LOCAL_EXPAND_UNITS if expand_units is None else expand_units,
        graph_guided_filter=graph_guided_filter,
    )
    print(f'Retrieval completed in {time.perf_counter() - search_t0:.2f}s')
    rows = []
    for rank, chunk in enumerate(result.chunks, start=1):
        rows.append({
            'rank': rank,
            'chunk_id': chunk.chunk_id,
            'id_str': chunk.id_str,
            'citation': chunk.citation_anchor or chunk.citation_label,
            'title': chunk.title,
            'unit_type': chunk.unit_type,
            'validity_group': chunk.validity_group,
            'parent_unit_id': chunk.parent_unit_id,
            'vector_score': round(chunk.vector_score, 4),
            'rerank_score': round(chunk.rerank_score, 4),
            'text': chunk.chunk_text[:700],
        })
    return rows, result


def show_results(rows):
    try:
        import pandas as pd
        from IPython.display import display
        display(pd.DataFrame(rows))
    except Exception:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, indent=2))
'''

QUERY_DEMO = '''query_t0 = time.perf_counter()
query = 'Điều kiện để người lao động đơn phương chấm dứt hợp đồng lao động là gì?'

# Primary run under default FILTER_PROFILE (pure vector / non-graph)
rows, result = search(query, top_n=10, filter_profile=FILTER_PROFILE)
print('Filter profile used:', result.filter_profile_used)
print('Total candidates:', result.total_candidates)
print('Empty filter warning:', result.empty_filter_warning)
show_results(rows)
print(f'Query phase completed in {time.perf_counter() - query_t0:.2f}s')

# --- Filter-profile comparison (non-graph profiles remain fully usable without graph) ---
print('\\n=== Filter profile comparison (same query) ===')
for profile in ('current_law', 'broad', 'historical'):
    _, r = search(query, top_n=TOP_N, filter_profile=profile)
    print(
        f'  {profile:12s} | candidates={r.total_candidates:4d} | '
        f'returned={len(r.chunks):2d} | empty_filter_warning={r.empty_filter_warning}'
    )

print(
    '  graph_guided  | secondary path — see optional demo cell '
    f'(ENABLE_GRAPH_GUIDED_PREFILTER_DEMO={ENABLE_GRAPH_GUIDED_PREFILTER_DEMO})'
)

# --- Local same-provision expansion demo (local_expand_units mechanism) ---
print('\\n=== Local expansion demo (local_expand_units=True vs False) ===')
print('Mechanism label: local_expand_units (payload same-provision window; not graph_expansion)')
_, r_no = search(query, top_n=5, filter_profile='broad', expand_units=False)
_, r_yes = search(query, top_n=5, filter_profile='broad', expand_units=True)
print(f'  local_expand_units=False → {len(r_no.chunks)} chunks')
print(f'  local_expand_units=True  → {len(r_yes.chunks)} chunks')
parent_ids = {c.parent_unit_id for c in r_yes.chunks if c.parent_unit_id}
print(f'  unique parent_unit_id among expanded results: {len(parent_ids)}')
'''

ASK_CELL = '''def ask(
    query: str,
    top_n: int = TOP_N,
    filter_profile: str = FILTER_PROFILE,
    score_threshold: float | None = SCORE_THRESHOLD,
    *,
    use_hybrid: bool | None = None,
    use_hybrid_evidence: bool | None = None,
):
    """Full pipeline: vector seed → (optional graph expand/overlays) → generate.

    Default demonstration path uses hybrid expanded evidence when
    ENABLE_HYBRID_EXPANSION and the graph is loaded (FR-009 / FR-022).
    Hybrid requested while graph unavailable fails clearly (FR-015).
    """
    hybrid = ENABLE_HYBRID_EXPANSION if use_hybrid is None else use_hybrid
    hybrid_for_gen = USE_HYBRID_EVIDENCE_FOR_GENERATION if use_hybrid_evidence is None else use_hybrid_evidence

    hybrid_ctx = None
    result = None
    evidence_chunks = []

    if hybrid:
        require_graph_for_hybrid('hybrid ask() full pipeline')
        hybrid_ctx = run_hybrid_retrieve(
            query,
            top_n=top_n,
            filter_profile=filter_profile,
            score_threshold=score_threshold,
            enable_expansion=True,
        )
        print('Mode:', hybrid_ctx.mode)
        print('Seed candidates:', hybrid_ctx.seed.total_candidates)
        print('Evidence chunks:', len(hybrid_ctx.evidence_chunks))
        print('Expansion added context:', hybrid_ctx.expansion_added_context)
        if hybrid_ctx.diagnostics:
            print('Diagnostics:')
            for note in hybrid_ctx.diagnostics:
                print(' -', note)
        show_results(chunks_to_display_rows(hybrid_ctx.evidence_chunks))
        evidence_chunks = list(hybrid_ctx.evidence_chunks)
        # Build a RetrievalResult-like object for callers that expect .chunks
        from retrieval.schema import RetrievalResult
        result = RetrievalResult(
            chunks=evidence_chunks,
            total_candidates=hybrid_ctx.seed.total_candidates,
            filter_profile_used=filter_profile,
            empty_filter_warning=False,
        )
    else:
        rows, result = search(
            query,
            top_n=top_n,
            filter_profile=filter_profile,
            score_threshold=score_threshold,
            expand_units=False,
        )
        print('Mode: vector_only')
        print('Filter profile used:', result.filter_profile_used)
        print('Total candidates:', result.total_candidates)
        print('Empty filter warning:', result.empty_filter_warning)
        show_results(rows)
        evidence_chunks = list(result.chunks)

    usable = [c for c in evidence_chunks if (c.chunk_text or '').strip()]
    if not usable:
        print('No usable evidence text after retrieval/expansion; skipping generation (empty context).')
        outcome = GenerationOutcome(qa_id=None, parsed=None, skipped_empty_context=True, error=None)
        return {
            'query': query,
            'outcome': outcome,
            'result': result,
            'hybrid': hybrid_ctx,
            'mode': hybrid_ctx.mode if hybrid_ctx else 'vector_only',
        }

    if generator is None:
        print('Generator not configured; returning retrieval/expansion-only result.')
        return {
            'query': query,
            'outcome': None,
            'result': result,
            'hybrid': hybrid_ctx,
            'mode': hybrid_ctx.mode if hybrid_ctx else 'vector_only',
        }

    if hybrid and hybrid_for_gen:
        gen_chunks = usable
        print('Generation uses hybrid expanded evidence (USE_HYBRID_EVIDENCE_FOR_GENERATION=True).')
    elif hybrid and not hybrid_for_gen:
        # Prefer seed-only evidence when hybrid retrieval ran but generation should not use expansion.
        seed_only = list(hybrid_ctx.seed.seed_chunks) if hybrid_ctx is not None else usable
        gen_chunks = [c for c in seed_only if (c.chunk_text or '').strip()] or usable
        print('Generation uses seed-only evidence (USE_HYBRID_EVIDENCE_FOR_GENERATION=False).')
    else:
        gen_chunks = usable
    outcome = generate_answer(query, gen_chunks)
    display_generation_outcome(outcome)

    print('\\n--- Citations used (citation-ready evidence only) ---')
    for rank, chunk in enumerate(gen_chunks, start=1):
        print(
            f'[{rank}] {chunk.citation_anchor or chunk.citation_label} - {chunk.title} '
            f'| chunk_id={chunk.chunk_id} → parent_unit_id={chunk.parent_unit_id} → id_str={chunk.id_str}'
        )
    return {
        'query': query,
        'outcome': outcome,
        'result': result,
        'hybrid': hybrid_ctx,
        'mode': hybrid_ctx.mode if hybrid_ctx else 'vector_only',
    }


pipeline_query = 'Điều kiện để người lao động đơn phương chấm dứt hợp đồng lao động là gì?'
# Uncomment when ready (generator optional — hybrid retrieval still completes without credentials):
# pipeline_output = ask(pipeline_query, top_n=10, filter_profile='broad')
print('ask() defined. Default path: vector seed → graph expand/overlays → generate when hybrid enabled.')
print('Call: pipeline_output = ask(pipeline_query, top_n=10, filter_profile="broad")')
print('Vector-only: pipeline_output = ask(pipeline_query, use_hybrid=False)')
'''

# --- Hybrid cell contents ---

HYBRID_MD_OUTLINE = """### HYBRID_GRAPH_INTEGRATION — Outline (003)

Primary hybrid path (default full pipeline):

```text
query → embed → vector seed retrieve → resolve chunk→provision→document
      → GraphExpansion + validity/authority overlays → fused evidence → optional LLM
```

Secondary path (optional only): graph-guided pre-filter whitelist before vector search.

This section orchestrates existing modules under `src/knowledge_graph/` and `src/retrieval/` — it does **not** reimplement graph logic and is **not** a replacement for `scripts/verify_kg.py` or `scripts/evaluate_e2e.py`.
"""

HYBRID_IMPORTS = '''# ### HYBRID_GRAPH_INTEGRATION — intended import surface (FR-002)
from dataclasses import dataclass, field
from typing import Any

from knowledge_graph import (
    GraphExpansion,
    GraphLoaderPaths,
    KnowledgeGraphFacade,
    QueryConstraints,
    parse_authority_index_rows,
    parse_validity_event_rows,
)
from knowledge_graph.context_schema import GraphGuidedFilter
from knowledge_graph.expansion_schema import ExpansionResult
from knowledge_graph.overlay import OverlayBundle
from knowledge_graph.overlay_schema import DocumentOverlay
from retrieval.io_utils import read_jsonl
from retrieval.schema import RetrievedChunk, RetrievalResult
from retrieval.stores import SearchHit

print('Hybrid import surface ready: KnowledgeGraphFacade, GraphExpansion, overlays, GraphGuidedFilter')
'''

HYBRID_PREFLIGHT_BUILD = '''# ### HYBRID_GRAPH_INTEGRATION — preflight, build, overlays, expansion wire, guard


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


def preflight_graph_sources(v2_dir: Path) -> GraphLoadStatus:
    """List present/missing structural + overlay files (FR-003)."""
    paths = GraphLoaderPaths(data_dir=v2_dir)
    missing_structural = [str(p) for p in paths.required_paths() if not p.exists()]
    overlay_names = ('validity_timeline.jsonl', 'authority_index.jsonl')
    missing_overlay = [str(v2_dir / name) for name in overlay_names if not (v2_dir / name).exists()]
    status = GraphLoadStatus(
        structural_ready=not missing_structural,
        overlays_ready=not missing_overlay,
        missing_structural_files=missing_structural,
        missing_overlay_files=missing_overlay,
    )
    print('=== Graph preflight ===')
    print('V2_DATA_DIR:', v2_dir)
    print('Structural files:')
    for p in paths.required_paths():
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')
    print('Overlay files (optional):')
    for name in overlay_names:
        p = v2_dir / name
        flag = 'OK' if p.exists() else 'MISSING'
        print(f'  [{flag}] {p}')
    if missing_structural:
        print('Structural graph UNAVAILABLE. Pure vector profiles remain usable.')
        print('Missing structural files:')
        for m in missing_structural:
            print(' -', m)
    if missing_overlay:
        print('Overlays unavailable (currency/authority labeled unavailable if structural graph loads).')
        for m in missing_overlay:
            print(' -', m)
    return status


graph_load_status = preflight_graph_sources(V2_DATA_DIR)
kg_facade: KnowledgeGraphFacade | None = None
kg_graph = None
kg_build_result = None
overlay_bundle: OverlayBundle | None = None
graph_expansion: GraphExpansion | None = None
hybrid_retriever: VectorRetriever | None = None
document_overlays: dict[str, DocumentOverlay] = {}

if graph_load_status.structural_ready:
    try:
        print('\\n=== Graph build ===')
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
        print(f'Knowledge graph built in {duration:.2f}s')
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

        # Overlays (optional)
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
            print('\\nOverlays MISSING — structural expansion allowed; currency/authority labeled unavailable.')

        # Expansion wiring
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
        graph_load_status.error = str(exc)
        kg_facade = None
        kg_graph = None
        graph_expansion = None
        hybrid_retriever = None
        print('Graph build FAILED:', exc)
        print('Pure vector retrieval remains usable; hybrid mode will fail clearly if requested.')
else:
    print('Skipping graph build (structural sources missing).')


def require_graph_for_hybrid(action: str = 'hybrid expansion') -> None:
    """Fail clearly if hybrid is requested without a loaded graph (FR-015)."""
    if not graph_load_status.structural_ready or kg_graph is None or graph_expansion is None:
        missing = graph_load_status.missing_structural_files or ['(structural graph not loaded)']
        detail = graph_load_status.error or '; '.join(missing)
        raise RuntimeError(
            f"Cannot run {action}: knowledge graph unavailable. "
            f"Do not silently fall back to vector-only under a hybrid label. Detail: {detail}"
        )


print('\\nGraphLoadStatus:')
print('  structural_ready:', graph_load_status.structural_ready)
print('  overlays_ready:', graph_load_status.overlays_ready)
print('  error:', graph_load_status.error)
'''

HYBRID_HELPER = '''# ### HYBRID_GRAPH_INTEGRATION — two-stage hybrid helper + views (US1)


@dataclass
class SeedRetrievalView:
    query: str
    filter_profile: str
    total_candidates: int
    seed_chunks: list[RetrievedChunk]
    seed_chunk_ids: list[str]
    mode_label: str  # vector_only | hybrid_seed


@dataclass
class GraphExpansionView:
    expansion: ExpansionResult | None
    expanded_chunk_ids: list[str]
    added_chunk_ids: list[str]
    resolved_chunks: list[RetrievedChunk]
    warnings: list[str]
    capped: bool
    mechanism_label: str = 'graph_expansion'


@dataclass
class HybridEvidenceContext:
    query: str
    mode: str  # vector_only | hybrid_expanded | graph_guided_prefilter
    seed: SeedRetrievalView
    expansion: GraphExpansionView | None
    evidence_chunks: list[RetrievedChunk]
    document_overlays: dict[str, DocumentOverlay]
    overlay_available: bool
    expansion_added_context: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class ModeComparisonRecord:
    query: str
    vector_only_count: int
    hybrid_count: int
    expansion_ran: bool
    added_context_count: int
    sample_vector_only_ids: list[str]
    sample_hybrid_ids: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass
class GraphGuidedDemoResult:
    start_id: str
    traversal_mode: str
    whitelist_size: int
    empty_filter_warning: bool
    filter_reason: str
    retrieval: RetrievalResult | None


def _hit_to_retrieved_chunk(hit: SearchHit, query: str, filter_profile: str) -> RetrievedChunk:
    """Reuse VectorRetriever conversion so identity fields stay consistent."""
    return retriever._to_retrieved_chunk(hit, query, filter_profile)


def _is_citation_safe_chunk(chunk: RetrievedChunk) -> bool:
    """External stubs / non-citation-safe nodes are never citation-ready (FR-013)."""
    meta = chunk.metadata or {}
    if meta.get('is_external_stub') is True:
        return False
    if meta.get('citation_safe') is False:
        return False
    # Graph external stubs keyed by id_str
    if kg_graph is not None and chunk.id_str and chunk.id_str in getattr(kg_graph, 'external_stubs', {}):
        return False
    if not (chunk.chunk_text or '').strip():
        return False
    return True


def _resolve_chunk_ids(chunk_ids: list[str], query: str, filter_profile: str) -> list[RetrievedChunk]:
    if not chunk_ids:
        return []
    # Preserve order from expansion; scroll may return unordered.
    hits = store.scroll({'chunk_id': {'in': list(chunk_ids)}}, limit=max(len(chunk_ids), 1))
    by_id: dict[str, SearchHit] = {}
    for hit in hits:
        cid = str(hit.payload.get('chunk_id') or hit.point_id)
        by_id[cid] = hit
    ordered: list[RetrievedChunk] = []
    for cid in chunk_ids:
        hit = by_id.get(cid)
        if hit is None:
            continue
        ordered.append(_hit_to_retrieved_chunk(hit, query, filter_profile))
    return ordered


def run_hybrid_retrieve(
    query: str,
    *,
    top_n: int = TOP_N,
    filter_profile: str = FILTER_PROFILE,
    score_threshold: float | None = SCORE_THRESHOLD,
    enable_expansion: bool | None = None,
    max_hop: int | None = None,
    max_context: int | None = None,
) -> HybridEvidenceContext:
    """Vector seed → optional GraphExpansion → overlay join → HybridEvidenceContext."""
    do_expand = ENABLE_HYBRID_EXPANSION if enable_expansion is None else enable_expansion
    max_hop = HYBRID_MAX_HOP if max_hop is None else max_hop
    max_context = HYBRID_MAX_CONTEXT if max_context is None else max_context
    diagnostics: list[str] = []

    # Stage 1: seed vector retrieve (never local expand here)
    seed_result = retriever.retrieve(
        query,
        top_n=top_n,
        filter_profile=filter_profile,
        score_threshold=score_threshold,
        expand_units=False,
    )
    seed_chunks = list(seed_result.chunks)
    seed_ids = [c.chunk_id for c in seed_chunks]
    seed_view = SeedRetrievalView(
        query=query,
        filter_profile=seed_result.filter_profile_used,
        total_candidates=seed_result.total_candidates,
        seed_chunks=seed_chunks,
        seed_chunk_ids=seed_ids,
        mode_label='hybrid_seed' if do_expand else 'vector_only',
    )

    if not do_expand:
        diagnostics.append('Hybrid expansion disabled — returning vector-only seeds.')
        return HybridEvidenceContext(
            query=query,
            mode='vector_only',
            seed=seed_view,
            expansion=None,
            evidence_chunks=seed_chunks,
            document_overlays={},
            overlay_available=graph_load_status.overlays_ready,
            expansion_added_context=False,
            diagnostics=diagnostics,
        )

    require_graph_for_hybrid('hybrid expansion')

    if not seed_ids:
        diagnostics.append('Zero seed hits — skipping graph expansion and recording empty context.')
        empty_expansion = GraphExpansionView(
            expansion=None,
            expanded_chunk_ids=[],
            added_chunk_ids=[],
            resolved_chunks=[],
            warnings=['No seed chunk IDs; expansion skipped.'],
            capped=False,
            mechanism_label='graph_expansion',
        )
        return HybridEvidenceContext(
            query=query,
            mode='hybrid_expanded',
            seed=seed_view,
            expansion=empty_expansion,
            evidence_chunks=[],
            document_overlays={},
            overlay_available=graph_load_status.overlays_ready,
            expansion_added_context=False,
            diagnostics=diagnostics,
        )

    expansion_result = graph_expansion.expand(
        seed_ids,
        max_hop=max_hop,
        max_context=max_context,
    )
    expanded_ids = list(expansion_result.ordered_context_chunks)
    seed_set = set(seed_ids)
    added_ids = [cid for cid in expanded_ids if cid not in seed_set]
    # Prefer expanded order; if expansion returned nothing usable, fall back to seeds
    ordered_ids = expanded_ids or list(seed_ids)
    capped = bool(
        max_context is not None
        and expansion_result.max_context is not None
        and len(expanded_ids) >= int(expansion_result.max_context)
    )
    if capped:
        diagnostics.append(f'Expansion context capped at max_context={max_context}.')

    warnings = list(expansion_result.warnings or ())
    resolved = _resolve_chunk_ids(ordered_ids, query, filter_profile)
    # Keep citation-ready only for generation/display of "evidence"
    citation_ready = [c for c in resolved if _is_citation_safe_chunk(c)]
    dropped = len(resolved) - len(citation_ready)
    if dropped:
        diagnostics.append(f'Excluded {dropped} non-citation-safe/stub/empty chunks from citation-ready evidence.')

    if not added_ids:
        diagnostics.append('Graph expansion ran with zero added neighbors (seeds only) — not a failure.')
    else:
        diagnostics.append(f'Graph expansion added {len(added_ids)} chunk ids beyond seeds.')

    for w in warnings:
        diagnostics.append(f'Expansion warning: {w}')

    expansion_view = GraphExpansionView(
        expansion=expansion_result,
        expanded_chunk_ids=expanded_ids,
        added_chunk_ids=added_ids,
        resolved_chunks=resolved,
        warnings=warnings,
        capped=capped,
        mechanism_label='graph_expansion',
    )

    # Overlay join by id_str (display-only signals; do not mutate payloads)
    involved_ids = {c.id_str for c in citation_ready if c.id_str}
    subset_overlays: dict[str, DocumentOverlay] = {}
    if graph_load_status.overlays_ready and document_overlays:
        subset_overlays = {i: document_overlays[i] for i in involved_ids if i in document_overlays}
        diagnostics.append(f'Overlays attached for {len(subset_overlays)}/{len(involved_ids)} involved documents (as_of={AS_OF_DATE}).')
    else:
        diagnostics.append('Overlays unavailable — structural expansion only; no authoritative currency claims.')

    evidence = citation_ready if citation_ready else list(seed_chunks)
    return HybridEvidenceContext(
        query=query,
        mode='hybrid_expanded',
        seed=seed_view,
        expansion=expansion_view,
        evidence_chunks=evidence,
        document_overlays=subset_overlays,
        overlay_available=graph_load_status.overlays_ready,
        expansion_added_context=bool(added_ids),
        diagnostics=diagnostics,
    )


def chunks_to_display_rows(chunks: list[RetrievedChunk], *, limit: int | None = None) -> list[dict[str, Any]]:
    rows = []
    for rank, chunk in enumerate(chunks[: limit or len(chunks)], start=1):
        rows.append({
            'rank': rank,
            'chunk_id': chunk.chunk_id,
            'parent_unit_id': chunk.parent_unit_id,
            'id_str': chunk.id_str,
            'citation': chunk.citation_anchor or chunk.citation_label,
            'title': chunk.title,
            'validity_group': chunk.validity_group,
            'legal_authority_rank': chunk.legal_authority_rank,
            'vector_score': round(chunk.vector_score, 4),
            'text': (chunk.chunk_text or '')[:400],
        })
    return rows


print('Hybrid helper ready: run_hybrid_retrieve(), require_graph_for_hybrid(), chunks_to_display_rows()')
'''

HYBRID_DIAGNOSTICS = '''# ### HYBRID_GRAPH_INTEGRATION — diagnostics, comparison, demos (US2/US3/US4)

hybrid_demo_query = 'Điều kiện để người lao động đơn phương chấm dứt hợp đồng lao động là gì?'


def show_hybrid_diagnostics(ctx: HybridEvidenceContext) -> None:
    """Seed vs expanded counts, identity samples, overlays, warnings (US2)."""
    print('=== Hybrid diagnostics ===')
    print('Query:', ctx.query)
    print('Mode:', ctx.mode)
    print('Mechanism: graph_expansion (not local_expand_units)')
    print(f'Seed count: {len(ctx.seed.seed_chunks)} | seed candidates: {ctx.seed.total_candidates}')
    if ctx.expansion is None:
        print('Expansion: not run')
    else:
        print(
            f'Expanded ids: {len(ctx.expansion.expanded_chunk_ids)} | '
            f'added: {len(ctx.expansion.added_chunk_ids)} | '
            f'capped: {ctx.expansion.capped} | '
            f'mechanism_label: {ctx.expansion.mechanism_label}'
        )
        if ctx.expansion.warnings:
            print('Expansion warnings:')
            for w in ctx.expansion.warnings:
                print(' -', w)
    print(f'Evidence (citation-ready) count: {len(ctx.evidence_chunks)}')
    print('Sample identity chain (chunk_id → parent_unit_id → id_str):')
    show_results(chunks_to_display_rows(ctx.evidence_chunks, limit=8))

    print('\\n--- Overlay diagnostics ---')
    if ctx.overlay_available and ctx.document_overlays:
        print(f'Overlay coverage for involved docs: {len(ctx.document_overlays)}')
        sample_id, sample_ov = next(iter(ctx.document_overlays.items()))
        print(f'Sample document id_str={sample_id}')
        print(f'  currency_status: {sample_ov.currency_status}')
        print(f'  currency_status_as_of: {sample_ov.currency_status_as_of}')
        print(f'  legal_authority_rank: {sample_ov.legal_authority_rank}')
        print(f'  authority_rank_source: {sample_ov.authority_rank_source}')
    else:
        print('Overlays unavailable or none matched involved documents — no authoritative currency/authority claims.')

    if ctx.diagnostics:
        print('\\nStage notes:')
        for note in ctx.diagnostics:
            print(' -', note)


def compare_vector_vs_hybrid(
    query: str,
    *,
    top_n: int = TOP_N,
    filter_profile: str = FILTER_PROFILE,
) -> ModeComparisonRecord:
    """Same query under vector_only vs hybrid_expanded (US3 / FR-011)."""
    notes: list[str] = []
    # Vector-only
    vo_result = retriever.retrieve(
        query,
        top_n=top_n,
        filter_profile=filter_profile,
        score_threshold=SCORE_THRESHOLD,
        expand_units=False,
    )
    vo_ids = [c.chunk_id for c in vo_result.chunks]

    expansion_ran = False
    added = 0
    hybrid_ids: list[str] = []
    hybrid_count = 0
    try:
        require_graph_for_hybrid('hybrid side of mode comparison')
        hctx = run_hybrid_retrieve(query, top_n=top_n, filter_profile=filter_profile, enable_expansion=True)
        expansion_ran = hctx.expansion is not None and hctx.mode == 'hybrid_expanded'
        added = len(hctx.expansion.added_chunk_ids) if hctx.expansion else 0
        hybrid_ids = [c.chunk_id for c in hctx.evidence_chunks]
        hybrid_count = len(hctx.evidence_chunks)
        if expansion_ran and added == 0:
            notes.append('Expansion ran but added nothing beyond seeds.')
        elif expansion_ran:
            notes.append(f'Expansion added {added} chunk ids.')
        notes.extend(hctx.diagnostics[:5])
    except RuntimeError as exc:
        notes.append(f'Hybrid unavailable: {exc}')
        hybrid_count = -1

    record = ModeComparisonRecord(
        query=query,
        vector_only_count=len(vo_result.chunks),
        hybrid_count=hybrid_count,
        expansion_ran=expansion_ran,
        added_context_count=added,
        sample_vector_only_ids=vo_ids[:5],
        sample_hybrid_ids=hybrid_ids[:5],
        notes=notes,
    )
    print('=== Mode comparison: vector_only vs hybrid_expanded ===')
    print('Query:', query)
    print(f'  vector_only     count={record.vector_only_count} sample_ids={record.sample_vector_only_ids}')
    print(f'  hybrid_expanded count={record.hybrid_count} expansion_ran={record.expansion_ran} added={record.added_context_count}')
    print(f'  sample_hybrid_ids={record.sample_hybrid_ids}')
    for n in record.notes:
        print('  note:', n)
    return record


def run_graph_guided_prefilter_demo(
    query: str,
    *,
    start_id: str | None = None,
    top_n: int = TOP_N,
    filter_profile: str = 'current_law',
) -> GraphGuidedDemoResult:
    """Secondary whitelist-before-search path (US4 / FR-020). Not the default ask() path."""
    require_graph_for_hybrid('graph-guided pre-filter demo')
    assert kg_facade is not None and kg_graph is not None

    sid = (start_id or GRAPH_GUIDED_START_ID or '').strip()
    if not sid:
        # Derive from a seed hit when possible
        seed = retriever.retrieve(query, top_n=max(1, top_n), filter_profile=FILTER_PROFILE, expand_units=False)
        if seed.chunks and seed.chunks[0].id_str:
            sid = seed.chunks[0].id_str
            print(f'Graph-guided start id_str taken from first seed hit: {sid}')
        else:
            # Fall back to first document with a verified edge
            for edge in kg_graph.verified_document_edges:
                if edge.src_id in kg_graph.documents:
                    sid = edge.src_id
                    print(f'Graph-guided start id_str taken from verified edge src: {sid}')
                    break
    if not sid:
        raise RuntimeError('No start id_str available for graph-guided pre-filter demo.')

    traversal = kg_facade.traverse(
        kg_graph,
        start_id=sid,
        mode=GRAPH_GUIDED_TRAVERSAL_MODE,  # type: ignore[arg-type]
        max_depth=GRAPH_GUIDED_MAX_DEPTH,
    )
    overlays = document_overlays if graph_load_status.overlays_ready else {}
    guided = kg_facade.build_graph_guided_filter(
        graph=kg_graph,
        traversal=traversal,
        overlays=overlays,
        filter_profile=filter_profile,  # type: ignore[arg-type]
        constraints=QueryConstraints(validity_groups=('active', 'partial', 'future')),
    )
    print('=== Graph-guided pre-filter demo (SECONDARY path) ===')
    print('start_id:', sid)
    print('traversal_mode:', GRAPH_GUIDED_TRAVERSAL_MODE)
    print('whitelist size:', len(guided.id_strs))
    print('empty_filter_warning:', guided.empty_filter_warning)
    print('filter_profile:', guided.filter_profile)
    print('filter reason:', getattr(guided, 'reason', '') or '(none)')

    retrieval = None
    if guided.empty_filter_warning or not guided.id_strs:
        print(
            'EMPTY whitelist — not searching full corpus under a graph-guided label. '
            'empty_filter_warning stays True; no unfiltered hits returned as graph-guided.'
        )
        retrieval = RetrievalResult([], 0, 'graph_guided', empty_filter_warning=True)
    else:
        retrieval = retriever.retrieve(
            query,
            top_n=top_n,
            graph_guided_filter=guided,
            expand_units=False,
        )
        print('graph-guided retrieval returned:', len(retrieval.chunks), 'chunks')
        print('empty_filter_warning on result:', retrieval.empty_filter_warning)
        show_results(chunks_to_display_rows(retrieval.chunks, limit=8))

    return GraphGuidedDemoResult(
        start_id=sid,
        traversal_mode=str(GRAPH_GUIDED_TRAVERSAL_MODE),
        whitelist_size=len(guided.id_strs),
        empty_filter_warning=bool(guided.empty_filter_warning or not guided.id_strs),
        filter_reason=str(getattr(guided, 'reason', '') or guided.filter_profile),
        retrieval=retrieval,
    )


# --- Demo runs (safe when graph missing: hybrid calls fail clearly) ---
print('Running hybrid demo query when enabled...')
hybrid_ctx = None
comparison_record = None
graph_guided_demo = None

if ENABLE_HYBRID_EXPANSION and graph_load_status.structural_ready:
    hybrid_ctx = run_hybrid_retrieve(hybrid_demo_query, top_n=TOP_N, filter_profile=FILTER_PROFILE)
    show_hybrid_diagnostics(hybrid_ctx)
    comparison_record = compare_vector_vs_hybrid(hybrid_demo_query)
elif ENABLE_HYBRID_EXPANSION and not graph_load_status.structural_ready:
    print('Hybrid enabled but graph unavailable — demonstrating FR-015 clear failure:')
    try:
        require_graph_for_hybrid('hybrid demo')
    except RuntimeError as exc:
        print('Expected failure:', exc)
    print('Pure vector search still works:')
    rows_v, res_v = search(hybrid_demo_query, top_n=5, filter_profile=FILTER_PROFILE, expand_units=False)
    print('vector_only returned:', len(res_v.chunks))
else:
    print('ENABLE_HYBRID_EXPANSION=False — skip hybrid demo. Vector-only path remains default.')

if ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:
    if graph_load_status.structural_ready:
        graph_guided_demo = run_graph_guided_prefilter_demo(hybrid_demo_query)
    else:
        print('Graph-guided demo enabled but graph unavailable — skipping with explicit message.')
else:
    print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO=False — secondary pre-filter demo not run.')
'''


def main() -> None:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = nb["cells"]

    # Drop any previous hybrid-tagged cells for idempotency
    cells = [c for c in cells if not is_hybrid_cell(c)]

    # Update intro
    set_source(cells[0], INTRO)

    # Update config cell (was index 5; still the first code cell after "## 2.")
    for c in cells:
        if c.get("cell_type") == "code" and "INDEX_DIR = PROJECT_ROOT" in cell_text(c) and "TOP_K" in cell_text(c):
            set_source(c, CONFIG)
            break

    # Update FAISS load cell to keep hybrid_retriever placeholder mention? leave as-is but ensure retriever is vector-only
    for c in cells:
        text = cell_text(c)
        if "retriever = VectorRetriever" in text and "SQLitePayloadFaissVectorStore.load" in text:
            # ensure hybrid_retriever initialized later; add note
            if "hybrid_retriever" not in text:
                set_source(
                    c,
                    text.rstrip()
                    + "\n\n# Vector-only retriever (graph_expansion=None). Hybrid retriever is wired after graph load.\nhybrid_retriever = None\ngraph_expansion = None\n",
                )
            break

    # Update search helper
    for c in cells:
        if c.get("cell_type") == "code" and cell_text(c).lstrip().startswith("def search("):
            set_source(c, SEARCH_HELPER)
            break

    # Update query demo
    for c in cells:
        if c.get("cell_type") == "code" and "Filter profile comparison" in cell_text(c):
            set_source(c, QUERY_DEMO)
            break

    # Update ask cell
    for c in cells:
        if c.get("cell_type") == "code" and cell_text(c).lstrip().startswith("def ask("):
            set_source(c, ASK_CELL)
            break

    # Find insertion index: after FAISS load cell (cell that defines retriever)
    insert_at = None
    for i, c in enumerate(cells):
        if c.get("cell_type") == "code" and "retriever = VectorRetriever" in cell_text(c):
            insert_at = i + 1
            break
    if insert_at is None:
        raise SystemExit("Could not find FAISS load cell for hybrid insertion")

    hybrid_block = [
        md(
            "## 4.3 Hybrid graph integration (vector-first)\n\n"
            + HYBRID_MD_OUTLINE.replace("### HYBRID_GRAPH_INTEGRATION — Outline (003)\n\n", "")
        ),
        code(HYBRID_IMPORTS),
        code(HYBRID_PREFLIGHT_BUILD),
        code(HYBRID_HELPER),
    ]

    # Find insertion for diagnostics: after query demo section (before full chunk inspect or generator)
    # We'll insert diagnostics block after the "Run a query" code cell.
    query_idx = None
    for i, c in enumerate(cells):
        if c.get("cell_type") == "code" and "local_expand_units=True vs False" in cell_text(c) or (
            c.get("cell_type") == "code" and "Filter profile comparison" in cell_text(c)
        ):
            query_idx = i
    # After updates, re-find
    # Build new list: insert hybrid foundation after FAISS load, insert demos after query cell
    new_cells: list[dict] = []
    for i, c in enumerate(cells):
        new_cells.append(c)
        if i == insert_at - 1:
            new_cells.extend(deepcopy(hybrid_block))

    # Find query cell in new_cells and insert diagnostics after it
    demo_insert_after = None
    for i, c in enumerate(new_cells):
        if c.get("cell_type") == "code" and "Filter profile comparison" in cell_text(c):
            demo_insert_after = i
            break
    if demo_insert_after is None:
        raise SystemExit("Could not find query demo cell")

    demo_block = [
        md(
            "## 6.1 Hybrid expansion demo, diagnostics, and comparison\n\n"
            "Seed vs graph-expanded evidence, overlay signals, vector-only vs hybrid comparison, "
            "and optional graph-guided pre-filter (secondary).\n\n"
            "Labels: **graph_expansion** is distinct from **local_expand_units**."
        ),
        code(HYBRID_DIAGNOSTICS),
    ]

    final_cells = new_cells[: demo_insert_after + 1] + deepcopy(demo_block) + new_cells[demo_insert_after + 1 :]
    nb["cells"] = final_cells
    NOTEBOOK_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Patched {NOTEBOOK_PATH} — cells now: {len(final_cells)}")


if __name__ == "__main__":
    main()
