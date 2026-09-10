# Current Status: End-to-End LLM Reasoning Ablation

The study-facing record is available in
[`results/report.md`](results/report.md), with compact table links in
[`results/tables.md`](results/tables.md).
The result is also wired into the formal manuscript at
[`docs/report/ablation_report.pdf`](../../../docs/report/ablation_report.pdf).

The primary complete comparison is GPT-4o-mini Base versus CoT on the same
500-question benchmark. CoT reduced Token F1 by 1.57 percentage points and
ROUGE-L by 1.71 points, increased mean latency by 0.90 seconds/query, and did
not change recognition of the saved unanswerable set (98.00% for both). It
reduced template-detected false refusals from 21.25% to 19.50%; this is a
format-level decision diagnostic, not semantic refusal quality.

The refreshed artifacts now complete the DeepSeek-V3.1-Thinking, GLM-5, and
Qwen3-8B Base/CoT pairs. DeepSeek Base is recorded under the normalized
`deepseekv3.1-thinking-base` directory, and its repaired CoT run evaluates all
500 questions. The Qwen Base/CoT pair is complete, but its manifests use
different code snapshots, timeout values, and retry limits, so its latency and
failure behavior remain descriptive.

DeepSeek CoT is 22.25% exact match, 16.51% Token F1, 14.12% ROUGE-L, and
92.20% template-based decision accuracy. Its Base/CoT retrieved top-10
chunk-ID sequences differ in four of 500 shared cases, so that comparison
remains descriptive.

## Evaluation and metric calculation

Each run contains 500 fixed question IDs and a saved top-10 retrieved context.
The analyzer pairs Base and CoT by `qa_id`; lexical metrics use the successful
answerable intersection (400 cases for every complete pair). Exact Match,
Token F1, and ROUGE-L are read from the original evaluator. Paired deltas are
`CoT - Base`, with 10,000 paired-bootstrap resamples (seed 42); Exact Match
also uses an exact McNemar test.

Additional diagnostics use the saved fields: `context_recall@k` measures the
fraction of gold chunk IDs present in the retrieved top-k and defines fully
retrieved/partial/absent evidence strata; the template-based answerability
score counts answer/refuse decisions; citation presence, structural coverage,
unique sources, and invalid markers describe citation formatting; completion,
failure stage, and latency p50/p95 describe operational reliability. None of
these structural metrics establishes legal correctness, citation entailment, or
faithful hidden reasoning.

The complete GLM pair is also descriptive: CoT minus Base is -0.68 pp Token
F1, -0.63 pp ROUGE-L, -0.25 pp exact match, and +1.60 pp template decision
accuracy; total-latency p50 rises from 14.29 s to 15.96 s. The complete Qwen
pair has a descriptive CoT-minus-Base change of -1.92 pp Token F1, -1.75 pp
ROUGE-L, -2.00 pp exact match, and -0.60 pp template decision accuracy; total
latency p50 rises from 14.15 s to 14.58 s. The derived results were regenerated
from the frozen artifacts with 10,000 paired-bootstrap replicates (seed 42).
Semantic legal correctness, claim faithfulness, citation entailment, and
faithful latent reasoning are not recoverable from the saved outputs.
