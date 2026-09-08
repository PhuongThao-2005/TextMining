#!/usr/bin/env bash
set -Eeuo pipefail

DENSE_PORT="${DENSE_PORT:-8000}"
BM25_PORT="${BM25_PORT:-8001}"
GRAPH_PORT="${GRAPH_PORT:-8002}"
RERANKER_PORT="${RERANKER_PORT:-8003}"
export DENSE_INDEX_DIR="${DENSE_INDEX_DIR:-/workspace/artifacts/dense}"
export BM25_INDEX_DIR="${BM25_INDEX_DIR:-/workspace/bm25_service/bm25/shards}"
export GRAPH_PICKLE_PATH="${GRAPH_PICKLE_PATH:-/workspace/artifacts/graph/knowledge_graph.gpickle}"
export GRAPH_PAYLOAD_CACHE="${GRAPH_PAYLOAD_CACHE:-/workspace/artifacts/dense/payload_cache.sqlite}"
export HF_HOME="${HF_HOME:-/workspace/artifacts/cache/huggingface}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-${HF_HOME}/hub}"
export SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/workspace/artifacts/cache/sentence-transformers}"
export TORCH_HOME="${TORCH_HOME:-/workspace/artifacts/cache/torch}"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Missing required artifact: $path" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_file "${DENSE_INDEX_DIR}/index.faiss"
require_file "${DENSE_INDEX_DIR}/payloads.jsonl"
require_file "${DENSE_INDEX_DIR}/index_manifest.json"

require_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    echo "Missing required directory: $path" >&2
    exit 1
  fi
}

validate_bm25_layout() {
  require_dir "$BM25_INDEX_DIR"
  shopt -s nullglob
  local shards=("${BM25_INDEX_DIR}"/shard_*/)
  shopt -u nullglob

  if [[ ${#shards[@]} -eq 0 ]]; then
    if [[ -f "${BM25_INDEX_DIR}/bm25_index.pkl" && -f "${BM25_INDEX_DIR}/bm25_metadata.pkl" ]]; then
      echo "BM25 single-index layout detected at ${BM25_INDEX_DIR}"
      return 0
    fi
    echo "BM25_INDEX_DIR must contain shard_* directories with bm25_index.pkl and bm25_metadata.pkl." >&2
    exit 1
  fi

  local shard_dir
  for shard_dir in "${shards[@]}"; do
    require_file "${shard_dir}/bm25_index.pkl"
    require_file "${shard_dir}/bm25_metadata.pkl"
  done
  echo "BM25 sharded layout detected: ${#shards[@]} shard(s) under ${BM25_INDEX_DIR}"
}

validate_bm25_layout

if [[ "${ENABLE_GRAPH:-false}" == "true" ]]; then
  require_file "$GRAPH_PICKLE_PATH"
  require_file "$GRAPH_PAYLOAD_CACHE"
  require_env GRAPH_API_KEY
fi

if [[ "${ENABLE_RERANKER:-false}" == "true" ]]; then
  require_env RERANKER_API_KEY
fi

terminate() {
  local code="${1:-0}"
  if [[ -n "${dense_pid:-}" ]]; then kill "$dense_pid" 2>/dev/null || true; fi
  if [[ -n "${bm25_pid:-}" ]]; then kill "$bm25_pid" 2>/dev/null || true; fi
  if [[ -n "${graph_pid:-}" ]]; then kill "$graph_pid" 2>/dev/null || true; fi
  if [[ -n "${reranker_pid:-}" ]]; then kill "$reranker_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
  exit "$code"
}
trap 'terminate 143' TERM INT

python -m uvicorn services.dense_service:app --host 0.0.0.0 --port "$DENSE_PORT" &
dense_pid="$!"
python -m uvicorn services.bm25_service:app --host 0.0.0.0 --port "$BM25_PORT" &
bm25_pid="$!"
pids=("$dense_pid" "$bm25_pid")

if [[ "${ENABLE_GRAPH:-false}" == "true" ]]; then
  python -m uvicorn services.graph_reranker_service:graph_app --host 0.0.0.0 --port "$GRAPH_PORT" &
  graph_pid="$!"
  pids+=("$graph_pid")
fi

if [[ "${ENABLE_RERANKER:-false}" == "true" ]]; then
  python -m uvicorn services.graph_reranker_service:reranker_app --host 0.0.0.0 --port "$RERANKER_PORT" &
  reranker_pid="$!"
  pids+=("$reranker_pid")
fi

python - <<'PY'
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def probe(url: str, api_key: str, *, attempts: int = 1800, delay: float = 1.0) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    last = None
    for _ in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=5.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"Service did not become ready: {url}; last_error={last}")


dense_port = os.environ.get("DENSE_PORT", "8000")
bm25_port = os.environ.get("BM25_PORT", "8001")
probe(f"http://127.0.0.1:{dense_port}/readyz", os.environ.get("DENSE_API_KEY", ""))
probe(f"http://127.0.0.1:{bm25_port}/healthz", os.environ.get("BM25_API_KEY", ""))
if os.environ.get("ENABLE_GRAPH", "false") == "true":
    graph_port = os.environ.get("GRAPH_PORT", "8002")
    probe(f"http://127.0.0.1:{graph_port}/readyz", os.environ.get("GRAPH_API_KEY", ""))
if os.environ.get("ENABLE_RERANKER", "false") == "true":
    reranker_port = os.environ.get("RERANKER_PORT", "8003")
    probe(f"http://127.0.0.1:{reranker_port}/readyz", os.environ.get("RERANKER_API_KEY", ""))
print("Enabled retrieval services are ready.")
PY

set +e
wait -n "${pids[@]}"
exit_code="$?"
echo "A retrieval service exited unexpectedly; shutting down container." >&2
terminate "$exit_code"
