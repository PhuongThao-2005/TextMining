# G-LRAG Dataset & Spec Alignment Report

| Field | Value |
| --- | --- |
| Scope | Dataset finalization stage vs. `Dataset_SPEC.md`; teammate specs (Knowledge Graph, Text Structuring, Vector Retrieval) vs. the current finalized dataset |
| Data inspected | `data/finalized/` (all six artifacts), verified row-by-row |
| Date | 2026-07-06 |
| Author | Dataset preprocessing owner |
| Status | For decision — no teammate specs or data files were modified |

---

## 0. How this report was produced

Every claim below was checked against the actual bytes in `data/finalized/`, not against the spec text or the generated `preprocessing_report.md`. Concretely:

- Field names were dumped from the first record of each JSONL file.
- The raw→canonical relationship mapping was tallied across **all 883,256** rows of `relationships_final.jsonl`.
- Quarantine reason tags were counted across the full quarantine files.
- Tier, validity, stub, and external-target counts were recomputed from the data.

Where a showcase row is shown, it is a real record copied from the dataset (Vietnamese text shown in correct NFC form; any garbling you may see in a raw terminal is a console display artifact, not a data problem).

---

## 1. Executive summary

| # | Problem | Severity | Where | Fixed? |
| --- | --- | --- | --- | --- |
| P1 | KG spec's validity mapping is the **inverse** of the actual data | 🔴 Critical | `SPEC_Knowledge Graph.md` §6.1 | Reported only — needs your decision |
| P2 | All three teammate specs depend on **full document text / chunks that don't exist yet** | 🟠 Major | all 3 specs | Reported only — upstream blocker |
| P3 | `quality_flags` naming conflict across specs | 🟠 Major | Dataset vs. Text Structuring vs. KG | Pinned in `Dataset_SPEC.md`; text spec still needs edit |
| P4 | `*_canonical` fields are **not** vocabulary-normalized, but specs use them as exact-match facets | 🟡 Minor | Vector §3.2, KG node schema | Documented in `Dataset_SPEC.md` |
| P5 | Wrong path prefix (`Road2AI_ApplePie/...`) throughout Dataset_SPEC + script | 🟡 Minor | `Dataset_SPEC.md`, `finalize_dataset.py` | Doc fixed; script constants still to change |
| P6 | Quarantine reason counts didn't reconcile to row counts (1,799≠1,796; 14,740≠14,634) | 🟡 Minor | `Dataset_SPEC.md` §5.4, §6.3 | Explained + documented |
| P7 | External-stub numbers looked contradictory (19,763 vs 57,120 vs 57,790) | 🟡 Minor | `Dataset_SPEC.md` §6.4 | Reconciled |
| P8 | `Retrieval_Handoff.md` was stale and duplicated contracts | 🟡 Minor | `Retrieval_Handoff.md` | Deleted |

**Actions already taken:** `Dataset_SPEC.md` updated (P3–P7), `Retrieval_Handoff.md` deleted (P8). **Decisions still needed from you:** P1, P2, and the source-side edits noted in P3/P5.

---

## 2. Dataset_SPEC vs. actual output — what was verified correct

Before the problems, the good news: the headline numbers are sound. These all matched the data exactly:

| Claim in Dataset_SPEC | Actual data | Match |
| --- | ---: | :---: |
| Final metadata records: 151,624 | 151,624 | ✅ |
| Metadata quarantine: 1,796 | 1,796 | ✅ |
| Final relationships: 883,256 | 883,256 | ✅ |
| Relationship quarantine: 14,634 | 14,634 | ✅ |
| External stubs: 19,763 | 19,763 | ✅ |
| Tier: reference 82,778 / primary 68,846 | identical | ✅ |
| All 17 canonical relationship counts | sum to 883,256 | ✅ |
| Metadata fields (§7.1) | exactly present in `metadata_final.jsonl` | ✅ |
| `edge_keep_status = kept` for all final rows | 883,256 / 883,256 | ✅ |

So the numbers never strayed. The straying was in **paths, unexplained discrepancies, missing handoff facts, and overstated field semantics** — the things a downstream teammate would trip over.

---

## 3. Detailed problems with showcases

### 🔴 P1 — Knowledge Graph validity mapping is inverted vs. the data

**What the KG spec says** — [`SPEC_Knowledge Graph.md`](Project/SPEC_Knowledge%20Graph.md:177) §6.1:

| Raw label | canonical (per KG spec) | Count |
| --- | --- | ---: |
| `Văn bản quy định hết hiệu lực` | `expires_or_replaces` | 61,227 |
| `Văn bản hết hiệu lực` | `expired_or_replaced_by` | 49,995 |

**What the data actually contains** — real row from `relationships_final.jsonl`:

```json
{"doc_id":77,"other_doc_id":"195","relationship":"Văn bản hết hiệu lực",
 "doc_id_str":"77","other_doc_id_str":"195",
 "relationship_raw":"Văn bản hết hiệu lực",
 "relationship_canonical":"expires_or_replaces",
 "relationship_group":"validity","external_target":false,"edge_keep_status":"kept"}
```

Tallied across all rows:

| Raw label | canonical (**actual data**) | Count |
| --- | --- | ---: |
| `Văn bản hết hiệu lực` | `expires_or_replaces` | 61,227 |
| `Văn bản quy định hết hiệu lực` | `expired_or_replaced_by` | 49,995 |

**The problem is twofold:**

1. **Spec ↔ data mismatch.** The KG spec attached the correct *counts* to the *wrong raw labels*. The two raw labels are swapped relative to the data. The KG builder converts `relationship_canonical` mechanically to edge types (`expires_or_replaces` → `EXPIRES_OR_REPLACES`), so building from the spec's assumption would point ~111,000 validity edges (61,227 + 49,995) in the wrong direction. Validity-lineage queries ("what replaced this law?") would return the opposite of the truth.

2. **The pipeline's own label may be semantically inverted.** Reading the Vietnamese: `Văn bản quy định hết hiệu lực` ≈ "document that *stipulates* the expiry" (i.e. the replacing/superseding document), yet [`finalize_dataset.py`](Project/scripts/finalize_dataset.py:63) maps it to `expired_or_replaced_by`. And `Văn bản hết hiệu lực` ≈ "document that *has expired*", yet it maps to `expires_or_replaces`. That reads backwards. Two explanations are possible and **cannot be told apart from labels alone**:
   - (a) the mapping label is genuinely inverted in the script, or
   - (b) the `(doc_id, other_doc_id)` row order is recorded from a perspective that makes the mapping correct (the label describes the *other* document's role).

   Notably, the *partial*-expiry pair in the same script follows the intuitive direction (`quy định hết hiệu lực 1 phần` → `partially_expires`), so the full-expiry pair is also internally inconsistent with its own partial counterpart.

**Showcase of the stakes** — for the row above (doc 77 → doc 195, `expires_or_replaces`): does document 77 replace 195, or was 77 replaced by 195? The graph's entire validity-lineage direction hinges on this, and right now the spec and the code disagree with each other and both look suspect.

**What I did:** documented the observed mapping and this exact ambiguity in the new [`Dataset_SPEC.md`](Project/Dataset_SPEC.md) §6.2.1, and marked the `validity` group direction as *unverified* pending sign-off.

**Decision needed:** pick one real, well-known document pair (e.g. a law and its known replacement), look it up in the data, and confirm whether direction (a) or (b) holds. This unblocks all `validity`-group graph edges (~125k edges total).

---

### 🟠 P2 — All three specs depend on data that does not exist yet

The finalized package is **metadata + document-to-document relationships only**. There is **no document body text** in it. Confirmed by the field dump of `metadata_final.jsonl` — the only text fields are `title` / `title_clean` / `citation_label`; there is no `content_html`, no article text, no body.

Yet:

| Spec | Assumed input | Exists in finalized data? |
| --- | --- | :---: |
| [`SPEC_Text Structuring.md`](Project/SPEC_Text%20Structuring.md:40) | full text (`content_html`/extracted text) joined by `id_str` | ❌ No |
| [`SPEC_Vector_Retrieval.md`](Project/SPEC_Vector_Retrieval.md:37) | `chunks.jsonl` (from text structuring) | ❌ No |
| [`SPEC_Knowledge Graph.md`](Project/SPEC_Knowledge%20Graph.md:41) | `documents_structured.jsonl`, `legal_units.jsonl`, `chunks.jsonl` | ❌ No |

**Showcase — the dependency chain:**

```
[MISSING: full document text]
        │
        ▼
Text Structuring ──► documents_structured.jsonl / legal_units.jsonl / chunks.jsonl
        │                        │
        ▼                        ▼
Vector Retrieval           Knowledge Graph (structural half)
(indexes chunks.jsonl)     (LegalUnit/Chunk nodes)
```

The **document-level** half of the graph (Document nodes + the 883,256 cross-document edges) *can* be built today from the finalized data. But everything text/chunk-based is blocked until a full-text source is located. This is the real critical-path blocker, independent of any spec correctness.

**Decision needed:** where does document body text come from? Until that is answered, the vector spec and the structural half of the graph spec are un-runnable end-to-end.

---

### 🟠 P3 — `quality_flags` naming conflict across specs

Three specs refer to overlapping-but-different flag fields under colliding names:

| Spec | Field name used | Meaning |
| --- | --- | --- |
| `Dataset_SPEC.md` (this stage) | `quality_flags` | metadata-level flags (missing issuer, etc.) |
| [`SPEC_Text Structuring.md`](Project/SPEC_Text%20Structuring.md:100) | sometimes `quality_flags_document`, plus its own `structuring_quality_flags` | mixes metadata-inherited and structuring-stage flags |
| [`SPEC_Knowledge Graph.md`](Project/SPEC_Knowledge%20Graph.md:110) §5 | stores **two** properties to disambiguate | flags the conflict explicitly |

**Showcase — the actual field in the data:**

```
metadata_final.jsonl field name  →  "quality_flags"   (not "quality_flags_document")
example value                    →  ["expired_full","missing_effective_date","missing_field"]
```

So the data uses exactly `quality_flags`. The KG spec already noticed the clash and worked around it by storing `quality_flags` + `structuring_quality_flags` as distinct node properties — but the text-structuring spec still introduces the `quality_flags_document` alias, which will re-seed the confusion.

**What I did:** pinned the convention in [`Dataset_SPEC.md`](Project/Dataset_SPEC.md) §7.1 — `quality_flags` = metadata-inherited, `structuring_quality_flags` = structuring-stage, never `quality_flags_document`.

**Decision needed:** approve this convention so the text-structuring spec can be corrected at the source (one-line clarification in its §5).

---

### 🟡 P4 — `*_canonical` fields are not actually canonicalized

The retrieval and graph specs treat `co_quan_ban_hanh_canonical`, `linh_vuc_canonical`, `nganh_canonical`, `pham_vi_canonical` as **exact-match keyword filters** (e.g. [`SPEC_Vector_Retrieval.md`](Project/SPEC_Vector_Retrieval.md:206) §3.2). That assumes each real-world value maps to one canonical key.

But in the data, only `loai_van_ban_canonical` has a real normalization map ([`finalize_dataset.py`](Project/scripts/finalize_dataset.py:26)). The others are produced by `clean_text` (whitespace/Unicode only) — no controlled vocabulary.

**Showcase — issuing-authority values in the first 20,000 records:**

```
272 distinct co_quan_ban_hanh_canonical values in just the first 20k records
sample:
  "UBND tỉnh Hà Tĩnh"
  "Ủy ban nhân dân tỉnh Đắk Nông"
  ...
```

`UBND tỉnh …` and `Ủy ban nhân dân tỉnh …` are the **same kind of authority** written two ways, but as exact-match filter keys they are different buckets. A facet filter on "provincial People's Committees" would silently miss whichever variant it didn't ask for.

**What I did:** documented the true behavior of these fields in [`Dataset_SPEC.md`](Project/Dataset_SPEC.md) §7.1 so downstream teams don't over-trust them.

**Decision needed:** either add a real canonicalization pass in a follow-up, or have the retrieval/graph specs treat these as fuzzy/cleaned values rather than strict facets.

---

### 🟡 P5 — Wrong path prefix throughout

`Dataset_SPEC.md` and the script referenced `Road2AI_ApplePie/data/...`, but the artifacts actually live in `data/finalized/`.

**Showcase:**

```
Dataset_SPEC (old):  Road2AI_ApplePie/data/finalized/metadata_final.jsonl
Actual location:     data/finalized/metadata_final.jsonl
Script constants:    RAW_DIR = Path("Road2AI_ApplePie/data/untracked_data")   ← still wrong
                     OUT_DIR = Path("Road2AI_ApplePie/data/finalized")         ← still wrong
```

Running the committed script as-is would not read or write the project's real `data/` directory.

**What I did:** fixed all paths in `Dataset_SPEC.md` and added a path-convention note.

**Decision needed:** approve changing the two constants in [`finalize_dataset.py`](Project/scripts/finalize_dataset.py:10) so the script is reproducible (a two-line change; I left it untouched pending your OK).

---

### 🟡 P6 — Quarantine reason counts didn't reconcile

The reason breakdowns summed higher than the row counts, which looked like lost/extra records:

| | Reason tags sum | Actual rows | Gap |
| --- | ---: | ---: | ---: |
| Metadata quarantine | 1,799 | 1,796 | +3 |
| Relationship quarantine | 14,740 | 14,634 | +106 |

**Showcase — a real double-tagged metadata record:**

```
id_str = 41855
exclusion_reasons = ["missing_issuer", "unknown_type"]   ← two reasons, one row
quality_flags     = ["expired_full","missing_effective_date","missing_expiry_date",
                     "missing_field","missing_issuer","missing_publication_date",
                     "missing_scope","missing_sector","missing_source","unknown_type"]
```

This single row contributes to **both** `missing_issuer` and `unknown_type` tallies — so the tag sum legitimately exceeds the row count. The +3 and +106 gaps are exactly these multi-tagged rows; no records are lost. Row totals (1,796 / 14,634) are authoritative.

**What I did:** documented this in [`Dataset_SPEC.md`](Project/Dataset_SPEC.md) §5.4 and §6.3, and listed the additional possible reasons (`missing_id`, `missing_title`, `missing_so_ky_hieu`, `unsupported_type`) that exist in the pipeline but triggered 0 quarantines this run.

---

### 🟡 P7 — External-stub numbers looked contradictory

Three different numbers describe the same phenomenon and read like a conflict:

| Number | Meaning | Value |
| --- | --- | ---: |
| unique missing target IDs | stub rows created | 19,763 |
| kept final edges pointing at a missing target | `external_target=true` in `relationships_final.jsonl` | 57,120 |
| raw edges with missing target (EDA §3.2) | before quarantine | 57,790 |

**Showcase — why unique-IDs ≪ edges:** a single missing target is cited by many documents.

```
stub 36138   ← referenced by 2,287 edges
stub 119683  ← referenced by 1,841 edges
stub 151301  ← referenced by 1,360 edges
```

So 19,763 unique stubs absorb 57,120 edges (many-to-one). And 57,790 − 57,120 = 670 raw edges were dropped earlier for *other* reasons (duplicate/self-loop/source-quarantined) before reaching the final set. Nothing is inconsistent once the three are read correctly.

**What I did:** added the reconciliation to [`Dataset_SPEC.md`](Project/Dataset_SPEC.md) §6.4.

---

### 🟡 P8 — `Retrieval_Handoff.md` was stale — deleted

It predated the text-structuring and vector specs and stated a **different vector-input contract**:

```
Retrieval_Handoff.md §4.1:  vector input = metadata_final.jsonl (+ full text when available)
SPEC_Vector_Retrieval.md §3: vector input = chunks.jsonl (from text structuring)
```

Two documents describing the same handoff boundary two different ways is exactly the kind of drift that causes integration bugs. It also duplicated field lists that now live authoritatively in `Dataset_SPEC.md` and the teammate specs.

**What I did:** deleted it. The authoritative contracts are `Dataset_SPEC.md` (data shape) and each `SPEC_*` (per-stage behavior).

---

## 4. Teammate-spec consistency — what is fine

Not everything is a problem. These were checked and are consistent with the data:

- **Tier / validity filter values** (`dataset_tier`, `validity_group`) that all three specs rely on are present and valid in every record.
- **Stub handling** (`citation_safe=false`, `dataset_tier=reference_stub`) matches across the dataset and both retrieval specs.
- **"Ingest every row as one independent edge, MERGE on the full triple"** (KG spec) is consistent with the data — duplicates are already removed, and inverse pairs have *unequal* counts (e.g. `expires_or_replaces` 61,227 vs `expired_or_replaced_by` 49,995), confirming the two directions are genuinely different edges, not redundant recordings.
- **"No quarantine ingestion"** is enforceable — quarantine records are cleanly separated into their own files.

---

## 5. Decisions requested from you

| Priority | Decision | Unblocks |
| --- | --- | --- |
| 1 | **P1** — confirm the `expires_or_replaces` / `expired_or_replaced_by` direction against a real known document pair | ~125k validity-group graph edges; correct lineage answers |
| 2 | **P2** — decide the full-text source for document bodies | text structuring → all chunk-level retrieval + structural graph |
| 3 | **P3** — approve the `quality_flags` naming convention | one-line fix to the text-structuring spec |
| 4 | **P4** — canonicalization pass vs. relax the specs to fuzzy facets | reliable faceted filtering |
| 5 | **P5** — approve the two-line path fix in `finalize_dataset.py` | script reproducibility |

Items P3–P8 are already handled in the docs; P1, P2, P4, and the P5 code change await your call.

---

## 6. Change log for this report

| File | Change |
| --- | --- |
| `Dataset_SPEC.md` | Paths corrected; no-text scope note added; authoritative raw→canonical table (§6.2.1) with direction caveat added; quarantine reason reconciliations (§5.4, §6.3); external-stub reconciliation (§6.4); `*_canonical` honesty note and `quality_flags` naming pin (§7.1); vector-input text-source note (§8.1) |
| `Retrieval_Handoff.md` | Deleted (stale, conflicting vector-input contract) |
| `report.md` | This report (new) |
| teammate specs / data files | **Not modified** — misalignments reported here for your decision |
