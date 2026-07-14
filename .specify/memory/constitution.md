# G-LRAG Constitution

## Core Principles

### I. Legal Evidence Is Ground Truth
Every generated answer, retrieval result, and graph expansion MUST be grounded in source legal evidence. The project treats the citable legal provision as the authoritative unit for user-facing claims, while chunks are implementation-level retrieval units. Every retrieved chunk MUST resolve through `parent_unit_id` to a provision and through `id_str` to a document. Answers MUST include citation-ready metadata when available, and the system MUST explicitly report when evidence is insufficient instead of producing unsupported claims.

### II. Shared Identity Across Dataset, Vector, and Graph
The dataset, vector index, and knowledge graph MUST share one deterministic identity space: `id_str` for documents, `unit_id` for provisions, and `chunk_id` for retrieval chunks. Features MUST preserve these join keys end-to-end. No component may introduce opaque IDs without retaining reversible mappings to the canonical keys. Vector retrieval, graph traversal, citation display, evaluation, and debugging MUST be able to move through `chunk_id → parent_unit_id → id_str` without lossy translation.

### III. Traceability, Reconciliation, and No Silent Data Loss
All data transformations MUST be auditable. Raw records, normalized records, quarantined records, stubs, derived fields, and build reports MUST reconcile so data loss is visible. Invalid or incomplete records MUST be quarantined or flagged, not silently dropped. Derived facts such as validity events, authority ranks, text extraction status, edge normalization, and structuring quality MUST preserve enough provenance to explain how they were produced. Empty retrieval filters, missing text, unverified edges, join misses, and skipped records MUST be surfaced explicitly.

### IV. Legal Correctness Over Convenience
Legal authority, temporal validity, and edge direction are correctness requirements, not optional metadata. The project MUST keep authority separate from currency: `legal_authority_rank` expresses legal precedence, while currency is derived from validity timelines or clearly labeled hints. Graph and validity builders MUST refuse to use unverified direction groups for reasoning. Expired, partial, suspended, future, unknown, external-stub, or low-authority records MUST be handled according to their legal status and MUST NOT be presented as current binding law unless the query context explicitly permits it.

### V. Modular, Testable, Reported Pipelines
Each pipeline stage MUST be independently testable and report its acceptance criteria: dataset preparation, text structuring, vector indexing, graph construction, retrieval, fusion, generation, and evaluation. Modules MUST expose clear contracts through schemas, typed data structures, tests, and reports. Changes that affect retrieval text construction, chunk schemas, graph edge semantics, filtering behavior, or citation payloads MUST include corresponding tests and documentation updates.

### VI. Retrieval Quality and Evaluation Are Product Requirements
The system exists to reduce hallucinations and improve legal retrieval quality. Implementations MUST preserve evaluation hooks for recall, precision, answer grounding, hallucination rate, multi-hop reasoning, and latency. Retrieval should prefer high-authority, current, citation-safe evidence for current-law questions while retaining explicit modes for broad or historical search. Performance improvements MUST NOT bypass grounding, traceability, or legal-status filtering.

## Project Constraints

- **Domain**: G-LRAG is a graph-enhanced legal retrieval augmented generation system for Vietnamese legal documents.
- **Primary architecture**: Hybrid RAG with vector retrieval over chunks and graph retrieval over documents, provisions, chunks, relationships, validity events, and authority overlays.
- **Canonical artifacts**: v2 dataset artifacts are the preferred contracts: `documents.jsonl`, `edges.jsonl`, `external_stubs.jsonl`, `text_provenance.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `validity_timeline.jsonl`, and `authority_index.jsonl`.
- **Citation safety**: External stubs and quarantined records are never citation-safe. Quarantined data MUST NOT be indexed or ingested into production graph paths.
- **Chunk policy**: Chunks are the embedding and retrieval units; provisions are the citation units. Long provisions may be split, but chunks MUST retain `parent_unit_id` and `id_str`.
- **Embedding policy**: Retrieval text is built at embed time from chunk, provision, and document joins. Structured control fields such as authority rank and validity are payload/filter signals, not semantic text to embed.
- **Graph policy**: Graph construction consumes normalized source facts; it MUST NOT infer, flip, merge, or drop edges based on undocumented assumptions.
- **Error handling**: Empty results, insufficient context, join failures, unverified directions, and missing text MUST produce explicit warnings, reports, or fallback messages.
- **Privacy and security**: Source documents, logs, user queries, API keys, credentials, and sensitive legal or personal data MUST be stored and handled securely. Logs should contain only what is necessary for operation and evaluation.
- **Local maintainability**: Code SHOULD remain modular under `src/`, tests SHOULD live under `tests/`, operational scripts SHOULD live under `scripts/`, and design decisions SHOULD be recorded in `docs/`.

## Development Workflow and Quality Gates

1. **Spec first**: New behavior MUST be aligned with the relevant project specification before implementation. If behavior changes a contract, update the spec or changelog with the code change.
2. **Schema first**: Data-producing code MUST define and validate schemas before downstream consumers rely on the output.
3. **Test before acceptance**: New or changed functionality MUST include unit tests or integration tests appropriate to the affected stage. Critical legal correctness gates require regression tests.
4. **Report every build**: Dataset, vector index, graph build, and evaluation runs MUST produce counts, warnings, and acceptance checks sufficient for review.
5. **No silent fallback**: Components MUST NOT silently degrade from graph-guided filters to unfiltered retrieval, from verified currency to hints, or from citation-ready evidence to uncited answer generation.
6. **Document operational decisions**: Model choices, retrieval-text templates, filter profiles, ranking weights, graph traversal caps, and acceptance thresholds MUST be versioned or documented.
7. **Preserve backward compatibility deliberately**: Migration from older artifacts should be additive and reversible where practical. Breaking changes require a migration note and affected consumer list.

## Governance

This constitution governs project-level decisions for G-LRAG and supersedes ad hoc implementation preferences when conflicts arise. All specifications, implementation plans, tests, and reviews MUST check compliance with these principles.

Amendments require:
1. A documented rationale explaining the legal, retrieval, data, or engineering need.
2. An impact assessment for dataset artifacts, vector retrieval, graph retrieval, generation, evaluation, and existing tests.
3. Updated specs, changelog entries, and migration notes where applicable.
4. Review approval before treating the amendment as active guidance.

Versioning follows semantic intent:
- **MAJOR**: Changes or removes a core principle or governance rule.
- **MINOR**: Adds a principle, constraint, workflow gate, or materially expands guidance.
- **PATCH**: Clarifies wording without changing meaning.

**Version**: 1.0.0 | **Ratified**: 2026-07-13 | **Last Amended**: 2026-07-13
