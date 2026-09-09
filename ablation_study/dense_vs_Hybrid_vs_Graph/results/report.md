# Ablation 2: Dense vs. Hybrid Retrieval and Graph Expansion

**Status:** Finalized from the existing 500-case Dense and Hybrid output
artifacts. The report uses deterministic metrics and paired bootstrap intervals;
LLM-judge metrics are intentionally excluded.

## Overview

This ablation compares four fixed configurations on the same 500-question legal
QA benchmark: Dense-Only, Hybrid-Only, Dense + Graph, and Hybrid + Graph. The
benchmark contains 400 answerable and 100 unanswerable questions. Retrieval
metrics are computed against gold chunk IDs for the answerable subset; answer
quality and abstention behavior are reported separately.

The Dense and Hybrid branches use the same FAISS chunk-metadata index,
`intfloat/multilingual-e5-large` embeddings, broad validity filtering, a
50-result candidate pool, and a final context limit of 10. Hybrid retrieval
adds BM25 and RRF fusion with `rrf_k=60`. Graph variants expand five seed
chunks by one hop with a maximum graph context of 10.

## Findings

### Hybrid retrieval does not improve exact-chunk retrieval on this benchmark

Dense-Only is stronger than Hybrid-Only on every headline retrieval metric:
Recall@10 is 0.4855 versus 0.4257, GoldInContext@10 is 0.5325 versus 0.4650,
MRR@10 is 0.2267 versus 0.2252, and nDCG@10 is 0.2813 versus 0.2638. The
paired analysis confirms the same direction: Hybrid changes Recall@10 by
−0.0598 and nDCG@10 by −0.0175 relative to Dense.

The generation metrics move in the opposite direction, but only slightly.
Hybrid-Only raises Token F1 by 0.0041 in the paired comparison and has a
slightly higher ROUGE-L than Dense-Only. This means that the current hybrid
fusion does not improve exact gold-chunk retrieval, yet can provide context
that is marginally more useful to the generator under the existing prompt.

### Hybrid seeds do not rescue graph-augmented retrieval

The same pattern remains after graph expansion. Dense + Graph exceeds Hybrid +
Graph on Recall@10 (0.3615 versus 0.3076), GoldInContext@10 (0.3900 versus
0.3250), MRR@10 (0.2045 versus 0.2012), and nDCG@10 (0.2374 versus 0.2228).
Therefore, the current results do not support the claim that hybrid seeds are
better graph-expansion inputs.

### Graph expansion mostly displaces existing evidence

Graph expansion substantially lowers retrieval coverage for both seed
retrievers. Dense graph expansion changes Recall@10 by −0.1240; Hybrid graph
expansion changes it by −0.1181. In the Hybrid branch, graph expansion adds a
new gold chunk at top-10 for only 6 of 400 answerable queries (1.5%), while it
misses a gold chunk that was present before expansion for 59 queries (14.75%).
The Dense branch shows the same behavior: 1 query gains a graph-only gold chunk,
whereas 61 queries lose at least one previously retrieved gold chunk.

The rank analysis is consistent with this interpretation. Of 550 gold-chunk
observations, Dense graph expansion moves 75 downward and only 8 upward;
Hybrid graph expansion moves 71 downward and 13 upward. Most gold chunks remain
unchanged, but the negative mean rank shifts and the large graph-missed counts
show that graph expansion is replacing useful seed evidence more often than it
adds missing evidence.

### Answer quality changes are small and do not track retrieval coverage

Graph expansion slightly increases Token F1 for both branches: Dense +0.0038
and Hybrid +0.0024 in paired comparisons. ROUGE-L increases for Dense but is
essentially unchanged/slightly lower for Hybrid. Unanswerable Accuracy improves
from 0.38 to 0.41 for Dense and from 0.38 to 0.47 for Hybrid. These downstream
changes should be described as small generation/abstention effects rather than
evidence that graph expansion improves retrieval.

Graph expansion does increase deterministic context density because it returns
fewer chunks. ID Context Precision rises from 0.0580 to 0.0800 for the Dense
branch and from 0.0493 to 0.0641 for the Hybrid branch. This should be read
alongside the substantial Context Recall@10 loss: the graph context is denser,
but it covers fewer of the gold chunks.

### Uncertainty of the paired comparisons

The paired percentile bootstrap intervals support the main retrieval findings.
The Hybrid-versus-Dense Recall@10 differences exclude zero both without graph
([−0.0971, −0.0221]) and with graph ([−0.0996, −0.0074]). The graph-expansion
Recall@10 and MRR@10 losses exclude zero for both Dense and Hybrid. In contrast,
the small Token F1 improvements have intervals that include zero, so they are
not statistically decisive.

### Hybrid retrieval has a substantial efficiency cost

Dense retrieval takes approximately 0.80 seconds at median retrieval latency,
compared with approximately 27.85 seconds for Hybrid retrieval when the
amortized BM25 cost is included. Total pipeline median latency is approximately
5.48 seconds for Dense-Only and 31.54 seconds for Hybrid-Only. The Hybrid run
also reports a one-time BM25 precomputation cost of roughly 13,495 seconds,
which should be reported separately from per-query latency.

Graph variants return fewer chunks on average: 5.605 for Dense + Graph and
6.305 for Hybrid + Graph, compared with 10 for the non-graph variants. This
context reduction is a likely mechanism behind the retrieval losses and should
be investigated before presenting graph expansion as a quality improvement.

## Conclusion

Under the current settings, Dense-Only is the strongest retrieval method.
Hybrid retrieval provides a small downstream generation benefit but lowers
exact-chunk retrieval quality and adds substantial BM25 latency. Graph
expansion currently reduces retrieval coverage for both Dense and Hybrid
seeds; it adds very few new gold chunks while frequently removing gold chunks
that were already present. The evidence therefore favors treating graph
expansion as an unresolved design issue rather than a demonstrated improvement.

These conclusions are limited to this legal QA benchmark, the current FAISS and
BM25 indexes, graph expansion implementation, and fixed generation prompt.

## Analysis limitations

LLM-judge metrics such as Faithfulness and Answer Relevancy were intentionally
excluded because no human-calibrated validation set is available. The hard
difficulty stratum contains only one answerable question, so its stratified
values are descriptive only. The conclusions are based on deterministic
retrieval/generation metrics and paired bootstrap intervals; no claim is made
about unmeasured semantic judge metrics.
