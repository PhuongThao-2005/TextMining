# Chunk-only vs. Chunk + Metadata: Section Plan

## Purpose and scope

This is one results subsection of the broader ablation study. Its purpose is to
present the existing chunk-only versus chunk-plus-metadata experiment clearly,
with enough statistics and analysis to explain the observed retrieval behavior.

It is a reporting and analysis task only. Do not rerun the experiment, alter the
source artifacts, add new metrics requiring manual labels, or launch a new
field-level ablation.

The source artifacts are:

- `../../ablation_work/chunkOnly_vs_chunkMetadata/20260803T065204666772Z_embed-chunkonly-dense_14eff24f/`
- `../../ablation_work/chunkOnly_vs_chunkMetadata/20260803T072719927028Z_embed-chunkmeta-dense_669b3b1b/`

Compute all derived statistics from the paired `e2e_predictions.jsonl` files.
Store only derived tables, figures, and prose under `results/` in this folder.

## Experimental statement

Compare two FAISS dense-retrieval indexes over the same 500 legal QA cases:

- **Chunk-only:** embeddings contain `chunk_text_only`.
- **Chunk + metadata:** embeddings contain `header_plus_chunk_text`.

The encoder (`intfloat/multilingual-e5-large`), top-k = 10, generator
(`gpt-4o-mini`), prompt, seed, corpus, and QA benchmark are held fixed. Sparse
retrieval, graph expansion, fusion, reranking, and agent logic are disabled.

## Statistics to report

Use both K = 5 and K = 10. K = 5 represents shallow/high-confidence retrieval;
K = 10 is the full context passed to the generator.

### Table 1 — Main retrieval results

Report existing exact-chunk metrics plus two source-level views derived from the
same predictions:

| Variant | Hit@5 | Recall@5 | MRR@5 | Document Success@5 | Provision Success@5 | Hit@10 | Recall@10 | MRR@10 | Document Success@10 | Provision Success@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chunk-only | | | | | | | | | | |
| Chunk + metadata | | | | | | | | | | |
| Delta (metadata - chunk-only) | | | | | | | | | | |

- **Document Success@K:** at least one retrieved top-K chunk has a
  `document_id` in the question's gold `document_ids`.
- **Provision Success@K:** at least one retrieved top-K chunk has a
  `provision_id` in the question's gold `provision_ids`.

These two additions distinguish exact-chunk misses from retrieval of a related
chunk within the correct legal source.

### Table 2 — Downstream and operational context

Keep this compact and secondary:

| Variant | Token F1 | ROUGE-L | Unanswerable accuracy | Citation validity | Citation coverage | Mean total latency (ms) | P95 total latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chunk-only | | | | | | | |
| Chunk + metadata | | | | | | | |
| Delta (metadata - chunk-only) | | | | | | | |

Exact Match may be placed in a footnote or appendix because it is nearly zero
for abstractive and extractive answers and is not a useful headline measure.

## Statistical analysis

For each answerable question, preserve the existing retrieval order (`rank` 1
through 10) and compare the two variants as a pair.

- Report metadata win / tie / loss counts for Hit@5, Hit@10, Document
  Success@5, and Document Success@10.
- Report paired bootstrap 95% confidence intervals for the differences in the
  metrics in Table 1.
- Report the mean first correct rank for gold chunks, provisions, and documents
  only as a short supporting statistic; always pair it with the relevant success
  rate so failures are not hidden.

## Figures

Include at most two figures:

1. **Success@K curve, K = 1--10:** chunk Hit@K, Provision Success@K, and
   Document Success@K for both variants. Mark K = 5 and K = 10.
2. **Paired outcome chart:** metadata win / tie / loss at K = 5 and K = 10 for
   chunk and document success.

## Insights to write

Organize the subsection around three concise questions:

1. **Coverage:** Does metadata improve or reduce the probability that a useful
   source appears in the top 5 or top 10?
2. **Disambiguation:** When exact chunk retrieval changes, does metadata improve
   document/provision identification, or does it cause source-level confusion?
3. **Downstream impact:** Are retrieval changes reflected in answer quality,
   abstention, citations, or latency? Treat small lexical-score differences
   cautiously.

Add 3--5 paired examples only if they explain a prominent quantitative pattern:
one metadata win, one chunk-only win, and one shared failure. For each, show the
gold source and the top three retrieved sources under both variants.

## Interpretation boundary

State that this analysis evaluates the two existing indexes on this legal QA
benchmark. The accompanying metadata-retrieval paper motivates reporting both
supporting-context and correct-document views, but its results are not assumed
to transfer to this corpus.
