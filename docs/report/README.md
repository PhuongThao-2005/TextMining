# L_RAG report sources

ablation_report.tex is the canonical ACL-style manuscript entry point for the
report. Its section order follows report_structure.md: Sections 1--8 and
Appendices A--F use the prescribed headings. The current tree combines the
substantive system, dataset, protocol, and discussion prose from the earlier
report with the detailed, inline-linked five-analysis ablation report in
Section 6. The five analyses are grouped into four run families because the
dense, hybrid, and graph comparisons share one retrieval/graph execution
family. The legacy Sections 9 and 10 remain as compatibility files but are not
included by the canonical entry point.

The ablation branch keeps compact manifests, aggregate metrics, derived
reports, analysis code, and the compiled manuscript. Raw per-query outputs,
retrieval caches, and the pending annotation scaffold remain local evaluation
artifacts and are excluded from the lean commit.

The existing main.tex remains the separate HCMUS course-report entry point and
is not changed by this restructuring. The two documents should therefore not
be treated as interchangeable.

## Build

Place the official acl.sty and acl_natbib.bst files from
[acl-org/acl-style-files](https://github.com/acl-org/acl-style-files) on the
TeX search path or next to ablation_report.tex, then run from this directory:

    latexmk -xelatex -interaction=nonstopmode -halt-on-error ablation_report.tex

Use the review option instead of final in ablation_report.tex for the
anonymous, line-numbered ACL review layout.

## Section map

| File | Role |
| --- | --- |
| sections/1_introduction.tex | Combined Introduction prose and scope |
| sections/2_related_work.tex | Combined Background and Related Work prose |
| sections/3_system_overview.tex | Legal Dataset and Benchmark Construction |
| sections/4_dataset_and_corpus.tex | L_RAG System Design and Methodology |
| sections/5_experimental_setup.tex | Controls, metrics, configurations, and reproducibility |
| sections/6_ablation_study.tex | Completed five-analysis evidence in the planned 6.1--6.10 layout, with retrieval/graph runs grouped as one family |
| sections/7_results.tex | Discussion, limitations, and ethical considerations |
| sections/8_discussion.tex | Conclusion and future work |
| sections/9_limitations.tex | Legacy guidance file; not included |
| sections/10_conclusion.tex | Legacy guidance file; not included |
| appendix.tex | Substantive Appendices A--F: schemas, examples, configs, prompts, and artifacts |
