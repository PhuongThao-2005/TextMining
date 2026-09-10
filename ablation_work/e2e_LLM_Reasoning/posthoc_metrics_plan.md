# Post-hoc Evaluation of LLM Reasoning Choices

## Scope and claim boundary

This plan uses **only files already present in this ablation directory**:
`e2e_predictions.jsonl`, `e2e_metrics.json`, `latency.json`, `errors.jsonl`,
and `manifest.json`. It requires no model call, rerun, new retrieval, or new
human/LLM annotation.

It can strengthen the ablation from a three-number comparison into a rigorous
analysis of observable LLM behavior: response quality conditional on available
evidence, refusal-versus-answer decisions, citation discipline, stability, and
latency. It cannot establish that a model's hidden chain of thought is more
faithful, or that citations semantically entail claims, because neither a
reasoning trace nor claim-level annotations were saved. This distinction is
important: plausible free-form CoT is not necessarily faithful reasoning.[^1]

The primary paired inference remains **GPT-4o-mini Base versus CoT** by
pre-specification. The GLM-5 and Qwen3-8B pairs are now complete and can be
reported as descriptive cross-model checks. DeepSeek remains descriptive because
its CoT cell has seven provider failures and four exact retrieved-context
sequence differences among shared successful cases.

| Pair | Base completed | CoT completed | Allowed interpretation |
| --- | ---: | ---: | --- |
| GPT-4o-mini | 500 / 500 | 500 / 500 | Primary paired prompt comparison |
| DeepSeek-V3.1-thinking | 500 / 500 | 493 / 500 | Descriptive; show seven CoT failures |
| GLM-5 | 500 / 500 | 500 / 500 | Descriptive only; primary inference remains GPT |
| Qwen3-8B | 500 / 500 | 500 / 500 | Descriptive only; Base/CoT runtime provenance differs |

## Metrics to calculate now

### 1. Paired answer-quality distribution

For each question ID shared by a Base/CoT pair, calculate
`CoT metric - Base metric` for exact match, Token F1, and ROUGE-L. Report:

- paired mean delta with a 95% paired-bootstrap confidence interval;
- count and percentage of **CoT win / tie / loss** per metric;
- a histogram or diverging bar chart of the per-question Token-F1 delta;
- the same values by `category`, `difficulty`, and `answer_type`.

This is more persuasive than two means: it tells readers whether CoT provides
broad small gains or helps a few questions while making many others worse.

For the complete GPT-4o-mini pair, the already saved predictions give:

| Answerable cases (n=400) | Base | CoT | CoT - Base |
| --- | ---: | ---: | ---: |
| Exact match | 14.00% | 13.75% | -0.25 pp |
| Token F1 | 24.72% | 23.15% | -1.57 pp |
| ROUGE-L | 21.60% | 19.90% | -1.71 pp |
| Token-F1 win / tie / loss | — | 79 / 164 / 157 | 19.8% / 41.0% / 39.2% |

These are descriptive values; add the paired confidence interval before making
a statistical-significance claim.

### 2. Evidence-availability stratification

Use the existing `context_recall@k` as a **stratification variable**, not a
metric that CoT is expected to improve. The retrieved context is fixed for the
matched conditions, so it asks a sharper LLM question: *when gold support was
or was not in the context, how did the prompt affect answer quality?*

Split the 400 answerable GPT-4o-mini cases into:

- **support fully present:** `context_recall@k = 1`;
- **support partly present:** `0 < context_recall@k < 1`;
- **support absent:** `context_recall@k = 0`.

| Existing evidence stratum | n | Base Token F1 | CoT Token F1 | CoT - Base | Base EM | CoT EM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gold support fully retrieved | 138 | 28.24% | 26.26% | -1.98 pp | 17.39% | 18.12% |
| Partial gold support retrieved | 29 | 25.62% | 23.76% | -1.86 pp | 10.34% | 6.90% |
| No gold support retrieved | 233 | 22.53% | 21.23% | -1.30 pp | 12.45% | 12.02% |

This is the closest available proxy for evidence use. It is not claim
faithfulness: the artifacts show whether gold chunks were retrieved, not
whether an individual generated claim was entailed by them. Reporting it
explicitly guards against overclaiming while still giving a meaningful
reasoning-relevant result.

### 3. Separate answerability behavior from answer quality

The saved `unanswerable_accuracy` is a deterministic **format-level decision
check**:

- for an unanswerable item, it is 1 when the output matches the system's
  insufficient-information/refusal detector;
- for an answerable item, it is 1 when the output does *not* match that
  detector.

It is therefore neither final-answer correctness nor a semantic assessment of
whether a refusal is helpful. Rename it in the report to **answerability
decision accuracy (template-based)** and present its two components:

| Decision metric | Denominator | GPT-4o-mini Base | GPT-4o-mini CoT |
| --- | ---: | ---: | ---: |
| Unanswerable recognition / refusal-template rate | 100 unanswerable | 98.0% | 98.0% |
| Answerable non-refusal rate | 400 answerable | 78.75% | 80.50% |
| False-refusal rate | 400 answerable | 21.25% (85) | 19.50% (78) |
| Overall template-based decision accuracy | all 500 | 82.60% | 84.00% |

This preserves the real behavioral insight: CoT did **not** improve detection
of the saved unanswerable set, but it reduced template-detected false refusals
by seven answerable cases. It avoids the incorrect statement that CoT raised
unanswerable refusal accuracy by 1.4 points.

The distinction follows the literature on unanswerable RAG evaluation: a good
system must distinguish direct answers from refusals/clarifications rather than
relying on one abstention score.[^2][^3]

### 4. Citation discipline, accurately named

The artifacts can report citation **structure**, not citation entailment. Use
only these names:

| Post-hoc metric | Definition | GPT-4o-mini Base | GPT-4o-mini CoT |
| --- | --- | ---: | ---: |
| Citation presence rate | Answerable outputs with at least one citation marker | 78.25% | 81.00% |
| Structural citation coverage | Mean share of detected factual sentences carrying a marker, among scored answers | 89.42% | 87.91% |
| Mean unique cited sources | Average source count per answerable output | 1.46 | 1.68 |
| Invalid marker rate | Markers that fail to map to a retrieved source | 0% in both saved runs | 0% in both saved runs |

The behavior is nuanced: CoT cited more often and cited more sources, but had
slightly lower structural coverage. Do not interpret either as better legal
grounding. ALCE and RAGChecker evaluate semantic claim--evidence support,
which cannot be recovered from these format-level fields alone.[^4][^5]

### 5. Reliability and efficiency

Add a reliability/cost block to every condition, including incomplete ones:

- completion, failure, and skipped counts from `e2e_metrics.json`;
- failure rate and failure stage from `errors.jsonl`;
- generation and total latency: median (p50) and p95, not mean only;
- citation-parser status/invalid marker count.

For the complete GPT-4o-mini pair, the latency files show:

| Latency | Base | CoT | CoT - Base |
| --- | ---: | ---: | ---: |
| Generation p50 | 2.92 s | 3.68 s | +0.76 s |
| Generation p95 | 5.74 s | 6.17 s | +0.44 s |
| Total p50 | 13.99 s | 14.75 s | +0.76 s |
| Total p95 | 17.21 s | 18.42 s | +1.21 s |

This makes the practical trade-off visible: in the complete GPT pair, CoT adds
latency while the saved lexical scores decline. It is not possible to attribute
the added time to hidden reasoning tokens because token accounting was not
recorded.

## Recommended report structure

Replace the current single overall table with the following four compact
displays. Every number already exists or is directly calculable from the saved
JSONL files.

1. **Primary paired comparison (GPT-4o-mini only):** completion, EM, Token F1,
   ROUGE-L, win/tie/loss, median/p95 generation latency, and median/p95 total
   latency.
2. **Evidence-availability table:** the three `context_recall@k` strata above,
   with EM/F1/ROUGE deltas. This is the headline analysis of whether prompt
   behavior changes when support is available.
3. **Answerability decision matrix:** answerable non-refusal, false refusal,
   unanswerable recognition, missed refusal, plus the overall template-based
   accuracy. Do not call the last item refusal accuracy.
4. **Citation and reliability appendix:** citation presence, structural
   coverage, unique sources, invalid markers, scheduled/completed/failed cases,
   and failure stages for every model/prompt condition.

Keep retrieval Recall/MRR/NDCG in an appendix or a small reproducibility row:
they are fixed inputs and should be identical for matched Base/CoT cases. They
help verify the control but cannot show that a reasoning prompt is better.

## Figures that require no new data

- **Paired Token-F1 slope chart:** one line per question from Base to CoT;
  facet by evidence-availability stratum. This exposes heterogeneous prompt
  effects better than a bar chart.
- **Win/tie/loss stacked bars:** by `category` and `difficulty`, using exact
  question-ID matches.
- **Refusal confusion matrix:** gold answerable/unanswerable versus the saved
  template-based answer/refusal decision for each GPT prompt.
- **Latency violin or ECDF:** generation and total latencies for the complete
  GPT pair, with p50/p95 labels.

No figure should be labeled “reasoning faithfulness,” “citation correctness,”
or “refusal quality”; the saved artifacts do not contain the evidence needed
for those claims.

## Appropriate conclusion from the existing evidence

The current work can support a bounded conclusion of this form:

> Under fixed retrieved context, GPT-4o-mini CoT changed observable output
> behavior: it reduced template-detected false refusals and increased citation
> presence, but its saved lexical answer-quality scores declined and its
> generation/total latency increased. Across all three existing
> evidence-availability strata, Token F1 was lower with CoT. These results
> characterize output behavior and cost; they do not demonstrate superior or
> inferior latent reasoning or semantic grounding.

That claim is more credible than a broad “CoT is worse/better” statement, and
it uses the current experiments without concealing their limits.

## Sources

[^1]: Lyu, Q. et al. (2023). *Faithful Chain-of-Thought Reasoning.* [arXiv:2301.13379](https://arxiv.org/abs/2301.13379).
[^2]: Peng, B. et al. (2025). *UAEval4RAG: Evaluating Unanswerable Questions in Retrieval-Augmented Generation.* [ACL Anthology](https://aclanthology.org/2025.acl-long.415/).
[^3]: Zhang, R. et al. (2024). *R-Tuning: Instructing Large Language Models to Say “I Don't Know”.* [ACL Anthology](https://aclanthology.org/2024.naacl-long.394/).
[^4]: Gao, T. et al. (2023). *Enabling Large Language Models to Generate Text with Citations.* [arXiv:2305.14627](https://arxiv.org/abs/2305.14627).
[^5]: Ru, D. et al. (2024). *RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation.* [arXiv:2408.08067](https://arxiv.org/abs/2408.08067).
