# SPEC Alignment Report — Vector Retrieval & Knowledge Graph vs. Dataset_SPEC_v2

| Field | Value |
| --- | --- |
| Date | 2026-07-06 |
| Question | Are [`SPEC_Vector_Retrieval.md`](../SPEC_Vector_Retrieval.md) and [`SPEC_Knowledge Graph.md`](../SPEC_Knowledge%20Graph.md) misaligned with [`Dataset_SPEC_v2.md`](../Dataset_SPEC_v2.md)? |
| Verdict | **Yes — materially misaligned.** Both downstream specs are written against v1 (`Dataset_SPEC.md`) and consume the exact fields v2 retires, renames, or redefines. |
| Important caveat | `Dataset_SPEC_v2.md` is **Status: Proposal / alternative** and "does not replace `Dataset_SPEC.md` until approved." So today the downstream specs are *correctly* aligned to the approved v1. The misalignments below are the work that becomes required **if v2 is adopted.** |

---

## 1. Summary

Neither downstream spec references `Dataset_SPEC_v2.md`. Both cite `Dataset_SPEC.md` (v1, now in `docs/archive/`) and `SPEC_Text_Structuring.md` as their contract sources. v2 changes five things at the dataset layer (its D1–D5), and four of the five collide directly with assumptions baked into the retrieval and graph specs.

The misalignments fall into three severities:

- **Breaking** — a field the downstream spec filters/ranks/keys on is retired or redefined by v2 (`dataset_tier`, `validity_group`, edge direction/inverse pairs, artifact names).
- **Structural** — schema field names, identity keys, or unit vocabularies differ.
- **Gap** — v2 introduces first-class concepts (`legal_authority_rank`, `currency_status`, `text_provenance`, controlled vocab) that neither downstream spec consumes.

---

## 2. Breaking misalignments

### 2.1 `dataset_tier` is retired (v2 §6.2) — both specs depend on it

v2 D3 explicitly retires `dataset_tier`, splitting it into `legal_authority_rank` (static authority) and `currency_status(as_of)` (temporal, derived). `primary`/`reference` survives only as an optional derived convenience view, "not the source of truth."

Both downstream specs treat `dataset_tier` as a first-class stored field:

- **Vector** ([`SPEC_Vector_Retrieval.md`](../SPEC_Vector_Retrieval.md)): `dataset_tier` is a hard-filter payload field (§3.2), drives the `current_law` / `broad` / `historical` filter profiles (§4.2), is a ranking boost (`primary` +0.10) and penalty (`reference` -0.05) signal (§4.4), is in the citation contract (§5.1), and appears in the hard acceptance metrics ("all vector records have valid dataset_tier value", §5).
- **Graph** ([`SPEC_Knowledge Graph.md`](../SPEC_Knowledge%20Graph.md)): `dataset_tier` is copied onto every `Document` and `ExternalStub` node (§5), is a graph-guided hard-filter field (§8), a ranking field (§8), and gets a dedicated index (§9 step 8).

**Impact:** every filter profile, ranking rule, and index that keys on `dataset_tier` has no source field under v2 unless the derived convenience view is explicitly produced. Both specs would need to migrate to `legal_authority_rank` + `currency_status`, or formally require v2 to emit the `primary`/`reference` compatibility view.

### 2.2 `validity_group` becomes a derived function, not a stored label (v2 §5) — both specs store and filter it

v2 D2 replaces the frozen `validity_group` label with a `validity_timeline.jsonl` of events and a `currency_status(id_str, as_of_date)` **function**. The stored label is demoted to a non-authoritative `currency_hint` on `documents.jsonl`.

Both downstream specs treat `validity_group` as a stored, filterable enum (`active | expired | partial | suspended | future | unknown`):

- **Vector:** hard-filter field (§3.2), core of all filter profiles (§4.2), ranking boost/penalty (§4.4), citation contract + acceptance metric "valid validity_group value" (§5).
- **Graph:** stored on `Document` nodes (§5), used in graph-guided filter and ranking (§8), indexed (§9), and the cross-validation warning in §7 ("`validity_group = active` with an incoming `EXPIRES_OR_REPLACES` edge") assumes a stored label.

**Impact:** v2 does not guarantee a stored `validity_group`; it guarantees a timeline plus a hint. Neither downstream spec knows about `validity_timeline.jsonl` or `currency_status(as_of)`. Retrieval-time validity filtering as currently specified cannot be satisfied by v2's authoritative outputs without either (a) computing `currency_status` and materializing it, or (b) consuming only `currency_hint` and accepting it is non-authoritative.

### 2.3 Edge direction: v2 folds inverse pairs; the graph spec forbids folding (v2 §8 vs. KG §6)

This is a **direct contradiction**, not just a rename.

- v2 D5 (§8.1) normalizes every edge to one canonical semantic direction, folding inverse raw labels onto a single direction with `direction_normalized: true`.
- KG §2, §6.1, §6.3 mandate the opposite: ingest all 17 canonical labels including the inverse pairs (`expires_or_replaces` **and** `expired_or_replaced_by`, etc.) as independent rows, and "never synthesize, merge, or drop a row based on its counterpart." KG §6.3 documents the deliberate count asymmetry (e.g. 61,227 vs 49,995) as the reason for keeping both directions.

**Impact:** under v2 the inverse-labeled edges would be collapsed into one direction, which would break KG's 17-type edge model, its raw→canonical mapping table (§6.1), the 883,256-edge reconciliation (§6.1, §7), and the "one row → one edge" acceptance metric (§7, §10). The two specs cannot both be right; this needs an explicit decision.

Note the **one point of agreement:** both v2 (§8.2) and KG (§6.2, §11 item 1) require the edge-direction convention to be verified against real document pairs before production. v2 gates its validity timeline on this sign-off; KG lists it as its highest-priority open item.

### 2.4 Artifact / file names differ across the board

v2 §3 renames the Layer 1 artifacts. The downstream specs still name the v1 files:

| Concept | v2 artifact (§3) | KG input (§3) | Vector input (§3) |
| --- | --- | --- | --- |
| Documents | `documents.jsonl` | `metadata_final.jsonl` | `metadata_final.jsonl` |
| Edges | `edges.jsonl` | `relationships_final.jsonl` | — |
| External stubs | `external_stubs.jsonl` | `metadata_external_stubs.jsonl` | `metadata_external_stubs.jsonl` |
| Citation unit | `provisions.jsonl` | `legal_units.jsonl` | `legal_units.jsonl` |
| Doc structural status | (folded into layers) | `documents_structured.jsonl` | `documents_structured.jsonl` |
| Chunks | `chunks.jsonl` | `chunks.jsonl` | `chunks.jsonl` |

Only `chunks.jsonl` keeps its name. Every input contract in both downstream specs points at filenames v2 does not produce.

---

## 3. Structural misalignments

### 3.1 Citation/legal unit: `provisions.jsonl` vs `legal_units.jsonl`

v2 (§4.2, §14) calls the citation unit a **Provision** in `provisions.jsonl`, keyed by `unit_id`, with `unit_type` values `dieu | khoan | diem | preamble | attachment | document_fallback`.

KG (§4.1, §5) and Vector (§3.1) call it a **LegalUnit** in `legal_units.jsonl`, with `unit_type` values `article | preamble | section | item | attachment_preamble | document` (verbatim from `SPEC_Text_Structuring.md`).

So the same concept has a different file name, node/record name, and a different `unit_type` controlled vocabulary (`dieu` vs `article`, `document_fallback` vs `document`, etc.). v2 §4.2 claims it "aligns to" the text-structuring `Document → Legal Unit → Chunk` model, but its own field listing uses Vietnamese-token unit types that do not match. This ambiguity should be reconciled.

### 3.2 Edge schema field names

v2 §8.3 edge fields vs KG §5 "Cross-Document Edge Record":

| v2 (§8.3) | KG (§5) |
| --- | --- |
| `edge_id` | (implicit via triple key) |
| `src_id`, `dst_id` | `doc_id_str`, `other_doc_id_str` |
| `rel_canonical` | `relationship_canonical` |
| `rel_group` | `relationship_group` |
| `rel_raw` | `relationship_raw` |
| `direction_normalized`, `direction_verified` | (KG uses per-group verification, no per-edge `direction_normalized`) |
| `external_target` | `external_target` |
| `provenance` | `source_in_metadata`, `target_in_metadata`, `edge_quality_flags` |

Field-for-field this is a rename plus the semantic conflict from §2.3.

### 3.3 Identity keys: `doc_id` vs `id_str`/`unit_id`

v2 principle 5 (§2) declares the identity space is exactly `id_str → unit_id → chunk_id`, "no translation anywhere." Both downstream specs additionally carry a separate `doc_id` field:

- Vector payload (§3.1) lists both `doc_id` and `id_str`; the citation contract (§5.1) returns both; same-unit expansion keys on `parent_unit_id`.
- KG (§3, §5) joins "by `id_str` / `doc_id`" and stores `doc_id` on `LegalUnit`/`Chunk` nodes.

v2 has no `doc_id` — it uses `id_str` as the sole document key. This is reconcilable (treat `doc_id == id_str`) but is currently unstated and inconsistent.

### 3.4 Controlled vocabularies: `{code, surface, raw}` vs `*_canonical` strings

v2 D4 (§7) replaces cleaned canonical strings with `{code, surface, raw}` triples in a versioned `vocabularies/` directory; filtering uses `code`, display uses `surface`.

Both downstream specs consume flat `*_canonical` strings and filter on them directly:

- Vector (§3.1, §3.2): `loai_van_ban_canonical`, `co_quan_ban_hanh_canonical`, `pham_vi_canonical`, `nganh_canonical`, `linh_vuc_canonical` — all keyword filter fields.
- KG (§5, §8): same `*_canonical` fields on `Document` nodes and in the graph-guided filter.

**Impact:** under v2 these fields become objects (`issuing_authority: {code, surface, raw}`), so every filter/index/payload that treats them as plain strings must switch to the `.code` sub-field. Field names also change (`co_quan_ban_hanh_canonical` → `issuing_authority`, `linh_vuc_canonical` → `legal_field`).

---

## 4. Gaps — v2 concepts neither downstream spec consumes

These are not contradictions but missing coverage: if v2 is adopted, these first-class artifacts have no downstream consumer defined.

- **`legal_authority_rank` + `authority_index.jsonl`** (v2 §6.1): v2's headline legal-precedence ranking (Hiến pháp > Luật > …). Vector ranking (§4.4) and KG ranking (§8) rank by `dataset_tier`, not authority rank — so the whole authority dimension is unused downstream.
- **`currency_status(as_of)` / `validity_timeline.jsonl`** (v2 §5): the temporal-validity engine. Neither spec has a query-time `as_of` parameter; both assume a static validity label.
- **`text_provenance.jsonl`** (v2 §4): per-document text coverage and the 6,563 `missing` tail. Vector's coverage check (§5) keys on `structuring_status` values (`structured_by_article`, etc.), not v2's `text_status` (`available | missing | empty | too_short | extraction_failed`).
- **`content.jsonl` multi-row merge** (v2 §4.0): v2 makes the 178,665-row → 149,051-ID merge a dataset-owned concern; downstream specs are unaware of it (correctly, it's upstream — noted for completeness).

---

## 5. Field-conflict quick reference

| Field / concept | v1 (what downstream specs use) | v2 (Dataset_SPEC_v2) | Severity |
| --- | --- | --- | --- |
| `dataset_tier` | stored enum `primary`/`reference` | **retired**, → `legal_authority_rank` + `currency_status` (view optional) | Breaking |
| `validity_group` | stored enum, filterable | **derived** `currency_status(as_of)`; stored `currency_hint` only, non-authoritative | Breaking |
| Edge inverse pairs | keep both directions, never fold (KG §6.3) | **fold** to one canonical direction (`direction_normalized`) | Breaking (contradiction) |
| Artifact filenames | `metadata_final` / `relationships_final` / `legal_units` / `external_stubs` | `documents` / `edges` / `provisions` / `external_stubs` | Breaking |
| Citation unit | `LegalUnit`, types `article…document` | `Provision`, types `dieu…document_fallback` | Structural |
| Edge schema fields | `doc_id_str`, `relationship_*`, `edge_quality_flags` | `src_id`/`dst_id`, `rel_*`, `provenance` | Structural |
| Document key | `id_str` + `doc_id` | `id_str` only | Structural |
| Faceted fields | `*_canonical` strings | `{code, surface, raw}` objects | Structural |
| `legal_authority_rank` | — (absent) | first-class authority rank | Gap |
| `validity_timeline` / `text_provenance` / `authority_index` | — (absent) | first-class artifacts | Gap |

---

## 6. Recommendations

1. **Treat this as gated on the v2 adoption decision.** v2 is a proposal; until approved, the downstream specs are correctly aligned to v1. Do not refactor the retrieval/graph specs yet — record the delta.
2. **If v2 is adopted, resolve the edge-direction contradiction first (§2.3).** It is the only true logical conflict: v2 folds inverse pairs, KG forbids folding. Both teams cannot proceed until this is decided, and it also gates the shared direction-verification sign-off both specs already require.
3. **Require v2 to emit the compatibility view.** The lowest-friction migration is for v2 (§6.2) to materialize the `primary`/`reference` derived view and a resolved `currency_status`/`validity_group` snapshot at `as_of = today`, so existing filter profiles and rankings keep working while the specs migrate to `legal_authority_rank` + `as_of` querying.
4. **Add an `as_of` parameter and authority-rank ranking** to the vector `retrieve()` API (§6.2) and the graph ranking (§8) to actually use v2's temporal and authority dimensions, otherwise v2's core value (D2, D3) is discarded downstream.
5. **Unify the identity/vocabulary contracts:** pick `id_str` as the sole document key (drop `doc_id` or alias it), and switch `*_canonical` filters to `{code, surface, raw}.code`, updating field names (`issuing_authority`, `legal_field`).
6. **Reconcile the citation-unit vocabulary** (`article` vs `dieu`, `LegalUnit` vs `Provision`) between v2 §4.2, `SPEC_Text_Structuring.md`, and both downstream specs before anyone builds against it.
7. **Update the cross-references.** Both downstream specs cite `Dataset_SPEC.md`; if v2 supersedes it, the references, filenames, and field names must be repointed as part of the migration.
