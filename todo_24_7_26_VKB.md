# TODO 24/7/26 — VKB — Bình Ablation Control

## 1. Purpose

Bình controls benchmark, corpus, config matrix, manifest validation, runbook/status.

Bình not implement Dense, Hybrid, Graph, Agent. Other people build those.

## 2. Execution order checklist

- [x] Spec 009 — Benchmark Contract and Validation
- [ ] Spec 010 — Corpus Artifact Contract
- [ ] Spec 011 — Ablation Config Matrix
- [ ] Spec 012 — Run Manifest and Output Validation
- [ ] Spec 013 — Ablation Runbook and Status Dashboard

## 3. Detailed specs

### Spec 009 — Benchmark Contract and Validation

Directory: `specs/009-ablation-benchmark-contract/`

Deliverables:
- `specs/009-ablation-benchmark-contract/spec.md`
- `specs/009-ablation-benchmark-contract/tasks.md`
- `scripts/validate_ablation_benchmark.py`
- `docs/ablation_benchmark_contract.md`

Command:
```bash
python scripts/validate_ablation_benchmark.py --benchmark data/benchmark/qa_final.jsonl --out docs/ablation_benchmark_contract.md
```

TODO:
- [x] Lock official benchmark path: `data/benchmark/qa_final.jsonl`
- [x] Set benchmark version: `qa-final-8edde818ac9d`
- [x] Count QA cases: 500
- [x] Validate fields: `qa_id`, `question`, `answer` or `reference_answer`, `answer_type`, `category`, `difficulty`, ground-truth IDs if available
- [x] Write validation report: `docs/ablation_benchmark_contract.md` (`PASS_WITH_WARNINGS`, locked with optional GT coverage warnings)

Done when official benchmark documented and validation pass/known issues recorded. Status: `PASS_WITH_WARNINGS`; benchmark locked for ablation with optional ground-truth coverage warnings documented.

### Spec 010 — Corpus Artifact Contract

Directory: `specs/010-ablation-corpus-contract/`

Deliverables:
- `specs/010-ablation-corpus-contract/spec.md`
- `specs/010-ablation-corpus-contract/tasks.md`
- `scripts/validate_ablation_corpus.py`
- `docs/ablation_corpus_contract.md`

Command:
```bash
python scripts/validate_ablation_corpus.py --corpus-root data --out docs/ablation_corpus_contract.md
```

TODO:
- [ ] Lock paths for `documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `validity_timeline.jsonl`, `authority_index.jsonl`
- [ ] Count records
- [ ] Check ID consistency where possible
- [ ] Set corpus version
- [ ] Mark optional/missing artifacts clearly

Done when corpus snapshot documented and team told not to mix snapshots.

### Spec 011 — Ablation Config Matrix

Directory: `specs/011-ablation-config-matrix/`

Deliverables:
- `specs/011-ablation-config-matrix/spec.md`
- `specs/011-ablation-config-matrix/tasks.md`
- `configs/ablation_configs.yaml`
- `docs/ablation_config_matrix.md`

TODO:
- [ ] Add benchmark path/version
- [ ] Add corpus paths/version
- [ ] Add all config names: `Retrieval-DenseOnly`, `Embed-ChunkOnly-Dense`, `Embed-ChunkMeta-Dense`, `Retrieval-Hybrid-SparseDense`, `Retrieval-Dense-Graph`, `Retrieval-Hybrid-SparseDense-Graph`, `Rerank-None-Hybrid`, `Rerank-RRF-Hybrid`, `Rerank-CrossEncoder-Hybrid`, `Rerank-RRFPlusCrossEncoder-Hybrid`, `LLM-BaseReasoning`, `LLM-CoTReasoning`, `LLM-LargerModel`, `Agent-None-PlainRAG`, `Agent-SimplePlanner`, `Agent-MultiTool-Orchestrated`
- [ ] Add owner, priority, type, top_k, require_e2e, expected outputs for each config
- [ ] Use priority labels: `must_have`, `should_have`, `nice_to_have`

Done when teammates can run by config name.

### Spec 012 — Run Manifest and Output Validation

Directory: `specs/012-ablation-run-manifest-validation/`

Deliverables:
- `specs/012-ablation-run-manifest-validation/spec.md`
- `specs/012-ablation-run-manifest-validation/tasks.md`
- `schemas/ablation_manifest.schema.json`
- `scripts/validate_ablation_run.py`
- `docs/ablation_run_output_contract.md`

Command:
```bash
python scripts/validate_ablation_run.py --run-dir evaluation_runs/ablation/<run_id> --config configs/ablation_configs.yaml
```

Required retrieval output:
- `manifest.json`
- `retrieval_cases.jsonl`
- `retrieval_metrics.json`
- `latency.json`
- `report.md`

Required E2E extra output:
- `e2e_predictions.jsonl`
- `e2e_metrics.json`

TODO:
- [ ] Define manifest schema
- [ ] Validate benchmark/corpus match official contract
- [ ] Validate config_name exists in matrix
- [ ] Validate metrics and latency files
- [ ] Separate retrieval-only vs E2E required files
- [ ] Output valid/needs_rerun result

Done when bad runs get caught before final report.

### Spec 013 — Ablation Runbook and Status Dashboard

Directory: `specs/013-ablation-runbook-dashboard/`

Deliverables:
- `specs/013-ablation-runbook-dashboard/spec.md`
- `specs/013-ablation-runbook-dashboard/tasks.md`
- `docs/ablation_runbook.md`
- `evaluation_runs/ablation/run_status.md`

TODO:
- [ ] Write runbook with official benchmark/corpus/config names
- [ ] Add commands for one config and batch configs
- [ ] Add failed/deferred rules
- [ ] Add validation checklist
- [ ] Create status table with columns: Config, Owner, Priority, Status, Run ID, Valid?, Notes
- [ ] Use statuses: `pending`, `ready`, `running`, `completed`, `failed`, `needs_rerun`, `deferred`

Done when team has one operating manual and dashboard.

## 4. Minimal if short time

- [x] Spec 009
- [ ] Spec 011
- [ ] Spec 012

## 5. Rule for team

Do not run full ablation until config exists in `configs/ablation_configs.yaml` and benchmark/corpus contracts are locked.
