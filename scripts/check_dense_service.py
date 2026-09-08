"""Smoke test the dense endpoint; optionally compare with local FAISS."""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from service.local_env import load_local_env

load_local_env(ROOT)

from retrieval.dense_client import DenseRemoteRetriever

QUESTIONS = [
    "Người lao động được nghỉ phép năm bao nhiêu ngày?",
    "Điều kiện để hợp đồng có hiệu lực là gì?",
    "Doanh nghiệp có nghĩa vụ nộp những loại thuế nào?",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("DENSE_SERVICE_URL"))
    parser.add_argument("--compare-local", action="store_true")
    parser.add_argument("--index-dir", default=str(ROOT / "data/chunk metadata"))
    args = parser.parse_args()
    remote = DenseRemoteRetriever(base_url=args.url or "", api_key=os.environ.get("DENSE_API_KEY"))
    print(json.dumps(remote.check_ready(), ensure_ascii=False))
    local = None
    if args.compare_local:
        from retrieval import SentenceTransformerEmbedder, VectorIndexConfig, VectorRetriever
        from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore
        from service.local_env import configure_local_cache_dirs
        configure_local_cache_dirs(ROOT)
        local = VectorRetriever(config=VectorIndexConfig(top_k=30, top_n=10, expand_units=False),
            embedder=SentenceTransformerEmbedder("intfloat/multilingual-e5-large"),
            store=SQLitePayloadFaissVectorStore.load(Path(args.index_dir), require_existing_cache=True))
    timings = []
    try:
        for profile in ("broad", "current_law", "historical"):
            for query in QUESTIONS:
                started = time.perf_counter()
                result = remote.retrieve(query, filter_profile=profile)
                timings.append((time.perf_counter() - started) * 1000)
                if local:
                    expected = local.retrieve(query, filter_profile=profile)
                    actual_chunks = [(c.chunk_id, c.chunk_text, c.citation_anchor, c.citation_label, c.metadata) for c in result.chunks]
                    expected_chunks = [(c.chunk_id, c.chunk_text, c.citation_anchor, c.citation_label, c.metadata) for c in expected.chunks]
                    if actual_chunks != expected_chunks:
                        raise RuntimeError(f"Local/remote results differ for profile={profile}.")
                    if any(not math.isclose(a.vector_score, b.vector_score, abs_tol=1e-5)
                           for a, b in zip(result.chunks, expected.chunks)):
                        raise RuntimeError(f"Local/remote scores differ for profile={profile}.")
                print(json.dumps({"profile": profile, "chunk_ids": [c.chunk_id for c in result.chunks],
                                  "latency_ms": remote.last_diagnostics["latency_ms"]}, ensure_ascii=False))
    finally:
        if local:
            local.store.conn.close()
    print(f"Smoke checks passed ({len(timings)} searches); mean round-trip: {sum(timings) / len(timings):.0f} ms.")


if __name__ == "__main__":
    main()
