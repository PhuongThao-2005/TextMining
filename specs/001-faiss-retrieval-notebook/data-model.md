# Phase 1 Data Model: Full FAISS Retrieval System Notebook (SQLite cache + reasoning generator)

This feature reads existing `data/faiss_index/` and `data/benchmark/` artifacts; it introduces one new derived on-disk artifact (`payload_cache.sqlite`, already uploaded) and no new source-of-truth data. This document restates the on-disk entities from [`spec.md`](spec.md)'s Key Entities section for traceability, then defines the in-memory result shapes the two new modules — [`src/retrieval/sqlite_faiss_store.py`](../../src/retrieval/sqlite_faiss_store.py) and [`src/generation/reasoning_client.py`](../../src/generation/reasoning_client.py) — expose to notebook cells.

## 1. Source entities (read-only, restated from spec.md Key Entities)

| Entity | File | Grain | Fields the notebook depends on |
| --- | --- | --- | --- |
| FAISS index | `data/faiss_index/index.faiss` | 1 vector index | loaded via `faiss.read_index`; dimension must match embedder output |
| Payloads (source of truth) | `data/faiss_index/payloads.jsonl` | 1 per-chunk metadata payload | `chunk_id`, `parent_unit_id`, `id_str`, `chunk_text`, `citation_anchor`/`citation_label`, `title`, `unit_type`, `validity_group`, `legal_authority_rank` |
| ID map | `data/faiss_index/id_map.json` (optional) | int-id → point-id mapping | consumed by [`FaissVectorStore.load`](../../src/retrieval/faiss_store.py:66); unchanged by this plan |
| Payload SQLite cache | `data/faiss_index/payload_cache.sqlite` | 1 row per payload, keyed by `line_no` | `line_no` (PK), full payload JSON blob, plus a `meta` table holding `payload_mtime_ns`, `payload_size` for staleness checks |
| Benchmark QA case | `data/benchmark/qa_final.jsonl` | 1 question | `qa_id`, `question`, `reference_answer`, `answer_type`, `ground_truth` (doc/provision/chunk IDs), `category`, `difficulty` |

No field beyond what's listed above is required by any FR; `SQLitePayloadFaissVectorStore` must tolerate the same payload shape `FaissVectorStore` already tolerates (it reads the same `payloads.jsonl`).

## 2. In-memory result shapes — `src/retrieval/sqlite_faiss_store.py`

### `SQLitePayloadFaissVectorStore`

Implements the existing [`VectorStore`](../../src/retrieval/stores.py:19) ABC. Not a `@dataclass` — a stateful class owning a `sqlite3.Connection` and a loaded `faiss.Index`, mirroring [`FaissVectorStore`](../../src/retrieval/faiss_store.py:32)'s shape but backed by SQLite for payload lookup instead of an in-memory `list[dict]`.

```text
class SQLitePayloadFaissVectorStore(VectorStore):
    index: faiss.Index                  # loaded from index.faiss
    conn: sqlite3.Connection            # open connection to payload_cache.sqlite
    id_map: dict[int, str] | None       # optional, same as FaissVectorStore

    @classmethod
    def load(cls, index_dir: Path) -> "SQLitePayloadFaissVectorStore": ...

    def search(self, query_vector: list[float], top_k: int,
               filters: dict[str, Any] | None) -> list[SearchHit]: ...
    def scroll(self, filters: dict[str, Any], limit: int) -> list[SearchHit]: ...
    def recreate_collection(self, vector_size: int) -> None: ...
    def upsert(self, records: list[VectorRecord]) -> None: ...

    def total_vectors(self) -> int: ...
    def close(self) -> None: ...
```

`search`/`scroll` return the same [`SearchHit`](../../src/retrieval/stores.py:13) frozen dataclass already used by every other `VectorStore` implementation — no new result type is introduced at this layer, preserving interchangeability with `FaissVectorStore`/`QdrantVectorStore`/`InMemoryVectorStore`.

### `PayloadCacheStatus`

New small dataclass, internal to the module, backing FR-016's staleness check:

```text
@dataclass(frozen=True)
class PayloadCacheStatus:
    exists: bool            # cache file present under index_dir
    is_stale: bool          # size or mtime differs from payloads.jsonl
    payload_size: int       # payloads.jsonl current os.stat().st_size
    payload_mtime_ns: int   # payloads.jsonl current os.stat().st_mtime_ns
```

Produced by an internal `_check_payload_cache(index_dir: Path) -> PayloadCacheStatus` helper; consumed by `_ensure_payload_cache` (rebuild-if-stale logic) and directly unit-tested (fresh cache, missing cache, stale-by-size, stale-by-mtime — four cases in `tests/retrieval/test_sqlite_faiss_store.py`).

## 3. In-memory result shapes — `src/generation/reasoning_client.py`

### `GeneratorConfig`

Restates the spec's "Generator configuration" Key Entity as a concrete dataclass:

```text
@dataclass(frozen=True)
class GeneratorConfig:
    base_url: str
    api_key: str
    model_name: str

    def is_complete(self) -> bool:
        return bool(self.base_url and self.api_key and self.model_name)

    def masked_key(self) -> str:
        # api_key[:4] + '...' + api_key[-4:] if len > 8 else '***'
        ...
```

`masked_key()` is the only method permitted to render the key for display; `__repr__`/`__str__` are not overridden to include the raw key, and no method returns the raw `api_key` embedded in a formatted string. Unit-tested directly (`test_reasoning_client.py::test_masked_key_never_leaks_raw_value`).

### `GeneratorClient`

```text
class GeneratorClient:
    model: str
    client: openai.OpenAI     # constructed from GeneratorConfig.base_url/api_key

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None: ...
    def generate(self, prompt: str, *, temperature: float = 0.0) -> RawGenerationResponse: ...
```

Unchanged constructor shape from the existing notebook inline class; `generate()`'s return type changes from a bare `str` to `RawGenerationResponse` (below) so reasoning can be extracted without a second round trip through the SDK's response object.

### `RawGenerationResponse`

```text
@dataclass(frozen=True)
class RawGenerationResponse:
    content: str                      # response.choices[0].message.content, stripped
    reasoning_field: str | None       # response.choices[0].message.reasoning_content (or .reasoning), if present
```

Produced inside `GeneratorClient.generate()` by reading whatever the SDK response object exposes; passed to `parse_generation_response()` (below) rather than parsed inline, so parsing is unit-testable against a plain dataclass instance instead of a live SDK response object.

### `ParsedAnswer`

Restates the spec's "Generated answer" Key Entity as a concrete dataclass — this is the record type stored per question in both the ad hoc and benchmark generation flows:

```text
@dataclass(frozen=True)
class ParsedAnswer:
    answer: str                 # final answer text, <think> block stripped if present
    reasoning: str | None       # extracted reasoning/thinking text, or None
    reasoning_available: bool   # True if reasoning_field or a <think> block was found
    reasoning_source: str       # "field" | "think_block" | "not_returned"
```

Produced by `parse_generation_response(raw: RawGenerationResponse) -> ParsedAnswer`, implementing the three-case decision from research.md R4:
1. `raw.reasoning_field` is non-empty → `reasoning_source = "field"`, `reasoning = raw.reasoning_field`, `answer = raw.content`.
2. `raw.reasoning_field` is empty/None but `raw.content` contains a `<think>...</think>` block → `reasoning_source = "think_block"`, `reasoning` = text between the tags, `answer` = `raw.content` with the `<think>` block removed and whitespace trimmed.
3. Neither present → `reasoning_source = "not_returned"`, `reasoning = None`, `reasoning_available = False`, `answer = raw.content` unchanged.

Backs FR-020/FR-021/SC-007. Unit-tested for all three cases plus the edge case of an unterminated `<think>` tag (treated as case 3, not a crash).

### `GenerationOutcome`

Wraps `ParsedAnswer` with the per-question error/skip state needed by the batch/benchmark flow (FR-022/FR-023, Edge Cases "empty context" and "transient failure"):

```text
@dataclass(frozen=True)
class GenerationOutcome:
    qa_id: str | None            # None for the ad hoc single-question flow
    parsed: ParsedAnswer | None  # None if skipped or errored
    skipped_empty_context: bool  # True if generation was not attempted (zero retrieved chunks)
    error: str | None            # str(exception) if the generator call failed, else None
```

Exactly one of `parsed`, `skipped_empty_context=True`, or `error` is set per instance. Produced by `generate_answer()` (ad hoc) and by the per-question loop body inside `run_benchmark_sample()` (batch) — both call the same `parse_generation_response()` under the hood, so the three-way branching logic lives in one place, not duplicated between the ad hoc and batch code paths.

## 4. Relationships the notebook must preserve

```text
SearchHit (from SQLitePayloadFaissVectorStore.search/scroll)
  └─ payload["chunk_id"] / ["parent_unit_id"] / ["id_str"]  ── same fields FaissVectorStore already exposes

RetrievedChunk (src/retrieval/retriever.py, unchanged)
  └─ passed as `chunks` into format_context_for_prompt() / generate_answer()

GenerationOutcome.parsed.answer / .reasoning
  └─ displayed alongside the RetrievedChunk citations already shown by show_results()
     (same question, same retrieval pass — FR-022 "reusing that retrieval output")
```

`GenerationOutcome` never carries its own copy of the retrieved chunk text; it is displayed alongside (not merged into) the existing retrieval result record for a question, keeping the retrieval and generation entities independently inspectable per Constitution Principle I (evidence stays traceable to its retrieval source).
