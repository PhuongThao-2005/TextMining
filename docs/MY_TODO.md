# My - Detailed TODO

## Current status (2026-07-31)

- **Source work plan:** `next_phase_work_plan.md`, section `[Người 5 - My] — E2E runner, LLM/Agent ablation, UI, final report`
- **Reviewed history:** `192cef8` (runner/E2E), `6627c5b` (LLM/agent/UI/aggregation), `ec49794` (Kaggle E2E notebook), and merge `0fc26fb`
- **Total major tasks:** 10
- **Implementation-complete:** 7
- **Partially complete:** 2
- **Not started / blocked on result data:** 1

| Task | Current status | Evidence and boundary |
| --- | --- | --- |
| 1. Single-config runner | Completed | Production API, strict validation, manifests, isolated outputs, and fixture tests pass. |
| 2. Batch runner | Completed | Ordered continuation, resume, summaries, and fixture tests pass. |
| 3. E2E evaluation core | Completed | Metrics, grouped denominators, latency, fault isolation, redaction, and artifacts pass tests. |
| 4. E2E Kaggle notebook | Completed locally | `notebooks/e2e_rag_eval.ipynb` is valid, clone-first, zero-output, and covered by 17 offline tests. Actual Kaggle execution remains unverified. |
| 5. Local UI and guide | Completed locally | `ui/app.py`, `src/service/qa_service.py`, `docs/ui_demo.md`, import validation, and 13 service tests pass. Live provider/index questions remain unverified. |
| 6. Aggregation script | Completed locally | `scripts/aggregate_ablation_results.py` and 14 fixture tests cover validation, compatibility grouping, partial runs, deterministic CSV, and Markdown. No official runs exist to aggregate. |
| 7. Ablation report notebook | Completed locally | Clone-first, aggregate-only notebook, reusable analysis helper, documentation, and 28 fixture tests are complete. Actual Kaggle execution and team aggregate analysis remain unverified. |
| 8. LLM ablation runs | Partially complete | All three configs, prompt strategies, fairness validation, secret-safe model selection, and tests exist; official live runs/results do not. |
| 9. Agent ablation runs | Partially complete | Plain RAG and bounded Simple Planner implementations/configs/tests exist; official runs do not. MultiTool is explicitly deferred with a documented reason. |
| 10. Final summary/recommendation | Not started | `ablation_summary.csv`, `ablation_report.md`, and an evidence-backed recommendation cannot be produced without validated owner runs. |

### Current validation evidence

- Requested Task 7 regression suite: `122 passed`, including `28` focused report-notebook tests.
- Full repository suite: `209 passed, 6 skipped`.
- All six LLM/agent named configs pass structural dry-run; MultiTool returns the intended `deferred` status.
- `ui.app` imports successfully; both the E2E and ablation-report notebooks pass `nbformat` validation.
- No production benchmark, live provider, Kaggle, GPU, or official full-run result is claimed.

## Historical audit (2026-07-28)

The detailed checklist below is retained as the original point-in-time scan. Its per-task status and “missing file” statements are superseded by the current-status table above where later commits added implementation.

## Legend

- [x] Completed
- [-] Partially Completed
- [ ] Not Started
- [?] Needs Manual Verification

## Tasks

### 1. Single-Config Ablation Runner

**Description:** Create `scripts/run_ablation_config.py` so a named entry in `configs/ablation_configs.yaml` can load the requested retrieval/generation stack, execute retrieval and generation, calculate metrics, isolate per-case failures, and persist the complete run contract.

**Overall status:** [x] Completed

**Implementation evidence:**

- `configs/ablation_configs.yaml:1` documents schema version 1, supported providers/backends, explicit stack sections, and an offline example.
- `scripts/run_ablation_config.py:88` loads YAML with duplicate-key detection.
- `scripts/run_ablation_config.py:107` resolves configs by exact name.
- `scripts/run_ablation_config.py:114` validates required structure, types, backends, providers, top-k, seed, and enabled components.
- `scripts/run_ablation_config.py:189` validates benchmark, corpus, FAISS, sparse, and graph paths before execution.
- `scripts/run_ablation_config.py:212` constructs supported dense/generation/judge stacks and explicitly defers unwired components.
- `scripts/run_ablation_config.py:255` provides the reusable single-run API, collision-safe output creation, initial/final manifests, E2E execution, artifacts, counts, and statuses.
- `scripts/run_ablation_config.py:370` creates sanitized timestamped run IDs with a config hash.
- `scripts/run_ablation_config.py:491` records environment, package, Git, stack, path, command, artifact, count, and error metadata.
- `tests/test_ablation_config.py:101` through `tests/test_ablation_config.py:200` validate parsing, exact resolution, duplicate/incomplete/invalid config rejection, path checks, artifacts, manifests, collision prevention, and run IDs.

**Why this status:** The runner implements and tests the complete contract for components currently available in the repository. Unsupported sparse/graph/fusion/reranker/agent selections produce explicit deferred results rather than fake success. Real benchmark/index execution remains manual verification, not missing implementation.

**Detailed checklist:**

- [x] Implement reusable Exact Match, Token F1, and ROUGE-L functions.
  - Evidence: `src/evaluation/metrics.py:26`, `src/evaluation/metrics.py:30`, `src/evaluation/metrics.py:46`
- [x] Implement vector retriever construction for FAISS and Qdrant.
  - Evidence: `src/evaluation/retriever_factory.py:32`
- [x] Implement standalone E2E retrieval and generation loop.
  - Evidence: `scripts/evaluate_e2e.py:106`
- [x] Support a reference-answer generator for offline evaluator plumbing.
  - Evidence: `scripts/evaluate_e2e.py:77`, `scripts/evaluate_e2e.py:135`
- [x] Support a Gemini generator and optional Gemini judge.
  - Evidence: `scripts/evaluate_e2e.py:87`, `scripts/evaluate_e2e.py:253`
- [x] Create `scripts/run_ablation_config.py`.
  - Evidence: `scripts/run_ablation_config.py:1`
- [x] Read and validate `configs/ablation_configs.yaml`.
  - Evidence: `scripts/run_ablation_config.py:88`, `configs/ablation_configs.yaml:25`
- [x] Resolve a config by its exact name.
  - Evidence: `scripts/run_ablation_config.py:107`
- [x] Reject unknown, duplicate, incomplete, wrongly typed, or unsupported config definitions.
  - Evidence: `scripts/run_ablation_config.py:64`, `scripts/run_ablation_config.py:114`
- [x] Load available dense/generation/judge components and explicitly defer requested unwired stacks.
  - Evidence: `scripts/run_ablation_config.py:212`
- [x] Validate benchmark, corpus, index, graph, and optional sparse paths before a run.
  - Evidence: `scripts/run_ablation_config.py:189`
- [x] Prevent accidental overwrite of an existing run directory.
  - Evidence: `scripts/run_ablation_config.py:289`, `tests/test_ablation_config.py:184`
- [x] Create a unique sanitized `run_id` and complete initial/final `manifest.json`.
  - Evidence: `scripts/run_ablation_config.py:370`, `scripts/run_ablation_config.py:491`
- [x] Execute retrieval and generation through the selected supported stack.
  - Evidence: `scripts/run_ablation_config.py:319`
- [x] Write `resolved_config.yaml`, predictions, metrics, latency, errors, report, and manifest.
  - Evidence: `scripts/run_ablation_config.py:297`, `scripts/run_ablation_config.py:331`
- [x] Return non-zero CLI status for validation, deferred, needs-rerun, or failed runs.
  - Evidence: `scripts/run_ablation_config.py:389`
- [x] Add unit tests for config parsing, stack selection behavior, path validation, manifests, artifacts, and collisions.
  - Evidence: `tests/test_ablation_config.py:101`
- [?] Run a named-config smoke test against the official benchmark and real index.

**Dependencies:**

- The repository now has a documented config schema and offline example, but Owner 1's complete official config matrix/runbook is still required.
- Retrieval owners must expose stable constructors for sparse, graph, fusion, and reranker stacks before those enabled sections can execute.
- The local repository still has no official `data/benchmark/` or `data/faiss_index/` directory.

**Acceptance criteria:**

- [x] `python scripts/run_ablation_config.py --config <name>` resolves and executes the exact named config.
- [x] Every successful fixture run writes all mandatory artifacts under an isolated run directory.
- [x] Case failure is recorded without aborting remaining cases.
- [?] Repeat against the official benchmark and production retrieval index.

### 2. Batch Ablation Runner

**Description:** Create `scripts/run_ablation_batch.py` to execute an ordered list of configs, track each run independently, and continue after an individual config failure.

**Overall status:** [x] Completed

**Implementation evidence:**

- `scripts/run_ablation_batch.py:52` executes requested configs in order through the reusable single-run API.
- `scripts/run_ablation_batch.py:29` defines the independent machine-readable per-config status contract.
- `scripts/run_ablation_batch.py:147` generates collision-resistant batch IDs.
- `scripts/run_ablation_batch.py:203` implements minimal safe resume by skipping prior completed configs and rerunning failed/needs-rerun configs.
- `scripts/run_ablation_batch.py:230` writes a Markdown batch report in addition to `batch_summary.json`.
- `tests/test_ablation_batch.py:25` through `tests/test_ablation_batch.py:73` validate order, distinct runs, continuation, failed outcomes, summaries, and resume.

**Why this status:** The batch CLI and Python API preserve order, call the single-run API, isolate config failures, write independent statuses and artifacts, return meaningful status, and provide tested minimal resume behavior.

**Detailed checklist:**

- [x] Create `scripts/run_ablation_batch.py`.
  - Evidence: `scripts/run_ablation_batch.py:1`
- [x] Accept whitespace-separated and comma-separated names through `--configs`.
  - Evidence: `scripts/run_ablation_batch.py:153`, `scripts/run_ablation_batch.py:190`
- [x] Preserve exact requested execution order.
  - Evidence: `scripts/run_ablation_batch.py:66`
- [x] Invoke the single-config runner through a reusable Python API.
  - Evidence: `scripts/run_ablation_batch.py:89`
- [x] Give every config a distinct run ID and output directory.
  - Evidence: `scripts/run_ablation_config.py:283`
- [x] Continue to the next config after one config fails.
  - Evidence: `scripts/run_ablation_batch.py:112`, `tests/test_ablation_batch.py:49`
- [x] Record completed, failed, skipped, deferred, and needs-rerun statuses.
  - Evidence: `scripts/run_ablation_batch.py:29`, `scripts/run_ablation_config.py:42`
- [x] Write `batch_summary.json` and `batch_report.md`.
  - Evidence: `scripts/run_ablation_batch.py:128`
- [x] Print a final summary and return an appropriate exit code.
  - Evidence: `scripts/run_ablation_batch.py:167`
- [x] Implement minimal safe resume without overwriting completed runs.
  - Evidence: `scripts/run_ablation_batch.py:203`
- [x] Add tests for all-success, partial-failure, invalid-config continuation, order, distinct runs, summaries, and resume.
  - Evidence: `tests/test_ablation_batch.py:25`
- [?] Run the work-plan batch command against real retrieval stacks.

**Dependencies:**

- Task 1's reusable API is implemented and tested.
- The full official config matrix and production retrieval artifacts remain external dependencies.

**Acceptance criteria:**

- [x] Fixture batches execute all requested configs without overwrite.
- [x] A failed config does not erase, invalidate, or block completed sibling runs.
- [?] Repeat the work-plan batch against production stacks and artifacts.

### 3. E2E Evaluation, Metrics, Latency, and Fault Isolation

**Description:** Evaluate complete RAG answers and record required answer metrics, grouped breakdowns, stage-level latency, and per-case errors.

**Overall status:** [x] Completed

**Implementation evidence:**

- `src/evaluation/e2e_runner.py:90` provides reusable case execution with per-stage fault isolation and continuation.
- `src/evaluation/e2e_runner.py:228` explicitly defines successful cases as the quality-metric denominator.
- `src/evaluation/e2e_runner.py:243` writes predictions, metrics, latency, errors, and report artifacts.
- `src/evaluation/e2e_runner.py:264` aggregates count, mean, median, min, max, and p95 for every recorded latency stage.
- `src/evaluation/e2e_runner.py:334` renders overall/category/answer-type/difficulty metrics, counts, latency, and failure-stage summaries.
- `src/evaluation/e2e_runner.py:400` consumes real hybrid latency breakdowns when exposed and otherwise measures dense retrieval.
- `src/evaluation/e2e_runner.py:482` records sanitized type/message/trace/retry/timestamp error details.
- `scripts/evaluate_e2e.py:115` preserves the legacy CLI as a thin consumer of the reusable core.
- `tests/test_evaluate_e2e.py:94` through `tests/test_evaluate_e2e.py:203` validate continuation, retrieval/generation/judge/parse/serialization failures, redaction, artifacts, difficulty report, latency, denominators, and disabled-stage null handling.

**Why this status:** The reusable core and legacy CLI now implement all requested metrics, status/count consistency, stage latency, aggregation, sanitized error artifacts, failure continuation, and complete reporting. Official benchmark values remain manual verification because production data/indexes are absent.

**Detailed checklist:**

- [x] Calculate Exact Match.
- [x] Calculate Token F1.
- [x] Calculate ROUGE-L.
- [x] Calculate Unanswerable Accuracy.
- [x] Calculate Context Recall@k.
- [x] Aggregate metrics overall.
- [x] Break down metrics by category.
- [x] Break down metrics by answer type.
- [x] Break down metrics by difficulty.
- [x] Persist per-case predictions and retrieved context.
- [x] Persist aggregate E2E metrics.
- [x] Unit-test core answer metric normalization and scoring.
- [x] Measure total per-case latency.
- [x] Measure dense retrieval latency.
- [x] Consume sparse retrieval latency when the retriever exposes a breakdown.
- [x] Consume graph traversal latency when the retriever exposes a breakdown.
- [x] Consume fusion latency when the retriever exposes a breakdown.
- [x] Consume reranker latency when the retriever exposes a breakdown.
- [x] Measure generation latency.
- [x] Measure judge and serialization latency where enabled.
- [x] Store structured per-case stage latency in `e2e_predictions.jsonl`.
- [x] Aggregate count, mean, median, min, max, and p95 by stage in `latency.json`.
- [x] Wrap each QA execution in fault isolation.
- [x] Recover from malformed JSONL rows and record failed/skipped reasons.
- [x] Continue after retrieval, generation, judge, metric, or serialization failure.
- [x] Redact secrets from error messages and shortened tracebacks.
- [x] Include difficulty, counts, stage latency, and failure stages in Markdown.
- [x] Keep failed/skipped cases out of quality averages and document denominators.
- [x] Add direct tests for scoring, output, all major failure stages, continuation, latency, and denominators.
- [?] Validate metric values on a frozen benchmark sample.

**Dependencies:**

- Official benchmark and retrievable index are missing locally.
- `faiss-cpu` and `sentence-transformers` are not installed in the current Python environment.
- No Gemini or OpenAI-compatible generator credentials are configured.

**Acceptance criteria:**

- [x] Every attempted fixture case has status and available stage latency; successful cases have quality metrics.
- [x] One failing case does not terminate the run.
- [x] Overall and all three grouped breakdowns are present in machine-readable and report outputs.
- [?] Confirm production latency breakdowns and metric values on the official benchmark.

### 4. E2E RAG Evaluation Notebook

**Description:** Deliver `notebooks/e2e_rag_eval.ipynb` as My's reproducible E2E evaluation notebook.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- `notebooks/e2e_rag_eval.ipynb` does not exist.
- `notebooks/archive/faiss_retrieval_ready.ipynb` demonstrates retrieval, optional graph expansion, generation, and a small benchmark sample.
- The archived notebook explicitly describes its sample as a demo rather than a full E2E evaluation.
- The archived notebook is not the required deliverable and has only one retained output across its code cells.

**Why this status:** Supporting notebook material exists, but no dedicated E2E evaluation notebook implements the work-plan deliverable.

**Detailed checklist:**

- [ ] Create `notebooks/e2e_rag_eval.ipynb`.
- [ ] Import production modules instead of duplicating runner logic.
- [ ] Load a named ablation config.
- [ ] Display benchmark/config/corpus preflight information.
- [ ] Support a bounded smoke sample and a full-run mode.
- [ ] Show per-case answer, citations/context, errors, and latency.
- [ ] Show overall and grouped E2E metric tables.
- [ ] Persist artifacts through the same code path as the CLI runner.
- [ ] Document required environment variables without embedding credentials.
- [ ] Clear large/transient outputs before committing.
- [?] Execute all cells from a clean kernel using available artifacts.

**Dependencies:**

- Tasks 1 and 3 should provide the reusable execution and reporting APIs.
- Official benchmark, index, config matrix, and generator credentials are required for a real run.

**Acceptance criteria:**

- A clean-kernel run reproduces the same metrics and artifacts as the CLI for the same config and case set.

### 5. Local UI Demo and UI Guide

**Description:** Build a local Streamlit UI in `ui/app.py` or `app.py` and document setup and usage in `docs/ui_demo.md`.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- Neither `ui/app.py` nor root `app.py` exists.
- `docs/ui_demo.md` does not exist.
- The `ui/` directory exists but contains no files.
- Streamlit is installed in the current Python environment, so the missing UI is not caused by an unavailable framework.
- `scripts/evaluate_e2e.py` and `src/generation/reasoning_client.py` contain backend building blocks but are not connected to a UI.

**Why this status:** No UI route, controls, rendering, integration, or user guide exists.

**Detailed checklist:**

- [ ] Create `ui/app.py` or root `app.py`.
- [ ] Add a question input.
- [ ] Add a retrieval-config dropdown sourced from the config matrix.
- [ ] Add a top-k input with safe bounds.
- [ ] Add a filter-profile selector.
- [ ] Add a Graph toggle.
- [ ] Add a Reranker toggle.
- [ ] Add an Ask button.
- [ ] Validate incompatible config/toggle combinations.
- [ ] Load expensive models/indexes through Streamlit resource caching.
- [ ] Call the production retrieval/generation pipeline.
- [ ] Render the final answer.
- [ ] Render citation-bearing context rows.
- [ ] Render retrieval scores and ranks.
- [ ] Render stage-level latency.
- [ ] Render warnings, missing configuration, and recoverable errors.
- [ ] Handle empty context and abstention clearly.
- [ ] Avoid displaying API keys or secret-bearing exception text.
- [ ] Add `docs/ui_demo.md` with install, environment, launch, controls, and troubleshooting instructions.
- [ ] Add lightweight tests for UI-facing helper functions where practical.
- [?] Launch the UI locally.
- [?] Ask an answerable question and verify answer/context/citation/latency rendering.
- [?] Ask an unanswerable question and verify safe abstention.
- [?] Verify the selected main-pipeline config works in the UI.

**Dependencies:**

- Stable runner/service API from Tasks 1 and 3.
- Owner 1's config matrix.
- Real index and optional graph artifacts.
- Generator credentials for non-reference answers.

**Acceptance criteria:**

- The local UI answers a question with the selected pipeline and displays answer, context/citation, latency, and actionable errors.

### 6. Ablation Result Aggregation Script

**Description:** Create `scripts/aggregate_ablation_results.py` to validate and aggregate all eligible run directories into comparison outputs.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- `scripts/aggregate_ablation_results.py` does not exist.
- No repository script scans `evaluation_runs/ablation/` or combines retrieval, E2E, and latency metrics across runs.
- `notebooks/hybrid_retrieval_eval.ipynb` creates a notebook-local summary for Người 3's five configs only; it is not the cross-team aggregator.

**Why this status:** No reusable cross-run aggregation implementation exists.

**Detailed checklist:**

- [ ] Create `scripts/aggregate_ablation_results.py`.
- [ ] Accept `--runs-dir`, defaulting to `evaluation_runs/ablation`.
- [ ] Discover run directories without treating aggregate outputs as runs.
- [ ] Load and validate every `manifest.json`.
- [ ] Exclude mismatched benchmark or corpus versions.
- [ ] Load retrieval metrics when present.
- [ ] Load E2E metrics when present.
- [ ] Load latency metrics when present.
- [ ] Preserve failure, skip, deferred, and validation notes.
- [ ] Handle missing optional metrics without crashing.
- [ ] Detect duplicate run IDs/config collisions.
- [ ] Compute or preserve average and median latency.
- [ ] Write deterministic `ablation_summary.csv`.
- [ ] Write `ablation_report.md`.
- [ ] Add fixture-based tests for valid, invalid, partial, failed, and mixed-version runs.
- [?] Aggregate the team's real run directory.

**Dependencies:**

- Owner 1's manifest schema and list of valid runs.
- Stable run artifacts from all owners.

**Acceptance criteria:**

- The script produces a reproducible comparison table containing every required quality, retrieval, latency, and notes/failure column.

### 7. Ablation Report Notebook

**Description:** Create `notebooks/ablation_report.ipynb` for interactive comparison tables, plots, and final analysis.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- `notebooks/ablation_report.ipynb` does not exist.
- Retrieval notebooks contain owner-specific comparisons but no cross-team final report notebook.

**Why this status:** There is no notebook that consumes the final aggregate outputs or covers all required ablation families.

**Detailed checklist:**

- [ ] Create `notebooks/ablation_report.ipynb`.
- [ ] Load `ablation_summary.csv` as the single comparison source.
- [ ] Display retrieval ablation results.
- [ ] Display embedding ablation results.
- [ ] Display reranker ablation results.
- [ ] Display graph ablation results.
- [ ] Display LLM ablation results.
- [ ] Display agent ablation results or defer notes.
- [ ] Plot quality versus latency.
- [ ] Highlight failed, excluded, and deferred configs.
- [ ] Produce reproducible analysis text/tables for the final report.
- [?] Run the notebook from a clean kernel after all team results are available.

**Dependencies:**

- Task 6 and valid outputs from all owners.

**Acceptance criteria:**

- The notebook reproduces every final report table from aggregate artifacts without manual copy/paste.

### 8. LLM Ablation Runs

**Description:** Execute and analyze `LLM-BaseReasoning`, `LLM-CoTReasoning`, and `LLM-LargerModel`.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- `src/generation/reasoning_client.py:16` contains one reasoning-oriented prompt.
- `scripts/evaluate_e2e.py:78` allows an arbitrary Gemini model name.
- There is no config matrix entry in the repository for any required LLM config.
- There is no distinct base-versus-CoT prompt selection in the E2E evaluator.
- There are no run directories, manifests, metrics, latency files, or reports for the three LLM configs.
- Generator credentials are not configured in the current environment.

**Why this status:** Prompt/client foundations do not constitute ablation runs. No required named config or result exists.

**Detailed checklist:**

- [x] Implement a reusable OpenAI-compatible generation client.
  - Evidence: `src/generation/reasoning_client.py:70`
- [x] Redact configured API keys from generation errors.
  - Evidence: `src/generation/reasoning_client.py:114`
- [x] Parse dedicated reasoning fields and `<think>` blocks.
  - Evidence: `src/generation/reasoning_client.py:123`
- [x] Unit-test generation config masking, parsing, prompting, skip, and error paths.
  - Evidence: `tests/generation/test_reasoning_client.py:22`
- [ ] Define and freeze the `LLM-BaseReasoning` config.
- [ ] Define a base prompt that does not request CoT/reasoning.
- [ ] Execute `LLM-BaseReasoning` on the official benchmark.
- [ ] Validate its manifest, metrics, latency, and failure counts.
- [ ] Define and freeze the `LLM-CoTReasoning` config.
- [ ] Define a reasoning-prompt strategy that preserves fair retrieval and decoding controls.
- [ ] Execute `LLM-CoTReasoning` on the same benchmark/corpus.
- [ ] Validate its manifest, metrics, latency, and failure counts.
- [ ] Define and freeze the `LLM-LargerModel` config.
- [ ] Change only the intended model variable relative to the baseline.
- [ ] Execute `LLM-LargerModel` on the same benchmark/corpus.
- [ ] Validate its manifest, metrics, latency, quota, and failure counts.
- [ ] Compare answer quality, unanswerable behavior, and generation latency.
- [ ] Document rate-limit, quota, retry, and deferred-run decisions.
- [?] Verify live API model names and availability before the full run.
- [?] Verify no provider returns hidden reasoning that should be exposed in UI/report outputs.

**Dependencies:**

- Tasks 1 and 3.
- Owner 1's config matrix and frozen benchmark/corpus.
- Generator API credentials and sufficient quota.

**Acceptance criteria:**

- All three named configs have valid, directly comparable run artifacts, or an explicit deferred note where the work plan permits it.

### 9. Agent Ablation Runs

**Description:** Execute and analyze `Agent-None-PlainRAG`, `Agent-SimplePlanner`, and, if feasible, `Agent-MultiTool-Orchestrated`.

**Overall status:** [-] Partially Completed

**Implementation evidence:**

- `scripts/evaluate_e2e.py:132` implements a plain retrieve-then-generate path that can serve as the foundation for `Agent-None-PlainRAG`.
- `notebooks/archive/faiss_retrieval_ready.ipynb` demonstrates ad hoc plain/hybrid RAG generation.
- No named `Agent-None-PlainRAG` config or result exists.
- No planner, agent state, tool interface, tool-call trace, orchestration policy, or agent-specific test exists.
- No agent output/defer note exists.

**Why this status:** A plain RAG foundation exists, but none of the three required named agent ablations has been configured or run, and both actual agent variants are absent.

**Detailed checklist:**

- [x] Implement a basic retrieve-then-generate execution path.
  - Evidence: `scripts/evaluate_e2e.py:129`
- [ ] Define `Agent-None-PlainRAG` with fixed retrieval/generation settings.
- [ ] Execute and validate the plain RAG baseline run.
- [ ] Define the Simple Planner decision/state contract.
- [ ] Expose retrieval as an explicit planner tool.
- [ ] Bound planner steps and retries.
- [ ] Record planner decisions and tool calls without leaking secrets.
- [ ] Ensure the planner actually invokes retrieval for answerable queries.
- [ ] Execute and validate `Agent-SimplePlanner`.
- [ ] Define the MultiTool orchestrator and allowed tools.
- [ ] Add loop, timeout, malformed-call, and empty-result safeguards.
- [ ] Execute `Agent-MultiTool-Orchestrated`, or write an explicit defer note with reason and smoke evidence.
- [ ] Compare answer quality, tool-use correctness, failure rate, and latency against plain RAG.
- [ ] Add unit tests with deterministic fake tools/models.
- [?] Inspect live agent traces for correct retrieval calls and bounded behavior.

**Dependencies:**

- Tasks 1 and 3.
- Stable retrieval APIs from other owners.
- Generator credentials and quota.
- A team decision on which tools the multi-tool agent may call.

**Acceptance criteria:**

- Plain RAG and Simple Planner have valid comparable results.
- MultiTool has a valid result or an explicit evidence-backed defer note.

### 10. Final Summary, Report, and Main-Pipeline Recommendation

**Description:** Produce `ablation_summary.csv`, `ablation_report.md`, and a final evidence-backed recommendation covering every ablation family and deferred config.

**Overall status:** [ ] Not Started

**Implementation evidence:**

- `evaluation_runs/ablation/ablation_summary.csv` does not exist.
- `evaluation_runs/ablation/ablation_report.md` does not exist.
- No `evaluation_runs/` directory exists.
- No final cross-family table, latency-quality analysis, best-config conclusion, or deferred-config register exists.

**Why this status:** The required final artifacts and conclusions have not been produced.

**Detailed checklist:**

- [ ] Generate `ablation_summary.csv`.
- [ ] Include config name.
- [ ] Include Exact Match.
- [ ] Include Token F1.
- [ ] Include ROUGE-L.
- [ ] Include Unanswerable Accuracy.
- [ ] Include Context Recall@k.
- [ ] Include Recall@1/5/10 where available.
- [ ] Include MRR and nDCG where available.
- [ ] Include average and median latency.
- [ ] Include notes/failure/deferred status.
- [ ] Generate `ablation_report.md`.
- [ ] Add the retrieval ablation table.
- [ ] Add the embedding ablation table.
- [ ] Add the reranker ablation table.
- [ ] Add the graph ablation table.
- [ ] Add the LLM ablation table.
- [ ] Add the agent ablation table or defer section.
- [ ] Analyze latency-quality trade-offs.
- [ ] Identify excluded runs and explain benchmark/corpus mismatches.
- [ ] Identify deferred configs and reasons.
- [ ] Recommend the best main-pipeline config using explicit criteria.
- [ ] Record limitations, confidence, and unresolved risks.
- [ ] Verify the recommended config is selectable and usable in the UI.
- [?] Have each owner review the interpretation of their ablation results.

**Dependencies:**

- Tasks 5 through 9.
- Owner 1's validated run list and experiment-setup metadata.
- Analysis notes from Dense/Embedding, Hybrid/Reranker, and Graph owners.

**Acceptance criteria:**

- The report covers every required ablation family, compares quality and latency, explains failures/deferred runs, and names a defensible main-pipeline config that works in the UI.

## Completed Work

Three major My-owned obligations are now fully implemented and validated offline:

- Named single-config runner with strict config validation, unique run directories, initial/final manifests, explicit deferred stacks, and complete artifacts.
- Ordered batch runner with independent statuses, continuation, machine-readable/Markdown summaries, and minimal safe resume.
- Reusable E2E core with metrics, stage latency, fault isolation, sanitized errors, consistent denominators, and complete reporting.
- Core E2E answer metrics: Exact Match, Token F1, ROUGE-L, Unanswerable Accuracy, and Context Recall@k.
- Overall and category/answer-type/difficulty metric aggregation in JSON.
- Standalone vector retrieve-then-generate evaluator with reference and Gemini generator modes.
- Optional Gemini LLM judge plumbing.
- OpenAI-compatible generation client, prompt formatting, reasoning parsing, skip handling, and secret redaction.
- Unit tests for metric primitives and generation-client behavior.
- An archived full-pipeline demonstration notebook that can inform, but not replace, the dedicated E2E notebook and UI.

## Partially Completed Work

### Agent Ablation

- **Existing:** Plain retrieve-then-generate foundation.
- **Missing:** Named plain-RAG run, planner, multi-tool orchestration, tool traces, safeguards, tests, and all agent result artifacts.
- **Next steps:** Freeze the plain RAG baseline first, then implement the smallest deterministic planner with one retrieval tool.

## Missing Work

- Owner 1's complete official config matrix, runbook, and production manifest governance.
- Production stack adapters for sparse, graph, fusion, reranker, and agent selections in the generic runner.
- `notebooks/e2e_rag_eval.ipynb`.
- `ui/app.py` or `app.py`.
- `docs/ui_demo.md`.
- `scripts/aggregate_ablation_results.py`.
- `notebooks/ablation_report.ipynb`.
- All three LLM ablation run artifacts.
- All three agent ablation run artifacts or permitted defer note.
- `evaluation_runs/ablation/ablation_summary.csv`.
- `evaluation_runs/ablation/ablation_report.md`.
- Final best-config recommendation and UI verification.

## Risks

- **Incomplete official matrix:** A documented schema and offline example now exist, but the complete team-owned config matrix and runbook are still absent.
- **Missing runtime artifacts:** The official benchmark directory and FAISS index directory are absent locally, preventing a real E2E smoke run.
- **Dependency metadata gap:** `pyproject.toml` configures tools but declares no project dependencies or runnable scripts.
- **Environment mismatch:** `faiss-cpu` and `sentence-transformers` are not installed. Streamlit, Gemini SDK, OpenAI SDK, PyYAML, and pandas are installed.
- **Generic stack limitation:** The config schema represents sparse, graph, fusion, reranker, and agent sections, but the generic runner deliberately marks enabled unwired components deferred.
- **Prompt comparability risk:** The repository has one reasoning-oriented generation prompt but no frozen base-versus-CoT prompt pair.
- **No result evidence:** There are no committed/local ablation run outputs for My's configs.
- **Credential/quota risk:** Gemini and OpenAI-compatible credentials are not configured, and full-run quota is unverified.
- **Aggregation integrity risk:** Runs now contain rich manifests, but the cross-run aggregator that excludes mismatched benchmark/corpus versions is still missing.
- **Notebook drift:** Existing notebooks include duplicated inline evaluation/retrieval logic, which can diverge from production modules.
- **Planned citation work incomplete:** `specs/009-reliable-generation-citations/tasks.md` lists unimplemented structured citation work that may affect authoritative UI/evaluation citation output.

## Recommended Priority

### Priority 1 - Blocking Features

1. Coordinate with Owner 1 to complete the official config matrix, benchmark path, corpus version, and runbook.
2. Obtain or mount the official benchmark and compatible FAISS/Qdrant index.
3. Add production adapters for the retrieval stacks selected by the official matrix.
4. Run the named-config and batch production smoke tests.

### Priority 2 - Core Functionality

1. Freeze and run `LLM-BaseReasoning`, then `LLM-CoTReasoning` and `LLM-LargerModel`.
2. Freeze and run `Agent-None-PlainRAG`, then implement `Agent-SimplePlanner`.
3. Build the aggregator before full runs so output-contract problems are detected early.
4. Keep the multi-tool agent deferred until the baseline and planner are stable.

### Priority 3 - UX and Analysis

1. Build the Streamlit UI against the same reusable runner/service API.
2. Reuse `src/evaluation/e2e_runner.py` artifacts for context/citation and stage-latency displays.
3. Create the E2E and report notebooks as thin consumers of production APIs/artifacts.
4. Attempt the multi-tool agent only after the baseline and planner are stable.

### Priority 4 - Testing and Documentation

1. Add `docs/ui_demo.md`.
2. Declare project dependencies and optional FAISS/model extras.
3. Run production CLI smoke, notebook clean-kernel, and UI manual tests.
4. Aggregate validated runs and complete the final report and recommendation.

## Related Files

| File | Purpose | Status | Notes |
| --- | --- | --- | --- |
| `next_phase_work_plan.md` | Source assignment and acceptance criteria | Available | Untracked in current Git status |
| `scripts/evaluate_e2e.py` | Backward-compatible standalone E2E CLI | Completed | Uses reusable core; supports FAISS/Qdrant, latency, errors, and complete report |
| `src/evaluation/e2e_runner.py` | Reusable E2E execution, latency, errors, metrics, and artifacts | Completed | Shared by legacy and ablation CLIs |
| `src/evaluation/metrics.py` | Retrieval and answer metric primitives | Completed foundation | Covered by focused unit tests |
| `src/evaluation/retriever_factory.py` | FAISS/Qdrant vector retriever construction | Partial foundation | No hybrid/graph/reranker factory |
| `src/generation/reasoning_client.py` | OpenAI-compatible generation orchestration | Completed foundation | Reused by the ablation stack builder |
| `tests/generation/test_reasoning_client.py` | Offline generation-client tests | Completed foundation | 9 tests passed |
| `tests/test_evaluation_metrics.py` | Metric primitive tests | Completed foundation | 2 tests passed |
| `notebooks/archive/faiss_retrieval_ready.ipynb` | Archived full-pipeline demo | Partial reference | Not the required E2E notebook |
| `notebooks/hybrid_retrieval_eval.ipynb` | Người 3's hybrid/reranker ablation notebook | Available dependency | Has notebook-local config loop and latency examples |
| `configs/ablation_configs.yaml` | Versioned ablation config schema and offline example | Completed foundation | Official team matrix still required |
| `scripts/run_ablation_config.py` | Required named-config runner | Completed | Strict validation, manifests, artifacts, explicit deferred stacks |
| `scripts/run_ablation_batch.py` | Required batch runner | Completed | Ordered continuation, statuses, reports, minimal resume |
| `tests/test_ablation_config.py` | Single-run config/manifest/artifact tests | Completed | 7 tests |
| `tests/test_ablation_batch.py` | Batch order/failure/resume tests | Completed | 3 tests |
| `tests/test_evaluate_e2e.py` | E2E latency/fault/artifact/denominator tests | Completed | 5 tests |
| `notebooks/e2e_rag_eval.ipynb` | Required E2E notebook | Missing | Create |
| `ui/app.py` or `app.py` | Required local UI | Missing | Create one canonical entry point |
| `docs/ui_demo.md` | Required UI guide | Missing | Create |
| `scripts/aggregate_ablation_results.py` | Required cross-run aggregator | Missing | Create |
| `notebooks/ablation_report.ipynb` | Required final analysis notebook | Missing | Create |
| `evaluation_runs/ablation/ablation_summary.csv` | Required aggregate table | Missing | Generate from validated runs |
| `evaluation_runs/ablation/ablation_report.md` | Required final ablation report | Missing | Generate and finalize |
| `pyproject.toml` | Pytest and type-tool path configuration | Partial | No dependency or command metadata |
| `specs/009-reliable-generation-citations/tasks.md` | Planned structured citation reliability work | Not implemented | Relevant to UI/eval citation contract |

## Build and Test Results

### Commands executed

| Command | Result | Effect on My's tasks |
| --- | --- | --- |
| `python -m pytest -p no:cacheprovider tests/test_evaluate_e2e.py tests/test_ablation_config.py tests/test_ablation_batch.py tests/test_evaluation_metrics.py tests/generation/test_reasoning_client.py` | Success: 26 passed | Focused runner, E2E, metrics, and generation validation |
| `python -m pytest -p no:cacheprovider` | Success: 141 passed, 6 skipped | Full repository regression suite passes |
| `python -m compileall -q scripts src tests` | Success | Syntax validation passed |
| `python scripts/run_ablation_config.py --help` | Success | Single-run CLI contract imports and renders |
| `python scripts/run_ablation_batch.py --help` | Success | Batch CLI contract imports and renders |
| `python scripts/evaluate_e2e.py --help` | Success | Backward-compatible evaluator CLI imports and renders |
| `python scripts/run_ablation_config.py --config Example-Reference-Hashing --dry-run` | Success | Exact config resolution and structural validation passed without claiming a production run |
| `$env:MYPYPATH='src'; mypy --no-incremental --explicit-package-bases --follow-imports=skip src/evaluation/e2e_runner.py scripts/run_ablation_config.py scripts/run_ablation_batch.py scripts/evaluate_e2e.py` | Success: no issues in 4 changed modules | New/refactored ablation and E2E modules pass isolated type checking |
| `ruff check .` | Not run: `ruff` unavailable | No Ruff result claimed |

### Validation notes

- The previous two FAISS missing-index failures were fixed by validating required files before importing optional `faiss` in `src/retrieval/sqlite_faiss_store.py:288`.
- A repository-following `mypy` run still reports pre-existing type errors in retrieval/knowledge-graph modules; the isolated changed-module run passes.
- Offline smoke behavior is covered by temporary pytest fixtures; no fake official benchmark data was added.

### Validation not possible

- Real E2E run: no local official benchmark or FAISS index.
- LLM/agent run: official named configs, API credentials, and confirmed quota are unavailable.
- UI run: no UI implementation.
- Aggregation/report run: no ablation run directory or result artifacts.
- Notebook clean-kernel run: required notebooks do not exist.

## Manual Verification

### Named-Config Runner Smoke Test

- **Setup:** Install declared dependencies; provide the official benchmark, compatible index, config matrix, and a writable empty output root.
- **Actions:** Run `python scripts/run_ablation_config.py --config LLM-BaseReasoning --limit 5`.
- **Expected result:** A new run directory contains a valid manifest, retrieval/E2E metrics, predictions, latency, and report; no existing directory is overwritten.

### Per-Case Failure Continuation

- **Setup:** Use a five-case fixture and a fake generator that fails on case three.
- **Actions:** Execute the single-config runner.
- **Expected result:** Cases one, two, four, and five complete; case three records a sanitized error; aggregate counts show one failure; the process does not abort.

### LLM Ablation Comparability

- **Setup:** Freeze benchmark, corpus, retrieval config, decoding controls, and three LLM configs.
- **Actions:** Run all three LLM configs and compare manifests.
- **Expected result:** Only intended prompt/model variables differ; every run has the same evaluated QA set or documents justified skips.

### Agent Retrieval Behavior

- **Setup:** Enable deterministic trace logging with fixed questions.
- **Actions:** Run plain RAG, Simple Planner, and MultiTool/deferred smoke.
- **Expected result:** Planner variants call approved retrieval tools correctly, stay within step limits, and record tool latency and failures.

### UI Answerable Question

- **Setup:** Launch Streamlit with the selected main-pipeline config, index, and credentials.
- **Actions:** Choose a config, set top-k/filter/toggles, submit an answerable legal question.
- **Expected result:** The UI displays a grounded answer, citation-bearing context table, scores/ranks, stage latency, and no secret material.

### UI Unanswerable and Error States

- **Setup:** Keep the UI running; prepare an unanswerable question and a deliberately unavailable config/index.
- **Actions:** Submit each case.
- **Expected result:** The first safely abstains; the second shows an actionable warning/error without crashing the app.

### Aggregation Integrity

- **Setup:** Prepare valid runs plus one wrong-corpus run, one partial run, one failed run, and one deferred config.
- **Actions:** Run `python scripts/aggregate_ablation_results.py --runs-dir evaluation_runs/ablation`.
- **Expected result:** The wrong-corpus run is excluded, partial/failed/deferred states remain visible, and CSV/Markdown totals reconcile with source manifests.

### Final Recommendation

- **Setup:** Complete all valid runs and owner reviews.
- **Actions:** Regenerate the summary/report and launch the recommended config in the UI.
- **Expected result:** Tables reproduce source metrics, the recommendation follows stated quality/latency criteria, deferred configs are explained, and the chosen pipeline works end to end.
