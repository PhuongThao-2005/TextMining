# Feature Specification: EDA Notebook for Dataset v2

**Feature Branch**: `002-eda-v2-dataset-notebook`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "Build a notebook for EDA the v2 dataset"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a full-corpus statistical overview across all v2 layers (Priority: P1)

A project member (dataset owner, retrieval/graph engineer, or reviewer) opens one notebook and runs it top to bottom to understand the shape and quality of the `data/v2/` dataset: how many documents/edges/provisions/chunks exist, how they are distributed across authority rank, validity, document type, time, and text-quality dimensions, without writing ad-hoc analysis code and without crashing on the multi-gigabyte structured-layer files.

**Why this priority**: Nobody downstream (retrieval, graph, benchmark) can trust or reason about `data/v2/` without a documented picture of its composition. This is the deliverable with the most immediate value and is a prerequisite for the other stories.

**Independent Test**: Open the notebook with `data/v2/` and `data/untracked_data/` populated, run all cells sequentially, and confirm summary tables/plots are produced for documents, edges, text/structure (provisions, chunks, text_provenance), validity timeline, and authority index, with no unhandled exception and no attempt to load `chunks.jsonl` or `provisions.jsonl` fully into memory.

**Acceptance Scenarios**:

1. **Given** `data/v2/documents.jsonl`, `data/v2/edges.jsonl`, `data/v2/text_provenance.jsonl`, `data/v2/validity_timeline.jsonl`, and `data/v2/authority_index.jsonl` exist, **When** the user runs all notebook cells in order, **Then** the notebook displays row counts, key distributions (e.g. `legal_authority_rank`, `validity_group`, `currency_hint`, `text_status`, `event_type`), and at least one time-based view (documents per `issue_year`) for each layer.
2. **Given** `data/v2/chunks.jsonl` (~2.7 GB) and `data/v2/provisions.jsonl` (multi-GB), **When** the notebook computes chunk-count/provision-count statistics, **Then** it does so via a streaming or sampled read (not a single in-memory `json.load`/`pandas.read_json` over the whole file) and still reports total row counts and key field distributions.
3. **Given** the required v2 files are missing or partially generated, **When** the user runs the preflight cell, **Then** the notebook clearly reports which `data/v2/` files are missing before attempting any analysis.

---

### User Story 2 - Validate v2 outputs against the reconciliation report (Priority: P2)

A project member wants confidence that the dataset currently on disk matches the guarantees documented in `data/v2/reconciliation_report.md` (e.g. `documents: raw == final + quarantine`, `edges: raw == final + quarantine`), so that after any pipeline re-run they can quickly spot a regression instead of trusting a static markdown report that may be stale.

**Why this priority**: The reconciliation identities are the dataset's core correctness contract (Dataset_SPEC_v2 §10). Recomputing them directly from the JSONL files, independent of the checked-in report, is the highest-value quality gate after the overview itself.

**Independent Test**: Run the notebook's reconciliation section and confirm it independently recomputes `len(documents_final) + len(documents_quarantine) == len(metadata_raw)` (and the equivalent identity for edges), then compares the recomputed numbers to the ones printed in `reconciliation_report.md`, flagging any mismatch.

**Acceptance Scenarios**:

1. **Given** `data/v2/documents.jsonl`, `data/v2/documents_quarantine.jsonl`, and `data/untracked_data/metadata.jsonl`, **When** the reconciliation cell runs, **Then** the notebook reports the three counts and whether the identity holds, matching the numbers in `reconciliation_report.md` (151,624 + 1,796 = 153,420).
2. **Given** the same pattern for `edges.jsonl` / `edges_quarantine.jsonl` / `relationships.jsonl`, **When** the reconciliation cell runs, **Then** the notebook reports the recomputed identity and any delta from the documented 883,256 + 14,634 = 897,890.
3. **Given** `validity_timeline.jsonl` events carry a `direction_verified` flag, **When** the notebook summarizes the timeline, **Then** it explicitly reports the verified/unverified split (matching the documented 34,379 verified / 125,426 unverified) and labels the unverified majority as not production-ready per the pending sign-off noted in the report.

---

### User Story 3 - Drill into specific data-quality issues (Priority: P3)

A project member wants to identify concrete, actionable quality gaps — missing/short text, unmapped controlled-vocabulary values, quarantine reasons, and external-stub exposure — so the team can prioritize what to fix before the dataset feeds retrieval or graph construction.

**Why this priority**: The overview (P1) shows *that* there are gaps (e.g. `text_missing`, `UNMAPPED`); this story is about surfacing *which* records and *why*, which is what turns EDA into an actionable backlog rather than just descriptive statistics.

**Independent Test**: Run the notebook's data-quality section and confirm it lists the top quarantine reasons with counts for both documents and edges, the count/percentage of documents with `text_status` in `{missing, empty, too_short, extraction_failed}`, and the count/percentage of controlled-vocabulary fields (`issuing_authority`, `legal_field`, `sector`, `scope`) with `code == "UNMAPPED"` or `"MISSING"`.

**Acceptance Scenarios**:

1. **Given** `data/v2/documents_quarantine.jsonl` and `data/v2/edges_quarantine.jsonl`, **When** the quality-drilldown cell runs, **Then** the notebook shows a ranked breakdown of `exclusion_reasons` (documents) and `edge_quality_flags` (edges) by frequency, honoring the "reasons are tags, rows are authoritative" multi-tag accounting rule from Dataset_SPEC_v2 §9.
2. **Given** `data/v2/text_provenance.jsonl`, **When** the quality-drilldown cell runs, **Then** the notebook reports the count and percentage of documents per `text_status` value and per `html_quality_flags` value.
3. **Given** `data/v2/external_stubs.jsonl`, **When** the quality-drilldown cell runs, **Then** the notebook reports how many distinct `id_str`s are external stubs (`citation_safe=false`) and the distribution of `referenced_by_edge_count`, so reviewers see how much of the graph touches non-citable placeholder nodes.

### Edge Cases

- What happens when the notebook tries to fully load `data/v2/chunks.jsonl` (~2.7 GB) or `data/v2/provisions.jsonl` (confirmed too large for a single string/read) into memory at once? The notebook MUST avoid this by design (streaming line-by-line aggregation and/or reservoir/random sampling for any per-record inspection), and MUST state the sampling method and sample size wherever full-corpus statistics are not computed.
- How does the notebook handle records with `null` or `"MISSING"`/`"UNMAPPED"` values in controlled-vocabulary or date fields (e.g. `ngay_het_hieu_luc_iso: null`, `issuing_authority.code: "MISSING"`)? It MUST count and display these as an explicit category rather than dropping the rows silently or letting them crash a groupby/plot.
- How does the notebook handle the large number of distinct `id_str` values (151k+ documents)? It MUST NOT attempt to plot or tabulate raw `id_str` cardinality directly; only aggregated/binned views are acceptable.
- What happens when required `data/v2/` or `data/untracked_data/` files are missing (e.g. dataset not yet built, or `content.jsonl` absent)? The preflight step MUST detect and report exactly which files are missing and skip only the sections that depend on them, rather than failing the entire run.
- How does the notebook present Vietnamese-language category labels (document types, legal fields, scopes) in tables/plots? It MUST render them correctly (UTF-8) and MUST NOT require a specific non-default font to avoid missing-glyph/tofu-box rendering, falling back to a table view if plotting Vietnamese labels is unreliable in the environment.
- What happens when the `validity_timeline.jsonl` counts don't match the checked-in `reconciliation_report.md` (e.g. after a partial re-run)? The notebook MUST report the discrepancy explicitly rather than silently trusting either source.
- How does the notebook handle the `vocabularies/*.json` mapping files being absent or incomplete relative to what's referenced in `documents.jsonl`? It MUST report unmapped-but-referenced codes rather than failing the join silently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The notebook MUST verify, in an early "preflight" step, that the expected `data/v2/` artifacts (`documents.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `text_provenance.jsonl`, `validity_timeline.jsonl`, `authority_index.jsonl`, `documents_quarantine.jsonl`, `edges_quarantine.jsonl`, `reconciliation_report.md`, and `vocabularies/*.json`) exist, and report exactly which are present/missing before running any analysis that depends on them.
- **FR-002**: The notebook MUST read large files (`chunks.jsonl`, `provisions.jsonl`, and any file over a configurable size threshold) via a streaming, line-by-line, or chunked approach for full-corpus counts/aggregates, and MUST use explicit random or systematic sampling (with a configurable sample size and fixed seed) for any analysis that inspects individual record content (e.g. chunk-text length distribution, example rows).
- **FR-003**: The notebook MUST report, for `documents.jsonl`, at minimum: total row count, distribution of `legal_authority_rank`, `loai_van_ban`, `validity_group`, `currency_hint`, `scope.code`, `legal_field.code`, `issuing_authority.code`, and a per-`issue_year` histogram.
- **FR-004**: The notebook MUST report, for `edges.jsonl`, at minimum: total row count, distribution of `rel_canonical`/`rel_group`, the proportion with `direction_verified = true` vs `false`, and the proportion with `external_target = true`.
- **FR-005**: The notebook MUST report, for the text/structure layer (`text_provenance.jsonl`, `provisions.jsonl`, `chunks.jsonl`), at minimum: `text_status` distribution, `content_row_count` distribution, `structuring_status` distribution, provisions-per-document and chunks-per-provision summary statistics (mean/median/percentiles), and a sampled `chunk_text` character-length / token-estimate distribution.
- **FR-006**: The notebook MUST report, for `validity_timeline.jsonl`, at minimum: total event count, `event_type` distribution, and the `direction_verified` true/false split, explicitly labeling the `direction_verified = false` share as pending sign-off (Dataset_SPEC_v2 §8.2, reconciliation report P1) rather than treating it as production-ready.
- **FR-007**: The notebook MUST report, for `authority_index.jsonl`, the full `loai_van_ban → legal_authority_rank` mapping table and cross-check that every distinct `loai_van_ban` value observed in `documents.jsonl` resolves to a rank (flagging any that fall back to `99`/unranked).
- **FR-008**: The notebook MUST independently recompute the reconciliation identities documented in `data/v2/reconciliation_report.md` — `documents: raw == final + quarantine` and `edges: raw == final + quarantine` — directly from the JSONL files (`data/untracked_data/metadata.jsonl`, `data/untracked_data/relationships.jsonl`, plus the v2 final/quarantine files) and report PASS/FAIL for each, alongside the numbers currently checked into the report.
- **FR-009**: The notebook MUST report a ranked breakdown (count and percentage) of `exclusion_reasons` for `documents_quarantine.jsonl` and `edge_quality_flags`/`exclusion_reasons` for `edges_quarantine.jsonl`, treating each row as potentially carrying multiple reason tags (no double counting of rows, but reasons tallied independently).
- **FR-010**: The notebook MUST report external-stub exposure: total distinct `id_str` values in `external_stubs.jsonl`, and the distribution of `referenced_by_edge_count`.
- **FR-011**: The notebook MUST report controlled-vocabulary coverage: for each of `issuing_authority`, `legal_field`, `sector`, `scope`, the count/percentage of documents whose `code` is `"UNMAPPED"` or `"MISSING"` versus successfully mapped.
- **FR-012**: The notebook MUST allow the user to configure, near the top of the notebook, the dataset root path, the sampling size/seed used for large-file record-level inspection, and a size threshold above which a file is read in streaming mode instead of loaded whole — without requiring edits elsewhere in the notebook.
- **FR-013**: The notebook MUST work when run from either the project root or the `notebooks/` directory, resolving `data/` paths relative to the detected project root.
- **FR-014**: The notebook MUST NOT crash the whole run when one section's required file is missing or a given record fails to parse (e.g. malformed JSON line); it MUST skip/flag that section or record and continue with the remaining analysis, reporting how many records were skipped.
- **FR-015**: The notebook MUST render all counts/distributions in tables and/or plots with human-readable labels (not raw codes alone, where a `surface`/label is available) and MUST NOT plot high-cardinality identifier fields (e.g. raw `id_str`, `edge_id`, `chunk_id`) directly.

### Key Entities *(include if feature involves data)*

- **Document record** (`data/v2/documents.jsonl`, `data/v2/documents_quarantine.jsonl`): One row per legal document with normalized fields — `id_str`, `legal_authority_rank`, `validity_group`, `currency_hint`, controlled-vocab facets (`issuing_authority`, `legal_field`, `sector`, `scope`), dates, and (for quarantined rows) `exclusion_reasons`.
- **Edge record** (`data/v2/edges.jsonl`, `data/v2/edges_quarantine.jsonl`): One directed relationship between two documents — `src_id`, `dst_id`, `rel_canonical`, `rel_group`, `direction_verified`, `external_target`, and (for quarantined rows) `exclusion_reasons`.
- **Text provenance record** (`data/v2/text_provenance.jsonl`): One row per document describing text extraction outcome — `content_row_count`, `text_status`, `extracted_char_count`, `structuring_status`, `chunk_count`.
- **Provision record** (`data/v2/provisions.jsonl`): One row per legal citation unit (Điều/khoản) — `unit_id`, `id_str`, `unit_type`, `chunk_count`, `coverage_verified`. Very large file; analyzed via streaming/sampling only.
- **Chunk record** (`data/v2/chunks.jsonl`): One row per embeddable slice — `chunk_id`, `parent_unit_id`, `id_str`, `chunk_text`, `chunk_char_count`. ~2.7 GB file; analyzed via streaming/sampling only.
- **Validity event** (`data/v2/validity_timeline.jsonl`): One row per validity-affecting event — `id_str`, `event_type`, `event_date_iso`, `source_edge_id`, `direction_verified`.
- **Authority index entry** (`data/v2/authority_index.jsonl`): One row per document-type-to-rank mapping — `loai_van_ban`, `legal_authority_rank`.
- **External stub** (`data/v2/external_stubs.jsonl`): One row per referenced-but-missing document — `id_str`, `citation_safe`, `referenced_by_edge_count`.
- **Reconciliation report** (`data/v2/reconciliation_report.md`): The checked-in ground-truth counts and identity checks the notebook cross-validates against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with `data/v2/` populated can run the entire notebook top to bottom in one sitting without manual code edits and without any cell raising an unhandled exception, including the sections touching `chunks.jsonl` and `provisions.jsonl`.
- **SC-002**: The notebook's recomputed reconciliation identities (documents and edges, `raw == final + quarantine`) match the numbers in `data/v2/reconciliation_report.md` exactly, or the notebook clearly flags the specific discrepancy.
- **SC-003**: The notebook completes its full run (including streaming passes over the ~2.7 GB `chunks.jsonl` and the multi-GB `provisions.jsonl`) without loading either file fully into memory, verified by the notebook using chunked/line-based reads rather than a single whole-file parse call for those two files.
- **SC-004**: 100% of the eight required v2 artifacts plus the reconciliation report are covered by at least one summary table or plot in the notebook.
- **SC-005**: For each controlled-vocabulary facet (`issuing_authority`, `legal_field`, `sector`, `scope`), the notebook reports an exact UNMAPPED/MISSING percentage a reviewer can act on without opening the raw JSONL files.

## Assumptions

- The v2 dataset has already been built by the existing pipeline (`scripts/build_dataset_v2.py`, `scripts/finalize_dataset.py`) and is assumed current under `data/v2/`; this notebook performs exploratory analysis and validation, it does not rebuild or mutate any dataset artifact.
- This notebook is read-only with respect to `data/v2/` and `data/untracked_data/`: it never writes back to these source files. Any derived summary output (tables, charts, an optional exported report) is written elsewhere (e.g. `notebooks/` output cells or a separate report file), not into `data/v2/`.
- "EDA" is scoped to descriptive statistics, distributions, and reconciliation/quality checks across the four dataset layers described in `docs/spec/SPEC_Dataset_v2.md`; it does not include building or evaluating the vector index (covered by `notebooks/faiss_retrieval_ready.ipynb` / spec `001-faiss-retrieval-notebook`) or the knowledge graph.
- Users run the notebook locally with enough disk I/O throughput to stream multi-gigabyte JSONL files; the notebook is expected to take longer to run on the large-file sections than a typical lightweight EDA notebook, and this is acceptable given the corpus size.
- The `direction_verified = false` majority in `validity_timeline.jsonl` and the corresponding `edges.jsonl` groups are a known, pre-existing, pending-sign-off condition (per `reconciliation_report.md` and Dataset_SPEC_v2 §8.2) — the notebook surfaces this clearly but does not attempt to resolve it.
- Plotting/visualization uses whatever plotting library is already available in the project's environment (e.g. `matplotlib`/`pandas` plotting); no new heavyweight visualization dependency is assumed necessary unless the implementer determines otherwise during planning.
