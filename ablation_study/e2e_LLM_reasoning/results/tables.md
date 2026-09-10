# End-to-End LLM reasoning ablation tables

The full study-facing narrative is in [`report.md`](report.md). The tables
below are generated from the frozen artifacts using 10,000 paired-bootstrap
replicates (seed 42).

The narrative report explains the evaluation workflow, row-validity rule,
denominators, pairing, and formulas for each additional metric.

## Main derived tables

- [Primary and descriptive Base/CoT deltas](paired_metrics.csv)
- [Category, difficulty, and answer-type slices](paired_group_deltas.csv)
- [Evidence-availability strata](evidence_strata.csv)
- [Answerability decisions and confusion counts](answerability_decisions.csv)
- [Structural citation diagnostics](citation_metrics.csv)
- [Completion, failures, and latency](run_reliability.csv)
- [Per-question paired deltas](paired_case_deltas.csv)

## Figures

- [Paired Token-F1 delta histogram](paired_token_f1_delta.svg)
- [Win/tie/loss slice bars](win_tie_loss.svg)
- [Base and CoT decision matrices](refusal_confusion.svg)

## Claim boundary

GPT-4o-mini is the pre-specified primary Base-versus-CoT pair. The DeepSeek,
GLM-5, and Qwen3-8B pairs are complete but remain descriptive. DeepSeek
Base/CoT retrieved top-10 chunk-ID sequences differ in four of 500 shared
cases. The Qwen Base/CoT manifests also use different code snapshots, timeouts,
and retry limits, so its latency and failure behavior are descriptive.
Structural citation validity is not citation entailment, and the saved records
cannot support claim-level faithfulness or semantic legal-correctness
conclusions.
