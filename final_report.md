# L_RAG System Report — Table of Contents

1. [Introduction](#1-introduction)
   1.1 [Project Background](#11-project-background)  
   1.2 [Problem Statement](#12-problem-statement)  
   1.3 [Project Objectives](#13-project-objectives)  
   1.4 [Scope of the System](#14-scope-of-the-system)  
   1.5 [Report Structure](#15-report-structure)  

2. [System Overview](#2-system-overview)
   2.1 [Overview of Legal Retrieval-Augmented Generation](#21-overview-of-legal-retrieval-augmented-generation)  
   2.2 [Motivation for L_RAG](#22-motivation-for-l-rag)  
   2.3 [Main System Components](#23-main-system-components)  
   2.4 [End-to-End Workflow](#24-end-to-end-workflow)  
   2.5 [Expected Use Cases](#25-expected-use-cases)  

3. [Dataset Design and Preparation](#3-dataset-design-and-preparation)
   3.1 [Raw Dataset Description](#31-raw-dataset-description)  
   3.2 [Metadata, Relationship, and Content Sources](#32-metadata-relationship-and-content-sources)  
   3.3 [Dataset Cleaning Strategy](#33-dataset-cleaning-strategy)  
   3.4 [Dataset Layers and Artifacts](#34-dataset-layers-and-artifacts)  
   3.5 [Document Normalization](#35-document-normalization)  
   3.6 [Relationship Normalization](#36-relationship-normalization)  
   3.7 [External Stub Handling](#37-external-stub-handling)  
   3.8 [Quarantine and Error Tracking](#38-quarantine-and-error-tracking)  
   3.9 [Dataset Reconciliation](#39-dataset-reconciliation)  

4. [Legal Text Structuring](#4-legal-text-structuring)
   4.1 [Role of Legal Text in the System](#41-role-of-legal-text-in-the-system)  
   4.2 [HTML Content Extraction](#42-html-content-extraction)  
   4.3 [Provision-Level Structuring](#43-provision-level-structuring)  
   4.4 [Chunk-Level Structuring](#44-chunk-level-structuring)  
   4.5 [Citation Unit and Embedding Unit Design](#45-citation-unit-and-embedding-unit-design)  
   4.6 [Text Provenance Tracking](#46-text-provenance-tracking)  
   4.7 [Handling Missing or Incomplete Text](#47-handling-missing-or-incomplete-text)  

5. [Knowledge Graph Design](#5-knowledge-graph-design)
   5.1 [Purpose of the Legal Knowledge Graph](#51-purpose-of-the-legal-knowledge-graph)  
   5.2 [Graph Nodes and Entity Types](#52-graph-nodes-and-entity-types)  
   5.3 [Graph Edges and Relationship Types](#53-graph-edges-and-relationship-types)  
   5.4 [Legal Validity Relationships](#54-legal-validity-relationships)  
   5.5 [Authority and Document Hierarchy](#55-authority-and-document-hierarchy)  
   5.6 [Direction Verification for Legal Edges](#56-direction-verification-for-legal-edges)  
   5.7 [GraphRAG Integration](#57-graphrag-integration)  

6. [Vector Retrieval Module](#6-vector-retrieval-module)
   6.1 [Purpose of Vector Retrieval](#61-purpose-of-vector-retrieval)  
   6.2 [Chunk Text Construction](#62-chunk-text-construction)  
   6.3 [Embedding Model and Representation](#63-embedding-model-and-representation)  
   6.4 [Vector Index Building](#64-vector-index-building)  
   6.5 [Metadata Filtering](#65-metadata-filtering)  
   6.6 [Retrieval Pipeline](#66-retrieval-pipeline)  
   6.7 [Ranking and Scoring Strategy](#67-ranking-and-scoring-strategy)  

7. [Hybrid Retrieval Architecture](#7-hybrid-retrieval-architecture)
   7.1 [Combining Vector Retrieval and Graph Retrieval](#71-combining-vector-retrieval-and-graph-retrieval)  
   7.2 [Query Processing Flow](#72-query-processing-flow)  
   7.3 [Graph-Based Filtering and Expansion](#73-graph-based-filtering-and-expansion)  
   7.4 [Retrieval-Time Validity Reasoning](#74-retrieval-time-validity-reasoning)  
   7.5 [Authority-Aware Retrieval](#75-authority-aware-retrieval)  
   7.6 [Result Aggregation](#76-result-aggregation)  
   7.7 [Citation and Evidence Selection](#77-citation-and-evidence-selection)  

8. [Answer Generation Module](#8-answer-generation-module)
   8.1 [Role of the Generation Component](#81-role-of-the-generation-component)  
   8.2 [Context Construction](#82-context-construction)  
   8.3 [Prompting Strategy](#83-prompting-strategy)  
   8.4 [Citation-Grounded Answer Generation](#84-citation-grounded-answer-generation)  
   8.5 [Handling Uncertain or Missing Evidence](#85-handling-uncertain-or-missing-evidence)  
   8.6 [Output Format](#86-output-format)  

9. [System Implementation](#9-system-implementation)
   9.1 [Project Directory Structure](#91-project-directory-structure)  
   9.2 [Dataset Processing Scripts](#92-dataset-processing-scripts)  
   9.3 [Retrieval Source Code Organization](#93-retrieval-source-code-organization)  
   9.4 [Configuration Management](#94-configuration-management)  
   9.5 [Index Construction Workflow](#95-index-construction-workflow)  
   9.6 [Data Input and Output Files](#96-data-input-and-output-files)  
   9.7 [Runtime Dependencies](#97-runtime-dependencies)  

10. [Experiments and Evaluation](#10-experiments-and-evaluation)
    10.1 [Evaluation Objectives](#101-evaluation-objectives)  
    10.2 [Test Query Design](#102-test-query-design)  
    10.3 [Retrieval Evaluation Metrics](#103-retrieval-evaluation-metrics)  
    10.4 [Generation Quality Metrics](#104-generation-quality-metrics)  
    10.5 [Citation Accuracy Evaluation](#105-citation-accuracy-evaluation)  
    10.6 [Legal Validity Evaluation](#106-legal-validity-evaluation)  
    10.7 [Experimental Results](#107-experimental-results)  
    10.8 [Error Analysis](#108-error-analysis)  

11. [System Limitations](#11-system-limitations)
    11.1 [Dataset Coverage Limitations](#111-dataset-coverage-limitations)  
    11.2 [Missing Text and Incomplete Content](#112-missing-text-and-incomplete-content)  
    11.3 [Relationship Direction Ambiguity](#113-relationship-direction-ambiguity)  
    11.4 [Retrieval Limitations](#114-retrieval-limitations)  
    11.5 [Generation Limitations](#115-generation-limitations)  
    11.6 [Legal Reliability Concerns](#116-legal-reliability-concerns)  

12. [Future Work](#12-future-work)
    12.1 [Improved Legal Text Parsing](#121-improved-legal-text-parsing)  
    12.2 [Better Relationship Verification](#122-better-relationship-verification)  
    12.3 [Temporal Legal Reasoning](#123-temporal-legal-reasoning)  
    12.4 [Enhanced Knowledge Graph Construction](#124-enhanced-knowledge-graph-construction)  
    12.5 [User Interface Development](#125-user-interface-development)  
    12.6 [Deployment and Monitoring](#126-deployment-and-monitoring)  

13. [Conclusion](#13-conclusion)
    13.1 [Summary of the System](#131-summary-of-the-system)  
    13.2 [Main Contributions](#132-main-contributions)  
    13.3 [Lessons Learned](#133-lessons-learned)  
    13.4 [Final Remarks](#134-final-remarks)  

14. [References](#14-references)

15. [Appendices](#15-appendices)
    15.1 [Dataset Schema](#151-dataset-schema)
    15.2 [Relationship Mapping Table](#152-relationship-mapping-table)
    15.3 [Example Documents and Chunks](#153-example-documents-and-chunks)
    15.4 [Example Retrieval Results](#154-example-retrieval-results)
    15.5 [Configuration Details](#155-configuration-details)
    15.6 [Additional Evaluation Results](#156-additional-evaluation-results)

---

# 1. Introduction

## 1.1 Project Background

Legal information retrieval is a critical task in domains where decisions depend on accurate interpretation of statutes, regulations, decrees, circulars, and other legal documents. Unlike general-purpose document search, legal search requires attention to document hierarchy, citation relationships, amendment history, validity status, and the precise wording of provisions. A relevant answer is therefore not only a semantically similar text segment, but also one that is legally grounded, traceable to authoritative sources, and consistent with the current legal context.

Recent advances in large language models have improved the ability to generate fluent natural-language answers from retrieved evidence. However, language models alone are not sufficient for legal question answering because they may hallucinate, omit citations, or fail to distinguish between valid, expired, amended, and superseded legal provisions. Retrieval-Augmented Generation (RAG) addresses part of this problem by combining document retrieval with answer generation, but a conventional vector-only RAG system still has limitations when applied to legal corpora. In particular, it may overlook explicit legal relationships, temporal validity, document authority, and cross-document dependencies.

The L_RAG project is designed as a legal Retrieval-Augmented Generation system that combines structured dataset preparation, legal text structuring, vector retrieval, and knowledge graph reasoning. The system aims to provide a foundation for retrieving relevant legal evidence and generating answers that are supported by citations. By integrating both semantic retrieval and graph-based legal relationships, L_RAG is intended to improve reliability, explainability, and traceability in legal question answering.

## 1.2 Problem Statement

Legal documents are often long, highly structured, and interconnected. A single user question may require information from multiple provisions or documents, and the correct answer may depend on whether a provision is still effective, has been amended, or is related to another legal instrument. Raw legal datasets also commonly contain inconsistencies such as missing metadata, incomplete text, duplicated records, ambiguous relationship directions, and references to documents outside the available corpus.

A simple keyword search system may fail to retrieve semantically relevant passages when the user's wording differs from the terminology used in legal documents. Conversely, a purely vector-based semantic retrieval system may retrieve text that appears relevant but is outdated, lower in authority, or disconnected from important legal relationships. These issues reduce the trustworthiness of generated answers and make it difficult for users to verify the evidence behind a response.

The main problem addressed by this project is how to build a legal retrieval and generation pipeline that can support evidence-based answers while preserving important legal structure. The system must process legal documents into reliable retrieval units, represent document-level and provision-level relationships, retrieve relevant evidence from both semantic and structural perspectives, and generate responses that remain grounded in the retrieved legal sources.

## 1.3 Project Objectives

The primary objective of L_RAG is to design and implement a legal RAG pipeline that improves the retrieval and use of legal evidence for question answering. To achieve this objective, the project focuses on the following goals:

- Construct a cleaned and normalized legal dataset from raw document metadata, relationship data, and textual content.
- Transform legal documents into structured units such as provisions, chunks, citation units, and embedding units suitable for retrieval and citation.
- Build a legal knowledge graph that represents documents, entities, and relationships such as amendment, replacement, validity, and authority-related links.
- Implement a vector retrieval module that embeds structured legal chunks and retrieves semantically relevant evidence for user queries.
- Design a hybrid retrieval architecture that combines vector similarity with graph-based filtering, expansion, and legal validity reasoning.
- Support citation-grounded answer generation by constructing prompts from selected evidence and requiring answers to reference their sources.
- Document the implementation workflow, dataset artifacts, limitations, and future improvements of the system.

These objectives emphasize both technical retrieval performance and legal reliability. The system is not intended to replace professional legal judgment, but to provide a structured computational approach for finding and presenting relevant legal evidence.

## 1.4 Scope of the System

The scope of L_RAG covers the backend pipeline required to prepare data, build retrieval indexes, model legal relationships, and support evidence-grounded answer generation. The project includes dataset cleaning, document normalization, text extraction, provision and chunk construction, vector index building, knowledge graph design, hybrid retrieval, and report-level evaluation planning.

The system focuses on legal documents available within the project dataset and the relationships that can be extracted or normalized from that dataset. It is designed to handle practical issues such as missing text, external document references, inconsistent identifiers, and relationship ambiguity. The retrieval component is intended to work with structured legal chunks and associated metadata so that results can be filtered, ranked, cited, and interpreted in relation to the original documents.

The project does not claim to provide complete legal coverage for all jurisdictions or legal topics. It also does not guarantee that generated answers are legally authoritative. Instead, the system should be understood as a research and engineering prototype for legal information retrieval and legal RAG. Its outputs must be evaluated against source documents and, in real-world use, reviewed by qualified legal experts.

## 1.5 Report Structure

This report is organized into fifteen main sections. Section 1 introduces the project background, problem statement, objectives, scope, and report structure. Section 2 provides a system overview and explains the motivation, core components, workflow, and expected use cases of L_RAG. Section 3 describes the dataset design and preparation process, including raw data sources, cleaning strategy, normalized artifacts, and error handling.

Section 4 explains how legal text is extracted and structured into provisions, chunks, citation units, and embedding units. Section 5 presents the design of the legal knowledge graph, including node types, edge types, validity relationships, authority hierarchy, and GraphRAG integration. Section 6 describes the vector retrieval module, including chunk text construction, embeddings, indexing, filtering, and scoring. Section 7 explains the hybrid retrieval architecture that combines vector retrieval with graph-based reasoning.

Section 8 discusses the answer generation module, including context construction, prompting, citation grounding, and handling of uncertain evidence. Section 9 summarizes the implementation structure, scripts, configuration, dependencies, and input-output files. Section 10 outlines the experimental and evaluation design. Section 11 identifies system limitations, while Section 12 proposes future improvements. Section 13 concludes the report, and Sections 14 and 15 provide references and appendices for supporting materials.

---

# 2. System Overview

## 2.1 Overview of Legal Retrieval-Augmented Generation

Retrieval-Augmented Generation is an architecture that improves language model responses by supplying external evidence during answer generation. Instead of relying only on the internal knowledge of a model, a RAG system first retrieves relevant documents or text fragments from a knowledge source and then uses those retrieved materials as context for generating an answer. This approach is especially useful in legal domains, where answers must be based on specific documents, provisions, and citations rather than general assumptions.

Legal Retrieval-Augmented Generation extends the general RAG approach by considering the structure and constraints of legal information. Legal documents are not independent plain-text records. They are connected through amendment, replacement, reference, authority, and validity relationships. A legal RAG system must therefore retrieve not only semantically similar text, but also legally appropriate evidence. For example, when answering a question about a regulation, the system should consider whether the retrieved provision is currently valid, whether it has been amended, and whether related legal documents provide additional context.

The L_RAG system follows this principle by combining vector-based retrieval with graph-based legal reasoning. Vector retrieval is used to identify text chunks that are semantically close to the user query, while the knowledge graph is used to represent explicit relationships between legal documents and support structural filtering or expansion. The final generation stage uses retrieved evidence to produce an answer with citations, making the response more transparent and easier to verify.

## 2.2 Motivation for L_RAG

The motivation for L_RAG comes from the limitations of traditional legal search and conventional RAG systems. Keyword-based legal search can be effective when the user knows the exact legal terminology, document title, or article number. However, users often ask questions in natural language, using words that differ from those used in official legal documents. This creates a gap between user intent and document wording.

Vector retrieval addresses this issue by retrieving passages based on semantic similarity. Nevertheless, semantic similarity alone is not enough for legal question answering. A retrieved passage may be topically relevant but legally outdated, incomplete, or less authoritative than another document. In addition, many legal answers depend on relationships that are not always visible from local text similarity, such as a document amending another document or a newer document replacing an older one.

L_RAG is motivated by the need to bridge these two perspectives. It aims to preserve the flexibility of semantic search while adding the reliability of structured legal relationships. By integrating cleaned metadata, normalized legal text, a vector index, and a legal knowledge graph, the system is designed to retrieve evidence that is both semantically relevant and legally meaningful.

## 2.3 Main System Components

The L_RAG system is organized into several main components, each responsible for a specific part of the legal question-answering pipeline.

1. **Dataset preparation component**: This component cleans and normalizes raw legal data, including document metadata, relationship files, and source text. It resolves inconsistent identifiers, removes duplicated or invalid records, handles missing fields, and separates problematic entries for later inspection.

2. **Legal text structuring component**: This component extracts usable text from legal document sources and transforms the content into structured units. These units may include provisions, chunks, citation units, and embedding units. The purpose is to ensure that the retrieval system works with meaningful and traceable legal passages rather than arbitrary text fragments.

3. **Knowledge graph component**: This component represents legal documents and their relationships as a graph. Nodes may represent documents, provisions, agencies, document types, or other legal entities. Edges may represent relationships such as amendment, replacement, reference, validity, or authority. This graph supports relationship-aware retrieval and legal context expansion.

4. **Vector retrieval component**: This component converts structured legal chunks into embedding vectors and stores them in a vector index. At query time, the user question is embedded and compared with indexed chunks to retrieve semantically similar evidence.

5. **Hybrid retrieval component**: This component combines vector retrieval results with graph-based operations. It can filter irrelevant or invalid results, expand evidence using connected documents, consider authority and validity relationships, and aggregate the final set of candidate evidence.

6. **Answer generation component**: This component constructs a context from selected evidence and sends it to a language model for answer generation. The generated answer should be grounded in the retrieved legal passages and include citations to the source documents or provisions.

7. **Evaluation and analysis component**: This component supports the assessment of retrieval quality, citation accuracy, generation quality, and legal validity handling. It helps identify system weaknesses and guides future improvements.

**Suggested figure location — System component architecture:**



## 2.4 End-to-End Workflow

The end-to-end workflow of L_RAG begins with raw legal data and ends with a citation-grounded answer to a user query. The workflow can be divided into two major phases: the offline indexing phase and the online question-answering phase.

In the offline phase, raw metadata, relationship data, and legal text are collected and normalized. The dataset preparation scripts clean the input files, reconcile document identifiers, validate relationships, and generate standardized artifacts. Legal texts are then extracted and segmented into structured provisions and chunks. Each chunk is enriched with metadata such as document identifier, title, document type, issuing agency, effective date, validity information, and citation references. These chunks are embedded and stored in a vector index. In parallel, document metadata and normalized relationships are used to build the legal knowledge graph.

In the online phase, a user submits a legal question. The system analyzes the query and retrieves semantically relevant chunks from the vector index. The initial results can then be refined using metadata filters and graph-based reasoning. For example, the graph may help identify related amended documents, newer replacing documents, or authoritative sources connected to the retrieved evidence. The hybrid retrieval module ranks and aggregates the final evidence set. The answer generation module uses this evidence to produce a natural-language answer with citations.

This workflow ensures that answer generation is not performed directly from the model's internal knowledge. Instead, the answer is generated from retrieved legal evidence that can be traced back to structured documents and graph relationships.

**Suggested figure location — End-to-end workflow pipeline:**



**Suggested flow chart location — Offline indexing phase:**



**Suggested flow chart location — Online query and answer generation phase:**



## 2.5 Expected Use Cases

The L_RAG system is expected to support several legal information access scenarios. The first use case is natural-language legal question answering. A user can ask a question in ordinary language, and the system retrieves relevant legal provisions before generating a citation-supported response. This is useful when users do not know the exact document name, article number, or legal terminology.

The second use case is legal document exploration. By combining vector search and knowledge graph traversal, the system can help users discover documents related to a given legal topic, including documents that amend, replace, refer to, or depend on one another. This supports a more connected view of the legal corpus than isolated keyword search results.

The third use case is validity-aware retrieval. In legal research, it is important to know whether a document or provision is currently effective or has been modified by later documents. L_RAG is designed to incorporate validity relationships into retrieval so that outdated or superseded evidence can be identified and handled more carefully.

The fourth use case is citation-grounded summarization. When multiple relevant provisions are retrieved, the system can generate a concise summary while preserving references to the original sources. This helps users quickly understand a legal issue without losing the ability to verify the supporting evidence.

The fifth use case is dataset and legal knowledge analysis. Because the project includes cleaned dataset artifacts, structured text units, and a knowledge graph, it can also be used to inspect corpus quality, relationship coverage, missing text, ambiguous links, and other data issues that affect legal information retrieval.

Overall, L_RAG is intended as a research prototype and engineering foundation for legal RAG. Its expected value lies in improving the traceability, structure, and reliability of legal retrieval and generation, while still requiring human verification for professional or official legal use.
