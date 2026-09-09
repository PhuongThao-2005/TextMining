# Ablation 2: Dense vs. Hybrid Retrieval and Graph Expansion

## Purpose and scope

This section evaluates two connected questions:

1. Does hybrid retrieval (dense retrieval + BM25 fused with RRF) improve over
   dense-only retrieval?
2. When graph expansion is enabled, does a hybrid seed retriever improve over
   a dense seed retriever?

The four existing configurations are treated as one Ablation 2 study:

- **Dense-Only**
- **Hybrid-Only**
- **Dense + Graph**
- **Hybrid + Graph**

This is an analysis and reporting task. Preserve the existing experiment
artifacts and write only derived tables, figures, and prose in this folder.

## Source artifacts

- `../../ablation_work/denseOnly_vs_denseGraph/results/`
- `../../ablation_work/hybridOnly_vs_hybridGraph/hybrid_graph_eval_outputs/`

Use `e2e_cases.jsonl` for all paired, per-query analysis. Use the manifests to
record configuration details and the summary CSV files only as a cross-check.

## Experimental design

### Comparison A — Retrieval without graph expansion

| Baseline | Treatment | Isolated change |
| --- | --- | --- |
| Dense-Only | Hybrid-Only | Add BM25 retrieval and RRF fusion |

This comparison measures whether sparse lexical evidence complements dense
semantic retrieval before any graph-based processing.

### Comparison B — Retrieval with graph expansion

| Baseline | Treatment | Isolated change |
| --- | --- | --- |
| Dense + Graph | Hybrid + Graph | Replace dense graph seeds with hybrid graph seeds |

This comparison measures whether a better seed set leads graph expansion to
retrieve better evidence and produce better answers.

### Controlled settings

Document the following shared settings: the legal QA benchmark and gold chunk
IDs, FAISS chunk-metadata index, `intfloat/multilingual-e5-large` embedding
model, broad filter profile, candidate pool of 50, final context limit of 10,
generation model/prompt/temperature, and graph parameters (five seeds, one
hop, maximum context of 10 chunks). Hybrid retrieval additionally uses BM25
and RRF (`rrf_k = 60`).

## Metrics

Restrict retrieval-quality statistics to answerable questions. Compute
generation and unanswerable metrics on their applicable question sets.

### Main retrieval results

Report the following at K = 5 and K = 10, with MRR and nDCG reported at K =
10 as headline ranking measures:

- Recall@5 and Recall@10
- Hit@5 and Hit@10 (label Hit@10 as **GoldInContext@10** when discussing the
  final context)
- MRR@10
- nDCG@10
- Precision@5 and Precision@10 as secondary diagnostics

### Graph-specific analysis

For each paired query in both comparisons, compute:

- Delta Recall@10, Delta MRR@10, Delta nDCG@10, and Delta Token F1
- Number and percentage of queries where graph adds at least one gold chunk
  absent from the corresponding non-graph context (**graph-only gold**)
- Number and percentage of queries where graph removes at least one gold chunk
  that was present in the corresponding non-graph context (**graph-missed
  gold**)
- Mean and median change in the rank of gold chunks, plus percentages moved
  up, down, or unchanged
- Number of gold chunks newly moved into the top 10 by graph expansion

Perform a stratified version of Recall@10, MRR@10, nDCG@10, graph-only gold,
and graph-missed gold by the existing `difficulty` and `answer_type` fields.

### Context and generation quality

- Context Precision@10 and Context Recall@10, derived from final-context and
  gold chunk IDs
- GoldInContext@10
- Exact Match, Token F1, and ROUGE-L
- Unanswerable Accuracy

### Efficiency

- Average number of chunks in the final context
- Retrieval latency: p50 and p95
- Total pipeline latency: p50 and p95
- Component latency where available: embedding, dense search, BM25 search,
  RRF fusion, graph expansion, and generation

Do not introduce Recall@15, Recall@20, final-context token counts, or token
efficiency in this study.

## Tables

### Table 1 — Retrieval without graph expansion

| Method | Recall@5 | Recall@10 | GoldInContext@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense-Only | | | | | | |
| Hybrid-Only | | | | | | |
| Delta (Hybrid - Dense) | | | | | | |

### Table 2 — Graph-augmented retrieval

| Method | Recall@5 | Recall@10 | GoldInContext@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense + Graph | | | | | | |
| Hybrid + Graph | | | | | | |
| Delta (Hybrid + Graph - Dense + Graph) | | | | | | |

### Table 3 — Effect of graph expansion

| Base retriever | Delta Recall@10 | Delta MRR@10 | Delta nDCG@10 | Graph-only gold | Graph-missed gold | Gold moved into top 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense: Only -> + Graph | | | | | | |
| Hybrid: Only -> + Graph | | | | | | |

### Table 4 — Downstream quality and efficiency

| Method | Token F1 | ROUGE-L | Unanswerable Accuracy | Avg. context chunks | Retrieval p50/p95 | Total latency p50/p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense-Only | | | | | | |
| Hybrid-Only | | | | | | |
| Dense + Graph | | | | | | |
| Hybrid + Graph | | | | | | |

Exact Match should be included in an appendix or a table footnote unless it is
meaningfully discriminative.

## Statistical analysis

- Pair records by `qa_id` and retain the original ranked chunk lists.
- Use paired bootstrap 95% confidence intervals for all headline metric
  differences.
- Report win/tie/loss counts for per-query Recall@10, MRR@10, nDCG@10, and
  Token F1 deltas.
- For each graph comparison, distinguish a ranking improvement from a context
  substitution: graph may add relevant chunks, remove them, or reorder them.
- Do not add LLM-judge metrics to this ablation: no human-calibrated validation
  set is available, so Faithfulness and Answer Relevancy are outside scope.

## Figures

Figures are presentation enhancements, not additional evidence. Under the
current deadline, the finalized section uses the reportable tables and paired
bootstrap intervals as the primary presentation; no plotting dependency or
new code is introduced. If figures are added later, use no more than three:

1. **Retrieval comparison:** grouped bars for Recall@10, MRR@10, and nDCG@10
   across all four methods.
2. **Graph effect:** paired win/tie/loss chart for the two Only -> +Graph
   comparisons, using Recall@10 and MRR@10.
3. **Quality-efficiency trade-off:** scatter plot of MRR@10 against total
   pipeline p50 latency, with point size or annotation for final-context chunk
   count.

Place stratified charts and detailed rank-shift distributions in the appendix
unless they reveal the central result.

## Interpretation questions

Write the findings around these questions:

1. Does Hybrid-Only improve early evidence ranking and final-context coverage
   over Dense-Only?
2. Does Hybrid + Graph improve on Dense + Graph, showing that hybrid seeds are
   better graph-expansion inputs?
3. Does graph expansion add new gold evidence or displace already-correct
   dense/hybrid evidence?
4. Are changes in retrieval quality reflected in Token F1 and ROUGE-L?
5. What latency and context-size cost accompanies each quality change?

Use 3--5 paired qualitative examples only when they explain a dominant
quantitative pattern: one graph win, one graph loss, and one shared failure.
For each example, show the gold chunk IDs and the ranked contexts before and
after graph expansion.

## Deliverables

- Derived report tables and paired bootstrap intervals
- Tables 1--4 in Markdown form, with source CSV summaries preserved unchanged
- Optional figures generated later from the finalized tables
- A short report subsection with conclusions bounded to this legal QA
  benchmark and these fixed configurations

## Final scope decision

LLM-judge metrics (including Faithfulness and Answer Relevancy) are excluded.
No human-calibrated validation set is available, so adding those metrics would
not strengthen the scientific claims under the current deadline.
