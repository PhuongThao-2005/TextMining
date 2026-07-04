# Dataset_SPEC.md

## 1. Purpose

This document is the EDA and finalization report for the cleaned dataset package produced from:

- `Road2AI_ApplePie/data/untracked_data/metadata.jsonl`
- `Road2AI_ApplePie/data/untracked_data/relationships.jsonl`

The finalized dataset is prepared for the G-LRAG system described in `SPEC.md`. This stage focuses on dataset filtering, preprocessing, normalization, quarantine handling, and handoff readiness. Graph construction remains out of scope and will be handled separately.

## 2. Finalized Dataset Artifacts

The finalized dataset was generated into `Road2AI_ApplePie/data/finalized/`.

| Artifact | Purpose |
| --- | --- |
| `Road2AI_ApplePie/data/finalized/metadata_final.jsonl` | Cleaned metadata records for retrieval, citation, and downstream processing |
| `Road2AI_ApplePie/data/finalized/relationships_final.jsonl` | Cleaned document-to-document relationships for downstream graph/retrieval work |
| `Road2AI_ApplePie/data/finalized/metadata_quarantine.jsonl` | Metadata records excluded from final use, retained for audit/recovery |
| `Road2AI_ApplePie/data/finalized/relationships_quarantine.jsonl` | Relationship records excluded from final use, retained for audit/recovery |
| `Road2AI_ApplePie/data/finalized/metadata_external_stubs.jsonl` | Placeholder records for relationship targets missing from metadata |
| `Road2AI_ApplePie/data/finalized/preprocessing_report.md` | Machine-generated preprocessing summary |

The preprocessing pipeline used to produce these files is available at `scripts/finalize_dataset.py`.

## 3. Raw Dataset EDA Summary

### 3.1 Raw Metadata

| Metric | Value |
| --- | ---: |
| Raw metadata records | 153,420 |
| Invalid JSON rows | 0 |
| Unique IDs | 153,420 |
| Duplicate IDs | 0 |

Raw metadata fields:

- `id`
- `title`
- `so_ky_hieu`
- `ngay_ban_hanh`
- `loai_van_ban`
- `ngay_co_hieu_luc`
- `ngay_het_hieu_luc`
- `nguon_thu_thap`
- `ngay_dang_cong_bao`
- `nganh`
- `linh_vuc`
- `co_quan_ban_hanh`
- `chuc_danh`
- `nguoi_ky`
- `pham_vi`
- `thong_tin_ap_dung`
- `tinh_trang_hieu_luc`

### 3.2 Raw Relationships

| Metric | Value |
| --- | ---: |
| Raw relationship records | 897,890 |
| Invalid JSON rows | 0 |
| Raw fields | `doc_id`, `other_doc_id`, `relationship` |
| Missing values | 0 |
| Unique exact edges | 890,238 |
| Duplicate exact edges | 7,652 |
| Self-loops | 277 |
| Source IDs missing from metadata | 0 |
| Target IDs missing from metadata | 57,790 edges |

## 4. Finalization Results

### 4.1 Final Output Counts

| Dataset | Count |
| --- | ---: |
| `metadata_final.jsonl` | 151,624 |
| `metadata_quarantine.jsonl` | 1,796 |
| `relationships_final.jsonl` | 883,256 |
| `relationships_quarantine.jsonl` | 14,634 |
| `metadata_external_stubs.jsonl` | 19,763 |

### 4.2 Retention Rate

| Dataset type | Raw count | Final count | Quarantine count | Final retention |
| --- | ---: | ---: | ---: | ---: |
| Metadata | 153,420 | 151,624 | 1,796 | 98.83% |
| Relationships | 897,890 | 883,256 | 14,634 | 98.37% |

The final retention rate is high because the dataset is mostly valid and legally relevant. Filtering primarily removed records with missing core identity fields, unknown document type, impossible issue year, duplicate edges, self-loops, and relationships connected to quarantined metadata.

## 5. Final Metadata EDA

### 5.1 Metadata by Dataset Tier

| Dataset tier | Count |
| --- | ---: |
| `reference` | 82,778 |
| `primary` | 68,846 |

Interpretation:

- `primary` records are retrieval-ready and best suited for citation-grounded answer generation.
- `reference` records are retained for historical context, lineage, legal basis, expired-document reasoning, or later graph expansion.
- Quarantined records are not included in `metadata_final.jsonl`.

### 5.2 Metadata by Validity Group

| Validity group | Count |
| --- | ---: |
| `expired` | 79,640 |
| `active` | 64,115 |
| `partial` | 5,423 |
| `unknown` | 1,993 |
| `suspended` | 371 |
| `future` | 82 |

Interpretation:

- The finalized dataset contains a large expired/reference corpus, useful for legal lineage and historical reasoning.
- The primary current-law corpus is mainly represented by `active`, `partial`, and `future` records.
- `unknown` and `suspended` records were retained as reference material when core identity metadata was sufficient.

### 5.3 Top Final Metadata Document Types

| Document type | Count |
| --- | ---: |
| `Quyết định` | 86,877 |
| `Nghị quyết` | 26,331 |
| `Thông tư` | 17,706 |
| `Chỉ thị` | 8,458 |
| `Nghị định` | 5,542 |
| `Thông tư liên tịch` | 3,435 |
| `Sắc lệnh` | 980 |
| `Công văn` | 733 |
| `Luật` | 663 |
| `Lệnh` | 379 |
| `Pháp lệnh` | 247 |
| `Văn bản hợp nhất` | 62 |
| `Văn bản liên quan` | 43 |
| `Chương trình` | 41 |
| `Nghị quyết liên tịch` | 32 |
| `Hiệp định` | 24 |
| `Bộ luật` | 19 |
| `Văn bản khác` | 16 |
| `Thông báo` | 12 |
| `Hiến pháp` | 8 |
| `Thông tư liên bộ` | 7 |
| `Sắc luật` | 4 |
| `Bản ghi nhớ` | 2 |
| `Nghị định thư` | 2 |
| `Thỏa thuận` | 1 |

Interpretation:

- The final dataset is dominated by `Quyết định`, `Nghị quyết`, `Thông tư`, `Chỉ thị`, and `Nghị định`.
- The dataset is suitable for legal/public-administration retrieval because it preserves a broad range of legal document types.
- Lower-frequency types were retained when they were legally meaningful.

### 5.4 Metadata Quarantine Reasons

| Reason | Count |
| --- | ---: |
| `missing_issuer` | 1,789 |
| `unknown_type` | 8 |
| `future_issue_date` | 2 |

Interpretation:

- Most metadata quarantine decisions were caused by missing issuer information.
- Only a small number of records were excluded for unknown type or impossible future issue date.
- Quarantined metadata is retained for audit/recovery and can be reviewed later if missing issuer/type/date can be corrected.

## 6. Final Relationship EDA

### 6.1 Relationships by Canonical Label

| Canonical relationship | Count |
| --- | ---: |
| `based_on` | 578,736 |
| `cites` | 75,023 |
| `expires_or_replaces` | 61,227 |
| `expired_or_replaced_by` | 49,995 |
| `guided_or_detailed_by` | 34,991 |
| `guides_or_details` | 34,240 |
| `supplements` | 12,794 |
| `partially_expired_by` | 8,073 |
| `amended_by` | 7,667 |
| `amends` | 7,420 |
| `supplemented_by` | 6,498 |
| `partially_expires` | 6,061 |
| `related_to` | 461 |
| `partially_suspends` | 21 |
| `partially_suspended_by` | 19 |
| `suspends` | 16 |
| `suspended_by` | 14 |

### 6.2 Relationships by Group

| Relationship group | Count |
| --- | ---: |
| `basis` | 578,736 |
| `validity` | 125,356 |
| `citation` | 75,023 |
| `guidance` | 69,231 |
| `supplement` | 19,292 |
| `amendment` | 15,087 |
| `related` | 461 |
| `suspension` | 70 |

Interpretation:

- `basis` relationships dominate the dataset and are valuable for upstream legal authority tracing.
- `validity`, `amendment`, `supplement`, and `suspension` relationships are useful for current-law and legal-lineage reasoning.
- `related` relationships are intentionally retained but should be treated as weak/low-priority context.

### 6.3 Relationship Quarantine Reasons

| Reason | Count |
| --- | ---: |
| `duplicate_edge` | 7,652 |
| `source_quarantined` | 4,781 |
| `target_quarantined` | 2,030 |
| `self_loop` | 277 |

Interpretation:

- Exact duplicate relationship edges were removed from final use.
- Relationships involving quarantined source or target metadata were excluded.
- Self-loops were quarantined by default because they are not generally useful for retrieval handoff without manual validation.

### 6.4 External Stub Summary

| Metric | Value |
| --- | ---: |
| External stubs created | 19,763 |

External stubs represent relationship target IDs that appear in `relationships.jsonl` but are missing from `metadata.jsonl`.

Stub policy:

- preserve missing-target connectivity for downstream teams;
- mark stubs as `citation_safe=false`;
- mark stubs as `dataset_tier=reference_stub`;
- do not use stubs as final answer evidence.

## 7. Final Preprocessing Schema

### 7.1 Added Metadata Fields

Each kept metadata record has added normalized fields:

- `id_str`
- `title_clean`
- `so_ky_hieu_clean`
- `loai_van_ban_canonical`
- `ngay_ban_hanh_iso`
- `ngay_co_hieu_luc_iso`
- `ngay_het_hieu_luc_iso`
- `issue_year`
- `co_quan_ban_hanh_canonical`
- `pham_vi_canonical`
- `nganh_canonical`
- `linh_vuc_canonical`
- `tinh_trang_hieu_luc_canonical`
- `validity_group`
- `dataset_tier`
- `quality_flags`
- `citation_label`

### 7.2 Added Relationship Fields

Each kept relationship record has added normalized fields:

- `doc_id_str`
- `other_doc_id_str`
- `relationship_raw`
- `relationship_canonical`
- `relationship_group`
- `source_in_metadata`
- `target_in_metadata`
- `external_target`
- `edge_quality_flags`
- `edge_keep_status`

### 7.3 External Stub Fields

Each external stub has:

- `id_str`
- `is_external_stub`
- `missing_metadata`
- `citation_safe`
- `dataset_tier`
- `source`
- `quality_flags`

## 8. Final Dataset Usage Guidance

### 8.1 Use for Vector Retrieval

Use `metadata_final.jsonl` as the metadata source for indexing and retrieval.

Recommended default indexing:

- prioritize `dataset_tier=primary`;
- keep `dataset_tier=reference` in a separate or lower-priority index;
- preserve `citation_label`, `validity_group`, `dataset_tier`, and `quality_flags` in chunk metadata;
- do not use `metadata_quarantine.jsonl` for production retrieval;
- do not cite external stubs.

### 8.2 Use for Relationship/Graph Retrieval

Use `relationships_final.jsonl` as the clean relationship source.

Recommended default handling:

- use `relationship_canonical` and `relationship_group`, not raw labels, for downstream logic;
- treat `related_to` as weak context;
- treat external targets as non-citation-safe;
- do not use `relationships_quarantine.jsonl` for production traversal;
- use quarantine files only for audit, debugging, or recovery.

## 9. Acceptance Criteria Status

| Criterion | Status |
| --- | --- |
| Raw fields preserved | Passed |
| Metadata normalized fields added | Passed |
| Relationship normalized fields added | Passed |
| Metadata tiers assigned | Passed |
| Validity groups assigned | Passed |
| Exact duplicate relationship edges removed from final relationships | Passed |
| Self-loops removed from final relationships | Passed |
| Quarantine files generated | Passed |
| External stubs generated for missing targets | Passed |
| Preprocessing report generated | Passed |

## 10. Final Recommendation

The dataset finalization step is complete.

The finalized dataset package is suitable for handoff to vector retrieval and relationship/graph retrieval teammates:

- `metadata_final.jsonl` should be used as the main cleaned legal metadata corpus.
- `relationships_final.jsonl` should be used as the cleaned relationship corpus.
- `metadata_external_stubs.jsonl` should be used only if missing-target connectivity is needed.
- Quarantine files should not be used in production retrieval.
- External stubs should not be used as citation evidence.

The final dataset is aligned with `SPEC.md` because it preserves source metadata, supports citation display, separates primary/reference records, removes noisy relationship edges, and provides clean normalized fields for retrieval and downstream graph construction.
