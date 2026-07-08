# SPEC_Knowledge_Graph.md

> **v2-aligned.** This spec matches the dataset actually produced by the v2 pipeline (`Dataset_SPEC_v2.md`, `data/v2/`). The pre-v2 version is archived at `docs/archive/SPEC_Knowledge Graph.md`. Key changes from the archived version are called out in §12.

## 1. Purpose

This document specifies the graph construction stage for the G-LRAG pipeline.

The stage assembles the v2 dataset artifacts into a Neo4j graph:

```text
documents.jsonl + edges.jsonl + external_stubs.jsonl        -> Document graph
provisions.jsonl + chunks.jsonl                              -> Structural graph
validity_timeline.jsonl + authority_index.jsonl             -> Reasoning overlay
```

This stage does not re-derive facts already computed upstream. `validity_group`, `currency_hint`, `legal_authority_rank`, `structuring_status`, edge direction, and all structural node/edge names are consumed as-is from `Dataset_SPEC_v2.md` and `SPEC_Text_Structuring.md`. The graph exists to support multi-hop legal-basis reasoning, temporal-validity lineage, and graph-guided filtering for vector retrieval, per `SPEC.md` §4.6–§6.8, and serves two measurable success criteria from `SPEC.md` §3: hallucination rate under 10% and average response latency under 1 minute.

Scope: **document-level relationships + document-internal structure + the temporal/authority reasoning overlay.** Free-standing entity/concept extraction (named legal terms inside article text) is out of scope until a dedicated extraction pipeline and dataset exist (§11).

## 2. Core Requirements

- Ingest every kept record from `documents.jsonl` as `Document` nodes, and every record from `external_stubs.jsonl` as `Document:ExternalStub` nodes.
- Never ingest `documents_quarantine.jsonl` or `edges_quarantine.jsonl`.
- Ingest every row of `edges.jsonl` as one independent directed edge; do not infer, flip, merge, or drop rows based on assumed symmetry.
- v2 edges are **direction-normalized**: `src_id -[REL]-> dst_id` always reads "src REL dst" in plain legal language. Respect `direction_normalized` and `direction_verified` — see §6.
- Treat `(src_id, dst_id, rel_canonical)` as the full triple key; a single document pair may hold more than one relationship type.
- Attach `text_provenance.jsonl` tracking fields (`text_status`, `structuring_status`, `legal_unit_count`, `chunk_count`) to the corresponding `Document` node, so structural health is visible without a separate lookup.
- Reuse `Provision`/`Chunk` node names and structural edge names (`DOCUMENT_HAS_PROVISION`, `PROVISION_HAS_CHUNK`, `CHUNK_NEXT`, `PROVISION_NEXT`) exactly as in `SPEC_Text_Structuring.md`.
- Do not copy `chunk_text` into the graph — `Chunk` nodes are pointers, resolved against the vector store when content is needed.
- Do not duplicate `Document`-level metadata onto `Provision`/`Chunk` nodes; traverse `DOCUMENT_HAS_PROVISION`/`PROVISION_HAS_CHUNK` back to `Document` instead. (v2 chunk rows are already slim and carry no metadata to copy.)
- Mark every `ExternalStub` node non-citable (`citation_safe = false`) and exclude it from evidence paths by default.
- A graph/validity builder **must refuse** to consume any edge group with `direction_verified = false`, surfacing it rather than guessing (`Dataset_SPEC_v2.md` §8.2).
- When a graph-guided filter returns an empty `id_str` set, surface it explicitly rather than silently degrading to an unfiltered query (`SPEC.md` §5.6).

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `data/v2/documents.jsonl` | `Document` nodes |
| `data/v2/external_stubs.jsonl` | `Document:ExternalStub` nodes |
| `data/v2/edges.jsonl` | Cross-document edges |
| `data/v2/text_provenance.jsonl` | Structural tracking fields merged onto `Document` nodes |
| `data/v2/provisions.jsonl` | `Provision` nodes |
| `data/v2/chunks.jsonl` | `Chunk` nodes (pointer fields only) |
| `data/v2/validity_timeline.jsonl` | Temporal reasoning overlay (§7) |
| `data/v2/authority_index.jsonl` | Document-type → authority-rank reference |

Join `Document` to `Provision`/`Chunk` by `id_str`. Join `Chunk` to `Provision` by `parent_unit_id`.

### Outputs

| Output | Purpose |
| --- | --- |
| Neo4j graph (`Document`, `ExternalStub`, `Provision`, `Chunk` nodes + edges) | Queryable graph for retrieval |
| `graph_build_report.md` | Node/edge counts, reconciliation checks, warnings |

## 4. Graph Model

### 4.1 Node Labels

| Label | Meaning |
| --- | --- |
| `Document` | A normalized legal document, enriched with structuring status |
| `Document:ExternalStub` | A relationship target with no metadata record; non-citable placeholder |
| `Provision` | A citation unit inside a document (`article`, `preamble`, `section`, `item`, `attachment_preamble`, `document`), from `SPEC_Text_Structuring.md` §4 |
| `Chunk` | A retrieval chunk, pointer-only, slim key fields from `SPEC_Text_Structuring.md` §5.3 |

### 4.2 Structural Edge Types (from `SPEC_Text_Structuring.md` §8)

| Edge | Meaning | Why (derivable-from) |
| --- | --- | --- |
| `DOCUMENT_HAS_PROVISION` | Document contains provision | Containment (set membership). Not derivable from another edge. |
| `PROVISION_HAS_CHUNK` | Provision contains chunk | Containment (set membership). Join key `parent_unit_id`. |
| `CHUNK_NEXT` | Next chunk in the same provision | **Reading order.** Powers same-provision expansion (`SPEC_Vector_Retrieval.md` §4.5): from one retrieved chunk of a long article, walk `#k → #k+1` to restore full-article context without re-querying the vector store. Materialized for the hot path; *derivable* from `chunk_index_in_unit` under a shared `parent_unit_id`. |
| `PROVISION_NEXT` | Next provision in the same document | **Reading order.** Supports cross-article reading ("the preceding Article", "subject to Điều 12") by walking to the adjacent provision. Materialized convenience; *derivable* from `char_start` (or the index in `unit_id`) under a shared `id_str`. |

> Containment edges say *what belongs to what* (an unordered set); the two `*_NEXT` edges add *what comes after what*. They carry no new information — both orderings are derivable from fields already on the rows — so they are a materialized convenience: pay build/storage cost once to avoid sorting on every query. Keeping both is the recommended default; a leaner build may drop `PROVISION_NEXT` and derive provision order on demand while retaining `CHUNK_NEXT` for the named expansion feature.

### 4.3 Cross-Document Edge Types

One edge type per `rel_canonical` value, converted mechanically to `UPPER_SNAKE_CASE` (`based_on` → `BASED_ON`). No canonical label is merged, split, or dropped. Full mapping and group table in §6.

### 4.4 Fallback / Exclusion Rules

- If an edge's `dst_id` is not a `Document`, it must exist as an `ExternalStub` (`external_target = true` on the edge). The edge is still created; the target carries `citation_safe = false`.
- If a `Document` has `text_status` in (`missing`, `empty`, `too_short`, `extraction_failed`) or `structuring_status` in (`missing_full_text`, `empty_text`, `text_too_short`, `parse_error`), it will have zero `Provision` children — the `Document` node must still be created from `documents.jsonl`. Absence of structural children never blocks Document-level construction.
- Structural drill-down queries (§8) must check `structuring_status` before assuming `Provision`/`Chunk` children exist.

## 5. Required Schemas

### 5.1 Document Node (from `documents.jsonl`)

```text
id_str, title, so_ky_hieu, citation_label
loai_van_ban, loai_van_ban_raw
legal_authority_rank
issuing_authority{code,surface,raw}
legal_field{code,surface,raw}
sector{code,surface,raw}
scope{code,surface,raw}
ngay_ban_hanh_iso, ngay_co_hieu_luc_iso, ngay_het_hieu_luc_iso, issue_year
tinh_trang_hieu_luc_raw, validity_group, currency_hint, currency_hint_authoritative
chuc_danh, nguoi_ky
quality_flags[]
```

Faceted fields are `{code, surface, raw}` triples. In Neo4j, flatten each to indexable scalars, e.g. `issuing_authority_code`, `issuing_authority_surface` (filter on `_code`, display `_surface`). Unmapped values carry `code = "MISSING"` / `"UNMAPPED"`.

Fields merged from `text_provenance.jsonl` (by `id_str`):

```text
text_status, structuring_status, legal_unit_count, chunk_count
```

No `quality_flags` naming collision exists in v2 (provenance has no `quality_flags`); metadata `quality_flags` stays as `Document.quality_flags`.

### 5.2 ExternalStub Node (from `external_stubs.jsonl`)

```text
id_str, is_external_stub, citation_safe, referenced_by_edge_count, quality_flags[]
```

### 5.3 Provision Node (from `provisions.jsonl`, structural fields only)

```text
unit_id, id_str
unit_type, article_number
unit_heading, path
citation_anchor
char_start, char_end, unit_char_count, unit_token_estimate
chunk_count, coverage_verified
```

The provision row also carries denormalized display fields (`title`, `citation_label`, `legal_authority_rank`, `validity_group`, `currency_hint`, `quality_flags`). These may be attached for query convenience, or resolved via `DOCUMENT_HAS_PROVISION` back to `Document`.

### 5.4 Chunk Node (from `chunks.jsonl`, pointers only)

```text
chunk_id, parent_unit_id, id_str
chunk_index_in_unit, chunk_count_in_unit
unit_split
structuring_quality_flags[]
```

`chunk_text` is excluded (content stays in the vector store). The v2 chunk row carries no `citation_anchor`, `unit_type`, or `article_number` — resolve those via `parent_unit_id → Provision`.

### 5.5 Cross-Document Edge Record (from `edges.jsonl`)

```text
(src_id) -[:REL_CANONICAL_UPPER]-> (dst_id)
  edge_id
  rel_raw, rel_group
  direction_normalized, direction_verified
  external_target
  edge_quality_flags[]
  provenance{doc_id, other_doc_id, relationship}
```

## 6. Relationship & Edge Policy

### 6.1 Raw-to-Canonical Mapping

`edges.jsonl` maps raw Vietnamese labels (`rel_raw`) to `rel_canonical` values, one-to-one, grouped by `rel_group`. The 17 raw labels and their groups (`basis`, `citation`, `related`, `validity`, `guidance`, `supplement`, `amendment`, `suspension`):

| Raw label (`rel_raw`) | `rel_group` |
| --- | --- |
| Văn bản căn cứ | `basis` |
| Văn bản dẫn chiếu | `citation` |
| Văn bản liên quan khác | `related` |
| Văn bản quy định hết hiệu lực / Văn bản hết hiệu lực | `validity` |
| Văn bản quy định hết hiệu lực 1 phần / Văn bản bị hết hiệu lực 1 phần | `validity` |
| Văn bản HD, QĐ chi tiết / Văn bản được HD, QĐ chi tiết | `guidance` |
| Văn bản bổ sung / Văn bản được bổ sung | `supplement` |
| Văn bản sửa đổi / Văn bản được sửa đổi | `amendment` |
| Văn bản đình chỉ / Văn bản bị đình chỉ | `suspension` |
| Văn bản đình chỉ 1 phần / Văn bản bị đình chỉ 1 phần | `suspension` |

The build report must enumerate every distinct `rel_canonical` and its edge count, and cross-check the sum against `edges.jsonl`'s row count. From the v2 reconciliation: `edges.jsonl` = 883,256 rows; `edges_quarantine.jsonl` = 14,634; raw total 897,890.

### 6.2 Direction — Verified Upstream

Unlike v1, v2 normalizes edge direction so `src_id -[REL]-> dst_id` reads "src REL dst" (`Dataset_SPEC_v2.md` §8.1). Each edge carries `direction_normalized` and `direction_verified`. Policy:

- Trust `direction_normalized = true` edges as canonical.
- **Refuse to ingest into reasoning paths** any edge whose `rel_group` is not signed off (`direction_verified = false`) — surface it in the build report; do not guess (§2).
- The `basis`/`citation`/`related` groups are directionally trivial; the `validity`/`amendment`/`guidance`/`supplement`/`suspension` groups are the ones the sign-off gate protects.

### 6.3 Edge Multiplicity

MERGE key is the full triple `(src_id, dst_id, rel_canonical)`, not the document pair — a pair may hold more than one relationship type.

### 6.4 Relationship Group Usage

| Group | Retrieval role |
| --- | --- |
| `basis` | Largest group (`BASED_ON`). Cap traversal depth (`*1..3`) — `SPEC.md` §3 sets a hard latency budget; unbounded multi-hop here is the most likely place to violate it. |
| `validity` | Lineage/explanation only — feeds `validity_timeline` (§7); never overrides derived currency. |
| `citation` | Supplementary context (`CITES`). |
| `guidance` | Law ↔ implementing Decree/Circular. |
| `supplement` | Content addition, no validity impact. |
| `amendment` | Content change, no full invalidation. |
| `suspension` | Very sparse — requires dedicated test cases. |
| `related` | Fallback only; excluded from default graph-guided filter. |

## 7. Reasoning Overlay (v2 addition)

v2 ships two derived artifacts the graph layers over the base edges. These replace v1's frozen `dataset_tier`.

### 7.1 Validity timeline (`validity_timeline.jsonl`)

```text
id_str, event_type, event_date_iso, counterparty_id, scope,
rel_canonical, source_edge_id, direction_verified
```

- `event_type` ∈ `enacted | effective | expired | replaced | amended | suspended | partially_*`.
- `currency_status(id_str, as_of_date)` is a **function**: fold events up to `as_of_date`. Default `as_of = today`.
- The stored `Document.currency_hint` is a fast-path fallback only; `currency_hint_authoritative = false` means prefer the timeline.
- Every timeline event traces to a `source_edge_id` in `edges.jsonl`. Events whose `direction_verified = false` must not drive authoritative currency decisions (§6.2).

Attach timeline events to `Document` nodes (or as `:VALIDITY_EVENT` nodes linked by `id_str` and `counterparty_id`) so lineage traversal and currency computation are the same operation as graph traversal.

### 7.2 Authority index (`authority_index.jsonl`)

```text
loai_van_ban, legal_authority_rank, rank_label, version
```

Rank 1 = `Hiến pháp`, 2 = `Bộ luật`/`Luật`, … 99 = unknown (`Dataset_SPEC_v2.md` §6.1). Each `Document` already carries `legal_authority_rank`; the index is the versioned reference for validating/refreshing it. Conflict resolution follows legal precedence: `min(legal_authority_rank)` wins, newer `ngay_co_hieu_luc_iso` breaks ties.

## 8. Retrieval and Graph Guidance

- **Graph-guided hard filter for vector retrieval** — filter `Document` by `validity_group`/`currency_status(as_of)`, `legal_authority_rank`, faceted `_code` fields, excluding `ExternalStub`; pass the resulting `id_str` set to the vector store as a hard filter. Empty set → surface explicitly (§2).
- **Legal-basis multi-hop** — traverse `BASED_ON` up to 3 hops (§6.4).
- **Guidance lookup** — traverse `GUIDES_OR_DETAILS` to find implementing Decrees/Circulars for a Law.
- **Validity lineage** — traverse `validity`-group edges / `validity_timeline` ordered by `event_date_iso` to explain, not override, current status.
- **Structural drill-down** — `Document -[:DOCUMENT_HAS_PROVISION]-> Provision -[:PROVISION_HAS_CHUNK]-> Chunk` to resolve an article to its `chunk_id`; check `structuring_status` first (§4.4).
- **Same-provision expansion** — sibling `Chunk` nodes under the same `Provision` via `parent_unit_id` (`SPEC_Vector_Retrieval.md` §4.5).
- Rank/filter by `legal_authority_rank`, `validity_group`/derived currency, and `rel_group`; treat `related` edges as fallback-only.

## 9. Processing Flow

1. Load `documents.jsonl` and `external_stubs.jsonl`; create `Document` (and `Document:ExternalStub`) nodes; flatten faceted triples to `_code`/`_surface`.
2. Load `text_provenance.jsonl`; merge `text_status`, `structuring_status`, counts onto each `Document` by `id_str`.
3. Load `edges.jsonl`; for each row create one edge using the `(src_id, dst_id, rel_canonical)` triple as MERGE key; skip `rel_group`s with `direction_verified = false` for reasoning (report them).
4. Load `provisions.jsonl`; create `Provision` nodes and link via `DOCUMENT_HAS_PROVISION` and `PROVISION_NEXT`.
5. Load `chunks.jsonl`; create pointer-only `Chunk` nodes and link via `PROVISION_HAS_CHUNK` (by `parent_unit_id`) and `CHUNK_NEXT`.
6. Load `validity_timeline.jsonl` and `authority_index.jsonl`; build the reasoning overlay (§7).
7. Run reconciliation checks (§10); write warnings — do not auto-correct source data.
8. Build indexes/constraints (`id_str`, `unit_id`, `chunk_id` uniqueness; index `validity_group`, `legal_authority_rank`, `structuring_status`, `issuing_authority_code`).
9. Write `graph_build_report.md`.

## 10. Validation and Acceptance Criteria

Hard metrics:

```text
total_document_nodes == documents.jsonl rows + external_stubs.jsonl rows
total_cross_document_edges == edges.jsonl rows (883,256)
orphan_provision_count == 0
orphan_chunk_count == 0
citation_safe == false for 100% of ExternalStub nodes
0 nodes/edges sourced from *_quarantine.jsonl
no reasoning path consumes a direction_verified = false edge group
```

Required report sections:

- Node counts by label; edge counts by `rel_canonical` and `rel_group` (cross-check §6.1).
- `direction_verified` status per `rel_group`, and which groups were excluded from reasoning.
- `ExternalStub` count + confirmation all carry `citation_safe = false`; reconcile against `referenced_by_edge_count` and `external_target = true` edges.
- Distribution of `structuring_status` / `text_status` across `Document` nodes.
- Reconciliation: `raw = final + quarantine` for documents and edges (per `Dataset_SPEC_v2.md` §10).

| Criterion | Status |
| --- | --- |
| All `documents.jsonl` + `external_stubs.jsonl` records become nodes | Required |
| No quarantine file is ingested | Required |
| Every `edges.jsonl` row becomes exactly one edge, no inference/merging | Required |
| Edge MERGE key is the full triple `(src_id, dst_id, rel_canonical)` | Required |
| Structural node/edge names match `SPEC_Text_Structuring.md` | Required |
| `Chunk`/`Provision` nodes exclude `chunk_text` | Required |
| `direction_verified = false` groups excluded from reasoning and reported | Required |
| `ExternalStub` nodes 100% `citation_safe = false` | Required |
| `validity_timeline` + `authority_index` overlay built and traceable to `source_edge_id` | Required |
| `BASED_ON` traversal depth capped | Required |
| Empty graph-guided filter surfaced, not silently ignored | Required |
| `graph_build_report.md` generated | Required |

## 11. Open Items for the Team

1. Confirm which `rel_group`s carry `direction_verified = true` in the current `edges.jsonl` before enabling `validity`/`amendment`/`guidance`/`supplement` reasoning paths.
2. Decide how faceted triples are flattened in Neo4j (`_code`/`_surface` properties vs. separate vocabulary nodes for facet traversal).
3. Decide Phase 1 scope: full `Provision`/`Chunk` ingestion vs. Document-level graph + reasoning overlay only for the first milestone.
4. Confirm the `validity_timeline` attachment model (event properties on `Document` vs. dedicated `:VALIDITY_EVENT` nodes) with the retrieval team.
5. Confirm whether entity/concept-level extraction is intended for a later phase and what data source feeds it — currently out of scope (§1).

## 12. Changes from the archived (pre-v2) spec

| Area | Archived spec | This v2 spec |
| --- | --- | --- |
| Input files | `metadata_final.jsonl`, `relationships_final.jsonl`, `documents_structured.jsonl`, `legal_units.jsonl` | `documents.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `provisions.jsonl`, `text_provenance.jsonl` |
| Structural level | `LegalUnit` (`DOCUMENT_HAS_UNIT`/`UNIT_HAS_CHUNK`) | `Provision` (`DOCUMENT_HAS_PROVISION`/`PROVISION_HAS_CHUNK`) |
| Edge fields | `doc_id_str`, `other_doc_id_str`, `relationship_canonical`, `relationship_group`, `relationship_raw` | `src_id`, `dst_id`, `rel_canonical`, `rel_group`, `rel_raw`, `edge_id` |
| Edge direction | Unverified; sign-off required downstream | Normalized upstream; `direction_normalized`/`direction_verified` per edge |
| Authority/currency | `dataset_tier` (primary/reference) | `legal_authority_rank` + `validity_group` + derived `currency_status` (`dataset_tier` retired) |
| Faceted metadata | `*_canonical` strings | `{code, surface, raw}` triples flattened to `_code`/`_surface` |
| `quality_flags` collision | Two sources; resolved as `quality_flags` + `structuring_quality_flags` | No collision (provenance has no `quality_flags`) |
| Reasoning overlay | none | `validity_timeline.jsonl` + `authority_index.jsonl` |
