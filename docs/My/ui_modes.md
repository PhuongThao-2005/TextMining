# Streamlit runtime modes and production transition

The Streamlit application uses one `QuestionResponse` contract and one answer renderer. Runtime mode changes only the answer provider; it does not create a second production retrieval path.

## Demo Preview

Demo Preview calls `DemoAnswerProvider` only. It does not construct an embedder, open a FAISS index, invoke a retriever or planner, access provider credentials, or use the network. Every response and source has `is_mock=True`, every source title begins with `DEMO`, and the page displays a persistent mock-data banner.

Deterministic questions expose one citation, multiple citations, an additional uncited source, safe abstention, an invalid marker warning, demo latency, and a demo Simple Planner trace. These are interface fixtures, not legal authorities, retrieval measurements, or factual answers.

## Production

Production calls `ProductionAnswerProvider`, a thin adapter over `answer_question`. The existing named-config loader, production stack builder, retriever factory, E2E runner, generation parser, citation validator, and agent executor remain authoritative. Explicit Production never substitutes demo output after a readiness or runtime failure.

## Auto

Auto runs the same readiness scan as Production. When every blocking check passes it selects Production. Otherwise it selects Demo Preview and states that production data is not ready. Demo responses remain visibly marked mock data.

## Artifact discovery and selection

Discovery is bounded to repository-controlled `data/` and `artifacts/` roots. It examines `index_manifest.json`, `manifest.json`, and `meta.json`; it never scans the whole disk or chooses by modification time.

Selection order is:

1. The exact `retrieval.dense.index_path` from the named config.
2. A manifest compatible with the config's embedding, corpus, index, and optional config identity.
3. A single unambiguous compatible artifact.
4. An explicit sidebar choice when several compatible artifacts exist.

A FAISS artifact requires `index.faiss`, `payloads.jsonl`, and a readable manifest. Supported manifest compatibility fields are `embedding_model`/`embedding_identity`, `embedding_dimension`/`dimension`, `corpus_version`/`corpus_identity`, `index_version`, `payload_count`, `vector_count`/`index_vector_count`, creation time, and config identity. Missing count or dimension metadata is warned about; identity mismatches and recorded payload-count mismatches block production. The loader still performs the actual FAISS load and exposes the real index dimension. The UI never rebuilds an index.

## Caching and teammate transition

Config parsing, readiness scans, and constructed production resources are cached. Resource keys include the effective config JSON, selected artifact path, overrides, and a cache epoch. Reset cache clears all three caches and rescans manifests, allowing Auto to transition from Demo Preview to Production after compatible teammate artifacts arrive without changing UI code.

## Citations and conversation

Both modes use service-validated citation references, source objects, answer segmentation, source cards, tabs, and bounded session turns. Citation IDs restart at 1 for every turn and remain separate from retrieval rank. Invalid markers are removed without remapping and cannot create source cards. Production sources originate only from retrieved contexts; demo sources never enter production response lists.

Conversation history is held only in `st.session_state`, capped at ten turns, and cleared when mode/config changes or New search is selected. Every Production follow-up calls the production service again and therefore retrieves again.

## Security and validation boundary

The UI does not display secret values, authorization data, hidden reasoning, raw tracebacks, or authenticated URLs. Model answers use native Streamlit Markdown without unsafe HTML; source chunks use plain text rendering. Application-owned static CSS is the only unsafe-HTML call.

A successful Demo Preview validates interface behavior only. A startup smoke validates import and server startup only. Browser behavior, compatible teammate artifacts, FAISS querying, live providers, semantic citation entailment, and production grounding require separate controlled validation.
