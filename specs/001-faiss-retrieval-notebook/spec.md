# Feature Specification: Full FAISS Retrieval System Notebook

**Feature Branch**: `001-faiss-retrieval-notebook`

**Created**: 2026-07-15

**Updated**: 2026-07-15 — added SQLite payload cache artifact and a reasoning-capable answer-generation step

**Status**: Draft

**Input**: User description: "Build a full notebook run the whole retrieval system."

**Update Input**: User description: "Update the spec for 'specs/001-faiss-retrieval-notebook'. I have uploaded the sqlite for the faiss retrieval. Also, I want to have the generator (using api call from base_url, api_key, model_name), prompt it so that it support reasoning"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the retrieval system end to end from a single notebook (Priority: P1)

A project member (developer, researcher, or reviewer) opens one notebook and runs it top to bottom to exercise the complete vector retrieval system: verify the FAISS index artifacts are present, load the index and retriever, run one or more legal questions through retrieval, and inspect citation-ready results — without writing any additional code.

**Why this priority**: This is the core deliverable requested. Without a working end-to-end run, the notebook has no value as a validation or demo tool for the retrieval system.

**Independent Test**: Open the notebook in a fresh environment with `data/faiss_index/` populated, run all cells sequentially, and confirm the final cells print retrieved chunks with citation metadata and no unhandled errors.

**Acceptance Scenarios**:

1. **Given** `index.faiss` and `payloads.jsonl` exist under `data/faiss_index/`, **When** the user runs all notebook cells in order, **Then** the notebook loads the index, builds a retriever, executes at least one sample query, and displays ranked, citation-ready results.
2. **Given** the required index files are missing or incomplete, **When** the user runs the preflight cell, **Then** the notebook clearly reports which files are missing and stops before attempting to load a broken index.
3. **Given** a `payload_cache.sqlite` file is already present alongside `index.faiss` and `payloads.jsonl` under `data/faiss_index/`, **When** the user runs the preflight and load cells, **Then** the notebook detects and reuses the existing SQLite cache instead of rebuilding it from `payloads.jsonl`, provided the cache is not stale relative to `payloads.jsonl`.

---

### User Story 2 - Validate retrieval quality against the benchmark dataset (Priority: P2)

A project member wants evidence that the retrieval system behaves correctly across the full range of question types (single-hop, multi-hop, citation, legal validity, unanswerable), not just one hand-picked query, using the existing frozen QA benchmark (`data/benchmark/qa_final.jsonl`).

**Why this priority**: A single sample query proves the pipeline runs, but the "whole retrieval system" implies coverage of filter profiles, ranking, expansion, and edge cases (e.g., unanswerable questions, empty graph-guided filters) that only show up across a batch of diverse questions.

**Independent Test**: Run the notebook's benchmark section against a small sample (e.g., 10–20 questions) drawn from `qa_final.jsonl` and confirm it reports per-question retrieval results plus aggregate timing and hit-rate style summaries, independent of any answer-generation step.

**Acceptance Scenarios**:

1. **Given** the benchmark file `data/benchmark/qa_final.jsonl` is available, **When** the user runs the benchmark cell with a configurable sample size, **Then** the notebook retrieves results for each sampled question and reports whether ground-truth chunk/provision/document IDs were found among the retrieved candidates.
2. **Given** a benchmark question has `answer_type = "unanswerable"` with empty ground truth, **When** retrieval runs for that question, **Then** the notebook records the result without treating the absence of matching ground-truth IDs as a pipeline error.

---

### User Story 3 - Exercise filter profiles and same-provision expansion (Priority: P3)

A project member wants to confirm that the retrieval system's configurable behaviors — filter profiles (`current_law`, `broad`, `historical`), score threshold, top-k/top-n, and same-provision expansion — are runnable and visibly different in the notebook, not just implemented in library code.

**Why this priority**: These are explicit, documented capabilities of the retrieval module (`docs/spec/SPEC_Vector_Retrieval.md`, `docs/spec/RETRIEVE_MODULE.md`). A "full" notebook that only ever runs the default profile does not actually demonstrate "the whole retrieval system."

**Independent Test**: Run the same query through each supported filter profile and confirm the notebook displays the profile used, candidate counts, and any empty-filter warnings distinctly per run.

**Acceptance Scenarios**:

1. **Given** a fixed query, **When** the user runs retrieval under `current_law`, `broad`, and `historical` profiles in sequence, **Then** the notebook shows the filter profile used and result sets for each, allowing visual comparison.
2. **Given** `expand_units` is toggled on, **When** retrieval runs, **Then** the notebook shows evidence of same-provision expansion (e.g., sibling chunks under the same `parent_unit_id`) in the returned results or a diagnostic count.

---

### User Story 4 - Generate a reasoning-backed answer from retrieved context (Priority: P2)

A project member wants the notebook to go one step past raw retrieval: take the top retrieved chunks for a question, send them to a configurable LLM API (reached via a user-supplied `base_url`, `api_key`, and `model_name`), and receive back both a final answer and the model's reasoning/thinking trace, so the user can judge not just what the model answered but how it got there from the retrieved evidence.

**Why this priority**: Retrieval alone proves the vector search works, but the project's broader goal is grounded answer generation. Exposing the model's reasoning trace lets a reviewer catch ungrounded leaps (hallucination, ignoring context) that a bare final answer would hide. This is scoped as a thin, notebook-local generation step layered on top of the existing retrieval system, not a new evaluation pipeline.

**Independent Test**: With retrieval already producing results for a sample question, configure `base_url`, `api_key`, and `model_name` in the notebook's generation section, run the generation cell, and confirm the notebook displays a final answer plus a visibly separate reasoning/thinking section, grounded in the retrieved chunk text.

**Acceptance Scenarios**:

1. **Given** valid `base_url`, `api_key`, and `model_name` values are configured and at least one chunk was retrieved for a question, **When** the user runs the generation cell, **Then** the notebook sends the question and retrieved context to the configured API endpoint, prompted to produce reasoning, and displays the final answer separately from the reasoning/thinking trace.
2. **Given** the configured model/provider returns an explicit reasoning field (e.g., a `reasoning_content`/`reasoning` field or a `<think>`-delimited section in the response), **When** generation completes, **Then** the notebook extracts and displays that reasoning content distinctly from the final answer text.
3. **Given** the configured model/provider does not return any distinguishable reasoning content, **When** generation completes, **Then** the notebook still displays the final answer and clearly labels the reasoning section as not returned by this model, rather than fabricating or omitting the section silently.
4. **Given** the benchmark/batch retrieval mode has already run for a sample of questions, **When** the user optionally runs generation over that same sample, **Then** the notebook reports, per question, the final answer and reasoning trace (or "not returned" label) without requiring the user to re-run retrieval.
5. **Given** an invalid or missing `api_key`, **When** the user runs the generation cell, **Then** the notebook surfaces a clear authentication/configuration error and does not print the `api_key` value in any cell output.

### Edge Cases

- What happens when `data/faiss_index/index.faiss` or `payloads.jsonl` is missing, partially downloaded, or corrupted? The notebook MUST detect this in the preflight step and stop with a clear message instead of failing deep inside index loading.
- How does the notebook handle a query that matches zero chunks above `score_threshold`? It MUST show an empty (not crashing) result with total candidate count and let the user see that zero results is a valid outcome, not an error.
- How does the notebook handle the `graph_guided` filter profile when no graph-derived `id_str` whitelist is available in this notebook's scope? It MUST surface this explicitly (e.g., skip or clearly label as "not exercised — requires knowledge graph module") rather than silently defaulting to unfiltered search.
- What happens if the embedding model download fails (no internet / no HF token) when running in a fresh environment? The environment-setup cell MUST surface the failure clearly so the user knows retrieval cannot proceed without the model.
- How does the notebook behave on a machine without a GPU? Retrieval MUST still complete (CPU-only FAISS + sentence-transformers), possibly slower; the notebook should not assume GPU availability.
- What happens when the benchmark sample includes questions whose `ground_truth` lists are empty (`unanswerable` type)? The notebook's scoring/summary logic MUST treat these as "no evidence expected" rather than counting them as retrieval misses.
- What happens when a `payload_cache.sqlite` file exists under `data/faiss_index/` but is stale relative to `payloads.jsonl` (different size or modification time)? The notebook MUST detect the mismatch and rebuild the cache rather than silently serving outdated payload data.
- What happens when the generator's `base_url`, `api_key`, or `model_name` is missing or invalid? The notebook MUST surface a clear configuration/authentication error for the generation step without crashing the rest of the notebook and without printing the `api_key` value.
- What happens when the configured generator model/provider does not return a distinguishable reasoning trace? The notebook MUST still display the model's final answer and label the reasoning trace as "not returned by this model" rather than presenting absent reasoning as if it were captured.
- What happens when the generator API call fails transiently (rate limit, network timeout) during a sample or benchmark run? The notebook MUST record the failure for that question and continue with the remaining questions instead of stopping the whole run.
- What happens when retrieval for a question returns zero chunks above `score_threshold`? The generation step MUST NOT call the generator with empty context; it MUST record "no context available" and skip generation for that question.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The notebook MUST verify, in an early "preflight" step, that the required FAISS artifacts (`index.faiss`, `payloads.jsonl` in `data/faiss_index/`) exist before attempting to load them, and MUST report exactly which files are missing if any.
- **FR-002**: The notebook MUST load the FAISS index and construct a working retriever object using the project's existing retrieval module (`src/retrieval/`), reusing its config, embedder, and retriever abstractions rather than re-implementing retrieval logic.
- **FR-003**: The notebook MUST allow the user to configure, near the top of the notebook, the embedding model name, `top_k`, `top_n`, `score_threshold`, `expand_units`, and default filter profile, without requiring edits elsewhere in the notebook.
- **FR-004**: The notebook MUST run at least one representative sample query end to end and display the ranked results with, at minimum: rank, `chunk_id`, citation (anchor or label), title, `unit_type`, `validity_group`, vector score, and rerank score.
- **FR-005**: The notebook MUST support running the same query under each of the three locally-supported filter profiles (`current_law`, `broad`, `historical`) and display which profile was used, the total candidate count, and whether an empty-filter warning was raised.
- **FR-006**: The notebook MUST provide a batch/benchmark mode that reads sampled questions from `data/benchmark/qa_final.jsonl`, runs retrieval for each, and reports per-question whether any ground-truth `chunk_id`/`provision_id`/`document_id` appears among the retrieved results, plus an aggregate summary (e.g., hit rate, average retrieval latency) across the sample.
- **FR-007**: The notebook MUST let the user configure the benchmark sample size (or run the full benchmark) so it can be used both for a quick smoke check and a fuller validation pass.
- **FR-008**: The notebook MUST report retrieval latency (per-query and averaged over repeated runs) so users can judge whether the system meets the project's response-time expectations.
- **FR-009**: The notebook MUST demonstrate same-provision expansion behavior (i.e., show that sibling chunks from the same parent legal provision can appear in results when `expand_units` is enabled) using at least one example.
- **FR-010**: The notebook MUST clearly label any stage that depends on a component outside this notebook's scope (for example, a knowledge-graph-derived `id_str` whitelist for the `graph_guided` filter profile) as not exercised here, rather than silently skipping it without explanation.
- **FR-011**: The notebook MUST allow inspection of one full retrieved chunk (full `chunk_text`, citation fields, and payload metadata keys) so users can manually verify grounding quality.
- **FR-012**: The notebook MUST NOT crash the whole run when a single sample or benchmark query returns zero results above the score threshold; it MUST record the empty result and continue.
- **FR-013**: The notebook MUST work when run from either the project root or the `notebooks/` directory, resolving `data/` and `src/` paths relative to the detected project root.
- **FR-014**: The notebook MUST NOT index, retrieve from, or otherwise expose chunks belonging to quarantined or external-stub documents, consistent with the project's citation-safety rules; if the underlying index already excludes them, the notebook MUST state this assumption rather than silently relying on it.
- **FR-015**: The notebook MUST support loading per-chunk payload metadata from a pre-existing `payload_cache.sqlite` file under `data/faiss_index/` when present, avoiding a full re-scan of `payloads.jsonl` on notebook startup.
- **FR-016**: The notebook MUST validate any existing `payload_cache.sqlite` against the current `payloads.jsonl` (e.g., by comparing file size and modification time) before reusing it, and MUST rebuild the cache automatically when the two are out of sync.
- **FR-017**: The notebook MUST provide a configuration section for a generation/answer step allowing the user to set, without editing code elsewhere, the API `base_url`, `api_key`, and `model_name` used to call an OpenAI-compatible chat completion endpoint.
- **FR-018**: The notebook MUST NOT hardcode a real `api_key` value in the notebook source; it MUST read the key from an environment variable or a clearly marked user-editable placeholder, and MUST NOT print the raw `api_key` value in any cell output.
- **FR-019**: The notebook MUST construct the generation prompt so that it explicitly instructs the model to produce a reasoning/thinking process in addition to a final answer, and MUST pass the retrieved chunk text (citation-ready context) as grounding evidence in that prompt.
- **FR-020**: The notebook MUST parse the generator's response to separate the final answer from the reasoning/thinking content when the provider returns them as distinguishable fields or delimited sections (e.g., a `reasoning_content` field, or a `<think>...</think>` block preceding the final answer), and MUST display both parts separately to the user.
- **FR-021**: The notebook MUST handle the case where the provider does not return separable reasoning content by displaying the final answer and explicitly labeling the reasoning section as not provided by the model, rather than leaving the reasoning section blank without explanation or inventing reasoning text.
- **FR-022**: The notebook MUST allow running the generation step over one sample question (ad hoc) and, optionally, over the benchmark sample already produced by the retrieval benchmark mode, reusing that retrieval output rather than re-querying the index.
- **FR-023**: The notebook MUST NOT let a single generation call's failure (timeout, rate limit, malformed response) stop a batch generation run; it MUST record the failure for that question/case and continue with the remaining questions.
- **FR-024**: The notebook MUST label the generation step as a thin demonstration/validation layer on top of retrieval (consistent with the project's existing `scripts/evaluate_e2e.py` pattern) and MUST NOT claim to be a full answer-correctness evaluation pipeline (e.g., no automated judge/scoring is implied by this notebook).

### Key Entities *(include if feature involves data)*

- **FAISS index artifacts**: `index.faiss` (vector index), `payloads.jsonl` (per-chunk metadata payload), optional `id_map.json`, all under `data/faiss_index/`. Represent the pre-built vector store the notebook loads and queries.
- **Payload SQLite cache**: `payload_cache.sqlite` under `data/faiss_index/`, an indexed cache of the per-chunk payload records from `payloads.jsonl`, keyed by line number/vector ID, used to avoid repeated full-file scans on notebook startup. Tracks the source file's size and modification time to detect staleness.
- **Retrieved chunk**: A single citation-ready retrieval result, including `chunk_id`, `chunk_text`, citation anchor/label, title, `unit_type`, `validity_group`, `legal_authority_rank`, vector score, and rerank score. Produced by the retrieval module for each query.
- **Benchmark QA case**: A record from `data/benchmark/qa_final.jsonl` with `qa_id`, `question`, `reference_answer`, `answer_type`, `ground_truth` (document/provision/chunk IDs), `category`, and `difficulty`. Used to validate retrieval coverage against known-correct evidence.
- **Retrieval run configuration**: The set of user-tunable parameters (embedding model, `top_k`, `top_n`, `score_threshold`, `expand_units`, filter profile) that determine how a query is executed.
- **Generator configuration**: The set of user-tunable parameters (`base_url`, `api_key`, `model_name`) that determine which OpenAI-compatible chat completion endpoint the notebook calls for answer generation.
- **Generated answer**: The output of the generation step for a given question, consisting of a final answer string, a reasoning/thinking trace (or an explicit "not returned" label), the retrieved context used as grounding, and any error state if the generator call failed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with the required FAISS artifacts already downloaded can run the entire notebook top to bottom in one sitting without manual code edits and without any cell raising an unhandled exception.
- **SC-002**: The notebook clearly reports, within the first few cells, whether the environment is ready to proceed (all required files present) or what is missing, in under 5 seconds of preflight checking (excluding large file downloads).
- **SC-003**: For a benchmark sample of at least 20 questions, the notebook produces a hit-rate summary (fraction of questions whose retrieved results include at least one ground-truth chunk, provision, or document, excluding unanswerable questions) and an average per-query retrieval latency.
- **SC-004**: A user can compare results for the same query across all three locally-runnable filter profiles within the same notebook session, seeing distinct candidate counts and/or result sets per profile.
- **SC-005**: 100% of displayed retrieval results include enough metadata (citation anchor or label, title, scores) for a user to manually judge relevance without leaving the notebook.
- **SC-006**: When a valid `payload_cache.sqlite` already exists under `data/faiss_index/`, notebook startup (index + payload load) completes noticeably faster than a run that must build the cache from scratch from `payloads.jsonl`, without the user changing any configuration.
- **SC-007**: For at least one sample question, a user can view the generator's final answer and its reasoning/thinking trace as two visibly distinct sections in the notebook output, using only the `base_url`, `api_key`, and `model_name` they configured.
- **SC-008**: 100% of generation attempts in a batch run either produce a final answer (with reasoning content or an explicit "not returned" label) or a recorded, non-fatal error for that question; no batch generation run stops early due to a single failed call.

## Assumptions

- The FAISS index at `data/faiss_index/` has already been built by the existing indexing pipeline (`src/retrieval/build_vector_db.py`, `scripts/build_vector_index.py`) and is assumed current; this notebook consumes it, it does not rebuild it from raw `chunks.jsonl`/`provisions.jsonl`/`documents.jsonl`.
- The notebook targets the project's existing `src/retrieval` module (`VectorIndexConfig`, `SentenceTransformerEmbedder`, `VectorRetriever`) rather than introducing a new retrieval implementation, consistent with the "Modular, Testable, Reported Pipelines" principle in the project constitution.
- "The whole retrieval system" is scoped to vector retrieval (FAISS + embedding + filtering + ranking + same-provision expansion) as specified in `docs/spec/SPEC_Vector_Retrieval.md` and `docs/spec/RETRIEVE_MODULE.md`. Knowledge-graph-guided retrieval is out of scope for this notebook and is only referenced where the retrieval module has an explicit integration point (e.g., `graph_guided` filter profile), which will be labeled as not exercised here.
- Users run the notebook locally or in a hosted notebook environment (e.g., Colab) with enough RAM/disk to hold the FAISS index and payload cache described in the existing `notebooks/faiss_retrieval_ready.ipynb`; GPU is optional.
- The frozen benchmark file `data/benchmark/qa_final.jsonl` is the reference dataset for validation; the notebook reads it but does not modify or regenerate it.
- The `payload_cache.sqlite` file, when provided or built, is a derived artifact of `payloads.jsonl` (same directory, `data/faiss_index/`); the notebook treats `payloads.jsonl` as the source of truth and the SQLite file as an accelerating cache, not an independent data source.
- The answer-generation step targets any OpenAI-compatible chat completion API reachable via a user-supplied `base_url`, `api_key`, and `model_name` (e.g., a locally hosted reasoning model, or a hosted provider exposing an OpenAI-compatible endpoint); it is not tied to one specific vendor SDK beyond that compatibility assumption.
- "Support reasoning" means the generation prompt explicitly asks the model to produce a reasoning/thinking process before or alongside its final answer, and the notebook displays whatever reasoning content the provider returns (via a dedicated field or a delimited section); it does not mean the notebook implements its own reasoning engine or verifies the correctness of the reasoning.
- Building a full answer-correctness evaluation/judge-model layer (as in `scripts/evaluate_e2e.py`) remains out of scope; this notebook adds a lightweight, inspectable generation step for demonstration and manual grounding review, not automated scoring of answer quality.
