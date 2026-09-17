# Presentation Notes

These notes explain the metrics and experimental protocol used in the slide
deck. They are written for quick presentation use, so every formula has a
small example.

## 1. Metrics

### Common reading rules

- The benchmark has **500 scheduled questions**: 400 answerable and 100
  unanswerable.
- Retrieval and lexical answer metrics use the 400 answerable questions.
  Decision accuracy uses all 500 unless the slide says “valid”.
- A row is valid when it is not failed, errored, or skipped and contains a
  prediction. Lexical metrics use successful answerable rows.
- Text is normalized before comparison: Unicode normalization, lowercasing,
  punctuation-to-space replacement, and whitespace collapse.
- A delta in percentage points (pp) is an absolute difference: 60% - 55% =
  **+5 pp**, not +9.1% relative growth.

### Why use these metrics?

| Metric | Why we use it | What it tells us / limitation |
|---|---|---|
| Exact Match (EM) | Gives a strict, easy-to-read success signal. | Exact agreement; it is brittle to valid synonyms or different wording. |
| Token F1 | Gives partial credit for shared words. | Balances answer precision and coverage; it does not verify meaning. |
| ROUGE-L | Rewards overlap in the same sequence order. | Captures phrase-level similarity better than unordered overlap; still not legal correctness. |
| Paired delta | Measures the change caused by a configuration on the same questions. | Reduces question-difficulty noise; only shared valid IDs are included. |
| Recall@k / Context Recall@k | Checks whether the system retrieved the annotated evidence. | Measures evidence coverage, not whether the answer used it correctly. |
| Hit@k | Checks whether at least one supporting chunk was found. | Simple discoverability signal; it can hide partial evidence coverage. |
| MRR@k | Rewards placing the first supporting chunk early. | Measures the rank of the first useful item; ignores later supporting items. |
| nDCG@k | Rewards multiple relevant chunks and discounts lower ranks. | Gives a fuller view of ranked evidence quality than Hit or MRR alone. |
| Precision@k | Penalizes irrelevant chunks in the returned context. | Shows context purity; it can fall when the system intentionally returns more evidence. |
| Document success@k | Separates finding the correct legal document from finding an exact chunk. | Detects document-level benefit even when chunk-level recall is unchanged. |
| Document-identity precision | Measures how much returned context belongs to the right document. | Useful for graph variants with variable context size; not exact provision correctness. |
| Candidate Recall/Hit@30 | Measures the evidence available before reranking. | Establishes the candidate ceiling and separates retrieval failure from ranking failure. |
| Decision accuracy | Tests answer-versus-refuse behavior on all 500 questions. | Includes both answerable and unanswerable cases; it is not a legal-safety score. |
| Abstain precision/recall/F1 | Separates refusal quality into correctness, coverage, and one summary score. | Shows whether refusals are appropriate and whether unanswerable cases are caught. |
| Citation presence | Checks whether successful answers visibly cite a source. | Measures citation compliance, not citation validity or entailment. |
| Structural coverage | Checks whether citations cover factual sentences, not just one sentence. | Reveals incomplete citation structure. |
| Invalid-marker rate | Checks whether citation markers follow the expected format. | Measures output reliability; a valid marker can still cite the wrong source. |
| Completion rate | Measures whether the system finishes scheduled cases. | Captures failures and skipped rows that quality scores may omit. |
| Mean / p50 / p95 latency | Reports average cost, typical user experience, and slow-tail behavior. | Prevents a quality gain from being judged without its deployment cost. |
| Human legal labels | Supply the judgments automatic metrics cannot provide. | Needed for legal correctness, completeness, faithfulness, and citation entailment. |

The metrics are used together because the study asks several different
questions: **Can the system find evidence? Can it rank the evidence? Does the
answer resemble the reference? Does it answer or abstain appropriately? Are
citations present and structurally complete? Does the system finish within a
reasonable cost?** A single score would hide these trade-offs.

### Primary answer metrics

#### Exact Match (EM)

EM is 1 when the normalized prediction exactly equals the normalized
reference, otherwise 0:

```text
EM_i = 1[y_i = r_i]
EM   = average(EM_i)
```

Example: reference “Valid for 12 months.” and prediction “valid for 12
months” receive EM = 1 after normalization. “Valid for one year” receives
EM = 0, even though the meaning may be similar.

#### Token F1

Token F1 measures word overlap while balancing precision and recall:

```text
P  = overlap / predicted_tokens
R  = overlap / reference_tokens
F1 = 2PR / (P + R)
```

Example: reference has 5 tokens and the prediction has 4, with 4 overlapping
tokens. Then P = 4/4 = 1.00, R = 4/5 = 0.80, and F1 = 0.89. Repeated words
are counted as a multiset, so one copy cannot match two copies.

#### ROUGE-L

ROUGE-L uses the same F-score calculation, but overlap is the length of the
longest common subsequence (LCS), so word order matters.

Example:

```text
Reference:  A B C D
Prediction: A C B D
```

All four tokens overlap, so Token F1 = 1.00. The LCS has length 3, so
ROUGE-L precision = recall = 3/4 and ROUGE-L = 0.75.

#### Paired delta

For the same question ID, compare two configurations directly:

```text
Delta_i(m) = m_treatment,i - m_baseline,i
Mean delta = average(Delta_i)
```

Example: Base F1 = 0.50 and CoT F1 = 0.60 gives a per-question delta of
+0.10, or **+10 pp**. The reported mean is calculated only over IDs with
valid outputs in both runs. Positive, zero, and negative deltas are wins,
ties, and losses.

### Retrieval and evidence metrics

Let `G` be the gold chunk-ID set and `R_k` the top-k retrieved chunks.

#### Recall@k / Context Recall@k

```text
Recall@k = |G ∩ R_k| / |G|
```

Example: gold chunks are `{A, B, C}` and the top-5 result contains `{A, C}`.
Recall@5 = 2/3 = 0.67. It measures how much of the annotated evidence was
retrieved.

#### Hit@k

Hit@k asks only whether at least one gold chunk appears in the top k:

```text
Hit@k = 1 if G ∩ R_k is non-empty, otherwise 0
```

The previous example has Hit@5 = 1, even though Recall@5 is only 0.67.

#### MRR@k

Mean Reciprocal Rank rewards the position of the first gold chunk:

```text
RR_i = 1 / rank(first gold chunk)
MRR@k = average(RR_i), or 0 when no gold chunk appears in top k
```

If the first gold chunk is ranked 3rd, its reciprocal rank is 1/3. A gold
chunk at rank 1 is better than the same evidence at rank 8.

#### nDCG@k

nDCG rewards relevant chunks near the top using a logarithmic rank discount,
then divides by the ideal ranking:

```text
DCG@k      = sum((2^relevance_j - 1) / log2(j + 1))
nDCG@k     = DCG@k / ideal_DCG@k
```

For binary relevance, placing gold chunks at ranks 1 and 2 scores higher than
placing them at ranks 8 and 9. nDCG is normalized to make queries with
different numbers of gold chunks comparable.

#### Precision@k and document-identity precision

```text
Precision@k = gold chunks in top k / k
ID precision = gold-document chunks returned / all chunks returned
```

If 2 of the top 5 chunks are gold, Precision@5 = 0.40. If a graph run
returns 5 chunks and 4 belong to the correct legal document, its identity
precision is 0.80. Identity precision can improve even while exact-chunk
recall falls.

#### Document success@k

Document success@k is 1 when any top-k chunk comes from the gold document,
otherwise 0. It answers “did we find the right legal instrument?” rather than
“did we retrieve the exact annotated chunk?”

Example: a top-10 result contains a different provision from the correct
document but none of the gold chunks. Document success@10 = 1, while exact
chunk Recall@10 can still be 0.

#### Candidate Recall@30 and Candidate Hit@30

These are pre-reranking diagnostics. They measure the evidence available in
the 30-candidate pool, not the reranker’s ordering:

```text
Candidate Recall@30 = gold chunks in C30 / all gold chunks
Candidate Hit@30    = 1 if C30 contains any gold chunk, otherwise 0
```

If C30 contains 1 of 2 gold chunks, candidate recall is 0.50 and candidate
hit is 1. A reranker cannot recover a gold chunk that is absent from C30.

### Answer, citation, and operational diagnostics

#### Decision accuracy

This is a template-based answer/refuse diagnostic, not a legal-safety score.
An answerable question that is refused is wrong; an unanswerable question
that is refused is correct.

```text
DecisionAccuracy_scheduled = correct decisions / 500
DecisionAccuracy_valid     = correct decisions / valid rows
```

Example: 450 correct decisions out of 500 gives 90.0% scheduled accuracy.
The valid version changes the denominator if some rows failed.

For refusal-focused tables, the related rates are:

```text
Abstain precision = correct refusals / all refusals
Abstain recall    = correct refusals / all unanswerable questions
Abstain F1        = 2PR / (P + R)
```

False-refusal rate counts answerable questions that were incorrectly refused;
false-answer rate counts unanswerable questions that received an answer.

#### Citation presence

```text
CitationPresence = successful answerable answers with a marker
                   / successful answerable answers
```

Example: 330 of 360 successful answers contain a citation marker, so the
presence rate is 91.7%. This does not prove that the citation is correct or
entails the claim.

#### Structural coverage

For each answer, compute the share of scored factual sentences that carry a
marker, then average those per-answer shares:

```text
StructuralCoverage = average(marked factual sentences / scored factual sentences)
```

Example: two answers have coverage 3/4 and 1/2. The reported mean is
((0.75 + 0.50) / 2) = 62.5%.

#### Invalid-marker rate

```text
InvalidMarkerRate = invalid markers / all markers
```

Example: 5 invalid markers among 50 total markers gives 10.0%. This checks
marker validity, not legal citation entailment.

#### Completion and latency

```text
CompletionRate = successful rows / scheduled rows
```

Example: 490 successful rows out of 500 gives 98.0% completion.

- **Mean latency:** average runtime; sensitive to unusually slow cases.
- **p50 latency:** median runtime; half of cases are faster.
- **p95 latency:** 95% of cases are no slower than this value; it exposes the
  slow tail.
- Convert milliseconds to seconds by dividing by 1,000.

The reranker artifacts used cached BM25 candidates, so their sparse-stage
timings are not full-online hybrid latency.

### How to interpret the metrics together

No single metric means “the system is legally correct.” Retrieval metrics
measure access to annotated evidence; EM/F1/ROUGE-L measure textual overlap;
decision metrics measure answer/refuse behavior; citation metrics measure
visible structure; latency and completion measure operational cost. Human
labels are still required for legal correctness, completeness, faithfulness,
and citation entailment.

## 2. Controlled Experimental Protocol

### Core design

Every run uses the same 500-question benchmark, question IDs, reference
answers, corpus/index version, temperature 0, and maximum output length of
1,024 tokens. Within an ablation family, only the named component changes.
This makes a within-family difference easier to attribute to that component.

The four families are:

1. **Embedding text:** chunk-only versus chunk plus metadata; raw dense top-10
   retrieval, with no sparse, graph, fusion, or reranking stage.
2. **Retrieval/graph:** DenseOnly, HybridOnly, DenseGraph, and HybridGraph;
   50 retrieved seeds and at most 10 final chunks, with graph expansion of
   five seeds by one hop.
3. **Reranking:** a common 30-candidate RRF pool is ordered into a final top
   10. The shared pool isolates reranker ordering from candidate availability.
4. **LLM reasoning:** four model pairs, Base versus CoT. The intended top-10
   context is fixed per question. GPT-4o-mini contexts match exactly and
   support the strongest causal comparison; the other model pairs are
   descriptive checks because their context/provenance is not fully aligned.

Candidate budgets differ across families, so scores should be compared within
their family, not as one pooled factorial experiment.

### Saved-artifact workflow

The post-hoc evaluator reads saved manifests, outputs, metric summaries, and
latency files. It does not call a model or rerun retrieval. A row is included
only when it is not failed, errored, or skipped, has no saved error, and has a
prediction. Paired lexical statistics retain only IDs valid in both runs and
containing all three lexical metrics.

### Uncertainty analysis

The key idea is to preserve the question pairing. Instead of comparing two
independent averages, compute the treatment-minus-baseline difference for
each shared question first:

```text
Delta_i = treatment_i - baseline_i
Mean delta = average(Delta_i)
```

This controls for question difficulty. A difficult legal question affects
both configurations, so its effect largely cancels in the paired difference.

#### Paired bootstrap procedure

For each main comparison:

1. Keep each Base/CoT or baseline/treatment pair together by `qa_id`.
2. Sample the paired IDs with replacement until the original sample size is
   reached.
3. Recompute the mean per-question delta for that resample.
4. Repeat this **10,000 times**.
5. Take the 2.5th and 97.5th percentiles as the 95% confidence interval.

Smaller reranker slices use 2,000 resamples. The interval describes
benchmark-sampling uncertainty in the mean delta; it is not a measure of
run-to-run generator randomness, human-label uncertainty, or legal risk.

#### Simple example

Suppose three paired F1 deltas are `+0.10`, `-0.05`, and `0.00`:

```text
Mean delta = (0.10 - 0.05 + 0.00) / 3 = +0.0167 = +1.67 pp
```

The bootstrap repeatedly resamples these three pairs, for example
`[+0.10, +0.10, -0.05]`, and recalculates the mean. The resulting percentile
range shows how stable the observed +1.67 pp estimate is across the sampled
questions.

#### How to read the interval

- CI entirely above zero: evidence of a positive paired effect under the
  tested conditions.
- CI entirely below zero: evidence of a negative paired effect.
- CI containing zero: the observed direction is **inconclusive**, not proof
  that the configurations are identical.
- Report percentage metrics in percentage points, not relative percentages.
- EM additionally uses an exact McNemar test on the discordant binary
  outcomes, because EM is a paired 0/1 result.

## 3. Slide change

The “Fixed candidate-pool test” block was removed from the **Four Completed
Ablation Families** slide to keep that slide focused on the four families.
The shared 30-candidate pool remains part of the reranker protocol because it
is necessary for a fair ordering comparison; it is explained here instead of
occupying a separate result block on the slide.
