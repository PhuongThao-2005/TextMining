# Implementation Plan: Full FAISS Retrieval System Notebook

**Branch**: `001-faiss-retrieval-notebook` | **Date**: 2026-07-15 | **Spec**: [`specs/001-faiss-retrieval-notebook/spec.md`](spec.md)

**Input**: Feature specification from [`specs/001-faiss-retrieval-notebook/spec.md`](spec.md)

## Summary

Extend the existing top-to-bottom-runnable notebook [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb) so it (1) formally supports the already-uploaded `payload_cache.sqlite` artifact under `data/faiss_index/` as a first-class, staleness-checked cache instead of an inline notebook-only class, and (2) adds a reasoning-capable answer-generation step that calls any OpenAI-compatible chat completion endpoint via user-supplied `base_url`, `api_key`, `model_name`, prompts the model to produce a reasoning/thinking trace alongside its final answer, and displays both distinctly.

Technical approach: extract the two pieces of logic in the notebook that currently exist only as inline cells — `SQLitePayloadFaissVectorStore` (Section 4) and `GeneratorClient` / prompt construction / response parsing (Sections 8–10) — into two small, testable modules: `src/retrieval/sqlite_faiss_store.py` (a `VectorStore` implementation, mirroring [`src/retrieval/faiss_store.py`](../../src/retrieval/faiss_store.py)) and `src/generation/reasoning_client.py` (a thin OpenAI-compatible client plus reasoning/answer parsing, filling in the empty placeholder at [`src/generation/temp.py`](../../src/generation/temp.py)). The notebook keeps its current structure but each cell becomes a thin call into these modules, matching the precedent already set by `002-eda-v2-dataset-notebook`'s own plan (which in turn cites this feature's thin-notebook-over-`src/retrieval/` pattern).

## Technical Context

**Language/Version**: Python 3.13 (verified via `python --version`), run through a Jupyter kernel (`ipykernel`), consistent with the rest of `src/`.

**Primary Dependencies**: `faiss-cpu` 1.13.2, `openai` 2.38.0 (both already installed, verified via `pip show faiss-cpu openai`), `sentence-transformers`, `pandas` — all already declared in the notebook's own `%pip install` cell. No new dependency is introduced; the notebook's existing pip-install cell already lists `openai`, confirming this was anticipated.

**Storage**: Read-only access to `data/faiss_index/index.faiss`, `data/faiss_index/payloads.jsonl`, `data/faiss_index/id_map.json`, and the already-uploaded `data/faiss_index/payload_cache.sqlite` (confirmed present on disk). Read-only access to `data/benchmark/qa_final.jsonl` for the batch/benchmark mode. The notebook does not write to any of these except to (re)build `payload_cache.sqlite` itself when stale/missing, and optionally an exported `payloads_export.csv` / copy of the sqlite file for download (existing Sections 4.1/4.2, unchanged by this plan).

**Testing**: `pytest` (already configured via `pyproject.toml`, `pythonpath = ["src"]`). New unit tests under `tests/retrieval/test_sqlite_faiss_store.py` (staleness detection, cache rebuild, `search`/`scroll` correctness against a tiny synthetic FAISS index + payload file) and `tests/generation/test_reasoning_client.py` (prompt construction, reasoning/answer parsing for `reasoning_content` field, `<think>...</think>` delimited text, and the "no reasoning returned" fallback path — using a fake OpenAI-compatible response object, no real network calls).

**Target Platform**: Local developer machine or hosted notebook environment (e.g., Colab), CPU-only FAISS + sentence-transformers; GPU optional. Runs from either the project root or `notebooks/` (existing root-resolution cell, unchanged).

**Project Type**: Single project — a notebook plus two small supporting library modules and their tests. No frontend/backend split.

**Performance Goals**: Loading `payload_cache.sqlite` (when present and fresh) must be noticeably faster than rebuilding it from `payloads.jsonl` on notebook startup (SC-006) — this already holds today via the batched `INSERT` + `line_no` primary-key lookup design; the plan formalizes and tests the staleness check rather than changing its performance characteristics. No new latency budget is introduced for generation beyond "one LLM call per question," which is inherently network/provider-bound and out of this plan's control.

**Constraints**: `api_key` MUST never be hardcoded or printed in any cell output (FR-018, constitution's "API keys, credentials... MUST be stored and handled securely"); a single generation-call failure (timeout, rate limit, malformed response) MUST NOT abort a batch run (FR-023); generation MUST be skipped (not called with empty context) when retrieval returns zero chunks (Edge Cases); the extracted `SQLitePayloadFaissVectorStore` MUST conform to the existing `VectorStore` ABC contract (`recreate_collection`, `upsert`, `search`, `scroll`) so it is a drop-in alternative to `FaissVectorStore`/`QdrantVectorStore`/`InMemoryVectorStore`.

**Scale/Scope**: One notebook (already ~914 lines / 11 sections, extended not rewritten), two new `src/` modules (~150–250 lines combined, extracted from existing inline code with minimal behavior change), two new test modules. Covers FR-001–FR-024 and SC-001–SC-008 of the updated spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Applicability | Assessment |
| --- | --- | --- |
| I. Legal Evidence Is Ground Truth | Yes | Generated answers (User Story 4) are grounded in retrieved `chunk_text` passed verbatim as context (FR-019); `format_context_for_prompt` already includes citation anchor/label and title per chunk, so the model is prompted with citation-bearing evidence, not bare text. The plan does not change this grounding contract. |
| II. Shared Identity Across Dataset, Vector, and Graph | Yes | The extracted `SQLitePayloadFaissVectorStore` keys its cache by `line_no` and resolves `chunk_id`/`parent_unit_id`/`id_str` from the same payload records `FaissVectorStore` already uses; no new identifiers are introduced. |
| III. Traceability, Reconciliation, and No Silent Data Loss | Yes — core of this feature | Staleness detection (FR-016) is not silent: a stale/missing cache is rebuilt and reported (existing `_ensure_payload_cache` print statements), not silently served as-is. Generation failures are recorded per-question rather than dropped (FR-023); "reasoning not returned" is an explicit label, never fabricated or silently blank (FR-021). |
| IV. Legal Correctness Over Convenience | Yes | The answer prompt instructs the model to answer only from CONTEXT and to say so explicitly when CONTEXT is insufficient (existing `ANSWER_PROMPT` Vietnamese wording, unchanged by this plan); reasoning is displayed for review, not treated as verified fact (spec Assumptions: "does not verify the correctness of the reasoning"). |
| V. Modular, Testable, Reported Pipelines | Yes — drives the design | This plan's core technical decision is extracting the SQLite store and generator client out of notebook-only cells into `src/retrieval/sqlite_faiss_store.py` and `src/generation/reasoning_client.py` with dedicated unit tests, exactly matching "Modules MUST expose clear contracts through schemas, typed data structures, tests" — closing the gap the 002 plan already assumed was closed. |
| VI. Retrieval Quality and Evaluation Are Product Requirements | Partial | This feature's batch mode reports retrieval hit-rate and latency (existing `run_benchmark_sample`, FR-006), satisfying the retrieval-quality half. The generation step is explicitly scoped as a thin demonstration layer, not an evaluation/judge pipeline (FR-024) — so answer-quality scoring is intentionally out of scope here and remains the responsibility of `scripts/evaluate_e2e.py`. |

**Result**: PASS. No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/001-faiss-retrieval-notebook/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created here)
```

No `contracts/` directory: this feature has no API/service boundary of its own — it calls an *external* OpenAI-compatible endpoint as a client, but does not expose one.

### Source Code (repository root)

```text
src/
├── retrieval/
│   ├── sqlite_faiss_store.py   # NEW: SQLitePayloadFaissVectorStore, extracted from the
│   │                            # notebook's Section 4 inline class. Implements the
│   │                            # existing VectorStore ABC (search, scroll,
│   │                            # recreate_collection, upsert) so it is interchangeable
│   │                            # with FaissVectorStore/QdrantVectorStore/InMemoryVectorStore.
│   │                            # Owns: _ensure_payload_cache (staleness check + rebuild),
│   │                            # _load_payloads, _iter_payloads, total_vectors, close.
│   ├── faiss_store.py           # EXISTING — unchanged.
│   ├── stores.py                # EXISTING — VectorStore ABC, SearchHit, payload_matches (reused, unchanged).
│   ├── retriever.py              # EXISTING — VectorRetriever (reused, unchanged).
│   ├── embeddings.py             # EXISTING — SentenceTransformerEmbedder (reused, unchanged).
│   └── config.py                 # EXISTING — VectorIndexConfig (reused, unchanged).
│
└── generation/
    ├── __init__.py               # NEW (package marker; temp.py placeholder is superseded).
    └── reasoning_client.py        # NEW: GeneratorClient (OpenAI-compatible chat completion
                                    # wrapper), ANSWER_PROMPT (reasoning-eliciting variant),
                                    # format_context_for_prompt, parse_generation_response
                                    # (splits reasoning_content/<think> block from final
                                    # answer, or returns an explicit "not returned" marker).
                                    # Extracted from the notebook's Sections 8-10.

notebooks/
└── faiss_retrieval_ready.ipynb   # EXTENDED (not rewritten): Sections 1-7 unchanged except
                                    # Section 4's inline class body is replaced with an
                                    # `from retrieval.sqlite_faiss_store import
                                    # SQLitePayloadFaissVectorStore` import; Sections 8-10's
                                    # inline GeneratorClient/prompt/parsing are replaced with
                                    # `from generation.reasoning_client import ...` imports;
                                    # ANSWER_PROMPT is updated to explicitly request a
                                    # reasoning/thinking section; Section 11's benchmark loop
                                    # gains a per-question reasoning/answer/error record.

tests/
├── retrieval/
│   ├── __init__.py
│   └── test_sqlite_faiss_store.py   # NEW: staleness detection (fresh vs. stale cache,
│                                      # size/mtime mismatch), cache rebuild correctness,
│                                      # search()/scroll() against a small synthetic
│                                      # FAISS index + payloads.jsonl fixture (tmp_path).
└── generation/
    ├── __init__.py
    └── test_reasoning_client.py      # NEW: prompt construction includes context +
                                       # reasoning instruction; response parsing for (a)
                                       # explicit reasoning_content field, (b)
                                       # <think>...</think> delimited text, (c) no
                                       # separable reasoning -> "not returned" label;
                                       # api_key never appears in any returned/printed
                                       # string. Uses a fake OpenAI client, no network calls.
```

**Structure Decision**: Single project, option 1 style (no frontend/backend split). This continues the precedent already established for this feature and cited by `002-eda-v2-dataset-notebook`'s own plan ("pairs a thin notebook with the pre-existing `src/retrieval/` module") — except here the two pieces of new logic (SQLite-backed store, reasoning-capable generator client) do not yet have a `src/` home; they currently exist only as inline notebook cells. Per Constitution Principle V, this plan formalizes both into small, unit-testable modules (`src/retrieval/sqlite_faiss_store.py`, `src/generation/reasoning_client.py`) rather than leaving them notebook-only, closing exactly the gap the sibling feature's plan assumed was already closed. The notebook itself is extended in place (not replaced) since Sections 1–7 already satisfy User Stories 1–3 ; only Section 4 (SQLite store) and Sections 8–10 (generator) change to import from the new modules, and Section 11 (benchmark) gains reasoning-aware per-question recording.

## Complexity Tracking

*No entries — Constitution Check passed with no violations.*
