# End-to-End LLM reasoning ablation tables

The full study-facing narrative is in [`report.md`](report.md). The tables
below are generated from the frozen artifacts using 10,000 paired-bootstrap
replicates (seed 42).

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

GPT-4o-mini is the pre-specified primary Base-versus-CoT pair. The refreshed
GLM-5 pair is complete but remains descriptive. DeepSeek has two CoT
directories (one partial and one quota-failed); the directory named
`qwen3-8b-CoT` is identified as DeepSeek by its manifest, so no Qwen3-8B
Base-versus-CoT result is inferred. Structural citation validity is not
citation entailment, and the saved records cannot support claim-level
faithfulness or semantic legal-correctness conclusions.
