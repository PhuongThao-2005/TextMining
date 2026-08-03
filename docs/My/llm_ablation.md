# Controlled LLM Ablation Contract

## Purpose and comparison matrix

These production-intent configurations evaluate one controlled variable at a time:

| Config | Prompt strategy | Model selector | Intended change |
| --- | --- | --- | --- |
| `LLM-BaseReasoning` | `base` | `env:LLM_BASE_MODEL` | Reference condition |
| `LLM-CoTReasoning` | `reasoning` | `env:LLM_BASE_MODEL` | Prompt strategy only |
| `LLM-LargerModel` | `base` | `env:LLM_LARGER_MODEL` | Model only |
| `LLM-LargerModel-CoTReasoning` | `reasoning` | `env:LLM_LARGER_MODEL` | Model and prompt interaction |

The config loader runs an automated fairness check. Base versus CoT may differ only
at `generation.prompt_strategy`; Base versus Larger may differ only at
`generation.model`; Larger+CoT must differ at exactly those two fields. Benchmark,
corpus, retrieval/index/embedding settings, top-k,
filters, agent and judge settings, decoding controls, retry/timeout policy, seed,
answer format, and citation format are held constant.

The committed configs use the same official Dense+BM25+RRF+Cross-Encoder+Graph
retrieval stack. The canonical full-stack adapter loads the handed-over BM25 and
graph artifacts, applies Graph expansion after fusion/reranking, and exposes one
retrieval contract to all four LLM comparisons.

## Prompt and output safety

Both modes use template version `legal-grounded-answer-v2-citations`, the same context
formatting, abstention text, answer format, and `[n]` citation-label contract.
The base strategy asks for a direct grounded answer. The reasoning strategy asks
the model to reason internally and return only the final grounded answer.

Provider reasoning fields and well-formed `<think>...</think>` blocks are removed
before scoring or serialization. For an unterminated `<think>` block, only text
after an explicit final-answer marker is retained; otherwise the unsafe remainder
is discarded. Reasoning is never written to predictions, aggregate CSV files, or
Markdown reports.

## Required environment and artifacts

No model availability is assumed or hard-coded. Set:

```text
LLM_BASE_URL
LLM_API_KEY
LLM_BASE_MODEL
LLM_LARGER_MODEL
```

The configured API must be OpenAI-compatible and support the selected models.
The production-intent configs also require:

```text
data/benchmark/qa_final.jsonl
data/v2/documents.jsonl
data/faiss_index/index.faiss
data/faiss_index/payloads.jsonl
data/sparse_index/bm25_index.pkl
data/sparse_index/bm25_metadata.pkl
data/graph/knowledge_graph.gpickle
```

The benchmark, corpus, and index versions must describe the same frozen
experiment inputs. The placeholder index version in the config must be replaced
with the team's verified index identity before official execution.

## Validation and execution

Structural validation does not call APIs or claim model availability:

```bash
python scripts/run_ablation_config.py --config LLM-BaseReasoning --dry-run
python scripts/run_ablation_config.py --config LLM-CoTReasoning --dry-run
python scripts/run_ablation_config.py --config LLM-LargerModel --dry-run
python scripts/run_ablation_config.py --config LLM-LargerModel-CoTReasoning --dry-run
```

After artifact, credential, model, and quota checks, run a bounded smoke test:

```bash
python scripts/run_ablation_config.py --config LLM-BaseReasoning --limit 5
```

Then use the identical limit and case set for the other three configs. The existing
batch runner preserves requested order and independent statuses:

```bash
python scripts/run_ablation_batch.py \
  --configs LLM-BaseReasoning LLM-CoTReasoning LLM-LargerModel LLM-LargerModel-CoTReasoning \
  --limit 5
```

Do not start a full benchmark until all four configs resolve, the
provider confirms model access, and quota is sufficient. Client calls use the
configured timeout and retry count. Missing model environment variables fail
preflight clearly; missing credentials or runtime API failures are recorded by
the existing failed/deferred run contracts and remain resumable through batch
summaries.

## Artifacts and comparability inspection

Runs are written below `evaluation_runs/ablation/<run-id>/`. The resolved config
and manifest record the provider, resolved model, prompt strategy, prompt template
version/hash, temperature, top-p, token limit, timeout, retries, seed, benchmark,
corpus, retrieval, judge, and agent configuration. They record environment
variable names but never credential values.

Inspect `manifest.json`, `resolved_config.yaml`, `e2e_predictions.jsonl`,
`e2e_metrics.json`, `latency.json`, and `errors.jsonl` before scaling up. Aggregate
compatible runs with:

```bash
python scripts/aggregate_ablation_results.py --runs-dir evaluation_runs/ablation
```

The aggregator exposes LLM comparison metadata as CSV columns. It compares
quality only within a compatible benchmark/corpus/index group and rejects a
completed named LLM run that lacks critical prompt/model/decoding metadata.

Offline tests prove configuration, prompt, parsing, runner, and aggregation
contracts only. They are not official LLM experiments and produce no production
metrics.
