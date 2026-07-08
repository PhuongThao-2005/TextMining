# SPEC_Vector_Retrieval.md

> **v2-aligned.** This spec matches the dataset actually produced by the v2 pipeline (`Dataset_SPEC_v2.md`, `data/v2/`). The pre-v2 version is archived at `docs/archive/SPEC_Vector_Retrieval.md`. Key changes from the archived version are called out in §11.

## 1. Purpose

This document specifies the vector retrieval stage for the G-LRAG pipeline.

The stage takes the v2 structured output and makes it searchable via dense vector similarity:

```text
chunks.jsonl (+ provisions.jsonl + documents.jsonl) → Embedding → Vector DB → Retrieval API
```

Vector retrieval is the primary semantic-search path in the hybrid RAG architecture. It works alongside graph retrieval (`SPEC_Knowledge_Graph.md`) to provide evidence for answer generation, per `SPEC.md` §4.7 and §6.6, and serves two measurable success criteria from `SPEC.md` §3: hallucination rate under 10% and average response latency under 1 minute.

**The single biggest v2 change:** chunk rows are **slim**. `chunks.jsonl` carries only join keys + `chunk_text` (12 fields, `SPEC_Text_Structuring.md` §5.3). There is no stored `retrieval_text` and no denormalized metadata. The embedding pipeline **joins** each chunk to its provision (`parent_unit_id → provisions.jsonl`) and document (`id_str → documents.jsonl`) to build `retrieval_text` at embed time and to populate the payload.

## 2. Core Requirements

- Index every chunk from `chunks.jsonl` (full v2 run: 1,513,376 chunks).
- **Build `retrieval_text` at embed time** by joining chunk → provision → document; embed `retrieval_text`, not bare `chunk_text`. `retrieval_text` has exactly **two parts** (§4 Step 2): (1) an **identity header** — the source document title + citation identity and the parent unit number *with its heading title* — and (2) the `chunk_text` itself. The header preserves the chunk's semantic identity so matching is not naive lexical matching on a bare, context-stripped clause (`SPEC_Text_Structuring.md` §6).
- **Do not embed structured control fields.** `legal_authority_rank`, `validity_group`/`currency_hint`, and the rule-based facets (`legal_field`, `sector`, `scope`) are **excluded from `retrieval_text`**. They are structured signals used by the filtering/ranking overlay (§4.2, §4.4), not semantic text; embedding a bare integer rank or a token like `expired` adds noise and duplicates a filter. Reliance is placed on query ↔ (title + unit heading + clause) semantic matching instead.
- Store `chunk_text` (clean content) in the payload — the LLM sees only the grounded text, not the retrieval wrapper.
- Populate payload metadata by **join**, not by reading it off the chunk row (the chunk row does not carry it).
- Support hard filtering by `legal_authority_rank`, `validity_group` (and derived `currency_status`), `id_str`, `unit_type`, and faceted `_code` fields at query time.
- Support soft ranking signals based on joined metadata (authority rank, validity, quality flags).
- Return enough metadata for citation display, graph joins, and same-provision expansion.
- Never index chunks belonging to `documents_quarantine.jsonl` or `external_stubs.jsonl` documents.
- Provide a baseline naive RAG flow before graph-guided enhancements.

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `data/v2/chunks.jsonl` | Retrieval units — `chunk_text` + join keys (`parent_unit_id`, `id_str`) |
| `data/v2/provisions.jsonl` | Join source for `citation_anchor`, `unit_type`, `article_number`, `path` |
| `data/v2/documents.jsonl` | Join source for title, citation label, authority, validity, facets |
| `data/v2/text_provenance.jsonl` | Coverage cross-check (`structuring_status`) |

All under `data/v2/`.

### Outputs

Recommended output directory: `data/v2/vector_retrieval/`.

| Output | Purpose |
| --- | --- |
| Vector database collection(s) | Searchable index of embedded chunks |
| `vector_index_report.md` | Indexing counts, quality checks, embedding stats |
| Retrieval API / module | Callable interface for the retrieval layer |

## 4. Step-by-Step Plan

### Step 1: Vector DB Setup

**Recommended DB:** Qdrant (native metadata filtering, gRPC, local Docker, good Python SDK).

**Configuration:**
- Collection name: `legal_chunks`.
- Vector dimension: from the embedding model (Step 2).
- Distance metric: **cosine**.
- Payload fields indexed for filtering — see §4 Step 3.2.
- HNSW: `m=16`, `ef_construction=100` (tune later — the corpus is ~1.5M chunks, so index build and memory need real sizing).

**Single vs. dual collection:** v2 retires `dataset_tier`, so the old `primary`/`reference` split no longer maps to a stored field. Use a **single collection** and filter by `legal_authority_rank` + derived `currency_status` at query time. A `primary`-style view (`high authority AND currently in force`) is a query-time filter, not a separate collection.

### Step 2: Embedding Pipeline

**Model selection criteria:** strong Vietnamese support, 768–1024 dim, open-source preferred.

| Model | Dim | Notes |
| --- | --- | --- |
| `bkai-foundation-models/vietnamese-bi-encoder` | 768 | Vietnamese-specific |
| `intfloat/multilingual-e5-large` | 1024 | Strong multilingual |
| `BAAI/bge-m3` | 1024 | SOTA multilingual, dense + sparse |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | Lightweight fallback |

> Recommendation: start with `multilingual-e5-large` or `bge-m3`.

**Embedding process (join-then-embed):**

`retrieval_text` is exactly two parts: an **identity header** (Part 1) then the **`chunk_text`** (Part 2). The header carries only semantic identity text — document title, citation label, parent unit + its heading title — all as Vietnamese surface strings. No numeric rank, no validity token, no rule-based facet.

```text
Load provisions.jsonl into a {unit_id -> provision} map (unit_type, article_number, unit_heading, citation_anchor).
Load documents.jsonl into a {id_str -> document} map (title, citation_label).
For each chunk in chunks.jsonl:
  1. provision = provisions[chunk.parent_unit_id]; document = documents[chunk.id_str]
  2. # Part 1 — identity header (semantic-matching context)
     unit_ref = f"Điều {provision.article_number}" if provision.unit_type == "article" else provision.unit_type
     unit_title = provision.unit_heading or ""      # article heading title, e.g. "Điều 11. Quyền và nghĩa vụ…"
     header = f"{document.title} | {document.citation_label} | {unit_ref} {unit_title}".strip(" |")
     # Part 2 — the clause body
     retrieval_text = f"{header}\n{chunk.chunk_text}"
  3. vector = normalize(encode(retrieval_text))          # L2 norm = 1 for cosine
  4. payload = build_payload(chunk, provision, document)  # §4 Step 3.1 (rank/validity/facets go here, NOT in the vector)
  5. upsert(id=chunk.chunk_id, vector=vector, payload=payload)
```

Design rationale (confirmed with the dataset owner):
- **Part 1 (header)** = the chunk's identity: original document title, the document's citation label, and the parent article/unit *with its heading title*. Without it, an isolated clause loses its identity and retrieval degrades toward lexical matching; with it, a query about a topic named in the title/heading matches semantically.
- **Part 2 (`chunk_text`)** = the clause body — the substantive content.
- **Excluded on purpose:** `legal_field`/`sector`/`scope` are rule-based and do not reliably denote topic, so they are not trusted as embedding signal; `legal_authority_rank` (a bare integer) is meaningless to the embedder; `validity_group` belongs to the later filtering overlay (§4.2). All three stay in the payload for filtering/ranking, never in the vector.

- Batch size 32–64; log progress every 1,000 chunks.
- ~1.5M chunks is a large run — size embedding time/hardware accordingly (§10).
- For `e5` models, prepend `"query: "` / `"passage: "` per model convention.
- Any change to the `retrieval_text` template requires re-embedding — treat it as a versioned contract with the text-structuring team.

### Step 3: Chunk Indexing Strategy

#### 3.1 Vector Payload Schema (built by join)

The chunk row supplies only the identity/intrinsic fields; everything else is joined in.

**From `chunks.jsonl` (the row itself):**
```text
chunk_id                  # vector point ID (primary key)
parent_unit_id            # same-provision expansion + provision join
id_str                    # document join / graph join
chunk_index_in_unit
chunk_count_in_unit
chunk_text                # clean content for the LLM (stored, NOT embedded alone)
chunk_char_count, chunk_token_estimate
unit_split
structuring_quality_flags
```

**Joined from `provisions.jsonl` (via `parent_unit_id`):**
```text
unit_type                 # article | preamble | section | item | attachment_preamble | document
article_number
unit_heading
path
citation_anchor           # citation-ready string for answer display
```

**Joined from `documents.jsonl` (via `id_str`):**
```text
title
citation_label
so_ky_hieu
loai_van_ban
legal_authority_rank      # integer authority rank (1 highest .. 99 unknown)
validity_group            # active | expired | partial | suspended | future | unknown
currency_hint             # fast-path hint; prefer graph-derived currency_status
issuing_authority_code, issuing_authority_surface
legal_field_code, legal_field_surface
sector_code, sector_surface
scope_code, scope_surface
issue_year
ngay_ban_hanh_iso, ngay_co_hieu_luc_iso, ngay_het_hieu_luc_iso
quality_flags             # metadata quality flags from documents.jsonl
```

Faceted fields are stored as `_code` (filter) + `_surface` (display) from the `{code, surface, raw}` triple.

#### 3.2 Filterable Payload Fields

| Field | Type | Filter use |
| --- | --- | --- |
| `legal_authority_rank` | integer | Range/exact: authority precedence (replaces `dataset_tier`) |
| `validity_group` | keyword | Hard filter: active, partial, expired, … |
| `id_str` | keyword | Hard filter: graph-guided document set |
| `unit_type` | keyword | Filter by provision type |
| `loai_van_ban` | keyword | Filter by document type |
| `legal_field_code` | keyword | Filter by legal field |
| `sector_code` | keyword | Filter by sector |
| `scope_code` | keyword | Filter by scope |
| `issuing_authority_code` | keyword | Filter by issuing authority |
| `issue_year` | integer | Range filter by year |

#### 3.3 Indexing Rules

- Index ALL chunks from `chunks.jsonl` — do not skip any, even `article_detected_false` ones.
- Store `chunk_text` in the payload (LLM input); embed `retrieval_text` (built at embed time).
- Do **not** store `retrieval_text` in the payload — it is derivable by re-joining. (This matches the slim-chunk principle: one source of truth per fact.)
- Use `chunk_id` as the vector point ID (or map deterministically to an integer if the DB requires).
- Validate zero duplicate `chunk_id` before indexing (v2 build: 0 duplicates across 1,513,376).

### Step 4: Retrieval Tuning and Filtering Logic

#### 4.1 Default Retrieval Flow

```text
User Query → preprocess → embed (same model + prefix) → vector search with filters
          → same-provision expansion → re-rank → return top-k chunks with joined metadata
```

#### 4.2 Filter Profiles

v2 filters on `legal_authority_rank` + `validity_group` (there is no `dataset_tier`).

**Profile: `current_law` (default)**
```text
validity_group IN [active, partial, future]
# optionally: legal_authority_rank <= 6   (statute-level and above)
```

**Profile: `broad`**
```text
validity_group IN [active, partial, future, expired, unknown]
```

**Profile: `historical`**
```text
validity_group IN [expired, active, partial]
# include expired for history/lineage
```

**Profile: `graph_guided`**
```text
id_str IN [<set from graph query>]
# Hard filter by document IDs from graph traversal.
# Empty set → surface explicitly; do NOT fall back to unfiltered (SPEC_Knowledge_Graph.md §2).
```

Optional filters on top of any profile:
```text
loai_van_ban        = <detected from query>   # e.g. "Luật", "Nghị định"
legal_field_code    = <detected from query>
sector_code         = <detected from query>
scope_code          = <detected from query>
issue_year BETWEEN <start> AND <end>
```

> Currency note: `validity_group`/`currency_hint` are fast-path hints. For authoritative currency, the caller should prefer `currency_status(id_str, as_of)` computed from `validity_timeline.jsonl` (`SPEC_Knowledge_Graph.md` §7.1) and pass the resulting `id_str` set as a `graph_guided` filter.

#### 4.3 Retrieval Parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| `top_k` (initial) | 20 | Candidates from vector search |
| `top_n` (after re-rank) | 5–10 | Chunks passed to LLM |
| `score_threshold` | 0.3 | Minimum cosine similarity |
| `same_unit_expansion` | true | Fetch sibling chunks under the same `parent_unit_id` |
| `max_expansion_chunks` | 3 | Max siblings per provision expansion |

#### 4.4 Ranking Signals

Re-rank after initial similarity retrieval using joined metadata.

**Boost:**
| Signal | Weight | Rationale |
| --- | --- | --- |
| `legal_authority_rank <= 2` (Hiến pháp/Luật) | +0.10 | Higher legal precedence |
| `validity_group = active` | +0.08 | Most relevant for current-law questions |
| `unit_type = article` | +0.05 | Article-structured chunks are higher quality |
| Title/citation match with query | +0.10 | Direct document match |

**Penalty:**
| Signal | Weight | Rationale |
| --- | --- | --- |
| `legal_authority_rank >= 7` or `= 99` | -0.05 | Low authority / unknown |
| `validity_group = expired` | -0.08 | Unless query is historical |
| `validity_group = unknown` | -0.03 | Uncertain validity |
| `quality_flags` contains severe warnings | -0.05 | Incomplete metadata |
| `structuring_quality_flags` non-empty | -0.02 | Structuring issues |

> Weights are initial estimates; tune against the evaluation dataset.

#### 4.5 Same-Provision Expansion

```text
1. Retrieve top-k chunks via vector search.
2. For each retrieved chunk:
   a. Read parent_unit_id.
   b. Fetch chunks with the same parent_unit_id (adjacent chunk_index_in_unit ± 1).
   c. Cap at max_expansion_chunks.
3. Deduplicate by chunk_id.
4. Re-rank the expanded set.
```

This restores full-article context and implements the guidance in `SPEC_Text_Structuring.md` §8 and `Dataset_SPEC_v2.md` §4.2.

### Step 5: Citation-Aware Retrieval Preparation

#### 5.1 Citation Contract

Every result returned to the generation layer must include:

```text
{
  "chunk_id": "...",
  "chunk_text": "...",          // clean text for LLM (from chunks.jsonl)
  "citation_anchor": "...",     // from provisions.jsonl (via parent_unit_id)
  "citation_label": "...",      // from documents.jsonl (via id_str)
  "title": "...",               // from documents.jsonl
  "article_number": "...",      // from provisions.jsonl, if applicable
  "unit_type": "...",           // from provisions.jsonl
  "path": "...",                // from provisions.jsonl
  "validity_group": "...",      // from documents.jsonl
  "legal_authority_rank": 0,    // from documents.jsonl (replaces dataset_tier)
  "vector_score": 0.85,
  "id_str": "...",              // graph join
  "parent_unit_id": "..."       // provision-level operations
}
```

#### 5.2 Citation Anchor Usage

`citation_anchor` comes from `provisions.jsonl` (not the chunk row), format per `SPEC_Text_Structuring.md` §6:

```text
{citation_label}, {path}                 # e.g. "…, preamble 0"
{citation_label}, Điều {article_number}  # for unit_type = article
```

The generation layer displays this per `SPEC.md` §5.5.

#### 5.3 Citation Safety Rules

- Only chunks from `documents.jsonl` documents are citation-safe.
- Chunks whose document has high `validity_group = expired` must not be presented as current law unless the user explicitly asks about historical regulations.
- Low authority (`legal_authority_rank >= 7`) should be marked as guidance/administrative, not primary law.
- `external_stubs.jsonl` documents have **no chunks** and must never be indexed or cited.
- Quarantined records (`documents_quarantine.jsonl`) must never be indexed.

### Step 6: Baseline Naive RAG Flow

```text
User Query → preprocess (clean/normalize/rewrite/detect language)
          → embed query (same model + prefix)
          → vector search (current_law profile, top_k=20, score_threshold=0.3)
          → same-provision expansion
          → re-rank & select top_n=5–10
          → format output (chunk_text for LLM, citation_anchor for citations, metadata for fusion)
```

#### 6.1 Baseline API Interface

```python
def retrieve(
    query: str,
    filter_profile: str = "current_law",     # current_law | broad | historical | graph_guided
    id_str_filter: list[str] | None = None,  # for graph-guided mode
    top_k: int = 20,
    top_n: int = 10,
    score_threshold: float = 0.3,
    expand_units: bool = True,
    extra_filters: dict | None = None,        # e.g. {"legal_field_code": "TAX"}
) -> RetrievalResult:
    """
    RetrievalResult:
      chunks: list[RetrievedChunk]   # chunk_text, citation_anchor, joined metadata, score
      total_candidates: int
      filter_profile_used: str
      empty_filter_warning: bool     # True if graph_guided filter returned empty set
    """
```

#### 6.2 Graph-Guided Integration Point

```text
1. Graph retrieval returns a set of id_str values.
2. Pass it as id_str_filter to retrieve() with filter_profile="graph_guided".
3. If the set is empty:
   - Surface explicitly (SPEC_Knowledge_Graph.md §2); do NOT silently fall back.
   - Let the caller decide: retry without graph filter, or inform the user.
4. Vector search restricts to those documents; continue with ranking and expansion.
```

Primary integration point between vector and graph retrieval, per `SPEC.md` §4.8.

## 5. Validation and Report

`vector_index_report.md` must include:

```text
total_chunks_in_source == total_chunks_indexed   # 1,513,376
total_chunks_skipped == 0
unique_documents_indexed   = distinct id_str
unique_provisions_indexed  = distinct parent_unit_id
join_misses == 0                                 # every chunk resolved a provision AND a document
```

Embedding statistics: model name+version, vector dimension, avg embed time/chunk, total time, token distribution (min/max/mean/p50/p95).

Index quality checks:
- Zero duplicate `chunk_id` in the DB.
- Every vector record has non-empty `chunk_text` and non-empty joined `citation_anchor`.
- Every vector record has a valid `validity_group` and integer `legal_authority_rank`.
- Payload field-type validation (keyword/integer/float/boolean).
- Coverage: every `id_str` with `structuring_status` in (`structured_by_article`, `structured_by_fallback_units`, `document_fallback`) has ≥1 chunk indexed.
- Sample retrieval test: 5–10 queries with manually verified results.

Metadata distribution: chunks by `validity_group`, by `legal_authority_rank`, by `unit_type`, by `loai_van_ban` (top 10), by `legal_field_code` (top 10).

Hard acceptance metrics:

```text
total_chunks_indexed == total_chunks_in_source
duplicate_chunk_id_in_db == 0
join_misses == 0
all vector records have non-empty chunk_text
all vector records have non-empty citation_anchor (joined)
all vector records have a valid validity_group and legal_authority_rank
zero chunks from quarantine or external-stub documents
retrieval_text template + embedding model/version recorded
sample retrieval test completed
```

## 6. Processing Flow

1. Load `provisions.jsonl` and `documents.jsonl` into in-memory join maps (or a lookup DB — ~1.4M provisions and ~150K documents).
2. Load embedding model; record name, version, dimension, and the `retrieval_text` template version.
3. Initialize vector DB; create collection with schema and filter indexes (§4 Step 3.2).
4. Stream `chunks.jsonl` in batches: join → build `retrieval_text` → encode → build payload → upsert.
5. Validate index — coverage + join-miss checks (§5).
6. Run sample retrieval tests.
7. Write `vector_index_report.md`.

## 7. Technology Stack

| Component | Recommended | Alternative |
| --- | --- | --- |
| Vector DB | Qdrant (Docker) | ChromaDB, FAISS |
| Embedding model | `intfloat/multilingual-e5-large` | `BAAI/bge-m3`, `paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding library | `sentence-transformers` | `transformers` + manual pooling |
| Language | Python 3.10+ | — |

## 8. Retrieval and Graph Guidance

Vector retrieval should:

- Retrieve at chunk level; every result is a single chunk from `chunks.jsonl`.
- Use `parent_unit_id` for same-provision expansion.
- Use `id_str` for document metadata and graph joins.
- Use joined `citation_anchor` for answer citations.
- Rank/filter by `legal_authority_rank`, `validity_group`, `unit_type`, and `structuring_quality_flags`.
- Prefer high-authority + active chunks for current-law questions; allow expired/low-authority chunks for historical, lineage, amendment, or validity questions.
- Accept a hard filter of `id_str` values from graph-guided retrieval; surface empty sets explicitly (`SPEC_Knowledge_Graph.md` §2, `SPEC.md` §5.6).

## 9. Acceptance Criteria

| Criterion | Status |
| --- | --- |
| All chunks from `chunks.jsonl` are indexed | Required |
| No chunks from quarantine or external-stub documents are indexed | Required |
| `retrieval_text` built at embed time (join) and embedded; `chunk_text` stored for LLM | Required |
| Payload populated by join to provisions + documents; zero join misses | Required |
| Filterable fields (`legal_authority_rank`, `validity_group`, facet `_code`, …) indexed | Required |
| Zero duplicate `chunk_id` in the DB | Required |
| Embedding model/version and `retrieval_text` template recorded | Required |
| Filter profiles (`current_law`, `broad`, `historical`, `graph_guided`) implemented | Required |
| Same-provision expansion implemented | Required |
| Citation-ready output format implemented | Required |
| Empty graph-guided filter surfaced, not silently ignored | Required |
| Ranking signals (boost/penalty) implemented | Required |
| Baseline naive RAG flow working end-to-end | Required |
| `vector_index_report.md` generated | Required |
| Sample retrieval tests completed and documented | Required |

## 10. Open Items for the Team

1. **`retrieval_text` template finalization** — agree the exact header format and version with the text-structuring team (`SPEC_Text_Structuring.md` §6). Any change requires a full re-embed.
2. **Join at scale** — ~1.4M provisions + ~150K documents held in memory during embedding is feasible but heavy; decide between in-memory maps, an embedded KV store, or a pre-join pass that materializes a temporary enriched chunk stream.
3. **Embedding model finalization** — small-scale comparison (`multilingual-e5-large` vs `bge-m3`) on Vietnamese legal text before the full ~1.5M-chunk run.
4. **Ranking weight tuning** — §4.4 weights are initial; tune with the evaluation dataset.
5. **Hardware/time budget** — ~1.5M chunks at 1024-dim is materially larger than the archived spec's ~100K estimate; size GPU hours and vector-DB storage/RAM accordingly.
6. **Derived currency vs. stored hint** — confirm whether the retrieval layer computes `currency_status(as_of)` itself or always defers to a `graph_guided` `id_str` filter from the graph team.
7. **Query preprocessing** — decide on query rewriting/expansion before embedding (`SPEC.md` §4.3).
8. **Evaluation dataset** — build retrieval test cases (query → expected chunks) for recall@k / precision@k.

## 11. Changes from the archived (pre-v2) spec

| Area | Archived spec | This v2 spec |
| --- | --- | --- |
| Chunk source | Fat `chunks.jsonl` with `retrieval_text` + denormalized metadata | **Slim** `chunks.jsonl` (12 fields); metadata joined from provisions + documents |
| `retrieval_text` | Read from the chunk row and embedded | **Built at embed time** by joining chunk → provision → document |
| Payload construction | Copy fields off the chunk row | **Join** to `provisions.jsonl` + `documents.jsonl` |
| Authority/currency filter | `dataset_tier` (primary/reference) | `legal_authority_rank` + `validity_group` (+ derived `currency_status`) |
| Facet filters | `linh_vuc_canonical`, `nganh_canonical`, `pham_vi_canonical`, `co_quan_ban_hanh_canonical` | `legal_field_code`, `sector_code`, `scope_code`, `issuing_authority_code` (from `{code,surface,raw}`) |
| Metadata names | `title_clean`, `so_ky_hieu_clean`, `loai_van_ban_canonical` | `title`, `so_ky_hieu`, `loai_van_ban` |
| Provision term | `legal_units.jsonl` / `LegalUnit` | `provisions.jsonl` / `Provision` |
| Structural fields on chunk | `structure_level`, `article_detected`, `parse_confidence`, `text_structuring_version` | Not on chunk; `unit_type`/`article_number` joined from provision; version dropped |
| Corpus size estimate | ~100K chunks | ~1.5M chunks (1,513,376) |
