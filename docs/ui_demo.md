# Local Streamlit QA Demo

## Purpose

`ui/app.py` is the canonical local single-question QA/RAG interface. It uses the same named configuration loader, retriever/generator stack builder, bounded agent executor, prompt/parser, and one-case E2E runner as repository ablation execution. It does not contain a parallel demo-only RAG pipeline and does not write an evaluation run directory for each question.

Implementation-complete, local-startup-verified, bounded-live-question-verified, and production-pipeline-verified are separate states. A page that imports or starts successfully is not evidence that a provider, index, answer, or benchmark run succeeded.

## Installation

This repository currently has no established application dependency declaration in `pyproject.toml` or a `requirements*.txt` file, so Task 5 does not introduce a competing package-management format. Install into the existing environment:

```bash
pip install streamlit pyyaml openai
```

For the configured FAISS retrieval stack, also install:

```bash
pip install faiss-cpu sentence-transformers
```

Gemini configurations require `google-genai`; Qdrant configurations require `qdrant-client`. Graph and reranker dependencies alone do not enable those controls because their adapters are not wired into the production ablation stack.

## Environment variables

Production-intent OpenAI-compatible configs use:

```text
LLM_BASE_URL       OpenAI-compatible base endpoint
LLM_API_KEY        provider credential
LLM_BASE_MODEL     model selector for base/reasoning and agent comparisons
LLM_LARGER_MODEL   model selector for LLM-LargerModel
```

Gemini configs use their configured model plus `GEMINI_API_KEY`. Only configured/missing state is shown in the UI; values are never rendered. Do not put real secrets in YAML or commit them.

## Required artifacts

The current FAISS configs expect:

```text
data/faiss_index/index.faiss
data/faiss_index/payloads.jsonl
```

`payload_cache.sqlite` is created/reused by the production read-only FAISS store when its source payload file is available. `id_map.json` is optional when the index does not require a separate identifier map.

The benchmark and corpus identities currently point to:

```text
data/benchmark/qa_final.jsonl
data/v2/documents.jsonl
```

They are checked for diagnostic completeness but are not read to answer one interactive question. Full evaluation still requires them. Qdrant configs require their real collection/server contract. An enabled graph requires its configured graph artifact, and a reranker requires its model/dependency and an integrated adapter; neither adapter is currently executable through the canonical stack.

## Launch

From the repository root:

```bash
streamlit run ui/app.py
```

The app adds only repository-relative import paths derived from `ui/app.py`; it contains no machine-specific path.

## Controls

- **Pipeline config:** sourced from `configs/ablation_configs.yaml`. Supported LLM/Plain RAG/Simple Planner identities are shown with current readiness. MultiTool is visible as deferred.
- **Top-k:** temporary in-memory override from 1 through 50. It never edits YAML.
- **Filter profile:** uses the real `current_law`, `broad`, and `historical` schema values.
- **Graph:** schema-visible, but enabling it blocks execution with an actionable message because no graph adapter is integrated with `build_ablation_stack`.
- **Reranker:** behaves the same way; it is never silently ignored.
- **Question:** one trimmed multiline question. Empty submissions are rejected without discarding the previous response.
- **Ask:** explicit form submission; no request occurs on each keystroke.
- **Clear resource cache:** clears parsed registry and lazily constructed stack resources. Use it after changing local artifacts or provider environment variables.

Only the selected stack is loaded. Parsed configs and expensive immutable stack resources use Streamlit resource caching. Final answers are not globally cached.

## Output

- **Answer/status:** distinguishes Completed, Abstained, Failed, Deferred, and Blocked.
- **Sources/context:** preserves retrieval rank, effective score, vector/reranker scores when present, document/provision/chunk IDs, title/article/path, context reference, preview, and bounded expandable full text.
- **Citations:** displayed values are retrieved evidence/context references. They are not claimed as independently verified formal citations.
- **Latency:** shows canonical stage names in milliseconds. Missing stages remain `N/A`; `agent_total` includes component stages and is not summed with them.
- **Agent trace:** shows ordered bounded planner events and approved fields only. Plain RAG explicitly has no trace.
- **Diagnostics:** shows safe config identity, effective top-k/filter, provider/model selector, prompt strategy/version, agent mode, retrieval/index identity, Graph/Reranker state, seed, and preflight checks.

## Answerable test

After all readiness checks pass, choose `Agent-None-PlainRAG` or `Agent-SimplePlanner`, keep the same effective top-k/filter settings, and enter a question whose topic you know is represented in the configured legal corpus. Verify that the returned answer is supported by the displayed context rows; this guide intentionally does not invent a question/answer pair or claim the official corpus contains a specific answer.

## Unanswerable test

Enter a question outside the configured corpus scope. Expected safe behavior is `Abstained` when retrieval is empty, with no grounded answer claimed. A non-empty but irrelevant retrieval result depends on the configured retrieval threshold and provider following the insufficient-context prompt contract, so inspect evidence rather than inferring correctness from a non-empty answer.

## Error test

Temporarily select a config whose model selector, credential, provider URL, package, or index artifact is unavailable. The readiness panel should show `runtime-blocked`, Ask execution should be blocked, previous successful output should remain, and no raw traceback or secret value should appear.

## Troubleshooting

- **`No module named streamlit`:** install `streamlit` in the environment used to launch the command.
- **Repository module import error:** launch from the repository root with `streamlit run ui/app.py`.
- **Missing FAISS:** install `faiss-cpu` and verify both required index files.
- **Missing sentence-transformers:** install `sentence-transformers`; the configured embedding model must also be locally obtainable.
- **Missing model selector:** set `LLM_BASE_MODEL` or `LLM_LARGER_MODEL` as required by the selected config.
- **Missing API key:** set the config's named key variable, normally `LLM_API_KEY`; the UI never displays its value.
- **Missing base URL/provider failure:** set `LLM_BASE_URL`, verify endpoint/model compatibility, and inspect the sanitized failed stage.
- **Deferred MultiTool:** expected; approve another typed read-only tool and bounded routing acceptance contract before implementation.
- **Graph/Reranker unavailable:** expected with the current stack builder. Turning either on blocks instead of silently falling back.
- **Cache still uses an old resource:** use **Clear resource cache** after changing artifacts or environment configuration.

## Security notes

The UI never requests or stores credentials in session state. Service errors use the E2E redaction contract; diagnostics expose only environment variable names and configured/missing states. Provider reasoning fields and `<think>` blocks are removed by the existing generation parser. Trace rows exclude prompts, hidden reasoning, environment dumps, raw stack traces, and retrieved documents. Context is rendered with standard safe Streamlit APIs and never with `unsafe_allow_html=True`.

## Validation boundary

- **UI implementation complete:** entry point, service/preflight, controls, rendering, offline tests, and guide exist.
- **Local startup verified:** the Streamlit server starts without an immediate import failure and is then stopped.
- **Bounded live question verified:** one answerable and one unanswerable question run with real compatible artifacts and credentials.
- **Production pipeline verified:** controlled live runs and their official evaluation contract complete successfully.

Do not promote one boundary to another without evidence.
