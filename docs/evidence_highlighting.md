# Evidence highlighting audit and contract

## Audit result

Production is classified as `SOURCE_MAPPING_ONLY`.

The retriever returns `RetrievedChunk` with `chunk_id`, cleaned `chunk_text`, document ID, parent unit, title, article number, path, citation label, rank-related scores, and metadata. `build_payload` applies the repository's deterministic `clean_text` normalization before indexing. The embedding text adds a title/citation/unit header, but the stored and generated source body remains the cleaned chunk text. Page metadata is optional; article and provision boundaries are preserved only as fields, not character boundaries.

`prepare_citation_sources` assigns source IDs after exact deduplication. Generation receives numbered context blocks and returns ordinary final-answer text containing `[1]` markers. The provider/parser, agent contracts, E2E predictions, and existing run artifacts contain no `evidence_start`, `evidence_end`, supporting quote, sentence ID, token offsets, original-document offsets, or claim-specific passage record. `citation_references` record answer-marker positions only. Retrieval scores do not identify evidence spans.

Consequently, Production citations can open the correct retrieved chunk but cannot highlight an exact supporting sentence reliably. No lexical similarity, LLM guessing, or whole-chunk highlighting is used. Evidence highlighting is optional and does not affect Production readiness.

## Schema and validation

`EvidenceSpan` contains `context_id`, nullable `start_char`/`end_char`, nullable `quote`, `match_type`, and a non-semantic confidence label such as `exact match`. Supported match types are `explicit_offsets`, `exact_unique_quote`, `unavailable`, and `invalid`.

Explicit offsets are accepted only inside the Python string boundary, with a positive-length range and exact quote equality when both are recorded. Quote-only evidence must occur exactly once with no fuzzy normalization. Context mismatches, negative or stale offsets, quote mismatches, duplicate quotes, zero-length spans, and unsupported match types produce no highlight and a diagnostic warning. Unicode indices use Python character positions and line breaks are preserved.

The current contract supports one optional recorded span per citation source. It does not merge or infer multiple passages. Artifact citation objects may carry the optional evidence object without duplicating retrieved source text; old artifacts without it remain readable.

## Demo contract

The long Demo fixture stores explicit offsets for each of its three fictional sources. Tests assert `source_text[start_char:end_char] == quote`. These spans demonstrate UI behavior only and are not evidence that Production supports spans.

Selecting an inline marker opens a compact in-page preview with title, section/page, rank, score, and span status. **View source** opens an in-app dialog showing document/chunk identifiers, citation use, the complete retrieved text, and either the exact recorded span highlight or the appropriate unavailable/invalid explanation. **Open original document ↗** is separate, optional, and never appears for Demo sources.

The highlight renderer splits the carried source string at validated offsets, escapes every text segment (including `<script>` and other markup), and inserts only a fixed application-owned span wrapper around the validated segment. CSS preserves line breaks and wraps long content. Invalid and mapping-only content uses native plain-text rendering. Source text is never treated as model-generated HTML.

## Interpretation boundary

A cited source means the validated answer marker maps to a retrieved context. A recorded evidence span means an explicit range or uniquely exact quote passed mechanical validation. Semantic entailment asks whether the passage actually justifies the generated claim and is not established by either structural check.

**A highlighted span shows the passage recorded or exactly matched for a citation. It does not by itself prove that every generated claim is semantically entailed by that passage.**

## Manual validation

Run `streamlit run ui/app.py`, select Demo Preview, and choose **Long answer · 3 sources**. Review desktop, dark, and 390 px layouts; open each citation; open the full source; confirm only the configured passage is highlighted. Then use a deterministic Production-style response with a valid source mapping and no evidence: the source must open without highlight and state that the exact passage was not recorded.
