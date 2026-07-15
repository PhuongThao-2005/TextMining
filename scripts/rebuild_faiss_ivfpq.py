#!/usr/bin/env python3
"""Rebuild a Flat IP FAISS index as compressed IndexIVFPQ (Colab RAM path).

Does **not** touch payloads.jsonl / payload_cache.sqlite / id_map.json.
Only rewrites index.faiss (optionally to a new directory) and writes
index_type.json + a small meta JSON.

Example (in-place after backup):

    python scripts/rebuild_faiss_ivfpq.py \\
        --source-dir data/faiss_index \\
        --dest-dir data/faiss_index_ivfpq \\
        --nlist 4096 --m 64 --nprobe 32

Then point notebooks at the dest dir (copy payloads + sqlite alongside, or
use --copy-sidecar).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from retrieval.faiss_index_types import FaissIndexConfig, rebuild_index_to_ivfpq  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild IndexFlatIP index.faiss as IndexIVFPQ for lower RAM.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing the source index.faiss (usually Flat IP).",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=None,
        help="Output directory for the compressed index (default: <source-dir>_ivfpq).",
    )
    parser.add_argument(
        "--source-index",
        type=Path,
        default=None,
        help="Explicit source index.faiss path (overrides --source-dir/index.faiss).",
    )
    parser.add_argument(
        "--dest-index",
        type=Path,
        default=None,
        help="Explicit dest index.faiss path (overrides --dest-dir/index.faiss).",
    )
    parser.add_argument("--nlist", type=int, default=4096, help="IVF coarse clusters.")
    parser.add_argument("--m", type=int, default=64, help="PQ sub-quantizers (must divide dim).")
    parser.add_argument("--nbits", type=int, default=8, help="Bits per PQ code.")
    parser.add_argument("--nprobe", type=int, default=32, help="Search-time IVF probes.")
    parser.add_argument(
        "--train-size",
        type=int,
        default=None,
        help="Optional train sample size (default: min(ntotal, nlist*39)).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="Reconstruct batch size when reading Flat vectors.",
    )
    parser.add_argument(
        "--copy-sidecar",
        action="store_true",
        help="Copy payloads.jsonl, id_map.json, payload_cache.sqlite into dest-dir.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write compressed index.faiss into source-dir (backs up Flat to index.flat.faiss.bak).",
    )
    args = parser.parse_args()

    source_dir = args.source_dir
    dest_dir = args.dest_dir or Path(str(source_dir) + "_ivfpq")
    if args.in_place:
        dest_dir = source_dir

    source_index = args.source_index or (source_dir / "index.faiss")
    dest_index = args.dest_index or (dest_dir / "index.faiss")

    if args.in_place and source_index.resolve() == dest_index.resolve():
        bak = source_dir / "index.flat.faiss.bak"
        if not bak.exists():
            print(f"Backing up Flat index to {bak}")
            shutil.copy2(source_index, bak)
        else:
            print(f"Backup already exists: {bak}")
        # Rebuild from backup so reconstruct stays exact.
        source_index = bak

    cfg = FaissIndexConfig(
        index_type="ivfpq",
        nlist=args.nlist,
        m=args.m,
        nbits=args.nbits,
        nprobe=args.nprobe,
        train_size=args.train_size,
        seed=args.seed,
    ).normalized()

    dest_dir.mkdir(parents=True, exist_ok=True)
    meta = rebuild_index_to_ivfpq(
        source_index,
        dest_index,
        cfg,
        meta_path=dest_dir / "index.ivfpq.meta.json",
        batch_size=args.batch_size,
    )

    # Sidecar config consumed by SQLitePayloadFaissVectorStore.load / FaissVectorStore.load
    (dest_dir / "index_type.json").write_text(
        json.dumps(cfg.to_meta(), indent=2),
        encoding="utf-8",
    )

    if args.copy_sidecar and not args.in_place:
        for name in ("payloads.jsonl", "id_map.json", "payload_cache.sqlite"):
            src = source_dir / name
            if src.exists():
                dst = dest_dir / name
                print(f"Copying {src} -> {dst}")
                shutil.copy2(src, dst)

    print(json.dumps(meta, indent=2))
    print("Done. Point INDEX_DIR at:", dest_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
