# Metrics Plan: Multi-Reranker Ablation

## Purpose

This plan defines the final evaluation protocol for the reranker-choice
ablation described in [current.md](current.md). It separates three questions
that the existing aggregate table partially conflates:

1. Is the required legal evidence available in the fixed candidate pool?
2. Does a reranker promote that evidence into the final generator context?
3. Does the generator produce a correct, supported, and safely abstaining
   answer from that context?

The protocol follows the fixed-candidate reranking pattern used by Qwen3 and
BGE, uses task-appropriate rank metrics in the spirit of Jina's evaluations,
and adopts claim-level RAG evaluation concepts from ARES and RAGChecker.

## Scope and controlled setup

All reranker comparisons must use the same:

- 500-question benchmark: 400 answerable and 100 unanswerable questions.
- Dense encoder, BM25 index, RRF configuration, candidate pool, generator
  model, prompt, final context size, maximum input length, GPU type, precision,
  and batch size.
- Per-question candidate list: RRF top-30 chunks (`C30`).
- Final context size: reranked top-10 chunks (`T10`).

`RRF-only` is the primary baseline for mMiniLM, Qwen3, BGE, and Jina because it
uses the same fusion stage and fixed candidate pool. `None` remains a separate
control for the RRF/fusion decision; it is not the primary reranker baseline.

## Final metric suite

### Main-paper metrics

| Evaluation layer | Metric | Population | Role |
| --- | --- | --- | --- |
| Candidate availability | Candidate Recall@30 | 400 answerable | Measures the evidence ceiling before reranking. |
| Ranking quality | nDCG@10 | 400 answerable | Primary reranker metric; rewards placing all relevant chunks early. |
| Evidence coverage | Recall@10 | 400 answerable | Measures gold-evidence coverage in the final context. |
| Early evidence | MRR@10 | 400 answerable | Measures how early the first supporting chunk appears. |
| Answer quality | Legal correctness (0–2) | 400 answerable | Measures whether the legal conclusion is correct. |
| Answer grounding | Claim faithfulness | 400 answerable | Measures whether answer claims are entailed by retrieved context. |
| Citation quality | Citation precision | Cited answers | Measures whether cited chunks support their linked claims. |
| Abstention safety | False-refusal rate | 400 answerable | Penalizes unnecessary refusals. |
| Abstention safety | False-answer rate | 100 unanswerable | Penalizes unsupported answers when abstention is required. |
| Deployment cost | Full-online p50 and p95 total latency | 500 total | Measures typical and tail end-to-end latency. |

### Diagnostic and appendix metrics

| Metric | Population | Purpose |
| --- | --- | --- |
| Candidate Hit@30 | 400 answerable | Share of queries with at least one gold chunk available to rerank. |
| Gold retention@10 | Candidate-hit queries only | Isolates reranker retention of gold chunks available in `C30`. |
| Candidate-hit preservation@10 | Candidate-hit queries only | Share of candidate-hit queries that retain at least one gold chunk in `T10`. |
| Hit@1 | 400 answerable | First-result success rate, useful for user-facing retrieval and examples. |
| Answer completeness (0–2) | 400 answerable | Measures coverage of material legal requirements. |
| Citation recall | Answers with verifiable claims | Measures whether claims that need evidence have support citations. |
| Abstain precision, recall, F1 | 500 total | Gives the full answerability confusion-matrix view. |
| Reranker-stage p50 and p95 latency | 500 total | Localizes latency regressions to the reranker. |
| GPU peak memory and throughput | Deployment run | Supports deployment trade-off claims. |
| Token F1, ROUGE-L, exact match | Answerable questions | Reproducible lexical diagnostics only; not decision metrics. |

## Metric definitions

For a question `q`, let `Gq` be the set of annotated gold chunk IDs, `C30q`
the fixed RRF top-30 candidate set, and `T10q` the final top-10 ranked list.

| Metric | Definition |
| --- | --- |
| Candidate Recall@30 | `mean_q(|Gq ∩ C30q| / |Gq|)` |
| Candidate Hit@30 | `mean_q(1[Gq ∩ C30q is not empty])` |
| Recall@10 | `mean_q(|Gq ∩ T10q| / |Gq|)` |
| MRR@10 | Mean reciprocal rank of the first gold chunk in `T10`; zero when none occurs. |
| nDCG@10 | Binary-relevance nDCG over `T10`; use graded labels only if the benchmark later supplies them. |
| Gold retention@10 | For `Gq ∩ C30q` nonempty: `mean_q(|Gq ∩ T10q| / |Gq ∩ C30q|)` |
| Candidate-hit preservation@10 | For `Gq ∩ C30q` nonempty: `mean_q(1[Gq ∩ T10q is not empty])` |
| Claim faithfulness | `supported answer claims / all answer claims` |
| Citation precision | `citations supporting their linked claim / all citations` |
| Citation recall | `verifiable answer claims with a supporting citation / all verifiable answer claims` |
| False-refusal rate | `answerable questions incorrectly classified as unanswerable / 400` |
| False-answer rate | `unanswerable questions incorrectly answered / 100` |

All retrieval metrics exclude unanswerable questions. All answerability metrics
use the full 500-question set.

## Answer-quality annotation rubric

Evaluate answers blind to configuration and randomized across systems. Preserve
the question, reference answer, retrieved chunks, generated answer, and each
answer citation's mapped chunk ID.

### Per-answer labels

| Dimension | Score | Annotation rule |
| --- | --- | --- |
| Legal correctness | 0–2 | `0`: materially wrong or contradictory; `1`: partly correct; `2`: legally correct under the benchmark reference. |
| Completeness | 0–2 | `0`: omits material conditions, exceptions, or required steps; `1`: partly complete; `2`: covers all material requirements. |
| Claim faithfulness | Fraction | Decompose the response into atomic claims; score the fraction entailed by retrieved context. |
| Citation precision | Fraction | Score each answer citation against the claim it is attached to. |
| Citation recall | Fraction | Score whether each verifiable claim has at least one supporting citation. |

Run an automatic claim-level judge over all answerable cases. Validate it against
a blinded, stratified human legal annotation sample before using its score as a
headline result. Report human agreement and judge-versus-human agreement.

## Statistical protocol

For each reranker (`mMiniLM`, `Qwen3`, `BGE`, `Jina`) versus `RRF-only`:

1. Pair records by `qa_id`.
2. Calculate the per-question delta for each metric.
3. Use paired bootstrap resampling over questions, with 10,000 or more
   replicates and a recorded random seed, to calculate a 95% confidence
   interval.
4. Report candidate-minus-baseline delta, 95% CI, and win/tie/loss counts.

Apply the protocol to Recall@10, MRR@10, nDCG@10, legal correctness, claim
faithfulness, and false-refusal rate. State explicitly that the interval
measures benchmark-sampling uncertainty, not run-to-run generator randomness.

For stochastic generation, either use deterministic decoding or repeat each
configuration with multiple fixed seeds and report the across-run mean and
variation.

## Slice reporting

Report counts and confidence intervals for:

- Citation questions
- Legal-validity questions
- Single-hop questions
- Multi-hop questions
- Extractive, abstractive, and boolean answer types

Treat any slice with fewer than 30 questions as exploratory. In the current
benchmark, do not draw comparative conclusions from `hard` (`n=1`) or
`cross_document` (`n=12`) results. Expand these slices before promoting them to
main-report evidence.

## Efficiency protocol

Latency runs must record per-query:

- Dense retrieval, online BM25 retrieval, fusion, reranking, generation, and
  total latency.
- p50 and p95 stage and total latency.
- GPU model, precision, batch size, candidate count, reranker maximum input
  length, peak GPU memory, and throughput.

Do not present cached BM25 timing as full-online latency. Where feasible, add a
candidate-pool sweep (`top-10`, `top-30`, `top-50`, and `top-100`) to expose
quality-versus-cost curves and to test whether conclusions depend on the
current `top_k=30` choice.

## Required report outputs

### Table 1: Candidate-controlled retrieval

| Model | Candidate Recall@30 | Candidate Hit@30 | Gold retention@10 | nDCG@10 | Recall@10 | MRR@10 | Hit@1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

### Table 2: Paired effects versus RRF-only

| Reranker | Delta nDCG@10 (95% CI) | Delta Recall@10 (95% CI) | Delta MRR@10 (95% CI) | Win / tie / loss |
| --- | ---: | ---: | ---: | ---: |

### Table 3: Grounded legal-answer quality and safety

| Model | Legal correctness | Completeness | Claim faithfulness | Citation precision | Citation recall | False-refusal rate | False-answer rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

### Table 4: Full-online deployment trade-off

| Model | Reranker p50 / p95 | Total p50 / p95 | Throughput | Peak GPU memory |
| --- | ---: | ---: | ---: | ---: |

Include two figures:

1. A paired-effect forest plot for nDCG@10, Recall@10, MRR@10, and legal
   correctness.
2. A Pareto plot of nDCG@10 against p50 total online latency, annotated by
   claim faithfulness.

## Interpretation rules

- Do not select a default model from a single composite score. Present the
  quality, grounding, safety, and latency trade-off explicitly.
- A retrieval improvement is credible only when its paired CI is reported.
- A legal-answer improvement is credible only when correctness and faithfulness
  agree; lexical overlap alone is insufficient.
- A safety improvement is credible only when false-answer and false-refusal
  rates are both shown.
- Conclusions are limited to this Vietnamese legal benchmark, index, prompt,
  candidate-pool size, and deployment hardware.

## References

- Zhang et al. (2025), [Qwen3 Embedding: Advancing Text Embedding and
  Reranking Through Foundation Models](https://arxiv.org/abs/2506.05176).
- BAAI, [Evaluate Reranker](https://bge-model.com/tutorial/5_Reranking/5.3.html).
- Jina AI, [jina-reranker-v2-base-multilingual model
  evaluation](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual).
- Bonifacio et al. (2021), [mMARCO: A Multilingual Version of MS MARCO Passage
  Ranking Dataset](https://arxiv.org/abs/2108.13897).
- Thakur et al. (2021), [BEIR](https://arxiv.org/abs/2104.08663).
- Muennighoff et al. (2022), [MTEB](https://arxiv.org/abs/2210.07316).
- Saad-Falcon et al. (2023), [ARES](https://arxiv.org/abs/2311.09476).
- Ru et al. (2024), [RAGChecker](https://arxiv.org/abs/2408.08067).
