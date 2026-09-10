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

The refreshed artifacts complete the GLM-5 Base/CoT pair and the Qwen3-8B Base
run. The directory `qwen3-8b-CoT` is not a Qwen run according to its manifest:
it declares `deepseek-v3.1-thinking`, with 334/500 successful cases. The
current source therefore contains two incomplete/partial DeepSeek CoT
directories and no manifest-backed Qwen3-8B CoT run. This mismatch is flagged
in [`results/report.md`](results/report.md), and those rows remain descriptive.

The complete GLM pair is also descriptive: CoT minus Base is -0.68 pp Token
F1, -0.63 pp ROUGE-L, -0.25 pp exact match, and +1.60 pp template decision
accuracy; total-latency p50 rises from 14.29 s to 15.96 s. The derived results
were regenerated from the frozen artifacts with 10,000 paired-bootstrap
replicates (seed 42). Semantic legal correctness, claim faithfulness, citation
entailment, and faithful latent reasoning are not recoverable from the saved
outputs.
