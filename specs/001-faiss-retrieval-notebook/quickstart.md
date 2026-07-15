# Quickstart: Full FAISS Retrieval System Notebook (SQLite cache + reasoning generator)

Validation guide for running [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) end-to-end after implementation. This is **not** the implementation itself — see [`plan.md`](plan.md), [`data-model.md`](data-model.md), and [`research.md`](research.md) for design. Task breakdown belongs in `tasks.md` (via `/speckit-tasks`).

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.13 kernel | Same env as the rest of `src/` (verified via `python --version`) |
| Packages | `faiss-cpu` 1.13.2, `openai` 2.38.0, `sentence-transformers`, `pandas`, `ipykernel` / Jupyter (already listed in the notebook's own `%pip install` cell) |
| FAISS index on disk | `data/faiss_index/` built by [`src/retrieval/build_vector_db.py`](../../src/retrieval/build_vector_db.py) / [`scripts/build_vector_index.py`](../../scripts/build_vector_index.py) |
| Benchmark file on disk | `data/benchmark/qa_final.jsonl` (frozen QA benchmark) |
| Generator credentials (optional) | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME` env vars, pointing at any OpenAI-compatible chat completion endpoint |
| Working directory | Project root **or** `notebooks/` (root resolution is automatic, FR-013) |

### Expected `data/faiss_index/` artifacts (preflight)

```text
data/faiss_index/
  index.faiss              # required
  payloads.jsonl           # required (source of truth for payload metadata)
  id_map.json              # optional
  payload_cache.sqlite     # optional — already uploaded; accelerates payload lookup (FR-015/FR-016)
```

If `index.faiss` or `payloads.jsonl` is missing, the preflight cell must list it and stop before loading (FR-001). If `payload_cache.sqlite` is missing or stale, the notebook rebuilds it automatically (FR-016) rather than failing.

## Setup (once)

From project root:

```powershell
# Optional: confirm deps
python -c "import faiss, openai, sentence_transformers, pandas; print(faiss.__version__, openai.__version__)"

# Unit tests for the extracted modules (after implementation)
python -m pytest tests/retrieval/test_sqlite_faiss_store.py tests/generation/test_reasoning_client.py -q
```

Set generator credentials (optional — retrieval-only mode works without them):

```powershell
$env:LLM_BASE_URL = "https://api.example.com/v1"
$env:LLM_API_KEY = "sk-..."
$env:LLM_MODEL_NAME = "your-model-name"
```

Open the notebook:

- VS Code / Cursor: open [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) and select the project Python kernel.
- Or Jupyter: `jupyter notebook notebooks/faiss_retrieval_ready.ipynb` (from project root).

## Config cell (top of notebook)

Set these near the top; do not hardcode them deeper in the notebook (FR-003):

| Parameter | Default (suggested) | Purpose |
| --- | --- | --- |
| `EMBEDDING_MODEL_NAME` | existing project default | Passed to `SentenceTransformerEmbedder` |
| `TOP_K` | `50` | Candidate pool before rerank |
| `TOP_N` | `5` | Final results returned per query |
| `SCORE_THRESHOLD` | `0.0` (or existing project default) | Minimum vector score to keep a candidate |
| `EXPAND_UNITS` | `True` | Enable same-provision sibling-chunk expansion (FR-009) |
| `DEFAULT_FILTER_PROFILE` | `"current_law"` | One of `current_law` / `broad` / `historical` |
| `BENCHMARK_SAMPLE_SIZE` | `20` | Rows sampled from `qa_final.jsonl` (FR-007) |

Generator config, read from environment (never hardcoded, FR-017/FR-018):

| Env var | Purpose |
| --- | --- |
| `LLM_BASE_URL` | OpenAI-compatible endpoint base URL |
| `LLM_API_KEY` | API key — read only, never printed raw, masked on display |
| `LLM_MODEL_NAME` | Model identifier passed to the chat completion call |

Project root is resolved via the existing `resolve_project_root()` cell (cwd if `src/` exists, else parent).

## Run order (top to bottom)

1. **Environment + path** — put `src/` on `sys.path`, resolve project root, `%pip install` if needed.
2. **Config** — parameters above.
3. **Preflight** — verify `index.faiss` / `payloads.jsonl` exist (FR-001).
4. **Load index + payload store** — `SQLitePayloadFaissVectorStore.load(INDEX_DIR)` (imported from [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py)); staleness check + rebuild happens here if `payload_cache.sqlite` is missing/stale (FR-015/FR-016).
5. **4.1/4.2 — export helpers** — CSV export and Colab/Drive SQLite export (unchanged).
6. **Search + display helpers** — `search()`, `show_results()` (FR-004).
7. **Filter profile comparison** — run the same query under `current_law`/`broad`/`historical` (FR-005, US3).
8. **Benchmark mode** — `run_benchmark_sample()` over `qa_final.jsonl` sample (FR-006/FR-007, US2).
9. **Single-chunk inspection** — full `chunk_text` + payload keys for one result (FR-011).
10. **Generator configuration** — read `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_NAME`, print masked confirmation (FR-017/FR-018).
11. **Generator client + reasoning parsing** — imports from [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py); `ANSWER_PROMPT` now explicitly requests a reasoning section (FR-019); `parse_generation_response()` splits answer from reasoning (FR-020/FR-021).
12. **Full pipeline (`ask()`)** — retrieve + generate for one sample question, displays answer and reasoning as two distinct sections (FR-022, US4).
13. **Benchmark + generation** — optionally extend the Section 8 sample with per-question `GenerationOutcome` records, reusing retrieval output without re-querying (FR-022/FR-023).

Stop only if preflight shows critical files missing; otherwise incomplete sections should flag and continue.

## Validation scenarios

### V1 — Happy path (retrieval only)

**Given** `data/faiss_index/` populated with `index.faiss` and `payloads.jsonl` (no cache yet).

**When** all cells through Section 9 run in order.

**Then**:

| Check | Expected |
| --- | --- |
| SC-001 | No unhandled exception; notebook completes top to bottom |
| SC-002 | Preflight reports readiness in well under 5s |
| SC-004 | Same query run under all 3 filter profiles shows distinct candidate counts |
| SC-005 | Every displayed result includes citation anchor/label, title, vector + rerank scores |

### V2 — SQLite cache reuse and staleness (US1 scenario 3, FR-015/FR-016, SC-006)

**Given** `payload_cache.sqlite` already exists and is fresh (size/mtime match `payloads.jsonl`).

**When** the load cell (Section 4) runs.

**Then** the notebook reuses the cache (no full `payloads.jsonl` re-scan) and startup is noticeably faster than a from-scratch build — confirm by timing both paths once (delete cache, time cold load; re-run, time warm load).

**Given** the cache file is then made stale (touch `payloads.jsonl` to bump its mtime, or edit its size).

**When** the load cell re-runs.

**Then** the notebook detects the mismatch and rebuilds the cache automatically, printing that a rebuild occurred (not silent).

### V3 — Reasoning extraction, three response shapes (US4 scenarios 2-3, FR-020/FR-021, SC-007)

**Given** a configured `GeneratorClient` (or a fake client in unit tests) whose response provides:

1. A `reasoning_content` field — **then** the notebook displays reasoning from that field, separate from the answer.
2. No field, but a `<think>...</think>` block inside `content` — **then** the notebook extracts and displays the block as reasoning, and the answer text has the block stripped.
3. Neither — **then** the notebook displays the answer and labels reasoning as "not returned by this model" (never blank, never fabricated).

### V4 — Batch generation with a forced failure (US4 scenario 4, FR-022/FR-023, SC-008)

**Given** a benchmark sample where one question's generator call is made to raise (e.g., simulate a timeout).

**When** the benchmark + generation cell runs over the sample.

**Then** that question's record shows a non-fatal recorded error, and every other question in the sample still gets a `GenerationOutcome` (answer+reasoning, or its own error) — the run does not stop early.

### V5 — Missing/invalid `api_key` (US4 scenario 5, FR-018)

**Given** `LLM_API_KEY` unset or empty.

**When** the generation configuration cell runs.

**Then** the notebook prints "Generator not fully configured..." and does not attempt any API call; retrieval sections remain fully usable. If a key is set but rejected by the provider (401), the generation cell surfaces a clear auth error without ever printing the raw key value.

### V6 — Unit tests (modules only)

```powershell
python -m pytest tests/retrieval/test_sqlite_faiss_store.py -q
python -m pytest tests/generation/test_reasoning_client.py -q
```

**Then** synthetic fixtures cover at least:

- `payload_cache.sqlite` staleness detection: fresh, missing, stale-by-size, stale-by-mtime
- `search()`/`scroll()` correctness against a small synthetic FAISS index + payloads fixture
- `parse_generation_response()` for all three reasoning-shape cases plus an unterminated `<think>` tag
- `GeneratorConfig.masked_key()` never returns the raw key; no exception message from `GeneratorClient` embeds the raw key

Do **not** point unit tests at a real API endpoint or the production FAISS index — use `tmp_path` fixtures and a fake OpenAI client.

## Runtime expectations

| Section | I/O character | Memory note |
| --- | --- | --- |
| Index + payload load (cold, no cache) | Full `payloads.jsonl` scan, one-time SQLite build | Proportional to payload file size |
| Index + payload load (warm, valid cache) | Indexed SQLite row lookups only | Small, bounded by `top_k` per query |
| Retrieval (search/benchmark) | FAISS in-memory search + per-hit SQLite/payload lookup | Bounded by `top_k`/`top_n`, not corpus size |
| Generation (ad hoc or batch) | One network call per question to the configured endpoint | Network/provider latency-bound, outside this notebook's control |

## Out of scope (do not expect in this notebook)

- Building or mutating `data/faiss_index/` from raw `chunks.jsonl`/`provisions.jsonl`/`documents.jsonl` (that's [`scripts/build_vector_index.py`](../../scripts/build_vector_index.py))
- Knowledge-graph-guided retrieval (`graph_guided` filter profile is labeled "not exercised here", FR-010)
- Automated answer-correctness judging/scoring — this notebook displays reasoning for manual review only (FR-024); see [`scripts/evaluate_e2e.py`](../../scripts/evaluate_e2e.py) for the judged evaluation pipeline
- Verifying that a model's displayed reasoning is factually correct — only that it is displayed distinctly when returned (spec Assumptions)

## After implementation — acceptance checklist

- [ ] `pytest tests/retrieval/test_sqlite_faiss_store.py` green
- [ ] `pytest tests/generation/test_reasoning_client.py` green
- [ ] Notebook runs from project root
- [ ] Notebook runs from `notebooks/`
- [ ] Preflight reports missing FAISS files without crashing
- [ ] Fresh `payload_cache.sqlite` is reused; stale cache is detected and rebuilt automatically
- [ ] All three filter profiles run and show distinct results in the same session
- [ ] Same-provision expansion demonstrated with at least one example
- [ ] Generator config never prints a raw `api_key`, in success or error paths
- [ ] Reasoning is displayed distinctly from the answer for all three response shapes (field, `<think>` block, not returned)
- [ ] A single failed generation call in a batch run does not stop the remaining questions
- [ ] Generation is skipped (not called) when retrieval returns zero chunks for a question

## Next step

Break this plan into implementation tasks:

```text
/speckit-tasks
```

(or the project's equivalent Speckit tasks command targeting `specs/001-faiss-retrieval-notebook`).
