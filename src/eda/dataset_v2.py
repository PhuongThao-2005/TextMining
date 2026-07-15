"""Streaming EDA helpers for Dataset v2 JSONL artifacts.

Pure functions used by ``notebooks/eda_v2_dataset.ipynb``. Designed for
line-by-line aggregation over multi-GB files (chunks/provisions) without
loading them fully into memory. See specs/002-eda-v2-dataset-notebook/.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Result dataclasses (data-model.md §2)
# ---------------------------------------------------------------------------


@dataclass
class PreflightResult:
    """Presence report for expected v2 / untracked artifacts."""

    present: list[Path]
    missing: list[Path]
    by_artifact: dict[str, bool]


@dataclass
class StreamCountResult:
    """Full-file row count plus per-field category counters."""

    total_rows: int
    malformed_lines: int
    field_counters: dict[str, Counter[str]] = field(default_factory=dict)


@dataclass
class ReservoirSample:
    """Uniform reservoir sample over a JSONL stream."""

    seed: int
    sample_size: int
    rows_seen: int
    sample: list[dict]


@dataclass
class ReconciliationCheck:
    """raw == final + quarantine identity vs reconciliation_report.md."""

    label: str
    raw_count: int
    final_count: int
    quarantine_count: int
    identity_holds: bool
    report_raw: int | None
    report_final: int | None
    report_quarantine: int | None
    matches_report: bool


@dataclass
class TagTally:
    """Multi-tag reason accounting: rows authoritative, tags independent."""

    row_count: int
    tag_counts: Counter[str] = field(default_factory=Counter)


@dataclass
class VocabCoverage:
    """UNMAPPED/MISSING share for one controlled-vocabulary facet."""

    facet: str
    total: int
    unmapped_or_missing: int
    pct_unmapped_or_missing: float


# ---------------------------------------------------------------------------
# Path / category utilities
# ---------------------------------------------------------------------------

# Core FR-001 artifacts under data/v2/ (relative names for by_artifact keys)
V2_JSONL_ARTIFACTS: tuple[str, ...] = (
    "documents.jsonl",
    "documents_quarantine.jsonl",
    "edges.jsonl",
    "edges_quarantine.jsonl",
    "external_stubs.jsonl",
    "provisions.jsonl",
    "chunks.jsonl",
    "text_provenance.jsonl",
    "validity_timeline.jsonl",
    "authority_index.jsonl",
)

V2_OTHER_ARTIFACTS: tuple[str, ...] = (
    "reconciliation_report.md",
)

VOCAB_FACETS: tuple[str, ...] = (
    "issuing_authority",
    "legal_field",
    "sector",
    "scope",
)

UNTRACKED_ARTIFACTS: tuple[str, ...] = (
    "metadata.jsonl",
    "relationships.jsonl",
)


def resolve_project_root(cwd: Path | None = None) -> Path:
    """Resolve project root: cwd if it contains ``src/``, else parent (R4/FR-013)."""
    base = (cwd or Path.cwd()).resolve()
    if (base / "src").is_dir():
        return base
    parent = base.parent
    if (parent / "src").is_dir():
        return parent
    return base


def coerce_category(value: Any) -> str:
    """Normalize missing/unmapped category values for counting (R6).

    - ``None`` → ``"(missing)"``
    - literal ``"MISSING"`` / ``"UNMAPPED"`` passed through
    - everything else → ``str(value)``
    """
    if value is None:
        return "(missing)"
    if isinstance(value, str) and value in {"MISSING", "UNMAPPED"}:
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def get_field(row: dict[str, Any], field_path: str) -> Any:
    """Read a top-level or dotted path field (e.g. ``scope.code``)."""
    if "." not in field_path:
        return row.get(field_path)
    cur: Any = row
    for part in field_path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


# ---------------------------------------------------------------------------
# Streaming JSONL reader (skips malformed lines; FR-014)
# ---------------------------------------------------------------------------


def iter_jsonl(
    path: Path,
    *,
    skip_counter: list[int] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from a JSONL file.

    Empty lines are ignored. Malformed JSON lines are skipped and counted
    in ``skip_counter[0]`` when provided (mutable single-int list).
    """
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if skip_counter is not None:
                    skip_counter[0] += 1
                continue
            if isinstance(obj, dict):
                yield obj
            else:
                if skip_counter is not None:
                    skip_counter[0] += 1


def count_jsonl_rows(path: Path) -> tuple[int, int]:
    """Return ``(total_valid_rows, malformed_lines)`` for a JSONL path."""
    skip = [0]
    total = 0
    for _ in iter_jsonl(path, skip_counter=skip):
        total += 1
    return total, skip[0]


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def preflight(project_root: Path) -> PreflightResult:
    """Check expected ``data/v2/`` and untracked raw files (FR-001)."""
    project_root = Path(project_root)
    v2 = project_root / "data" / "v2"
    untracked = project_root / "data" / "untracked_data"

    present: list[Path] = []
    missing: list[Path] = []
    by_artifact: dict[str, bool] = {}

    for name in V2_JSONL_ARTIFACTS:
        path = v2 / name
        ok = path.is_file()
        by_artifact[name] = ok
        (present if ok else missing).append(path)

    for name in V2_OTHER_ARTIFACTS:
        path = v2 / name
        ok = path.is_file()
        by_artifact[name] = ok
        (present if ok else missing).append(path)

    vocab_dir = v2 / "vocabularies"
    vocab_ok = vocab_dir.is_dir() and any(vocab_dir.glob("*.json"))
    by_artifact["vocabularies/*.json"] = vocab_ok
    if vocab_ok:
        present.append(vocab_dir)
    else:
        missing.append(vocab_dir)

    for facet in VOCAB_FACETS:
        path = vocab_dir / f"{facet}.json"
        ok = path.is_file()
        by_artifact[f"vocabularies/{facet}.json"] = ok

    for name in UNTRACKED_ARTIFACTS:
        path = untracked / name
        ok = path.is_file()
        by_artifact[f"untracked_data/{name}"] = ok
        (present if ok else missing).append(path)

    return PreflightResult(present=present, missing=missing, by_artifact=by_artifact)


# ---------------------------------------------------------------------------
# Stream count / reservoir sample / lookup
# ---------------------------------------------------------------------------


def stream_count(
    path: Path,
    category_fields: list[str],
    coerce_missing: bool = True,
) -> StreamCountResult:
    """Single-pass total + per-field category counters (FR-003/004/006/…)."""
    counters: dict[str, Counter[str]] = {f: Counter() for f in category_fields}
    skip = [0]
    total = 0
    for row in iter_jsonl(path, skip_counter=skip):
        total += 1
        for f in category_fields:
            raw = get_field(row, f)
            if coerce_missing:
                key = coerce_category(raw)
            else:
                key = "(missing)" if raw is None else str(raw)
            counters[f][key] += 1
    return StreamCountResult(
        total_rows=total,
        malformed_lines=skip[0],
        field_counters=counters,
    )


def reservoir_sample(
    path: Path,
    sample_size: int,
    seed: int,
    predicate: Callable[[dict], bool] | None = None,
) -> ReservoirSample:
    """Algorithm R reservoir sampling over a JSONL stream (R2/FR-002)."""
    if sample_size < 0:
        raise ValueError("sample_size must be >= 0")
    rng = random.Random(seed)
    sample: list[dict] = []
    rows_seen = 0
    skip = [0]
    for row in iter_jsonl(path, skip_counter=skip):
        if predicate is not None and not predicate(row):
            continue
        rows_seen += 1
        if sample_size == 0:
            continue
        if len(sample) < sample_size:
            sample.append(row)
        else:
            j = rng.randint(0, rows_seen - 1)
            if j < sample_size:
                sample[j] = row
    return ReservoirSample(
        seed=seed,
        sample_size=sample_size,
        rows_seen=rows_seen,
        sample=sample,
    )


def lookup_by_key(path: Path, key_field: str, key_value: str) -> dict | None:
    """Stream until first row where ``key_field`` equals ``key_value``."""
    target = str(key_value)
    for row in iter_jsonl(path):
        if str(get_field(row, key_field)) == target:
            return row
    return None


# ---------------------------------------------------------------------------
# Reconciliation (FR-008 / R7)
# ---------------------------------------------------------------------------

# Patterns for identity rows and metric tables in reconciliation_report.md
_IDENTITY_LINE = re.compile(
    r"\|\s*(documents|edges)\s*\|\s*"
    r"([\d,]+)\s*==\s*([\d,]+)\s*\+\s*([\d,]+)",
    re.IGNORECASE,
)
_METRIC_LINE = re.compile(
    r"\|\s*(metadata_raw|documents_final|documents_quarantine|"
    r"relationships_raw|edges_final|edges_quarantine)\s*\|\s*([\d,]+)",
    re.IGNORECASE,
)
_ACCEPTANCE_LINE = re.compile(
    r"\|\s*(documents|edges)\s+raw\s*==\s*final\s*\+\s*quarantine\s*\|",
    re.IGNORECASE,
)


def _parse_int(token: str) -> int:
    return int(token.replace(",", "").strip())


def parse_reconciliation_report(report_path: Path) -> dict[str, dict[str, int | None]]:
    """Parse document/edge raw/final/quarantine counts from the markdown report.

    Returns ``{"documents": {"raw", "final", "quarantine"}, "edges": {...}}``
    with ``None`` values when unparseable.
    """
    result: dict[str, dict[str, int | None]] = {
        "documents": {"raw": None, "final": None, "quarantine": None},
        "edges": {"raw": None, "final": None, "quarantine": None},
    }
    if not report_path.is_file():
        return result

    text = report_path.read_text(encoding="utf-8")

    for match in _IDENTITY_LINE.finditer(text):
        label = match.group(1).lower()
        result[label]["raw"] = _parse_int(match.group(2))
        result[label]["final"] = _parse_int(match.group(3))
        result[label]["quarantine"] = _parse_int(match.group(4))

    metrics: dict[str, int] = {}
    for match in _METRIC_LINE.finditer(text):
        metrics[match.group(1).lower()] = _parse_int(match.group(2))

    if result["documents"]["raw"] is None and "metadata_raw" in metrics:
        result["documents"]["raw"] = metrics.get("metadata_raw")
        result["documents"]["final"] = metrics.get("documents_final")
        result["documents"]["quarantine"] = metrics.get("documents_quarantine")
    if result["edges"]["raw"] is None and "relationships_raw" in metrics:
        result["edges"]["raw"] = metrics.get("relationships_raw")
        result["edges"]["final"] = metrics.get("edges_final")
        result["edges"]["quarantine"] = metrics.get("edges_quarantine")

    return result


def reconcile(
    raw_path: Path,
    final_path: Path,
    quarantine_path: Path,
    report_path: Path,
    label: str,
) -> ReconciliationCheck:
    """Recompute raw == final + quarantine and compare to the report (FR-008)."""
    raw_count = count_jsonl_rows(raw_path)[0] if raw_path.is_file() else 0
    final_count = count_jsonl_rows(final_path)[0] if final_path.is_file() else 0
    quarantine_count = (
        count_jsonl_rows(quarantine_path)[0] if quarantine_path.is_file() else 0
    )
    identity_holds = raw_count == final_count + quarantine_count

    parsed = parse_reconciliation_report(report_path)
    key = label.lower()
    if key not in ("documents", "edges"):
        # Allow free-form labels that start with documents/edges
        if key.startswith("doc"):
            key = "documents"
        elif key.startswith("edge"):
            key = "edges"
        else:
            key = label.lower()

    bucket = parsed.get(key, {"raw": None, "final": None, "quarantine": None})
    report_raw = bucket.get("raw")
    report_final = bucket.get("final")
    report_quarantine = bucket.get("quarantine")

    matches_report = (
        report_raw is not None
        and report_final is not None
        and report_quarantine is not None
        and raw_count == report_raw
        and final_count == report_final
        and quarantine_count == report_quarantine
    )

    return ReconciliationCheck(
        label=label,
        raw_count=raw_count,
        final_count=final_count,
        quarantine_count=quarantine_count,
        identity_holds=identity_holds,
        report_raw=report_raw,
        report_final=report_final,
        report_quarantine=report_quarantine,
        matches_report=matches_report,
    )


# ---------------------------------------------------------------------------
# Tag tally / vocab coverage (US3)
# ---------------------------------------------------------------------------


def tally_tags(path: Path, tag_field: str) -> TagTally:
    """Count multi-valued reason/flag tags without double-counting rows (FR-009)."""
    tag_counts: Counter[str] = Counter()
    row_count = 0
    for row in iter_jsonl(path):
        row_count += 1
        raw = get_field(row, tag_field)
        if raw is None:
            continue
        if isinstance(raw, str):
            tags = [raw] if raw else []
        elif isinstance(raw, (list, tuple, set)):
            tags = [str(t) for t in raw if t is not None and str(t) != ""]
        else:
            tags = [str(raw)]
        for tag in tags:
            tag_counts[tag] += 1
    return TagTally(row_count=row_count, tag_counts=tag_counts)


def vocab_coverage(documents_path: Path, facet: str) -> VocabCoverage:
    """UNMAPPED/MISSING percentage for a document facet code field (FR-011)."""
    total = 0
    bad = 0
    code_path = f"{facet}.code"
    for row in iter_jsonl(documents_path):
        total += 1
        code = get_field(row, code_path)
        if code is None:
            # also accept bare string facet or top-level
            code = get_field(row, facet)
            if isinstance(code, dict):
                code = code.get("code")
        if code is None or str(code) in {"UNMAPPED", "MISSING", ""}:
            bad += 1
    pct = (100.0 * bad / total) if total else 0.0
    return VocabCoverage(
        facet=facet,
        total=total,
        unmapped_or_missing=bad,
        pct_unmapped_or_missing=pct,
    )
