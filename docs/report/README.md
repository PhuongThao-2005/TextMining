# L_RAG report sources

`ablation_report.tex` is the ACL-structured manuscript entry point for the
ablation branch. It follows the official *ACL source layout: 11pt article,
ACL style, two-column body, no title page or table of contents, numbered
main sections, unnumbered limitations/ethics/acknowledgments, BibTeX
references, and lettered appendices.

The manuscript is populated with four completed deterministic ablations
(embedding text, dense/hybrid plus graph retrieval, multi-reranker choice, and
the generator-reasoning prompt comparison). Human-validated legal-answer
metrics remain unavailable and are clearly separated from the deterministic
results.

The ablation branch keeps compact manifests, aggregate metrics, derived
reports, analysis code, and the compiled manuscript. Raw per-query outputs,
retrieval caches, and the pending annotation scaffold remain local evaluation
artifacts and are excluded from the lean commit.

The existing `main.tex` remains the HCMUS course-report entry point. The two
documents serve different purposes and share the first four modular section
files where their content overlaps.

## Build

Place the official `acl.sty` and `acl_natbib.bst` files from
[`acl-org/acl-style-files`](https://github.com/acl-org/acl-style-files) on the
TeX search path or next to `ablation_report.tex`, then run from this directory:

```bash
latexmk -xelatex -interaction=nonstopmode -halt-on-error ablation_report.tex
```

Use `[review]` instead of `[final]` in `ablation_report.tex` for the
anonymous, line-numbered ACL review layout.

## Section map

| File | Role |
| --- | --- |
| `sections/1_introduction.tex` | Motivation, problem, objectives, contributions |
| `sections/2_related_work.tex` | RAG, Legal IR, hybrid search, GraphRAG |
| `sections/3_system_overview.tex` | L_RAG architecture and components |
| `sections/4_dataset_and_corpus.tex` | Legal corpus, graph schema, QA benchmark |
| `sections/5_experimental_setup.tex` | Questions, metrics, protocol, configurations |
| `sections/6_ablation_study.tex` | Controlled comparisons and completed runs |
| `sections/7_results.tex` | Results ledger and breakdowns |
| `sections/8_discussion.tex` | Interpretation and threats to validity |
| `sections/9_limitations.tex` | Limitations and ethical considerations |
| `sections/10_conclusion.tex` | Conclusion and future work |
| `appendix.tex` | Schema, additional results, and manifests |
