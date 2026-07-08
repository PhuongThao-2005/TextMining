# 2026-07-06 — Implement the v2 dataset pipeline

## What was done

Implemented the layered v2 dataset contract from `Dataset_SPEC_v2.md` as a
runnable pipeline that turns the raw scrape (`metadata.jsonl`,
`relationships.jsonl`, `content.jsonl`) into the four-layer retrieval-ready
package under `Project/data/v2/`.

## New code

Package `Project/src/data/pipeline/`:

| Module | Responsibility |
| --- | --- |
| `config.py` | Paths, versions, chunking bounds, and the canonical mapping tables (type map, status→validity/currency, authority ranks, relationship canonicalization + verified-direction flags, validity-event map) |
| `io_utils.py` | Streaming JSONL read/write (UTF-8, `ensure_ascii=False`), `clean_text` NFC normalization |
| `vocab.py` | D4 controlled vocabularies — faceted fields become `{code, surface, raw}`; unmapped values flagged, never dropped |
| `textutils.py` | HTML→text (bs4+lxml), legal-unit parsing (article-preferred with section/item/document fallbacks), and chunk splitting (clause-aware, then paragraph windows) |
| `normalize.py` | Layer 1 — `documents.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `authority_index.jsonl`, `vocabularies/*.json` |
| `structure.py` | Layer 2 — `text_provenance.jsonl`, `provisions.jsonl` (citation unit), `chunks.jsonl` (embedding unit) |
| `derive.py` | Layer 3 — `validity_timeline.jsonl` from verified edges |
| `report.py` | AUDIT — `reconciliation_report.md` |

Orchestrator: `Project/scripts/build_dataset_v2.py` (`--limit N` smoke test,
`--skip-text` to run Layers 1+3 only).

## Key design decisions carried into code

- **Provision ≠ chunk.** `provisions.jsonl` is the citation unit (no embedding);
  `chunks.jsonl` is the embedding unit, each carrying `parent_unit_id` + `id_str`
  so a vector hit resolves up to a citable provision and document.
- **Slim chunk rows.** The first full run produced a bloated `chunks.jsonl`
  (~2,800 B/row): a stored `retrieval_text` (~45% of bytes) duplicated
  `chunk_text`, and every chunk denormalized the document's display/authority
  metadata. Fixed by dropping `retrieval_text` and that metadata from disk —
  chunks now carry only join keys + chunk-intrinsic fields (~1,100 B/row, ~2.5x
  smaller). `retrieval_text` is reassembled at embed time from
  `parent_unit_id → provisions.jsonl` and `id_str → documents.jsonl`, so
  display/citation/authority facts stay authoritative in one place.
- **4 GB `content.jsonl` is never fully loaded.** A one-pass byte-offset index
  (`id → [offsets]`) is built, then each document's HTML is seeked and merged in
  file order; only one document's text is in memory at a time. This handles the
  1-to-many content rows (178,665 rows / 149,051 unique ids) deterministically
  and flags `multi_row_merged`.
- **D5 verified direction.** The `validity` and `suspension` relationship groups
  are marked `direction_verified=false` (report.md P1 is unresolved), and every
  validity-timeline event derived from them inherits that flag so downstream
  consumers can refuse to trust them.
- **Windows/cp1252 console** is handled by reconfiguring stdout/stderr to UTF-8
  in the orchestrator; all data files are UTF-8 regardless of console codepage.

## Verification

- Layer 1 reconciles exactly with the known finalize numbers:
  documents 151,624 kept + 1,796 quarantined = 153,420 raw;
  edges 883,256 kept + 14,634 quarantined = 897,890 raw; external stubs 19,763.
- 300-document text smoke test: 0 duplicate `chunk_id`, 0 duplicate `unit_id`,
  0 orphan chunks, 0 empty `chunk_text`; split chunks correctly link to their
  parent provision.
- Full-corpus run (counts in `Project/data/v2/reconciliation_report.md`):
  127,018 documents with text, 5,025 missing, 19,581 too short;
  1,386,267 provisions and 1,513,376 chunks (1.09 chunks/provision);
  159,805 validity events (125,426 direction-unverified). All reconciliation
  identities PASS.
- Slim `chunks.jsonl` verified over all 1,513,376 rows: 0 duplicate `chunk_id`,
  0 empty `chunk_text`, exactly the 12 slim keys. File is **2.6 GB at ~1,826
  B/row** vs the pre-fix schema that was headed past 7 GB.

## How to run

```bash
cd Project
python scripts/build_dataset_v2.py            # full build
python scripts/build_dataset_v2.py --limit 500  # quick smoke test
```

Output package: `Project/data/v2/` (git-ignored like other data).
