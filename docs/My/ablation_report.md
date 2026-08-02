# Ablation report notebook

`notebooks/ablation_report.ipynb` is the Kaggle-first, aggregate-only analysis
surface for Task 7. It reads the canonical output of
`scripts/aggregate_ablation_results.py`; it does not run retrieval, generation,
agent, or judge inference.

## Kaggle workflow

Copy only the notebook to Kaggle, open its editable configuration cell, replace
the repository URL and branch, and run from the first cell. The notebook detects
the Kaggle filesystem, clones or safely fast-forwards the checkout, validates the
checkout, adds its root and `src` directory to the import path, and installs only
missing analysis dependencies. It reports the checked-out branch and commit.

The notebook supports three aggregate input modes:

1. Set `SUMMARY_CSV_SOURCE` and optionally `REPORT_MD_SOURCE` to attached files.
2. Attach a Kaggle Dataset containing `ablation_summary.csv`; automatic discovery
   searches `/kaggle/input`, `/kaggle/working`, then the checkout deterministically.
3. Set `RUN_AGGREGATOR=True` and `RUNS_SOURCE_DIR` to call the canonical Python
   aggregation API. Its output is written below `/kaggle/working`; input datasets
   are never modified.

If no summary CSV is found, execution stops with instructions for attaching an
aggregate Dataset or enabling the canonical aggregator. The default does not
create or modify runs and does not require a GPU or provider credentials.

## Source-of-truth and validation

`ablation_summary.csv` is the sole comparison-table source. Individual run
metrics are never read or reaggregated. The optional canonical Markdown report
is supplementary diagnostic context only. Eligibility, exclusion reasons, and
benchmark/corpus compatibility remain exactly as persisted by the aggregator.

Validation reports missing required columns, invalid boolean and numeric cells,
duplicate run IDs, duplicate rows, multiple compatibility groups, and the absence
of eligible rows. Numeric blanks remain null and malformed values become flagged
nulls, never zero. Rows are retained for diagnostics rather than silently dropped.

## Family classification and coverage

Family classification prefers explicit aggregate/config metadata, then config
metadata or tags, exact documented configuration names, and finally controlled
name prefixes. Anything else remains `unclassified`. The supported families are
retrieval, embedding, reranker, graph, LLM, and agent.

Coverage displays row and status totals, compatibility-group count, available
and expected named configs, missing configs, and eligible completed rows by
family. A deferred MultiTool row stays deferred and never counts as completed.

Family tables use only persisted columns. Optional unavailable fields are shown
as `N/A` for display while exports preserve nulls. The LLM and agent tables add
absolute display-only deltas only when their documented baselines,
`LLM-BaseReasoning` and `Agent-None-PlainRAG`, are present. Baselines are never
guessed from row order, and deltas do not alter source metrics or eligibility.

## Quality, latency, and Pareto interpretation

Plots are created with matplotlib only when at least two eligible completed,
compatible rows have both selected metrics. They include primary quality versus
average and median total latency, retrieval quality versus retrieval latency,
LLM quality versus generation latency, and agent quality versus agent latency
when the needed persisted columns exist. Excluded and deferred runs are displayed
separately and do not enter the primary plots.

The mechanical Pareto frontier includes only aggregator-eligible completed rows
with complete benchmark/corpus metadata and non-null selected metrics. A row is
dominated when another row has at least as much quality and no more latency, with
one strict improvement. Ties are preserved and ordering is deterministic. Pareto
candidates are not a final pipeline recommendation and do not establish causality
or statistical superiority.

Failed, skipped, deferred, needs-rerun/partial, invalid, duplicate, missing-metric,
and benchmark/corpus-excluded rows remain visible in diagnostic tables and
exports.

## Outputs

The notebook creates a collision-safe directory based on
`/kaggle/working/ablation_report_outputs` containing:

- `coverage_summary.csv`
- retrieval, embedding, reranker, graph, LLM, and agent table CSVs
- `pareto_candidates.csv`
- `excluded_runs.csv`
- `failed_deferred_runs.csv`
- `mechanical_observations.md`
- `analysis_manifest.json`
- only those PNG plots supported by sufficient valid data
- optionally, a ZIP adjacent to the output directory

Empty family CSVs retain an explicit schema. The manifest records the source
artifact name, repository commit, UTC generation time, selected metrics, and
filters; it does not copy benchmark data, indexes, caches, credentials, or secret
environment values. Existing output directories are not overwritten.

## Recommendation boundary and validation levels

A final main-pipeline recommendation cannot be finalized until all required
experiment families have valid comparable runs and the selected candidate is
verified in the UI.

These validation states are distinct:

- **Notebook structurally validated:** JSON, cell order, clean outputs, and safety
  constraints pass local tests.
- **Fixture analysis validated:** deterministic helper behavior and exports pass
  with synthetic temporary CSVs.
- **Actual team aggregate analyzed:** the notebook has run against the team's
  canonical aggregate CSV. Task 7 implementation does not imply this occurred.
- **Final recommendation completed:** Task 10 interpretation, team-owner review,
  and UI verification are complete. This notebook intentionally does not claim it.
