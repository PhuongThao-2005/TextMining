# Retrieval_Handoff.md

## 1. Purpose

This artifact notifies the teammates responsible for vector retrieval and graph retrieval about the finalized dataset preprocessing scope, expected inputs, and responsibilities after dataset filtering is completed.

The dataset preprocessing owner will provide cleaned metadata and relationship files. Vector and graph retrieval teammates should not consume the raw files directly unless debugging or validating preprocessing decisions.

## 2. Reference Documents

| Artifact | Purpose |
| --- | --- |
| `SPEC.md` | Main system specification for G-LRAG |
| `Dataset_SPEC.md` | Final dataset filtering and preprocessing specification |
| `metadata_final.jsonl` | Cleaned metadata handoff file after preprocessing |
| `relationships_final.jsonl` | Cleaned relationship handoff file after preprocessing |
| `metadata_quarantine.jsonl` | Excluded metadata records for audit only |
| `relationships_quarantine.jsonl` | Excluded relationship records for audit only |
| `metadata_external_stubs.jsonl` | Optional placeholder records for relationship targets missing from metadata |
| `preprocessing_report.md` | Preprocessing summary and count report |

## 3. Dataset Handoff Contract

The preprocessing stage will hand off normalized files with raw fields preserved and additional canonical fields added.

### 3.1 Metadata Fields Expected by Retrieval Teams

Expected core fields in `metadata_final.jsonl`:

- `id`
- `id_str`
- `title`
- `title_clean`
- `so_ky_hieu`
- `so_ky_hieu_clean`
- `loai_van_ban`
- `loai_van_ban_canonical`
- `ngay_ban_hanh`
- `ngay_ban_hanh_iso`
- `ngay_co_hieu_luc`
- `ngay_co_hieu_luc_iso`
- `ngay_het_hieu_luc`
- `ngay_het_hieu_luc_iso`
- `issue_year`
- `co_quan_ban_hanh`
- `co_quan_ban_hanh_canonical`
- `pham_vi`
- `pham_vi_canonical`
- `nganh`
- `nganh_canonical`
- `linh_vuc`
- `linh_vuc_canonical`
- `tinh_trang_hieu_luc`
- `tinh_trang_hieu_luc_canonical`
- `validity_group`
- `dataset_tier`
- `quality_flags`
- `citation_label`

### 3.2 Relationship Fields Expected by Retrieval Teams

Expected core fields in `relationships_final.jsonl`:

- `doc_id`
- `doc_id_str`
- `other_doc_id`
- `other_doc_id_str`
- `relationship`
- `relationship_raw`
- `relationship_canonical`
- `relationship_group`
- `source_in_metadata`
- `target_in_metadata`
- `external_target`
- `edge_quality_flags`
- `edge_keep_status`

## 4. Vector Retrieval Teammate Notification

### 4.1 Scope

The vector retrieval teammate should build semantic retrieval over cleaned, citation-safe document content and metadata.

Primary input:

- `metadata_final.jsonl`

Optional inputs:

- full text files or parsed document content when available;
- `preprocessing_report.md` for dataset quality context.

Do not use:

- `metadata_quarantine.jsonl` for normal retrieval;
- `metadata_external_stubs.jsonl` as answer evidence;
- raw `metadata.jsonl` as the production retrieval source.

### 4.2 Indexing Recommendation

Prioritize records where:

- `dataset_tier = primary`;
- `validity_group` is `active`, `partial`, or `future`;
- `citation_label` exists;
- `quality_flags` does not contain severe warnings such as `invalid_issue_date`, `unknown_type`, or `missing_issuer`.

Reference records may be indexed separately for historical or low-priority retrieval:

- `dataset_tier = reference`;
- `validity_group = expired`, `suspended`, or `unknown`.

Expired documents are intentionally retained as reference-tier records, not as current-law evidence. They preserve legal history, amendment/replacement lineage, validity reasoning, and cited legal basis context. Retrieval should penalize or filter expired documents for normal current-law answers unless the user explicitly asks about historical law, old regulations, lineage, amendments, replacements, or validity changes.

### 4.3 Metadata to Attach to Each Vector Chunk

Every embedded chunk should preserve:

- `id_str`
- `title_clean`
- `citation_label`
- `loai_van_ban_canonical`
- `co_quan_ban_hanh_canonical`
- `ngay_ban_hanh_iso`
- `validity_group`
- `dataset_tier`
- `pham_vi_canonical`
- `nganh_canonical`
- `linh_vuc_canonical`
- `quality_flags`

### 4.4 Retrieval Ranking Signals

Suggested ranking boosts:

- `dataset_tier = primary`
- `validity_group = active`
- exact or semantic match on title;
- match on `loai_van_ban_canonical`;
- match on `pham_vi_canonical` for jurisdiction-specific queries;
- match on `nganh_canonical` or `linh_vuc_canonical` for sector-specific queries;
- clean citation metadata.

Suggested ranking penalties:

- `dataset_tier = reference` unless the query asks for history or expired documents;
- `validity_group = expired`, `suspended`, or `unknown`;
- quality flags indicating incomplete citation metadata;
- external stubs, which should not be embedded as answer evidence.

### 4.5 Expected Vector Retrieval Output

Vector retrieval should return:

- retrieved chunk text;
- document ID;
- chunk ID;
- vector score;
- metadata fields needed for filtering/ranking;
- citation label;
- source document status and tier.

## 5. Graph Retrieval Teammate Notification

### 5.1 Scope

The graph retrieval teammate should build graph retrieval using cleaned metadata and cleaned relationship edges.

Primary inputs:

- `metadata_final.jsonl`
- `relationships_final.jsonl`

Optional input:

- `metadata_external_stubs.jsonl`, only if the team accepts external stub nodes.

Do not use:

- `relationships_quarantine.jsonl` for production graph traversal;
- raw `relationships.jsonl` as the production graph source;
- external stubs as citation-safe answer evidence.

### 5.2 Relationship Semantics

Use `relationship_canonical` and `relationship_group`, not raw relationship labels, for traversal logic.

Important canonical relationship groups:

| Group | Use case |
| --- | --- |
| `basis` | Legal basis and upstream authority tracing |
| `citation` | Citation/context expansion |
| `guidance` | Finding implementation or detailed guidance documents |
| `amendment` | Current-law and change tracking |
| `supplement` | Additional context or expanded regulation coverage |
| `validity` | Expiration/replacement reasoning |
| `suspension` | Suspension status reasoning |
| `related` | Weak context expansion only |

### 5.3 Graph Node Requirements

Minimum node properties for document nodes:

- `id_str`
- `title_clean`
- `citation_label`
- `dataset_tier`
- `validity_group`
- `loai_van_ban_canonical`
- `co_quan_ban_hanh_canonical`
- `ngay_ban_hanh_iso`
- `quality_flags`

External stub nodes, if used, must include:

- `id_str`
- `is_external_stub = true`
- `missing_metadata = true`
- `citation_safe = false`
- `dataset_tier = reference_stub`

### 5.4 Graph Edge Requirements

Minimum edge properties:

- `doc_id_str`
- `other_doc_id_str`
- `relationship_raw`
- `relationship_canonical`
- `relationship_group`
- `external_target`
- `edge_quality_flags`

### 5.5 Traversal Recommendations

For normal legal QA:

- start from vector-retrieved document IDs;
- expand one hop using high-value groups: `basis`, `citation`, `guidance`, `amendment`, `validity`;
- avoid broad expansion through high-degree hubs unless the query asks for legal basis;
- exclude quarantine and non-citation-safe nodes from final answer evidence.

For current-law or validity questions:

- prioritize `amendment`, `validity`, and `suspension` groups;
- inspect active and partially active documents first;
- include expired documents only to explain legal history or lineage;
- do not present expired documents as currently binding law when active or partially active successors exist.

For historical or lineage questions:

- allow `reference` tier documents;
- traverse amendment, supplement, expiration, and guidance links;
- clearly separate historical evidence from currently valid evidence.

### 5.6 Graph Retrieval Output

Graph retrieval should return:

- seed document ID;
- expanded document IDs;
- relationship path;
- canonical relationship labels;
- graph score or path confidence;
- document tier and validity group;
- citation-safe indicator;
- explanation of why each graph-expanded document was included.

## 6. Fusion Expectations Between Vector and Graph Retrieval

The final retrieval layer should combine vector and graph results.

Suggested fusion signals:

- vector similarity score;
- graph path relevance;
- relationship group priority;
- document tier;
- validity group;
- citation-safe status;
- metadata completeness;
- source diversity;
- path length.

Final answer generation should only use citation-safe documents as grounded evidence.

## 7. Important Constraints

- Do not use quarantined records in production retrieval.
- Do not cite external stubs.
- Do not treat expired documents as currently binding law unless the user query is explicitly historical or asks about prior validity.
- Do not treat relationship edges as text evidence by themselves.
- Do not let high-degree hub documents dominate graph expansion.
- Preserve raw IDs as strings when joining metadata and relationships.
- Use `dataset_tier` and `validity_group` in both vector and graph retrieval filters.
- Use canonical relationship labels instead of raw relationship labels in retrieval logic.

## 8. Required Acknowledgement From Teammates

Vector retrieval teammate should confirm:

- which metadata fields will be stored with chunks;
- whether `reference` tier will be indexed separately;
- how validity and tier filters will be applied;
- how citation labels will be returned.

Graph retrieval teammate should confirm:

- whether external stubs will be used;
- how missing targets are handled;
- how high-degree hubs are controlled;
- how canonical relationship groups map to traversal strategies;
- how graph results will be returned for fusion.

## 9. Final Message

Dataset preprocessing will provide cleaned metadata and relationship artifacts. Vector retrieval should consume the finalized metadata records and preserve citation metadata at chunk level. Graph retrieval should consume finalized relationship records and canonical relationship labels, while treating external stubs as non-citation-safe.

This handoff keeps responsibilities clear: preprocessing prepares reliable data, vector retrieval builds semantic search, and graph retrieval builds relationship-based expansion.
