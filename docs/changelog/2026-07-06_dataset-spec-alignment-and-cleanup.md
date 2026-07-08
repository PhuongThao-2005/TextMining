# 2026-07-06 — Dataset_SPEC alignment, handoff cleanup, and spec misalignment report

| Field | Value |
| --- | --- |
| Date | 2026-07-06 |
| Author | Dataset preprocessing owner |
| Area | Dataset finalization stage; cross-team spec alignment |
| Related output | [`report.md`](../../report.md) |

## Goal

Verify that `Dataset_SPEC.md` matches the actual finalized dataset in `data/finalized/`, correct any drift, retire the stale handoff document, and produce a decision-oriented report on how the three teammate specs (Knowledge Graph, Text Structuring, Vector Retrieval) align with the dataset as it exists today.

## What was done

### 1. Verified Dataset_SPEC.md against the real data
Checked every headline claim by recomputing from the actual JSONL files (not from the generated `preprocessing_report.md`):
- Row counts, tier split, validity groups, document-type counts — all reconcile.
- All 17 raw→canonical relationship labels tallied across the full 883,256 rows — sum matches exactly.
- Field lists dumped from `metadata_final.jsonl` / `relationships_final.jsonl` / `metadata_external_stubs.jsonl` — match §7.
- `edge_keep_status = kept` confirmed for 100% of final relationship rows.

Conclusion: the numbers were correct; the drift was in paths, unexplained discrepancies, and missing/overstated handoff facts.

### 2. Fixed `Dataset_SPEC.md`
- **Paths:** replaced the `Road2AI_ApplePie/data/...` prefix with the project-real `data/...`; added a path-convention note (script constants still point at the old prefix — flagged, not changed).
- **No-text scope note:** documented that the finalized package is metadata + relationships only, with no document body text (top of doc and §8.1).
- **Authoritative raw→canonical table (new §6.2.1):** added the 17-row mapping taken from the actual data, including the direction caveat for the `validity` group.
- **Quarantine reason reconciliations (§5.4, §6.3):** explained that reason tags (1,799 metadata / 14,740 relationship) exceed row counts (1,796 / 14,634) because of multi-tagged rows; listed the extra possible reasons that fired 0 times.
- **External-stub reconciliation (§6.4):** related the 19,763 unique missing-target IDs, 57,120 kept `external_target` edges, and 57,790 raw missing-target edges.
- **`*_canonical` honesty note (§7.1):** documented that only `loai_van_ban_canonical` uses a real map; the other `*_canonical` fields are whitespace/Unicode-cleaned only.
- **`quality_flags` naming pin (§7.1):** fixed the convention (`quality_flags` = metadata, `structuring_quality_flags` = structuring, never `quality_flags_document`).

### 3. Removed `Retrieval_Handoff.md`
Deleted as stale: it stated a vector-input contract (`metadata_final.jsonl` + full text) that conflicts with `SPEC_Vector_Retrieval.md` (`chunks.jsonl`), and duplicated field lists now owned authoritatively by `Dataset_SPEC.md` and the `SPEC_*` files.

### 4. Analyzed teammate specs vs. the dataset and wrote `report.md`
Created [`report.md`](../../report.md) with a concrete showcase (real data rows) for each problem:
- **P1 🔴** Knowledge Graph validity mapping is the inverse of the data (~125k edges at stake); direction unresolved.
- **P2 🟠** All three specs depend on full text / chunks that don't exist yet.
- **P3 🟠** `quality_flags` naming conflict across specs.
- **P4 🟡** `*_canonical` fields not truly canonicalized but used as exact-match facets.
- **P5 🟡** Wrong path prefix in spec and script.
- **P6 🟡** Quarantine reason counts don't reconcile to row counts (multi-tagged rows).
- **P7 🟡** External-stub numbers look contradictory (unique IDs vs edges vs raw edges).
- **P8 🟡** Stale `Retrieval_Handoff.md`.

## Key finding (highest priority)

The pipeline maps `Văn bản hết hiệu lực → expires_or_replaces` (61,227) and `Văn bản quy định hết hiệu lực → expired_or_replaced_by` (49,995). This is the **inverse** of [`SPEC_Knowledge Graph.md`](../../SPEC_Knowledge%20Graph.md) §6.1, and the label direction itself reads backwards relative to the Vietnamese wording. Must be confirmed against a known real document pair before the graph team builds validity edges.

## Files touched

| File | Change |
| --- | --- |
| `Dataset_SPEC.md` | Corrected (paths, scope note, §6.2.1 mapping table, §5.4/§6.3/§6.4 reconciliations, §7.1 notes, §8.1 text-source note) |
| `Retrieval_Handoff.md` | Deleted |
| `report.md` | Created (detailed misalignment report with showcases) |
| `docs/changelog/2026-07-06_dataset-spec-alignment-and-cleanup.md` | Created (this entry) |
| teammate specs / data files | Not modified — misalignments reported for decision |

## Open decisions requested

1. **P1** — confirm the `expires_or_replaces` / `expired_or_replaced_by` direction against a real known document pair.
2. **P2** — decide the document full-text source (blocks text structuring → vector + structural graph).
3. **P3** — approve the `quality_flags` naming convention so the text-structuring spec can be corrected at source.
4. **P4** — add a canonicalization pass or relax the specs to fuzzy facets.
5. **P5** — approve the two-line path fix in `scripts/finalize_dataset.py`.
