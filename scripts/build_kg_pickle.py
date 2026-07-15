"""Build a portable structural knowledge-graph pickle from v2 JSONL sources.

Operator entrypoint for feature 004-kg-pickle-persist:

    python scripts/build_kg_pickle.py \\
      --data-dir data/v2 \\
      --output data/graph/knowledge_graph.gpickle

Preflights the five structural sources (documents, provisions, chunks, edges,
external_stubs). Quarantine / overlay files are never inputs. On success writes
a versioned ``.gpickle`` via atomic replace and prints core counts + size.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from knowledge_graph import GraphLoaderPaths, KnowledgeGraphFacade, save_knowledge_graph  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build structural KnowledgeGraph pickle from v2 JSONL sources."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "v2",
        help="Directory containing structural v2 JSONL sources (default: data/v2)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "graph" / "knowledge_graph.gpickle",
        help="Output .gpickle path (default: data/graph/knowledge_graph.gpickle)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Acknowledge overwrite of an existing output path after successful rebuild",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    data_dir = args.data_dir.resolve()
    output_path = args.output.resolve()

    print("--------------------------------------------------")
    print("Legal Graph RAG - Structural KG Pickle Build")
    print("--------------------------------------------------")
    print(f"data_dir: {data_dir}")
    print(f"output:   {output_path}")

    if output_path.exists() and not args.force:
        print(
            f"Note: existing artifact at {output_path} will be replaced "
            "only after a fully successful build+save (use --force to silence this note)."
        )
    elif output_path.exists() and args.force:
        print(f"Force: will replace existing artifact at {output_path} after successful save.")

    paths = GraphLoaderPaths(data_dir=data_dir)
    # Quarantine files are never part of GraphLoaderPaths.required_paths()
    try:
        paths.validate()
    except FileNotFoundError as exc:
        print(f"[FAIL] Preflight: {exc}", file=sys.stderr)
        return 1

    facade = KnowledgeGraphFacade(paths=paths)

    print("\n[1/2] Building structural knowledge graph...")
    start = time.time()
    try:
        build_result = facade.build_graph()
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Build error: {exc}", file=sys.stderr)
        return 1
    duration = time.time() - start
    print(f"      Built in {duration:.2f} seconds.")

    stats = build_result.stats
    warnings = build_result.warnings

    print("\n[Build Statistics]")
    print(f"  - Document nodes:      {stats.document_count:,}")
    print(f"  - External Stub nodes: {stats.external_stub_count:,}")
    print(f"  - Provision nodes:     {stats.provision_count:,}")
    print(f"  - Chunk nodes:         {stats.chunk_count:,}")
    print(f"  - Document edges:      {stats.document_edge_count:,}")
    print(f"  - Verified edges:      {stats.verified_document_edge_count:,}")
    print(f"  - Unverified edges:    {stats.unverified_document_edge_count:,}")
    print(f"  - Structural edges:    {stats.structural_edge_count:,}")
    print(f"  - Warnings:            {len(warnings)}")

    print("\n[2/2] Saving portable structural pickle...")
    try:
        artifact = save_knowledge_graph(
            build_result.graph,
            output_path,
            stats=stats,
            warnings=warnings,
            source_data_dir=str(data_dir),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Save error: {exc}", file=sys.stderr)
        return 1

    print(f"      Wrote: {artifact.path}")
    print(f"      format_version: {artifact.format_version}")
    print(f"      created_at_utc: {artifact.created_at_utc}")
    print(f"      byte_size: {artifact.byte_size:,}")
    print("\n[OK] Structural graph pickle ready for transfer/load.")
    print("     Overlays are NOT included; join dynamically after load if needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
