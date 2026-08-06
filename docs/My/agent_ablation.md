# Agent Ablation Runs

## Objective

Task 9 isolates one intended variable: direct retrieve-then-generate execution versus a deterministic bounded planner that exposes retrieval as an explicit tool. It does not introduce an LLM planner or an autonomous loop.

Implementation-complete means the repository contracts, offline tests, structural dry-runs, artifacts, and aggregation support exist. Production-validated requires both executable configurations to finish on the same official benchmark, corpus, index, model, case set, and judge contract; no such result is claimed here.

## Experiment flows

`Agent-None-PlainRAG` uses the existing E2E path:

```text
question -> retrieval -> grounded generation -> final answer
```

There is no planner loop. Each non-empty case invokes retrieval once, and the normal prediction artifact stores the answer, retrieved context, stage latency, and errors.

`Agent-SimplePlanner` uses this state machine:

```text
START -> inspect question -> retrieve | abstain
      -> grounded generation after non-empty retrieval -> END
```

The policy `deterministic-retrieve-or-abstain` normalizes a string question, retrieves for a non-empty question, and abstains for empty input. Invalid types abstain with `unsupported_request`. Retrieval failure becomes a safe case failure, empty context becomes an abstention, and generation failure remains isolated to its case.

## Contracts and limits

The reusable package is `src/agent`. Its typed contracts include `AgentMode`, `AgentAction`, `AgentStatus`, `ToolRequest`, `ToolResult`, `PlannerDecision`, `AgentTraceEvent`, and `AgentExecutionResult`.

The only approved tool is `retrieve`. `RetrievalTool` wraps the existing retriever without mutating the corpus or index, preserves returned chunks in repository form, distinguishes `completed`, `empty`, and `failed`, records latency/result count, and sanitizes bounded error messages.

The Simple Planner configuration fixes:

- maximum planner steps: 3;
- maximum retrieval tool calls: 1;
- maximum generation calls: 1;
- planner retries: 0;
- execution deadline: 60 seconds.

The deadline is checked between synchronous stages. It prevents another stage from starting after expiry; it is not a thread-killing mechanism. Provider generation also retains its configured 60-second request timeout and two provider retries, identically for Plain RAG and Simple Planner.

No hidden reasoning is generated or stored. Decisions retain only the selected action and a bounded reason code: `retrieval_required`, `insufficient_question`, `unsupported_request`, `empty_context`, `tool_failure`, or `step_limit_reached`.

## Trace schema

Trace schema `agent-trace-v1` uses at most the configured steps and contains safe events such as:

```json
{"step": 1, "event": "planner_decision", "action": "retrieve", "reason_code": "retrieval_required", "latency_ms": 0.01}
{"step": 2, "event": "tool_call", "tool": "retrieve", "status": "completed", "result_count": 5, "latency_ms": 12.3}
{"step": 3, "event": "generation", "status": "completed", "latency_ms": 410.2}
```

Trace events never contain retrieved documents, credentials, environment dumps, raw stack traces, prompts, or chain-of-thought. Retrieved content stays in `e2e_predictions.jsonl` under `retrieved_context`.

## Latency and metrics

Existing retrieval, generation, judge, serialization, and total latency stages remain intact. Agent runs add `planner_decision`, `tool_retrieval`, and `agent_total`; `agent_total` is wall-clock planner execution and therefore includes decision, retrieval, and generation. It must not be summed with those child stages. Plain RAG has no planner or agent-total measurement, so those fields remain null rather than zero.

Existing answer/retrieval metrics remain authoritative. Agent metrics use these denominators:

- `tool_call_success_rate`: successful tool calls / attempted tool calls;
- `retrieval_invocation_rate`: cases invoking retrieval / all input cases;
- `average_tool_calls_per_case`: attempted tool calls / all input cases;
- `planner_abstention_rate`: planner-abstained cases / all input cases;
- `step_limit_failure_rate`: step-limit cases / all input cases;
- `empty_context_rate`: empty-context cases / all input cases;
- `agent_failure_rate`: agent-execution failures / all input cases.

When a denominator is zero the rate is null, not fabricated as zero. Failed cases remain excluded from answer-quality averages under the existing E2E policy.

## Fairness and metadata

Automated validation rejects every Plain RAG/Simple Planner difference outside the `agent` section. Thus benchmark and corpus identities; dense backend, index and embedding identity, top-k, filters, graph/fusion/reranker settings; provider/model/prompt/hash and decoding controls; judge, seed, output format, citations, and evaluation metrics are held constant. Planner limits and trace settings are the intended intrinsic differences.

Manifests add agent mode/enabled/version, planner policy/version, limits, allowed tools, trace/tool schema versions, plus the existing generation, prompt, retrieval, dataset, and seed identities. Credentials are never written. Old manifests remain readable; completed named agent runs missing critical comparison metadata are marked inconsistent by aggregation.

Aggregation keeps deferred and old runs visible, leaves absent optional fields blank, treats agent mode as an ablation dimension rather than a compatibility mismatch, and emits an Agent Comparison section only from eligible observed runs. It does not invent a best-agent recommendation.

## MultiTool decision

`Agent-MultiTool-Orchestrated` is explicitly `deferred`. The repository currently has one stable approved typed agent tool: read-only retrieval. A meaningful multi-tool orchestrator requires at least a second approved read-only typed tool, deterministic routing/loop tests, and a bounded acceptance contract. The retrieval tool input/output, empty-result, latency, and sanitized-failure interfaces are smoke-validated offline. Structural dry-run is the only MultiTool evidence; the config does not claim implementation or a live result.

## Offline and command usage

Offline tests use deterministic fake retrievers/generators and require no network, API key, FAISS, Qdrant, sentence-transformers, Gemini, or OpenAI-compatible endpoint.

Structural validation (creates no run artifact):

```bash
python scripts/run_ablation_config.py --config Agent-None-PlainRAG --dry-run
python scripts/run_ablation_config.py --config Agent-SimplePlanner --dry-run
python scripts/run_ablation_config.py --config Agent-MultiTool-Orchestrated --dry-run
```

Bounded live smoke, only after the shared benchmark/index/model/credentials and quota are verified:

```bash
python scripts/run_ablation_config.py --config Agent-None-PlainRAG --limit 5
python scripts/run_ablation_config.py --config Agent-SimplePlanner --limit 5
```

Use the same benchmark prefix/case set for both. Batch and aggregation:

```bash
python scripts/run_ablation_batch.py --configs Agent-None-PlainRAG Agent-SimplePlanner
python scripts/aggregate_ablation_results.py --runs-dir evaluation_runs/ablation
```

Real execution still requires the configured official benchmark, corpus, FAISS index, `LLM_BASE_MODEL`, `LLM_API_KEY`, and `LLM_BASE_URL`. Missing dependencies must produce diagnostics, never a fake production result.
