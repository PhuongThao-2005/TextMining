# L_RAG Report Structure and Visual Plan

The report follows the system lifecycle:

**Problem → Data → Methodology → Implementation → Evaluation → Ablations → Discussion → Conclusion**

The visual plan is designed to demonstrate the work performed in the repository. Each technical subsection should contain at least one primary visual: a diagram, schema, table, chart, example, or screenshot of a reproducible system output.

Use the following conventions throughout the report:

- **Existing asset:** a visual already available in `docs/slide/imgs/` or an ablation-results directory.
- **Create:** a visual that should be generated for the report.
- **Table:** a compact structured comparison or audit record.
- **Worked example:** the same legal question carried through multiple stages of the system.

The strongest presentation will reuse one Vietnamese legal question as a running example. Show its source document, provision, chunk, graph neighbors, retrieval candidates, final evidence, and generated answer across Chapters 3 and 4.

## 1. Introduction

### 1.1 Background and Motivation

- **Create — motivation figure:** Show a Vietnamese legal question, the relevant legal provision, and the need for an answer with an explicit source citation.
- **Create — problem contrast:** Present three columns for keyword search, vector-only RAG, and L_RAG, showing what each method can and cannot preserve.

### 1.2 Problem Statement

- **Create — failure-mode diagram:** Show the main difficulties: long documents, legal hierarchy, cross-document references, outdated provisions, missing text, and unsupported answers.
- **Table — problem-to-consequence mapping:** Map each problem to its effect on retrieval, generation, or user trust.

### 1.3 Project Objectives

- **Table — objective-to-component mapping:** Map each objective to the implemented module, source file or script, and validation evidence.
- **Create — contribution map:** Connect dataset preparation, text structuring, graph construction, retrieval, generation, and evaluation to the project objectives.

### 1.4 Scope of the System

- **Create — scope boundary diagram:** Show the included corpus, preprocessing, graph, retrieval, generation, and evaluation stages, together with features outside the current implementation.
- **Table — included and excluded capabilities:** Clarify what the prototype supports and what requires future work.

### 1.5 Main Contributions

- **Create — contribution overview:** Use four or five labeled blocks for the main deliverables: structured legal corpus, G-LRAG graph, hybrid retrieval pipeline, citation-grounded generation, and controlled ablations.

### 1.6 Report Organization

- **Create — report roadmap:** Show the chapter sequence as a horizontal flow from problem definition to conclusion.

## 2. Background and Related Work

### 2.1 Retrieval-Augmented Generation

- **Create — standard RAG diagram:** Show query, retriever, retrieved chunks, prompt, LLM, and answer.
- **Create — grounding illustration:** Show how an answer changes when the model receives supporting evidence.

### 2.2 Legal Information Retrieval

- **Create — legal document hierarchy:** Illustrate document, article, clause, item, and chunk relationships.
- **Create — legal retrieval example:** Show why a semantically similar passage may still be unsuitable because of authority or validity.

### 2.3 Dense, Sparse, and Hybrid Retrieval

- **Table — retrieval comparison:** Compare dense retrieval, BM25, hybrid fusion, and their strengths for legal queries.
- **Create — vocabulary mismatch example:** Show a query and a legally equivalent passage that share few exact words but have similar meaning.

### 2.4 Knowledge-Graph-Augmented Retrieval

- **Create — graph retrieval illustration:** Show a seed chunk connected to its provision, document, amendment, citation, and neighboring chunks.
- **Table — vector retrieval versus graph retrieval:** Compare the evidence each method can discover.

### 2.5 Reranking and Citation-Grounded Generation

- **Create — two-stage ranking diagram:** Show candidate retrieval followed by cross-encoder scoring and top-10 selection.
- **Create — citation grounding illustration:** Connect factual claims in a generated answer to the retrieved legal provisions that support them.

### 2.6 Design Requirements for Legal RAG

- **Table — requirement traceability matrix:** Map legal reliability requirements to L_RAG design choices and evaluation checks.
- **Create — design rationale diagram:** Show how the requirements lead to structured text, graph overlays, hybrid retrieval, reranking, citations, and abstention.

## 3. Legal Dataset and Benchmark Construction

### 3.1 Legal Corpus and Raw Data Sources

- **Existing asset:** `docs/slide/imgs/document_type.png` for the distribution of legal document types.
- **Table — raw input inventory:** List source files, record types, identifiers, relationships, and text fields.
- **Create — raw-data example:** Display a small sanitized example of raw document metadata and a raw relationship record.

### 3.2 Dataset Normalization and Cleaning

- **Existing asset:** `docs/slide/imgs/Data_pipeline.png` as the main raw-to-final data pipeline.
- **Create — before-and-after record:** Show inconsistent raw fields beside the normalized document record.
- **Table — normalization rules:** List identifier, date, document type, status, and relationship transformations.

### 3.3 Relationship Processing and External References

- **Create — relationship-resolution diagram:** Show a source document, a resolved in-corpus target, and an unresolved external target represented as an external stub.
- **Table — relationship vocabulary:** List raw relationship labels, canonical labels, source direction, and verification status.
- **Create — external-stub example:** Show how an unavailable referenced document remains represented without being used as citation evidence.

### 3.4 Quarantine and Data-Quality Verification

- **Existing asset:** `docs/slide/imgs/edge_quarantine.png` for quarantined or unverified relationships.
- **Create — quality-control flow:** Show accepted records, quarantined records, verification, and final inclusion.
- **Table — audit counts:** Report input count, accepted count, quarantined count, external-stub count, and reconciliation status.

### 3.5 Legal Text Structuring

- **Existing assets:** `docs/slide/imgs/provision.png` and `docs/slide/imgs/Chunk.png`.
- **Create — hierarchy diagram:** Show `Document → Provision → Chunk` and the associated provenance pointers.
- **Table — structured artifact inventory:** Describe `documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, and `text_provenance.jsonl`.

### 3.6 QA Benchmark Construction

- **Create — benchmark-generation flow:** Show context sampling, question generation, verification, diversity filtering, deduplication, and final benchmark export.
- **Create — benchmark record example:** Display a question, category, answer type, reference answer, and ground-truth identifiers.
- **Table — benchmark construction stages:** Include the number of candidates and retained questions at each stage.

### 3.7 Question Categories and Answer Types

- **Existing assets:** `docs/slide/imgs/category.png`, `docs/slide/imgs/answer_type.png`, and `docs/slide/imgs/nuance.png`.
- **Create — category-answer-type matrix:** Show how categories such as single-hop, citation, validity, multi-hop, and cross-document relate to abstractive, boolean, extractive, and unanswerable answers.

### 3.8 Ground-Truth Evidence

- **Create — evidence-link diagram:** Connect a benchmark question to its reference answer, document IDs, provision IDs, and chunk IDs.
- **Create — annotated JSONL record:** Highlight the fields used for retrieval evaluation and the fields used for generation evaluation.
- **Table — ground-truth coverage:** Summarize evidence availability for answerable and unanswerable questions.

### 3.9 Dataset Statistics and Validation

- **Existing assets:** `docs/slide/imgs/length.png`, `node_type_distribution.png`, and `document_type.png` where applicable.
- **Table — final corpus statistics:** Report documents, provisions, chunks, edges, and external stubs.
- **Create — validation dashboard:** Combine corpus size, missing-text counts, orphan counts, quarantine counts, and reconciliation checks.

## 4. L_RAG System Design and Methodology

### 4.1 End-to-End System Architecture

- **Existing asset:** `docs/slide/imgs/system_architecture.png` as the main architecture figure.
- **Create — labeled architecture version:** Add clear labels for corpus construction, graph construction, vector indexing, retrieval, ranking, generation, and output.
- **Table — component responsibilities:** List each component, its input, output, and implementation location.

### 4.2 Offline Data and Index Construction

- **Existing asset:** `docs/slide/imgs/graph_pipeline.png` for the graph-building flow.
- **Create — offline pipeline:** Show normalized data branching into structured text, graph artifacts, and vector-index artifacts.
- **Create — artifact lineage diagram:** Connect each input file to the generated artifact consumed by retrieval or generation.

### 4.3 Online Query-Processing Workflow

- **Create — sequence diagram:** Show query input, embedding, dense/BM25 retrieval, graph filtering or expansion, fusion, reranking, context construction, and generation in time order.
- **Create — runtime decision flow:** Include the paths for normal answering, insufficient evidence, invalid filters, and unanswerable questions.

### 4.4 Knowledge Graph Construction

- **Existing assets:** `docs/slide/imgs/graph_pipeline.png`, `node_type_distribution.png`, and `edges_dashboard.png`.
- **Create — graph schema:** Show Document, ExternalStub, Provision, and Chunk nodes with their relationships.
- **Create — structural-edge diagram:** Illustrate `HAS_PROVISION`, `HAS_CHUNK`, `PROVISION_NEXT`, and `CHUNK_NEXT`.
- **Create — legal-edge diagram:** Illustrate `AMENDS`, `REPLACES`, `CITES`, and validity-related relationships.
- **Create — overlay diagram:** Show how validity and authority metadata are joined at query time.
- **Create — traversal example:** Start from a seed chunk and show the returned graph path and evidence context.
- **Table — graph API mapping:** Map loader, parser, builder, traversal, overlay, context-builder, and persistence responsibilities to implementation modules.

### 4.5 Retrieval and Ranking

- **Existing asset:** `docs/slide/imgs/retrieve_pipeline.png` as the retrieval overview.
- **Create — embedding representation example:** Show chunk-only text beside title-plus-provision-header-plus-chunk text.
- **Create — dense retrieval diagram:** Show query and chunks becoming normalized vectors and being searched in FAISS.
- **Create — sparse retrieval diagram:** Show Vietnamese tokenization, BM25 scoring, and ranked results.
- **Create — RRF illustration:** Show two ranked lists being merged into one candidate list.
- **Create — graph expansion illustration:** Show seed candidates before expansion and evidence candidates after expansion.
- **Create — reranking flow:** Show a 30-candidate pool being scored by a cross-encoder and reduced to the final top 10.
- **Table — reranker configuration:** Compare mMiniLM, BGE, Jina, and Qwen3 by model size, role, and expected cost.

### 4.6 Answer Generation

- **Create — context-construction diagram:** Show selected chunks being serialized with rank, document, provision, and citation metadata.
- **Create — prompt anatomy:** Annotate system instructions, question, evidence context, answer type, citation rules, and abstention rule.
- **Create — answer-format examples:** Show boolean, extractive, abstractive, and unanswerable output formats.
- **Create — citation mapping:** Highlight answer claims and connect each claim to a supporting chunk or provision.
- **Create — insufficient-context branch:** Show how the system returns an abstention response when usable evidence is unavailable.

### 4.7 End-to-End Worked Example

- **Create — six-stage storyboard:** Use one real benchmark question and show: source document → structured provision → chunk → graph neighborhood → ranked evidence → final cited answer.
- **Create — evidence table:** Show each retrieved chunk, its rank, retrieval source, graph status, citation status, and use in the final answer.
- **Create — success or failure comparison:** If possible, show one successful case and one case where the system correctly abstains or retrieves incomplete evidence.

## 5. Implementation and Experimental Setup

### 5.1 Software Architecture and Project Modules

- **Create — repository map:** Organize `src/retrieval`, `src/knowledge_graph`, `src/evaluation`, `src/generation`, and `scripts` by responsibility.
- **Create — module dependency diagram:** Show how loaders, schemas, stores, retrievers, graph facades, context builders, and evaluators interact.
- **Table — implementation inventory:** Map important modules and scripts to the report subsection where they are explained.

### 5.2 Dataset, Graph, and Vector-Index Build Process

- **Create — command workflow:** Show the order of dataset building, graph pickle creation, vector-index construction, and evaluation.
- **Create — build checkpoint diagram:** Mark the inputs, outputs, and validation checks after each stage.
- **Table — build commands and artifacts:** Include script name, purpose, inputs, outputs, and verification command.

### 5.3 Runtime Configuration and Model Selection

- **Table — model and configuration matrix:** Include embedding model, tokenizer, FAISS settings, BM25 parameters, rerankers, generator, temperature, and token limits.
- **Create — sequential model lifecycle:** Show load → run → delete → empty GPU cache for reranker evaluation.
- **Create — configuration example:** Display a compact resolved configuration with sensitive credentials removed.

### 5.4 Input, Output, and Intermediate Artifacts

- **Create — artifact lineage map:** Show how JSONL, graph, index, retrieval, prediction, metrics, latency, and manifest files relate.
- **Table — artifact contract:** Record the format, key identifiers, producer, consumer, and purpose of each artifact.
- **Create — output example:** Show a retrieval case and an end-to-end prediction record with identifiers and metrics.

### 5.5 Evaluation Questions

- **Table — research-question map:** Connect each question to the ablation, changed component, fixed components, and primary metrics.
- **Create — question-to-evidence diagram:** Show how each experimental question isolates one part of the system.

### 5.6 Baselines and Ablation Configurations

- **Create — ablation matrix:** Rows are configurations; columns are dense text, sparse retrieval, graph, fusion, reranking, generator prompt, candidate budget, and final context size.
- **Create — controlled-comparison diagram:** Highlight what changes and what remains fixed in each ablation family.

### 5.7 Evaluation Metrics

- **Create — metric taxonomy:** Separate retrieval metrics, generation-overlap metrics, decision diagnostics, citation diagnostics, and efficiency metrics.
- **Table — metric definitions:** Include formula, evaluation subset, interpretation, and limitation for Recall@k, Hit@k, MRR, nDCG, EM, Token F1, ROUGE-L, citation presence, and latency.
- **Create — retrieval metric illustration:** Use a small ranked list to demonstrate relevance, rank, and gold-chunk matching.

### 5.8 Experimental Protocol

- **Existing asset:** `docs/slide/imgs/eval_pipeline.png` as the evaluation workflow figure.
- **Create — paired-evaluation diagram:** Show matching by `qa_id`, answerable-only retrieval scoring, scheduled-denominator decision scoring, and paired deltas.
- **Create — bootstrap illustration:** Show question-level resampling and confidence-interval construction.

### 5.9 Reproducibility and Run Management

- **Table — run ledger:** Include run name, configuration, corpus/index version, question count, completion count, and output directory.
- **Create — reproducibility checklist:** Show manifest, configuration, predictions, metrics, latency, and error files as a complete run package.

## 6. Ablation Studies

### 6.1 Embedding Text Ablation: Chunk-Only versus Chunk+Metadata

- **Create — paired input figure:** Show the exact text sent to the encoder in both conditions.
- **Existing assets:** `ablation_study/chunkOnly_vs_chunkMetadata/results/success_at_k_curve.png` and `paired_win_tie_loss.png`.
- **Create — result table:** Report exact-chunk retrieval and document-level retrieval side by side.
- **Create — qualitative retrieval example:** Show how metadata helps identify the correct document while changing provision-level ranking.

### 6.2 Retrieval Ablation: Dense versus Hybrid Retrieval

- **Create — ranked-list comparison:** Show dense results, BM25 results, and their RRF-fused list for the same query.
- **Create — grouped metric chart:** Compare Recall@10, MRR@10, nDCG@10, and latency for DenseOnly and HybridOnly.
- **Table — paired differences:** Report absolute scores, paired deltas, confidence intervals, and interpretation.

### 6.3 Graph Ablation: With versus Without Graph Expansion

- **Create — before-and-after evidence map:** Show seed chunks, graph-added chunks, displaced chunks, and retained chunks.
- **Create — graph expansion outcome chart:** Compare gold evidence added, gold evidence lost, average context size, and identity precision.
- **Existing asset:** `docs/slide/imgs/edges_dashboard.png` for relationship-level context.
- **Create — qualitative graph case:** Show a case where graph expansion adds useful related evidence and a case where it displaces a relevant seed.

### 6.4 Reranker Ablation

- **Existing assets:** `charts.png`, `forest_plot.svg`, and `pareto_plot.svg` under `ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/`.
- **Create — ranking movement figure:** Show the rank of gold chunks before and after each reranker.
- **Table — quality-cost comparison:** Report Recall@10, MRR@10, nDCG@10, Token F1, ROUGE-L, reranker latency, and total latency.
- **Create — candidate-ceiling diagram:** Show that all rerankers receive the same 30-candidate pool and can only reorder or retain existing evidence.

### 6.5 Generator Ablation: Base Prompt versus Chain-of-Thought Prompt

- **Existing assets:** `paired_token_f1_delta.svg`, `win_tie_loss.svg`, and `refusal_confusion.svg` under the generator-reasoning results directory.
- **Create — prompt comparison:** Show the structural difference between Base and CoT prompts without reproducing hidden reasoning.
- **Table — paired generation results:** Report EM, Token F1, ROUGE-L, citation presence, structural coverage, refusal behavior, and latency.
- **Create — output comparison:** Display the same retrieved context with the two generated outputs and annotate differences in answer quality and citations.

### 6.6 Performance by Question Category and Answer Type

- **Create — category performance chart:** Use grouped bars or small multiples for single-hop, citation, validity, multi-hop, and cross-document questions.
- **Create — answer-type performance chart:** Compare boolean, extractive, abstractive, and unanswerable cases.
- **Table — subgroup denominators:** Report the number of questions in each subgroup so every chart is interpretable.

### 6.7 Evidence Coverage, Abstention, and Citation Analysis

- **Create — evidence-strata chart:** Compare fully supported, partially supported, and unsupported contexts.
- **Create — abstention confusion matrix:** Show answerable answers, answerable refusals, unanswerable refusals, and unsupported answers.
- **Create — citation flow chart:** Show retrieved chunks, citation-ready chunks, cited sources, and uncited factual sentences.
- **Table — diagnostic limitations:** Clearly distinguish structural citation and refusal diagnostics from human-validated legal correctness.

### 6.8 Latency and Efficiency Comparison

- **Create — latency decomposition:** Break total latency into retrieval, graph processing, reranking, generation, and overhead.
- **Create — quality-latency Pareto chart:** Plot retrieval or generation quality against p50 and p95 latency.
- **Existing asset:** `pareto_plot.svg` for the reranker quality-cost frontier.
- **Table — resource observations:** Include candidate count, final context size, model size, and available latency statistics.

### 6.9 Qualitative Ablation Examples and Failure Cases

- **Create — standardized case-study layout:** Query, expected evidence, retrieved evidence, graph changes, generated answer, citations, and diagnosis.
- **Create — success case:** Show a query where the selected evidence supports a clear cited answer.
- **Create — retrieval failure case:** Show missing or incorrectly ranked gold evidence.
- **Create — graph failure case:** Show context displacement or an incorrect relationship path.
- **Create — generation failure case:** Show unsupported, incomplete, or incorrectly formatted output.

### 6.10 Summary of Ablation Findings

- **Create — decision table:** For every ablation, list the changed component, observed effect, quality impact, latency impact, and recommended decision.
- **Create — system recommendation diagram:** Show the configuration supported by the evidence and the components requiring further validation.

## 7. Discussion, Limitations, and Ethical Considerations

### 7.1 Interpretation of the Main Findings

- **Create — finding-to-evidence matrix:** Link each major conclusion to the relevant ablation, metric, and figure.
- **Create — balanced findings graphic:** Display positive findings, neutral findings, and negative trade-offs without combining incomparable metrics.

### 7.2 Retrieval Quality, Context Coverage, and Latency Trade-offs

- **Create — three-axis trade-off figure:** Relate retrieval quality, evidence coverage, and latency for the main configurations.
- **Table — engineering decision matrix:** Compare the current candidates for quality-oriented, latency-oriented, and graph-aware use cases.

### 7.3 Implications for Legal RAG Design

- **Create — design-principles figure:** Summarize the practical lessons about metadata, graph expansion, reranking, citations, and abstention.
- **Table — implication-to-action mapping:** State the observed result and the corresponding implementation recommendation.

### 7.4 Dataset and Coverage Limitations

- **Create — coverage boundary map:** Show corpus coverage, external references, missing text, and unrepresented legal sources.
- **Table — limitation impact:** Map each dataset limitation to affected components and evaluation claims.

### 7.5 Knowledge Graph and Validity Limitations

- **Create — uncertainty diagram:** Mark unresolved relationship direction, validity annotations, external stubs, and verification gates.
- **Create — validity timeline example:** Show how a document can change status over time and where the current overlay logic is applied.

### 7.6 Retrieval and Generation Limitations

- **Create — error taxonomy:** Group failures into retrieval miss, ranking error, graph displacement, context truncation, citation failure, and generation error.
- **Table — limitation-to-mitigation plan:** Include the current limitation, its consequence, and a future improvement.

### 7.7 Evaluation Limitations

- **Table — claim validity matrix:** Distinguish what the current metrics demonstrate from what requires human legal assessment.
- **Create — evaluation boundary figure:** Separate lexical overlap, structural diagnostics, operational metrics, and semantic legal correctness.

### 7.8 Ethical Considerations and Safe Use

- **Create — human-verification workflow:** Show generated answer, source citation, validity check, expert review, and user decision.
- **Create — safe-use warning panel:** Explain that the system supports evidence discovery and does not replace qualified legal judgment.
- **Table — risk and mitigation:** Cover outdated law, incomplete corpus coverage, hallucination, privacy, and over-trust.

## 8. Conclusion and Future Work

### 8.1 Summary of the Implemented System

- **Create — one-page system summary:** Combine corpus, graph, retrieval, reranking, generation, and evaluation into one compact figure.

### 8.2 Main Contributions

- **Create — contribution checklist:** Mark each implemented contribution and link it to the corresponding chapter and artifact.

### 8.3 Lessons Learned

- **Create — lessons diagram:** Summarize the practical lessons from data quality, graph expansion, reranking, prompt design, and evaluation.

### 8.4 Recommended System Configuration

- **Create — recommended pipeline:** Highlight the currently preferred retrieval, reranking, context, and generation path.
- **Table — recommendation basis:** Include the ablation evidence supporting each selected component.

### 8.5 Future Improvements

- **Create — roadmap:** Organize future work into data validation, seed-preserving graph expansion, human evaluation, temporal reasoning, efficiency, and deployment.
- **Create — priority-impact matrix:** Rank future work by expected benefit and implementation effort.

### 8.6 Final Conclusion

- **Create — closing figure:** Show the transformation from raw legal data to traceable evidence and a grounded answer.

## References

- No additional visual is required.
- Ensure every figure adapted from prior work has a citation in its caption.

## Appendices

### A. Dataset and JSONL Schemas

- **Create — schema diagrams:** Show required fields and relationships for documents, provisions, chunks, edges, and provenance records.
- **Create — annotated JSONL examples:** Use one compact record per artifact type.

### B. Example Documents, Provisions, Chunks, and Edges

- **Create — annotated examples:** Highlight identifiers, parent-child links, text fields, citation anchors, and quality flags.

### C. Graph Relationship Vocabulary

- **Table — complete edge dictionary:** Include edge name, source node, target node, direction, meaning, and verification status.
- **Create — relationship legend:** Use the same colors and arrow styles as the main graph figures.

### D. Retrieval and Reranker Configurations

- **Table — full configuration reference:** Include model names, dimensions, index settings, candidate budgets, reranker settings, and runtime parameters.
- **Create — configuration comparison card:** Provide a compact visual for each major ablation family.

### E. Prompt and Output Formats

- **Create — prompt template diagram:** Annotate instructions, question, context, output rules, and citations.
- **Create — output examples:** Include boolean, extractive, abstractive, and unanswerable formats.

### F. Run Manifests and Additional Results

- **Table — run manifest examples:** Show configuration identity, corpus version, question count, completion status, and artifact paths.
- **Existing assets:** Include supplementary ablation plots, confidence-interval plots, subgroup tables, and latency charts that are too detailed for the main body.

## Recommended Visual Inventory

### Reuse from the Repository

- `docs/slide/imgs/system_architecture.png`
- `docs/slide/imgs/Data_pipeline.png`
- `docs/slide/imgs/graph_pipeline.png`
- `docs/slide/imgs/retrieve_pipeline.png`
- `docs/slide/imgs/eval_pipeline.png`
- `docs/slide/imgs/document_type.png`
- `docs/slide/imgs/category.png`
- `docs/slide/imgs/answer_type.png`
- `docs/slide/imgs/evidence.png`
- `docs/slide/imgs/nuance.png`
- `docs/slide/imgs/provision.png`
- `docs/slide/imgs/Chunk.png`
- `docs/slide/imgs/length.png`
- `docs/slide/imgs/node_type_distribution.png`
- `docs/slide/imgs/edges_dashboard.png`
- `docs/slide/imgs/edge_quarantine.png`
- Existing embedding, reranker, and generator-ablation plots under `ablation_study/` and `ablation_work/`.

### Highest-Priority Figures to Create

1. Legal QA motivation and failure-mode figure.
2. Raw data to final artifact pipeline with labeled layers.
3. Document → provision → chunk → provenance schema.
4. Offline/online L_RAG architecture with clear data flows.
5. Knowledge graph schema and worked traversal example.
6. Dense/BM25/RRF/reranking query flow.
7. Prompt, evidence, citation, and abstention flow.
8. One complete end-to-end running example.
9. Ablation configuration matrix.
10. Standardized qualitative case-study template.
11. Quality, evidence coverage, and latency trade-off chart.
12. Human-verification and safe-use workflow.

### Visual Style Rules

- Use one consistent color for data, another for graph operations, another for retrieval, and another for generation.
- Use the same identifiers—`document_id`, `provision_id`, and `chunk_id`—in diagrams and examples.
- Put the main architecture and main data pipeline in the body; move full schemas and large audit tables to the appendices.
- Use captions that state what the figure demonstrates, which data or configuration it uses, and why it matters.
- Prefer one informative figure over several decorative screenshots.
- Do not include private credentials, raw API keys, or hidden chain-of-thought content in screenshots or appendices.
