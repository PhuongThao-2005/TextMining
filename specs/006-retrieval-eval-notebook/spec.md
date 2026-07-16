# Feature Specification: Retrieval Evaluation Notebook

**Feature Branch**: `006-retrieval-eval-notebook`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "I want a separate notebook for retrieval evaluation. It will evaluate on the vector retrieval only and hybrid retrieval as well. use the evaluation module to calculate the specified metrics for the system. The evaluation data is the qa_final.json"

## Clarifications

### Session 2026-07-16

- Q: What must hybrid retrieval include beyond vector seed search? → A: Hybrid retrieval MUST include both GraphExpansion and GraphTraversal (not expansion-only).
- Q: How should GraphExpansion + GraphTraversal results fuse into the hybrid ranked chunk list used for metrics? → A: Seeds (vector order) → GraphExpansion chunks → GraphTraversal chunks; dedupe keep first occurrence.
- Q: Default GraphTraversal mode(s) / hybrid graph behavior for evaluation? → A: Adhere to `docs/spec/GRAPH_MODULE.md` (Traversal modes/caps §6, Expansion §7, Integration with Retrieval §10: traversals → overlays → whitelist filter; expansion of vector hits).
- Q: Hybrid operational sequence for evaluation? → A: Primary path is GRAPH_MODULE §10: GraphTraversal (+ overlays / ContextBuilder whitelist) → vector search with `id_str_filter` → GraphExpansion on retrieved hits; score fused list with seeds → expansion → any extra traversal-resolved chunks (dedupe keep first).
- Q: Where do GraphTraversal start IDs come from for official scored hybrid evaluation? → A: Seed-derived starts from an unfiltered vector pre-pass on the question; never use `ground_truth` IDs as traversal starts for scored hybrid (no label leakage).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run vector-only retrieval evaluation on the frozen QA benchmark (Priority: P1)

A project member opens a dedicated retrieval-evaluation notebook, points it at the frozen QA benchmark (`data/benchmark/qa_final.jsonl`, referred to by the user as `qa_final.json`), runs vector-only retrieval over answerable questions, and obtains the project's standard retrieval metrics (recall@k, hit@k, mrr@k, ndcg@k, jaccard@k) computed through the existing evaluation module—not ad-hoc notebook scoring.

**Why this priority**: Without a reproducible vector-only baseline scored with the shared evaluation metrics, hybrid comparison and report-ready numbers cannot be trusted. This is the minimum viable evaluation deliverable.

**Independent Test**: With FAISS index artifacts and `data/benchmark/qa_final.jsonl` available, run the notebook's vector-only evaluation section (optionally limited to a sample) and confirm per-case scores plus aggregate metrics match the evaluation module's defined metrics, with unanswerable / missing-ground-truth rows skipped and counted.

**Acceptance Scenarios**:

1. **Given** `data/benchmark/qa_final.jsonl` exists and the vector index is loadable, **When** the user runs the vector-only evaluation path, **Then** the notebook evaluates answerable QA rows that have non-empty ground-truth `chunk_ids`, retrieves ranked chunk IDs, and scores each case with recall@k, hit@k, mrr@k, ndcg@k, and jaccard@k for the configured k values.
2. **Given** the evaluation module's metric and aggregation helpers are available, **When** scoring and summary are produced, **Then** the notebook uses those helpers for per-case metrics and overall / by-category / by-difficulty / by-answer-type aggregates rather than reimplementing metric formulas in notebook cells.
3. **Given** a QA row is unanswerable or lacks ground-truth chunk IDs, **When** evaluation iterates the benchmark, **Then** the notebook skips that row, increments an explicit skip counter, and does not treat the skip as a retrieval failure.
4. **Given** the user configures a sample limit (or full-run mode), **When** evaluation runs, **Then** the notebook either evaluates only the first N answerable cases or the full eligible set, as configured, without requiring code edits outside the config section.

---

### User Story 2 - Run hybrid retrieval evaluation with the same metrics and benchmark (Priority: P1)

A project member evaluates hybrid retrieval on the same frozen QA benchmark and the same metric suite. Hybrid follows `docs/spec/GRAPH_MODULE.md` §10 as the **primary** path: **GraphTraversal** starts are seed-derived from an unfiltered vector pre-pass (not ground-truth); traversal (and dynamic overlays / ContextBuilder) produce a document whitelist; vector search runs with that `id_str_filter`; **GraphExpansion** expands retrieved hits into reading-order context. Both GraphTraversal and GraphExpansion are required. Fused hybrid evidence chunk IDs are scored so hybrid quality is measured under the same rules as vector-only.

**Why this priority**: The system architecture is hybrid; evaluating only vector search would understate the product path. Hybrid evaluation is co-equal to vector-only for this feature's purpose.

**Independent Test**: With vector index and knowledge-graph inputs available, run the hybrid evaluation path on a sample of answerable QA rows and confirm each case is labeled hybrid, shows GraphTraversal (whitelist/visits) and GraphExpansion both participated (or records explicit empty/no-op diagnostics), is scored with the same evaluation-module metrics against ground-truth chunk IDs, and is summarized with the same aggregation slices.

**Acceptance Scenarios**:

1. **Given** vector index and graph/hybrid prerequisites are available, **When** the user runs the hybrid evaluation path, **Then** the notebook derives GraphTraversal starts from an unfiltered vector pre-pass (not ground-truth), runs GRAPH_MODULE §10 order (traversal → overlays/whitelist → filtered vector seeds → GraphExpansion), fuses the ranked chunk list as seeds → expansion → any extra traversal-resolved chunks with first-seen dedupe, and scores that list with the same recall@k, hit@k, mrr@k, ndcg@k, and jaccard@k metrics used for vector-only.
2. **Given** hybrid evaluation completes for one or more cases, **When** results are recorded, **Then** each case is explicitly labeled with mode `hybrid`, includes the ranked/fused retrieved chunk IDs used for scoring, and records GraphTraversal and GraphExpansion participation (whitelist size / visited IDs, expansion counts, zero-added or empty-filter diagnostics when applicable).
3. **Given** the graph/hybrid path is unavailable (missing graph artifacts, missing expansion/traversal capability, empty silent-fallback risk, or hybrid guard failure), **When** the user requests hybrid evaluation, **Then** the notebook fails clearly or marks hybrid evaluation unavailable—never silently scores unfiltered pure vector results under a hybrid label, and never labels expansion-only or traversal-only partial paths as full hybrid without stating the missing service.

---

### User Story 3 - Compare vector-only vs hybrid side by side (Priority: P2)

A project member wants one notebook session that runs both modes on the same QA subset and presents a side-by-side comparison of aggregate metrics (and optional per-case deltas) so they can see whether hybrid improves retrieval quality.

**Why this priority**: Separate scores are useful; comparison is the decision artifact for reports and architecture claims. Depends on US1 and US2.

**Independent Test**: Run both evaluation modes on the same configured sample/full set and confirm the notebook shows overall metrics for vector-only and hybrid in a comparable table, plus counts of evaluated and skipped cases for each mode.

**Acceptance Scenarios**:

1. **Given** both modes can run successfully, **When** comparison is generated, **Then** the notebook displays overall metric values for both modes at the same k cutoffs using the same metric definitions.
2. **Given** comparison is shown, **When** the user inspects counts, **Then** evaluated/skipped counts are reported per mode so unequal eligibility is visible.
3. **Given** only vector-only can run (hybrid unavailable), **When** comparison is requested, **Then** the notebook still reports vector-only results and clearly states hybrid comparison is unavailable, without inventing hybrid scores.

---

### User Story 4 - Persist evaluation artifacts for review and reproducibility (Priority: P2)

A project member wants machine-readable and human-readable outputs from the notebook run (case-level results, summary metrics, short report) so evaluation can be shared, checked into run folders, or pasted into reports without re-running the notebook.

**Why this priority**: Evaluation is a product requirement under the constitution; ephemeral cell output is not enough for review and reproducibility.

**Independent Test**: After a successful evaluation run, confirm the configured output directory contains case-level results, aggregate metrics JSON, and a markdown summary report for each completed mode (vector-only and/or hybrid), including run configuration and benchmark path.

**Acceptance Scenarios**:

1. **Given** a completed vector-only and/or hybrid evaluation, **When** artifacts are written, **Then** the notebook writes per-case results, aggregate metrics (overall + slice breakdowns), and a human-readable report under a user-configurable output directory.
2. **Given** artifacts are written, **When** a reviewer opens the summary, **Then** they can see QA path, mode labels, filter/top-k configuration, evaluated/skipped counts, and metric tables without reopening the notebook kernel.
3. **Given** both modes were run, **When** artifacts are written, **Then** mode-specific outputs are distinguishable (separate files or clearly namespaced sections) so vector-only and hybrid results cannot be confused.

---

### Edge Cases

- What happens when `data/benchmark/qa_final.jsonl` is missing or unreadable? The notebook MUST preflight the path and stop with a clear message before retrieval starts.
- What happens when the user path is written as `qa_final.json` but the frozen file is JSONL? The notebook MUST use the project's frozen benchmark path (`data/benchmark/qa_final.jsonl`) as the default and allow an explicit path override; it MUST fail clearly if the configured path does not exist.
- What happens when ground-truth chunk IDs are empty for an answerable-looking row? The notebook MUST skip with `skipped_missing_ground_truth` (or equivalent) rather than scoring empty relevance sets as perfect or zero without explanation.
- What happens when retrieval returns zero chunks for a question? The notebook MUST still score the case (metrics reflect misses), record empty retrieved IDs, and continue the run.
- What happens when hybrid GraphExpansion adds no extra chunks beyond seeds? The notebook MUST still score the hybrid result list as returned and MUST NOT treat zero-added expansion as a hard failure (GRAPH_MODULE expansion may legitimately add nothing after dedupe/cap).
- What happens when hybrid GraphTraversal visits no additional nodes, or graph-guided whitelist is empty? The notebook MUST surface empty-filter/empty-visit diagnostics per GRAPH_MODULE/context rules, MUST NOT silently search full corpus under a hybrid/graph-guided label, and MUST still complete scoring only on the legitimately obtained fused list (or mark the case failed/unavailable if hybrid path cannot proceed without silent fallback).
- What happens when the unfiltered vector pre-pass yields no seed IDs for GraphTraversal starts? The notebook MUST record empty-start diagnostics for that case and MUST NOT substitute ground-truth IDs; hybrid for that case is scored only if a legitimate non-leaking path remains, otherwise marked failed/unavailable without silent full-corpus fallback.
- What happens when only one of GraphExpansion or GraphTraversal can be constructed? Full hybrid evaluation MUST be unavailable (or explicitly degraded with a non-hybrid label); the notebook MUST NOT claim full hybrid when either required graph service is missing.
- What happens when graph/hybrid prerequisites are missing? Hybrid evaluation MUST be unavailable with an explicit message; vector-only evaluation MUST remain runnable.
- What happens when a single query raises a retrieval error mid-run? The notebook MUST record the error for that case (or skip with error count) and continue remaining cases rather than aborting the entire evaluation.
- What happens when k cutoffs exceed the number of retrieved results? Metrics MUST use the evaluation module semantics on the truncated retrieved ID list (same as CLI evaluation).
- What happens when the output directory already contains previous run files? The notebook MUST write to the configured path (overwriting or using a user-chosen run subdirectory) without corrupting the benchmark file.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide a **separate** notebook dedicated to retrieval evaluation, distinct from the interactive FAISS/hybrid demo notebooks.
- **FR-002**: The notebook MUST evaluate **vector-only retrieval** against the frozen QA benchmark.
- **FR-003**: The notebook MUST evaluate **hybrid retrieval** against the same frozen QA benchmark when hybrid prerequisites are available. Hybrid retrieval MUST mean: **GraphTraversal** + **GraphExpansion** with behavior and integration aligned to `docs/spec/GRAPH_MODULE.md`, outputs fused into the hybrid evidence chunk list used for scoring.
- **FR-003a**: Hybrid evaluation MUST invoke **GraphExpansion** on vector seed chunk IDs as specified in GRAPH_MODULE §7 (parent provision sibling window, `PROVISION_NEXT` walk within hop budget, dedupe/cap to context limit).
- **FR-003b**: Hybrid evaluation MUST invoke **GraphTraversal** as specified in GRAPH_MODULE §6 (verified edges only; modes `basis` depth-capped at 3, `guidance`, `validity`, `structure`, `neighbors`).
- **FR-003c**: Hybrid case records MUST indicate that both GraphExpansion and GraphTraversal were part of the hybrid path (including diagnostics when either service adds no extra chunk IDs or yields an empty whitelist/visit set).
- **FR-003d**: Hybrid ranked `retrieved_chunk_ids` used for metrics MUST be fused as: (1) vector seed chunk IDs in vector rank order, then (2) GraphExpansion context chunk IDs, then (3) any additional GraphTraversal-resolved chunk IDs not already present; duplicates MUST be removed by keeping the first occurrence so seed rank is preserved for MRR/nDCG. Under the §10 path, seeds are the filtered vector hits.
- **FR-003e**: Hybrid graph behavior MUST NOT invent alternate expansion/traversal semantics; when configurable, caps and mode names MUST match GRAPH_MODULE (e.g., basis `max_depth` default 3). Empty graph-guided candidate sets MUST be surfaced explicitly (no silent full-corpus hybrid label), consistent with GRAPH_MODULE context/filter warnings and project constitution.
- **FR-003f**: The **primary** hybrid evaluation sequence MUST follow GRAPH_MODULE §10: (1) GraphTraversal (and dynamic overlays / ContextBuilder as applicable) produce document whitelist IDs, (2) vector retrieval runs with that whitelist as `id_str_filter` / graph-guided filter, (3) GraphExpansion expands the retrieved hits. Vector-first-then-expand-only without Traversal is not full hybrid for this notebook.
- **FR-003g**: GraphTraversal **start IDs** for official scored hybrid evaluation MUST be **seed-derived** from an **unfiltered vector pre-pass** on the question text (map pre-pass hit chunk IDs to graph start nodes as the runtime contract requires). Hybrid evaluation MUST **never** use `ground_truth.document_ids`, `ground_truth.provision_ids`, or `ground_truth.chunk_ids` as traversal starts for official metrics (no label leakage into retrieval).
- **FR-004**: The notebook MUST use the project's **evaluation module** to compute the specified retrieval metrics and aggregations; it MUST NOT reimplement recall/hit/mrr/ndcg/jaccard formulas in ad-hoc notebook code.
- **FR-005**: The default evaluation dataset MUST be the frozen benchmark at `data/benchmark/qa_final.jsonl` (user-facing name: `qa_final.json` / `qa_final.jsonl`), with a config cell allowing path override.
- **FR-006**: For each configured k in the top-k list, the notebook MUST compute: `recall@k`, `hit@k`, `mrr@k`, `ndcg@k`, and `jaccard@k` per eligible case.
- **FR-007**: Eligibility for retrieval scoring MUST match evaluation-module practice: skip unanswerable rows and rows without ground-truth `chunk_ids`; score only answerable rows with non-empty ground-truth chunk ID sets.
- **FR-008**: The notebook MUST aggregate metrics overall and by `category`, `difficulty`, and `answer_type` using the evaluation module aggregation helpers.
- **FR-009**: The notebook MUST expose a configuration section for: QA path, output directory, top-k list, sample limit (optional), filter profile, score threshold, expand-units / hybrid toggles, and any paths required to load vector and hybrid retrieval runtimes.
- **FR-010**: Vector-only and hybrid runs MUST be clearly labeled in both on-screen output and persisted artifacts so results cannot be misread as the other mode.
- **FR-011**: Hybrid evaluation MUST refuse silent fallback: if hybrid cannot run, the notebook MUST surface unavailability rather than labeling vector-only results as hybrid.
- **FR-012**: The notebook MUST support both a smoke sample (limited N) and a full-benchmark run via configuration.
- **FR-013**: The notebook MUST persist, for each completed mode: case-level results, aggregate metrics JSON, and a markdown report including run configuration and counts.
- **FR-014**: The notebook MUST report evaluated count, skipped unanswerable count, and skipped missing-ground-truth count for each mode.
- **FR-015**: The notebook MUST continue after per-case retrieval failures, recording them without aborting the whole evaluation run.
- **FR-016**: The notebook MUST resolve project paths so it can run from the project root or `notebooks/` without hard-coded machine-specific absolute paths as the only option.
- **FR-017**: The notebook MUST NOT modify the frozen QA benchmark file.
- **FR-018**: End-to-end answer generation metrics (exact match, token F1, ROUGE-L, judge scores) are **out of scope** for this notebook; scope is retrieval-only evaluation for vector and hybrid modes.
- **FR-019**: When both modes complete, the notebook MUST present a side-by-side comparison of overall metrics at the shared k cutoffs.
- **FR-020**: Ground-truth matching for metrics MUST use retrieved `chunk_id` values against `ground_truth.chunk_ids`, preserving the shared identity contract.

### Key Entities

- **Benchmark QA case**: One row from `qa_final.jsonl` with `qa_id`, `question`, `category`, `difficulty`, `answer_type`, reference answer fields, and `ground_truth` (`document_ids`, `provision_ids`, `chunk_ids`).
- **Eligible evaluation case**: An answerable QA case with a non-empty ground-truth chunk ID set used for retrieval scoring.
- **Retrieval mode**: Either `vector_only` (pure vector path) or `hybrid` (vector seed + GraphExpansion + GraphTraversal fused evidence), always labeled explicitly.
- **Hybrid graph services**: **GraphExpansion** (GRAPH_MODULE §7 reading-order context) and **GraphTraversal** (GRAPH_MODULE §6 verified path queries; §10 integration with overlays/whitelist). Both are required constituents of hybrid evaluation.
- **Traversal start source**: Unfiltered vector pre-pass seeds mapped to graph start IDs for official hybrid runs; ground-truth IDs are scoring labels only, never retrieval starts.
- **Hybrid fused ranking**: Ordered chunk ID list for scoring = seeds (vector order) → expansion chunks → traversal chunks, deduped keep-first.
- **Graph module contract**: Hybrid evaluation treats `docs/spec/GRAPH_MODULE.md` as the authoritative behavior source for expansion, traversal, overlays, and retrieval integration.
- **Per-case retrieval score row**: QA metadata, ground-truth chunk IDs, ranked retrieved chunk IDs, mode label, optional diagnostics, and per-k metric values.
- **Aggregate metrics summary**: Overall averages plus slice breakdowns (category, difficulty, answer type), run configuration, and skip/eval counts.
- **Evaluation run artifacts**: Case JSONL/JSON records, metrics JSON, and markdown report written under the configured output directory.
- **Run configuration**: User-tunable evaluation and retrieval settings that must be recorded with artifacts for reproducibility.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with vector index artifacts and `data/benchmark/qa_final.jsonl` can complete a vector-only evaluation sample (at least 20 eligible cases when available) in one notebook session and obtain all five metric families at each configured k without writing new metric code.
- **SC-002**: When hybrid prerequisites are present, the same user can complete a hybrid evaluation sample on the same QA subset and obtain the same metric families under an explicit hybrid mode label that reflects a path using both GraphExpansion and GraphTraversal.
- **SC-003**: 100% of eligible scored cases in a successful run have per-k metrics produced via the evaluation module functions (no parallel ad-hoc scoring path for the official results).
- **SC-004**: After a dual-mode run, the notebook shows a comparison view where each shared metric@k appears for both modes (or hybrid is explicitly marked unavailable).
- **SC-005**: A completed run writes reviewable artifacts such that a second person can read overall metrics and counts from files alone, without re-executing the notebook.
- **SC-006**: Unanswerable and missing-ground-truth rows never appear as scored successes or scored failures in the metric averages; they appear only in skip counts.
- **SC-007**: Hybrid-unavailable conditions never produce hybrid-labeled metric tables derived from unlabeled vector-only retrieval.

## Assumptions

- The frozen evaluation file is the existing benchmark `data/benchmark/qa_final.jsonl`. The user phrase `qa_final.json` refers to this benchmark; JSONL is the on-disk format used by the evaluation module and prior notebooks.
- Retrieval metrics and aggregation behavior follow `docs/spec/EVALUATION_MODULE.md` and `src/evaluation/metrics.py` (`recall_at_k`, `hit_at_k`, `mrr_at_k`, `ndcg_at_k`, `jaccard_at_k`, `aggregate`, `aggregate_by`).
- Vector-only evaluation reuses the project's production vector retrieval path (as used by evaluation/retrieval tooling and FAISS notebook stack), not a one-off similarity hack.
- Hybrid evaluation means the project's hybrid path per `docs/spec/GRAPH_MODULE.md`: **primary operational sequence is §10** — GraphTraversal (+ overlays/ContextBuilder whitelist) → filtered vector search (`id_str_filter`) → GraphExpansion on hits — not expansion-only, not silent unfiltered vector under a hybrid label, and not a separate undocumented ranker.
- GraphTraversal start IDs for official hybrid metrics are seed-derived from an unfiltered vector pre-pass on the question; ground-truth IDs MUST NOT be used as traversal starts for scored hybrid evaluation (prevents label leakage). Ground-truth remains scoring-only.
- Hybrid fusion order for metrics is fixed: seeds (vector rank of filtered hits) → GraphExpansion chunks → any extra GraphTraversal-resolved chunk IDs, dedupe keep first occurrence.
- GraphTraversal modes and caps follow GRAPH_MODULE §6 (`basis` max depth 3, `guidance`, `validity`, `structure`, `neighbors`); only verified edges participate in path queries. Notebook config may select among those modes but MUST NOT redefine them.
- GraphExpansion follows GRAPH_MODULE §7 (provision windowing, horizontal `PROVISION_NEXT` walk, dedupe/`max_context` cap).
- Default top-k cutoffs align with existing evaluation practice (e.g., 1, 5, 10) unless the user changes them in the config section.
- Graph/hybrid inputs (structural graph and any required overlays) may be optional at environment level; vector-only must still work when hybrid cannot run.
- This notebook does not build indexes, synthesize QA, or run end-to-end generation/judge evaluation (`evaluate_e2e` track remains separate).
- Existing CLI `scripts/evaluate_retrieval.py` is vector-oriented; this feature adds a **notebook** surface that covers vector-only **and** hybrid under the same metric module, for interactive and report-oriented runs.
- Constitution principles apply: shared identities (`chunk_id` → `parent_unit_id` → `id_str`), no silent hybrid fallback, evaluation quality as a product requirement, and modular reuse of the evaluation package.
