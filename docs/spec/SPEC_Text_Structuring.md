# SPEC_Text_Structuring.md

> **v2-aligned.** This spec matches the dataset actually produced by the v2 pipeline (`Dataset_SPEC_v2.md`, `src/data/pipeline/`). The pre-v2 version is archived at `docs/archive/SPEC_Text Structuring.md`. Key changes from the archived version are called out in §12.

## 1. Purpose

This document specifies the text structuring stage for the G-LRAG pipeline.

In v2 the text-structuring work is **owned by the dataset layer** and emitted as Layer 2 artifacts (`Dataset_SPEC_v2.md` §3–§4). This spec is therefore both the contract those artifacts satisfy and the reference the graph (`SPEC_Knowledge_Graph.md`) and vector-retrieval (`SPEC_Vector_Retrieval.md`) teams consume.

The stage converts finalized legal documents into a two-level hierarchy:

```text
Document ──has many──▶ Provision (Điều / citation unit) ──has many──▶ Chunk (embedding unit)
   id_str                    unit_id                                     chunk_id
```

Two levels, not three. v2 renames the old `LegalUnit` level to **Provision** and drops the flat denormalized model: a provision is the *citable* unit (what a lawyer cites, what the graph reasons over); a chunk is the *embeddable* unit (what the vector store indexes). The output must preserve legal structure, prevent text loss, and carry enough join keys for retrieval, citation, graph alignment, and debugging — without duplicating document metadata onto every row.

## 2. Core Requirements

- Run over the full normalized corpus: every `id_str` in `documents.jsonl` (plus the audit total of 153,420 metadata records) must be accounted for in `text_provenance.jsonl`.
- Missing, empty, too-short, and extraction-failed documents must be tracked in `text_provenance.jsonl`, not silently dropped.
- Text arrives as HTML in `content.jsonl` and is a **1-to-many** source (178,665 rows / 149,051 unique IDs). Group content rows by `id` and merge deterministically **before** structuring, recording `content_row_count` and the `multi_row_merged` flag; otherwise offsets and reconstruction are wrong.
- Parse usable text into provisions before chunking.
- Treat `article` / `Điều` as the preferred citation/retrieval unit.
- Preserve non-article text: preambles, sections, items, attachments (`PHỤ LỤC`, `QUY CHẾ`, `ĐIỀU LỆ`, `DANH MỤC`, `MẪU SỐ`).
- Short provisions are preserved and may become a single chunk.
- Chunk **inside** each provision; chunks must not cross article boundaries in normal mode.
- Every chunk has a parent provision (`parent_unit_id`), a document (`id_str`), and a deterministic `chunk_id`.
- **Slim chunk rows.** Chunks carry only join keys and chunk-intrinsic fields. No `retrieval_text`, no denormalized document/authority metadata, no `text_structuring_version`. Citation and display facts live once, on the provision and document, and are joined at read/embed time.
- Duplicate article numbers in the same document must still produce unique `unit_id` values.

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `data/v2/documents.jsonl` | Authoritative normalized document metadata (join by `id_str`) |
| `content.jsonl` (`content_html`) | Raw HTML body text, 1-to-many by `id` |
| `data/v2/edges.jsonl` | Optional graph-alignment input |

Join metadata and full text by `id_str` (`content.id` stringified).

### Outputs

Output directory: `data/v2/`.

| Output | Purpose |
| --- | --- |
| `provisions.jsonl` | Citation units (one row per Điều/provision); full clause text lives here |
| `chunks.jsonl` | Embedding units (one or more rows per provision); slim join keys + `chunk_text` |
| `text_provenance.jsonl` | One tracking record per `id_str`, including missing text |
| `reconciliation_report.md` | Counts, coverage, quality, and reconciliation checks |

`provisions.jsonl` is canonical for citation; `chunks.jsonl` is canonical for retrieval. There is no separate `articles.jsonl` view in v2 (query `provisions.jsonl` where `unit_type = "article"`).

## 4. Provision Model

Observed `unit_type` values in v2 output:

| Unit type | Meaning |
| --- | --- |
| `preamble` | Text before the first provision |
| `article` | A legal `Điều` (preferred citation unit) |
| `section` | Fallback section heading (`I.`, `II.`) |
| `item` | Fallback numbered item (`1.`, `2.`) |
| `attachment_preamble` | Intro text inside an attachment |
| `document` | Whole-document fallback |

Fallback order when no reliable `Điều` structure exists: (1) Roman section headings, (2) numbered item headings, (3) whole-document fallback. Attachments must not be dropped; if an attachment contains its own `Điều`, those articles may be parsed under the attachment context. Ambiguous headings must not cut an article unconditionally.

## 5. Required Schemas

### 5.1 `text_provenance.jsonl` — one record per `id_str`

```text
id_str
content_row_count       # content.jsonl rows joined (0 for missing text)
text_source             # content_html | none
raw_html_hash           # hash of the concatenated, ordered raw HTML
extracted_char_count    # chars after HTML→text extraction
extraction_method       # parser + version, e.g. "bs4+lxml+cleanrules@1"
html_quality_flags[]    # e.g. multi_row_merged, table_heavy, boilerplate_detected
text_status             # available | missing | empty | too_short | extraction_failed
structuring_status      # see values below
legal_unit_count        # provisions produced for this document
chunk_count             # chunks produced for this document
```

Allowed `structuring_status` values:

- `structured_by_article`
- `structured_by_fallback_units`
- `document_fallback`
- `missing_full_text`
- `empty_text`
- `text_too_short`
- `parse_error`

Note the v2 split: `text_status` tracks whether usable text exists; `structuring_status` tracks how it was structured. These are two separate fields, not one.

### 5.2 `provisions.jsonl` — the citation unit

```text
unit_id             # deterministic: "{id_str}::{unit_type}::{index}"  e.g. "72::article::1"
id_str              # parent document → join to documents.jsonl
unit_type           # preamble | article | section | item | attachment_preamble | document
article_number      # Điều number when unit_type = article, else null
unit_heading        # heading text, or null
path                # hierarchical path, e.g. "preamble" or "Chương II > Điều 11"
citation_anchor     # human-readable citation string (see §6)
char_start, char_end
unit_char_count
unit_token_estimate
chunk_count         # how many chunks this provision was split into
coverage_verified   # bool — provision text reconciles against source

# denormalized display fields kept on the provision (join convenience for citation):
title
citation_label
loai_van_ban
so_ky_hieu
legal_authority_rank
validity_group
currency_hint
quality_flags[]     # metadata quality flags inherited from documents.jsonl
```

The provision is where document display/authority metadata is denormalized (a small, bounded set of rows). Chunks do **not** repeat it.

### 5.3 `chunks.jsonl` — the embedding unit (SLIM)

```text
chunk_id                    # deterministic: "{unit_id}::chunk::{k}"  e.g. "72::article::1::chunk::1"
parent_unit_id              # the provision  → join to provisions.jsonl
id_str                      # parent document → join to documents.jsonl
chunk_index_in_unit         # 1, 2, 3 … position within the provision
chunk_count_in_unit         # total chunks in the parent provision
chunk_text                  # clean chunk text — the embeddable payload (what the LM sees)
chunk_char_count
chunk_token_estimate
char_start, char_end        # offsets within the source
unit_split                  # bool — was the parent provision split into multiple chunks
structuring_quality_flags[] # e.g. article_detected_false
```

Exactly 12 fields. **Deliberately excluded** (recover by join, not by copy):

| Excluded field | Recover via |
| --- | --- |
| `retrieval_text` | Built at embed time from provision + document (§6, `SPEC_Vector_Retrieval.md` §2) |
| `citation_anchor`, `article_number`, `unit_type`, `path` | `parent_unit_id` → `provisions.jsonl` |
| `title`, `citation_label`, `validity_group`, `legal_authority_rank`, all faceted metadata | `id_str` → `documents.jsonl` |
| `text_structuring_version` | Dropped entirely (tracked in the build report, not per row) |

Field-naming policy:

- `quality_flags` (on documents/provisions) = metadata quality flags inherited from `documents.jsonl`, unchanged.
- `structuring_quality_flags` (on chunks) = warnings/errors from text matching, provision parsing, coverage validation, or chunking.
- The two are always distinct properties; never merge or rename them.

## 6. Chunking Policy and Citation Anchor

Chunking policy (implemented in `src/data/pipeline/structure.py`):

- Chunk inside each provision; never cross article boundaries in normal mode.
- Keep short provisions as one chunk.
- Split long provisions by khoản / numbered paragraphs when possible; otherwise use paragraph-aware token windows.
- Target size ~700–1,000 tokens; hard max ~1,200 tokens; overlap ~100–150 tokens.
- Mark split chunks with `unit_split = true`.
- Mark non-article chunks with `article_detected_false` in `structuring_quality_flags`.

**Citation anchor** lives on the provision (`provisions.jsonl.citation_anchor`), not on the chunk. Observed format:

```text
{citation_label}, {path}                 # e.g. "Sắc lệnh 103/SL, …, preamble 0"
{citation_label}, Điều {article_number}  # for unit_type = article
```

**`retrieval_text` (built at embed time, never stored):** the embedder resolves `parent_unit_id → provisions.jsonl` and `id_str → documents.jsonl` once, then builds a two-part value — an **identity header** (document `title` + `citation_label` + parent unit reference with its `unit_heading` title) followed by `chunk_text` — and encodes that. The header is semantic-identity text only; `legal_authority_rank`, `validity_group`, and the rule-based facets are **not** embedded (they live in the vector payload for filtering/ranking). This keeps the on-disk chunk slim while preserving the chunk's identity for semantic matching. Full template and rationale in `SPEC_Vector_Retrieval.md` §2 and §4 Step 2.

For this to work, the provision's `unit_heading` must carry the article's title text where one exists (e.g. `"Điều 11. Quyền và nghĩa vụ…"`), not be left blank — it is the strongest per-unit topical signal in the header.

## 7. Validation and Report

`reconciliation_report.md` must include the coverage identity:

```text
total_metadata_records (153,420)
= structured_by_article
+ structured_by_fallback_units
+ document_fallback
+ missing_full_text
+ empty_text
+ text_too_short
+ parse_error
```

and the source reconciliation:

```text
sum(content_row_count) over provenance == 178,665   # content.jsonl rows
count(id_str with content_row_count > 0) == 149,051  # unique joined IDs
count(text_status = missing) == 6,563                # no-content tail
```

For every `text_status = available` document, validate: no unexpected overlap between provisions, no long uncovered gaps, `coverage_verified` computed, offsets stored.

Required report sections: provision counts by `unit_type`; chunk counts and token statistics; `structuring_status` distribution; top warning reasons; coverage results; examples of failed/low-confidence documents.

Hard acceptance metrics (verified on the full v2 run):

```text
every id_str has a text_provenance record            # 153,420
duplicate_unit_id  == 0
duplicate_chunk_id == 0                               # verified: 0 of 1,513,376
every chunk has a parent_unit_id resolving to a provision
every chunk has non-empty chunk_text                  # verified: 0 empty
every provision has chunk_count >= 1
every provision has a citation-ready citation_anchor
chunk rows carry exactly the 12 slim fields (§5.3)
```

Reference numbers from the full v2 build: 127,018 documents with text, 1,386,267 provisions, 1,513,376 chunks (avg ~1,826 B/row).

## 8. Retrieval and Graph Guidance

Downstream consumers should:

- Retrieve at chunk level from `chunks.jsonl`.
- Use `parent_unit_id` for same-unit expansion (fetch sibling chunks of the same provision).
- Use `parent_unit_id → provisions.jsonl` for the citation anchor, and `id_str → documents.jsonl` for document metadata and graph joins.
- Build `retrieval_text` at embed time (§6); never expect it in `chunks.jsonl`.
- Rank/filter by document-level `legal_authority_rank`, `validity_group`, `currency_hint`, and by `unit_type`, joined from the provision/document — not from the chunk row.

Graph alignment edge names (consumed by `SPEC_Knowledge_Graph.md`):

| Edge | Meaning | Why (derivable-from) |
| --- | --- | --- |
| `DOCUMENT_HAS_PROVISION` | Document contains provision | Containment (set membership). |
| `PROVISION_HAS_CHUNK` | Provision contains chunk | Containment; join key `parent_unit_id`. |
| `CHUNK_NEXT` | Next chunk in the same provision | **Reading order.** Powers same-provision expansion (§8, `SPEC_Vector_Retrieval.md` §4.5) — walk `#k → #k+1` to restore full-article context. Materialized convenience; *derivable* from `chunk_index_in_unit` under a shared `parent_unit_id`. |
| `PROVISION_NEXT` | Next provision in the same document | **Reading order.** Cross-article reading ("the preceding Article"). Materialized convenience; *derivable* from `char_start` under a shared `id_str`. |

Containment edges give set membership; the two `*_NEXT` edges add sequence. Both orderings are derivable from the fields above, so these edges are a precompute-vs-sort tradeoff, not new data — see `SPEC_Knowledge_Graph.md` §4.2.

## 9. Processing Flow

1. Load `documents.jsonl`; enumerate every `id_str`.
2. Join and group `content.jsonl` rows by `id`; merge deterministically; record `content_row_count` + `multi_row_merged`.
3. Emit one `text_provenance.jsonl` record per `id_str` (including `missing`).
4. For usable text, extract HTML→text preserving line boundaries.
5. Parse text into provisions; assign deterministic `unit_id`, `path`, `citation_anchor`.
6. Validate coverage; set `coverage_verified`.
7. Chunk each provision independently; emit slim chunk rows.
8. Write `provisions.jsonl`, `chunks.jsonl`, `text_provenance.jsonl`, and `reconciliation_report.md`.

## 10. Acceptance Criteria

| Criterion | Status |
| --- | --- |
| Full coverage reported against 153,420 metadata records | Required |
| Missing/empty/too-short/error text records tracked in `text_provenance.jsonl` | Required |
| Multi-row content merged deterministically with `multi_row_merged` flag | Required |
| Usable documents parsed into provisions; `article` preferred | Required |
| Preambles, fallback units, and attachments preserved | Required |
| Chunks stay inside parent provisions; no cross-article splits in normal mode | Required |
| Every chunk has `parent_unit_id` + `id_str` | Required |
| Chunk rows are slim (12 fields; no `retrieval_text`, no denormalized metadata, no version) | Required |
| Metadata `quality_flags` and `structuring_quality_flags` kept separate | Required |
| Every chunk has deterministic `chunk_id`; zero duplicates | Required |
| Every provision has citation-ready `citation_anchor` | Required |
| Coverage/reconciliation checks reported | Required |
| `reconciliation_report.md` generated | Required |

## 11. Open Items for the Team

1. **`retrieval_text` assembly contract** — the exact header format is owned by `SPEC_Vector_Retrieval.md` §2; any change requires re-embedding. Confirm before full indexing.
2. **`coverage_verified` semantics** — confirm the threshold used for marking a provision reconciled against source.
3. **Attachment article numbering** — confirm the `unit_id` scheme when an attachment carries its own `Điều` sequence that collides with the body.

## 12. Changes from the archived (pre-v2) spec

| Area | Archived spec | This v2 spec |
| --- | --- | --- |
| Hierarchy naming | `LegalUnit` | **Provision** (`DOCUMENT_HAS_PROVISION` / `PROVISION_HAS_CHUNK`) |
| Output files | `documents_structured.jsonl`, `legal_units.jsonl`, `chunks.jsonl`, `articles.jsonl` | `text_provenance.jsonl`, `provisions.jsonl`, `chunks.jsonl` (no separate `articles.jsonl`) |
| Chunk row | Fat: `retrieval_text`, denormalized metadata, `text_structuring_version` | **Slim**: 12 join-key + intrinsic fields only |
| `retrieval_text` | Stored per chunk | Built at embed time from provision + document |
| Status tracking | Single `structuring_status` | Split into `text_status` + `structuring_status` |
| Metadata field names | `title_clean`, `*_canonical`, `dataset_tier` | `title`, faceted `{code,surface,raw}`, `legal_authority_rank` + `validity_group` + `currency_hint` |
| IDs | `{id_str}::article::{article_number}` | `{id_str}::{unit_type}::{index}` and `{unit_id}::chunk::{k}` |
