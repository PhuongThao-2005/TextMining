# SPEC_Vector_Retrieval.md

## 1. Purpose

This document specifies the vector retrieval stage for the G-LRAG pipeline.

The stage takes the structured output of the text structuring pipeline and makes it searchable via dense vector similarity:

```text
chunks.jsonl → Embedding → Vector DB → Retrieval API
```

The vector retrieval system is the primary semantic search path in the hybrid RAG architecture. It works alongside graph-based retrieval (specified in `SPEC_Knowledge_Graph.md`) to provide evidence for answer generation, per `SPEC.md` §4.7 and §6.6.

This stage directly serves two measurable success criteria from `SPEC.md` §3:
- Hallucination rate under 10% — by retrieving grounded, citation-ready chunks with rich metadata.
- Average response latency under 1 minute — by maintaining efficient indexing, filtering, and retrieval.

## 2. Core Requirements

- Index every chunk from `chunks.jsonl` produced by the text structuring stage.
- Embed `retrieval_text` (not `chunk_text`) as the primary embedding source — `retrieval_text` includes contextual information (title, citation label, legal path, article heading, validity metadata) that improves semantic matching.
- Store `chunk_text` as the clean content returned to the generation layer — the LLM sees only the grounded text, not the retrieval-enriched wrapper.
- Preserve all required metadata fields on each vector record for downstream filtering, ranking, citation display, and graph alignment.
- Support hard filtering by `dataset_tier`, `validity_group`, `unit_type`, `id_str`, and `linh_vuc_canonical` at query time.
- Support soft ranking signals based on metadata (tier, validity, parse confidence, quality flags).
- Return results with enough metadata for citation display, graph joins, and same-unit expansion.
- Never index chunks from `metadata_quarantine.jsonl` or `metadata_external_stubs.jsonl`.
- Provide a baseline naive RAG retrieval flow as the first working end-to-end path before graph-guided enhancements.

## 3. Inputs and Outputs

### Inputs

| Input | Purpose |
| --- | --- |
| `chunks.jsonl` | Retrieval chunks with `chunk_text`, `retrieval_text`, and full metadata |
| `legal_units.jsonl` | For same-unit expansion lookups (sibling chunks under same `parent_unit_id`) |
| `documents_structured.jsonl` | Document-level structuring status for filtering |
| `metadata_final.jsonl` | Authoritative metadata for cross-validation |

All files are produced by the text structuring stage (`data/processed/text_structuring/`).

### Outputs

Recommended output directory:

```text
data/processed/vector_retrieval/
```

| Output | Purpose |
| --- | --- |
| Vector database collection(s) | Searchable index of embedded chunks |
| `vector_index_report.md` | Indexing counts, quality checks, embedding stats |
| Retrieval API / module | Callable interface for the retrieval layer |

## 4. Step-by-Step Plan

### Step 1: Vector DB Setup

**Goal:** Choose and configure a vector database that supports dense vector search with metadata filtering.

**Recommended DB:** Qdrant (open-source, supports metadata filtering natively, runs locally via Docker).

**Alternatives considered:**
| Option | Pros | Cons |
| --- | --- | --- |
| Qdrant | Native metadata filtering, gRPC, local Docker, good Python SDK | Requires Docker |
| ChromaDB | Simple API, embedded mode | Limited filtering, less production-ready |
| Weaviate | Rich features, hybrid search | Heavier setup |
| FAISS + custom metadata store | Pure Python, lightweight | No native metadata filtering, must build filter layer manually |
| Milvus | Scalable, metadata filtering | Heavy infrastructure |

**Configuration:**
- Collection name: `legal_chunks` (primary), optionally `legal_chunks_reference` (for reference-tier separation).
- Vector dimension: determined by embedding model (see Step 2).
- Distance metric: **Cosine similarity** (standard for text embeddings).
- Payload (metadata) fields indexed for filtering — see §5.
- HNSW index parameters: `m=16`, `ef_construction=100` (default, tune later based on collection size).

**Decision: Single collection vs. dual collection**

Two viable strategies:

| Strategy | Description | When to use |
| --- | --- | --- |
| **Single collection** with `dataset_tier` filter | All chunks in one collection, filter at query time | Simpler, recommended for Phase 1 |
| **Dual collection** (`primary` + `reference`) | Separate collections, query reference only when needed | Better isolation, slightly more complex |

> **Recommendation:** Start with a single collection. Use `dataset_tier` as a filter payload. Revisit if performance or relevance degrades.

---

### Step 2: Embedding Pipeline

**Goal:** Convert `retrieval_text` of each chunk into a dense vector for indexing.

**Embedding model selection:**

| Criteria | Requirement |
| --- | --- |
| Language | Must support Vietnamese well |
| Dimension | 768–1024 recommended for quality/cost balance |
| Open-source | Preferred for local deployment |
| Performance | Proven on Vietnamese semantic tasks |

**Recommended models (in priority order):**

| Model | Dim | Notes |
| --- | --- | --- |
| `bkai-foundation-models/vietnamese-bi-encoder` | 768 | Vietnamese-specific, trained on Vietnamese STS |
| `intfloat/multilingual-e5-large` | 1024 | Strong multilingual, good Vietnamese support |
| `BAAI/bge-m3` | 1024 | State-of-art multilingual, supports dense + sparse |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | Lightweight, acceptable Vietnamese quality |

> **Recommendation:** Start with `intfloat/multilingual-e5-large` or `BAAI/bge-m3` for best Vietnamese quality. If resources are limited, use `paraphrase-multilingual-MiniLM-L12-v2`.

**Embedding process:**

```text
For each chunk in chunks.jsonl:
  1. Read retrieval_text → this is the text to embed
  2. Tokenize and encode with the embedding model
  3. Normalize the vector (L2 norm = 1 for cosine similarity)
  4. Store vector + metadata payload in the vector DB
```

**Batch processing:**
- Batch size: 32–64 chunks per batch (adjust based on GPU memory).
- Use `sentence-transformers` library for batch encoding.
- Log progress every 1,000 chunks.
- Estimated total: based on `chunks.jsonl` row count (tens of thousands to hundreds of thousands).

**Embedding the query:**
- At query time, embed the user query (or rewritten query) using the **same model** and **same normalization**.
- For `e5` models, prepend `"query: "` to query text and `"passage: "` to chunk text per model convention.

---

### Step 3: Chunk Indexing Strategy

**Goal:** Define exactly what data is stored alongside each vector in the DB.

#### 3.1 Vector Payload Schema (stored with each vector)

Every vector record in the DB must carry:

**Identity fields:**
```text
chunk_id                  # unique chunk identifier (primary key)
parent_unit_id            # for same-unit expansion
doc_id                    # document-level grouping
id_str                    # string ID for graph/metadata joins
```

**Structural fields:**
```text
unit_type                 # article, preamble, section, item, document
unit_index                # unit position in document
unit_heading              # heading text of the unit
article_number            # if unit_type=article
article_title             # if unit_type=article
section_path              # hierarchical path
chunk_index_in_unit       # position within unit
chunk_index_global        # global position in document
chunk_count_in_unit       # total chunks in parent unit
```

**Content fields (stored but NOT embedded):**
```text
chunk_text                # clean content for LLM generation
citation_anchor           # citation-ready string for answer display
```

**Metadata fields for filtering/ranking:**
```text
title_clean               # document title
citation_label            # e.g. "Luật số 01/2024/QH15"
loai_van_ban_canonical    # document type
so_ky_hieu_clean          # document number
co_quan_ban_hanh_canonical # issuing authority
ngay_ban_hanh_iso         # issue date
ngay_co_hieu_luc_iso      # effective date
ngay_het_hieu_luc_iso     # expiry date
issue_year                # issue year (integer, for range filter)
tinh_trang_hieu_luc_canonical # validity status text
validity_group            # active | expired | partial | suspended | future | unknown
dataset_tier              # primary | reference
pham_vi_canonical         # jurisdiction scope
nganh_canonical           # sector/industry
linh_vuc_canonical        # field/domain
quality_flags             # metadata quality flags from Dataset_SPEC
structuring_quality_flags # text structuring quality flags
```

**Structuring fields:**
```text
structure_level           # parsing depth achieved
article_detected          # boolean
unit_split                # boolean — was unit split into multiple chunks?
parse_confidence          # float from text structuring
text_structuring_version  # version tag
```

#### 3.2 Filterable Payload Fields

The following fields must be **indexed for filtering** in the vector DB:

| Field | Type | Filter use |
| --- | --- | --- |
| `dataset_tier` | keyword | Hard filter: primary vs reference |
| `validity_group` | keyword | Hard filter: active, partial, expired, etc. |
| `id_str` | keyword | Hard filter: graph-guided document set |
| `unit_type` | keyword | Filter by legal unit type |
| `loai_van_ban_canonical` | keyword | Filter by document type |
| `linh_vuc_canonical` | keyword | Filter by legal field/domain |
| `nganh_canonical` | keyword | Filter by sector |
| `pham_vi_canonical` | keyword | Filter by jurisdiction |
| `co_quan_ban_hanh_canonical` | keyword | Filter by issuing authority |
| `issue_year` | integer | Range filter by year |
| `article_detected` | boolean | Filter for article-structured chunks |
| `parse_confidence` | float | Filter out low-confidence chunks |

#### 3.3 Indexing Rules

- Index ALL chunks from `chunks.jsonl` — do not skip any chunk, even those with `article_detected = false` or low `parse_confidence`.
- Store `chunk_text` in the payload for retrieval output — this is what gets passed to the LLM.
- Do NOT embed `chunk_text` — embed only `retrieval_text`.
- Do NOT store `retrieval_text` in the vector payload (it's only used for embedding; storing it wastes space). If debugging is needed, it can be reconstructed from `chunks.jsonl`.
- Use `chunk_id` as the vector point ID (or map it deterministically to an integer ID if the DB requires it).
- Validate: zero duplicate `chunk_id` values before indexing.

---

### Step 4: Retrieval Tuning and Filtering Logic

**Goal:** Define how queries are executed against the vector DB, with filters and ranking.

#### 4.1 Default Retrieval Flow

```text
User Query
  → Query preprocessing (clean, normalize)
  → Embed query with same model
  → Vector similarity search with filters
  → Score and re-rank results
  → Return top-k chunks with metadata
```

#### 4.2 Filter Profiles

Define named filter profiles for different query types:

**Profile: `current_law` (default)**
```text
dataset_tier IN [primary]
validity_group IN [active, partial, future]
```

**Profile: `broad`**
```text
dataset_tier IN [primary, reference]
validity_group IN [active, partial, future, expired, unknown]
```

**Profile: `historical`**
```text
dataset_tier IN [primary, reference]
validity_group IN [expired, active, partial]
# No validity restriction — include expired for history/lineage
```

**Profile: `graph_guided`**
```text
id_str IN [<set from graph query>]
# Hard filter by document IDs returned from graph traversal
# If graph returns empty set → surface explicitly, do NOT fall back to unfiltered
```

Additional optional filters applied on top of any profile:
```text
loai_van_ban_canonical = <detected from query>    # e.g. "Luật", "Nghị định"
linh_vuc_canonical = <detected from query>         # e.g. specific legal field
pham_vi_canonical = <detected from query>           # e.g. jurisdiction
issue_year BETWEEN <start> AND <end>               # temporal range
```

#### 4.3 Retrieval Parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| `top_k` (initial retrieval) | 20 | Number of candidates from vector search |
| `top_n` (after re-ranking) | 5–10 | Number of chunks passed to LLM |
| `score_threshold` | 0.3 | Minimum cosine similarity to include |
| `same_unit_expansion` | true | If a chunk is retrieved, also fetch sibling chunks from same `parent_unit_id` |
| `max_expansion_chunks` | 3 | Max sibling chunks to add per unit expansion |

#### 4.4 Ranking Signals

After initial vector similarity retrieval, apply re-ranking based on:

**Boost signals (increase score):**
| Signal | Weight | Rationale |
| --- | --- | --- |
| `dataset_tier = primary` | +0.10 | Primary documents are citation-preferred |
| `validity_group = active` | +0.08 | Active law is most relevant for current-law questions |
| `unit_type = article` | +0.05 | Article-structured chunks are higher quality |
| `article_detected = true` | +0.03 | Better-parsed content |
| `parse_confidence >= 0.8` | +0.02 | Higher parse quality |
| Title/citation match with query | +0.10 | Direct document match |

**Penalty signals (decrease score):**
| Signal | Weight | Rationale |
| --- | --- | --- |
| `dataset_tier = reference` | -0.05 | Unless query is historical |
| `validity_group = expired` | -0.08 | Unless query is historical |
| `validity_group = unknown` | -0.03 | Uncertain validity |
| `quality_flags` contains severe warnings | -0.05 | Incomplete metadata |
| `structuring_quality_flags` non-empty | -0.02 | Structuring issues |

> **Note:** These weights are initial values. They should be tuned based on evaluation results.

#### 4.5 Same-Unit Expansion

When a chunk is retrieved, optionally fetch its sibling chunks under the same `parent_unit_id`:

```text
1. Retrieve top-k chunks via vector search
2. For each retrieved chunk:
   a. Look up parent_unit_id
   b. Fetch all chunks with same parent_unit_id from the vector DB
   c. Add adjacent chunks (chunk_index_in_unit ± 1) to context
   d. Cap at max_expansion_chunks
3. Deduplicate by chunk_id
4. Re-rank the expanded set
```

This implements the "same-unit expansion" guidance from `SPEC_Text_Structuring.md` §8.

---

### Step 5: Citation-Aware Retrieval Preparation

**Goal:** Ensure every retrieved chunk carries enough information for citation display in the final answer.

#### 5.1 Citation Contract

Every retrieval result returned to the generation layer must include:

```text
{
  "chunk_id": "...",
  "chunk_text": "...",              // clean text for LLM
  "citation_anchor": "...",        // human-readable citation string
  "citation_label": "...",         // document-level citation (e.g. "Luật số 01/2024/QH15")
  "title_clean": "...",            // document title
  "article_number": "...",         // if applicable
  "article_title": "...",          // if applicable
  "unit_type": "...",              // article, preamble, section, etc.
  "section_path": "...",           // hierarchical location
  "validity_group": "...",         // for validity indicator in citation
  "dataset_tier": "...",           // for confidence indicator
  "vector_score": 0.85,            // similarity score
  "id_str": "...",                 // for graph join
  "doc_id": "...",                 // for document-level operations
  "parent_unit_id": "..."          // for unit-level operations
}
```

#### 5.2 Citation Anchor Usage

The `citation_anchor` field from `chunks.jsonl` follows the format defined in `SPEC_Text_Structuring.md` §6:

```text
{citation_label}, Điều {article_number}: {article_title}
{citation_label}, {attachment_context}, {unit_heading}
{citation_label}, {unit_type} {unit_index}, đoạn {chunk_index_in_unit}
```

This field is stored as-is in the vector payload and returned with every retrieval result. The generation layer uses it to produce source citations in the final answer, per `SPEC.md` §5.5.

#### 5.3 Citation Safety Rules

- Only chunks from `metadata_final.jsonl` documents are citation-safe.
- Chunks from documents with `dataset_tier = reference` may be cited but must be clearly marked as reference/historical.
- Chunks from documents with `validity_group = expired` must not be presented as current law unless the user explicitly asks about historical regulations.
- External stubs (`metadata_external_stubs.jsonl`) must NEVER be indexed or cited.
- Quarantined records (`metadata_quarantine.jsonl`) must NEVER be indexed.

---

### Step 6: Baseline Naive RAG Retrieval Flow

**Goal:** Implement a minimal end-to-end retrieval flow before adding graph-guided enhancements.

#### 6.1 Baseline Flow

```text
┌──────────────┐
│  User Query  │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│  Query Preprocessing │
│  - Clean/normalize   |
|  - Rewrite           |   │
│  - Detect language   │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Embed Query         │
│  - Same model as     │
│    indexing           │
│  - Same prefix       │
│    convention         │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Vector Search       │
│  - Filter: current_  │
│    law profile       │
│  - top_k = 20        │
│  - score_threshold   │
│    = 0.3             │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Same-Unit Expansion │
│  - Fetch sibling     │
│    chunks            │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Re-rank & Select    │
│  - Apply ranking     │
│    signals           │
│  - Select top_n =    │
│    5-10              │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Format Output       │
│  - chunk_text for    │
│    LLM context       │
│  - citation_anchor   │
│    for citations     │
│  - metadata for      │
│    fusion layer      │
└──────────────────────┘
```

#### 6.2 Baseline API Interface

```python
def retrieve(
    query: str,
    filter_profile: str = "current_law",    # current_law | broad | historical | graph_guided
    id_str_filter: list[str] | None = None, # for graph-guided mode
    top_k: int = 20,
    top_n: int = 10,
    score_threshold: float = 0.3,
    expand_units: bool = True,
    extra_filters: dict | None = None,       # additional metadata filters
) -> RetrievalResult:
    """
    Returns:
        RetrievalResult with:
        - chunks: list of RetrievedChunk (chunk_text, citation_anchor, metadata, score)
        - total_candidates: number of candidates before re-ranking
        - filter_profile_used: which filter was applied
        - empty_filter_warning: True if graph_guided filter returned empty set
    """
```

#### 6.3 Graph-Guided Integration Point

When graph retrieval is ready (per `SPEC_Knowledge_Graph.md` §8):

```text
1. Graph retrieval returns a set of id_str values
2. Pass id_str set as id_str_filter to retrieve()
3. If id_str set is empty:
   - Surface explicitly to the caller (per SPEC_Knowledge_Graph.md §2)
   - Do NOT silently fall back to unfiltered search
   - Let the caller decide: retry without graph filter, or inform the user
4. Vector search filters chunks to only those documents
5. Continue with normal ranking and expansion
```

This is the primary integration point between vector retrieval and graph retrieval, per `SPEC.md` §4.8.

## 5. Validation and Report

### Full Coverage Counts

`vector_index_report.md` must include:

- `total_chunks_in_source`: rows in `chunks.jsonl`
- `total_chunks_indexed`: vectors inserted into DB
- `total_chunks_skipped`: must be 0 (no chunks should be skipped)
- `unique_documents_indexed`: distinct `id_str` count
- `unique_legal_units_indexed`: distinct `parent_unit_id` count

Required identity:

```text
total_chunks_in_source == total_chunks_indexed
total_chunks_skipped == 0
```

### Embedding Statistics

- Embedding model name and version
- Vector dimension
- Average embedding time per chunk
- Total embedding time
- Embedding token distribution (min, max, mean, p50, p95)

### Index Quality Checks

- Zero duplicate `chunk_id` in the vector DB
- All required payload fields present on every vector record
- Payload field type validation (keyword, integer, float, boolean)
- Sample retrieval test: 5–10 test queries with expected results manually verified
- Coverage: every `id_str` from `metadata_final.jsonl` that has `structuring_status` in (`structured_by_article`, `structured_by_fallback_units`, `document_fallback`) should have at least one chunk indexed

### Metadata Distribution

- Chunks by `dataset_tier`
- Chunks by `validity_group`
- Chunks by `unit_type`
- Chunks by `loai_van_ban_canonical` (top 10)
- Chunks by `linh_vuc_canonical` (top 10)
- `parse_confidence` distribution

### Hard Acceptance Metrics

```text
total_chunks_indexed == total_chunks_in_source
duplicate_chunk_id_in_db == 0
all vector records have non-empty chunk_text in payload
all vector records have non-empty citation_anchor in payload
all vector records have valid dataset_tier value
all vector records have valid validity_group value
zero chunks from quarantine or external stubs
embedding model and version recorded
sample retrieval test completed
```

## 6. Processing Flow

1. Load `chunks.jsonl` — validate row count, no duplicate `chunk_id`.
2. Load embedding model — record model name, version, dimension.
3. Initialize vector DB — create collection with schema and indexes.
4. For each chunk in batches:
   a. Extract `retrieval_text` for embedding.
   b. Encode batch with embedding model.
   c. Build payload from chunk metadata (§4, Step 3).
   d. Upsert vector + payload into DB.
   e. Log progress.
5. Validate index — run coverage checks (§5).
6. Run sample retrieval tests.
7. Write `vector_index_report.md`.

## 7. Technology Stack

| Component | Recommended | Alternative |
| --- | --- | --- |
| Vector DB | Qdrant (Docker) | ChromaDB (embedded), FAISS |
| Embedding model | `intfloat/multilingual-e5-large` | `BAAI/bge-m3`, `paraphrase-multilingual-MiniLM-L12-v2` |
| Embedding library | `sentence-transformers` | `transformers` + manual pooling |
| Language | Python 3.10+ | — |
| Orchestration | Script-based pipeline | — |

## 8. Retrieval and Graph Guidance

Vector retrieval should:

- Retrieve at chunk level — every result is a single chunk from `chunks.jsonl`.
- Use `parent_unit_id` for same-unit expansion — fetch sibling chunks when context is needed.
- Use `doc_id` / `id_str` for metadata and graph joins — the graph layer uses these to expand or filter documents.
- Use `citation_anchor` for answer citations — the generation layer displays this to the user.
- Rank/filter by `dataset_tier`, `validity_group`, `unit_type`, `parse_confidence`, metadata `quality_flags`, and `structuring_quality_flags`.
- Prefer `primary` and `active` chunks for current-law questions.
- Allow `reference` and expired chunks for historical, lineage, amendment, or validity questions.
- Support receiving a hard filter of `id_str` values from graph-guided retrieval.
- Surface empty graph-guided filter sets explicitly, per `SPEC_Knowledge_Graph.md` §2 and `SPEC.md` §5.6.

## 9. Acceptance Criteria

| Criterion | Status |
| --- | --- |
| All chunks from `chunks.jsonl` are indexed | Required |
| No chunks from quarantine or external stubs are indexed | Required |
| `retrieval_text` is used for embedding, `chunk_text` is stored for LLM | Required |
| Every vector record carries all required metadata payload fields | Required |
| Filterable fields are indexed in the vector DB | Required |
| Zero duplicate `chunk_id` in the vector DB | Required |
| Embedding model and version are recorded | Required |
| Filter profiles (`current_law`, `broad`, `historical`, `graph_guided`) are implemented | Required |
| Same-unit expansion is implemented | Required |
| Citation-ready output format is implemented | Required |
| Empty graph-guided filter is surfaced, not silently ignored | Required |
| Ranking signals (boost/penalty) are implemented | Required |
| Baseline naive RAG flow is working end-to-end | Required |
| `vector_index_report.md` is generated | Required |
| Sample retrieval tests are completed and documented | Required |

## 10. Open Items for the Team

1. **Embedding model finalization** — Run a small-scale comparison (50–100 sample queries) between `multilingual-e5-large` and `bge-m3` on Vietnamese legal text to pick the best model. This should be done before full indexing.
2. **Ranking weight tuning** — The boost/penalty weights in §4.4 are initial estimates. They should be tuned using the evaluation dataset once available.
3. **Query preprocessing** — Decide whether to apply query rewriting or expansion before embedding. This affects retrieval quality and is specified in `SPEC.md` §4.3 but not detailed here.
4. **Re-ranker model** — Consider adding a cross-encoder re-ranker (e.g. `cross-encoder/ms-marco-MiniLM-L-12-v2` or a Vietnamese-trained variant) as a second-stage ranker after initial vector retrieval. This would improve precision but adds latency.
5. **Coordinate with graph team** — Confirm the `id_str` filter interface for graph-guided retrieval. Agree on the contract: graph returns `list[str]` of `id_str`, vector filters by it.
6. **Coordinate with text structuring team** — Confirm `retrieval_text` format and whether it's stable. Any change to `retrieval_text` generation requires re-embedding.
7. **Hardware requirements** — Estimate GPU/CPU needs for embedding the full corpus. For ~100K chunks with a 1024-dim model, embedding takes ~1–2 hours on a single GPU. Vector DB storage is ~500MB–1GB.
8. **Evaluation dataset** — Work with the evaluation dataset team to create retrieval-specific test cases (query → expected relevant chunks) for measuring recall@k and precision@k.
