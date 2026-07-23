# Quickstart: Reliable Generation Citations

**Feature**: `009-reliable-generation-citations`  
**Purpose**: Validate system-owned citations and eval records without a live model

## Prerequisites

- Repo root on PATH for `src` imports (same as existing generation tests)
- `pytest` available in the project environment
- No `LLM_*` credentials required for these checks

## 1. Offline unit tests (primary gate)

```powershell
pytest tests/generation -q
```

**Expected**:
- Existing generation tests still pass
- New tests cover:
  - local `article_id` / `chunk_id` (no `doc::…` compounds)
  - `law_id` = doc id; `so_hieu` from `so_ky_hieu`
  - chunk-grain order + dedupe
  - unsafe / uncitable drops
  - mocked `generate_answer`: invented model citations **not** in `outcome.citations`
  - same evidence, three answer texts → identical `outcome.citations`
  - empty context, config error, API error, abstention → `citations == ()`
  - substantive success → eligible evidence citations
  - eval case record keys: `question_id`, `question_type`, `question`, `answer`, `relevant_articles`

## 2. Pure builder smoke (optional REPL)

```python
from types import SimpleNamespace
from generation import build_system_citations

chunks = [
    SimpleNamespace(
        chunk_id="183807::article::34::chunk::1",
        parent_unit_id="183807::article::34",
        id_str="183807",
        article_number="34",
        chunk_index_in_unit=1,
        so_ky_hieu="20/2023/QH15",
        citation_anchor="Điều 34",
        citation_label="Luật mẫu",
        title="Luật mẫu",
        chunk_text="...",
        citation_safe=True,
    ),
    SimpleNamespace(
        chunk_id="183807::article::34::chunk::1",  # duplicate corpus id
        parent_unit_id="183807::article::34",
        id_str="183807",
        article_number="34",
        chunk_index_in_unit=1,
        so_ky_hieu="20/2023/QH15",
        citation_anchor="Điều 34",
        citation_label="Luật mẫu",
        title="Luật mẫu",
        chunk_text="...",
        citation_safe=True,
    ),
]
cites = build_system_citations(chunks)
# Expect one row after chunk-grain dedupe
assert len(cites) == 1 or len(cites.citations) == 1
row = cites[0] if isinstance(cites, tuple) else cites.citations[0]
assert row.law_id == "183807"
assert row.so_hieu == "20/2023/QH15"
assert row.article_id == "34"
assert row.chunk_id == "1"
assert "::" not in row.article_id or row.article_id.count("::") < 2  # local form
assert row.chunk_id == "1"
```

## 3. Eval record smoke (optional)

```python
from generation import build_evaluation_case_record  # name may match exports

qa = {
    "qa_id": "private_test_alquac25_1",
    "answer_type": "boolean",
    "question": "Hợp đồng điện tử ... có giá trị pháp lý trong mọi trường hợp.",
}
# outcome from generate_answer(...); citations already attached on success
record = build_evaluation_case_record(qa, outcome)
assert list(record)[:5] == [
    "question_id",
    "question_type",
    "question",
    "answer",
    "relevant_articles",
] or set(record) >= {
    "question_id",
    "question_type",
    "question",
    "answer",
    "relevant_articles",
}
assert record["question_type"] == "boolean"
for art in record["relevant_articles"]:
    assert set(art) >= {"law_id", "so_hieu", "article_id", "chunk_id"}
```

## 4. Orchestration smoke with mock (optional)

Same fake client pattern as `tests/generation/test_reasoning_client.py`:

1. Evidence with known local ids / so_hieu.
2. Mock invents “Điều 999” → not in `outcome.citations`.
3. Mock omits citations → list still from evidence.
4. Exact `INSUFFICIENT_CONTEXT_ANSWER` → `citations == ()`.

## 5. Spec / docs alignment check

After implementation:

- [ ] `docs/spec/GENERATION_MODULE.md` documents `SystemCitation`, local-id rules, eval record, outcome matrix
- [ ] §14 system citations in-scope (model-text faithfulness may remain out of scope)
- [ ] `generation/__init__.py` exports public symbols

## 6. Out of scope for this quickstart

- Live LLM calls
- End-user UI rendering
- Retrieve index rebuild
- Full gold citation scoring harness (consumes the field later)

## References

- [spec.md](./spec.md)
- [data-model.md](./data-model.md)
- [contracts/generation-citations.md](./contracts/generation-citations.md)
- [plan.md](./plan.md)
- [research.md](./research.md)
