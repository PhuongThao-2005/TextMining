# My - Detailed TODO

## Summary

- **Scan date:** 2026-08-01
- **Repository scope:** branch `my`, commit `94757a2`; clean working tree at audit start; no merge, rebase, cherry-pick, revert, or unmerged index entries.
- **Total major tasks:** 10. Subtasks do not increase this total.
- **Current overall assessment:** Tasks 1–8 are implemented. Task 9 has complete Plain RAG and Simple Planner implementations but an explicitly deferred MultiTool sub-scope. Task 10 cannot begin conclusively until real compatible experiment outputs and teammate review are available. No task is production-validated by this audit.

### Major implementation status

| Status | Count | Tasks |
| --- | ---: | --- |
| [x] Implementation Complete | 8 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [-] Partially Implemented | 1 | 9 |
| [ ] Not Started | 1 | 10 |

### Validation and dependency status

| Status | Count | Meaning |
| --- | ---: | --- |
| Production validated | 0 | No official benchmark/provider/Kaggle result is present. |
| [?] Awaiting manual/live validation | 9 | Tasks 1–9 have at least one unperformed manual, Kaggle, browser, or production check. |
| [B] Blocked by external dependency | 8 | Tasks 1, 2, 3, 6, 7, 8, 9, and 10 require official/team artifacts or decisions for remaining acceptance. |
| [D] Explicitly deferred | 1 | The MultiTool sub-scope within Task 9 is deferred. |

These validation counts overlap implementation counts: an implementation-complete task can still be production-pending or externally blocked.

## Status Vocabulary

- `[x] Implementation Complete`
- `[-] Partially Implemented`
- `[ ] Not Started`
- `[?] Awaiting Manual Validation`
- `[B] Blocked by External Dependency`
- `[D] Explicitly Deferred`

## Tasks

### 1. Single-Config Ablation Runner

**Overall implementation status:** [x] Implementation Complete
**Validation status:** Offline tests and structural dry-runs pass; [?] official production smoke pending.

**Implementation evidence:**

- `scripts/run_ablation_config.py:118`, `:141`, and `:148` load, exactly resolve, and strictly validate named configs.
- `scripts/run_ablation_config.py:326` validates required paths before execution.
- `scripts/run_ablation_config.py:469` executes one config through the reusable API; `:514` creates a collision-safe isolated directory.
- The runner writes resolved config, manifest, predictions, metrics, latency, errors, and report, and records `case_limit` in the manifest.
- `tests/test_ablation_config.py` has seven passing tests for parsing, validation, paths, artifacts, collision refusal, and run IDs.

**Why this status:** The supported execution contract is present and tested. Unsupported MultiTool or unwired components return explicit statuses instead of false success. No official benchmark/index run exists.

**Detailed checklist:**

- [x] Named config loading and exact resolution.
- [x] Strict schema/type/backend/provider validation.
- [x] Required benchmark/corpus/index path validation.
- [x] Supported stack construction and explicit deferred behavior.
- [x] Isolated non-overwriting run directories.
- [x] Initial/final manifest and mandatory artifacts.
- [x] Case-limit and dry-run behavior.
- [?] Run a bounded named-config smoke against the frozen benchmark and compatible production index.

**Dependencies:** official benchmark, compatible index, selected provider/model variables, and quota.
**Acceptance criteria:** implementation criteria pass; production smoke remains open.
**Next action:** do not change the runner; execute a five-case production smoke only after identities and credentials are frozen.

### 2. Batch Ablation Runner

**Overall implementation status:** [x] Implementation Complete
**Validation status:** Offline tests pass; [?] production batch validation pending.

**Implementation evidence:**

- `scripts/run_ablation_batch.py:52` executes configs in requested order through Task 1.
- Independent statuses and continuation are implemented; batch directories are collision-safe at `:68`.
- Resume support reads prior completion state at `:72`; CLI `--resume` is defined at `:161`.
- `batch_summary.json` and Markdown reporting are written.
- `tests/test_ablation_batch.py` has three passing tests covering order, distinct runs, continuation, and resume.

**Why this status:** The batch orchestration contract is complete; it has not run against the team’s official config list and artifacts.

**Detailed checklist:**

- [x] Ordered execution through the single-run Python API.
- [x] One failure does not stop sibling configs.
- [x] Independent completed/failed/skipped/deferred/needs-rerun statuses.
- [x] Machine-readable and Markdown summaries.
- [x] Safe resume without overwriting completed runs.
- [?] Run the approved production batch.

**Dependencies:** the same frozen inputs as Task 1 plus an owner-approved run list.
**Acceptance criteria:** fixture behavior passes; production batch remains open.
**Next action:** wait for the validated run list and shared input identities.

### 3. E2E Evaluation, Metrics, Latency, and Fault Isolation

**Overall implementation status:** [x] Implementation Complete
**Validation status:** Offline tests pass; [?] frozen-benchmark metric and latency validation pending.

**Implementation evidence:**

- `src/evaluation/e2e_runner.py:19` defines Exact Match, Token F1, ROUGE-L, Unanswerable Accuracy, and Context Recall@k outputs.
- `src/evaluation/e2e_runner.py:20` defines stage-level latency; `:94` implements per-case execution and fault isolation.
- `src/evaluation/e2e_runner.py:254-280` retains failed/skipped counts, uses successful cases only for quality denominators, and groups by category, answer type, and difficulty.
- `src/evaluation/e2e_runner.py:286`, `:307`, `:319`, and `:621` write artifacts, aggregate latency/agent metrics, and sanitize diagnostics.
- Five current `tests/test_evaluate_e2e.py` tests and two metric tests pass.

**Why this status:** The required evaluation semantics are implemented and tested with deterministic fixtures. Fixture correctness is not evidence that official benchmark values or production latency are validated.

**Detailed checklist:**

- [x] Required answer and retrieval metrics.
- [x] Overall and three grouped breakdowns.
- [x] Null-preserving stage latency.
- [x] Per-case parsing/retrieval/generation/judge/serialization isolation.
- [x] Sanitized error records and continuation.
- [x] Explicit successful/failed/skipped denominator policy.
- [?] Validate metrics and latency on a frozen real sample.

**Dependencies:** official benchmark and compatible retrieval artifacts.
**Acceptance criteria:** offline contract passes; production metric review remains open.
**Next action:** prepare a small owner-reviewed frozen sample before any full benchmark.

### 4. E2E RAG Evaluation Notebook

**Overall implementation status:** [x] Implementation Complete
**Validation status:** JSON/structure and 17 offline tests pass; local clean-kernel was not rerun in this audit; [?] actual Kaggle inspect/smoke/full validation pending.

**Implementation evidence:**

- `notebooks/e2e_rag_eval.ipynb` is a valid Python 3 notebook with 29 cells, 14 code cells, zero retained outputs, and 14/14 null execution counts.
- Its editable Kaggle parameters precede Git clone/update; repository import-path setup precedes production imports.
- It supports `/kaggle/input`, `/kaggle/working`, Kaggle Secrets, runtime path overrides, inspect/smoke/full dispatch, the canonical runner, artifact loading, and safe export.
- `tests/test_e2e_rag_notebook.py` has 17 passing tests covering clone behavior, ordering, secrets, optional pandas/pyarrow, path overrides, run modes, and export safety.
- `docs/e2e_rag_eval.md` documents the copy-to-Kaggle workflow and validation boundaries.

**Why this status:** The notebook deliverable and offline contract exist. No actual Kaggle execution, Kaggle GPU run, production FAISS smoke, provider call, or full benchmark is evidenced.

**Detailed checklist:**

- [x] Valid, clean, clone-first Kaggle notebook.
- [x] Safe editable parameters and inspect default.
- [x] Repository clone/update before project imports.
- [x] Dataset mounts, Secrets, path overrides, and writable outputs.
- [x] Production preflight/runner/artifact APIs reused.
- [x] Run/case/context/metric/latency/trace/failure/reproducibility displays.
- [?] Execute a local clean-kernel rerun if the display ABI is repaired.
- [?] Execute Kaggle inspect mode.
- [?] Execute bounded Kaggle smoke with real inputs.
- [?] Execute full production run only after approval.

**Dependencies:** Kaggle Internet or a repository snapshot; attached benchmark/index datasets; provider variables for live modes.
**Acceptance criteria:** implementation and offline tests pass; Kaggle/live acceptance remains open.
**Next action:** perform a no-provider Kaggle inspect-mode check first.

### 5. Local UI Demo and UI Guide

**Overall implementation status:** [x] Implementation Complete
**Validation status:** 13 service tests and `ui.app` import pass; [?] browser and real-pipeline validation pending.

**Implementation evidence:**

- `ui/app.py` is the canonical Streamlit entry point and uses `src/service/qa_service.py` rather than a second RAG pipeline.
- `src/service/qa_service.py:162`, `:205`, `:313`, and `:325` implement bounded overrides, preflight, lazy resource construction, and one-question execution.
- The UI renders config controls, context ranks/scores/references, latency, bounded agent trace, diagnostics, blocked/deferred states, abstention, and safe errors.
- `tests/test_ui_service.py` has 13 passing tests for preflight, overrides, Plain RAG, Simple Planner, null preservation, failures, and trace limits.
- `docs/ui_demo.md` documents installation, launch, artifacts, controls, security, and troubleshooting.
- `python -c "import ui.app"` passed during this audit; no browser session was launched.

**Why this status:** Code, guide, and offline service behavior are complete. Import success is not browser interaction or a live answer.

**Detailed checklist:**

- [x] Canonical Streamlit entry point and reusable service.
- [x] Real config registry, bounded top-k/filter, and safe unsupported toggles.
- [x] Plain RAG and Simple Planner integration.
- [x] Context, score/rank, latency, trace, warning, and safe-error rendering.
- [x] Offline tests and guide.
- [?] Browser-test missing-dependency, answerable, unanswerable, and error states.
- [?] Verify the eventual recommended pipeline in the UI.

**Dependencies:** browser/manual test time; real index and credentials for live questions.
**Acceptance criteria:** implementation passes; manual browser and production pipeline checks remain open.
**Next action:** run the UI first with intentionally missing dependencies to verify blocked-state UX without quota.

### 6. Ablation Result Aggregation Script

**Overall implementation status:** [x] Implementation Complete
**Validation status:** 14 fixture tests pass; [B] real team aggregation pending.

**Implementation evidence:**

- `scripts/aggregate_ablation_results.py:187` discovers runs recursively.
- Compatibility selection and exclusion are implemented at `:568`, `:632`, and `:646`.
- Duplicate/collision checks are implemented at `:593`.
- `aggregate_ablation_results` at `:665` writes deterministic `ablation_summary.csv` and `ablation_report.md` while retaining failed/deferred/ineligible rows.
- `tests/test_aggregate_ablation_results.py` has 14 passing tests covering discovery, schema failures, null/zero handling, compatibility, duplicates, partial states, and CLI policy.

**Why this status:** The aggregator is complete for fixtures, but `evaluation_runs/ablation/` does not exist in this checkout, so no team run directory was aggregated.

**Detailed checklist:**

- [x] Run discovery and manifest/artifact validation.
- [x] Compatibility grouping and mismatch exclusion.
- [x] Failed/deferred visibility and optional metric preservation.
- [x] Duplicate/collision detection.
- [x] Deterministic CSV and Markdown outputs.
- [B] Aggregate the canonical team run directory.

**Dependencies:** validated owner run directories and shared benchmark/corpus/index identities.
**Acceptance criteria:** fixture behavior passes; real aggregation remains blocked.
**Next action:** request the exact canonical run directory or archived run bundle from each owner.

### 7. Ablation Report Notebook

**Overall implementation status:** [x] Implementation Complete
**Validation status:** Notebook structure passes; current report-test collection is blocked by the host pandas/pyarrow/NumPy ABI; [B] actual team aggregate analysis pending.

**Implementation evidence:**

- `notebooks/ablation_report.ipynb` is a valid Python 3 notebook with 29 cells, 14 code cells, zero retained outputs, and 14/14 null execution counts.
- `src/evaluation/ablation_analysis.py:226`, `:275`, `:306`, `:323`, `:342`, `:371`, and `:422` implement family classification/tables, Pareto analysis, diagnostics, mechanical observations, plots, and report-ready exports.
- `ablation_summary.csv` is the sole comparison source; the notebook does not re-read raw runs for comparison.
- `tests/test_ablation_report_notebook.py` covers schema, duplicates, nulls, families, eligibility, Pareto behavior, observations, exports, and collision safety.
- `docs/ablation_report.md` documents Kaggle use, output contracts, and the recommendation boundary.

**Why this status:** Task 7 code/docs/notebook exist. During this audit its test module failed at collection because pandas/pyarrow binaries were compiled for NumPy 1.x while the host has NumPy 2.5.1. That environment failure prevents a fresh pass claim. No canonical team `ablation_summary.csv` exists locally.

**Detailed checklist:**

- [x] Kaggle clone-first report notebook.
- [x] Aggregator CSV as sole comparison input and schema validation.
- [x] Family classification/tables and quality-latency plots.
- [x] Mechanical Pareto, failed/excluded/deferred, and coverage analysis.
- [x] Report-ready collision-safe exports and documentation.
- [?] Repair the local pandas ABI and rerun its test module.
- [?] Execute notebook in Kaggle.
- [B] Analyze the canonical team aggregate.

**Dependencies:** compatible pandas/NumPy environment for local tests; canonical `ablation_summary.csv` for real analysis.
**Acceptance criteria:** implementation/structure present; fresh fixture pass and real-data analysis remain open.
**Next action:** repair dependency declaration/environment, rerun Task 7 tests, then use team aggregate data when available.

### 8. LLM Ablation Runs

**Overall implementation status:** [x] Implementation Complete for configuration/execution support
**Validation status:** 11 LLM tests plus nine generation-client tests pass; structural dry-runs pass; [B] three comparable production runs pending.

**Implementation evidence:**

- `configs/ablation_configs.yaml:75`, `:125`, and `:175` define `LLM-BaseReasoning`, `LLM-CoTReasoning`, and `LLM-LargerModel`.
- `scripts/run_ablation_config.py:266` enforces controlled LLM comparison differences.
- `src/generation/prompt_strategy.py` defines deterministic Base/Reasoning prompts with a shared answer/citation contract and prompt hash.
- `src/generation/reasoning_client.py:143-192` strips provider reasoning fields and `<think>` content from serialized answers.
- Runner manifests persist model, prompt strategy/version/hash, decoding settings, and environment variable names—not secret values.
- All three configs returned `completed` structural dry-run status during this audit.

**Why this status:** The experiment definitions and safe execution infrastructure are implemented. “Runs” are not production-complete because no comparable official artifacts exist.

**Detailed checklist:**

- [x] Three named configs with one intended variable per comparison.
- [x] Base/CoT strategies and LargerModel-only model change.
- [x] Automated fairness validation and safe metadata.
- [x] Hidden-reasoning removal and offline tests.
- [x] Structural dry-runs.
- [B] Execute all three on the same official case set.

**Dependencies:** official benchmark, compatible index, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_BASE_MODEL`, `LLM_LARGER_MODEL`, model availability, and quota.
**Acceptance criteria:** implementation passes; three comparable completed production artifacts are still required.
**Next action:** obtain provider/model confirmation and run a same-limit smoke matrix before any full run.

### 9. Agent Ablation Runs

**Overall implementation status:** [-] Partially Implemented at major-task level
**Validation status:** Plain RAG and Simple Planner offline tests/dry-runs pass; [D] MultiTool deferred; [B] comparable production runs pending.

**Implementation evidence:**

- `configs/ablation_configs.yaml:227` and `:272` define implemented Plain RAG and Simple Planner configs; `:324` defines the deferred MultiTool contract.
- `src/agent/contracts.py`, `tools.py`, and `simple_planner.py` implement typed contracts, a read-only retrieval tool, bounded steps/tool calls/deadline, safe trace, and failure/abstention handling.
- `scripts/run_ablation_config.py:293` enforces that Plain RAG and Simple Planner differ only in the agent section.
- `src/evaluation/e2e_runner.py:319` derives agent metrics with explicit denominators.
- `tests/test_agent_ablation.py` has 13 passing cases after parametrization; both executable configs structurally dry-run as completed and MultiTool as deferred.

**Why this status:** Two required variants are implemented, but their real comparable runs do not exist. MultiTool is intentionally not implemented because only one approved typed tool exists.

**Detailed checklist:**

- [x] `Agent-None-PlainRAG` config and execution.
- [x] Typed retrieval tool and bounded deterministic Simple Planner.
- [x] Safe bounded trace, latency, agent metrics, fairness, aggregation, and tests.
- [B] Produce comparable Plain RAG/Simple Planner official artifacts.
- [D] MultiTool: wait for a second approved read-only tool and bounded orchestration acceptance contract.

**Dependencies:** same frozen benchmark/corpus/index/provider/model/case set for both executable variants; second approved tool/decision for MultiTool.
**Acceptance criteria:** offline implementation passes; two comparable production runs remain required; MultiTool remains evidence-backed deferred.
**Next action:** run Plain RAG and Simple Planner with identical frozen inputs when infrastructure is ready; do not implement MultiTool yet.

### 10. Final Summary, Report, and Main-Pipeline Recommendation

**Overall implementation status:** [ ] Not Started
**Validation status:** [B] Blocked by teammate experiment artifacts and real comparable results.

**Implementation evidence:**

- The aggregator and Task 7 notebook can prepare mechanical summaries, but `evaluation_runs/ablation/` and its `ablation_summary.csv`/`ablation_report.md` do not exist locally.
- No evidence-backed cross-family best pipeline or final UI verification exists.

**Why this status:** A final recommendation requires observed compatible results, owner interpretation, and UI verification. Templates and analysis code are not the final report.

**Detailed checklist:**

- [ ] Obtain validated retrieval, embedding, reranker, graph, LLM, and agent outputs.
- [ ] Confirm benchmark/corpus/index identities and approved run list.
- [ ] Generate canonical summary/report from actual runs.
- [ ] Review exclusions, failures, deferred work, quality, and latency with owners.
- [ ] Verify the selected candidate in the UI.
- [ ] Write the final recommendation with limitations and confidence.

**Dependencies:** teammate results, validated run list, identity review, owner interpretation, and UI verification.
**Acceptance criteria:** all required families are represented by compatible real results and the selected candidate works through the UI.
**Next action:** remain blocked; prepare only non-conclusive templates/checklists until artifacts arrive.

## Completed Work

- Tasks 1–8 implementation is present.
- The current non-Task-7 focused audit suite passed 94 tests.
- Both notebooks are structurally valid, Python 3, output-clean, and have null execution counts.
- Six LLM/agent config dry-runs resolved as intended; MultiTool returned deferred.
- `ui.app` imports successfully.
- Compile validation passed for `ui`, `scripts`, `src`, and `tests`.

## Partially Completed Work

- Task 9: Plain RAG and Simple Planner are implementation-complete; production comparison is absent and MultiTool is deferred.
- Validation, not implementation, remains incomplete for Tasks 1–8.

## Missing Work

- No production run directory or canonical aggregate/report artifacts exist locally.
- No three-run LLM result set exists.
- No comparable Plain RAG/Simple Planner production pair exists.
- No final evidence-backed Task 10 report/recommendation exists.

These are actual missing deliverables. Official data, credentials, and quota are blockers rather than “missing code.”

## Blocked Work

- **Teammate outputs:** retrieval, embedding, reranker, and graph result bundles; validated run list; owner interpretation review.
- **Data/artifacts:** frozen official benchmark, corpus identity, compatible FAISS/index identity, and canonical aggregate CSV.
- **Credentials/infrastructure:** provider URL, API key, exact model availability, quota, and attached Kaggle datasets.
- **Task 10:** blocked until the above results are compatible and reviewed.

## Deferred Work

- `Agent-MultiTool-Orchestrated` only. The current repository has one approved read-only typed tool; a second tool and bounded routing/loop acceptance contract are required.

## Risks

- The local pandas/pyarrow binaries are incompatible with NumPy 2.5.1, blocking a fresh Task 7 test run.
- No real run artifacts exist locally, so reports can only be fixture/mechanical until team data arrives.
- Production config paths still intentionally identify pending official benchmark/index inputs.
- Provider/model access and quota are unverified.
- Cross-family conclusions would be invalid if benchmark/corpus/index versions differ.
- UI import/offline tests do not establish browser usability or production correctness.

## Recommended Priority

1. Repair/declare a compatible analysis dependency environment and rerun Task 7 tests.
2. Perform Task 4 Kaggle inspect mode without provider spending.
3. Browser-test Task 5’s missing-dependency and blocked-state UX.
4. Request canonical owner run bundles and validate identities before aggregation.
5. Run bounded LLM/agent smoke comparisons only after inputs, credentials, model access, and quota are confirmed.
6. Keep Task 10 non-conclusive and MultiTool deferred until their blockers clear.

## Related Files

| Area | Canonical files |
| --- | --- |
| Single/batch execution | `scripts/run_ablation_config.py`, `scripts/run_ablation_batch.py`, `configs/ablation_configs.yaml` |
| E2E core | `src/evaluation/e2e_runner.py`, `metrics.py`, `retriever_factory.py`, `artifacts.py`, `export.py` |
| E2E notebook | `notebooks/e2e_rag_eval.ipynb`, `tests/test_e2e_rag_notebook.py`, `docs/e2e_rag_eval.md` |
| UI/service | `ui/app.py`, `src/service/qa_service.py`, `tests/test_ui_service.py`, `docs/ui_demo.md` |
| Aggregation | `scripts/aggregate_ablation_results.py`, `tests/test_aggregate_ablation_results.py` |
| Report notebook | `notebooks/ablation_report.ipynb`, `src/evaluation/ablation_analysis.py`, `tests/test_ablation_report_notebook.py`, `docs/ablation_report.md` |
| LLM | `src/generation/`, `tests/test_llm_ablation.py`, `docs/llm_ablation.md` |
| Agent | `src/agent/`, `tests/test_agent_ablation.py`, `docs/agent_ablation.md` |

## Build and Test Results

### Commands executed on 2026-08-01

| Command | Result |
| --- | --- |
| Requested 11-file focused suite, including `tests/test_ablation_report_notebook.py` | **Blocked during collection:** pandas/pyarrow binary built for NumPy 1.x cannot import with NumPy 2.5.1. Pytest reported 94 other items plus one collection error; no pass count is claimed for this command. |
| Same suite excluding only `tests/test_ablation_report_notebook.py` | **94 passed in 2.81s.** |
| `python -m compileall -q ui scripts src tests` | **Passed.** |
| `nbformat` validation of `notebooks/e2e_rag_eval.ipynb` | **Passed:** 29 cells, Python 3, zero outputs, 14/14 code execution counts null. |
| `nbformat` validation of `notebooks/ablation_report.ipynb` | **Passed:** 29 cells, Python 3, zero outputs, 14/14 code execution counts null. |
| Six `run_ablation_config.py --dry-run` commands | LLM Base/CoT/Larger, Agent None/Simple: **completed**; Agent MultiTool: **deferred** as designed. |
| `python -c "import ui.app"` | **Passed.** |

### Test interpretation

- Offline tests do not prove provider access, production retrieval, benchmark correctness, Kaggle execution, browser interaction, or official results.
- Task 7 implementation is present, but this audit does not claim its tests pass in the current host environment.
- No Ruff, mypy, Pyright, clean-kernel, live provider, GPU, production FAISS, bounded live smoke, or full benchmark result was executed in this audit.

## Validation Not Possible

- Actual Kaggle execution for either notebook.
- Browser interaction and real UI questions.
- Production FAISS/provider execution.
- Frozen-benchmark metric/latency review.
- LLM and agent live comparisons.
- Team aggregate analysis and final recommendation.

## Manual Verification

- Run the E2E notebook in Kaggle inspect mode with only repository access.
- Attach the benchmark/index datasets and check preflight without starting a provider call.
- Launch Streamlit and inspect blocked/missing-dependency behavior.
- After infrastructure approval, run identical five-case smoke sets for LLM and agent comparisons.
- Aggregate only compatible owner runs and have each owner review their family interpretation.
- Verify any final candidate in the UI before Task 10 completion.

## What My Should Do Next

### Can do now

- Repair or isolate the pandas/NumPy analysis environment and rerun `tests/test_ablation_report_notebook.py`.
- Run Task 4 in Kaggle inspect mode without model calls.
- Browser-test Task 5’s missing-dependency, deferred, and blocked states.
- Improve dependency metadata so evaluation, Kaggle, report, and UI requirements are explicit.
- Prepare non-conclusive Task 10 templates and an owner artifact intake checklist.

### Waiting for teammates

- Retrieval-family run directories and summary.
- Embedding-family run directories and summary.
- Reranker-family run directories and summary.
- Graph-family run directories and summary.
- Owner-approved run list and benchmark/corpus/index identity confirmation.
- Interpretation review for every family and approval of any final candidate.

### Waiting for infrastructure

- Frozen official benchmark and corpus.
- Compatible FAISS/index artifacts and manifests mounted as Kaggle Datasets.
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_BASE_MODEL`, and `LLM_LARGER_MODEL`.
- Confirmed provider/model availability and quota.
- Kaggle runtime/Internet access for actual notebook validation.

### Do not do yet

- Do not publish a final best-pipeline recommendation.
- Do not run full LLM/agent experiments without frozen compatible inputs.
- Do not compare runs across incompatible benchmark/corpus/index versions.
- Do not implement MultiTool without a second approved typed tool and bounded acceptance contract.
