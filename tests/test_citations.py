from types import SimpleNamespace

import pytest

from generation.citations import (
    MAX_SOURCE_TEXT_CHARS, aggregate_citation_metrics, format_sources_for_prompt,
    prepare_citation_sources, validate_answer_citations,
)
from generation.reasoning_client import format_context_for_prompt
from generation.prompt_strategy import PromptStrategy, build_generation_prompt


def chunk(identifier: str, text: str, *, rank: int = 1, **values):
    return SimpleNamespace(chunk_id=identifier, chunk_text=text, rank=rank, **values)


def test_source_preparation_is_deterministic_deduplicated_and_preserves_rank() -> None:
    chunks = [chunk("a", "Alpha", rank=4, id_str="doc"), chunk("a", "Alpha", rank=9, id_str="doc"), chunk("b", "Beta", rank=2)]
    sources = prepare_citation_sources(chunks)
    assert [(item.citation_id, item.chunk_id, item.rank) for item in sources] == [(1, "a", 4), (2, "b", 2)]
    assert prepare_citation_sources(chunks) == sources
    assert prepare_citation_sources([]) == ()


def test_missing_metadata_and_source_text_bound() -> None:
    full_text = "x" * (MAX_SOURCE_TEXT_CHARS + 20)
    source = prepare_citation_sources([chunk("a", full_text)])[0]
    assert source.title is None and source.url is None
    assert len(source.text) == MAX_SOURCE_TEXT_CHARS
    assert "secret" not in source.to_dict(include_text=False)
    assert full_text in format_context_for_prompt([chunk("a", full_text)])


def test_secret_bearing_metadata_and_urls_are_removed() -> None:
    source = prepare_citation_sources([chunk(
        "a", "Evidence", path="api_key=do-not-expose",
        url="https://example.test/source?X-Amz-Signature=do-not-expose",
    )])[0]
    assert source.source_path is None
    assert source.url is None


def test_prompt_uses_shared_source_ids_and_strict_contract() -> None:
    context = format_sources_for_prompt(prepare_citation_sources([chunk("a", "Evidence")]))
    assert "[SOURCE 1]" in context
    for strategy in (PromptStrategy.BASE, PromptStrategy.REASONING):
        prompt = build_generation_prompt(question="Q", answer_type="", context=context, strategy=strategy)
        assert "Never invent a source number" in prompt
        assert "Return only the final answer" in prompt
        assert "context is insufficient" in prompt


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Claim [1].", "Claim [1]."),
        ("Claim [1][2].", "Claim [1][2]."),
        ("Claim [1, 2].", "Claim [1][2]."),
        ("Claim [1][1].", "Claim [1][1]."),
        ("Array [abc] remains.", "Array [abc] remains."),
        ("Malformed [1, x] remains.", "Malformed [1, x] remains."),
    ],
)
def test_parser_supported_forms(answer: str, expected: str) -> None:
    result = validate_answer_citations(answer, prepare_citation_sources([chunk("a", "A"), chunk("b", "B")]))
    assert result.answer == expected


def test_invalid_ids_are_removed_not_remapped_with_deterministic_warnings() -> None:
    sources = prepare_citation_sources([chunk("a", "A")])
    result = validate_answer_citations("Supported [1]. Unsupported [0][-2][9].", sources)
    assert result.answer == "Supported [1]. Unsupported ."
    assert result.invalid_ids == (0, -2, 9)
    assert [item.citation_id for item in result.cited_sources] == [1]
    assert result.metrics["invalid_citation_count"] == 3
    assert result.warnings[0] == "Invalid citation IDs were removed: 0, -2, 9."


def test_repeated_invalid_markers_count_occurrences_but_report_unique_ids() -> None:
    result = validate_answer_citations("Claim [9][9].", prepare_citation_sources([chunk("a", "A")]))
    assert result.invalid_ids == (9,)
    assert result.metrics["citation_count"] == 2
    assert result.metrics["invalid_citation_count"] == 2


def test_code_fence_markers_are_ignored() -> None:
    answer = "```text\n[9]\n```\nActual claim [1]."
    result = validate_answer_citations(answer, prepare_citation_sources([chunk("a", "A")]))
    assert "[9]" in result.answer
    assert result.invalid_ids == ()


def test_no_citations_and_uncited_sources_warn_without_crashing() -> None:
    result = validate_answer_citations("This is a factual sentence with enough words.", prepare_citation_sources([chunk("a", "A")]))
    assert result.uncited_source_ids == (1,)
    assert result.metrics["citation_validity_rate"] is None
    assert "no valid" in result.warnings[0]


def test_structural_coverage_denominator_ignores_headings_and_short_fragments() -> None:
    answer = "# Heading\nShort.\nFirst factual sentence has support [1]. Second factual sentence lacks support."
    result = validate_answer_citations(answer, prepare_citation_sources([chunk("a", "A")]))
    assert result.metrics["factual_sentence_count"] == 2
    assert result.metrics["cited_factual_sentence_count"] == 1
    assert result.metrics["structural_citation_coverage"] == pytest.approx(0.5)
    assert result.metrics["citation_coverage_warning"] is True
    abstain = validate_answer_citations("Không có đủ thông tin trong ngữ cảnh được cung cấp.", ())
    assert abstain.metrics["structural_citation_coverage"] is None


def test_aggregation_keeps_missing_metrics_null() -> None:
    empty = aggregate_citation_metrics([{"status": "success"}])
    assert empty["citation_validity_rate"] is None
    values = aggregate_citation_metrics([{"citation_metrics": {"citation_validity_rate": 1.0, "structural_citation_coverage": .5, "unique_cited_source_count": 2, "invalid_citation_count": 0, "valid_citation_count": 1}}])
    assert values["average_structural_citation_coverage"] == .5
