# Contract: Generation System Citations

**Feature**: `009-reliable-generation-citations`  
**Module**: `src/generation`  
**Consumers**: notebooks, evaluation Track B, future UI, offline tests

## 1. Public types

### `SystemCitation`

Frozen value object. All string fields are plain `str` (empty string when unknown, never `None` on the public type).

```text
SystemCitation(
  law_id: str,              # doc_id / id_str
  so_hieu: str,             # from so_ky_hieu; "" if missing
  article_id: str,          # LOCAL only (e.g. "34" or "preamble::0")
  chunk_id: str,            # LOCAL only (e.g. "1")
  corpus_chunk_id: str,     # full corpus chunk id (internal joins)
  parent_unit_id: str,      # full provision id (internal joins)
  display_label: str,       # optional human label
  identity_key: str,        # non-empty; chunk-grain dedupe key
)
```

### Evaluation case record (eval export, not end-user UI)

```text
{
  "question_id": str,       # qa_id from qa_final
  "question_type": str,     # answer_type: boolean|extractive|abstractive|unanswerable
  "question": str,
  "answer": str,            # generation outcome answer or ""
  "relevant_articles": [
    {
      "law_id": str,
      "so_hieu": str,
      "article_id": str,    # local only
      "chunk_id": str       # local only
    }
  ]
}
```

`relevant_articles` is the public projection of `GenerationOutcome.citations` (internal join fields omitted).

### Eval helpers (public)

```text
to_relevant_article(citation: SystemCitation) -> dict
  # {"law_id", "so_hieu", "article_id", "chunk_id"}  # local ids only

build_evaluation_case_record(qa_row: Mapping, outcome: GenerationOutcome) -> dict
  # {
  #   "question_id": qa_row["qa_id"] or outcome.qa_id,
  #   "question_type": qa_row["answer_type"],
  #   "question": qa_row["question"],
  #   "answer": outcome.parsed.answer if parsed else "",
  #   "relevant_articles": [to_relevant_article(c) for c in outcome.citations],
  # }
```

Names may be slightly adjusted in implementation but MUST provide this behavior and be re-exported.

### `GenerationOutcome` (additive fields)

```text
GenerationOutcome(
  qa_id: str | None,
  parsed: ParsedAnswer | None,
  skipped_empty_context: bool,
  error: str | None,
  citations: tuple[SystemCitation, ...] = (),
  dropped_uncitable: int = 0,
  dropped_unsafe: int = 0,
)
```

Backward compatibility: new fields MUST have defaults so existing keyword constructions that omit them remain valid. Prefer keyword construction at all call sites.

## 2. Public functions

### `build_system_citations(chunks: Sequence[Any]) -> ...`

Pure function. No I/O. Accepts the same chunk-like contract as `format_context_for_prompt`, plus optional identity/safety fields:

```text
id_str, so_ky_hieu, article_number, parent_unit_id, chunk_id, chunk_index_in_unit,
citation_anchor, citation_label, title, citation_safe, metadata
```

**Returns** (exact shape chosen in implementation, both acceptable):
- `tuple[SystemCitation, ...]`, or
- a small result object / tuple including `(citations, dropped_uncitable, dropped_unsafe)`

**Guarantees**:
1. Does not read model answer text.
2. Deterministic for identical input sequences.
3. Dedupes by chunk-grain `identity_key`; preserves first-seen order.
4. Excludes `citation_safe is False`.
5. Excludes items with no identity key; counts them as uncitable drops.
6. Never fabricates `chunk-{rank}` identities.
7. Eval-facing `article_id` / `chunk_id` are local-only (never full `doc::…::chunk::n` strings).
8. `law_id` = document id; `so_hieu` = `so_ky_hieu` or `""`.

### `generate_answer(...) -> GenerationOutcome`

Unchanged signature for existing parameters. Behavior additive:

| Condition | `citations` |
|-----------|-------------|
| `not chunks` | `()` |
| `client is None` | `()` |
| exception during generate/parse | `()` |
| success and answer is insufficient-context phrase | `()` |
| success and substantive answer | `build_system_citations(chunks)` eligible list |

Insufficient-context phrase MUST match module constant shared with `ANSWER_PROMPT`:

```text
INSUFFICIENT_CONTEXT_ANSWER = "Không có đủ thông tin trong ngữ cảnh được cung cấp."
```

## 3. Non-goals (contract)

- No guarantee that `parsed.answer` prose citations match `citations`.
- No API to inject citations from outside evidence for a given call.
- No streaming citation partials.
- No multi-turn citation merge.

## 4. Export surface

`generation/__init__.py` MUST re-export at least:

- `SystemCitation`
- `build_system_citations`
- `to_relevant_article` (or equivalent)
- `build_evaluation_case_record` (or equivalent)
- `INSUFFICIENT_CONTEXT_ANSWER` (if public constant)
- existing symbols unchanged

## 5. Consumer checklist

| Consumer | Required change |
|----------|-----------------|
| Offline unit tests | Assert local ids, `so_hieu`, eval record; citations independent of mocked answer text |
| Evaluation / notebooks | Prefer `build_evaluation_case_record` / `relevant_articles` for metrics |
| Direct `GenerationOutcome(...)` | Use keywords; set `citations=()` on skip/error paths |
| `docs/spec/GENERATION_MODULE.md` | Document eval record + local-id rules; system citations in-scope |

## 6. Compatibility notes

- `ParsedAnswer` remains citation-free by design.
- `format_context_for_prompt` may keep `chunk-{rank}` fallback for **prompt labels only**; that path is not the system citation contract.
- Retrieve module schema need not change for v1: read `so_ky_hieu` / `chunk_index_in_unit` from attr or `metadata`; `citation_safe` default true when absent.
- Benchmark field map is `qa_final.jsonl` (`qa_id`, `answer_type`, `question`).
