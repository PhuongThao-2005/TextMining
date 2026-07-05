# SPEC_Knowledge_Graph.md

## 1. Purpose

This document specifies the graph construction stage for the G-LRAG pipeline.

The stage assembles the finalized outputs of two upstream pipelines into a Neo4j graph:

```text
metadata_final.jsonl + relationships_final.jsonl                    -> Document graph
documents_structured.jsonl + legal_units.jsonl + chunks.jsonl        -> Structural graph
```

This stage does not re-derive facts already computed upstream. `validity_group`, `dataset_tier`, `structuring_status`, and all structural node/edge names are consumed as-is from `Dataset_SPEC.md` and `SPEC_Text_Structuring.md`. The graph exists to support multi-hop legal-basis reasoning, temporal-validity lineage, and graph-guided filtering for vector retrieval, per `SPEC.md` §4.6-§6.8, and directly serves two measurable success criteria from `SPEC.md` §3: hallucination rate under 10% and average response latency under 1 minute.

`SPEC.md` §4.6/§6.7 describes graph construction in general terms as extracting "entities, concepts, and relationships." Given the currently finalized data, this spec scopes the graph to **document-level relationships and document-internal structure only** — free-standing entity/concept extraction (e.g. named legal terms, defined concepts inside article text) is out of scope until a dedicated extraction pipeline and dataset exist. This is a scope note for the team, not a silent limitation (see §11).

## 2. Core Requirements

- Ingest every kept record from `metadata_final.jsonl` and `metadata_external_stubs.jsonl` as `Document` nodes.
- Never ingest `metadata_quarantine.jsonl` or `relationships_quarantine.jsonl`.
- Ingest every row of `relationships_final.jsonl` as one independent directed edge; do not infer, flip, merge, or drop rows based on assumed symmetry with an inverse-labeled pair.
- Treat `(doc_id_str, other_doc_id_str, relationship_canonical)` as a full triple key — a single document pair may hold more than one relationship type.
- Attach `documents_structured.jsonl` tracking fields (`structuring_status`, `parse_confidence`, `coverage_ratio`, unit/chunk counts) to the corresponding `Document` node, so a document's structural health is visible without a separate lookup.
- Reuse `LegalUnit` and `Chunk` node names and structural edge names (`DOCUMENT_HAS_UNIT`, `UNIT_HAS_CHUNK`, `CHUNK_NEXT`, `UNIT_NEXT`) exactly as defined in `SPEC_Text_Structuring.md`; do not introduce a competing hierarchy.
- Do not copy full chunk content (`chunk_text`, `retrieval_text`) into the graph — `Chunk` nodes are pointers only, resolved against the vector store when content is needed.
- Do not duplicate `Document`-level metadata fields onto `LegalUnit`/`Chunk` nodes. The flat `legal_units.jsonl`/`chunks.jsonl` files denormalize document metadata onto every row because they have no join mechanism; Neo4j does not need this — traverse `DOCUMENT_HAS_UNIT`/`UNIT_HAS_CHUNK` back to `Document` instead.
- Mark every `ExternalStub` node non-citable (`citation_safe = false`) and exclude it from any evidence path by default.
- Verify the direction convention of `relationship_canonical` against real examples before production use (§6); do not assume it from the field name alone.
- When a graph-guided filter returns an empty `id_str` set, surface this explicitly to the caller rather than silently returning no filter — this maps to `SPEC.md` §5.6's requirement to notify the user when no relevant information is found, rather than degrading to an unfiltered (and therefore less reliable) query.

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `metadata_final.jsonl` | `Document` nodes |
| `metadata_external_stubs.jsonl` | `Document:ExternalStub` nodes |
| `relationships_final.jsonl` | Cross-document edges |
| `documents_structured.jsonl` | Structural tracking fields merged onto `Document` nodes |
| `legal_units.jsonl` | `LegalUnit` nodes |
| `chunks.jsonl` | `Chunk` nodes (pointer fields only) |

Join `Document` to `LegalUnit`/`Chunk` by `id_str` / `doc_id`, matching the join keys already used in `SPEC_Text_Structuring.md`.

### Outputs

Recommended output location: Neo4j graph database instance, plus a build report.

| Output | Purpose |
| --- | --- |
| Neo4j graph (`Document`, `ExternalStub`, `LegalUnit`, `Chunk` nodes + edges) | Queryable graph for retrieval |
| `graph_build_report.md` | Node/edge counts, reconciliation checks, warnings |

## 4. Graph Model

### 4.1 Node Labels

| Label | Meaning |
| --- | --- |
| `Document` | A finalized legal document record, enriched with structuring status |
| `Document:ExternalStub` | A relationship target with no metadata record; non-citable placeholder |
| `LegalUnit` | A structural unit inside a document (`article`, `preamble`, `section`, `item`, `attachment_preamble`, `document`), verbatim from `SPEC_Text_Structuring.md` §4 |
| `Chunk` | A retrieval chunk, pointer-only, verbatim key fields from `SPEC_Text_Structuring.md` §5 |

### 4.2 Structural Edge Types (verbatim from `SPEC_Text_Structuring.md` §8)

| Edge | Meaning |
| --- | --- |
| `DOCUMENT_HAS_UNIT` | Document contains legal unit |
| `UNIT_HAS_CHUNK` | Legal unit contains chunk |
| `CHUNK_NEXT` | Next chunk in the same legal unit |
| `UNIT_NEXT` | Next legal unit in the same document |

### 4.3 Cross-Document Edge Types

17 types, one per `relationship_canonical` value, converted mechanically to `UPPER_SNAKE_CASE` (`based_on` → `BASED_ON`, etc.). No canonical label is merged, split, or dropped. Full mapping and group table in §6.

### 4.4 Fallback / Exclusion Rules

- If a relationship's target `id_str` is not found in `metadata_final.jsonl`, the target must already exist as an `ExternalStub` (per `Dataset_SPEC.md` §6.4) — the edge is still created, but the target node carries `citation_safe = false`.
- If a `Document` has `structuring_status` in (`missing_full_text`, `empty_text`, `text_too_short`, `parse_error`), it will have zero `LegalUnit` children — the `Document` node must still be created from `metadata_final.jsonl` alone. Absence of structural children must never block Document-level graph construction, since Document-level relationships (`BASED_ON`, `GUIDES_OR_DETAILS`, etc.) are independent of text-structuring success.
- Structural drill-down queries (§8) must check `structuring_status` before assuming `LegalUnit`/`Chunk` children exist, and fall back to Document-level evidence only when they do not.

## 5. Required Schemas

### Document Node

Core fields copied as-is from `Dataset_SPEC.md` §7.1:

```text
id_str, title_clean, citation_label
loai_van_ban_canonical, so_ky_hieu_clean
co_quan_ban_hanh_canonical
ngay_ban_hanh_iso, ngay_co_hieu_luc_iso, ngay_het_hieu_luc_iso
issue_year, tinh_trang_hieu_luc_canonical, validity_group
dataset_tier
pham_vi_canonical, nganh_canonical, linh_vuc_canonical
quality_flags
```

Additional fields merged from `documents_structured.jsonl` (per `SPEC_Text_Structuring.md` §5, Document Record):

```text
structuring_status, parse_confidence, coverage_ratio, reconstruction_exact
legal_unit_count, article_count, chunk_count, text_char_count
```

**Naming conflict to resolve with the text-structuring team:** `Dataset_SPEC.md` §7.1 names the metadata-level quality field `quality_flags`, while `SPEC_Text_Structuring.md` §5 refers to the same field as `quality_flags_document` when listing it among fields every legal unit/chunk must preserve, and *separately* defines its own structuring-stage `quality_flags` on the Document Record (parse errors, coverage issues, etc.). These are two different concepts sharing overlapping names across specs. This graph spec resolves it by storing them under two distinct properties:

```text
Document.quality_flags              // from metadata_final.jsonl (Dataset_SPEC.md §7.1)
Document.structuring_quality_flags  // from documents_structured.jsonl (SPEC_Text_Structuring.md §5)
```

This is a naming inconsistency in the source specs, not something this graph spec can silently paper over — flag it to both teams so `documents_structured.jsonl`'s field is unambiguously identified going forward.

### ExternalStub Node

Copied as-is from `Dataset_SPEC.md` §7.3:

```text
id_str, is_external_stub, missing_metadata
citation_safe, dataset_tier, source, quality_flags
```

### LegalUnit Node

Copied as-is from `SPEC_Text_Structuring.md` §5, excluding full-text fields and excluding the denormalized document-metadata fields (per §2 — resolved via graph traversal instead):

```text
unit_id, doc_id, id_str
unit_type, unit_index, unit_number
unit_heading, unit_title
article_number, article_title, section_path
unit_char_count, unit_token_estimate, chunk_count
parse_confidence, quality_flags
```

`raw_unit_text`, `unit_text`, `full_text`, `retrieval_text` are excluded — content stays in `legal_units.jsonl` / the vector store.

### Chunk Node

Pointer subset of `SPEC_Text_Structuring.md` §5, same exclusion policy as above:

```text
chunk_id, parent_unit_id, doc_id, id_str
unit_type, article_number, section_path
chunk_index_in_unit, chunk_index_global
citation_anchor, structure_level, article_detected
quality_flags
```

`chunk_text` and `retrieval_text` are excluded (§2).

### Cross-Document Edge Record

```text
(doc_id_str) -[:RELATIONSHIP_CANONICAL_UPPER]-> (other_doc_id_str)
  relationship_raw, relationship_group
  external_target, source_in_metadata, target_in_metadata
  edge_quality_flags
```

## 6. Relationship Extraction & Edge Policy

### 6.1 Raw-to-Canonical Mapping

`relationships_final.jsonl` maps 17 raw Vietnamese labels to 17 `relationship_canonical` values, one-to-one, no collapsing:

| Raw label | `relationship_canonical` | `relationship_group` | Inverse pair | Count |
| --- | --- | --- | --- | ---: |
| Văn bản căn cứ | `based_on` | `basis` | — | 578,736 |
| Văn bản dẫn chiếu | `cites` | `citation` | — | 75,023 |
| Văn bản liên quan khác | `related_to` | `related` | — | 461 |
| Văn bản quy định hết hiệu lực | `expires_or_replaces` | `validity` | `expired_or_replaced_by` | 61,227 |
| Văn bản hết hiệu lực | `expired_or_replaced_by` | `validity` | `expires_or_replaces` | 49,995 |
| Văn bản quy định hết hiệu lực 1 phần | `partially_expires` | `validity` | `partially_expired_by` | 6,061 |
| Văn bản bị hết hiệu lực 1 phần | `partially_expired_by` | `validity` | `partially_expires` | 8,073 |
| Văn bản HD, QĐ chi tiết | `guides_or_details` | `guidance` | `guided_or_detailed_by` | 34,240 |
| Văn bản được HD, QĐ chi tiết | `guided_or_detailed_by` | `guidance` | `guides_or_details` | 34,991 |
| Văn bản bổ sung | `supplements` | `supplement` | `supplemented_by` | 12,794 |
| Văn bản được bổ sung | `supplemented_by` | `supplement` | `supplements` | 6,498 |
| Văn bản sửa đổi | `amends` | `amendment` | `amended_by` | 7,420 |
| Văn bản được sửa đổi | `amended_by` | `amendment` | `amends` | 7,667 |
| Văn bản đình chỉ | `suspends` | `suspension` | `suspended_by` | 16 |
| Văn bản bị đình chỉ | `suspended_by` | `suspension` | `suspends` | 14 |
| Văn bản đình chỉ 1 phần | `partially_suspends` | `suspension` | `partially_suspended_by` | 21 |
| Văn bản bị đình chỉ 1 phần | `partially_suspended_by` | `suspension` | `partially_suspends` | 19 |

**Verified:** the 17 counts above sum to exactly 883,256, matching `relationships_final.jsonl`'s row count precisely. This confirms the mapping table is complete — there is no eighteenth category or leftover bucket hiding elsewhere.

### 6.2 Direction Convention — Verification Required

The raw taxonomy is normally recorded from the viewing document's perspective (a label attached to Document A typically describes the *other* document's role relative to A). It is not documented whether `finalize_dataset.py` reordered `(doc_id, other_doc_id)` accordingly, or preserved row order and only translated the label text. This affects the `amendment`, `supplement`, `guidance`, and `validity` groups — over 195,000 edges combined. This must be confirmed with real sample rows before production ingestion (§7).

### 6.3 Pair Count Asymmetry — No Collapsing

| Pair | Forward | Inverse | Difference |
| --- | ---: | ---: | ---: |
| `expires_or_replaces` / `expired_or_replaced_by` | 61,227 | 49,995 | 11,232 |
| `guides_or_details` / `guided_or_detailed_by` | 34,240 | 34,991 | 751 |
| `supplements` / `supplemented_by` | 12,794 | 6,498 | 6,296 |
| `amends` / `amended_by` | 7,420 | 7,667 | 247 |
| `partially_expires` / `partially_expired_by` | 6,061 | 8,073 | 2,012 |
| `suspends` / `suspended_by` | 16 | 14 | 2 |
| `partially_suspends` / `partially_suspended_by` | 21 | 19 | 2 |

Unequal counts mean the two directions of each pair are not duplicate recordings of the same edge. Policy: ingest every row independently; never synthesize, merge, or drop a row based on its counterpart.

### 6.4 Edge Multiplicity Rule

MERGE key is the full triple `(doc_id_str, other_doc_id_str, relationship_canonical)`, not the document pair alone — a pair may legitimately hold more than one relationship type at once.

### 6.5 Relationship Group Usage

| Group | Edge types | Retrieval role |
| --- | --- | --- |
| `basis` | `BASED_ON` | 578,736 edges (~65.5% of total). Cap traversal depth (`*1..3`) — this is the largest group by far, and `SPEC.md` §3 sets a hard latency budget (<1 minute average response); unbounded multi-hop here is the most likely place to violate it. |
| `validity` | `EXPIRES_OR_REPLACES`, `EXPIRED_OR_REPLACED_BY`, `PARTIALLY_EXPIRES`, `PARTIALLY_EXPIRED_BY` | Lineage/explanation only — never overrides `validity_group`. |
| `citation` | `CITES` | Supplementary context. |
| `guidance` | `GUIDES_OR_DETAILS`, `GUIDED_OR_DETAILED_BY` | Law ↔ implementing Decree/Circular. |
| `supplement` | `SUPPLEMENTS`, `SUPPLEMENTED_BY` | Content addition, no validity impact. |
| `amendment` | `AMENDS`, `AMENDED_BY` | Content change, no full invalidation. |
| `suspension` | `SUSPENDS`, `SUSPENDED_BY`, `PARTIALLY_SUSPENDS`, `PARTIALLY_SUSPENDED_BY` | ≤70 edges total across all four types — sparse; requires dedicated test cases rather than incidental coverage. |
| `related` | `RELATED_TO` | 461 edges — fallback only, excluded from default graph-guided filter. |

## 7. Validation and Report

### Full Coverage Counts

`graph_build_report.md` must include:

- `total_document_nodes` (must equal rows in `metadata_final.jsonl` + `metadata_external_stubs.jsonl`)
- `total_cross_document_edges` (must equal rows in `relationships_final.jsonl` — one row, one edge)
- `total_legal_unit_nodes`, `total_chunk_nodes`
- `orphan_legal_unit_count`, `orphan_chunk_count` (must be 0)

### No Data Loss / No Silent Drop Checks

- Zero nodes or edges sourced from `metadata_quarantine.jsonl` or `relationships_quarantine.jsonl`.
- Zero relationship rows silently dropped, flipped, or merged based on inverse-pair assumptions (§6.3).
- Confirmed: `metadata_final.jsonl` + `metadata_quarantine.jsonl` = 151,624 + 1,796 = 153,420, matching raw metadata exactly — no metadata record is unaccounted for.
- Confirmed: `relationships_final.jsonl` + `relationships_quarantine.jsonl` = 883,256 + 14,634 = 897,890, matching raw relationships exactly — no relationship row is unaccounted for.
- **Reason-breakdown mismatch (does not indicate lost records, but must be reconciled):** the metadata quarantine reasons (`missing_issuer` 1,789 + `unknown_type` 8 + `future_issue_date` 2 = 1,799) sum to 3 more than the actual quarantine row count (1,796); the relationship quarantine reasons (`duplicate_edge` 7,652 + `source_quarantined` 4,781 + `target_quarantined` 2,030 + `self_loop` 277 = 14,740) sum to 106 more than the actual row count (14,634). Since the totals themselves reconcile exactly, these two mismatches most likely indicate a small number of rows tagged with more than one reason. Confirm this with whoever owns `finalize_dataset.py` before treating it as understood — it should not silently be assumed.
- Reconcile the 57,790 raw "target missing from metadata" edges against `external_target = true` edge count and the 19,763 `metadata_external_stubs.jsonl` records; report any gap.
- Enumerate all `edge_keep_status` values found in `relationships_final.jsonl`; confirm only "kept" rows reach ingestion.

### Required Report Sections

- Node counts by label; edge counts by `relationship_canonical` and by `relationship_group` (cross-check against §6.1's verified total of 883,256).
- Direction-convention sample-check results (§6.2): 5-10 manually verified edges per pair, prioritizing `guides_or_details`/`guided_or_detailed_by` and `amends`/`amended_by`.
- Cross-validation warnings: `Document` nodes with `validity_group = active` that have an incoming `EXPIRES_OR_REPLACES` edge from another active document whose effective date has passed.
- `ExternalStub` count and confirmation all carry `citation_safe = false`.
- Distribution of `structuring_status` across ingested `Document` nodes, so the team can see what fraction of documents have no structural children.
- Examples of orphan or unresolved nodes, if any.

### Hard Acceptance Metrics

```text
total_document_nodes == metadata_final.jsonl rows + metadata_external_stubs.jsonl rows
total_cross_document_edges == relationships_final.jsonl rows
orphan_legal_unit_count == 0
orphan_chunk_count == 0
citation_safe == false for 100% of ExternalStub nodes
0 nodes/edges sourced from quarantine files
direction-convention sample check completed and signed off before production use
```

## 8. Retrieval and Graph Guidance

Graph queries should support:

- **Graph-guided hard filter for vector retrieval** — filter `Document` by `validity_group`, `dataset_tier`, `linh_vuc_canonical`, excluding `ExternalStub`, and pass the resulting `id_str` set to the vector store as a hard filter. If the filter yields an empty set, return that explicitly (§2) rather than silently falling through to an unfiltered query.
- **Legal-basis multi-hop** — traverse `BASED_ON` up to 3 hops, per the depth cap in §6.5.
- **Guidance lookup** — traverse `GUIDES_OR_DETAILS` to find implementing Decrees/Circulars for a Law.
- **Validity lineage** — traverse `EXPIRES_OR_REPLACES` / `PARTIALLY_EXPIRES` ordered by `ngay_co_hieu_luc_iso` to explain, not override, current status.
- **Structural drill-down** — `Document -[:DOCUMENT_HAS_UNIT]-> LegalUnit -[:UNIT_HAS_CHUNK]-> Chunk` to resolve a specific article to its `chunk_id`/`citation_anchor`; check `structuring_status` first (§4.4) and fall back to Document-level evidence if no `LegalUnit` children exist.
- **Same-unit expansion** — sibling `Chunk` nodes under the same `LegalUnit`, matching the vector-retrieval guidance already defined in `SPEC_Text_Structuring.md` §8 ("use `parent_unit_id` for same-unit expansion").
- Rank/filter results by `dataset_tier`, `validity_group`, and `relationship_group`; treat `related` group edges as fallback-only, used when no edge from another group connects two documents.

## 9. Processing Flow

1. Load `metadata_final.jsonl` and `metadata_external_stubs.jsonl`; create `Document` (and `Document:ExternalStub`) nodes.
2. Load `documents_structured.jsonl`; merge structuring fields onto the matching `Document` node by `id_str`, using the distinct property names defined in §5 to avoid the `quality_flags` naming collision.
3. Load `relationships_final.jsonl`; for each row, create one edge using the full `(doc_id_str, other_doc_id_str, relationship_canonical)` triple as the MERGE key.
4. Load `legal_units.jsonl`; create `LegalUnit` nodes and link via `DOCUMENT_HAS_UNIT` and `UNIT_NEXT`.
5. Load `chunks.jsonl`; create `Chunk` nodes (pointer fields only) and link via `UNIT_HAS_CHUNK` and `CHUNK_NEXT`.
6. Run reconciliation checks (§7) and write warnings to the build report — do not auto-correct source data.
7. Run the direction-convention sample check (§6.2) and record sign-off status.
8. Build indexes/constraints (`id_str`, `unit_id`, `chunk_id` uniqueness; index on `validity_group`, `dataset_tier`, `structuring_status`).
9. Write `graph_build_report.md`.

## 10. Acceptance Criteria

| Criterion | Status |
| --- | --- |
| All `metadata_final.jsonl` + `metadata_external_stubs.jsonl` records become `Document` nodes | Required |
| No quarantine file is ingested | Required |
| Every `relationships_final.jsonl` row becomes exactly one edge, no inference/merging | Required |
| Edge MERGE key is the full triple, not the document pair | Required |
| Structural node/edge names match `SPEC_Text_Structuring.md` exactly | Required |
| `Chunk`/`LegalUnit` nodes exclude full-text fields and denormalized document metadata | Required |
| `Document` nodes carry both `quality_flags` and `structuring_quality_flags` as distinct properties | Required |
| `ExternalStub` nodes are 100% marked `citation_safe = false` | Required |
| Direction-convention sample check completed before production use | Required |
| Quarantine-count and external-stub-count reconciliations reported, including the reason-breakdown mismatches | Required |
| `BASED_ON` traversal depth capped in retrieval queries | Required |
| Empty graph-guided filter results are surfaced, not silently ignored | Required |
| `graph_build_report.md` is generated | Required |

## 11. Open Items for the Team

1. Confirm the direction convention (§6.2) with real sample rows — highest-priority open item, blocks production use of the `amendment`/`supplement`/`guidance`/`validity` groups.
2. Resolve the `quality_flags` vs `quality_flags_document` naming ambiguity between `Dataset_SPEC.md` and `SPEC_Text_Structuring.md` at the source, so future spec revisions don't reintroduce the confusion this spec had to work around (§5).
3. Confirm whether the quarantine reason-breakdown mismatches (§7) are caused by overlapping reason tags on the same row, or something else.
4. Decide Phase 1 scope: full `LegalUnit`/`Chunk` ingestion vs. Document-level graph only for the first milestone.
5. Confirm whether entity/concept-level extraction (per `SPEC.md` §4.6's general description) is intended for a later phase, and if so, what data source will feed it — currently out of scope (§1).