# Feature Specification: Reliable Generation Citations

**Feature Branch**: `[009-reliable-generation-citations]`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "I want the citation within the generation module to be exactly reliable, not rely on the output of the generator"

## Clarifications

### Session 2026-07-24

- Q: What machine-readable shape should evaluation (not end-user UI) use for question + answer + citations? → A: Per-case eval record with `question_id`, `question_type`, `question`, then `answer`, then `relevant_articles[]` (see FR-015–FR-019). Example shape inspired by ALQ-style rows; field semantics bound to `data/benchmark/qa_final.jsonl` and corpus identity rules.
- Q: What is `law_id`? → A: Document id (`doc_id` / corpus `id_str`), not a free-text law title.
- Q: Must official number / số hiệu appear? → A: Yes — each `relevant_articles` item includes `so_hieu` from document `so_ky_hieu` (e.g. `01-QH/ND-123`, `103/SL`).
- Q: May `article_id` / `chunk_id` be full compound keys (`doc::…::chunk::n`)? → A: No. Emit **local** ids only so eval output stays readable (see FR-017).
- Q: How is `question_type` defined from `qa_final`? → A: Canonical value is `answer_type` from each QA row: one of `boolean`, `extractive`, `abstractive`, `unanswerable`. (Display labels such as “Đúng/Sai” may map to `boolean` for external sets; they are not a second stored vocabulary.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy legal citations on every answer (Priority: P1)

A legal researcher asks a Vietnamese legal question and receives an answer grounded in retrieved provisions. The citations shown with the answer are taken only from the evidence that was actually supplied to generation—not invented, rewritten, or selectively omitted by the language model. The researcher can open each citation and land on the same provision that supported the answer.

**Why this priority**: Citation trust is a core product requirement for legal RAG. Model free-text citations are unreliable and can hallucinate anchors, so the system must own the citation record.

**Independent Test**: Given a fixed question and a fixed set of retrieved evidence items with known citation anchors, run generation (or a mocked generator) and verify the returned citation list equals the deterministic projection of that evidence—independent of whatever the model wrote in the answer text.

**Acceptance Scenarios**:

1. **Given** retrieved evidence with distinct citation anchors A, B, and C was used as generation context, **When** generation completes successfully, **Then** the outcome exposes a citation list whose anchors are exactly {A, B, C} (order and dedupe rules as specified below), regardless of whether the model text mentions A, B, C, or other strings.
2. **Given** the model answer text invents a citation that is not in the supplied evidence, **When** the outcome is assembled, **Then** that invented citation does not appear in the system citation list.
3. **Given** the model answer text omits some or all citations, **When** the outcome is assembled, **Then** the system citation list still includes every eligible citation from the supplied evidence.

---

### User Story 2 - Clear citations when the system abstains or skips (Priority: P2)

A user asks a question for which evidence is empty or insufficient. The system either skips generation or returns the fixed insufficient-context response. In both cases the citation behavior is explicit and safe: no leftover or fabricated citations are shown as if they supported an answer.

**Why this priority**: Empty or abstaining paths are common and must not present false legal grounding.

**Independent Test**: Run generation with an empty evidence set and with a non-empty set that still yields the fixed abstention answer; inspect citation lists for emptiness vs. evidence-only contents.

**Acceptance Scenarios**:

1. **Given** no retrieved evidence is available, **When** generation is skipped for empty context, **Then** the citation list is empty and no answer is presented as cited.
2. **Given** evidence was supplied but the answer is the fixed insufficient-context abstention, **When** the outcome is assembled, **Then** either the citation list is empty or it is clearly labeled as context that was inspected but not used as supporting authority for a substantive answer—never mixed with a claim that those provisions answer the question.
3. **Given** generation fails (configuration or remote error), **When** the error outcome is returned, **Then** the citation list is empty or omitted; errors do not carry partial invented citations.

---

### User Story 3 - Evaluation and review use the same citation contract (Priority: P3)

An evaluator or notebook reviewer inspects end-to-end runs. For each case they receive a single eval-oriented record: question identity/type/text from the benchmark row, the system `answer`, and `relevant_articles` built only from retrieved evidence (with local `article_id` / `chunk_id`, `law_id`, and `so_hieu`). They compare citations to gold without parsing free-text answers. Hallucinated model citations do not inflate or pollute citation metrics. This record is for **evaluation and offline review**, not end-user UI chrome.

**Why this priority**: Reliable evaluation of grounding depends on a machine-readable, evidence-derived citation field shared by demos, E2E scripts, and scoring—aligned with benchmark fields in `qa_final`.

**Independent Test**: Serialize a batch of generation outcomes + QA rows into the eval record shape; score `relevant_articles` against gold using only that array; confirm the array does not change when model answer wording changes but evidence is fixed; confirm no compound `doc::article::chunk` strings appear in `article_id` or `chunk_id`.

**Acceptance Scenarios**:

1. **Given** two successful runs with identical evidence and different model answer wording, **When** `relevant_articles` are compared, **Then** the lists are identical.
2. **Given** a batch evaluation consumer, **When** it reads each eval record, **Then** it obtains `question_id`, `question_type`, `question`, `answer`, and `relevant_articles` without parsing answer prose for citations.
3. **Given** evidence for document `183807`, article number `34`, chunk index `1`, and `so_ky_hieu` `20/2023/QH15`, **When** the eval record is emitted, **Then** a `relevant_articles` item has `law_id="183807"`, `article_id="34"`, `chunk_id="1"`, `so_hieu="20/2023/QH15"` (not compound corpus keys).

---

### Edge Cases

- Evidence items missing citation anchors but carrying other identity fields must still produce a stable, non-empty citation identity via the established fallback chain; items that cannot form any identity are excluded from the citation list and surfaced as a warning count, not silently turned into fake law citations.
- Duplicate evidence pointing at the same **eval citation grain** (same local law/article/chunk identity) appears once in `relevant_articles`.
- Mixed citation-safe and non-citation-safe evidence: only citation-safe items appear in the citation / `relevant_articles` list; non-safe items must not be presented as citable authority.
- Very large evidence sets: citation list includes every eligible unique citation from the evidence actually passed into that generation call (no silent truncation of the citation record relative to context).
- Model embeds marker tokens or free-form “Điều …” strings in the answer: those strings never become the source of the system citation list.
- Non-article units (e.g. preamble) with empty `article_number`: `article_id` uses the **local unit suffix** of `parent_unit_id` after stripping the leading `{law_id}::` prefix (e.g. `preamble::0`), never the full compound id.
- Missing `so_ky_hieu`: `so_hieu` is emitted as an empty string; the item is still included if otherwise citable.
- Skip / error / abstention paths: `relevant_articles` is an empty array; `answer` follows generation outcome rules (empty/absent on skip-error as defined by outcome state; fixed abstention phrase when that path applies).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The generation outcome MUST expose a structured citation list derived solely from the retrieved evidence supplied to that generation call.
- **FR-002**: The system MUST NOT parse, trust, or require the generator’s free-text answer as the source of official citations.
- **FR-003**: Each citation entry MUST identify the legal unit using evidence metadata already present on retrieved items, and MUST expose eval-facing fields: `law_id` (document id), `so_hieu`, local `article_id`, and local `chunk_id` (see FR-016–FR-018).
- **FR-004**: Citation list construction MUST be deterministic: identical evidence input MUST yield an identical citation list across runs, models, temperatures, and answer phrasings.
- **FR-005**: The eval citation list (`relevant_articles`) MUST deduplicate by stable **chunk-level** identity (local `law_id` + local `article_id` + local `chunk_id`, or equivalent internal full `chunk_id` key) so the same chunk is not listed twice; distinct chunks of the same article MAY appear as separate rows so `chunk_id` remains meaningful for evaluation.
- **FR-006**: Citation order MUST follow first-seen order in the evidence sequence used for context (retrieval rank order), after deduplication.
- **FR-007**: Only citation-safe evidence MAY appear in the citation / `relevant_articles` list. External stubs, quarantined, or otherwise non-citation-safe items MUST be excluded from that list.
- **FR-008**: When generation is skipped for empty context, fails, or is misconfigured, the outcome MUST NOT present a non-empty citation list as support for an answer (`relevant_articles` MUST be `[]`).
- **FR-009**: When a substantive answer is produced, the outcome MUST attach the full eligible citation list for the evidence used in that call, even if the model text omits citations.
- **FR-010**: Invented or altered citation strings that appear only in model text MUST NOT be added to the system citation list.
- **FR-011**: Downstream consumers (notebooks, end-to-end evaluation) MUST be able to read citations from the structured outcome / eval record without parsing answer prose.
- **FR-012**: The generation module MAY continue to instruct the model to ground its prose in context, but prose grounding is advisory only; the structured citation list remains authoritative.
- **FR-013**: For the fixed insufficient-context abstention answer, the system MUST not imply that listed provisions answer the question; `relevant_articles` MUST be `[]` on that path.
- **FR-014**: Changes to this citation contract MUST remain independently testable offline without a live model, using fixed evidence fixtures and a mocked or absent generator where appropriate.
- **FR-015**: For evaluation export (not end-user UI), each case MUST be representable as one JSON object with exactly this top-level field order and names:
  1. `question_id` — benchmark case id (`qa_id` from `qa_final`)
  2. `question_type` — `answer_type` from the same QA row (`boolean` | `extractive` | `abstractive` | `unanswerable`)
  3. `question` — question text from the QA row
  4. `answer` — system-generated answer text for the case (from the generation outcome; empty string when no answer body exists)
  5. `relevant_articles` — array of evidence-derived citation objects (may be empty)
- **FR-016**: Each element of `relevant_articles` MUST include at least: `law_id`, `so_hieu`, `article_id`, `chunk_id`. Optional display aids (e.g. title) MUST NOT replace these fields.
- **FR-017**: Local id rules (mandatory readability):
  - `law_id` = document id (`id_str` / doc_id), e.g. `"183807"` — **not** the law title string.
  - `article_id` = article number only when present (e.g. `"34"`), **not** `"{doc}::article::{n}"` or other compound keys. If `article_number` is absent, use the local unit suffix of `parent_unit_id` after removing the leading `"{law_id}::"` prefix (e.g. `"preamble::0"`).
  - `chunk_id` = local chunk index only (e.g. `"1"` from `chunk_index_in_unit` or the segment after `::chunk::`), **not** `"{doc}::…::chunk::{n}"`.
- **FR-018**: `so_hieu` MUST be taken from document/provision official number metadata (`so_ky_hieu`), e.g. `"103/SL"`, `"01-QH/ND-123"`. Empty string if missing. MUST NOT be invented from model text.
- **FR-019**: Internal pipeline join keys (full corpus `chunk_id`, `parent_unit_id`, anchors) MAY be retained on internal types for debugging and joins, but **eval-facing** `article_id` and `chunk_id` MUST follow FR-017 local-only rules so consumers are not forced to parse compound strings.

### Key Entities

- **Retrieved Evidence Item**: One chunk (or equivalent) passed into generation, carrying clean text plus citation and identity metadata from retrieval (document id, `so_ky_hieu`, article number, local/full chunk ids, citation-safety flag, rank/order).
- **System Citation / Relevant Article**: One evidence-derived citation row for eval and authoritative citation use; exposes `law_id`, `so_hieu`, local `article_id`, local `chunk_id`; identity comes only from retrieved metadata; never from model invention.
- **Generation Outcome**: The terminal result of one generation attempt, including answer/reasoning state (success, skip, error) and the authoritative system citation list for that attempt.
- **Evaluation Case Record**: Eval-only serialization combining QA row fields (`question_id`, `question_type`, `question`) with `answer` and `relevant_articles`; not an end-user UI payload.
- **Citation Identity**: Stable key for dedupe of eval rows at **chunk grain** (full corpus chunk id or equivalent law+article+chunk local triple)—never a model-generated string.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of successful generation cases with non-empty eligible evidence, every `relevant_articles` row maps to an evidence item supplied to that call (no citations without evidence; no eligible citation-safe evidence omitted after chunk-level dedupe).
- **SC-002**: In 100% of test cases where the model answer text contains fabricated citation strings, zero fabricated strings appear in `relevant_articles`.
- **SC-003**: Holding evidence fixed, `relevant_articles` lists are identical across at least three different answer phrasings (including answers that omit all citations).
- **SC-004**: Empty-context and hard-failure paths produce `relevant_articles: []` in 100% of cases.
- **SC-005**: Offline unit tests covering citation construction, local id projection, deduplication, safety filtering, eval-record assembly, and outcome attachment pass without network access.
- **SC-006**: An evaluator can score citation presence against gold using only `relevant_articles` for an entire batch without reading answer text.
- **SC-007**: In 100% of offline fixtures with compound corpus ids, emitted `article_id` and `chunk_id` contain no `::`-joined document prefix forms (local ids only); `law_id` equals document id; `so_hieu` equals source `so_ky_hieu` when present.
- **SC-008**: Eval records always expose `question_id`, `question_type`, `question`, `answer`, and `relevant_articles` keys; `question_type` matches the QA row’s `answer_type`.

## Assumptions

- Retrieval already returns citation-ready evidence with document id, `so_ky_hieu`, article number, and chunk identity fields; this feature does not redesign retrieval or the corpus.
- Chunks remain the retrieval unit; eval citations are emitted at **chunk grain** with local article and chunk ids for readability and scoring.
- Benchmark input for field mapping is `data/benchmark/qa_final.jsonl` (`qa_id`, `answer_type`, `question`, …).
- “Exactly reliable” means the official citation record is system-owned and evidence-derived, not that the model’s prose is guaranteed free of mistaken legal references.
- Citation-safety flags and fallback identity rules already defined for retrieval/handoff are reused rather than inventing a parallel citation vocabulary.
- For abstention answers, `relevant_articles` is empty (safest).
- Multi-turn dialogue citation accumulation is out of scope; each generation call’s citations reflect only that call’s evidence.
- End-user UI layout is out of scope; the eval record and generation outcome supply the data contract only.
- Stripping or rewriting model answer text to remove bad inline citations is out of scope; reliability is achieved by authoritative structured citations.
- No live model is required to accept the citation-construction and eval-serialization behavior.
- Plan/data-model/tasks written before this clarification MUST be re-synced (`/speckit-plan` / tasks refresh) so `SystemCitation` fields match FR-015–FR-019.
