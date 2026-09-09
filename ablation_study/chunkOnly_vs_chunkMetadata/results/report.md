# Chunk-only vs. Chunk + Metadata

## Scope

This reporting analysis compares frozen chunk-only run `20260803T065204666772Z_embed-chunkonly-dense_14eff24f` (`chunk_text_only`) with frozen chunk + metadata run `20260803T072719927028Z_embed-chunkmeta-dense_669b3b1b` (`header_plus_chunk_text`) on the same 500-case legal QA benchmark. The encoder, top-k = 10, generator, prompt, seed, corpus, and QA benchmark were held fixed; sparse retrieval, graph expansion, fusion, reranking, and agent logic were disabled. The paired prediction files contain the same 500 `qa_id`s, including 400 answerable questions. Retrieval analyses below use only those 400 answerable pairs.

## Evaluation Setup

This ablation uses two active modules: one dense-retrieval module and one generator. The frozen run manifests specify the following configuration:

- **Retrieval:** Dense retrieval only, using FAISS with `intfloat/multilingual-e5-large`, `top_k: 10`, `filter_profile: broad`, and raw FAISS contexts. Sparse retrieval is disabled. Graph retrieval/expansion is disabled. Fusion is disabled.
- **Reranker:** Disabled. No cross-encoder, RRF, or other reranking module is used.
- **Generator:** Enabled, using `gpt-4o-mini` with the `legal-grounded-answer-v2-citations` base prompt, temperature 0.0, and a 1,024-token maximum output.
- **Agent logic:** Disabled.

The only configured retrieval difference is the text embedded in the dense index: `chunk_text_only` for chunk-only and `header_plus_chunk_text` for chunk + metadata. Both runs use seed 42, benchmark `qa-final-v1`, and corpus version `v2`.

Evaluation-setup sources: [chunk-only `e2e_metrics.json`](../../../ablation_work/chunkOnly_vs_chunkMetadata/20260803T065204666772Z_embed-chunkonly-dense_14eff24f/e2e_metrics.json) and [chunk + metadata `e2e_metrics.json`](../../../ablation_work/chunkOnly_vs_chunkMetadata/20260803T072719927028Z_embed-chunkmeta-dense_669b3b1b/e2e_metrics.json).

## Evidence Coverage

At K = 5, metadata reduced exact chunk Hit by -3.8 pp (44.0% to 40.2%), but increased document success by +2.8 pp (59.0% to 61.8%); the latter interval crosses zero. At K = 10, exact-chunk coverage is effectively unchanged (-0.2 pp), while document success increases by +4.5 pp with a paired bootstrap 95% CI of [+0.5 pp, +8.8 pp]. The success curves are in `success_at_k_curve.png`; exact values and intervals are in `tables.md`.

## Disambiguation

Metadata shifts retrieval toward the correct document without improving exact provision or chunk matching. At K = 5, document success rises by 2.8 pp while provision success falls by 4.0 pp and MRR falls by 6.5 pp; the MRR interval excludes zero. At K = 10, document success rises by 4.5 pp, whereas provision success and Hit are essentially unchanged and MRR remains 5.9 pp lower. The paired outcome counts and conditional first-correct ranks in `tables.md` make this document-versus-provision divergence explicit.

## Downstream Diagnostics

Downstream differences are secondary to retrieval coverage. Metadata changes Token F1 by +0.1 pp, ROUGE-L by -0.1 pp, and unanswerable accuracy by +1.6 pp. Citation validity remains 100.0% for both variants; citation coverage changes by +0.3 pp. Mean total latency changes by -41.7 ms and P95 total latency by +130.7 ms. Small lexical-score differences should not override the paired retrieval results.

## Uncertainty And Limits

Table 1 deltas have paired bootstrap 95% confidence intervals based on 10,000 resamples of the 400 answerable question pairs; intervals that cross zero do not establish a directional effect at this sample size. Category and difficulty subgroups, especially the smallest groups, are not used for conclusions because their sample sizes are limited. This analysis concerns only this legal QA benchmark and these two frozen indexes. The accompanying metadata-retrieval paper motivates reporting evidence and document views, but its results are not assumed to transfer to this corpus.

## Frozen Source Artifacts

- Chunk-only run: `/Users/mac/Dev/HCMUS/Text_mining/L_RAG/ablation_work/chunkOnly_vs_chunkMetadata/20260803T065204666772Z_embed-chunkonly-dense_14eff24f`
- Chunk + metadata run: `/Users/mac/Dev/HCMUS/Text_mining/L_RAG/ablation_work/chunkOnly_vs_chunkMetadata/20260803T072719927028Z_embed-chunkmeta-dense_669b3b1b`
- Derived outputs only: `/Users/mac/Dev/HCMUS/Text_mining/L_RAG/ablation_study/chunkOnly_vs_chunkMetadata/results`
