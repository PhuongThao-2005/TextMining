# Phase 0 Research: Full FAISS Retrieval System Notebook (SQLite cache + reasoning generator)

## R1: Where should the SQLite-backed payload store live — notebook-only vs. extracted module

**Decision**: Extract `SQLitePayloadFaissVectorStore` from the notebook's Section 4 into [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py), implemented against the existing [`VectorStore`](../../src/retrieval/stores.py:19) ABC (`recreate_collection`, `upsert`, `search`, `scroll`), alongside the existing `FaissVectorStore`.

**Rationale**: A repo-wide search for `sqlite3|payload_cache|\.sqlite` in `*.py` returned zero matches outside the notebook — this logic currently exists *only* as an inline class in `notebooks/faiss_retrieval_ready.ipynb`, with no unit tests. Constitution Principle V requires modules to "expose clear contracts through schemas, typed data structures, tests," and `002-eda-v2-dataset-notebook`'s own plan already assumed this feature's notebook "pairs a thin notebook with the pre-existing `src/retrieval/` module" — an assumption only true for the *existing* retriever/embedder/config trio, not for the SQLite store the user just uploaded a cache file for. Extracting it now makes that assumption accurate and gives the staleness-detection logic (FR-016) a regression test surface.

**Alternatives considered**:
- Leave it notebook-only, just document the staleness behavior in prose — rejected: staleness detection (comparing `payload_mtime_ns`/`payload_size` against a `meta` table) is exactly the kind of easy-to-silently-break logic (e.g., an off-by-one in the batch `INSERT` loop, or a wrong key comparison) that benefits from a fixture-based unit test, and notebook cells are not discovered by `pytest` (`pyproject.toml`'s `pythonpath = ["src"]` only looks at `src/`).
- Fold the SQLite caching directly into `FaissVectorStore` (in `faiss_store.py`) as an optional mode — rejected: `FaissVectorStore` already has a stable, tested-by-usage contract (in-memory payload list, `save()`/`load()` round-trip); bolting on a second, SQLite-backed code path with different internals (a persistent `sqlite3.Connection`, `close()` lifecycle) would conflate two different storage strategies in one class. A sibling class implementing the same `VectorStore` ABC is more in line with the existing `InMemoryVectorStore`/`QdrantVectorStore`/`FaissVectorStore` sibling pattern in `stores.py`/`faiss_store.py`.

## R2: Staleness detection strategy for `payload_cache.sqlite` vs. `payloads.jsonl`

**Decision**: Keep the existing approach already implemented in the notebook — compare `payloads.jsonl`'s `os.stat().st_size` and `st_mtime_ns` against values stored in a `meta` table inside the SQLite file (`payload_mtime_ns`, `payload_size`), rebuilding the cache when either differs.

**Rationale**: This is already implemented and working in the notebook (`_ensure_payload_cache`); the plan's job is to extract and test it, not redesign it. Size+mtime is the same lightweight staleness heuristic used by many build-cache tools (e.g., `make`, most language build caches) and avoids hashing a multi-hundred-MB `payloads.jsonl` on every notebook startup, which would defeat the purpose of caching (SC-006 requires startup to be "noticeably faster" when the cache is fresh).

**Alternatives considered**:
- Content hash (e.g., SHA-256 of `payloads.jsonl`) stored in the cache — rejected: correct but requires a full read of the large file on every startup just to validate the cache, which is strictly slower than the operation the cache exists to avoid; size+mtime is sufficient for the notebook's single-machine, single-user use case described in the spec's Assumptions.
- No staleness check at all (always trust an existing cache file) — rejected: this is exactly the "silently serving outdated payload data" failure mode called out in the spec's Edge Cases and forbidden by Constitution Principle III (No Silent Data Loss / no stale-data-as-truth).

## R3: Where should the OpenAI-compatible generator client live — notebook-only vs. extracted module

**Decision**: Extract `GeneratorClient`, `ANSWER_PROMPT` (updated to explicitly request reasoning), `format_context_for_prompt`, and a new `parse_generation_response()` helper from the notebook's Sections 8–10 into [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py), superseding the empty placeholder at [`src/generation/temp.py`](../../src/generation/temp.py).

**Rationale**: Same reasoning as R1 — a repo-wide search for `openai|reasoning_content|extra_body` in `*.py` found no existing usage outside the notebook, and the existing `src/generation/temp.py` (one blank line) is clearly a placeholder anticipating this exact module. Response parsing that must correctly split "reasoning" from "final answer" across at least three provider response shapes (a dedicated `reasoning_content` field, a `<think>...</think>` delimited block, or no separable reasoning at all — FR-020/FR-021) is precisely the kind of branching logic that is easy to get subtly wrong (e.g., leaving `<think>` tags in the visible answer, or mislabeling "no reasoning" as an error) and benefits from unit tests with canned fake responses, no live API calls required.

**Alternatives considered**:
- Reuse `scripts/evaluate_e2e.py`'s `GeminiClient` pattern directly — rejected: `GeminiClient` is Gemini-SDK-specific (`google.generativeai`) and has no concept of `reasoning_content`/`<think>` parsing; the spec explicitly asks for an OpenAI-compatible `base_url`/`api_key`/`model_name` interface instead (already anticipated by the notebook's own `%pip install ... openai` cell), so a new client is required regardless. The *prompt style* (Vietnamese, context-grounded, explicit "insufficient information" fallback) is reused from `evaluate_e2e.py`'s `ANSWER_PROMPT` as a starting point, then extended with a reasoning instruction.
- Keep the client notebook-only since it is "just a thin wrapper" — rejected: the *parsing* logic (not the wrapper itself) is where correctness risk concentrates, and Constitution Principle V's testability requirement applies to exactly this kind of small-but-easy-to-break logic, not just large pipelines.

## R4: How to elicit and parse a reasoning/thinking trace from an OpenAI-compatible endpoint

**Decision**: Two-layer approach — (1) prompt-level: instruct the model explicitly to produce a reasoning section before its final answer (e.g., "Trước tiên, trình bày quá trình suy luận... Sau đó, đưa ra câu trả lời cuối cùng."), and (2) response-level: check for a `reasoning_content` (or `reasoning`) attribute on the response message first (as exposed by some OpenAI-compatible reasoning-model providers, e.g., DeepSeek-R1-style APIs via `extra_body`/custom fields), then fall back to scanning the message content for a `<think>...</think>` delimited block and splitting it out, and only if neither is present, label the reasoning section as "not returned by this model."

**Rationale**: Different OpenAI-compatible providers expose reasoning differently — some via a distinct API field, some via inline delimiters in the content string, some not at all. FR-020/FR-021 require handling all three cases explicitly rather than assuming one shape. Checking the dedicated field first is correct because it's structured and unambiguous when present; falling back to delimiter-scanning covers providers/models that only emit `<think>` tags inline (a widely used convention for locally-hosted reasoning models); the explicit "not returned" label (never fabricated, never silently blank) satisfies FR-021 and the Edge Cases section directly.

**Alternatives considered**:
- Always require the `reasoning_content` field and treat its absence as an error — rejected: this would break for providers that only support inline `<think>` delimiters (a common pattern for open-weight reasoning models served via vLLM/Ollama-style OpenAI-compatible shims), contradicting the spec's provider-agnostic Assumption ("not tied to one specific vendor SDK beyond OpenAI compatibility").
- Ask a second, separate "explain your reasoning" follow-up call after getting the answer — rejected: doubles API cost/latency per question and does not match "prompt it so it support reasoning" (a single call producing both), which the user's original request implies.

## R5: Batch/benchmark integration — reusing retrieval output for generation without re-querying

**Decision**: Extend the existing `run_benchmark_sample()` (notebook Section 11) so each per-question record already includes `answer` alongside `retrieval_hit`/`latency_s`/etc — this already happens today by calling `generate_answer(question, result.chunks)` inline in the same loop that produced `result`. The plan's change is to additionally capture and record the parsed reasoning trace (or "not returned" label) per question, and to catch generation exceptions per-question (already done via the existing `try/except` around `generate_answer`) without stopping the loop (FR-023).

**Rationale**: FR-022 requires generation to reuse retrieval output "rather than re-querying the index" — the existing benchmark loop already satisfies this shape (single `search()` call per question, chunks passed directly to `generate_answer`); the only gap is that reasoning is not yet extracted/recorded distinctly (today `generate_answer` returns a bare string). Once `parse_generation_response()` exists (R3/R4), the benchmark loop calls it and stores `{'answer': ..., 'reasoning': ..., 'reasoning_available': bool}` per record instead of a bare answer string.

**Alternatives considered**:
- A separate generation-only batch function that takes a list of already-computed `RetrievalResult`s as input — rejected as unnecessary indirection: the existing single-loop design (search → optionally generate, same iteration) already avoids re-querying and keeps the notebook cell readable; splitting it into two passes would need to persist retrieval results across cells and doesn't provide additional testability (the `parse_generation_response()` function is unit-tested directly, independent of the loop that calls it).

## R6: `api_key` handling — security constraint (FR-018, constitution "secure credential handling")

**Decision**: Keep the existing pattern already implemented in the notebook's Section 8 — read `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_NAME` from environment variables, never hardcode a real key in the notebook source, and when confirming configuration, print only a masked form (`API_KEY[:4] + '...' + API_KEY[-4:]`, or `'***'` if too short) — never the raw value. The extracted `GeneratorClient` in `src/generation/reasoning_client.py` must not log, print, or include the raw `api_key` in any exception message it raises.

**Rationale**: This is already correctly implemented in the notebook and matches the constitution's "API keys, credentials... MUST be stored and handled securely" constraint and FR-018 exactly. The plan's job is to preserve this behavior through the extraction (R1/R3) and add a unit test asserting the masking function and that `GeneratorClient.__init__`/`generate()` never include the raw key in any returned string or raised exception's `str()`.

**Alternatives considered**:
- Move to a `.env` file + `python-dotenv` — rejected as unnecessary new dependency; plain `os.environ.get(...)` already satisfies "read from an environment variable" (FR-017/018) and matches the project's existing style (no `.env` usage found elsewhere in `src/`/`scripts/`).
