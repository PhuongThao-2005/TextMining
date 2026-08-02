# Retrieved-context citation contract

This contract maps model-visible citation numbers to the final retrieved chunks. It does not certify a formal legal citation and does not prove that a source semantically entails a claim.

## Source preparation and prompt

`prepare_citation_sources` receives the final ordered context list, removes exact duplicates, and assigns sequential IDs starting at 1. Retrieval rank is retained separately and is never reused as a display ID after deduplication. Only actual allow-listed metadata is copied; absent title, article, section, page, path, or URL stays absent. URLs are accepted only when an actual HTTP(S) value exists and credential-bearing URL/path values are dropped. The citation metadata carrier is capped at 4,000 text characters, while prompt formatting and the normalized response's context rows retain the complete retrieved chunk. The full source viewer resolves the matching context row already in that response; it does not refetch or reconstruct the document.

Both Base and reasoning generation use the same formatter:

```text
[SOURCE 1]
Title: ...
Section: ...
Document ID: ...
Content:
...
```

The prompt requires final-answer-only output, immediate `[n]` citations, supplied IDs only, no bibliography, and abstention for insufficient evidence. Run manifests record the prompt template version/hash and citation contract version/hash.

## Parsing and validation

Canonical syntax is adjacent markers: `[1][2]`. A single marker and comma groups such as `[1, 2]` are accepted; comma groups normalize to canonical syntax. Fenced-code markers are ignored. Ordinary or malformed bracket text is unchanged. Zero, negative, and unavailable IDs are removed, never remapped, and recorded in warning metadata. Repeated answer markers remain; source-card display deduplicates sources by first valid occurrence.

The service returns the safe answer, authoritative citation sources/references, warnings, metrics, and deterministic follow-up suggestions. The UI uses that response instead of reparsing raw contexts. Cited sources appear first; other retrieved contexts remain inspectable as additional sources.

## Structural citation coverage

The denominator is meaningful factual sentences after headings, short fragments, empty answers, and abstention answers are ignored. The numerator is those sentences ending with a valid marker (immediately before terminal punctuation is also accepted). Missing denominators remain null. This is a syntax/placement heuristic, not citation accuracy, legal correctness, or semantic entailment.

## Artifacts and compatibility

Each successful E2E prediction can contain `citations` without full text, `citation_references`, `citation_warnings`, and `citation_metrics`. The existing `retrieved_context` field remains the full context carrier. Run metrics aggregate only cases with available citation metrics and publish explicit denominators. Old prediction and metrics files without citation fields still load, and aggregator cells stay blank/null rather than becoming zero.

Conversation state exists only in Streamlit session state, is capped at 10 turns, and is cleared by **New search**. Every follow-up runs retrieval again and starts citation numbering at 1 for its new source list.

Optional evidence metadata is backward compatible: `EvidenceSpan` records a context ID, optional character offsets, optional exact quote, and an explicit match type. Missing fields remain null and old artifacts continue to load. Explicit offsets must satisfy `0 <= start < end <= len(source_text)` and, when a quote is present, the slice must equal it exactly. Quote-only evidence is accepted only when the exact quote occurs once. Invalid or stale spans are retained as diagnostics warnings and never highlighted.

The current Production capability is `SOURCE_MAPPING_ONLY`. The model returns answer text with `[n]` markers, not structured quote or offset records. Retrieved chunks contain cleaned `chunk_text` plus document/chunk/article/path metadata, but no citation-specific supporting passage. Source mapping therefore remains valid while exact highlighting remains unavailable. Demo fixtures carry explicit offsets solely to exercise presentation.

Citation selection is keyed by stable turn ID plus citation ID. Citation IDs restart at one each turn and are independent of retrieval rank. A highlighted span is recorded evidence for a source, not proof for every use of the same marker.

## In-app source interaction

The UI keeps source selection separate from external navigation:

- An inline `[n]` marker is a native Streamlit button with a key containing turn ID, citation ID, and occurrence. It selects only a citation present in that turn and shows a bounded in-page preview.
- **View source** is the primary action. It opens the normalized response's full retrieved chunk in an `st.dialog`, preserving the answer and conversation on the current Streamlit page. No retrieval, file read, URL reconstruction, or external fetch occurs.
- **Open original document ↗** is an optional secondary link. It appears only for a non-Demo source carrying a validated, credential-free HTTP(S) URL. Paths are never converted to URLs.
- **Close**, **New search**, and **Clear conversation** clear selection. Theme-only reruns do not.

The compact preview contains the source identity, article/section/page when present, a truncated excerpt, retrieval rank/score, evidence status, and an explicit Demo warning where applicable. The dialog contains the complete carried chunk and available metadata. This repository uses `st.dialog` because the pinned runtime supports it; a deployment on a Streamlit version without dialogs must use a state-controlled in-page panel with the same internal-action contract.

## Validation

```bash
python -m pytest -p no:cacheprovider tests/test_citations.py tests/test_ui_citations.py tests/test_ui_service.py
python -m compileall -q ui scripts src tests
streamlit run ui/app.py
```

The server command is only a startup smoke unless a real browser, provider, configured index, and corpus are exercised separately.
