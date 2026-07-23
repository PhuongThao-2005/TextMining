# Implementation Plan: Reliable Generation Citations

**Branch**: `009-reliable-generation-citations` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-reliable-generation-citations/spec.md`  
**Clarification**: Session 2026-07-24 — eval case record + local citation ids (FR-015–FR-019)

**Note**: Setup script under `.specify/scripts` is absent in this checkout; paths resolved from `.specify/feature.json` and repo layout. Working tree may be on `main`; feature branch name is the logical Spec Kit id.

## Summary

Make generation citations **exactly reliable** by attaching a structured, evidence-derived citation list to every `GenerationOutcome`. Official citations are built only from retrieved chunk metadata—never from model free text.

**Eval-facing contract** (not end-user UI): each case serializes to:

```text
question_id, question_type, question, answer, relevant_articles[]
```

where each `relevant_articles` item is `{ law_id, so_hieu, article_id, chunk_id }` with:

| Field | Source / rule |
|-------|----------------|
| `law_id` | document id (`id_str` / doc_id) — not law title |
| `so_hieu` | `so_ky_hieu` (official number), else `""` |
| `article_id` | **local** only (`article_number` or unit suffix after `{law_id}::`) |
| `chunk_id` | **local** only (`chunk_index_in_unit` or suffix after `::chunk::`) |

Dedupe grain is **chunk-level**. Pure `build_system_citations` + `generate_answer` attachment + eval record helper; offline tests cover local-id projection, construction, safety, abstention emptiness, and phrasing independence.

## Technical Context

**Language/Version**: Python 3.11+ (project standard; type hints / `from __future__ import annotations`)

**Primary Dependencies**: Existing generation stack only (`dataclasses`, stdlib). No new third-party packages. `openai` remains optional for live transport only.

**Storage**: N/A (in-memory outcome fields; no persistence schema change)

**Testing**: `pytest`, offline under `tests/generation/` (focused `test_system_citations.py` + existing `test_reasoning_client.py`)

**Target Platform**: Local library module used by notebooks, scripts, and evaluation Track B / batch export

**Project Type**: Library module inside monorepo (`src/generation`)

**Performance Goals**: Citation construction O(n) over evidence list; negligible vs. LLM latency

**Constraints**:
- Deterministic given identical evidence order
- No network required for citation / eval-serialization logic
- No silent invention of legal anchors (`chunk-{rank}` is prompt-only, not system citation identity)
- Eval `article_id` / `chunk_id` MUST NOT be full compound corpus keys (`doc::…::chunk::n`)
- Secrets must never appear on outcomes (unchanged)
- Constitution: evidence-grounded authority; external stubs / non-citation-safe never listed as authority
- Benchmark field map: `data/benchmark/qa_final.jsonl` (`qa_id`, `answer_type`, `question`)

**Scale/Scope**: Single-turn generation; typical evidence lists tens of chunks; one citation list per `generate_answer` call; one eval record per QA case when exported

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Legal Evidence Is Ground Truth | PASS | System citations only from supplied evidence; abstention/empty → no fake authority |
| II. Shared Identity Across Dataset, Vector, Graph | PASS | Internal `corpus_chunk_id` + `parent_unit_id` + `law_id` retain full join chain; eval projects **local** article/chunk ids for readability without discarding joins |
| III. Traceability / No Silent Data Loss | PASS | Uncitable items excluded with explicit drop count; not rewritten into fake law labels |
| IV. Legal Correctness Over Convenience | PASS | Non-citation-safe evidence excluded from citation / `relevant_articles` list |
| V. Modular, Testable, Reported Pipelines | PASS | Pure builder + outcome field + eval serializer; offline tests; `GENERATION_MODULE.md` contract update |
| VI. Retrieval Quality and Evaluation | PASS | Eval scores `relevant_articles` without parsing answer prose; aligns with `qa_final` types |
| Spec/schema/test gates | PASS | Spec + clarify done; data-model/contracts/quickstart aligned; tests mandatory |
| No silent fallback | PASS | Do not fall back from system citations to model-parsed citations |

**Post-design re-check**: PASS — design stays inside `src/generation`; optional thin helpers for eval JSON; no retrieve schema migration required for v1 (`so_ky_hieu` / `chunk_index_in_unit` read from attr or `metadata` payload).

## Project Structure

### Documentation (this feature)

```text
specs/009-reliable-generation-citations/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── generation-citations.md
├── spec.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/generation/
├── __init__.py              # Re-export SystemCitation, build_system_citations,
│                            # to_relevant_article / build_evaluation_case_record (names per impl),
│                            # INSUFFICIENT_CONTEXT_ANSWER
└── reasoning_client.py      # SystemCitation, builders, GenerationOutcome.citations,
                             # generate_answer attachment, eval record helper

docs/spec/
└── GENERATION_MODULE.md     # Outcome schema, eval record, local-id rules, scope

tests/generation/
├── test_reasoning_client.py
└── test_system_citations.py # Local ids, so_hieu, eval record, orchestration

# Consumers (defaults / keyword GenerationOutcome; eval export optional):
notebooks/archive/faiss_retrieval_ready.ipynb
scripts/_patch_faiss_hybrid_notebook.py
scripts/evaluate_e2e.py      # Prefer relevant_articles when wiring Track B (minimal touch)
data/benchmark/qa_final.jsonl  # Field source for question_id / question_type / question
```

**Structure Decision**: Keep citation + eval serialization inside the existing generation package. No new top-level package. Retrieve schema change **not** required for v1: `RetrievedChunk.metadata` already holds full payload (`so_ky_hieu`, `chunk_index_in_unit`); first-class attrs used when present (`id_str`, `article_number`, `chunk_id`, `parent_unit_id`).

## Complexity Tracking

> No constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach (for tasks phase)

1. Add frozen `SystemCitation` with eval fields (`law_id`, `so_hieu`, `article_id`, `chunk_id`) plus internal join fields (`corpus_chunk_id`, `parent_unit_id`, `display_label`, `identity_key`).
2. Implement pure `build_system_citations(chunks)`:
   - Resolve fields from object / dict / `metadata`
   - Project **local** `article_id` and `chunk_id` (FR-017)
   - Dedupe at **chunk grain** via `identity_key` (prefer full corpus `chunk_id`)
   - Safety filter + uncitable drop counts
3. Extend `GenerationOutcome` with `citations`, `dropped_uncitable`, `dropped_unsafe` (defaults).
4. In `generate_answer`: attach eligible list only on substantive success; `()` on skip, config/API error, and fixed abstention.
5. Add eval helpers:
   - project citation → `{law_id, so_hieu, article_id, chunk_id}`
   - assemble evaluation case record from QA row + outcome (`question_id`←`qa_id`, `question_type`←`answer_type`, …)
6. Do **not** parse answer text for citations; do **not** strip model prose.
7. Update exports, `GENERATION_MODULE.md`, offline tests, and any broken `GenerationOutcome(...)` call sites.

## Phase Outputs

| Phase | Artifact | Status |
|-------|----------|--------|
| 0 | [research.md](./research.md) | Regenerated (aligned to clarify) |
| 1 | [data-model.md](./data-model.md) | Aligned |
| 1 | [contracts/generation-citations.md](./contracts/generation-citations.md) | Aligned |
| 1 | [quickstart.md](./quickstart.md) | Regenerated |
| 2 | [tasks.md](./tasks.md) | Regenerated with plan alignment |
