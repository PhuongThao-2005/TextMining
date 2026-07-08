# Handoff — G-LRAG v2 Dataset & Specs

The v2 dataset is finalized and the three specs are rewritten to match it exactly.
Build against the specs, **not** the old docs (archived under [`docs/archive/`](archive/)).

## Data location: [`Project/data/v2/`](../data/v2/)

- `documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `text_provenance.jsonl`
- Reasoning overlay: `validity_timeline.jsonl`, `authority_index.jsonl`
- `vocabularies/{issuing_authority,legal_field,scope,sector}.json`

## Core model

Document (`id_str`) → Provision / `unit_id` (Điều/article — the citation unit, **not embedded**) → Chunk (`chunk_id` — the embedding unit).

Corpus ≈ 1,513,376 chunks.

## Vector embedding → [`SPEC_Vector_Retrieval.md`](../SPEC_Vector_Retrieval.md)

- Chunk rows are **slim** (join keys + `chunk_text` only). There is no stored `retrieval_text` — build it at embed time by joining chunk → provision → document.
- **`retrieval_text` = two parts:** (1) identity header = `document.title | citation_label | unit_ref + unit_heading`, then (2) `chunk_text`. Exact loop is in §4 Step 2.
- **Do not embed control fields.** `legal_authority_rank`, `validity_group`/`currency_hint`, and the rule-based facets (`legal_field`, `sector`, `scope`) go in the **payload only** — used for filtering (§4.2) and ranking (§4.4), never inside the vector.
- Normalize vectors (L2 = 1 for cosine). Payload schema is §3.1.

## Graph → [`SPEC_Knowledge_Graph.md`](../SPEC_Knowledge_Graph.md)

- Nodes: Document, Provision, Chunk (+ external stubs). Edges use `src_id`/`dst_id`/`rel_*`; only traverse relationship edges where `direction_verified` is true (§4).
- Faceted vocab is `{code, surface, raw}`; flatten to `_code`/`_surface`. Empties are `MISSING`/`UNMAPPED`.
- Structural edges: `DOCUMENT_HAS_PROVISION`, `PROVISION_HAS_CHUNK` (containment) and `CHUNK_NEXT`, `PROVISION_NEXT` (reading order — materialized but derivable from `char_start`; see the "Why (derivable-from)" note in §4.2). `CHUNK_NEXT` powers same-provision context expansion.
- Validity/authority live in the overlay files, not on the nodes — join at query time.

## Shared conventions

- `dataset_tier` is retired → use `legal_authority_rank` (1–99) + `validity_group` + derived `currency_status`.
- Each spec ends with a "Changes from the archived spec" migration table mapping every renamed file/field.

---

*Specs reflect the actual emitted schema, verified against real samples. Ping the data owner if any field shape is unclear.*
