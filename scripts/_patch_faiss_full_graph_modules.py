#!/usr/bin/env python3
"""Integrate the full knowledge_graph package surface into faiss_retrieval_ready.ipynb.

Idempotent: replaces FULL_GRAPH_MODULE-marked cells and upgrades hybrid import /
load / demo cells without breaking Colab-safe hybrid defaults (003/004/005).
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "faiss_retrieval_ready.ipynb"
MARKER = "FULL_GRAPH_MODULE"
HYBRID_MARKER = "HYBRID_GRAPH_INTEGRATION"


def _id() -> str:
    return uuid.uuid4().hex[:8]


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


def is_full_module_cell(cell: dict) -> bool:
    tags = cell.get("metadata", {}).get("tags") or []
    if MARKER in tags:
        return True
    text = cell_text(cell)
    return "### FULL_GRAPH_MODULE" in text


IMPORT_CELL = r'''# ### HYBRID_GRAPH_INTEGRATION — intended import surface (FR-002)
# ### FULL_GRAPH_MODULE — full knowledge_graph package surface
# ### COLAB_SAFE_RAM_FIT — pickle load surface (004)
from dataclasses import dataclass, field
from typing import Any, Literal

# --- Public package surface (loader → parse → build → traverse → expand → overlay → context → persist) ---
from knowledge_graph import (
    # loader
    GraphLoader,
    GraphLoaderPaths,
    GraphSourceBundle,
    load_jsonl_records,
    # schema / parser nodes
    ChunkNode,
    DocumentNode,
    ExternalStubNode,
    FacetValue,
    ProvisionNode,
    TextProvenanceRecord,
    index_text_provenance,
    parse_chunk_row,
    parse_chunk_rows,
    parse_document_row,
    parse_document_rows,
    parse_external_stub_row,
    parse_external_stub_rows,
    parse_provision_row,
    parse_provision_rows,
    parse_text_provenance_row,
    # edges
    GraphEdge,
    parse_edge_row,
    parse_edge_rows,
    verified_edge_rows,
    # builder
    GraphBuildResult,
    GraphBuildStats,
    GraphBuilder,
    KnowledgeGraph,
    StructuralEdge,
    # traversal
    GraphTraversal,
    TraversalMode,
    TraversalPath,
    TraversalResult,
    TraversalStep,
    # expansion (primary hybrid)
    GraphExpansion,
    ExpansionResult,
    ExpansionStep,
    # overlay
    OverlayBundle,
    OverlayJoiner,
    AuthorityIndexEntry,
    DocumentOverlay,
    ValidityEvent,
    compute_currency_status,
    index_authority_index,
    index_validity_timeline,
    parse_authority_index_row,
    parse_authority_index_rows,
    parse_validity_event_row,
    parse_validity_event_rows,
    resolve_authority_rank_conflicts,
    # context
    ContextBuilder,
    EvidenceContext,
    FilterProfile,
    GraphGuidedFilter,
    QueryConstraints,
    # facade + parse bundle
    KnowledgeGraphFacade,
    ParsedGraphSources,
    # persist
    FORMAT_NAME,
    FORMAT_VERSION,
    GraphPickleArtifactInfo,
    GraphPickleCorruptError,
    GraphPickleEnvelope,
    GraphPickleError,
    GraphPickleIncompatibleError,
    GraphPickleLoadResult,
    GraphPickleNotFoundError,
    load_knowledge_graph,
    save_knowledge_graph,
)

# Internal helpers (not re-exported on package __all__, still part of the module)
from knowledge_graph import utils as kg_utils
from knowledge_graph.utils import as_bool, as_int, quality_flags

from retrieval.io_utils import read_jsonl
from retrieval.schema import RetrievedChunk, RetrievalResult
from retrieval.stores import SearchHit

GRAPH_MODULE_SURFACE = {
    'loader': (GraphLoader, GraphLoaderPaths, GraphSourceBundle, load_jsonl_records),
    'parser_schema': (
        ChunkNode, DocumentNode, ExternalStubNode, FacetValue, ProvisionNode,
        TextProvenanceRecord, index_text_provenance,
        parse_chunk_rows, parse_document_rows, parse_external_stub_rows,
        parse_provision_rows, parse_text_provenance_row,
    ),
    'edge_parser': (GraphEdge, parse_edge_row, parse_edge_rows, verified_edge_rows),
    'builder': (GraphBuilder, KnowledgeGraph, GraphBuildResult, GraphBuildStats, StructuralEdge),
    'traversal': (GraphTraversal, TraversalMode, TraversalPath, TraversalResult, TraversalStep),
    'expansion': (GraphExpansion, ExpansionResult, ExpansionStep),
    'overlay': (
        OverlayJoiner, OverlayBundle, DocumentOverlay, ValidityEvent, AuthorityIndexEntry,
        parse_validity_event_rows, parse_authority_index_rows,
        index_validity_timeline, index_authority_index,
        compute_currency_status, resolve_authority_rank_conflicts,
    ),
    'context': (ContextBuilder, EvidenceContext, GraphGuidedFilter, QueryConstraints, FilterProfile),
    'facade': (KnowledgeGraphFacade, ParsedGraphSources),
    'persist': (
        load_knowledge_graph, save_knowledge_graph, GraphPickleLoadResult,
        FORMAT_NAME, FORMAT_VERSION, GraphPickleError,
    ),
    'utils': (as_int, as_bool, quality_flags, kg_utils),
}

print('Full Graph Module import surface ready:')
for group, objs in GRAPH_MODULE_SURFACE.items():
    names = ', '.join(getattr(o, '__name__', type(o).__name__) for o in objs[:4])
    more = f' (+{len(objs)-4} more)' if len(objs) > 4 else ''
    print(f'  [{group}] {names}{more}')
'''


STAGE_C_MD = """## 4.3 Hybrid graph integration (vector-first) — Stage C

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

**Full Graph Module orchestration (this notebook)**
Stage C imports and wires the entire `src/knowledge_graph/` surface through [`KnowledgeGraphFacade`](../src/knowledge_graph/facade.py) plus direct services:

| Layer | Modules | Notebook role |
| --- | --- | --- |
| Loader | `loader.py` | path contract + optional JSONL source streams |
| Parser / edges | `parser.py`, `schema.py`, `edge_parser.py`, `edge_schema.py` | typed nodes/edges (via facade parse / rebuild) |
| Builder | `builder.py` | structural `KnowledgeGraph` (pickle load or JSONL rebuild) |
| Persist | `persist.py` | preferred Colab-safe pickle load |
| Expansion | `expansion.py`, `expansion_schema.py` | **primary** hybrid seed→context |
| Traversal | `traversal.py` | **secondary** modes + guided pre-filter |
| Overlay | `overlay.py`, `overlay_schema.py` | validity/authority join (non-mutating) |
| Context | `context.py`, `context_schema.py` | guided filter + `EvidenceContext` |
| Facade | `facade.py` | public orchestration |
| Utils | `utils.py` | coercion helpers used by parsers/overlays |

This section orchestrates existing modules under `src/knowledge_graph/` and `src/retrieval/` — it does **not** reimplement graph logic.
"""


FULL_MODULE_MD = """## 4.4 Full Graph Module surface demos (Stage C extension)

Opt-in inventory and lightweight demos for **every** graph layer after a successful structural load.

Controlled by `ENABLE_FULL_GRAPH_MODULE_DEMO` (default **True** when the structural graph is ready; still skips heavy JSONL parse/build under Colab-safe unless `ALLOW_JSONL_GRAPH_REBUILD=True`).

Demos (read-only / bounded):
1. Module inventory + live service handles (`loader`, `builder`, `traversal`, `overlay_joiner`, `context_builder`, `expansion`)
2. Direct [`GraphTraversal`](../src/knowledge_graph/traversal.py) modes (`basis` / `guidance` / `validity` / `structure` / `neighbors`)
3. [`ContextBuilder.build_evidence_context`](../src/knowledge_graph/context.py) + citation context
4. Direct [`OverlayJoiner`](../src/knowledge_graph/overlay.py) sample (when overlay files exist)
5. Optional facade `parse_sources` / `build_graph` **only** when JSONL rebuild is permitted

Primary hybrid path (`run_hybrid_retrieve` / `GraphExpansion`) remains unchanged.
"""


FULL_MODULE_CODE = r'''# ### FULL_GRAPH_MODULE — service handles + inventory + demos for all graph layers
# Keeps primary hybrid path intact; demos are read-only / bounded (005-safe).

# Live service handles populated after Stage C load (None when graph unavailable)
kg_loader: GraphLoader | None = None
kg_builder: GraphBuilder | None = None
kg_overlay_joiner: OverlayJoiner | None = None
kg_context_builder: ContextBuilder | None = None
kg_traversal: GraphTraversal | None = None
kg_parsed_sources: ParsedGraphSources | None = None
full_graph_module_demo: dict[str, Any] | None = None

if kg_facade is not None:
    kg_loader = kg_facade.loader
    kg_builder = kg_facade.builder
    kg_overlay_joiner = kg_facade.overlay_joiner
    kg_context_builder = kg_facade.context_builder
if kg_facade is not None and kg_graph is not None:
    kg_traversal = kg_facade.build_traversal(kg_graph)


@dataclass
class GraphModuleInventoryRow:
    layer: str
    module_file: str
    status: str
    detail: str


def inventory_graph_modules() -> list[GraphModuleInventoryRow]:
    """Report which graph layers are importable and which live services are wired."""
    rows: list[GraphModuleInventoryRow] = []

    def add(layer: str, module_file: str, ready: bool, detail: str) -> None:
        rows.append(
            GraphModuleInventoryRow(
                layer=layer,
                module_file=module_file,
                status='ready' if ready else 'not_wired',
                detail=detail,
            )
        )

    add('loader', 'loader.py', kg_loader is not None, type(kg_loader).__name__ if kg_loader else 'GraphLoader not attached')
    add('parser/schema', 'parser.py + schema.py', True, 'parse_* / node types imported on package surface')
    add('edge_parser', 'edge_parser.py + edge_schema.py', True, 'GraphEdge + parse_edge_rows imported')
    add('builder', 'builder.py', kg_builder is not None or kg_graph is not None,
        f'builder={type(kg_builder).__name__ if kg_builder else None}; graph_loaded={kg_graph is not None}')
    add('persist', 'persist.py', True, f'FORMAT={FORMAT_NAME} v{FORMAT_VERSION}; pickle_mode={graph_load_status.graph_source_mode}')
    add('expansion', 'expansion.py', graph_expansion is not None, 'primary hybrid path')
    add('traversal', 'traversal.py', kg_traversal is not None, 'direct GraphTraversal + facade.traverse')
    add('overlay', 'overlay.py', kg_overlay_joiner is not None,
        f'joiner_ready; overlays_ready={graph_load_status.overlays_ready}; n={len(document_overlays)}')
    add('context', 'context.py', kg_context_builder is not None, 'ContextBuilder + EvidenceContext / GraphGuidedFilter')
    add('facade', 'facade.py', kg_facade is not None, type(kg_facade).__name__ if kg_facade else 'missing')
    add('utils', 'utils.py', True, f'as_int/as_bool/quality_flags via knowledge_graph.utils')
    return rows


def print_graph_module_inventory() -> list[GraphModuleInventoryRow]:
    rows = inventory_graph_modules()
    print('=== Full Graph Module inventory ===')
    print(f'structural_ready={graph_load_status.structural_ready} source={graph_load_status.graph_source_mode}')
    for row in rows:
        print(f'  [{row.status:10}] {row.layer:14} | {row.module_file:28} | {row.detail}')
    return rows


def _pick_demo_start_id(preferred: str | None = None) -> str | None:
    """Choose a document id_str for traversal/context demos."""
    sid = (preferred or GRAPH_GUIDED_START_ID or '').strip()
    if sid:
        return sid
    if kg_graph is None:
        return None
    if kg_graph.verified_document_edges:
        for edge in kg_graph.verified_document_edges:
            if edge.src_id in kg_graph.documents:
                return edge.src_id
    if kg_graph.documents:
        return next(iter(kg_graph.documents.keys()))
    return None


def run_traversal_modes_demo(
    start_id: str | None = None,
    *,
    max_depth: int = 2,
    modes: tuple[str, ...] = ('basis', 'guidance', 'validity', 'structure', 'neighbors'),
) -> dict[str, TraversalResult]:
    """Exercise GraphTraversal directly (all modes) via facade.build_traversal."""
    require_graph_for_hybrid('full GraphTraversal demo')
    assert kg_facade is not None and kg_graph is not None
    traversal_svc = kg_facade.build_traversal(kg_graph)
    global kg_traversal
    kg_traversal = traversal_svc

    sid = _pick_demo_start_id(start_id)
    if not sid:
        raise RuntimeError('No start id_str available for traversal demo.')

    print('=== GraphTraversal modes demo (direct service) ===')
    print('start_id:', sid)
    print('max_depth:', max_depth)
    results: dict[str, TraversalResult] = {}
    for mode in modes:
        result = traversal_svc.traverse(sid, mode=mode, max_depth=max_depth)  # type: ignore[arg-type]
        results[mode] = result
        print(
            f'  mode={mode:10} visited={len(result.visited_ids):4} '
            f'edges={len(result.visited_edges):4} paths={len(result.paths):4}'
        )
    return results


def run_evidence_context_demo(
    start_id: str | None = None,
    *,
    mode: str = 'basis',
    max_depth: int = 2,
    filter_profile: str = 'current_law',
) -> EvidenceContext:
    """Build EvidenceContext + citation context via ContextBuilder (through facade)."""
    require_graph_for_hybrid('EvidenceContext demo')
    assert kg_facade is not None and kg_graph is not None

    sid = _pick_demo_start_id(start_id)
    if not sid:
        raise RuntimeError('No start id_str available for evidence context demo.')

    traversal = kg_facade.traverse(
        kg_graph,
        start_id=sid,
        mode=mode,  # type: ignore[arg-type]
        max_depth=max_depth,
    )
    overlays = document_overlays if graph_load_status.overlays_ready else {}
    constraints = QueryConstraints(validity_groups=('active', 'partial', 'future'))
    evidence = kg_facade.build_evidence_context(
        graph=kg_graph,
        traversal=traversal,
        overlays=overlays,
        filter_profile=filter_profile,  # type: ignore[arg-type]
        constraints=constraints,
    )
    citations = kg_facade.build_citation_context(
        graph=kg_graph,
        traversal=traversal,
        overlays=overlays,
        filter_profile=filter_profile,  # type: ignore[arg-type]
        constraints=constraints,
    )
    print('=== EvidenceContext / citation context demo ===')
    print('start_id:', sid, '| traversal_mode:', mode)
    print('filter empty_warning:', evidence.filter.empty_filter_warning)
    print('filter profile:', evidence.filter.filter_profile)
    print('documents in evidence:', len(evidence.documents))
    print('overlays attached:', len(evidence.overlays))
    print('paths:', len(evidence.paths))
    print('warnings:', evidence.warnings or ())
    print('citation ids (sample):', list(citations)[:8])
    return evidence


def run_overlay_joiner_sample(limit: int = 3) -> dict[str, Any]:
    """Show OverlayJoiner direct usage + currency histogram sample (no mutation)."""
    out: dict[str, Any] = {'ready': False}
    if kg_overlay_joiner is None:
        print('OverlayJoiner not wired (facade missing).')
        return out
    if not graph_load_status.overlays_ready or not document_overlays:
        print('Overlays unavailable — OverlayJoiner is imported/wired but no overlay files joined.')
        out['ready'] = False
        out['reason'] = 'overlays_missing'
        return out

    sample_ids = list(document_overlays.keys())[: max(1, limit)]
    samples = []
    for id_str in sample_ids:
        ov = document_overlays[id_str]
        samples.append({
            'id_str': id_str,
            'currency_status': ov.currency_status,
            'currency_status_as_of': ov.currency_status_as_of,
            'legal_authority_rank': ov.legal_authority_rank,
            'authority_rank_source': ov.authority_rank_source,
        })
    hist: dict[str, int] = {}
    for ov in document_overlays.values():
        hist[ov.currency_status] = hist.get(ov.currency_status, 0) + 1
    print('=== OverlayJoiner sample (joined DocumentOverlay) ===')
    print('joiner class:', type(kg_overlay_joiner).__name__)
    print('document_overlays:', len(document_overlays))
    print('currency histogram:', hist)
    print('sample rows:')
    for row in samples:
        print(' -', row)
    # utils smoke (same helpers overlay parsers use)
    print('utils smoke: as_int("3")=', as_int('3'), 'as_bool("yes")=', as_bool('yes'),
          'quality_flags([" a ", ""])=', quality_flags([' a ', '']))
    out.update({'ready': True, 'histogram': hist, 'samples': samples})
    return out


def run_loader_builder_optional() -> dict[str, Any]:
    """Optional JSONL parse/build visibility — only when rebuild is permitted.

    Colab-safe pickle sessions skip this to avoid multi-GB structural rebuilds.
    """
    report: dict[str, Any] = {'ran': False}
    if kg_facade is None:
        print('Facade missing — skip loader/builder optional demo.')
        return report
    if graph_load_status.graph_source_mode == 'jsonl_rebuild' and kg_build_result is not None:
        stats = kg_build_result.stats
        print('=== Loader/Builder already exercised via JSONL rebuild ===')
        print('documents:', stats.document_count, 'chunks:', stats.chunk_count,
              'verified_edges:', stats.verified_document_edge_count)
        report.update({'ran': True, 'path': 'jsonl_rebuild_already', 'stats': stats})
        return report
    if not ALLOW_JSONL_GRAPH_REBUILD:
        print(
            '=== Loader/Builder optional demo SKIPPED ===\n'
            '  Structural JSONL parse/build is heavy. Set ALLOW_JSONL_GRAPH_REBUILD=True\n'
            '  (and prefer unconstrained profile) to exercise GraphLoader.parse_sources / GraphBuilder.\n'
            f'  Current mode={graph_load_status.graph_source_mode}; pickle preferred under Colab-safe.'
        )
        report.update({'ran': False, 'reason': 'allow_jsonl_rebuild_false'})
        return report

    print('=== Optional facade.parse_sources (JSONL) ===')
    try:
        parsed = kg_facade.parse_sources()
        global kg_parsed_sources
        kg_parsed_sources = parsed
        print('ParsedGraphSources counts:')
        print('  documents:', len(parsed.documents))
        print('  external_stubs:', len(parsed.external_stubs))
        print('  provisions:', len(parsed.provisions))
        print('  chunks:', len(parsed.chunks))
        print('  edges:', len(parsed.edges))
        print('  text_provenance keys:', len(parsed.text_provenance))
        report.update({
            'ran': True,
            'path': 'parse_sources',
            'counts': {
                'documents': len(parsed.documents),
                'external_stubs': len(parsed.external_stubs),
                'provisions': len(parsed.provisions),
                'chunks': len(parsed.chunks),
                'edges': len(parsed.edges),
            },
        })
    except Exception as exc:
        print('parse_sources failed:', exc)
        report.update({'ran': False, 'error': str(exc)})
    return report


def run_full_graph_module_demo(
    *,
    start_id: str | None = None,
    include_jsonl_parse: bool | None = None,
) -> dict[str, Any]:
    """Orchestrate inventory + traversal + evidence + overlay + optional parse demos."""
    summary: dict[str, Any] = {
        'inventory': [],
        'traversal': None,
        'evidence': None,
        'overlay': None,
        'loader_builder': None,
    }
    summary['inventory'] = print_graph_module_inventory()
    if not graph_load_status.structural_ready or kg_graph is None or kg_facade is None:
        print('Structural graph not ready — full module demos that need a live graph are skipped.')
        print('Imports still cover the entire package surface (see previous cell).')
        return summary

    summary['traversal'] = run_traversal_modes_demo(start_id=start_id, max_depth=GRAPH_GUIDED_MAX_DEPTH)
    summary['evidence'] = run_evidence_context_demo(
        start_id=start_id,
        mode=GRAPH_GUIDED_TRAVERSAL_MODE,
        max_depth=GRAPH_GUIDED_MAX_DEPTH,
        filter_profile=FILTER_PROFILE,
    )
    summary['overlay'] = run_overlay_joiner_sample()
    do_jsonl = ALLOW_JSONL_GRAPH_REBUILD if include_jsonl_parse is None else include_jsonl_parse
    if do_jsonl:
        summary['loader_builder'] = run_loader_builder_optional()
    else:
        summary['loader_builder'] = run_loader_builder_optional()  # still prints skip reason
    print('\nFull Graph Module demo complete (primary hybrid path unchanged).')
    return summary


# Default: run lightweight full-module demos when graph is ready.
# Heavy JSONL parse remains gated by ALLOW_JSONL_GRAPH_REBUILD.
ENABLE_FULL_GRAPH_MODULE_DEMO = globals().get('ENABLE_FULL_GRAPH_MODULE_DEMO', True)

if ENABLE_FULL_GRAPH_MODULE_DEMO:
    full_graph_module_demo = run_full_graph_module_demo()
else:
    print('ENABLE_FULL_GRAPH_MODULE_DEMO=False — inventory/services still defined; demos not run.')
    print_graph_module_inventory()
'''


def patch_intro(cell: dict) -> None:
    text = cell_text(cell)
    if "Full Graph Module orchestration" in text and "loader.py" in text:
        return
    # Expand architecture bullet for knowledge graph
    old = (
        "- Knowledge graph: [`KnowledgeGraphFacade`](../src/knowledge_graph/facade.py), "
        "pickle load ([`load_knowledge_graph`](../src/knowledge_graph/persist.py)), "
        "[`GraphExpansion`](../src/knowledge_graph/expansion.py)"
    )
    new = (
        "- Knowledge graph: full [`src/knowledge_graph/`](../src/knowledge_graph/) package — "
        "[`KnowledgeGraphFacade`](../src/knowledge_graph/facade.py), "
        "[`GraphExpansion`](../src/knowledge_graph/expansion.py) (primary), "
        "[`GraphTraversal`](../src/knowledge_graph/traversal.py) (secondary), "
        "overlay/context/builder/loader/persist"
    )
    if old in text:
        text = text.replace(old, new)
    else:
        # fallback insert after Architecture heading line if present
        text = text.replace(
            "- Knowledge graph:",
            "- Knowledge graph (full package):",
        )
    # Primary vs secondary already exists; add full-module note
    note = (
        "\n\n**Full Graph Module coverage**\n"
        "Stage C imports the entire public `knowledge_graph` surface and wires live services "
        "(`GraphLoader`, `GraphBuilder`, `GraphTraversal`, `OverlayJoiner`, `ContextBuilder`, "
        "`GraphExpansion`, persist helpers). See §4.4 demos after hybrid load.\n"
    )
    if "Full Graph Module coverage" not in text:
        # insert before the demonstration note if present
        anchor = "**Note:** Demonstration notebook"
        if anchor in text:
            text = text.replace(anchor, note.lstrip() + "\n" + anchor)
        else:
            text = text.rstrip() + note
    set_source(cell, text)


def patch_config_cell(cell: dict) -> None:
    text = cell_text(cell)
    if "ENABLE_FULL_GRAPH_MODULE_DEMO" in text:
        return
    insertion = (
        "\n# Full Graph Module demos (inventory + traversal modes + EvidenceContext + overlay sample)\n"
        "# Lightweight when pickle-loaded; JSONL parse/build still gated by ALLOW_JSONL_GRAPH_REBUILD.\n"
        "ENABLE_FULL_GRAPH_MODULE_DEMO = True\n"
    )
    # place after ENABLE_GRAPH_GUIDED_PREFILTER_DEMO assignment if present
    m = re.search(r"^ENABLE_GRAPH_GUIDED_PREFILTER_DEMO\s*=.*$", text, flags=re.M)
    if m:
        idx = m.end()
        text = text[:idx] + insertion + text[idx:]
    else:
        text = text.rstrip() + insertion
    # also print the flag near other prints
    if "print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:" in text and "ENABLE_FULL_GRAPH_MODULE_DEMO" not in text.split("print(")[-1]:
        text = text.replace(
            "print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)",
            "print('ENABLE_GRAPH_GUIDED_PREFILTER_DEMO:', ENABLE_GRAPH_GUIDED_PREFILTER_DEMO)\n"
            "print('ENABLE_FULL_GRAPH_MODULE_DEMO:', ENABLE_FULL_GRAPH_MODULE_DEMO)",
        )
    set_source(cell, text)


def patch_load_cell(cell: dict) -> None:
    """After successful graph wire, attach service handles comments (handles set in FULL cell)."""
    text = cell_text(cell)
    if "FULL_GRAPH_MODULE service handles" in text:
        return
    # After GraphExpansion wired messages, note that full module cell attaches services
    needle = "print('Label reminder: graph_expansion ≠ local_expand_units')"
    if needle in text:
        text = text.replace(
            needle,
            needle
            + "\n"
            + "        # FULL_GRAPH_MODULE service handles (loader/builder/traversal/overlay/context)\n"
            + "        # are attached in the following full-module cell once this load succeeds.\n"
            + "        print('Full Graph Module services will attach in the next Stage C cell.')",
        )
    needle2 = "print('\\nGraphExpansion wired after JSONL rebuild.')"
    if needle2 in text:
        text = text.replace(
            needle2,
            needle2
            + "\n"
            + "        print('Full Graph Module services will attach in the next Stage C cell.')",
        )
    set_source(cell, text)


def patch_demo_cell(cell: dict) -> None:
    """Keep hybrid demos; mention full-module cell runs separately."""
    text = cell_text(cell)
    if "FULL_GRAPH_MODULE demos run in" in text:
        return
    footer = (
        "\n\n# FULL_GRAPH_MODULE demos run in the dedicated Stage C cell (§4.4),\n"
        "# not inside this hybrid smoke cell — keeps primary hybrid path focused.\n"
        "if 'print_graph_module_inventory' in globals() and graph_load_status.structural_ready:\n"
        "    print('Full Graph Module helpers available: inventory_graph_modules, '\n"
        "          'run_traversal_modes_demo, run_evidence_context_demo, run_full_graph_module_demo')\n"
    )
    if "run_full_graph_module_demo" not in text:
        text = text.rstrip() + footer
    set_source(cell, text)


def main() -> None:
    nb = json.loads(NOTEBOOK_PATH.read_text())
    cells = nb["cells"]

    # Remove previous FULL_GRAPH_MODULE cells (idempotent re-run)
    cells = [c for c in cells if not is_full_module_cell(c)]

    # Identify key cells by content
    intro_idx = None
    config_idx = None
    stage_c_md_idx = None
    import_idx = None
    load_idx = None
    hybrid_helper_idx = None
    hybrid_demo_md_idx = None
    hybrid_demo_idx = None

    for i, cell in enumerate(cells):
        text = cell_text(cell)
        if cell["cell_type"] == "markdown" and text.lstrip().startswith("# FAISS Vector Retrieval"):
            intro_idx = i
        if "RUNTIME_PROFILE" in text and "GRAPH_PICKLE_PATH" in text and cell["cell_type"] == "code":
            config_idx = i
        if "Hybrid graph integration (vector-first)" in text and cell["cell_type"] == "markdown":
            stage_c_md_idx = i
        if "intended import surface (FR-002)" in text or (
            "from knowledge_graph import" in text and "GraphExpansion" in text and "HYBRID_GRAPH_INTEGRATION" in text
        ):
            if cell["cell_type"] == "code" and "preflight_graph_sources" not in text:
                import_idx = i
        if "preflight_graph_sources" in text and "graph_source_mode" in text:
            load_idx = i
        if "def run_hybrid_retrieve" in text:
            hybrid_helper_idx = i
        if "Hybrid expansion demo" in text and cell["cell_type"] == "markdown":
            hybrid_demo_md_idx = i
        if "def show_hybrid_diagnostics" in text or "def compare_vector_vs_hybrid" in text:
            hybrid_demo_idx = i

    if intro_idx is not None:
        patch_intro(cells[intro_idx])
    if config_idx is not None:
        patch_config_cell(cells[config_idx])
    if stage_c_md_idx is not None:
        set_source(cells[stage_c_md_idx], STAGE_C_MD)
    if import_idx is not None:
        set_source(cells[import_idx], IMPORT_CELL)
    else:
        raise SystemExit("Could not find Stage C import cell")
    if load_idx is not None:
        patch_load_cell(cells[load_idx])
    if hybrid_demo_idx is not None:
        patch_demo_cell(cells[hybrid_demo_idx])

    # Insert full module md+code after hybrid helper cell (before optional Stage E)
    insert_at = (hybrid_helper_idx + 1) if hybrid_helper_idx is not None else (load_idx + 1 if load_idx is not None else len(cells))
    full_cells = [md(FULL_MODULE_MD), code(FULL_MODULE_CODE)]
    cells = cells[:insert_at] + full_cells + cells[insert_at:]

    nb["cells"] = cells
    NOTEBOOK_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"Patched {NOTEBOOK_PATH}")
    print(f"cells now: {len(cells)}")
    print(f"insert_at={insert_at} import_idx={import_idx} load_idx={load_idx} hybrid_helper_idx={hybrid_helper_idx}")


if __name__ == "__main__":
    main()
