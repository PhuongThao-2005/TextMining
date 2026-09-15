# L_RAG report sources

ablation_report.tex is the canonical ACL-style manuscript entry point for the
report. Its section order now follows report_structure.md: Sections 1--8 and
Appendices A--F use the prescribed headings. Sections 1--5, 7, 8, and the
appendices intentionally contain short guidance placeholders; Section 6
retains the completed deterministic ablation evidence.

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
| sections/1_introduction.tex | Introduction structure and guidance |
| sections/2_related_work.tex | Background and Related Work structure |
| sections/3_system_overview.tex | Legal Dataset and Benchmark Construction structure |
| sections/4_dataset_and_corpus.tex | L_RAG System Design and Methodology structure |
| sections/5_experimental_setup.tex | Implementation and Experimental Setup structure |
| sections/6_ablation_study.tex | Completed ablation evidence in the planned 6.1--6.10 layout |
| sections/7_results.tex | Discussion, limitations, and ethical considerations guidance |
| sections/8_discussion.tex | Conclusion and future work guidance |
| sections/9_limitations.tex | Legacy guidance file; not included |
| sections/10_conclusion.tex | Legacy guidance file; not included |
| appendix.tex | Appendices A--F guidance skeleton |
