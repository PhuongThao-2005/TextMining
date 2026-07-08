# Pre-Processing Phase Report — Producing the v2 Dataset

| Field | Value |
| --- | --- |
| Subject | How `scripts/build_dataset_v2.py` transforms raw scrape into the v2 dataset package |
| Pipeline version | 2.0.0 |
| Entry point | [`build_dataset_v2.py`](../scripts/build_dataset_v2.py:53) |
| Pipeline package | [`src/data/pipeline/`](../src/data/pipeline/) |
| Output package | `Project/data/v2/` |
| Source-of-truth spec | [`Dataset_SPEC_v2.md`](../Dataset_SPEC_v2.md) |
| Stats basis | [`reconciliation_report.md`](../data/v2/reconciliation_report.md) generated 2026-07-06 |

---

## 1. Purpose and shape of the phase

The pre-processing phase turns three raw JSONL scrapes into a legal-retrieval-ready
dataset organized as four layers. The controlling idea (Dataset_SPEC_v2 §2) is a single
identity space that every artifact joins on:

```
id_str  (document)  →  unit_id  (provision / citation unit)  →  chunk_id  (embedding unit)
```

A vector hit on a `chunk_id` resolves up to a citable provision (`unit_id`) and its
document (`id_str`) with no ID translation, and the graph, validity, and authority
overlays all key off those same IDs.

### 1.1 Inputs (Layer 0 — RAW)

Located in `Project/data/untracked_data/`, resolved in [`config.py`](../src/data/pipeline/config.py:18):

| File | Grain | Role |
| --- | --- | --- |
| `metadata.jsonl` | one legal document | titles, types, dates, issuer, validity status |
| `relationships.jsonl` | one directed relationship | amends / replaces / guides / cites edges |
| `content.jsonl` | one HTML fragment (1-to-many per doc) | `content_html` body text (~4 GB) |

### 1.2 Outputs (Layer 1–3 + AUDIT)

Written to `Project/data/v2/`:

```
Layer 1  NORMALIZED   documents.jsonl · edges.jsonl · external_stubs.jsonl · authority_index.jsonl · vocabularies/*.json
Layer 2  STRUCTURED   text_provenance.jsonl · provisions.jsonl · chunks.jsonl
Layer 3  DERIVED      validity_timeline.jsonl
AUDIT                 documents_quarantine.jsonl · edges_quarantine.jsonl · reconciliation_report.md
```

---

## 2. Orchestration — the four-step run

[`main()`](../scripts/build_dataset_v2.py:53) runs the layers end to end and passes state
forward through an in-memory `NormalizeResult` carrier so later layers reuse Layer 1's
decisions instead of re-reading raw files:

```
[1/4] normalize.run()   → NormalizeResult (final_ids, doc_meta, counts)
[2/4] structure.run(norm, limit) → provenance + provisions + chunks
[3/4] derive.run(collect_doc_dates())  → validity_timeline
[4/4] report.write(norm.counts, struct_counts, derive_counts) → reconciliation_report.md
```

Flags: `--limit N` structures only N documents (smoke test); `--skip-text` runs Layers 1
and 3 only. Before running, `main()` hard-fails if any of the three raw inputs are
missing. `stdout` is forced to UTF-8 so Vietnamese progress lines never crash a Windows
console.

Everything is line-streamed through [`io_utils`](../src/data/pipeline/io_utils.py:26)
(`read_jsonl` + context-managed `JsonlWriter`) because `content.jsonl` never fits in
memory. All text is NFC-normalized and whitespace-collapsed by
[`clean_text()`](../src/data/pipeline/io_utils.py:62) at every entry point.

---

## 3. Layer 1 — NORMALIZED (documents, edges, stubs)

Implemented in [`normalize.run()`](../src/data/pipeline/normalize.py:62). Two streaming
passes plus derived side-tables.

### 3.1 Pass 1 — metadata → documents / quarantine

For each raw metadata row:

1. **Clean + canonicalize.** `id`, title, `so_ky_hieu`, issuer are cleaned; `loai_van_ban`
   is mapped through `TYPE_MAP` (e.g. `"Nghị Quyết"` → `"Nghị quyết"`, empty → `unknown_type`).
2. **Dates** parsed `dd/mm/YYYY` → ISO via [`parse_date()`](../src/data/pipeline/normalize.py:26); `"..."` and bad formats become nulls / flags.
3. **Validity split (D2).** Raw `tinh_trang_hieu_luc` maps through `STATUS_TO_GROUP` into a
   `validity_group` plus a `currency_hint` that is explicitly marked non-authoritative
   (`currency_hint_authoritative: false`) — the stored label is a hint, not truth.
4. **Authority rank (D3).** `loai_van_ban` → integer `legal_authority_rank` via
   `AUTHORITY_RANK` (1 = Hiến pháp … 6 = Thông tư … 99 = unknown), independent of currency.
5. **Controlled vocab (D4).** Issuer, field, sector, scope are each encoded to a
   `{code, surface, raw}` triple via [`vocab.py`](../src/data/pipeline/vocab.py:55).
6. **Quality flags vs. exclusion reasons.** A flag annotates but keeps a record; a *reason*
   quarantines it. Missing `id`, `title`, or `so_ky_hieu`, `unknown_type`, unsupported type,
   `future_issue_date` are quarantine reasons. Kept records land in `documents.jsonl`; the
   rest go to `documents_quarantine.jsonl` with `exclusion_reasons`. **Nothing is deleted.**

Kept `id_str`s are recorded in `final_ids`, and a slim `doc_meta` (title, label, type, rank,
validity, flags) is cached for Layer 2 so the text stage never rereads metadata.

### 3.2 Pass 2 — relationships → edges / quarantine / stubs

For each raw relationship (D5, direction correctness):

1. Map raw label through `REL_MAP` → `(rel_canonical, rel_group, inverse)`.
2. **Direction normalization.** When `inverse` is true the edge is flipped so `src REL dst`
   always reads active voice ("A amends B"). `direction_normalized` records the flip.
3. **Direction sign-off.** `DIRECTION_VERIFIED_GROUPS` marks which groups are reviewed.
   `basis, citation, guidance, amendment, supplement, related` are verified; **`validity` and
   `suspension` are `false`** (pending manual sign-off flagged in report.md P1). Unverified
   edges get a `direction_unverified` flag but are still emitted.
4. **Referential integrity.** Missing/self-loop/duplicate/unmapped edges are quarantined.
   A target `b` absent from all raw IDs becomes an **external stub** (`external_target`),
   counted for later emission; a target that exists but was quarantined flags `target_quarantined`.

Kept edges → `edges.jsonl`; excluded → `edges_quarantine.jsonl`. Referenced-but-missing
targets are emitted once each to `external_stubs.jsonl` with `citation_safe: false`.

### 3.3 Side-tables

- `authority_index.jsonl` — the versioned doc-type → rank table (Layer 3 static input).
- `vocabularies/*.json` — the four observed vocab tables dumped for human review.

---

## 4. Layer 2 — STRUCTURED (the article/chunk core)

Implemented in [`structure.run()`](../src/data/pipeline/structure.py:99). This is the phase
that produces "articles and chunks."

### 4.1 The memory-safe join

`content.jsonl` is ~4 GB and 1-to-many, so the code never loads it. Instead
[`build_offset_index()`](../src/data/pipeline/structure.py:37) makes **one streaming pass**
recording `id → [byte offsets]`. Then for each kept document it `seek()`s to those offsets,
reads only that document's HTML fragments, and concatenates them **in file order** (the
deterministic merge for multi-row documents). Only one document's HTML is in memory at a time.

### 4.2 Per-document processing

For every `id_str` in `norm.doc_meta`:

```
offsets = index[id_str]
├─ row_count == 0            → text_provenance: text_status = "missing"      (skip)
├─ extracted chars < 40      → text_status = "too_short" / "empty"           (skip)
└─ otherwise                 → text_status = "available"  → parse → chunk
```

1. **HTML → text.** [`html_to_text()`](../src/data/pipeline/textutils.py:25) strips
   script/style, forces newlines around block tags so `Điều`/`khoản` headings start their
   own line, and normalizes whitespace while preserving line boundaries.
2. **Quality flags.** `multi_row_merged` when >1 content row; `table_heavy` when raw HTML
   contains `<table`. A SHA-1 of the concatenated raw HTML is stored as `raw_html_hash`.
3. **Parse into provisions.** [`parse_units()`](../src/data/pipeline/textutils.py:83) splits
   the text into legal units with a preference cascade:
   - **`structured_by_article`** — ≥1 line matches `Điều <n>`; text before the first article
     is a `preamble`, `PHỤ LỤC`/`QUY CHẾ`/etc. become `attachment_preamble`.
   - **`structured_by_fallback_units`** — no articles, but ≥2 Roman-numeral sections or ≥3
     numbered items.
   - **`document_fallback`** — no reliable structure; the whole document is one unit.
4. **Emit provision rows.** Each unit gets a deterministic
   `unit_id = {id_str}::{unit_type}::{number|index}` (with `::idx::` suffix on collisions),
   a `citation_anchor` (e.g. *"Luật …, Điều 11: heading"*), char offsets, token estimate,
   `chunk_count`, and denormalized document metadata (title, rank, validity). Provisions are
   the citation/graph anchor and **carry no embedding**.
5. **Split each provision into chunks.** [`split_into_chunks()`](../src/data/pipeline/textutils.py:164):
   - Units ≤ `CHUNK_MAX_CHARS` (1200 tok × 4 = 4800 chars) stay a single chunk.
   - Longer units split on clause markers (`1.`, `2.`, …) when ≥2 exist, targeting
     ~900 tokens; any still-oversized segment falls back to a paragraph-aware sliding window
     with ~130-token overlap. Chunks never cross the provision boundary.
6. **Emit chunk rows (slim by design).** Each chunk carries only join keys + intrinsic fields
   (`chunk_id = {unit_id}::chunk::{k}`, `parent_unit_id`, `id_str`, index/count, `chunk_text`,
   char/token counts, offsets, `unit_split`). `retrieval_text` and display/authority metadata
   are **not** stored — they are reassembled at embed time from the parent provision and
   document (Dataset_SPEC_v2 §4.2), which keeps `chunks.jsonl` at roughly a third of the size.
7. **Provenance record.** Every document (available, missing, or too-short) gets one
   `text_provenance.jsonl` row — the text analogue of quarantine: track, never drop.

---

## 5. Layer 3 — DERIVED (validity timeline)

Implemented in [`derive.run()`](../src/data/pipeline/derive.py:17). Validity is computed, not
stored. It streams `edges.jsonl`, keeps only edges whose `rel_canonical` maps through
`VALIDITY_EVENT_MAP` (`replaces → replaced`, `amends → amended`, `suspends → suspended`,
plus the partial variants), and emits one event per qualifying edge:

- The **`dst_id`** is the affected document; the **`src_id`** is the counterparty.
- The event is dated from the counterparty's effective date (falling back to issue date),
  pulled from the `doc_dates` map [`collect_doc_dates()`](../scripts/build_dataset_v2.py:42)
  built from Layer 1 output.
- Each event records its `source_edge_id` (provenance) and the edge's `direction_verified`
  flag, so downstream consumers can refuse to trust events derived from unverified-direction
  edges.

---

## 6. Layer 4 — AUDIT (reconciliation)

[`report.write()`](../src/data/pipeline/report.py:19) proves the core acceptance criteria and
writes `reconciliation_report.md`. The two reconciliation identities it enforces:

- **documents:** `raw == final + quarantine`
- **edges:** `raw == final + quarantine`

plus text-coverage totals, provision/chunk linkage, and the direction sign-off status.

---

## 7. Final output statistics

Taken from the shipped [`reconciliation_report.md`](../data/v2/reconciliation_report.md)
(generated 2026-07-06, pipeline 2.0.0).

### 7.1 Reconciliation identities — both hold

| Identity | Check | Holds |
| --- | --- | :---: |
| documents | 153,420 == 151,624 + 1,796 | ✅ |
| edges | 897,890 == 883,256 + 14,634 | ✅ |

### 7.2 Layer 1 — NORMALIZED

| Metric | Count |
| --- | ---: |
| metadata_raw | 153,420 |
| documents_final | 151,624 |
| documents_quarantine | 1,796 |
| relationships_raw | 897,890 |
| edges_final | 883,256 |
| edges_quarantine | 14,634 |
| external_stubs | 19,763 |
| authority_index rows | 28 |

Roughly **98.8%** of documents and **98.4%** of edges pass normalization; the rest are
quarantined (not dropped) with reasons.

### 7.3 Layer 2 — STRUCTURED

| Metric | Count |
| --- | ---: |
| documents_seen | 151,624 |
| text_available | 127,018 |
| text_missing | 5,025 |
| text_too_short | 19,581 |
| content_rows_joined | 175,682 |
| status_structured_by_article | 108,570 |
| status_structured_by_fallback_units | 13,443 |
| status_document_fallback | 5,005 |
| text_provenance rows | 151,624 |
| **provisions_final** | **1,386,267** |
| **chunks_final** | **1,513,376** |

Interpretation:

- **Text coverage.** Of 151,624 kept documents, **127,018 (83.8%)** produced usable text;
  5,025 had no content row (`missing`); 19,581 were below the 40-char usable threshold
  (`too_short`/`empty`). Every one of the 151,624 has a provenance record — full accounting.
- **Structure quality.** Among documents with text, **85.5% parsed by article** (`Điều`),
  10.6% via Roman/numbered fallback, and only ~3.9% fell back to whole-document. This means
  the vast majority of citable units are true legal articles.
- **Chunking.** 1.39M provisions expanded to 1.51M chunks — an **average of 1.09 chunks per
  provision**. Most Vietnamese articles fit inside one embedding window; only long articles
  split, which matches the "keep short articles whole, split long ones" policy.

### 7.4 Layer 3 — DERIVED

| Metric | Count |
| --- | ---: |
| validity_events | 159,805 |
| events_direction_verified | 34,379 |
| events_direction_unverified | 125,426 |

**78.5%** of validity events come from the `validity`/`suspension` edge groups whose
direction is not yet signed off. They are emitted and flagged, but must not be treated as
production-ready until the manual review (report.md P1) completes. This is the honest,
surfaced dependency called out in Dataset_SPEC_v2 §8.2 and §12.

### 7.5 Controlled vocabularies (D4)

| Vocabulary | Codes | Raw forms |
| --- | ---: | ---: |
| issuing_authority | 472 | 550 |
| legal_field | 1,635 | 1,671 |
| sector | 765 | 765 |
| scope | 392 | 416 |

The gap between raw forms and codes (e.g. 550 → 472 authorities) is exactly the facet
de-fragmentation D4 targets: surface variants of one issuer collapse to a single `code`.

### 7.6 Acceptance criteria

| Criterion | Result |
| --- | --- |
| documents raw == final + quarantine | PASS |
| edges raw == final + quarantine | PASS |
| every kept document has a text_provenance record (151,624 == 151,624) | PASS |
| validity edges carry direction_verified flag | PASS |
| validity direction signed off | **PENDING (report P1)** |

---

## 8. End-to-end flow summary

```
metadata.jsonl ─┐
                ├─[1] normalize ─▶ documents.jsonl · edges.jsonl · external_stubs.jsonl
relationships ──┘                   authority_index.jsonl · vocabularies/*.json
                                          │ (final_ids + doc_meta carried in memory)
content.jsonl ──────[2] structure ─▶ text_provenance.jsonl
   (byte-offset index,               provisions.jsonl  (citation unit, unit_id)
    seek per doc, HTML→text,         chunks.jsonl      (embedding unit, chunk_id)
    parse Điều, split chunks)
edges.jsonl ────────[3] derive ────▶ validity_timeline.jsonl (events, source_edge_id)
all counts ─────────[4] report ────▶ reconciliation_report.md
```

The single join chain that the whole design exists to enable:

`chunk (vector hit) → parent_unit_id (provision) → id_str (document) → edges (graph) →
validity_timeline (still in force?) + authority_index (how authoritative?) → answer cited at
the provision level.`

### Key numbers at a glance

- **151,624** documents kept from 153,420 raw (1,796 quarantined, reversible).
- **883,256** direction-normalized edges + **19,763** external stubs.
- **127,018** documents with usable clause text (83.8% coverage), 85.5% parsed by `Điều`.
- **1,386,267** citable provisions → **1,513,376** embeddable chunks (1.09 avg).
- **159,805** validity events, 78.5% still gated on edge-direction sign-off.
