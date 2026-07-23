# Data Model: Reliable Generation Citations

**Feature**: `009-reliable-generation-citations`  
**Date**: 2026-07-24

## Entities

### 1. Retrieved Evidence Item (input; existing)

Logical input to generation. Satisfied by `RetrievedChunk` or dict-like objects.

| Field | Role for citations | Required for inclusion |
|-------|--------------------|------------------------|
| `id_str` | → eval `law_id` (doc_id) | Preferred |
| `so_ky_hieu` | → eval `so_hieu` | Optional |
| `article_number` | → eval `article_id` when present | Preferred for articles |
| `parent_unit_id` | Full provision join key; local suffix → `article_id` if no article_number | Optional |
| `chunk_id` | Full corpus chunk key (internal joins/dedupe) | Preferred |
| `chunk_index_in_unit` | → eval local `chunk_id` when present | Preferred |
| `citation_anchor` | Display / internal identity aid | Optional |
| `citation_label` | Document-level display aid | Optional |
| `title` | Display aid only | Optional |
| `chunk_text` | Prompt context only (not a citation field) | N/A |
| `citation_safe` | Gate for citation list | Optional; default true if absent |
| `metadata` | May hold `citation_safe`, `so_ky_hieu`, or extras | Optional |

**Validation (builder)**:
- Evidence sequence order is authoritative for first-seen ranking.
- Empty sequence → no citations, no drops.

### 2. SystemCitation (new)

Frozen value type: one eval-facing / authoritative citation derived from evidence (maps 1:1 to a `relevant_articles[]` element).

| Field | Type | Description |
|-------|------|-------------|
| `law_id` | `str` | Document id (`id_str` / doc_id) — **not** law title |
| `so_hieu` | `str` | Official number from `so_ky_hieu`, or `""` |
| `article_id` | `str` | **Local** article id only (e.g. `"34"`); see local-id rules |
| `chunk_id` | `str` | **Local** chunk id only (e.g. `"1"`); see local-id rules |
| `corpus_chunk_id` | `str` | Full corpus chunk id for joins/dedupe (internal; optional on public eval JSON) |
| `parent_unit_id` | `str` | Full provision id for joins (internal; optional on public eval JSON) |
| `display_label` | `str` | Optional human label (anchor/title); not a substitute for the four eval fields |
| `identity_key` | `str` | Stable dedupe key (chunk grain) |

**Local-id rules** (eval-facing `article_id` / `chunk_id`):
- `article_id` = stripped `article_number` if non-empty; else `parent_unit_id` with leading `"{law_id}::"` removed (e.g. `preamble::0`). Never emit full `doc::article::n` as `article_id`.
- `chunk_id` = decimal string of `chunk_index_in_unit` if available; else segment after final `::chunk::` in corpus chunk id. Never emit full compound corpus chunk id as eval `chunk_id`.

**Identity key rules** (chunk grain; first non-empty):
1. Full corpus `chunk_id` if present
2. Composite of `law_id` + local `article_id` + local `chunk_id` if all formable
3. Else uncitable

If none → item is **uncitable** (not a `SystemCitation`).

**Invariants**:
- `identity_key` non-empty.
- Eval JSON projection always includes `law_id`, `so_hieu`, `article_id`, `chunk_id` (strings; `so_hieu` may be `""`).
- No field is populated from model answer text.
- Equality is structural (frozen dataclass).

### 2b. EvaluationCaseRecord (eval serialization)

Not end-user UI. Top-level keys in this order:

| Field | Source |
|-------|--------|
| `question_id` | QA `qa_id` |
| `question_type` | QA `answer_type` (`boolean` \| `extractive` \| `abstractive` \| `unanswerable`) |
| `question` | QA `question` |
| `answer` | `GenerationOutcome.parsed.answer` or `""` |
| `relevant_articles` | list of `{law_id, so_hieu, article_id, chunk_id}` from `SystemCitation` (omit internal-only fields) |

### 3. CitationBuildResult (optional internal)

| Field | Type | Description |
|-------|------|-------------|
| `citations` | `tuple[SystemCitation, ...]` | Deduped, ordered |
| `dropped_uncitable` | `int` | Count of evidence items skipped for missing identity |
| `dropped_unsafe` | `int` | Count skipped for `citation_safe is False` |

Implementation may return only the tuple from the public helper and keep counts on the outcome or as a second value; both counts MUST be available to tests (via return value or outcome fields).

### 4. GenerationOutcome (extended)

Existing terminal state plus citations:

| Field | Type | Description |
|-------|------|-------------|
| `qa_id` | `str \| None` | Unchanged |
| `parsed` | `ParsedAnswer \| None` | Unchanged |
| `skipped_empty_context` | `bool` | Unchanged |
| `error` | `str \| None` | Unchanged |
| `citations` | `tuple[SystemCitation, ...]` | **New**; default `()`; serializes to eval `relevant_articles` |
| `dropped_uncitable` | `int` | **New**; default `0` (recommended) |
| `dropped_unsafe` | `int` | **New**; default `0` (recommended) |

**State × citations matrix**:

| State | `parsed` | `skipped_empty_context` | `error` | `citations` |
|-------|----------|-------------------------|---------|-------------|
| Empty context | `None` | `True` | `None` | `()` |
| Misconfigured client | `None` | `False` | config msg | `()` |
| Transport/format failure | `None` | `False` | redacted | `()` |
| Success, abstention answer | `ParsedAnswer` | `False` | `None` | `()` |
| Success, substantive answer | `ParsedAnswer` | `False` | `None` | eligible list |

**Abstention**: `parsed.answer.strip() == INSUFFICIENT_CONTEXT_ANSWER` where the constant equals the fixed phrase in `ANSWER_PROMPT`.

### 5. ParsedAnswer (unchanged)

No citation fields. Remains answer + reasoning only so prose never becomes the citation source of truth.

## Relationships

```text
Retrieved Evidence Item*  --build_system_citations-->  SystemCitation*
                                                      |
generate_answer ------------------------------------> GenerationOutcome
        |                                                    |
        +-- parse_generation_response --> ParsedAnswer ------+
                                                             |
QA row (qa_final) + outcome --eval helper--> EvaluationCaseRecord
                             (relevant_articles = projection of citations)
```

- One generation call → one outcome → zero or more system citations (chunk grain).
- Duplicate evidence with the same corpus chunk id collapses to one `SystemCitation`.
- Distinct chunks of the same article remain separate rows (different local `chunk_id`).
- Eval JSON omits internal join fields; keeps `law_id`, `so_hieu`, local `article_id`, local `chunk_id`.

## Validation Rules (summary)

1. Determinism: same evidence sequence → same `citations` tuple.
2. Dedupe: unique `identity_key` only (chunk grain).
3. Order: first-seen among unique keys.
4. Safety: explicit `citation_safe=False` excluded.
5. No model-derived identities.
6. Synthetic rank labels (`chunk-{n}`) never invented as identity by the builder.
7. Eval-facing `article_id` / `chunk_id` are local-only (no `doc::…` compounds).
8. `law_id` is doc id; `so_hieu` is `so_ky_hieu`.
9. Substantive success never omits eligible citations present in evidence.
10. Skip/error/abstention never present non-empty citations as answer authority.
