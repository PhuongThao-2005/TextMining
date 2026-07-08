#!/usr/bin/env python3
"""Build the G-LRAG v2 dataset package (Dataset_SPEC_v2.md).

Runs the four-layer pipeline end to end:

    Layer 1  NORMALIZED  documents / edges / external_stubs / authority_index / vocab
    Layer 2  STRUCTURED  text_provenance / provisions / chunks
    Layer 3  DERIVED     validity_timeline
    AUDIT                reconciliation_report.md (+ *_quarantine.jsonl)

Usage:
    python scripts/build_dataset_v2.py               # full run
    python scripts/build_dataset_v2.py --limit 500   # smoke test on 500 docs
    python scripts/build_dataset_v2.py --skip-text   # Layer 1 + 3 only

Run from the ``Project/`` directory (or anywhere; paths self-resolve).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so progress lines with
# Vietnamese text never crash the run (output files are UTF-8 regardless).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Make ``src`` importable when launched as a plain script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from data.pipeline import config as C          # noqa: E402
from data.pipeline import derive, normalize, report, structure  # noqa: E402
from data.pipeline.io_utils import read_jsonl   # noqa: E402


def collect_doc_dates() -> dict:
    """Minimal id_str -> dates map for validity-event dating (from Layer 1)."""
    out = {}
    for d in read_jsonl(C.DOCUMENTS_OUT):
        out[d["id_str"]] = {
            "ngay_ban_hanh_iso": d.get("ngay_ban_hanh_iso"),
            "ngay_co_hieu_luc_iso": d.get("ngay_co_hieu_luc_iso"),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the v2 dataset package.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Structure only N documents (smoke test).")
    ap.add_argument("--skip-text", action="store_true",
                    help="Skip Layer 2 text structuring.")
    args = ap.parse_args()

    for required in (C.METADATA_IN, C.REL_IN, C.CONTENT_IN):
        if not required.exists():
            print(f"ERROR: missing raw input {required}", file=sys.stderr)
            return 2

    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("[1/4] Layer 1 — NORMALIZED (documents, edges, stubs, authority, vocab)")
    norm = normalize.run()

    struct_counts = {}
    if args.skip_text:
        print("[2/4] Layer 2 — STRUCTURED  (skipped: --skip-text)")
    else:
        print("[2/4] Layer 2 — STRUCTURED (text_provenance, provisions, chunks)")
        struct_counts = structure.run(norm, limit=args.limit)
        print(f"      provisions: {struct_counts.get('provisions_final', 0):,} | "
              f"chunks: {struct_counts.get('chunks_final', 0):,} | "
              f"text_available: {struct_counts.get('text_available', 0):,} | "
              f"missing: {struct_counts.get('text_missing', 0):,}")

    print("[3/4] Layer 3 — DERIVED (validity_timeline)")
    derive_counts = derive.run(collect_doc_dates())

    print("[4/4] AUDIT — reconciliation_report.md")
    report.write(norm.counts, struct_counts, derive_counts)

    dt = time.time() - t0
    print(f"\nDone in {dt:,.1f}s. Output package -> {C.OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
