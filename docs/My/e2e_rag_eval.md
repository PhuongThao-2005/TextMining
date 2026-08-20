# Kaggle E2E RAG evaluation

The supported workflow is:

```text
Copy notebooks/e2e_rag_eval.ipynb to Kaggle
→ edit REPO_URL and REPO_BRANCH
→ attach benchmark/index Kaggle Datasets
→ configure Kaggle Secrets
→ run setup
→ restart the kernel if required
→ use inspect or smoke first
→ retrieve outputs from /kaggle/working
```

The notebook is self-bootstrapping. The repository is not expected to exist in the Kaggle runtime, and no project module is imported until cloning, working-directory setup, and dependency setup are complete.

## Configuration

The editable cell defaults to the documented public repository and branch `main`. For a fork, change `REPO_URL` and `REPO_BRANCH`. Internet access must be enabled for cloning, dependency installation, model downloads, and remote-provider calls.

Public Git is the primary path. For a private repository, set `PRIVATE_REPOSITORY = True` and add a Kaggle Secret named by `GITHUB_TOKEN_SECRET_NAME` (default `GITHUB_TOKEN`). The notebook reads it lazily, passes it only as an in-memory HTTP header, and keeps `origin` on the unauthenticated URL. It never prints or persists the token.

`FORCE_RECLONE` removes only `REPO_DIR`; it never removes `/kaggle/working`. Existing valid checkouts can be reused and updated with a fast-forward-only pull.

## Kaggle Secrets

Configure these secrets as required by the selected named config:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_BASE_MODEL`
- `LLM_LARGER_MODEL`

Existing environment variables are preserved. Otherwise values are copied from Kaggle Secrets into `os.environ`. Diagnostics show only `configured` or `missing`. Values are not written to configs, manifests, errors, exports, or notebook metadata.

Provider/model access and quota remain the user's responsibility. An API-hosted LLM does not run on Kaggle GPU.

## Benchmark and retrieval inputs

Attach benchmark, corpus, and retrieval artifacts as Kaggle Datasets. Kaggle mounts them read-only below `/kaggle/input`; the notebook never writes there.

Set these values when unique-name discovery is insufficient:

- `BENCHMARK_SOURCE`: benchmark JSONL.
- `CORPUS_SOURCE`: corpus identity file.
- `FAISS_INDEX_SOURCE`: `index.faiss`.
- `FAISS_PAYLOADS_SOURCE`: `payloads.jsonl`.
- `FAISS_MANIFEST_SOURCE`: optional index manifest.
- `GRAPH_SOURCE`: graph artifact when graph retrieval is enabled.

Real files are required; placeholders and fixture substitution are prohibited. FAISS index/payload artifacts must come from the same compatible build and match the corpus/benchmark identity. When files are mounted in different dataset directories, the notebook creates canonical links under `/kaggle/working/e2e_runtime_inputs/faiss`. The effective paths and original Kaggle input identities are persisted in the resolved run config; `configs/ablation_configs.yaml` is never modified.

## Dependencies and CPU/GPU behavior

The current `pyproject.toml` contains tool settings but no complete install metadata, so the notebook installs PyYAML and, only for smoke/full, missing packages required by the FAISS/OpenAI-compatible path plus `sentence-transformers` for embedding and global Cross-Encoder reranking. It does not request Streamlit, pandas, pyarrow, CUDA, or PyTorch directly.

Pandas is optional and imported only in the final display cell. If pandas, NumPy, or pyarrow are incompatible, tables fall back to Python dictionaries and production execution/artifact export continue. If newly installed imports are not visible, the notebook prints exactly:

```text
Restart the Kaggle session and rerun from the first cell.
```

CUDA is selected only when enabled and reported available by PyTorch. CPU is otherwise valid. GPU can accelerate local embedding/reranking/models; it is not required for a remote-provider LLM and the notebook does not claim remote inference used Kaggle GPU.

## Run modes

`inspect` is the committed default. It performs no retrieval or model call. Set `EXISTING_RUN_DIR` to a run under `/kaggle/input` or `/kaggle/working`; leaving it unset completes with an informational message.

`smoke` requires complete preflight and calls the canonical named-config runner with exactly `SMOKE_LIMIT` cases. It does not substitute fixture data.

The notebook defaults to `CONFIG_NAME = "LLM-BaseReasoning"`. Select each of the four LLM configs in turn while holding the benchmark and retrieval artifacts fixed. Their shared path is Dense FAISS -> Graph -> RRF fusion -> global Cross-Encoder reranker -> Generator. BM25 is disabled, so no BM25 server or BM25 credential is needed.

`full` must be selected explicitly. It requires all packages, compatible benchmark/corpus/index artifacts, credentials, provider access, model access, and quota. It never downgrades to smoke.

Preflight distinguishes structural validity from runtime readiness and reports repository, commit, Kaggle/GPU/device, packages, optional pandas, config/defer state, all input artifacts, model/provider/credential status, writable roots, and selected mode. Secret values are never displayed.

## Runs, exports, and analysis

Canonical runs are written to:

```text
/kaggle/working/evaluation_runs/ablation
```

Successful smoke/full runs are exported without overwrite to:

```text
/kaggle/working/e2e_rag_outputs/<run_id>
/kaggle/working/e2e_rag_outputs/<run_id>.zip
```

Export uses the repository artifact loader/exporter and copies only existing canonical output files. It excludes benchmark/corpus data, FAISS indexes, model caches, credentials, and environment dumps.

The notebook displays safe resolved config, run/case details, contexts and scores, evidence references, overall/retrieval/agent/grouped metrics, stage latency, bounded agent trace, failures, denominators, reproducibility metadata, and artifact paths. Null values remain null/`N/A`; failed/skipped cases stay visible. Context references are not described as verified formal citations unless the structured contract establishes that status. Hidden reasoning and raw stack traces are not displayed.

## Troubleshooting

- Clone blocked: enable Kaggle Internet, verify URL/branch, and for private Git verify the secret has repository read access.
- Invalid checkout: remove only the configured `REPO_DIR` by setting `FORCE_RECLONE = True`.
- Ambiguous input: set the corresponding `*_SOURCE` to a full file below `/kaggle/input`.
- Missing FAISS artifacts: attach both `index.faiss` and `payloads.jsonl` from the same build.
- Model selector blocked: configure `LLM_BASE_MODEL` or `LLM_LARGER_MODEL` as selected.
- Provider blocked: verify endpoint, credential, network access, model permission, and quota.
- Pandas display failure: continue with Python-row output; pandas/pyarrow are not execution dependencies.
- Existing export: choose a new production run; exports intentionally never overwrite.

## Validation boundary

Repository tests validate notebook structure, ordering, helper behavior with mocks, secret handling, dependency fallback, path overrides, run-mode dispatch, and export safety without network, Kaggle, GPU, FAISS, or a live provider. They do not constitute actual Kaggle execution, bounded Kaggle smoke, production FAISS execution, GPU execution, provider execution, or a full benchmark.
