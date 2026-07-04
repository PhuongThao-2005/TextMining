# SPEC_Text Structuring.md

## 1. Purpose

This document specifies the text structuring stage for the G-LRAG pipeline.

The stage converts finalized legal documents into:

```text
Document -> Legal Unit -> Chunk
```

For article-based documents, the preferred path is:

```text
Document -> Điều / Article -> Chunk
```

The output must preserve legal structure, prevent text loss, and attach enough metadata for retrieval, citation, graph alignment, and debugging.

## 2. Core Requirements

- Run on the full `metadata_final.jsonl`.
- Every metadata record must appear in `documents_structured.jsonl`.
- Missing, empty, too-short, and parse-error documents must be tracked, not silently dropped.
- Parse usable text into legal units before chunking.
- Treat `article` / `Điều` as the preferred semantic retrieval unit.
- Preserve non-article text such as preambles, sections, items, and attachments.
- Short `Điều` units must be preserved and may become single chunks.
- Chunk inside each legal unit; chunks must not cross article boundaries in normal mode.
- Every chunk must have a parent legal unit, citation metadata, and deterministic ID.

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `metadata_final.jsonl` | Authoritative finalized metadata |
| Full text source, e.g. `content_html`, cleaned text files, or extracted text records | Full document text when available |
| `relationships_final.jsonl` | Optional graph alignment input |

Join metadata and full text by `id_str` whenever possible.

### Outputs

Recommended output directory:

```text
data/processed/text_structuring/
```

| Output | Purpose |
| --- | --- |
| `documents_structured.jsonl` | One tracking record per metadata record |
| `legal_units.jsonl` | Canonical structured text units |
| `chunks.jsonl` | Retrieval chunks |
| `articles.jsonl` | Optional view for `unit_type = article` |
| `text_structuring_report.md` | Counts, warnings, coverage, and quality report |

`legal_units.jsonl` is canonical. `articles.jsonl` is optional and must not replace it.

## 4. Legal Unit Model

Valid `unit_type` values:

| Unit type | Meaning |
| --- | --- |
| `preamble` | Text before the first legal unit |
| `article` | A legal `Điều` |
| `attachment_preamble` | Intro text inside an attachment |
| `section` | Fallback section, for example `I.`, `II.` |
| `item` | Fallback numbered item, for example `1.`, `2.` |
| `document` | Whole-document fallback |

Fallback order when no reliable `Điều` structure exists:

1. Roman section headings, such as `I.`, `II.`, `III.`
2. Numbered item headings, such as `1.`, `2.`, `3.`
3. Whole-document fallback

Attachments and appended regulations must not be dropped. Examples include `PHỤ LỤC`, `QUY CHẾ`, `ĐIỀU LỆ`, `DANH MỤC`, and `MẪU SỐ`. If an attachment contains its own `Điều`, those articles may be parsed under the attachment context. Ambiguous headings must not cut an article unconditionally.

Duplicate article numbers in the same document must still produce unique `unit_id` values.

## 5. Required Schemas

Every legal unit and chunk must preserve these key fields from `metadata_final.jsonl`:

- `id_str`, `title_clean`, `citation_label`
- `loai_van_ban_canonical`, `so_ky_hieu_clean`
- `co_quan_ban_hanh_canonical`
- `ngay_ban_hanh_iso`, `ngay_co_hieu_luc_iso`, `ngay_het_hieu_luc_iso`
- `issue_year`, `tinh_trang_hieu_luc_canonical`
- `validity_group`, `dataset_tier`
- `pham_vi_canonical`, `nganh_canonical`, `linh_vuc_canonical`
- `quality_flags_document`

### Document Record

Each `documents_structured.jsonl` record must include:

- `doc_id`, `id_str`
- `title_clean`, `citation_label`
- `loai_van_ban_canonical`, `so_ky_hieu_clean`
- `co_quan_ban_hanh_canonical`
- `ngay_ban_hanh_iso`, `ngay_co_hieu_luc_iso`, `ngay_het_hieu_luc_iso`
- `issue_year`, `tinh_trang_hieu_luc_canonical`
- `validity_group`, `dataset_tier`
- `pham_vi_canonical`, `nganh_canonical`, `linh_vuc_canonical`
- `quality_flags_document`
- `source_text_path`, `source_text_hash`
- `text_char_count`, `legal_unit_count`, `article_count`, `chunk_count`
- `coverage_ratio`, `reconstruction_exact`, `reconstructed_text_hash`
- `structuring_status`, `parse_confidence`, `quality_flags`

Allowed `structuring_status` values:

- `structured_by_article`
- `structured_by_fallback_units`
- `document_fallback`
- `missing_full_text`
- `empty_text`
- `text_too_short`
- `parse_error`

### Legal Unit Record

Each `legal_units.jsonl` record must include:

- `unit_id`, `doc_id`, `id_str`
- `unit_type`, `unit_index`, `unit_number`
- `unit_heading`, `unit_title`
- `article_number`, `article_title`
- `section_path`
- `raw_unit_text`, `unit_text`, `full_text`, `retrieval_text`
- `unit_char_count`, `unit_token_estimate`, `chunk_count`
- `start_char`, `end_char`
- `source_text_path`, `parse_confidence`, `quality_flags`
- the key document metadata listed above

Recommended IDs:

```text
{id_str}::article::{article_number}
{id_str}::{unit_type}::{unit_index}
```

If duplicate article numbers occur, append `::idx::{unit_index}`.

### Chunk Record

Each `chunks.jsonl` record must include:

- `chunk_id`, `parent_unit_id`
- `doc_id`, `id_str`
- `unit_type`, `unit_index`, `unit_heading`
- `article_number`, `article_title`, `section_path`
- `chunk_index_in_unit`, `chunk_index_global`, `chunk_count_in_unit`
- `chunk_text`, `retrieval_text`
- `chunk_char_count`, `chunk_token_estimate`
- `citation_anchor`
- `start_char`, `end_char`
- `structure_level`, `article_detected`
- `unit_split`, `multi_unit_chunk`
- `source_text_path`, `quality_flags`
- `text_structuring_version`
- the key document metadata listed above

Recommended chunk ID:

```text
{parent_unit_id}::chunk::{chunk_index_in_unit}
```

Text field meanings:

- `chunk_text`: clean content of the chunk.
- `retrieval_text`: chunk text plus retrieval context such as document title, citation label, legal path, article heading, and validity metadata.

## 6. Chunking Policy

- Chunk inside each legal unit.
- Keep short units as one chunk.
- Split long units by clauses or numbered paragraphs when possible.
- Otherwise use paragraph-aware token windows.
- Recommended target size: `700-1,000` tokens.
- Recommended hard max: `1,200` tokens.
- Recommended overlap: `100-150` tokens.
- Mark split chunks with `unit_split = true`.
- Mark fallback chunks with `article_detected = false`, `unit_type`, `structure_level`, and `quality_flags`.
- Each chunk must include `parent_unit_id`, deterministic `chunk_id`, `citation_anchor`, `chunk_text`, `retrieval_text`, chunk indexes, offsets, and quality flags.

Citation anchor format:

```text
{citation_label}, Điều {article_number}: {article_title}
{citation_label}, {attachment_context}, {unit_heading}
{citation_label}, {unit_type} {unit_index}, đoạn {chunk_index_in_unit}
```

## 7. Validation and Report

### Full Coverage Counts

`text_structuring_report.md` must include:

- `total_metadata_records`
- `matched_full_text_documents`
- `missing_full_text_documents`
- `empty_or_too_short_text_documents`
- `structured_documents`
- `fallback_documents`
- `parse_error_documents`

Definitions:

- `structured_documents`: documents with reliable article-based structure.
- `fallback_documents`: documents structured by section, item, or whole-document fallback.

Required identity:

```text
total_metadata_records
= structured_documents
+ fallback_documents
+ empty_or_too_short_text_documents
+ missing_full_text_documents
+ parse_error_documents
```

### No Text Loss Checks

For every usable-text document, validate:

- no unexpected overlap between legal units;
- no long uncovered gaps;
- `coverage_ratio` is computed;
- `reconstruction_exact` is computed;
- `source_text_hash` and `reconstructed_text_hash` are stored when possible.

Required report sections:

- legal unit counts by `unit_type`;
- chunk counts and token statistics;
- parse confidence distribution;
- top warning reasons;
- coverage and reconstruction results;
- examples of failed or low-confidence documents.

Hard acceptance metrics:

```text
coverage_failed_documents == 0 for usable-text documents
duplicate_unit_id == 0
duplicate_chunk_id == 0
all chunks have parent_unit_id
all chunks have non-empty chunk_text
all chunks have citation-ready citation_anchor
every unit and chunk preserves key document metadata
```

## 8. Retrieval and Graph Guidance

Vector retrieval should index `chunks.jsonl`.

Retrieval should:

- retrieve at chunk level;
- use `parent_unit_id` for same-unit expansion;
- use `doc_id` / `id_str` for metadata and graph joins;
- use `citation_anchor` for answer citations;
- rank/filter by `dataset_tier`, `validity_group`, `unit_type`, `parse_confidence`, and `quality_flags`;
- prefer `primary` and `active` chunks for current-law questions;
- allow `reference` and expired chunks for historical, lineage, amendment, or validity questions.

Graph alignment may create:

| Edge | Meaning |
| --- | --- |
| `DOCUMENT_HAS_UNIT` | Document contains legal unit |
| `UNIT_HAS_CHUNK` | Legal unit contains chunk |
| `CHUNK_NEXT` | Next chunk in same legal unit |
| `UNIT_NEXT` | Next legal unit in same document |

## 9. Processing Flow

1. Load `metadata_final.jsonl`.
2. Load or join full text source by `id_str`.
3. Create one `documents_structured.jsonl` record for every metadata record.
4. For usable text, normalize text while preserving line boundaries.
5. Parse text into legal units.
6. Validate coverage and reconstruction.
7. Chunk each legal unit independently.
8. Attach metadata, IDs, offsets, quality flags, and citation anchors.
9. Write output files and report.

## 10. Acceptance Criteria

| Criterion | Status |
| --- | --- |
| Full `metadata_final.jsonl` coverage is reported | Required |
| Missing/empty/too-short/error text records are tracked | Required |
| Usable documents are parsed into legal units | Required |
| `Điều` / article units are preferred when available | Required |
| Preambles, fallback units, and attachments are preserved | Required |
| Chunks stay inside parent legal units | Required |
| Chunks do not cross article boundaries in normal mode | Required |
| Every chunk has `parent_unit_id` | Required |
| Every unit and chunk preserves key document metadata | Required |
| Every chunk has deterministic `chunk_id` | Required |
| Every chunk has citation-ready `citation_anchor` | Required |
| No usable text is silently dropped | Required |
| Coverage and reconstruction checks are reported | Required |
| `text_structuring_report.md` is generated | Required |
