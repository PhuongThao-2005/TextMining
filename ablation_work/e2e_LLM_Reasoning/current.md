# Current Status: End-to-End LLM Reasoning Ablation

## Snapshot

The current run evaluates whether a reasoning/CoT prompt improves end-to-end
legal RAG answers. It uses the same 500-question benchmark in every run (400
answerable and 100 unanswerable), with a fixed retrieval stack: top-10
multilingual-E5 dense retrieval, graph expansion + RRF fusion, and mMiniLM
cross-encoder reranking. Generation uses temperature 0 and a 1,024-token cap.

Eight run directories are present, with artifacts recorded from 2026-09-02 to
2026-09-10. The refreshed files complete the GLM-5 Base/CoT pair and the
Qwen3-8B Base run. They also contain a provenance mismatch: the directory
`qwen3-8b-CoT` has a manifest and resolved config for
`deepseek-v3.1-thinking` (334/500 successful), so the current snapshot has two
DeepSeek CoT directories and no manifest-backed Qwen3-8B CoT run. The analysis
uses manifest metadata and reports this ambiguity instead of relabeling it.

## Results

Answer metrics are calculated over the applicable answerable cases. The
`unanswerable_accuracy` column is relabeled in the post-hoc report as
template-based answerability decision accuracy; it is not semantic refusal
quality. Latency is mean end-to-end time per input, including failed inputs
where recorded.

| Model | Prompt | Run directory | Evaluated / 500 | Failures | Exact match | Token F1 | ROUGE-L | Decision accuracy (template) | Mean latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-4o-mini | Base | `4o-mini-base` | 500 | 0 | 0.1400 | **0.2472** | **0.2160** | 0.826 | **14.19 s** |
| GPT-4o-mini | CoT | `4o-mini-CoT` | 500 | 0 | 0.1375 | 0.2315 | 0.1990 | 0.840 | 15.09 s |
| DeepSeek-V3.1-Thinking | Base | `deepseekv3.1-thinking-basereasoning` | 500 | 0 | **0.2225** | 0.1784 | 0.1528 | 0.920 | 17.00 s |
| DeepSeek-V3.1-Thinking | CoT* | `deepseekv3.1-thinking-CoT` | 493 | 7 | 0.2239 | 0.1650 | 0.1415 | 0.923 | 20.20 s |
| DeepSeek-V3.1-Thinking | CoT* | `qwen3-8b-CoT` | 334 | 166 | 0.2157 | 0.1762 | 0.1514 | 0.904 | 23.28 s |
| GLM-5 | Base | `glm5-base` | 500 | 0 | 0.2525 | 0.1691 | 0.1490 | 0.918 | 14.82 s |
| GLM-5 | CoT | `glm5-CoT` | 500 | 0 | 0.2500 | 0.1623 | 0.1427 | 0.934 | 16.51 s |
| Qwen3-8B | Base | `qwen3-8b-base` | 500 | 0 | 0.1925 | 0.2198 | 0.1892 | **0.958** | 14.77 s |

\* Incomplete run: do not use for model ranking or paired Base-vs-CoT claims.

## Current Readout

- **GPT-4o-mini remains the pre-specified primary paired prompt comparison.**
  CoT did not change recognition of the saved unanswerable set (98.00% for both), but
  reduced template-detected false refusals from 21.25% to 19.50%. Overall
  template-based decision accuracy moved from 82.60% to 84.00%; Token F1 fell
  by 1.57 points, ROUGE-L by 1.71 points, and mean latency increased by
  0.90 s/query. This does not demonstrate an overall answer-quality gain.
- Among the currently complete runs, **GPT-4o-mini Base** has the strongest
  Token F1 and ROUGE-L, while **GLM-5 Base** has the strongest exact match.
  These are descriptive cross-model observations, not a statistical
  significance result. The complete GLM pair is also descriptive because the
  study's primary inference remains the pre-specified GPT pair.
- The refreshed GLM pair has a descriptive CoT-minus-Base change of -0.68 pp
  Token F1, -0.63 pp ROUGE-L, -0.25 pp exact match, and +1.60 pp template
  decision accuracy. Its total latency p50 rises from 14.29 s to 15.96 s.
- Before making any Qwen CoT claim, move or restore the Qwen3-8B CoT artifacts
  so that their manifest identifies `qwen3-8b`. The current `qwen3-8b-CoT`
  directory is retained as a second, incomplete DeepSeek CoT run.

## Source Artifacts

- Per-run reports: `*/report.md`
- Metrics and latency: `*/e2e_metrics.json`, `*/latency.json`
- Completion and configuration records: `*/manifest.json`
- Failed-call records: `*/errors.jsonl`

## Implemented Post-hoc Analysis

Run `python3 analyze_posthoc.py` to regenerate the no-rerun analysis. It writes
the paired bootstrap deltas, evidence-availability strata, answerability
matrices, structural citation diagnostics, reliability tables, and SVG figures
under [`posthoc_results/`](posthoc_results/). The generated narrative is
[`posthoc_report.md`](posthoc_results/posthoc_report.md); semantic claim
faithfulness and citation entailment remain unavailable from these artifacts.

The manifests use the same benchmark, retrieval configuration, and decoding
settings described above. The original runs identify Git commit
`32a3b70a5a8b06de0329812238e936ae138b4ca8`; the refreshed GLM/Qwen-directory
artifacts identify `bce815dac051401f920934228a365d0f318694d6`.
