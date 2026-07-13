# SPEC Audit — Knowledge Graph Module vs. `SPEC_Knowledge_Graph.md`

| Field | Value |
| --- | --- |
| Date | 2026-07-13 |
| Scope | Audit of `src/knowledge_graph/` and `src/retrieval/retriever.py` against [`docs/spec/SPEC_Knowledge_Graph.md`](../spec/SPEC_Knowledge_Graph.md) |
| Verdict | **Partially implemented overall.** The module surface exists and most structural traversal/filtering behaviors are present, but the implementation is still in-memory, lacks the required Neo4j/reporting layer, and several spec-mandated reconciliation / refusal rules are not enforced. |

## Legend

- ✓ Implemented
- ⚠ Partially implemented
- ✗ Missing

## 1. Purpose

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Assemble `documents.jsonl` + `edges.jsonl` + `external_stubs.jsonl` into a Document graph; `provisions.jsonl` + `chunks.jsonl` into a structural graph; `validity_timeline.jsonl` + `authority_index.jsonl` into a reasoning overlay | ⚠ Partially implemented | The module has separate loader / parser / builder / overlay services, but the output is an in-memory `KnowledgeGraph` plus overlay bundle, not a Neo4j graph. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/overlay.py`, `src/knowledge_graph/facade.py` | Add a persistence adapter layer for Neo4j materialization and keep the current in-memory model only as an intermediate representation. |
| Do not re-derive upstream facts; consume validity, authority, structure, and edge direction as upstream inputs | ⚠ Partially implemented | The graph module consumes upstream artifacts, but `overlay.py` still derives `currency_status` and `resolve_authority_rank_conflicts()`, and `parser.py` does not retain all spec-listed stored fields on `DocumentNode`. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/overlay.py`, `src/knowledge_graph/context.py` | Make the overlay join purely attach derived views from the source tables and align node schema with the spec / compatibility policy in one place. |
| Support multi-hop legal-basis reasoning, temporal-validity lineage, and graph-guided vector filtering | ✓ Implemented | `GraphTraversal.traverse_basis()`, `GraphTraversal.traverse_validity()`, `ContextBuilder.build_graph_guided_filter()`, and retriever graph-guided filtering are present. | `src/knowledge_graph/traversal.py`, `src/knowledge_graph/context.py`, `src/retrieval/retriever.py` | Keep these APIs stable; only tighten enforcement and reporting. |

## 2. Core Requirements

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Ingest every kept `documents.jsonl` row as a `Document` node and every `external_stubs.jsonl` row as a `Document:ExternalStub` node | ⚠ Partially implemented | Parsed rows are turned into typed nodes and stored in-memory, but there is no Neo4j node creation layer. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add a graph-store adapter that materializes node labels/properties and keep the current builder as the source of truth for typed records. |
| Never ingest `documents_quarantine.jsonl` or `edges_quarantine.jsonl` | ✓ Implemented | Loader reads only the allowed five core v2 source files plus overlay files; no quarantine files are referenced. | `src/knowledge_graph/loader.py`, `src/knowledge_graph/facade.py` | None. |
| Ingest every `edges.jsonl` row as one independent directed edge; do not infer, flip, merge, or drop rows | ✓ Implemented | `parse_edge_rows()` preserves every row; `GraphBuilder.build()` stores `document_edges` as a tuple without deduplication or folding. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py` | Keep as-is. |
| Respect `direction_normalized` and `direction_verified` | ⚠ Partially implemented | Direction flags are parsed and preserved; traversal uses `verified_document_edges`, but the builder does not refuse unverified groups and there is no build report surfacing the exclusion set. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py` | Add build-time validation/reporting that lists unverified groups and blocks reasoning-path consumption when the spec requires refusal. |
| Use the full triple key `(src_id, dst_id, rel_canonical)` | ⚠ Partially implemented | The code never MERGEs edges, so it does not collapse pairwise relationships; however, the triple key is not explicitly enforced or reported as the identity contract. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/edge_schema.py` | Add explicit triple-key validation to the future graph-store adapter and report duplicate-triple behavior. |
| Attach `text_provenance.jsonl` tracking fields to the corresponding `Document` node | ✓ Implemented | `DocumentNode` includes `text_status`, `structuring_status`, `legal_unit_count`, and `chunk_count`, and `parse_document_row()` merges provenance by `id_str`. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/facade.py` | Keep stable. |
| Reuse `Provision` / `Chunk` names and structural edge names exactly | ✓ Implemented | `ProvisionNode`, `ChunkNode`, and `StructuralEdge` use the required names; `GraphBuilder` materializes `DOCUMENT_HAS_PROVISION`, `PROVISION_HAS_CHUNK`, `CHUNK_NEXT`, and `PROVISION_NEXT`. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/builder.py` | Keep stable. |
| Do not copy `chunk_text` into the graph | ✓ Implemented | `ChunkNode` has no `chunk_text`; only `chunk_id`, join keys, and structural fields are stored. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py` | Keep stable. |
| Do not duplicate `Document`-level metadata onto `Provision` / `Chunk` nodes | ⚠ Partially implemented | `ProvisionNode` carries denormalized display fields (`title`, `citation_label`, `loai_van_ban`, `so_ky_hieu`) for convenience, which is allowed by the schema but is a partial deviation from the stricter core requirement. `ChunkNode` remains slim. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py` | Decide whether those provision display fields should remain in the graph model or move to the graph-store adapter as query-time joins. |
| Mark every `ExternalStub` non-citable and exclude it from evidence paths by default | ⚠ Partially implemented | `parse_external_stub_row()` sets `citation_safe = false`, but there is no explicit evidence-path exclusion rule outside the context builder’s document-only filter. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/context.py`, `src/knowledge_graph/facade.py` | Add a clear evidence-path exclusion filter in the graph context layer and surface stub counts in the report. |
| Refuse to consume edge groups with `direction_verified = false` for reasoning | ⚠ Partially implemented | `GraphTraversal` only traverses `verified_document_edges`, and `compute_currency_status()` only uses verified events, but `GraphBuilder` still ingests unverified edges and no report enumerates excluded groups. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py`, `src/retrieval/retriever.py` | Add build-time refusal/reporting for unverified groups and keep the verified-only traversal rule explicit. |
| Surface empty graph-guided filter results explicitly | ✓ Implemented | `ContextBuilder.build_graph_guided_filter()` and `VectorRetriever.retrieve()` return explicit empty results with warnings. | `src/knowledge_graph/context.py`, `src/knowledge_graph/context_schema.py`, `src/retrieval/retriever.py` | Keep stable. |

## 3. Inputs and Outputs

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Read `documents.jsonl`, `external_stubs.jsonl`, `edges.jsonl`, `text_provenance.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `validity_timeline.jsonl`, `authority_index.jsonl` | ✓ Implemented | The loader / facade read the five core graph inputs plus the overlay files; no quarantine sources are touched. | `src/knowledge_graph/loader.py`, `src/knowledge_graph/facade.py`, `src/knowledge_graph/overlay.py` | Keep stable. |
| Join `Document` to `Provision` / `Chunk` by `id_str`; join `Chunk` to `Provision` by `parent_unit_id` | ✓ Implemented | `GraphBuilder` creates `document_to_provisions` and `provision_to_chunks` adjacency maps; `GraphExpansion` and `GraphTraversal` consume them. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/expansion.py` | Keep stable. |
| Output a Neo4j graph (`Document`, `ExternalStub`, `Provision`, `Chunk` nodes + edges) | ✗ Missing | Current output is an in-memory `KnowledgeGraph` and overlay objects; there is no Neo4j adapter or persistence layer. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Introduce a graph-store adapter that writes the built graph into Neo4j while keeping the in-memory model as a staging object. |
| Output `graph_build_report.md` | ✗ Missing | `GraphBuildResult` returns stats/warnings, but no report writer exists in the graph module. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add a report writer mirroring the dataset pipeline’s reconciliation style. |

## 4. Graph Model

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| `Document` label with structuring status enrichment | ⚠ Partially implemented | `DocumentNode` stores structuring provenance, but the implementation is not a persisted label-based graph. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Persist the same typed fields as node properties in the graph-store adapter. |
| `Document:ExternalStub` label as non-citable placeholder | ⚠ Partially implemented | `ExternalStubNode` exists and is marked `citation_safe = false`, but the label is not materialized in a graph store. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Materialize as a second label when the Neo4j adapter lands. |
| `Provision` citation-unit node | ✓ Implemented | The required fields exist and are indexed from `provisions.jsonl`. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Keep stable. |
| `Chunk` retrieval-pointer node | ✓ Implemented | `ChunkNode` is slim and excludes content text. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Keep stable. |
| `DOCUMENT_HAS_PROVISION` / `PROVISION_HAS_CHUNK` / `CHUNK_NEXT` / `PROVISION_NEXT` edge types | ✓ Implemented | All four structural edge types are materialized in `GraphBuilder`. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/expansion.py` | Keep stable. |
| Cross-document edge type per `rel_canonical`, no merging/splitting/dropping | ⚠ Partially implemented | Edges are parsed as canonical records, but there is no canonicalization table / count report and no explicit enforcement of the raw-to-canonical mapping contract. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add raw-to-canonical mapping validation/reporting and a canonical edge-count summary. |

### 4.4 Fallback / Exclusion Rules

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Non-Document edge targets must exist as `ExternalStub` when `external_target = true` | ⚠ Partially implemented | `GraphBuilder` checks for missing external targets and counts them, but does not enforce a graph-store rule or produce a report section. | `src/knowledge_graph/builder.py` | Add build-report output and optionally a hard validation mode in the future adapter. |
| Documents with missing / empty / too-short / extraction-failed text should have zero `Provision` children | ✗ Missing | The builder does not gate structural edges by document text status; it builds adjacency based on the provision/chunk inputs. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/facade.py` | Add a structural precondition check before creating document→provision links, or explicitly document that the upstream structuring phase guarantees zero-child docs. |
| Structural drill-down queries must check `structuring_status` before assuming children exist | ⚠ Partially implemented | `DocumentNode` exposes `structuring_status`, but traversal does not enforce that check before walking children. | `src/knowledge_graph/traversal.py`, `src/knowledge_graph/context.py` | Add a guard in structural traversal or context-building callers. |

## 5. Required Schemas

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Document schema includes `legal_authority_rank`, `validity_group`, `currency_hint`, `currency_hint_authoritative`, and `tinh_trang_hieu_luc_raw` | ✗ Missing | `DocumentNode` intentionally omits authority/validity fields; they are only available via the overlay, which diverges from the spec’s stored-node schema. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/overlay.py`, `src/knowledge_graph/context.py` | Decide whether the graph should persist compatibility fields on Document nodes or continue to keep them exclusively in overlays and update the spec/report accordingly. |
| Document faceted fields are flattened to `_code` / `_surface` scalars | ⚠ Partially implemented | Facets are parsed as `{code, surface, raw}` objects rather than flattened node properties. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Add a flattening layer in the graph-store adapter or expose helper properties alongside the current objects. |
| ExternalStub schema (`id_str`, `is_external_stub`, `citation_safe`, `referenced_by_edge_count`, `quality_flags[]`) | ✓ Implemented | All required fields are present on `ExternalStubNode`. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py` | Keep stable. |
| Provision schema contains structural fields only | ⚠ Partially implemented | Structural fields are present, but `ProvisionNode` also carries denormalized display fields. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py` | Decide whether to keep display fields as convenience properties or move them out of the structural node model. |
| Chunk schema contains join keys and split metadata only; no `chunk_text` | ✓ Implemented | `ChunkNode` is pointer-only and excludes content. | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py` | Keep stable. |
| Cross-document edge schema includes `edge_id`, `rel_raw`, `rel_group`, direction flags, `external_target`, `edge_quality_flags`, and provenance | ✓ Implemented | `GraphEdge` carries the required fields, with provenance preserved as a dict. | `src/knowledge_graph/edge_schema.py`, `src/knowledge_graph/edge_parser.py` | Keep stable. |

## 6. Relationship & Edge Policy

### 6.1 Raw-to-canonical mapping

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Map raw Vietnamese labels to canonical `rel_canonical` values and group them by `rel_group` | ✗ Missing | `parse_edge_row()` assumes `rel_canonical` / `rel_group` are already present in the input row and does not perform the mapping itself. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/overlay.py`, `src/knowledge_graph/facade.py` | Add a canonical relationship mapping table and report counts per `rel_canonical` / `rel_group`. |
| Build report must enumerate distinct `rel_canonical` values and cross-check the sum against the row count | ✗ Missing | There is no graph build report yet. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add report generation with canonical edge counts and reconciliation totals. |

### 6.2 Direction — verified upstream

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Trust `direction_normalized = true` edges as canonical | ⚠ Partially implemented | Flags are parsed and preserved, but no explicit validation/reporting is done at build time. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py` | Add build-time validation/reporting around direction-normalized edges. |
| Refuse reasoning on edge groups with `direction_verified = false` | ⚠ Partially implemented | `GraphTraversal` uses `verified_document_edges`, but unverified edges still live in the graph and are not surfaced in a report. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py` | Keep the verified-only traversal rule and add an explicit excluded-groups report. |
| Treat `basis` / `citation` / `related` as directionally trivial; protect `validity` / `amendment` / `guidance` / `supplement` / `suspension` | ⚠ Partially implemented | The traversal API supports basis/guidance/validity/structure/neighbors, but there is no explicit policy object separating trivial vs. protected groups. | `src/knowledge_graph/traversal.py`, `src/knowledge_graph/context.py` | Introduce a policy helper or report section for protected groups and their sign-off state. |

### 6.3 Edge multiplicity

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Use the full triple `(src_id, dst_id, rel_canonical)` as the merge key | ⚠ Partially implemented | The in-memory graph does not merge or dedupe edges, so the key is not actively enforced. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/edge_schema.py` | Enforce triple-key identity in the graph-store adapter and report duplicate-triple behavior. |

### 6.4 Relationship group usage

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Basis traversal should be capped at depth 1..3 | ✓ Implemented | `GraphTraversal.traverse_basis()` defaults to depth 3 and only traverses verified basis edges. | `src/knowledge_graph/traversal.py` | Keep stable. |
| Validity is lineage / explanation only and never overrides derived currency | ✓ Implemented | Currency is derived from overlay events; traversal only surfaces lineage paths. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/context.py` | Keep stable. |
| Citation is supplementary context | ✗ Missing | There is no dedicated citation traversal method or policy; `neighbors` is the closest approximation. | `src/knowledge_graph/traversal.py`, `src/knowledge_graph/facade.py` | Add a citation-mode traversal or explicitly define `neighbors` as the supplementary context path. |
| Guidance links law ↔ implementing decree/circular | ✓ Implemented | `traverse_guidance()` exists and filters verified guidance edges. | `src/knowledge_graph/traversal.py` | Keep stable. |
| Supplement / amendment / suspension behaviors are respected | ⚠ Partially implemented | Edges and overlay events are preserved, but there is no dedicated policy / test surface for these groups in the graph module. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py` | Add explicit report coverage and tests for the protected edge groups. |
| `related` is fallback-only and excluded from the default graph-guided filter | ✗ Missing | No graph-guided filter policy explicitly excludes `related` edges; the current filter is traversal-id based. | `src/knowledge_graph/context.py`, `src/knowledge_graph/traversal.py` | Add a policy gate that excludes `related` from default graph-guided traversal/filtering. |

## 7. Reasoning Overlay

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Build a validity timeline from `validity_timeline.jsonl` and expose `currency_status(id_str, as_of_date)` | ✓ Implemented | `overlay.py` parses validity events, indexes them, and computes a coarse currency status. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/overlay_schema.py` | Keep stable. |
| Every timeline event must trace to `source_edge_id` and respect `direction_verified` | ✓ Implemented | `ValidityEvent` stores `source_edge_id` and `direction_verified`; currency computation filters to verified events. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/overlay_schema.py` | Keep stable. |
| Attach timeline events to `Document` nodes or as dedicated `:VALIDITY_EVENT` nodes | ✗ Missing | The implementation keeps overlay data separate from node storage; nothing is attached to graph nodes. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/facade.py`, `src/knowledge_graph/builder.py` | Add a graph-store join layer that can materialize event nodes or attach event properties, depending on the chosen storage model. |
| Build versioned authority index and resolve rank conflicts by legal precedence | ⚠ Partially implemented | Authority entries are parsed and indexed, but conflict resolution uses rank + version string ordering rather than the spec’s richer precedence rule (`min(rank)` with newer effective date tie-break). | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/overlay_schema.py` | Refine the conflict resolution rule once the canonical version semantics are settled. |

## 8. Retrieval and Graph Guidance

| Requirement | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Graph-guided hard filter for vector retrieval should filter by derived currency, legal authority, and facet codes, exclude `ExternalStub`, and surface empty sets explicitly | ⚠ Partially implemented | `ContextBuilder` and `VectorRetriever` now support graph-guided filters and empty-set warnings, but the graph module still operates on in-memory overlays and document IDs rather than a persisted graph store. | `src/knowledge_graph/context.py`, `src/knowledge_graph/context_schema.py`, `src/retrieval/retriever.py` | Keep the API stable, then wire the filter into the eventual graph-store backed query planner. |
| Legal-basis multi-hop traversal (`BASED_ON` up to 3 hops) | ✓ Implemented | `GraphTraversal.traverse_basis()` is depth-capped and verified-edge only. | `src/knowledge_graph/traversal.py` | Keep stable. |
| Guidance lookup traversal | ✓ Implemented | `GraphTraversal.traverse_guidance()` exists and is verified-edge only. | `src/knowledge_graph/traversal.py` | Keep stable. |
| Validity lineage traversal ordered by `event_date_iso` | ⚠ Partially implemented | Timeline events are sorted in the overlay layer, but traversal itself does not explicitly order paths by `event_date_iso`; the overlay and traversal are split. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/traversal.py` | If ordering matters in downstream explanations, add a traversal helper that consumes the sorted overlay timeline. |
| Structural drill-down from Document → Provision → Chunk, checking structuring status first | ⚠ Partially implemented | Structural traversal exists, but it does not gate on `structuring_status` before walking. | `src/knowledge_graph/traversal.py`, `src/knowledge_graph/context.py` | Add a structuring-status guard before structural drill-down in the traversal/context layer. |
| Same-provision expansion via `parent_unit_id` / `CHUNK_NEXT` | ⚠ Partially implemented | `GraphExpansion` preserves ordered context, but it reconstructs chunk order from `chunk_index_in_unit` and does not explicitly walk `chunk_next` for neighbor expansion. | `src/knowledge_graph/expansion.py`, `src/knowledge_graph/builder.py` | Refactor expansion to consume the cached `chunk_next` adjacency directly for same-provision neighbor hops. |
| Rank/filter by authority, currency, and rel_group; treat `related` as fallback only | ⚠ Partially implemented | Filtering by authority/currency is present in `ContextBuilder`, but `related` fallback behavior is not explicit. | `src/knowledge_graph/context.py` | Add explicit related-edge fallback policy and report it in the audit/build report. |

## 9. Processing Flow

| Step | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| 1. Load documents and external stubs; flatten facets to `_code` / `_surface` | ⚠ Partially implemented | Loader and parser exist, but facets remain objects in typed nodes; no graph-store flattening layer exists yet. | `src/knowledge_graph/loader.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/schema.py` | Add a flattening adapter for the graph-store layer while preserving typed objects in the current intermediate model. |
| 2. Load text provenance and merge onto each Document by `id_str` | ✓ Implemented | `index_text_provenance()` and `parse_document_rows(..., provenance)` do this. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/facade.py` | Keep stable. |
| 3. Load edges and create one edge per row; skip unverified groups for reasoning and report them | ⚠ Partially implemented | Edges are preserved, and traversal uses verified edges, but no build-time report enumerates skipped groups. | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py` | Add a reconciliation/reporting layer for unverified groups. |
| 4. Load provisions and link via `DOCUMENT_HAS_PROVISION` / `PROVISION_NEXT` | ✓ Implemented | `GraphBuilder` materializes both relation types. | `src/knowledge_graph/builder.py` | Keep stable. |
| 5. Load chunks and link via `PROVISION_HAS_CHUNK` / `CHUNK_NEXT` | ✓ Implemented | `GraphBuilder` materializes both relation types. | `src/knowledge_graph/builder.py` | Keep stable. |
| 6. Load validity timeline and authority index; build reasoning overlay | ⚠ Partially implemented | Overlay joins exist, but they are separate from the graph nodes / edges and not materialized into a graph store. | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/facade.py` | Add a store-backed overlay materialization step if required by the graph backend. |
| 7. Run reconciliation checks and write warnings without auto-correction | ⚠ Partially implemented | `GraphBuildStats` / `warnings` exist, but there is no dedicated build report writer. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Implement the report writer and keep auto-correction disabled. |
| 8. Build indexes / constraints (`id_str`, `unit_id`, `chunk_id`, plus `validity_group`, `legal_authority_rank`, `structuring_status`, `issuing_authority_code`) | ⚠ Partially implemented | In-memory dictionaries provide uniqueness by key, but there are no persisted indexes / constraints and no `validity_group` node property on `DocumentNode`. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/schema.py`, `src/knowledge_graph/overlay.py` | Surface the intended index set in the future Neo4j adapter and align node properties accordingly. |
| 9. Write `graph_build_report.md` | ✗ Missing | No writer exists in the graph module. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add a report generation function and route the stats/warnings through it. |

## 10. Validation and Acceptance Criteria

| Criterion | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| `total_document_nodes == documents.jsonl rows + external_stubs.jsonl rows` | ⚠ Partially implemented | The builder can count in-memory nodes, but there is no persisted reconciliation report proving the identity. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Emit a reconciliation report with node totals. |
| `total_cross_document_edges == edges.jsonl rows (883,256)` | ⚠ Partially implemented | All edge rows are parsed, but no report cross-checks the final count. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Add edge-count reconciliation to the report writer. |
| `orphan_provision_count == 0` | ⚠ Partially implemented | `GraphBuildStats` tracks orphan provisions, but the build does not currently fail or report them in a dedicated artifact. | `src/knowledge_graph/builder.py` | Add explicit report output and optional enforcement. |
| `orphan_chunk_count == 0` | ⚠ Partially implemented | `GraphBuildStats` tracks orphan chunks, but no report exists. | `src/knowledge_graph/builder.py` | Same as above. |
| `citation_safe == false` for 100% of `ExternalStub` nodes | ✓ Implemented | `parse_external_stub_row()` sets `citation_safe` to false by default. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/schema.py` | Keep stable. |
| No nodes/edges from quarantine files | ✓ Implemented | Loader scope excludes quarantine artifacts. | `src/knowledge_graph/loader.py` | Keep stable. |
| No reasoning path consumes a `direction_verified = false` edge group | ⚠ Partially implemented | Traversal respects verified edges, but there is no report proving the excluded groups and no build-time refusal. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py` | Add report coverage and an explicit refusal rule in the build layer. |

### Required report sections

| Report section | Status | Why / evidence | Affected files | Proposed plan |
| --- | --- | --- | --- | --- |
| Node counts by label; edge counts by `rel_canonical` and `rel_group` | ✗ Missing | There is no `graph_build_report.md` writer. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Implement the report writer. |
| `direction_verified` status per `rel_group`, plus excluded groups | ✗ Missing | No report artifact exists. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/overlay.py` | Add a report section powered by the edge stats. |
| ExternalStub count, `citation_safe = false`, reconciliation against `referenced_by_edge_count` and `external_target = true` | ✗ Missing | The necessary data is present, but not summarized into a report. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Add report generation. |
| Distribution of `structuring_status` / `text_status` across Documents | ✗ Missing | The fields exist on `DocumentNode`, but no report aggregates them. | `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Add report aggregation. |
| Reconciliation `raw = final + quarantine` for documents and edges | ✗ Missing | This reconciliation exists in the dataset pipeline, not in the graph module. | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Either reference the dataset report or reproduce the identities in the graph report. |

## 11. Open Items for the Team

| Open item | Audit status | Affected files | Implementation plan |
| --- | --- | --- | --- |
| Confirm which `rel_group`s carry `direction_verified = true` before enabling validity / amendment / guidance / supplement reasoning paths | ⚠ Partially addressed | `src/knowledge_graph/edge_parser.py`, `src/knowledge_graph/builder.py`, `src/knowledge_graph/traversal.py`, `src/knowledge_graph/overlay.py` | Keep verified-only traversal and add a report enumerating unverified groups. |
| Decide how faceted triples are flattened in Neo4j | ✗ Missing | `src/knowledge_graph/schema.py`, `src/knowledge_graph/parser.py`, `src/knowledge_graph/builder.py` | Choose property flattening vs. separate vocab nodes before introducing the graph-store adapter. |
| Decide Phase 1 scope: full Provision/Chunk ingestion vs Document-level graph + overlay only | ✓ Implemented (full typed model), ⚠ for Neo4j persistence | `src/knowledge_graph/builder.py`, `src/knowledge_graph/facade.py` | Continue with the current full typed model, then materialize to the chosen backend. |
| Confirm the validity attachment model (event properties on Document vs `:VALIDITY_EVENT` nodes) | ✗ Missing | `src/knowledge_graph/overlay.py`, `src/knowledge_graph/facade.py` | Pick one model and implement it in the graph-store adapter. |
| Confirm whether concept extraction is later-phase only | ✓ Out of scope | No code in `src/knowledge_graph/` attempts concept extraction. | None | Keep out of scope until the dedicated extraction pipeline exists. |

## 12. Change Summary for This Audit

No code was modified while producing this audit. The review identified three important cleanup / correctness items already addressed in the current branch state and several remaining gaps:

- The graph module is currently an in-memory, typed service layer; it does **not** yet satisfy the spec’s Neo4j persistence/reporting requirement.
- The retriever’s `graph_guided` path now respects a supplied `GraphGuidedFilter`, but the graph module still needs a report and build-time refusal surface for unverified edge groups.
- Same-provision expansion is present, but `CHUNK_NEXT` is not the primary navigation primitive yet; it is reconstructed from chunk ordering rather than traversed directly.

## 13. Remaining Technical Debt

1. Add a graph-store adapter so the current typed model can be materialized into Neo4j.
2. Add `graph_build_report.md` generation with node/edge counts, reconciliation, and excluded-group reporting.
3. Decide the authoritative node schema for validity and authority: persist compatibility fields on `Document` nodes or keep them exclusively in the overlay layer.
4. Make `GraphExpansion` consume `chunk_next` directly for same-provision neighbor expansion.
5. Add explicit policy coverage for `related`-only fallback behavior and the protected edge groups.