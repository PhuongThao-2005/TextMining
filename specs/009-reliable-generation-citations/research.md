# Research: Reliable Generation Citations

**Feature**: `009-reliable-generation-citations`  
**Date**: 2026-07-24  
**Aligned to**: Clarification session 2026-07-24 (eval record + local ids)

## 1. Source of truth for citations

**Decision**: Official citations are a deterministic projection of the **retrieved evidence list** passed into `generate_answer`. Model answer text is never parsed for citation identity.

**Rationale**: Spec FR-002/FR-010 and constitution I/IV. Model free text invents/omits anchors; as-built module documented this gap (`GENERATION_MODULE.md` §14).

**Alternatives considered**:
- Parse “Điều …” from answer → rejected
- Model JSON citation field → rejected (still model-owned)
- Post-hoc NLI on model citations → out of scope

## 2. Where logic lives

**Decision**: Pure `build_system_citations`, `SystemCitation`, outcome attachment, and eval-record helpers inside `src/generation/reasoning_client.py`; re-export from `generation/__init__.py`.

**Rationale**: Generation owns the answer package; one test surface; no new package.

**Alternatives considered**:
- New `citations.py` → defer until file size warrants
- Assemble only in evaluation scripts → rejected; citations must be on every generation outcome

## 3. Eval record shape (clarification)

**Decision**: Evaluation (not end-user UI) uses one JSON object per case:

```text
question_id, question_type, question, answer, relevant_articles[]
```

| Field | Canonical source |
|-------|------------------|
| `question_id` | `qa_final.qa_id` |
| `question_type` | `qa_final.answer_type` ∈ {`boolean`, `extractive`, `abstractive`, `unanswerable`} |
| `question` | `qa_final.question` |
| `answer` | `outcome.parsed.answer` or `""` |
| `relevant_articles` | projection of `outcome.citations` |

**Rationale**: FR-015; matches user-requested ALQ-style layout while binding types to existing benchmark (`data/benchmark/qa_final.jsonl`). Display labels like “Đúng/Sai” are external synonyms for `boolean`, not a second stored vocabulary.

**Alternatives considered**:
- `question_type` = `category` (single_hop, …) → rejected; weaker match to true/false style types
- Nested `question: {…}` object → rejected; flat keys per user example

## 4. Citation identity, grain, and local ids (clarification)

**Decision**:

- **Grain**: one `relevant_articles` row per eligible **chunk** (dedupe by full corpus `chunk_id` / chunk-grain `identity_key`). Distinct chunks of the same article → multiple rows (so `chunk_id` remains useful for eval).
- **Eval fields** (always present on projection):
  - `law_id` = `id_str` (doc_id) — **never** document title
  - `so_hieu` = `so_ky_hieu` or `""`
  - `article_id` = **local** only: `article_number` if set; else `parent_unit_id` with leading `"{law_id}::"` stripped (e.g. `preamble::0`)
  - `chunk_id` = **local** only: `str(chunk_index_in_unit)` if available; else segment after final `::chunk::` in corpus chunk id
- **Internal** on `SystemCitation`: keep `corpus_chunk_id`, `parent_unit_id` for joins/debug; omit from public eval JSON.
- **Never** use synthetic `chunk-{rank}` as identity (prompt-only).

**Rationale**: FR-005/FR-016–FR-019; user requirement that compound `doc::article::chunk` strings are hard to read for eval; constitution II satisfied via retained internal full keys.

**Alternatives considered**:
- Provision-level dedupe only (one row per article) → rejected after clarify (loses chunk_id usefulness)
- Emit full corpus ids in `article_id`/`chunk_id` → rejected (user readability)
- `law_id` = law title string → rejected (user: law_id is doc_id)

## 5. Field resolution from RetrievedChunk

**Decision**: Reader helper order for each logical field: attribute → top-level dict key → `metadata[key]` when mapping-like.

| Logical | Typical source on production path |
|---------|-----------------------------------|
| `id_str` / law_id | `RetrievedChunk.id_str` |
| `article_number` | `RetrievedChunk.article_number` |
| full `chunk_id` | `RetrievedChunk.chunk_id` |
| `parent_unit_id` | `RetrievedChunk.parent_unit_id` |
| `so_ky_hieu` | `metadata["so_ky_hieu"]` (payload); attr if present |
| `chunk_index_in_unit` | `metadata["chunk_index_in_unit"]`; attr if present |
| `citation_safe` | attr / key / metadata; **default True** if absent |

**Rationale**: `RetrievedChunk` already puts full payload on `metadata` (`retriever._to_retrieved_chunk`); first-class fields cover most joins. Avoids retrieve schema migration for v1.

**Alternatives considered**:
- Require first-class `so_ky_hieu` on `RetrievedChunk` → optional follow-up; not blocking
- Default `citation_safe=False` when absent → empties all current fixtures

## 6. Citation safety filter

**Decision**: Exclude only when `citation_safe is False` explicitly. Absent → include (default true).

**Rationale**: FR-007; production index does not serve external stubs as normal hits.

## 7. Order

**Decision**: First-seen order in the evidence sequence after chunk-grain dedupe (retrieval rank as passed in).

**Rationale**: FR-006.

## 8. When the citation list is non-empty

| Outcome path | `citations` / `relevant_articles` |
|--------------|-------------------------------------|
| Empty chunks (skip) | `()` / `[]` |
| Client `None` / config error | `()` / `[]` |
| API/format exception | `()` / `[]` |
| Success + fixed abstention | `()` / `[]` |
| Success + substantive answer | Full eligible list |

**Rationale**: FR-008/FR-013; safest abstention has no supporting citations.

## 9. Abstention detection

**Decision**: Module constant `INSUFFICIENT_CONTEXT_ANSWER` shared with `ANSWER_PROMPT`; abstention iff `parsed.answer.strip() == constant`.

**Rationale**: Deterministic offline tests; single source of truth.

## 10. Relationship to prompt / model prose

**Decision**: Keep prose grounding instructions. Do not strip model inline citations. Structured list is authoritative.

**Rationale**: FR-012; spec assumptions.

## 11. Downstream consumers

**Decision**:
- Eval/batch: `build_evaluation_case_record(qa_row, outcome)` (or equivalent) → FR-015 JSON
- Metrics: score `relevant_articles` only (SC-006)
- `GenerationOutcome.citations` default `()` for keyword backward compatibility
- Update `docs/spec/GENERATION_MODULE.md` in the same change set

**Rationale**: FR-011; Track B / notebooks / e2e scripts.

## 12. Testing strategy

**Decision**: Offline unit tests:
- Local-id projection (compound corpus → local article/chunk; law_id; so_hieu)
- Builder: order, chunk-grain dedupe, safety, uncitable drops, object vs dict vs metadata
- Orchestration: invent/omit model citations; empty/error/abstention → empty; three phrasings → identical list
- Eval record: keys/order semantics; `question_type` from `answer_type`; projection omits internal fields

**Rationale**: FR-014, SC-002–SC-008.

## 13. Resolved unknowns

All Technical Context items resolved; clarify session closed open product questions on eval shape and local ids. No remaining NEEDS CLARIFICATION for plan gates.
