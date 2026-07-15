# Phase 0 Research: EDA Notebook for Dataset v2

## R1: How to stream `chunks.jsonl` (2.64 GB) / `provisions.jsonl` (1.78 GB) without loading them whole

**Decision**: Line-by-line streaming with a single-pass accumulator pattern (running `Counter`s / sums / reservoir samples), mirroring [`src/data/pipeline/io_utils.read_jsonl()`](../../src/data/pipeline/io_utils.py:16), which the dataset-build pipeline already uses for the ~4 GB `content.jsonl`.

**Rationale**: The project already has a working, in-repo pattern for this exact problem (`read_jsonl` yields one parsed dict at a time from an open file handle). Reusing it keeps behavior consistent with how the dataset itself was built, avoids introducing `pandas.read_json(..., chunksize=...)` (which still buffers per-chunk DataFrames and adds a dependency behavior difference) for a case where plain-Python counters are simpler and cheaper.

**Alternatives considered**:
- `pandas.read_json(path, lines=True, chunksize=N)` — rejected as primary approach because it still materializes N-row DataFrames repeatedly and pulls in pandas type-inference overhead for a workload that's mostly counting/summing; kept as an option only for the sampled subset once it's small enough to fit in memory (e.g., the reservoir sample of chunk-text lengths).
- `dask`/`polars` streaming — rejected: not currently a project dependency, and the constitution / spec explicitly caution against adding heavyweight dependencies unless proven necessary (spec.md Assumptions).

## R2: Sampling method for record-level inspection (e.g., chunk-text length distribution)

**Decision**: Reservoir sampling (Algorithm R) with a fixed, configurable seed and sample size, applied in the same streaming pass used for full-corpus counts wherever possible (one pass computes both the exact count and the sample).

**Rationale**: Reservoir sampling gives a uniform random sample of a stream of unknown-in-advance length without a second pass or knowing total row count ahead of time, and is a standard, easily unit-testable algorithm (deterministic given a seed). FR-002 requires "explicit random or systematic sampling (with a configurable sample size and fixed seed)" — reservoir sampling satisfies this directly.

**Alternatives considered**:
- Systematic sampling (every Nth row) — simpler but biased if the file has any positional structure (e.g., grouped by document, which `chunks.jsonl` is, since chunks are emitted in document order); rejected as the default, but exposed as a documented option for FR-002's "or systematic" clause.
- Two-pass sampling (count first, then pick random line numbers, then re-read) — rejected: doubles I/O time over multi-GB files for no accuracy benefit over reservoir sampling.

## R3: Where to put reusable logic — notebook-only vs. extracted module

**Decision**: Extract streaming/sampling/reconciliation/preflight helpers into `src/eda/dataset_v2.py`, keep the notebook as thin orchestration (config + calls + display).

**Rationale**: Constitution principle V ("Modular, Testable, Reported Pipelines") requires modules to "expose clear contracts through schemas, typed data structures, tests." Notebook cells are not unit-testable in the project's existing `pytest` setup (`pyproject.toml`'s `pythonpath = ["src"]"` only discovers `src/`). Precedent: `001-faiss-retrieval-notebook`'s notebook itself stays thin and calls into the pre-existing `src/retrieval/` module rather than reimplementing retrieval logic (FR-002 of that spec). No equivalent EDA module exists yet, so this feature creates the minimal one.

**Alternatives considered**:
- Pure-notebook implementation with no extracted module — rejected: FR-002's streaming/sampling correctness and FR-008/FR-009's reconciliation/tally correctness are exactly the kind of logic that benefits from regression tests; a bug here (e.g., off-by-one in reservoir sampling, or double-counting quarantine reasons) would be easy to introduce silently and hard to catch by eye in notebook output alone.
- A full new package with schemas/dataclasses mirroring `src/data/pipeline/` — rejected as overscoped: this feature is read-only analysis, not a new pipeline stage; a handful of pure functions plus lightweight `TypedDict`/dataclass return types is sufficient and matches the "small, testable module" spirit without duplicating the dataset-build pipeline's structure.

## R4: Project-root / path resolution for "run from root or `notebooks/`" (FR-013)

**Decision**: Reuse the existing pattern already in [`notebooks/faiss_retrieval_ready.ipynb`](../../notebooks/faiss_retrieval_ready.ipynb:65-68): check `Path.cwd() / 'src'`; if absent, use `Path.cwd().parent`. Encapsulate this as `resolve_project_root()` in `src/eda/dataset_v2.py` so it's unit-testable (given a fake cwd) instead of duplicated inline notebook code.

**Rationale**: Consistency with the sibling notebook feature avoids two different root-resolution conventions in the same `notebooks/` directory. Making it a function (rather than inline cell code) allows a unit test to assert the fallback behavior without spawning a real notebook kernel.

**Alternatives considered**:
- `pyprojectroot`/`pyrootutils` style marker-file search — rejected: adds a dependency for a one-line problem already solved elsewhere in the repo.

## R5: Vietnamese label rendering in plots (Edge Case, FR-015)

**Decision**: Default to `matplotlib`'s default font but always pair every plot with the underlying table (DataFrame `.head()`/`display()` or printed table) so Vietnamese diacritics are never solely dependent on plot glyph rendering. Where a plot is produced, keep bar/line orientation such that long Vietnamese labels are horizontal (`barh`) rather than rotated/truncated on the x-axis.

**Rationale**: Spec edge cases explicitly require UTF-8-correct rendering "without requiring a specific non-default font" and a "fallback to a table view if plotting... is unreliable." Testing actual glyph rendering is out of scope for automated tests (visual/manual concern per `WCAG`-style guardrail on manual review), so the design choice is to make the table the source of truth and the plot a secondary, always-degradable view.

**Alternatives considered**:
- Bundling a Vietnamese-safe font (e.g., Noto Sans) and setting `matplotlib.rcParams['font.family']` — rejected: adds a font-file dependency/download step for a notebook that should run offline once data is present; current environment's default font (DejaVu Sans, shipped with matplotlib) already covers Vietnamese Latin Extended glyphs in practice, so this is unnecessary complexity for the stated constraint.

## R6: Handling `null`/`"MISSING"`/`"UNMAPPED"` in groupby/plot (Edge Case)

**Decision**: Normalize missing/unmapped values to an explicit sentinel category string (e.g., `"(missing)"`, `"(unmapped)"`) before any `groupby`/`value_counts`, via a small `coerce_category()` helper in `src/eda/dataset_v2.py`, rather than relying on pandas' default `NaN` handling (which silently excludes `NaN` from `value_counts()` unless `dropna=False` is passed everywhere).

**Rationale**: `pandas.Series.value_counts()` defaults to `dropna=True`, which would silently under-report exactly the missing-data cases the spec requires surfacing (Edge Cases: "MUST count and display these as an explicit category rather than dropping the rows silently"). A single coercion helper applied consistently avoids needing to remember `dropna=False` at every call site and gives one place to unit test.

**Alternatives considered**:
- Passing `dropna=False` everywhere inline — rejected: easy to forget at one of the ~10+ distribution call sites (FR-003, FR-004, FR-005, FR-011), reintroducing silent drops by omission.

## R7: Reconciliation cross-check design (FR-008, US2)

**Decision**: Recompute `len(documents_final) + len(documents_quarantine) == len(metadata_raw)` and the edges equivalent purely by streaming-counting each file (no join needed, just counts), then compare against the numbers parsed out of `data/v2/reconciliation_report.md`'s markdown table via a small regex-based parser, reporting PASS/FAIL plus the raw numbers from both sources.

**Rationale**: FR-008 requires recomputing "directly from the JSONL files... and report PASS/FAIL... alongside the numbers currently checked into the report." Since the identity is a row-count identity (not a content/field-level join), streaming line counts (`sum(1 for _ in read_jsonl(path))`) are sufficient and cheap even for `metadata.jsonl`/`relationships.jsonl` in `data/untracked_data/`.

**Alternatives considered**:
- Parsing `reconciliation_report.md` with a markdown table library — rejected: report format is small and stable (fixed table produced by [`src/data/pipeline/report.py`](../../src/data/pipeline/report.py)); a targeted regex avoids a new dependency for one file.

## R8: Multi-tag reason accounting (FR-009, Dataset_SPEC_v2 §9)

**Decision**: For each quarantine/quality row, iterate its `exclusion_reasons` (and `edge_quality_flags` for edges) list and increment a `Counter` per tag, while separately tracking `len(rows)` for the row-level denominator — i.e., two independent tallies (row count, tag count) computed in the same streaming pass, never conflated.

**Rationale**: Constitution principle III and Dataset_SPEC_v2 §9 both state "reasons are tags, rows are authoritative" — a row with 3 reasons must count once toward total quarantined rows but contribute to 3 tag counters. This is a well-understood pattern (`Counter.update(list_of_tags)` for tags, separate `len()`/increment for rows) and is directly unit-testable with a tiny synthetic fixture (e.g., 3 rows, one with 2 tags, assert row_count=3 and tag_count sums correctly with no double counting of rows).

**Alternatives considered**:
- Exploding rows via `pandas.explode()` on the loaded quarantine DataFrame — viable since quarantine files are small (2.12 MB / 6.61 MB, per file size check), but a plain-Python `Counter` pass is simpler, avoids an intermediate DataFrame explosion, and reuses the same streaming helper used for the large files, keeping one code path instead of two.
