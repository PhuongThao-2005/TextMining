"""Unit tests for eda.dataset_v2 — synthetic tmp_path fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eda.dataset_v2 import (
    coerce_category,
    lookup_by_key,
    parse_reconciliation_report,
    preflight,
    reconcile,
    reservoir_sample,
    resolve_project_root,
    stream_count,
    tally_tags,
    vocab_coverage,
)


def _write_jsonl(path: Path, rows: list[dict | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row.rstrip("\n") + "\n")
            else:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# coerce_category (T014)
# ---------------------------------------------------------------------------


def test_coerce_category_none() -> None:
    assert coerce_category(None) == "(missing)"


def test_coerce_category_missing_unmapped_passthrough() -> None:
    assert coerce_category("MISSING") == "MISSING"
    assert coerce_category("UNMAPPED") == "UNMAPPED"


def test_coerce_category_normal_values() -> None:
    assert coerce_category("Luật") == "Luật"
    assert coerce_category(3) == "3"
    assert coerce_category(True) == "true"
    assert coerce_category(False) == "false"


# ---------------------------------------------------------------------------
# stream_count (T015)
# ---------------------------------------------------------------------------


def test_stream_count_totals_and_fields(tmp_path: Path) -> None:
    path = tmp_path / "docs.jsonl"
    _write_jsonl(
        path,
        [
            {"legal_authority_rank": 1, "scope": {"code": "A"}},
            {"legal_authority_rank": 1, "scope": {"code": "UNMAPPED"}},
            {"legal_authority_rank": None, "scope": {"code": None}},
            {"legal_authority_rank": 2},
        ],
    )
    result = stream_count(path, ["legal_authority_rank", "scope.code"])
    assert result.total_rows == 4
    assert result.malformed_lines == 0
    assert result.field_counters["legal_authority_rank"]["1"] == 2
    assert result.field_counters["legal_authority_rank"]["2"] == 1
    assert result.field_counters["legal_authority_rank"]["(missing)"] == 1
    assert result.field_counters["scope.code"]["A"] == 1
    assert result.field_counters["scope.code"]["UNMAPPED"] == 1
    assert result.field_counters["scope.code"]["(missing)"] == 2


def test_stream_count_skips_malformed(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    _write_jsonl(
        path,
        [
            {"x": "ok"},
            "{not-json",
            {"x": "also"},
            "[]",  # not a dict → treated as skip
        ],
    )
    result = stream_count(path, ["x"])
    assert result.total_rows == 2
    assert result.malformed_lines == 2
    assert result.field_counters["x"]["ok"] == 1
    assert result.field_counters["x"]["also"] == 1


# ---------------------------------------------------------------------------
# reservoir_sample (T016)
# ---------------------------------------------------------------------------


def test_reservoir_sample_determinism(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    rows = [{"chunk_id": f"c{i}", "n": i} for i in range(50)]
    _write_jsonl(path, rows)

    a = reservoir_sample(path, sample_size=10, seed=42)
    b = reservoir_sample(path, sample_size=10, seed=42)
    c = reservoir_sample(path, sample_size=10, seed=7)

    assert a.rows_seen == 50
    assert len(a.sample) == 10
    assert [r["chunk_id"] for r in a.sample] == [r["chunk_id"] for r in b.sample]
    assert [r["chunk_id"] for r in a.sample] != [r["chunk_id"] for r in c.sample]


def test_reservoir_sample_size_bounds(tmp_path: Path) -> None:
    path = tmp_path / "small.jsonl"
    _write_jsonl(path, [{"i": 1}, {"i": 2}, {"i": 3}])
    result = reservoir_sample(path, sample_size=10, seed=1)
    assert result.rows_seen == 3
    assert len(result.sample) == 3


def test_reservoir_sample_predicate(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    _write_jsonl(
        path,
        [
            {"keep": True, "id": 1},
            {"keep": False, "id": 2},
            {"keep": True, "id": 3},
        ],
    )
    result = reservoir_sample(
        path, sample_size=5, seed=0, predicate=lambda r: r.get("keep") is True
    )
    assert result.rows_seen == 2
    assert all(r["keep"] for r in result.sample)


# ---------------------------------------------------------------------------
# preflight / resolve_project_root (T017)
# ---------------------------------------------------------------------------


def test_resolve_project_root_with_src(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert resolve_project_root(tmp_path) == tmp_path.resolve()


def test_resolve_project_root_from_notebooks(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    assert resolve_project_root(notebooks) == tmp_path.resolve()


def test_preflight_present_missing(tmp_path: Path) -> None:
    v2 = tmp_path / "data" / "v2"
    v2.mkdir(parents=True)
    untracked = tmp_path / "data" / "untracked_data"
    untracked.mkdir(parents=True)

    (v2 / "documents.jsonl").write_text("{}\n", encoding="utf-8")
    (v2 / "edges.jsonl").write_text("{}\n", encoding="utf-8")
    vocab = v2 / "vocabularies"
    vocab.mkdir()
    (vocab / "scope.json").write_text("{}", encoding="utf-8")
    (untracked / "metadata.jsonl").write_text("{}\n", encoding="utf-8")

    result = preflight(tmp_path)
    assert result.by_artifact["documents.jsonl"] is True
    assert result.by_artifact["edges.jsonl"] is True
    assert result.by_artifact["chunks.jsonl"] is False
    assert result.by_artifact["vocabularies/*.json"] is True
    assert result.by_artifact["untracked_data/metadata.jsonl"] is True
    assert result.by_artifact["untracked_data/relationships.jsonl"] is False
    assert any(p.name == "documents.jsonl" for p in result.present)
    assert any(p.name == "chunks.jsonl" for p in result.missing)


# ---------------------------------------------------------------------------
# lookup_by_key (T018)
# ---------------------------------------------------------------------------


def test_lookup_by_key_first_match(tmp_path: Path) -> None:
    path = tmp_path / "provisions.jsonl"
    _write_jsonl(
        path,
        [
            {"unit_id": "u1", "id_str": "d1"},
            {"unit_id": "u2", "id_str": "d2"},
            {"unit_id": "u2", "id_str": "d2b"},
        ],
    )
    hit = lookup_by_key(path, "unit_id", "u2")
    assert hit is not None
    assert hit["id_str"] == "d2"


def test_lookup_by_key_not_found(tmp_path: Path) -> None:
    path = tmp_path / "provisions.jsonl"
    _write_jsonl(path, [{"unit_id": "u1"}])
    assert lookup_by_key(path, "unit_id", "missing") is None


# ---------------------------------------------------------------------------
# reconcile (T025 / T026)
# ---------------------------------------------------------------------------


def _write_report(
    path: Path,
    *,
    doc_raw: int,
    doc_final: int,
    doc_q: int,
    edge_raw: int,
    edge_final: int,
    edge_q: int,
) -> None:
    path.write_text(
        f"""# Reconciliation report

## Identities

| Identity | Check | Holds |
| --- | --- | :---: |
| documents | {doc_raw:,} == {doc_final:,} + {doc_q:,} | ✅ |
| edges | {edge_raw:,} == {edge_final:,} + {edge_q:,} | ✅ |

## Metrics

| Metric | Count |
| --- | ---: |
| metadata_raw | {doc_raw:,} |
| documents_final | {doc_final:,} |
| documents_quarantine | {doc_q:,} |
| relationships_raw | {edge_raw:,} |
| edges_final | {edge_final:,} |
| edges_quarantine | {edge_q:,} |
""",
        encoding="utf-8",
    )


def test_reconcile_pass_matches_report(tmp_path: Path) -> None:
    raw = tmp_path / "metadata.jsonl"
    final = tmp_path / "documents.jsonl"
    quarantine = tmp_path / "documents_quarantine.jsonl"
    report = tmp_path / "reconciliation_report.md"

    _write_jsonl(raw, [{"id": i} for i in range(5)])
    _write_jsonl(final, [{"id": i} for i in range(3)])
    _write_jsonl(quarantine, [{"id": i} for i in range(2)])
    _write_report(
        report,
        doc_raw=5,
        doc_final=3,
        doc_q=2,
        edge_raw=10,
        edge_final=8,
        edge_q=2,
    )

    check = reconcile(raw, final, quarantine, report, "documents")
    assert check.raw_count == 5
    assert check.final_count == 3
    assert check.quarantine_count == 2
    assert check.identity_holds is True
    assert check.report_raw == 5
    assert check.report_final == 3
    assert check.report_quarantine == 2
    assert check.matches_report is True


def test_reconcile_fail_broken_identity(tmp_path: Path) -> None:
    raw = tmp_path / "metadata.jsonl"
    final = tmp_path / "documents.jsonl"
    quarantine = tmp_path / "documents_quarantine.jsonl"
    report = tmp_path / "reconciliation_report.md"

    _write_jsonl(raw, [{"id": i} for i in range(5)])
    _write_jsonl(final, [{"id": i} for i in range(2)])
    _write_jsonl(quarantine, [{"id": i} for i in range(1)])  # 2+1 != 5
    _write_report(
        report,
        doc_raw=5,
        doc_final=3,
        doc_q=2,
        edge_raw=1,
        edge_final=1,
        edge_q=0,
    )

    check = reconcile(raw, final, quarantine, report, "documents")
    assert check.identity_holds is False
    assert check.matches_report is False


def test_reconcile_unparseable_report(tmp_path: Path) -> None:
    raw = tmp_path / "metadata.jsonl"
    final = tmp_path / "documents.jsonl"
    quarantine = tmp_path / "documents_quarantine.jsonl"
    report = tmp_path / "reconciliation_report.md"

    _write_jsonl(raw, [{"id": 1}])
    _write_jsonl(final, [{"id": 1}])
    _write_jsonl(quarantine, [])
    report.write_text("no identity tables here\n", encoding="utf-8")

    check = reconcile(raw, final, quarantine, report, "documents")
    assert check.identity_holds is True
    assert check.report_raw is None
    assert check.matches_report is False


def test_parse_reconciliation_report_metrics_fallback(tmp_path: Path) -> None:
    report = tmp_path / "reconciliation_report.md"
    report.write_text(
        """
| Metric | Count |
| --- | ---: |
| metadata_raw | 153,420 |
| documents_final | 151,624 |
| documents_quarantine | 1,796 |
| relationships_raw | 897,890 |
| edges_final | 883,256 |
| edges_quarantine | 14,634 |
""",
        encoding="utf-8",
    )
    parsed = parse_reconciliation_report(report)
    assert parsed["documents"]["raw"] == 153420
    assert parsed["documents"]["final"] == 151624
    assert parsed["edges"]["quarantine"] == 14634


# ---------------------------------------------------------------------------
# tally_tags (T030)
# ---------------------------------------------------------------------------


def test_tally_tags_multi_tag_accounting(tmp_path: Path) -> None:
    path = tmp_path / "documents_quarantine.jsonl"
    _write_jsonl(
        path,
        [
            {"exclusion_reasons": ["missing_id"]},
            {"exclusion_reasons": ["missing_id", "unknown_type"]},
            {"exclusion_reasons": []},
            {"exclusion_reasons": ["future_issue_date"]},
        ],
    )
    tally = tally_tags(path, "exclusion_reasons")
    assert tally.row_count == 4
    assert tally.tag_counts["missing_id"] == 2
    assert tally.tag_counts["unknown_type"] == 1
    assert tally.tag_counts["future_issue_date"] == 1
    # sum of tag counts can exceed row_count; rows not double-counted
    assert sum(tally.tag_counts.values()) == 4
    assert tally.row_count == 4


def test_tally_tags_edge_quality_flags(tmp_path: Path) -> None:
    path = tmp_path / "edges_quarantine.jsonl"
    _write_jsonl(
        path,
        [
            {"edge_quality_flags": ["self_loop", "missing_dst"]},
            {"edge_quality_flags": ["self_loop"]},
        ],
    )
    tally = tally_tags(path, "edge_quality_flags")
    assert tally.row_count == 2
    assert tally.tag_counts["self_loop"] == 2
    assert tally.tag_counts["missing_dst"] == 1


# ---------------------------------------------------------------------------
# vocab_coverage (T031)
# ---------------------------------------------------------------------------


def test_vocab_coverage_percentages(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    _write_jsonl(
        path,
        [
            {"issuing_authority": {"code": "bo_tu_phap", "surface": "Bộ Tư pháp"}},
            {"issuing_authority": {"code": "UNMAPPED", "surface": "???"}},
            {"issuing_authority": {"code": "MISSING", "surface": ""}},
            {"issuing_authority": {"code": "bo_cong_an"}},
            {"issuing_authority": None},
        ],
    )
    cov = vocab_coverage(path, "issuing_authority")
    assert cov.facet == "issuing_authority"
    assert cov.total == 5
    assert cov.unmapped_or_missing == 3
    assert cov.pct_unmapped_or_missing == pytest.approx(60.0)


def test_vocab_coverage_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    _write_jsonl(path, [])
    cov = vocab_coverage(path, "scope")
    assert cov.total == 0
    assert cov.unmapped_or_missing == 0
    assert cov.pct_unmapped_or_missing == 0.0
