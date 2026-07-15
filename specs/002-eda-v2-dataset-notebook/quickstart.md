# Quickstart: EDA Notebook for Dataset v2

Validation guide for running the planned EDA notebook end-to-end after implementation. This is **not** the implementation itself — see [`plan.md`](plan.md), [`data-model.md`](data-model.md), and [`research.md`](research.md) for design. Task breakdown belongs in `tasks.md` (via `/speckit-tasks`).

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ kernel | Same env as the rest of `src/` |
| Packages | `pandas`, `matplotlib`, `numpy`, `ipykernel` / Jupyter (already used in-repo; no new viz stack) |
| Dataset on disk | `data/v2/` built by `scripts/build_dataset_v2.py` / `scripts/finalize_dataset.py` |
| Raw inputs for reconciliation | `data/untracked_data/metadata.jsonl`, `data/untracked_data/relationships.jsonl` |
| Working directory | Project root **or** `notebooks/` (root resolution is automatic, FR-013) |

### Expected `data/v2/` artifacts (preflight)

```text
data/v2/
  documents.jsonl
  documents_quarantine.jsonl
  edges.jsonl
  edges_quarantine.jsonl
  external_stubs.jsonl
  text_provenance.jsonl
  provisions.jsonl          # multi-GB — stream/sample only
  chunks.jsonl              # ~2.6 GB — stream/sample only
  validity_timeline.jsonl
  authority_index.jsonl
  reconciliation_report.md
  vocabularies/*.json
```

If any file is missing, the notebook preflight cell must list it and skip only dependent sections (FR-001, FR-014).

## Setup (once)

From project root:

```powershell
# Optional: confirm deps
python -c "import pandas, matplotlib, numpy; print(pandas.__version__, matplotlib.__version__, numpy.__version__)"

# Unit tests for the extracted module (after implementation)
python -m pytest tests/eda/ -q
```

Open the notebook:

- VS Code / Cursor: open [`notebooks/eda_v2_dataset.ipynb`](../../notebooks/eda_v2_dataset.ipynb) and select the project Python kernel.
- Or Jupyter: `jupyter notebook notebooks/eda_v2_dataset.ipynb` (from project root).

No install step is required beyond the existing environment unless those packages are missing.

## Config cell (top of notebook)

Set these near the top; do not hardcode them deeper in the notebook (FR-012):

| Parameter | Default (suggested) | Purpose |
| --- | --- | --- |
| `DATASET_ROOT` | `{project_root}/data/v2` | Override if data lives elsewhere |
| `UNTRACKED_ROOT` | `{project_root}/data/untracked_data` | Raw metadata / relationships for FR-008 |
| `SAMPLE_SIZE` | `5000` | Reservoir sample size for large-file inspection |
| `SAMPLE_SEED` | `42` | Fixed seed for reproducible samples |
| `STREAM_SIZE_THRESHOLD_BYTES` | e.g. `50 * 1024 * 1024` | Files larger than this always stream |

Project root is resolved via `resolve_project_root()` (same idea as the FAISS notebook: use cwd if `src/` exists, else parent).

## Run order (top to bottom)

1. **Environment + path** — put `src/` on `sys.path`, resolve project root.
2. **Config** — parameters above.
3. **Preflight** — `preflight(project_root)` → present/missing table (FR-001).
4. **Documents** — row count + distributions (FR-003).
5. **Edges** — counts + `rel_*` / `direction_verified` / `external_target` (FR-004).
6. **Text / structure** — `text_provenance`; stream/sample `provisions` + `chunks` (FR-005). State sample method + size in output.
7. **Validity timeline** — event counts; label `direction_verified=false` as pending sign-off (FR-006).
8. **Authority index** — full mapping table; flag unranked `loai_van_ban` (FR-007).
9. **Reconciliation** — recompute documents/edges identities vs report (FR-008).
10. **Quality drilldown** — quarantine tags, text_status / html flags, external stubs, vocab coverage (FR-009–FR-011).

Stop only if preflight shows critical files missing; otherwise incomplete sections should flag and continue.

## Validation scenarios

### V1 — Happy path (full corpus)

**Given** `data/v2/` and `data/untracked_data/` as produced by the pipeline.

**When** all cells run in order.

**Then**:

| Check | Expected |
| --- | --- |
| SC-001 | No unhandled exception; notebook completes top to bottom |
| SC-003 | `chunks.jsonl` / `provisions.jsonl` never fully loaded (module uses line stream + reservoir sample) |
| SC-004 | Every required artifact has at least one summary table or plot |
| Documents / edges totals | Align with report: **151,624** docs final, **883,256** edges final (or notebook flags delta) |
| Sample metadata | Chunk/provision sample cells print `seed`, `sample_size`, `rows_seen` |

Approximate reference counts from current [`data/v2/reconciliation_report.md`](../../data/v2/reconciliation_report.md):

```text
documents: 153,420 raw == 151,624 final + 1,796 quarantine
edges:     897,890 raw == 883,256 final + 14,634 quarantine
provisions_final: 1,386,267
chunks_final:     1,513,376
validity_events:  159,805 (34,379 verified / 125,426 unverified)
external_stubs:   19,763
```

### V2 — Reconciliation identity (US2 / SC-002)

**When** the reconciliation section runs.

**Then** for both documents and edges:

1. Recomputed `raw_count == final_count + quarantine_count` → `identity_holds` true/false.
2. Parsed report numbers compared → `matches_report` true/false.
3. Any mismatch printed with both recomputed and report triples (never silent).

Expected on a clean build: both identities **PASS** and **match report**.

### V3 — Quality drilldown (US3 / SC-005)

**When** the quality section runs.

**Then**:

- Ranked `exclusion_reasons` / edge quality tags with **row_count** separate from **tag_counts** (no double-counting rows).
- `text_status` and `html_quality_flags` counts/percentages.
- External stubs: distinct `id_str` count + `referenced_by_edge_count` distribution.
- Per facet (`issuing_authority`, `legal_field`, `sector`, `scope`): exact UNMAPPED/MISSING % (SC-005).

### V4 — Partial / missing data (edge case)

**Given** one optional or section-specific file renamed/removed (e.g. temporarily hide `authority_index.jsonl`).

**When** notebook is re-run.

**Then**:

- Preflight lists the missing path.
- Dependent section is skipped/flagged.
- Other sections still complete (FR-014).

### V5 — Unit tests (module only)

```powershell
python -m pytest tests/eda/test_dataset_v2.py -q
```

**Then** synthetic fixtures cover at least:

- streaming counts + malformed-line skip count  
- reservoir sample determinism for a fixed seed  
- reconciliation PASS/FAIL  
- multi-tag tally (row vs tag accounting)  
- `coerce_category` for `None` / `"MISSING"` / `"UNMAPPED"`  

Do **not** point unit tests at the real multi-GB corpus.

## Runtime expectations

| Section | I/O character | Memory note |
| --- | --- | --- |
| documents, edges, provenance, validity, authority, quarantine, stubs | Full stream or small full load | Fine in tens–hundreds of MB |
| provisions / chunks aggregation | Full line stream once | Counters only — tens of MB peak |
| provisions / chunks examples | Reservoir sample | `SAMPLE_SIZE` rows only |

Large-file cells will be I/O-bound and slower than typical lightweight EDA; that is acceptable (spec Assumptions).

## Out of scope (do not expect in this notebook)

- Building or mutating `data/v2/`
- FAISS / vector retrieval EDA ([`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb))
- Knowledge-graph construction or evaluation
- New plotting libraries beyond `matplotlib`/`pandas`

## After implementation — acceptance checklist

- [ ] `pytest tests/eda/` green  
- [ ] Notebook runs from project root  
- [ ] Notebook runs from `notebooks/`  
- [ ] Preflight reports missing files without crashing  
- [ ] Reconciliation matches report or flags deltas  
- [ ] Chunk/provision cells document sampling method + size + seed  
- [ ] Sampled chunk/provision displays include resolvable `id_str` / citation (not bare ids only)  
- [ ] `direction_verified=false` labeled pending sign-off, not production-ready  
- [ ] Every plot paired with a table (Vietnamese label fallback)  

## Next step

Break this plan into implementation tasks:

```text
/speckit-tasks
```

(or the project’s equivalent Speckit tasks command targeting `specs/002-eda-v2-dataset-notebook`).
