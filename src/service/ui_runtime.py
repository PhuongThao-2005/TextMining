"""Dual-mode UI providers and bounded production artifact readiness checks."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from generation.citations import (
    EvidenceCapability, EvidenceSpan, evidence_diagnostics, prepare_citation_sources,
    validate_answer_citations,
)

from .qa_service import (
    ContextRow, PreflightCheck, QuestionRequest, QuestionResponse, SafeError,
    normalize_context_rows, run_preflight,
)

DEMO_MODE = "Demo Preview"
PRODUCTION_MODE = "Production"
AUTO_MODE = "Auto"
RUNTIME_MODES = (AUTO_MODE, DEMO_MODE, PRODUCTION_MODE)
ARTIFACT_SEARCH_ROOTS = (Path("data"), Path("artifacts"))
MANIFEST_NAMES = ("index_manifest.json", "manifest.json", "meta.json")


@dataclass(frozen=True)
class ArtifactCandidate:
    index_dir: Path
    manifest_path: Path
    embedding_identity: str | None
    embedding_dimension: int | None
    corpus_identity: str | None
    index_version: str | None
    payload_count: int | None
    vector_count: int | None
    created_at: str | None
    config_identity: str | None

    @property
    def label(self) -> str:
        identity = self.embedding_identity or "unknown embedding"
        corpus = self.corpus_identity or "unknown corpus"
        version = self.index_version or "unknown index"
        count = str(self.vector_count) if self.vector_count is not None else "? vectors"
        created = self.created_at or "unknown creation time"
        return f"{identity} · {corpus} · {version} · {count} · {created} · {self.index_dir.as_posix()}"


@dataclass(frozen=True)
class ProductionReadiness:
    ready: bool
    selected_config: str
    retriever_backend: str | None
    embedding_identity: str | None
    checks: tuple[PreflightCheck, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    candidates: tuple[ArtifactCandidate, ...]
    selected_artifact: ArtifactCandidate | None
    resolved_config: dict[str, Any]


@dataclass(frozen=True)
class ModeResolution:
    requested_mode: str
    active_mode: str
    production_ready: bool
    banner: str | None


class AnswerProvider(Protocol):
    def answer(self, request: QuestionRequest) -> QuestionResponse: ...


class ProductionAnswerProvider:
    """Thin adapter over the existing production QA service."""

    def __init__(self, answerer: Callable[[QuestionRequest], QuestionResponse]) -> None:
        self._answerer = answerer

    def answer(self, request: QuestionRequest) -> QuestionResponse:
        response = self._answerer(request)
        if response.is_mock or any(source.is_mock for source in response.citation_sources) or any(row.is_mock for row in response.contexts):
            raise RuntimeError("Production provider rejected a mock-marked response.")
        return replace(response, mode="production", question=request.question, is_mock=False)


class DemoAnswerProvider:
    """Deterministic UI preview provider with no production dependencies or calls."""

    def answer(self, request: QuestionRequest) -> QuestionResponse:
        scenario = _demo_scenario(request.question)
        rows = scenario["sources"]
        sources = prepare_citation_sources(rows)
        raw_answer = str(scenario.get("answer") or "")
        validation = validate_answer_citations(raw_answer, sources)
        evidence = evidence_diagnostics(
            validation.cited_sources, capability=EvidenceCapability.EXACT_SPANS_SUPPORTED,
        )
        abstained = bool(scenario.get("abstained"))
        answer = None if abstained else validation.answer
        cited_ids = {source.citation_id for source in validation.cited_sources}
        contexts = tuple(normalize_context_rows(rows))
        diagnostics = {
            "runtime_mode": "demo",
            "demo_scenario": scenario["name"],
            "production_call_performed": False,
            "latency_values_are_demo": True,
            "trace_values_are_demo": True,
            "citation_contract": {
                "invalid_ids": list(validation.invalid_ids),
                "uncited_source_ids": [source.citation_id for source in sources if source.citation_id not in cited_ids],
            },
            **evidence,
        }
        return QuestionResponse(
            status="abstained" if abstained else "completed",
            answer=answer,
            abstained=abstained,
            contexts=contexts,
            latency={"dense_retrieval": 18.0, "generation": 42.0, "total": 64.0},
            trace=tuple(scenario.get("trace") or ()),
            warnings=("Demo values only; no benchmark measurement was performed.",),
            error=None,
            resolved_config={"mode": "demo", "scenario": scenario["name"]},
            diagnostics=diagnostics,
            citation_sources=validation.cited_sources,
            citation_references=validation.references,
            citation_warnings=validation.warnings,
            citation_metrics=validation.metrics,
            suggested_followups=tuple(scenario["followups"]),
            mode="demo",
            question=request.question,
            is_mock=True,
        )


def resolve_runtime_mode(requested_mode: str, readiness: ProductionReadiness) -> ModeResolution:
    if requested_mode == DEMO_MODE:
        return ModeResolution(requested_mode, "demo", readiness.ready, None)
    if requested_mode == PRODUCTION_MODE:
        banner = None if readiness.ready else "Production is unavailable. Resolve the readiness blockers; demo data will not be used."
        return ModeResolution(requested_mode, "production", readiness.ready, banner)
    if requested_mode != AUTO_MODE:
        raise ValueError(f"Unknown runtime mode: {requested_mode}")
    if readiness.ready:
        return ModeResolution(requested_mode, "production", True, None)
    return ModeResolution(
        requested_mode, "demo", False,
        "Production data is not ready. Showing UI preview with demo data.",
    )


def discover_artifact_candidates(
    project_root: Path,
    *,
    search_roots: Sequence[Path] = ARTIFACT_SEARCH_ROOTS,
) -> tuple[ArtifactCandidate, ...]:
    """Inspect manifest files only inside controlled repository-relative roots."""
    candidates: dict[Path, ArtifactCandidate] = {}
    root = project_root.resolve()
    for configured_root in search_roots:
        scan_root = configured_root if configured_root.is_absolute() else root / configured_root
        try:
            resolved_scan = scan_root.resolve()
            resolved_scan.relative_to(root)
        except (OSError, ValueError):
            continue
        if not resolved_scan.is_dir():
            continue
        for name in MANIFEST_NAMES:
            for manifest_path in resolved_scan.rglob(name):
                candidate = _candidate_from_manifest(manifest_path, root)
                if candidate is not None:
                    candidates[candidate.index_dir.resolve()] = candidate
    return tuple(candidates[key] for key in sorted(candidates, key=lambda value: value.as_posix()))


def scan_production_readiness(
    registry: Mapping[str, dict[str, Any]],
    config_name: str,
    *,
    project_root: Path,
    environ: Mapping[str, str] | None = None,
    package_available: Callable[[str], bool] | None = None,
    search_roots: Sequence[Path] = ARTIFACT_SEARCH_ROOTS,
    selected_artifact: Path | None = None,
) -> ProductionReadiness:
    """Validate production config, runtime, and manifest-backed FAISS compatibility."""
    if config_name not in registry:
        message = f"Unknown production config {config_name!r}."
        return ProductionReadiness(False, config_name, None, None,
                                   (PreflightCheck("config", "blocked", message),),
                                   (message,), (), (), None, {})

    config = deepcopy(registry[config_name])
    dense = config.get("retrieval", {}).get("dense", {})
    backend = dense.get("backend") if dense.get("enabled") else None
    candidates = discover_artifact_candidates(project_root, search_roots=search_roots) if backend == "faiss" else ()
    compatible = tuple(candidate for candidate in candidates if not _compatibility_issues(candidate, config, config_name))

    chosen: ArtifactCandidate | None = None
    configured_dir = _resolve_path(dense.get("index_path", "data/faiss_index"), project_root) if backend == "faiss" else None
    if backend == "faiss":
        if selected_artifact is not None:
            selected_resolved = selected_artifact.resolve()
            chosen = next((item for item in compatible if item.index_dir.resolve() == selected_resolved), None)
        if chosen is None and configured_dir is not None:
            chosen = next((item for item in candidates if item.index_dir.resolve() == configured_dir.resolve()), None)
        if chosen is None and configured_dir is not None and not (configured_dir / "index.faiss").is_file() and len(compatible) == 1:
            chosen = compatible[0]
        if chosen is not None:
            dense["index_path"] = str(chosen.index_dir)
            dense["manifest_path"] = str(chosen.manifest_path)

    preflight = run_preflight(
        config, config_name=config_name, project_root=project_root,
        environ=os.environ if environ is None else environ,
        package_available=package_available,
    )
    checks = list(preflight.checks)
    blockers = list(preflight.blockers)
    warnings = list(preflight.warnings)

    if backend == "faiss":
        active_dir = _resolve_path(dense.get("index_path", "data/faiss_index"), project_root)
        manifest_path = _configured_manifest(dense, active_dir, project_root)
        if manifest_path is None:
            message = "Missing compatible FAISS manifest (index_manifest.json, manifest.json, or meta.json)."
            blockers.append(message)
            checks.append(PreflightCheck("faiss_manifest", "blocked", message))
        else:
            parsed = _candidate_from_manifest(manifest_path, project_root.resolve())
            if parsed is None:
                message = f"FAISS manifest is malformed or does not identify an index: {manifest_path.name}."
                blockers.append(message)
                checks.append(PreflightCheck("faiss_manifest", "blocked", message))
            else:
                chosen = parsed
                issues = _compatibility_issues(parsed, config, config_name)
                for issue in issues:
                    blockers.append(issue)
                    checks.append(PreflightCheck("artifact_compatibility", "blocked", issue))
                if not issues:
                    checks.append(PreflightCheck("artifact_compatibility", "ready", "Embedding, corpus, and index manifest identities are compatible."))
                actual_payload_count = _jsonl_count(active_dir / "payloads.jsonl")
                if parsed.payload_count is not None and actual_payload_count is not None and parsed.payload_count != actual_payload_count:
                    message = f"Payload count mismatch: manifest={parsed.payload_count}, file={actual_payload_count}."
                    blockers.append(message)
                    checks.append(PreflightCheck("payload_count", "blocked", message))
                elif parsed.payload_count is None:
                    warnings.append("Manifest does not record payload_count; count compatibility is unverified.")
                if parsed.vector_count is None:
                    warnings.append("Manifest does not record vector_count; index/payload cardinality is unverified.")
                if parsed.embedding_dimension is None:
                    warnings.append("Manifest does not record embedding_dimension; dimension compatibility is unverified until load.")
                if parsed.embedding_identity is None:
                    message = "Manifest does not record an embedding identity."
                    blockers.append(message)
                    checks.append(PreflightCheck("embedding_identity", "blocked", message))
                if parsed.corpus_identity is None:
                    message = "Manifest does not record a corpus identity."
                    blockers.append(message)
                    checks.append(PreflightCheck("corpus_identity", "blocked", message))
                if parsed.index_version is None:
                    warnings.append("Manifest does not record index_version.")
                cache_ready = (active_dir / "payload_cache.sqlite").is_file()
                if not cache_ready and not os.access(active_dir, os.W_OK):
                    message = "FAISS index directory is not writable and no payload_cache.sqlite is available."
                    blockers.append(message)
                    checks.append(PreflightCheck("payload_cache", "blocked", message))

        if chosen is None and len(compatible) > 1:
            message = "Multiple compatible FAISS artifacts were found; choose one explicitly."
            blockers.append(message)
            checks.append(PreflightCheck("artifact_selection", "blocked", message))

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    embedding = chosen.embedding_identity if chosen else _optional_text(dense.get("model"))
    return ProductionReadiness(
        not blockers, config_name, _optional_text(backend), embedding,
        tuple(checks), tuple(blockers), tuple(warnings), compatible, chosen,
        preflight.resolved_config,
    )


def _demo_scenario(question: str) -> dict[str, Any]:
    lowered = question.casefold()
    sources = _demo_sources()
    followups = (
        "When is supporting evidence needed?",
        "Show a complete example with several supporting sources",
        "Show an abstention example.",
    )
    if "abstain" in lowered or "abstention" in lowered or "insufficient" in lowered:
        return {"name": "abstention", "answer": "", "abstained": True, "sources": sources[:1], "followups": followups}
    if "invalid" in lowered:
        return {"name": "invalid-citation", "answer": "This preview intentionally contains an invalid marker [99].", "sources": sources[:1], "followups": followups}
    if "single source" in lowered or "what information is required" in lowered:
        return {
            "name": "single-source",
            "answer": "A complete request identifies the requester and affected record, then briefly describes the requested change [1].",
            "sources": (sources[0], sources[3]), "followups": followups,
        }
    if "multiple sources" in lowered and "complete example" not in lowered:
        return {
            "name": "multiple-sources",
            "answer": "A complete request identifies the affected record [1]. Changes to an existing record should include directly relevant supporting material [2].",
            "sources": sources[:3], "followups": followups,
            "trace": (
                {"step": 1, "event": "plan", "action": "retrieve", "status": "demo"},
                {"step": 2, "event": "answer", "status": "demo"},
            ),
        }
    return {
        "name": "long-answer-three-sources", "answer": _long_demo_answer(),
        "sources": sources[:3], "followups": followups,
        "trace": (
            {"step": 1, "event": "plan", "action": "retrieve", "status": "demo"},
            {"step": 2, "event": "answer", "status": "demo"},
        ),
    }


def _demo_sources() -> tuple[dict[str, Any], ...]:
    guide_text = (
        "Mock content — not an authoritative document.\n\n"
        "A complete request identifies the requester and the affected record. It provides the reference number, "
        "the name associated with the record, and a concise description of the requested change. This information "
        "allows the fictional receiving team to locate the correct record before review begins."
    )
    guide_quote = (
        "A complete request identifies the requester and the affected record. It provides the reference number, "
        "the name associated with the record, and a concise description of the requested change."
    )
    handbook_text = (
        "Mock content — not an authoritative document.\n\n"
        "When a request would change an existing record, it should include supporting material that directly relates "
        "to the requested correction. A practical request has three parts: identification of the record and requester; "
        "a clear description of the requested action; and directly relevant evidence when the current record is challenged."
    )
    handbook_quote = (
        "When a request would change an existing record, it should include supporting material that directly relates "
        "to the requested correction. A practical request has three parts: identification of the record and requester; "
        "a clear description of the requested action; and directly relevant evidence when the current record is challenged."
    )
    intake_text = (
        "Mock content — not an authoritative document.\n\n"
        "The fictional intake team performs an initial completeness review after submission. Complete requests proceed "
        "to substantive review, while incomplete requests are returned with a list of missing items. A completeness review "
        "is not final approval; it only confirms that enough information is present for evaluation."
    )
    intake_quote = (
        "The fictional intake team performs an initial completeness review after submission. Complete requests proceed "
        "to substantive review, while incomplete requests are returned with a list of missing items. A completeness review "
        "is not final approval; it only confirms that enough information is present for evaluation."
    )
    return (
        _demo_source("demo-request-guide", "demo-request-guide-01", "Demo Request Submission Guide", "Required information", 1, 0.93, guide_text, guide_quote),
        _demo_source("demo-evidence-handbook", "demo-evidence-handbook-02", "Demo Evidence Review Handbook", "Supporting materials", 2, 0.89, handbook_text, handbook_quote),
        _demo_source("demo-intake-procedure", "demo-intake-procedure-03", "Demo Intake Procedure", "Completeness review", 3, 0.84, intake_text, intake_quote),
        {
            "document_id": "demo-background-note", "chunk_id": "demo-background-note-04",
            "title": "Demo Background Note", "section": "General context", "rank": 4,
            "score": 0.52, "is_mock": True,
            "text": "Mock content — not an authoritative document. This additional context is intentionally uncited.",
        },
    )


def _demo_source(
    document_id: str, chunk_id: str, title: str, section: str, rank: int, score: float,
    source_text: str, quote: str,
) -> dict[str, Any]:
    start = source_text.index(quote)
    return {
        "document_id": document_id, "chunk_id": chunk_id, "title": title, "section": section,
        "rank": rank, "score": score, "is_mock": True, "text": source_text,
        "evidence": EvidenceSpan(
            context_id=chunk_id, start_char=start, end_char=start + len(quote), quote=quote,
            match_type="explicit_offsets", confidence="exact match",
        ),
    }


def _long_demo_answer() -> str:
    return """To submit a complete fictional request, begin with enough identifying information for the receiving team to locate the affected record. Include the reference number, the name associated with the record, and a concise description of the requested change [1].

Next, explain the desired outcome and why the change is needed. When a request would alter an existing record, directly relevant supporting material should connect the proposed correction to the information already on file [1][2]. General background material should be left out when it does not help a reviewer assess the requested change.

A practical submission can be organized into three parts:

1. Identify the record and requester.
2. Describe the requested action clearly.
3. Attach directly relevant evidence when challenging or amending the current record [2].

After submission, the fictional intake team performs an initial completeness review. Complete requests proceed to substantive review; incomplete requests are returned with a list of missing items [3]. This initial check is not final approval and does not predict the eventual outcome.

The clearest approach is therefore to keep the request concise, distinguish factual corrections from unsupported preferences, and attach only material that helps connect each requested change to the record under review [2][3]."""


def _candidate_from_manifest(manifest_path: Path, project_root: Path) -> ArtifactCandidate | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    dense = _nested_mapping(payload, "resolved_config", "retrieval", "dense")
    raw_index = payload.get("index_path") or dense.get("index_path")
    index_dir = _resolve_manifest_path(raw_index, manifest_path.parent, project_root) if raw_index else manifest_path.parent
    if not ((index_dir / "index.faiss").is_file() or (index_dir / "payloads.jsonl").is_file()):
        return None
    model = payload.get("embedding_model") or payload.get("embedding_identity") or dense.get("model")
    corpus = payload.get("corpus_version") or payload.get("corpus_identity")
    return ArtifactCandidate(
        index_dir=index_dir, manifest_path=manifest_path,
        embedding_identity=_optional_text(model),
        embedding_dimension=_optional_int(payload.get("embedding_dimension") or payload.get("dimension")),
        corpus_identity=_optional_text(corpus), index_version=_optional_text(payload.get("index_version")),
        payload_count=_optional_int(payload.get("payload_count")),
        vector_count=_optional_int(payload.get("vector_count") or payload.get("index_vector_count")),
        created_at=_optional_text(payload.get("created_at") or payload.get("creation_timestamp") or payload.get("start_time")),
        config_identity=_optional_text(payload.get("config_name") or payload.get("selected_config")),
    )


def _compatibility_issues(candidate: ArtifactCandidate, config: Mapping[str, Any], config_name: str) -> tuple[str, ...]:
    dense = config.get("retrieval", {}).get("dense", {})
    corpus = config.get("corpus", {})
    issues: list[str] = []
    expected_model = _optional_text(dense.get("model"))
    if candidate.embedding_identity and expected_model and candidate.embedding_identity != expected_model:
        issues.append(f"Embedding identity mismatch: config={expected_model}, manifest={candidate.embedding_identity}.")
    expected_dimension = _optional_int(dense.get("dimension") or dense.get("embedding_dimension"))
    if expected_dimension and candidate.embedding_dimension and expected_dimension != candidate.embedding_dimension:
        issues.append(f"Embedding dimension mismatch: config={expected_dimension}, manifest={candidate.embedding_dimension}.")
    expected_corpus = _optional_text(corpus.get("version"))
    if candidate.corpus_identity and expected_corpus and candidate.corpus_identity != expected_corpus:
        issues.append(f"Corpus identity mismatch: config={expected_corpus}, manifest={candidate.corpus_identity}.")
    expected_index = _optional_text(dense.get("index_version"))
    if expected_index and "pending" not in expected_index and candidate.index_version and expected_index != candidate.index_version:
        issues.append(f"Index version mismatch: config={expected_index}, manifest={candidate.index_version}.")
    if candidate.config_identity and candidate.config_identity != config_name:
        issues.append(f"Artifact config identity mismatch: selected={config_name}, manifest={candidate.config_identity}.")
    return tuple(issues)


def _configured_manifest(dense: Mapping[str, Any], index_dir: Path, project_root: Path) -> Path | None:
    explicit = dense.get("manifest_path")
    if explicit:
        path = _resolve_path(explicit, project_root)
        return path if path.is_file() else None
    for name in MANIFEST_NAMES:
        path = index_dir / name
        if path.is_file():
            return path
    return None


def _nested_mapping(value: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _resolve_manifest_path(value: Any, manifest_dir: Path, project_root: Path) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    project_candidate = project_root / path
    return project_candidate if project_candidate.exists() else manifest_dir / path


def _resolve_path(value: Any, project_root: Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else project_root / path


def _jsonl_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return None


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


__all__ = [
    "ARTIFACT_SEARCH_ROOTS", "AUTO_MODE", "AnswerProvider", "ArtifactCandidate",
    "DEMO_MODE", "DemoAnswerProvider", "ModeResolution", "PRODUCTION_MODE",
    "ProductionAnswerProvider", "ProductionReadiness", "RUNTIME_MODES",
    "discover_artifact_candidates", "resolve_runtime_mode", "scan_production_readiness",
]
