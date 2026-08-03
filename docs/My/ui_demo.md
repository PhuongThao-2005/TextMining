# Local Streamlit QA Demo

## Purpose

`ui/app.py` is the canonical search-first QA/RAG interface. It uses the same named configuration loader, retriever/generator stack builder, bounded agent executor, prompt/parser, and one-case E2E runner as repository ablation execution. Follow-ups execute that same retrieval path again; there is no parallel demo-only RAG pipeline and no per-question evaluation directory.

The interface has three explicit selections: **Demo Preview**, **Production**, and **Auto**. Demo is a deterministic UI fixture with prominent mock labels. Production uses only the existing QA/RAG service and never falls back to mock data. Auto selects Production only after all blocking readiness checks pass; otherwise it clearly opens Demo Preview. See `docs/ui_modes.md` for the artifact compatibility and transition contract.

The presentation uses the centralized warm-light/charcoal-dark design system documented in `docs/ui_theme.md`. The empty state is a single search-first hero; answers use an editorial research thread rather than chat bubbles. Runtime custom tokens extend `.streamlit/config.toml` without changing service behavior.

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

They are checked for diagnostic completeness but are not read to answer one interactive question. Full evaluation still requires them. Qdrant configs require their real collection/server contract. Full-stack configs additionally require BM25 index/metadata, a compatible graph pickle, `rank-bm25`, and the configured Cross-Encoder dependency/model.

## Launch

From the repository root:

```bash
streamlit run ui/app.py
```

For the internal deterministic component gallery, open the application with `?preview=design-system`. This preview never constructs production resources.

Use `?preview=long-answer&citation=1-1&full_source=1` for the deterministic highlighted Demo source view. Use `?preview=production-mapping&citation=1-1&full_source=1` for a non-live Production-shaped source mapping with no evidence span. Both are visual fixtures and never validate a real provider or corpus.

The app adds only repository-relative import paths derived from `ui/app.py`; it contains no machine-specific path.

## Controls

- **Runtime mode:** explicitly selects Demo Preview, Production, or Auto. The selection and normalized responses are session-local.
- **Pipeline config:** sourced from `configs/ablation_configs.yaml`. Supported LLM/Plain RAG/Simple Planner identities are shown with current readiness. MultiTool is visible as deferred.
- **Top-k:** temporary in-memory override from 1 through 50. It never edits YAML.
- **Filter profile:** uses the real `current_law`, `broad`, and `historical` schema values.
- **Graph:** enables the integrated bounded structural expansion stage when its compatible pickle is available.
- **Reranker:** enables the configured Cross-Encoder after Hybrid/RRF candidate fusion.
- **Question:** a dominant landing-page search field. After the first turn, `st.chat_input` submits follow-ups.
- **Ask:** explicit form submission; no request occurs on each keystroke.
- **Reset cache:** clears parsed registry and lazily constructed stack resources. **New search** clears the bounded in-memory thread.

When more than one manifest-backed artifact is compatible, the sidebar requires an explicit artifact selection. The application never chooses by timestamp and never rebuilds an index.

Only the selected stack is loaded. Parsed configs and expensive immutable stack resources use Streamlit resource caching. Final answers are not globally cached.

## Output

- **Answer/status:** distinguishes Completed, Abstained, Failed, Deferred, and Blocked.
- **Sources/context:** preserves retrieval rank, effective score, vector/reranker scores when present, document/provision/chunk IDs, title/article/path, context reference, preview, and bounded expandable full text.
- **Citations:** validated answer markers link to cited source sections. Cited cards and additional uncited retrieved contexts are distinct. These remain retrieved evidence/context references, not independently verified formal legal citations.
- **Latency:** shows canonical stage names in milliseconds. Missing stages remain `N/A`; `agent_total` includes component stages and is not summed with them.
- **Agent trace:** shows ordered bounded planner events and approved fields only. Plain RAG explicitly has no trace.
- **Diagnostics:** shows safe config identity, effective top-k/filter, provider/model selector, prompt strategy/version, agent mode, retrieval/index identity, Graph/Reranker state, seed, and preflight checks.

## Long-form Demo Preview

The primary **Long answer · 3 sources** example asks “Show a complete example with several supporting sources.” It deterministically returns a multi-paragraph fictional answer, a numbered list, `[1]`, `[2]`, and `[3]`, and claims with adjacent multi-source markers. The three mock documents are **Demo Request Submission Guide**, **Demo Evidence Review Handbook**, and **Demo Intake Procedure**. Every card says **DEMO SOURCE** and every full text says **Mock content — not an authoritative document**.

Other deterministic examples cover one cited plus one additional source, multiple sources, abstention, and an invalid marker. None constructs a Production provider. Clicking a valid inline badge is an internal control: it selects that citation within its owning turn and shows a compact preview without navigating. **View source** opens the complete retrieved chunk in an `st.dialog` on the same page. **Open original document ↗** is a separate secondary action, appears only for a validated HTTP(S) URL on a Production source, and is the only source action that leaves the app. Invalid IDs cannot resolve to a source. New search, Clear conversation, and viewer Close clear source selection; theme reruns preserve it.

Demo sources use preconfigured explicit offsets. The full view highlights only the validated slice. Production sources still open normally, but because the current pipeline is `SOURCE_MAPPING_ONLY`, they explain that an exact supporting passage was not recorded and show no highlight. Diagnostics separately report citation validity, evidence availability, valid spans, rejected spans, and validation warnings.

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
- **Graph/Reranker unavailable:** verify graph/BM25 artifacts, `rank-bm25`, `sentence-transformers`, model download access and the resolved config; preflight blocks rather than silently falling back.
- **Cache still uses an old resource:** use **Clear resource cache** after changing artifacts or environment configuration.

## Security notes

The UI never requests or stores credentials in session state. Service errors use the E2E redaction contract; diagnostics expose only environment variable names and configured/missing states. Provider reasoning fields and `<think>` blocks are removed by the existing generation parser. Trace rows exclude prompts, hidden reasoning, environment dumps, raw stack traces, and retrieved documents. Model answers use native Streamlit rendering. Retrieved source text uses native rendering unless an exact validated highlight is available; in that case every untrusted segment is HTML-escaped before the UI inserts its own fixed highlight wrapper. Model-generated HTML is never trusted.

Conversation history is session-only and capped at 10 turns. Every turn owns its response and citation list, so `[1]` never links across turns. Suggested follow-ups are deterministic UI prompts and make no factual claims.

## Validation boundary

- **UI implementation complete:** entry point, service/preflight, controls, rendering, offline tests, and guide exist.
- **Local startup verified:** the Streamlit server starts without an immediate import failure and is then stopped.
- **Bounded live question verified:** one answerable and one unanswerable question run with real compatible artifacts and credentials.
- **Production pipeline verified:** controlled live runs and their official evaluation contract complete successfully.

Do not promote one boundary to another without evidence.
