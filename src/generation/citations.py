"""Deterministic retrieved-context citation preparation and validation.

These citations identify retrieved chunks. They are not independently verified
formal legal citations, and structural coverage is not semantic entailment.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlsplit

CITATION_CONTRACT_VERSION = "retrieved-context-citations-v1"
MAX_SOURCE_TEXT_CHARS = 4_000
EVIDENCE_MATCH_TYPES = frozenset({"explicit_offsets", "exact_unique_quote", "unavailable", "invalid"})


class EvidenceCapability(str, Enum):
    EXACT_SPANS_SUPPORTED = "EXACT_SPANS_SUPPORTED"
    EXACT_QUOTES_SUPPORTED = "EXACT_QUOTES_SUPPORTED"
    SOURCE_MAPPING_ONLY = "SOURCE_MAPPING_ONLY"
    NO_STRUCTURED_CITATIONS = "NO_STRUCTURED_CITATIONS"


PRODUCTION_EVIDENCE_CAPABILITY = EvidenceCapability.SOURCE_MAPPING_ONLY


@dataclass(frozen=True)
class EvidenceSpan:
    context_id: str
    start_char: int | None = None
    end_char: int | None = None
    quote: str | None = None
    match_type: str = "unavailable"
    confidence: str | None = None


@dataclass(frozen=True)
class EvidenceValidation:
    status: str
    span: EvidenceSpan | None
    warning: str | None = None


@dataclass(frozen=True)
class CitationSource:
    citation_id: int
    context_id: str
    document_id: str | None
    chunk_id: str | None
    title: str | None
    section: str | None
    article: str | None
    page: str | int | None
    source_path: str | None
    url: str | None
    rank: int
    score: float | None
    text: str
    is_mock: bool = False
    evidence: EvidenceSpan | None = None

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_text:
            value.pop("text")
        return value


@dataclass(frozen=True)
class CitationReference:
    citation_id: int
    marker: str
    answer_start: int | None
    answer_end: int | None
    evidence: EvidenceSpan | None = None


@dataclass(frozen=True)
class CitationValidationResult:
    answer: str
    references: tuple[CitationReference, ...]
    cited_sources: tuple[CitationSource, ...]
    invalid_ids: tuple[int, ...]
    uncited_source_ids: tuple[int, ...]
    warnings: tuple[str, ...]
    metrics: dict[str, int | float | bool | None]


_GROUP_RE = re.compile(r"\[\s*(-?\d+(?:\s*,\s*-?\d+)*)\s*\]")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|access[_-]?token|secret|password|credential|signature)\s*[:=]"
)
_SECRET_QUERY_KEYS = ("key", "token", "secret", "password", "credential", "signature", "authorization")
_SOURCE_FIELDS = (
    "text", "chunk_text", "document_id", "id_str", "chunk_id", "rank", "url",
    "rerank_score", "score", "vector_score", "title", "section", "provision_id",
    "parent_unit_id", "citation_anchor", "citation_label", "article", "article_number",
    "page", "source_path", "path",
    "evidence",
)


def prepare_citation_sources(
    chunks: Sequence[Any], *, max_text_chars: int | None = MAX_SOURCE_TEXT_CHARS,
) -> tuple[CitationSource, ...]:
    """Deduplicate contexts and assign stable one-based IDs.

    The default bounds response-facing text. Internal prompt construction passes
    ``None`` so complete retrieved chunks remain available to generation.
    """
    sources: list[CitationSource] = []
    seen: set[tuple[str, str, str]] = set()
    for fallback_rank, chunk in enumerate(chunks, 1):
        data = _chunk_data(chunk)
        text = str(data.get("text") or data.get("chunk_text") or "")
        document_id = _metadata_text(data.get("document_id") or data.get("id_str"))
        chunk_id = _metadata_text(data.get("chunk_id"))
        key = (document_id or "", chunk_id or "", text)
        if key in seen:
            continue
        seen.add(key)
        rank_value = data.get("rank", fallback_rank)
        rank = int(rank_value) if isinstance(rank_value, (int, float)) and not isinstance(rank_value, bool) else fallback_rank
        context_id = chunk_id or "context-" + hashlib.sha256("\0".join(key).encode("utf-8")).hexdigest()[:16]
        url = _safe_url(data.get("url"))
        score = _number(data.get("rerank_score"))
        if score is None:
            score = _number(data.get("score"))
        if score is None:
            score = _number(data.get("vector_score"))
        raw_page = data.get("page")
        page: str | int | None = raw_page if isinstance(raw_page, int) and not isinstance(raw_page, bool) else _metadata_text(raw_page)
        evidence = _coerce_evidence(data.get("evidence"), context_id=context_id)
        sources.append(CitationSource(
            citation_id=len(sources) + 1, context_id=context_id,
            document_id=document_id, chunk_id=chunk_id,
            title=_metadata_text(data.get("title")),
            section=_metadata_text(data.get("section") or data.get("provision_id") or data.get("parent_unit_id")
                                   or data.get("citation_anchor") or data.get("citation_label")),
            article=_metadata_text(data.get("article") or data.get("article_number")),
            page=page,
            source_path=_metadata_text(data.get("source_path") or data.get("path")), url=url,
            rank=rank, score=score, text=_bounded(text, max_text_chars),
            is_mock=bool(data.get("is_mock", False)), evidence=evidence,
        ))
    return tuple(sources)


def format_sources_for_prompt(sources: Sequence[CitationSource]) -> str:
    blocks: list[str] = []
    for source in sources:
        lines = [f"[SOURCE {source.citation_id}]"]
        for label, value in (("Title", source.title), ("Section", source.section),
                             ("Article", source.article), ("Document ID", source.document_id),
                             ("Chunk ID", source.chunk_id), ("Page", source.page)):
            if value not in (None, ""):
                lines.append(f"{label}: {value}")
        lines.extend(("Content:", source.text))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def validate_answer_citations(answer: str, sources: Sequence[CitationSource]) -> CitationValidationResult:
    """Normalize supported markers, remove invalid markers, and compute structure-only metrics."""
    source_by_id = {source.citation_id: source for source in sources}
    fenced = [match.span() for match in _FENCE_RE.finditer(answer)]
    parts: list[str] = []
    references: list[CitationReference] = []
    invalid: list[int] = []
    invalid_occurrences = 0
    cursor = 0
    output_length = 0
    for match in _GROUP_RE.finditer(answer):
        if any(start <= match.start() < end for start, end in fenced):
            continue
        prefix = answer[cursor:match.start()]
        parts.append(prefix)
        output_length += len(prefix)
        for value in (int(item.strip()) for item in match.group(1).split(",")):
            if value <= 0 or value not in source_by_id:
                invalid_occurrences += 1
                if value not in invalid:
                    invalid.append(value)
                continue
            marker = f"[{value}]"
            start = output_length
            parts.append(marker)
            output_length += len(marker)
            references.append(CitationReference(value, marker, start, output_length, source_by_id[value].evidence))
        cursor = match.end()
    suffix = answer[cursor:]
    parts.append(suffix)
    normalized = "".join(parts)
    cited_ids = list(dict.fromkeys(ref.citation_id for ref in references))
    uncited = tuple(source.citation_id for source in sources if source.citation_id not in cited_ids)
    factual, cited_factual = _structural_coverage(normalized)
    citation_count = len(references) + invalid_occurrences
    warnings: list[str] = []
    if invalid:
        warnings.append("Invalid citation IDs were removed: " + ", ".join(map(str, invalid)) + ".")
    if normalized.strip() and not references and not _is_abstention(normalized):
        warnings.append("The answer contains no valid retrieved-source citations.")
    if factual and cited_factual < factual:
        warnings.append(f"Structural citation coverage is incomplete ({cited_factual}/{factual} factual sentences).")
    coverage_warning = bool(factual and cited_factual < factual)
    metrics: dict[str, int | float | bool | None] = {
        "citation_count": citation_count,
        "valid_citation_count": len(references),
        "invalid_citation_count": invalid_occurrences,
        "unique_cited_source_count": len(cited_ids),
        "citation_validity_rate": len(references) / citation_count if citation_count else None,
        "factual_sentence_count": factual,
        "cited_factual_sentence_count": cited_factual,
        "structural_citation_coverage": cited_factual / factual if factual else None,
        "citation_coverage_warning": coverage_warning,
    }
    return CitationValidationResult(
        normalized, tuple(references), tuple(source_by_id[value] for value in cited_ids),
        tuple(invalid), uncited, tuple(warnings), metrics,
    )


def aggregate_citation_metrics(predictions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[Mapping[str, Any]] = []
    for prediction in predictions:
        metric = prediction.get("citation_metrics")
        if isinstance(metric, Mapping):
            rows.append(metric)
    validity = [float(row["citation_validity_rate"]) for row in rows if row.get("citation_validity_rate") is not None]
    coverage = [float(row["structural_citation_coverage"]) for row in rows if row.get("structural_citation_coverage") is not None]
    unique = [float(row["unique_cited_source_count"]) for row in rows if row.get("unique_cited_source_count") is not None]
    return {
        "denominators": {"cases_with_citation_metrics": len(rows), "validity_cases": len(validity), "coverage_cases": len(coverage)},
        "citation_validity_rate": sum(validity) / len(validity) if validity else None,
        "average_structural_citation_coverage": sum(coverage) / len(coverage) if coverage else None,
        "average_unique_cited_sources": sum(unique) / len(unique) if unique else None,
        "cases_with_invalid_citations": sum(int(row.get("invalid_citation_count") or 0) > 0 for row in rows),
        "cases_with_no_valid_citation": sum(int(row.get("valid_citation_count") or 0) == 0 for row in rows),
    }


def citation_contract_hash() -> str:
    return hashlib.sha256((CITATION_CONTRACT_VERSION + _GROUP_RE.pattern).encode("utf-8")).hexdigest()


def detect_evidence_capability(
    *, structured_citations: bool, explicit_offsets: bool = False, exact_quotes: bool = False,
) -> EvidenceCapability:
    if not structured_citations:
        return EvidenceCapability.NO_STRUCTURED_CITATIONS
    if explicit_offsets:
        return EvidenceCapability.EXACT_SPANS_SUPPORTED
    if exact_quotes:
        return EvidenceCapability.EXACT_QUOTES_SUPPORTED
    return EvidenceCapability.SOURCE_MAPPING_ONLY


def validate_evidence_span(
    source_text: str, evidence: EvidenceSpan | None, *, context_id: str | None = None,
) -> EvidenceValidation:
    """Validate explicit offsets or a unique exact quote without semantic guessing."""
    if evidence is None or evidence.match_type == "unavailable":
        return EvidenceValidation("unavailable", None)
    if evidence.match_type not in EVIDENCE_MATCH_TYPES or evidence.match_type == "invalid":
        return EvidenceValidation("invalid", None, "Evidence match type is invalid or unsupported.")
    if context_id is not None and evidence.context_id != context_id:
        return EvidenceValidation("invalid", None, "Evidence context ID does not match the cited source.")
    if evidence.start_char is not None or evidence.end_char is not None:
        start, end = evidence.start_char, evidence.end_char
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            return EvidenceValidation("invalid", None, "Evidence offsets must both be integers.")
        if not 0 <= start < end <= len(source_text):
            return EvidenceValidation("invalid", None, "Evidence offsets are outside the cited source text.")
        if evidence.quote is not None and source_text[start:end] != evidence.quote:
            return EvidenceValidation("invalid", None, "Recorded evidence quote does not match its offsets.")
        return EvidenceValidation("valid", evidence)
    if evidence.quote:
        first = source_text.find(evidence.quote)
        if first < 0:
            return EvidenceValidation("invalid", None, "Recorded evidence quote was not found in the cited source.")
        if source_text.find(evidence.quote, first + 1) >= 0:
            return EvidenceValidation("invalid", None, "Recorded evidence quote is not unique in the cited source.")
        matched = EvidenceSpan(
            evidence.context_id, first, first + len(evidence.quote), evidence.quote,
            "exact_unique_quote", evidence.confidence or "exact match",
        )
        return EvidenceValidation("valid", matched)
    return EvidenceValidation("invalid", None, "Evidence metadata contains neither offsets nor an exact quote.")


def evidence_diagnostics(
    sources: Sequence[CitationSource], *, capability: EvidenceCapability,
) -> dict[str, Any]:
    available = valid = rejected = 0
    warnings: list[str] = []
    for source in sources:
        if source.evidence is None:
            continue
        available += 1
        result = validate_evidence_span(source.text, source.evidence, context_id=source.context_id)
        if result.status == "valid":
            valid += 1
        elif result.status == "invalid":
            rejected += 1
            warnings.append(f"Citation [{source.citation_id}]: {result.warning}")
    return {
        "evidence_capability": capability.value,
        "evidence_spans_available": available,
        "evidence_spans_valid": valid,
        "evidence_spans_rejected": rejected,
        "span_validation_warnings": warnings,
    }


def _structural_coverage(answer: str) -> tuple[int, int]:
    if not answer.strip() or _is_abstention(answer):
        return 0, 0
    factual = cited = 0
    for line in answer.splitlines():
        value = line.strip()
        if not value or value.startswith("#") or (value.endswith(":") and len(value.split()) < 12):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?!\[\d+\])", value):
            plain = _GROUP_RE.sub("", sentence).strip()
            if len(re.findall(r"\w+", plain, re.UNICODE)) < 4:
                continue
            factual += 1
            if re.search(r"(?:\[\d+\])+\s*[.!?]?\s*$", sentence):
                cited += 1
    return factual, cited


def _is_abstention(value: str) -> bool:
    lowered = value.casefold()
    return "insufficient" in lowered or "không có đủ thông tin" in lowered


def _bounded(value: str, maximum: int | None) -> str:
    if maximum is None or len(value) <= maximum:
        return value
    if maximum < 1:
        return ""
    return value[: maximum - 1].rstrip() + "…"


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _chunk_data(chunk: Any) -> Mapping[str, Any]:
    if isinstance(chunk, Mapping):
        return chunk
    return {name: getattr(chunk, name, None) for name in _SOURCE_FIELDS}


def _metadata_text(value: Any) -> str | None:
    text = _text(value)
    return None if text is not None and _SECRET_VALUE_RE.search(text) else text


def _safe_url(value: Any) -> str | None:
    text = _metadata_text(value)
    if text is None:
        return None
    try:
        parsed = urlsplit(text)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.casefold()
            if any(marker in lowered for marker in _SECRET_QUERY_KEYS):
                return None
    except ValueError:
        return None
    return text


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _coerce_evidence(value: Any, *, context_id: str) -> EvidenceSpan | None:
    if value is None:
        return None
    if isinstance(value, EvidenceSpan):
        return value
    if not isinstance(value, Mapping):
        return EvidenceSpan(context_id=context_id, match_type="invalid")
    return EvidenceSpan(
        context_id=str(value.get("context_id") or context_id),
        start_char=value.get("start_char"),
        end_char=value.get("end_char"),
        quote=str(value["quote"]) if value.get("quote") is not None else None,
        match_type=str(value.get("match_type") or "unavailable"),
        confidence=str(value["confidence"]) if value.get("confidence") is not None else None,
    )


__all__ = ["CITATION_CONTRACT_VERSION", "MAX_SOURCE_TEXT_CHARS", "CitationReference",
           "CitationSource", "CitationValidationResult", "EvidenceCapability", "EvidenceSpan",
           "EvidenceValidation", "PRODUCTION_EVIDENCE_CAPABILITY", "aggregate_citation_metrics",
           "citation_contract_hash", "format_sources_for_prompt", "prepare_citation_sources",
           "detect_evidence_capability", "evidence_diagnostics", "validate_answer_citations",
           "validate_evidence_span"]
