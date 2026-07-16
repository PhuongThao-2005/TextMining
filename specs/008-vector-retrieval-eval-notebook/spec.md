# Feature Specification: Vector-Only Retrieval Evaluation Notebook

**Feature Branch**: `008-vector-retrieval-eval-notebook`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "I want a notebook to run vector retrieval only and evaluate against the qa_final.jsonl. DO NOT READ THE ARCHIVE NOTEBOOK."

## Clarifications

### Session 2026-07-16

- Q: Should this notebook reuse the existing hybrid/traversal-capable retrieval notebook or be independent? → A: Independent — the notebook is scoped to vector-only retrieval and must not require building the knowledge graph, GraphExpansion, or hybrid fusion. It is a new notebook, not a modification of `L_RAG/notebooks/archive/*` (explicitly out of scope per user instruction) or of the existing `006-retrieval-eval-notebook` hybrid-capable notebook.
- Q: What defines "evaluate against qa_final.jsonl"? → A: Run the same eligibility rules, retrieval metrics (Recall@k, Hit@k, MRR@k, nDCG@k, Jaccard@k), and breakdowns (overall / by category / by difficulty / by answer_type) already implemented in `src/evaluation/metrics.py`, `src/evaluation/eligibility.py`, and `scripts/evaluate_retrieval.py`, presented interactively in notebook form rather than only via CLI script.
- Q: Where does the vector index/embeddings come from? → A: A local FAISS index (`index.faiss` + `payloads.jsonl`) with a SQLite payload cache (`payload_cache.sqlite`), loaded via `src/retrieval/sqlite_faiss_store.py`'s `SQLitePayloadFaissVectorStore.load(index_dir)` and the existing `VectorRetriever` retrieval path — **not Qdrant**. The notebook does not invent a new retrieval backend; `src/evaluation/retriever_factory.py`'s `build_vector_retriever` currently only constructs a Qdrant-backed retriever and MUST be extended to support this FAISS-backed construction path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run vector-only retrieval evaluation end-to-end in a notebook (Priority: P1)

A person evaluating the RAG system's vector retrieval quality opens a new, dedicated notebook, configures the vector store/model/top-k settings, loads `data/qa_final.jsonl`, runs vector-only retrieval for every eligible question, and sees aggregate metrics (Recall@k, Hit@k, MRR@k, nDCG@k, Jaccard@k) plus breakdowns by category, difficulty, and answer type — all without needing to build or reference the knowledge graph or hybrid fusion pipeline.

**Why this priority**: This is the entire purpose of the notebook — a standalone way to measure vector-retrieval-only quality against the frozen benchmark. Without this, there is no dedicated, interactive vector-only evaluation path.

**Independent Test**: Run the notebook top to bottom against a populated local FAISS index directory (or a dev/hashing embedder for a smoke test) and `data/qa_final.jsonl`, and confirm it prints/displays an overall metrics table and per-category/per-difficulty/per-answer_type breakdown tables, with no cell requiring knowledge-graph or hybrid-specific objects.

**Acceptance Scenarios**:

1. **Given** a populated local FAISS index directory (`index.faiss` + `payloads.jsonl`, with its SQLite payload cache) containing the corpus's chunks and `data/qa_final.jsonl` present, **When** the user runs the notebook's configuration, retrieval, and evaluation cells in order, **Then** the notebook produces an overall metrics summary (Recall@k, Hit@k, MRR@k, nDCG@k, Jaccard@k for the configured k values) and category/difficulty/answer_type breakdown tables.
2. **Given** the notebook has produced per-case results, **When** the user inspects the per-case output, **Then** each evaluated case shows its `qa_id`, question, ground-truth chunk IDs, retrieved chunk IDs, and computed per-k metrics.
3. **Given** the evaluation run has completed, **When** the user chooses to persist results, **Then** the notebook writes a per-case JSONL file and an aggregate metrics JSON file to a run-scoped output directory, mirroring the shapes already produced by `scripts/evaluate_retrieval.py`.

---

### User Story 2 - Correctly exclude unanswerable/missing-ground-truth rows (Priority: P2)

A user running the evaluation wants confidence that unanswerable QA rows and rows lacking ground-truth chunk IDs are excluded from the scored metrics in the same well-defined way as the existing CLI evaluator, and that the notebook reports how many rows were skipped and why.

**Why this priority**: Incorrect eligibility filtering silently inflates or deflates metrics and undermines trust in the results; this must match the established, tested eligibility rules. Depends on US1 existing.

**Independent Test**: Run the notebook against `data/qa_final.jsonl` and confirm the reported "skipped unanswerable" and "skipped missing ground truth" counts match what `src/evaluation/eligibility.py`'s `select_eligible_cases` would compute for the same file, and that the "evaluated" count equals eligible rows minus any optional sample limit.

**Acceptance Scenarios**:

1. **Given** `data/qa_final.jsonl` contains rows with `answer_type == "unanswerable"` (or `category == "unanswerable"`), **When** the notebook runs eligibility filtering, **Then** those rows are excluded from scoring and counted under "skipped unanswerable" in the displayed summary.
2. **Given** an eligible-looking row has an empty `ground_truth.chunk_ids` list, **When** the notebook runs eligibility filtering, **Then** that row is excluded from scoring and counted under "skipped missing ground truth."
3. **Given** the user sets an optional sample limit (e.g., first 25 eligible cases), **When** the notebook runs retrieval, **Then** exactly that many eligible cases are evaluated and the summary states the limit was applied.

---

### User Story 3 - Configure retrieval parameters without editing library code (Priority: P3)

A user wants to try different `top_k`/`top_n`, score thresholds, embedding models, or `expand_units` settings to see their effect on vector-only metrics, adjusting only notebook configuration cells/variables rather than editing source files.

**Why this priority**: Enables quick experimentation and sensitivity analysis; valuable but not required for the minimum viable evaluation delivered by US1. Depends on US1.

**Independent Test**: Change the notebook's configured `top_k` list (e.g., from `[1, 5, 10]` to `[1, 3]`) and score threshold in the config cell only, rerun the retrieval/evaluation cells, and confirm the resulting metrics table reflects the new `k` values and threshold without any source file edits.

**Acceptance Scenarios**:

1. **Given** the notebook's configuration cell exposes `top_k` list, score threshold, embedding model name, and `expand_units` flag, **When** the user edits these values and reruns retrieval, **Then** the new configuration is reflected in both the retrieved results and the metrics table's columns/values.
2. **Given** the user provides an invalid, missing, or corrupt FAISS index directory configuration, **When** the retrieval cell runs, **Then** the notebook surfaces a clear error message identifying the configuration problem rather than a raw, unexplained stack trace propagating through unrelated cells.

---

### Edge Cases

- What happens when `data/qa_final.jsonl` is missing or unreadable at the configured path? The notebook MUST report a clear, specific error (naming the expected path) rather than failing with an unrelated exception several cells later.
- What happens when the configured FAISS index directory is missing, empty, or its SQLite payload cache is stale/corrupt? The notebook MUST surface a clear load/configuration error at the retrieval step rather than silently returning empty results for every case.
- What happens when every row in `qa_final.jsonl` is ineligible (all unanswerable or missing ground truth)? The notebook MUST report zero evaluated cases explicitly (with skip counts explaining why) rather than erroring on an empty metrics aggregation.
- What happens when a `top_k` value exceeds the number of chunks a case retrieves? The notebook MUST rely on the existing `src/evaluation/metrics.py` semantics for `k` larger than the retrieved list (already handled there) rather than introducing new truncation/padding logic.
- What happens when the user reruns the evaluation cells multiple times in one session (e.g., after changing config)? Each run MUST produce a fresh, self-consistent set of results reflecting the current configuration, without mixing stale per-case rows from a previous configuration into the new aggregate.
- What happens if hybrid/graph-related objects from another notebook or a previous cell happen to exist in the same kernel session? The vector-only evaluation cells MUST NOT depend on or require any hybrid/GraphExpansion/knowledge-graph object to produce correct results.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The notebook MUST be a new, standalone notebook file dedicated to vector-only retrieval evaluation, distinct from any hybrid/graph-capable retrieval notebook and from the archived notebooks under `L_RAG/notebooks/archive/`.
- **FR-002**: The notebook MUST perform retrieval using only the vector retrieval path (embedding + vector-store similarity search, optionally with unit expansion), and MUST NOT require building, loading, or invoking the knowledge graph, `GraphExpansion`, `GraphTraversal`, or any hybrid fusion component to produce its results.
- **FR-003**: The notebook MUST load the frozen QA benchmark from `data/qa_final.jsonl` and classify every row as eligible, skipped-unanswerable, or skipped-missing-ground-truth using the same rules as `src/evaluation/eligibility.py`'s `select_eligible_cases` (no row silently dropped or double-counted).
- **FR-004**: For every eligible case, the notebook MUST run vector-only retrieval (via the existing `VectorRetriever`/`build_vector_retriever` construction path) and compute, for each configured `k` in a user-configurable `top_k` list, Recall@k, Hit@k, MRR@k, nDCG@k, and Jaccard@k using `src/evaluation/metrics.py` as the sole metric source (no ad-hoc formulas reimplemented in the notebook).
- **FR-005**: The notebook MUST display an overall aggregate metrics table/summary and breakdown tables by `category`, `difficulty`, and `answer_type`, matching the aggregation semantics already used by `scripts/evaluate_retrieval.py` (`aggregate`/`aggregate_by`).
- **FR-006**: The notebook MUST expose configuration for at least: `top_k` values, the local FAISS index directory path (containing `index.faiss`, `payloads.jsonl`, and `payload_cache.sqlite`), embedding model name, score threshold, `expand_units` flag, and an optional sample-size limit — all editable in a clearly marked configuration cell/section without requiring per-run edits to files under `src/`. (One-time extension of `src/evaluation/retriever_factory.py` to support FAISS-backed construction, per FR-002a below, is a planning/implementation task, not a per-run configuration edit.)
- **FR-002a**: `src/evaluation/retriever_factory.py`'s `RetrieverRuntimeConfig`/`build_vector_retriever` MUST be extended to support constructing a `VectorRetriever` backed by `SQLitePayloadFaissVectorStore.load(index_dir)` (in addition to, or in place of, its current Qdrant-only path), so the notebook can obtain a FAISS-backed retriever without inventing its own construction logic.
- **FR-007**: The notebook MUST report, for its run, the total row count, number evaluated, number skipped-unanswerable, and number skipped-missing-ground-truth, visibly in its summary output.
- **FR-008**: The notebook MUST provide an option to persist results to disk: a per-case JSONL file (one row per evaluated case, including `qa_id`, question, ground-truth chunk IDs, retrieved chunk IDs, and per-k metrics) and an aggregate metrics JSON file (counts, overall, by_category, by_difficulty, by_answer_type), written under a run-scoped output directory.
- **FR-009**: The notebook MUST NOT read, import from, or otherwise depend on any notebook under `L_RAG/notebooks/archive/` (explicit user instruction); any shared logic needed MUST come from `src/evaluation/` or `src/retrieval/` modules instead.
- **FR-010**: The notebook MUST clearly label its scope as "vector-only" in its title/header and in any output summary, so results are not confused with hybrid/graph-fused retrieval results produced elsewhere in the project.
- **FR-011**: The notebook MUST guard against a missing or unreadable `data/qa_final.jsonl` path with a clear, specific error message naming the expected path, rather than an unrelated downstream failure.
- **FR-012**: The notebook MUST guard against FAISS index load/configuration failures (missing index directory, missing `index.faiss`/`payloads.jsonl`, or an unreadable/corrupt SQLite payload cache) at the retrieval step with a clear error message, rather than silently treating such failures as empty-result cases.
- **FR-013**: When zero cases are eligible for evaluation (e.g., an entirely unanswerable/no-ground-truth QA file), the notebook MUST report zero evaluated cases explicitly, including the skip-reason counts, rather than raising an error during metrics aggregation.
- **FR-014**: Rerunning the notebook's retrieval/evaluation cells after a configuration change MUST produce results reflecting only the current configuration; prior run's per-case rows or aggregates MUST NOT be silently merged with the new run's results within the same displayed summary.

### Key Entities

- **QA benchmark row**: A single line from `data/qa_final.jsonl` containing `qa_id`, `question`, `answer_type`, `category`, `difficulty`, and `ground_truth` (`chunk_ids`, `provision_ids`, `document_ids`); the notebook's unit of evaluation input.
- **Eligible case**: A QA row classified as scorable (not unanswerable, has non-empty `ground_truth.chunk_ids`), per the existing `EligibleCase`/`select_eligible_cases` model.
- **Vector-only retrieval result**: The ranked list of retrieved chunk IDs (and associated scores/citations) produced by `VectorRetriever` for a single question, independent of any graph/hybrid signal.
- **Per-case metrics row**: The combination of a case's ground-truth and retrieved chunk IDs with computed `{metric}@{k}` values (Recall, Hit, MRR, nDCG, Jaccard) for each configured `k`.
- **Run summary**: The aggregate output for a notebook run: total/evaluated/skipped counts, overall metrics, and breakdowns by category, difficulty, and answer_type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can run the notebook top to bottom against `data/qa_final.jsonl` and a populated local FAISS index directory and obtain overall Recall@k/Hit@k/MRR@k/nDCG@k/Jaccard@k metrics for all configured `k` values without running any knowledge-graph or hybrid-fusion cell.
- **SC-002**: The notebook's reported skipped-unanswerable and skipped-missing-ground-truth counts exactly match the counts `src/evaluation/eligibility.py` would compute for the same QA file.
- **SC-003**: Changing only the notebook's configuration cell (top_k list, score threshold, model, expand_units) and rerunning produces a metrics table reflecting the new configuration, with zero edits to files under `src/`.
- **SC-004**: When the notebook is asked to persist results, the produced per-case JSONL and metrics JSON files can be loaded and their structure matches the fields described in FR-008, enabling reuse by downstream reporting tools.
- **SC-005**: The notebook contains no import from or reference to any file under `L_RAG/notebooks/archive/`.

## Assumptions

- A local FAISS index directory (default `data/faiss_index/`, containing `index.faiss`, `payloads.jsonl`, and `payload_cache.sqlite`) populated with the project's chunk embeddings is available on disk when running the notebook for real evaluation; a dev/hashing embedder path may be used for structural smoke-testing without a live model/index. **Qdrant is not used by this notebook.**
- `data/qa_final.jsonl` is the frozen benchmark file already used by `scripts/evaluate_retrieval.py`; this notebook evaluates against it as-is and does not modify or regenerate it.
- Metric definitions and eligibility rules are not being redesigned; this feature reuses `src/evaluation/metrics.py` and `src/evaluation/eligibility.py` as the single source of truth, exposed through a notebook UI/flow instead of (or in addition to) the existing CLI script.
- The existing hybrid-capable evaluation notebook (spec `006-retrieval-eval-notebook`, if present) and the archived notebooks under `L_RAG/notebooks/archive/` are out of scope for reading, reuse, or modification, per explicit user instruction; this is a net-new notebook file.
- Output artifacts (per-case JSONL, metrics JSON) are written to a run-scoped directory analogous to `scripts/evaluate_retrieval.py`'s `--out-dir` (e.g., under `evaluation_runs/`), but persistence itself is optional/user-triggered rather than mandatory for every notebook run.
