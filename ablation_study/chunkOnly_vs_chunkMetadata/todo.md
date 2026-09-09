# To-do: Chunk-only vs. Chunk + Metadata

## Setup

- [ ] Create `results/` for derived outputs only.
- [ ] Record the chunk-only and chunk-metadata run IDs in every derived table,
  figure, and report.
- [ ] Confirm both `e2e_predictions.jsonl` files contain the same 500 `qa_id`s.
- [ ] Restrict retrieval statistics to the 400 answerable questions.

## Compute retrieval statistics

- [ ] Read ranked `retrieved_context` and gold chunk, provision, and document
  IDs from each paired prediction record.
- [ ] Compute Hit, Recall, and MRR at K = 5 and K = 10.
- [ ] Compute Provision Success@5 / @10.
- [ ] Compute Document Success@5 / @10.
- [ ] Compute first correct chunk, provision, and document rank.
- [ ] Compute metadata win / tie / loss counts for chunk and document success
  at K = 5 and K = 10.
- [ ] Compute paired bootstrap 95% confidence intervals for all Table 1 deltas.

## Prepare reporting outputs

- [ ] Fill the main retrieval table from `plan.md`.
- [ ] Fill the compact downstream/operational table using the existing metrics
  and latency artifacts.
- [ ] Create a Success@K curve for K = 1 through 10, highlighting K = 5 and
  K = 10.
- [ ] Create the paired win / tie / loss chart.
- [ ] Select 3--5 paired examples only if they explain the dominant result.

## Write insights

- [ ] State whether metadata changes top-5 and top-10 evidence coverage.
- [ ] State whether changes are at chunk, provision, or document level.
- [ ] Explain the leading source-disambiguation pattern, if one is observed.
- [ ] Describe downstream answer, citation, and latency changes as secondary
  diagnostics.
- [ ] Report uncertainty and small-sample subgroup limitations.
- [ ] Verify that conclusions concern this legal benchmark only and do not
  assume the reference paper's results transfer.

## Final checks

- [ ] Verify no source run artifact was edited.
- [ ] Verify tables label K = 5 and K = 10 consistently.
- [ ] Verify all deltas are `metadata - chunk-only`.
- [ ] Link or list the frozen source artifact paths in the final subsection.
