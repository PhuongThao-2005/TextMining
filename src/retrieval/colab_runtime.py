"""Colab-safe runtime profile, load-plan, and memory helpers (feature 005).

Pure helpers for notebook orchestration around FAISS + portable graph pickle.
No hybrid ranking changes; no silent embedder swap.
"""

from __future__ import annotations

import gc
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

GraphSourceMode = Literal["pickle", "jsonl_rebuild", "unavailable"]
SessionOutcomeLabel = Literal[
    "vector_only_colab_safe_success",
    "hybrid_colab_safe_success_pickle",
    "hybrid_unavailable",
    "unconstrained_success",
    "failed_preflight",
    "failed_oom_or_runtime",
]
ComponentAction = Literal[
    "load",
    "reuse",
    "defer",
    "skip",
    "opt_in_required",
    "warn_rebuild",
]
PipelineStage = Literal[
    "config_preflight",
    "vector_load",
    "vector_smoke",
    "graph_load",
    "hybrid_smoke",
    "generation",
    "heavy_optional",
]

STRUCTURAL_JSONL_NAMES: tuple[str, ...] = (
    "documents.jsonl",
    "provisions.jsonl",
    "chunks.jsonl",
    "edges.jsonl",
    "external_stubs.jsonl",
)
OVERLAY_JSONL_NAMES: tuple[str, ...] = (
    "validity_timeline.jsonl",
    "authority_index.jsonl",
)


@dataclass
class RuntimeProfile:
    """Named config targeting host RAM class (Colab-safe vs unconstrained)."""

    name: Literal["colab_safe", "unconstrained"]
    colab_safe: bool

    prefer_graph_pickle: bool = True
    allow_jsonl_graph_rebuild: bool = False
    graph_pickle_path: Path | None = None
    v2_data_dir: Path | None = None

    top_k: int = 20
    top_n: int = 8
    hybrid_max_hop: int = 1
    hybrid_max_context: int = 8
    score_threshold: float = 0.30
    embedding_model: str = "intfloat/multilingual-e5-large"

    enable_hybrid_expansion: bool = True
    enable_graph_guided_prefilter_demo: bool = False
    use_hybrid_evidence_for_generation: bool = True
    local_expand_units: bool = False

    run_payload_csv_export: bool = False
    run_payload_cache_export: bool = False
    run_benchmark_sample: bool = False
    run_filter_profile_comparison: bool = False
    benchmark_sample_size: int = 5
    payload_csv_export_limit: int | None = 5000


def resolve_runtime_profile(
    name: str,
    *,
    project_root: Path | None = None,
    graph_pickle_path: Path | str | None = None,
    v2_data_dir: Path | str | None = None,
    embedding_model: str = "intfloat/multilingual-e5-large",
    allow_jsonl_graph_rebuild: bool | None = None,
    enable_hybrid_expansion: bool = True,
    enable_graph_guided_prefilter_demo: bool | None = None,
    run_payload_csv_export: bool | None = None,
    run_payload_cache_export: bool | None = None,
    run_benchmark_sample: bool | None = None,
    run_filter_profile_comparison: bool | None = None,
    top_k: int | None = None,
    top_n: int | None = None,
    hybrid_max_hop: int | None = None,
    hybrid_max_context: int | None = None,
    score_threshold: float = 0.30,
    benchmark_sample_size: int | None = None,
    use_hybrid_evidence_for_generation: bool = True,
    local_expand_units: bool = False,
    payload_csv_export_limit: int | None = 5000,
) -> RuntimeProfile:
    """Build a RuntimeProfile from a profile name + optional overrides."""

    key = (name or "colab_safe").strip().lower()
    if key not in {"colab_safe", "unconstrained"}:
        raise ValueError(f"Unknown RUNTIME_PROFILE={name!r}; use 'colab_safe' or 'unconstrained'")

    root = Path(project_root) if project_root is not None else Path.cwd()
    pickle_path = Path(graph_pickle_path) if graph_pickle_path is not None else root / "data" / "graph" / "knowledge_graph.gpickle"
    v2_dir = Path(v2_data_dir) if v2_data_dir is not None else root / "data" / "v2"
    colab_safe = key == "colab_safe"

    if colab_safe:
        return RuntimeProfile(
            name="colab_safe",
            colab_safe=True,
            prefer_graph_pickle=True,
            allow_jsonl_graph_rebuild=False if allow_jsonl_graph_rebuild is None else bool(allow_jsonl_graph_rebuild),
            graph_pickle_path=pickle_path,
            v2_data_dir=v2_dir,
            top_k=20 if top_k is None else int(top_k),
            top_n=8 if top_n is None else int(top_n),
            hybrid_max_hop=1 if hybrid_max_hop is None else int(hybrid_max_hop),
            hybrid_max_context=8 if hybrid_max_context is None else int(hybrid_max_context),
            score_threshold=float(score_threshold),
            embedding_model=embedding_model,
            enable_hybrid_expansion=bool(enable_hybrid_expansion),
            enable_graph_guided_prefilter_demo=False
            if enable_graph_guided_prefilter_demo is None
            else bool(enable_graph_guided_prefilter_demo),
            use_hybrid_evidence_for_generation=bool(use_hybrid_evidence_for_generation),
            local_expand_units=bool(local_expand_units),
            run_payload_csv_export=False if run_payload_csv_export is None else bool(run_payload_csv_export),
            run_payload_cache_export=False if run_payload_cache_export is None else bool(run_payload_cache_export),
            run_benchmark_sample=False if run_benchmark_sample is None else bool(run_benchmark_sample),
            run_filter_profile_comparison=False
            if run_filter_profile_comparison is None
            else bool(run_filter_profile_comparison),
            benchmark_sample_size=5 if benchmark_sample_size is None else int(benchmark_sample_size),
            payload_csv_export_limit=payload_csv_export_limit,
        )

    return RuntimeProfile(
        name="unconstrained",
        colab_safe=False,
        prefer_graph_pickle=True,
        allow_jsonl_graph_rebuild=True if allow_jsonl_graph_rebuild is None else bool(allow_jsonl_graph_rebuild),
        graph_pickle_path=pickle_path,
        v2_data_dir=v2_dir,
        top_k=30 if top_k is None else int(top_k),
        top_n=10 if top_n is None else int(top_n),
        hybrid_max_hop=1 if hybrid_max_hop is None else int(hybrid_max_hop),
        hybrid_max_context=12 if hybrid_max_context is None else int(hybrid_max_context),
        score_threshold=float(score_threshold),
        embedding_model=embedding_model,
        enable_hybrid_expansion=bool(enable_hybrid_expansion),
        enable_graph_guided_prefilter_demo=False
        if enable_graph_guided_prefilter_demo is None
        else bool(enable_graph_guided_prefilter_demo),
        use_hybrid_evidence_for_generation=bool(use_hybrid_evidence_for_generation),
        local_expand_units=bool(local_expand_units),
        run_payload_csv_export=True if run_payload_csv_export is None else bool(run_payload_csv_export),
        run_payload_cache_export=True if run_payload_cache_export is None else bool(run_payload_cache_export),
        run_benchmark_sample=False if run_benchmark_sample is None else bool(run_benchmark_sample),
        run_filter_profile_comparison=True
        if run_filter_profile_comparison is None
        else bool(run_filter_profile_comparison),
        benchmark_sample_size=10 if benchmark_sample_size is None else int(benchmark_sample_size),
        payload_csv_export_limit=payload_csv_export_limit,
    )


@dataclass
class ArtifactPresence:
    key: str
    path: Path
    required_for: list[str]
    present: bool
    byte_size: int | None
    notes: str = ""


@dataclass
class ComponentLoadAction:
    component: str
    action: ComponentAction
    detail: str


@dataclass
class MemorySnapshot:
    source: str
    process_rss_bytes: int | None
    available_system_bytes: int | None
    note: str = ""

    def format_line(self) -> str:
        rss = _fmt_bytes(self.process_rss_bytes)
        avail = _fmt_bytes(self.available_system_bytes)
        return (
            f"MemorySnapshot(source={self.source}, process_rss={rss}, "
            f"available_system={avail}, note={self.note!r})"
        )


@dataclass
class LoadPlan:
    profile: str
    artifacts: list[ArtifactPresence]
    actions: list[ComponentLoadAction]
    graph_source_mode: GraphSourceMode
    hybrid_expected: bool
    warnings: list[str] = field(default_factory=list)
    memory_before: MemorySnapshot | None = None


@dataclass
class ResidentComponentSnapshot:
    store_loaded: bool
    embedder_loaded: bool
    structural_graph_loaded: bool
    graph_source_mode: GraphSourceMode | None
    overlays_loaded: bool
    hybrid_retriever_ready: bool
    generator_configured: bool
    optional_frames_held: list[str] = field(default_factory=list)


@dataclass
class CleanupRequest:
    drop_export_frames: bool = True
    drop_comparison_records: bool = True
    unload_overlays: bool = False
    unload_structural_graph: bool = False
    run_gc: bool = True


@dataclass
class GraphSourceDecision:
    mode: GraphSourceMode
    pickle_path: Path | None
    pickle_present: bool
    jsonl_structural_ready: bool
    missing_structural_jsonl: list[str]
    rebuild_opt_in_required: bool
    rebuild_warning: str | None
    detail: str


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.2f} MB"


def _file_size(path: Path) -> int | None:
    try:
        if path.exists() and path.is_file():
            return int(path.stat().st_size)
    except OSError:
        return None
    return None


def structural_jsonl_ready(v2_data_dir: Path) -> tuple[bool, list[str]]:
    """Return (all_present, missing_names) for structural v2 JSONL set."""

    missing = [name for name in STRUCTURAL_JSONL_NAMES if not (v2_data_dir / name).exists()]
    return (not missing, missing)


def decide_graph_source_mode(
    *,
    pickle_path: Path | str | None,
    v2_data_dir: Path | str | None,
    colab_safe: bool,
    allow_jsonl_graph_rebuild: bool,
    prefer_graph_pickle: bool = True,
) -> GraphSourceDecision:
    """Pickle-first graph source decision (research R3 / FR-003/FR-004)."""

    ppath = Path(pickle_path) if pickle_path is not None else None
    v2 = Path(v2_data_dir) if v2_data_dir is not None else None
    pickle_present = bool(ppath is not None and ppath.exists() and ppath.is_file())
    jsonl_ready = False
    missing: list[str] = []
    if v2 is not None:
        jsonl_ready, missing = structural_jsonl_ready(v2)

    if prefer_graph_pickle and pickle_present:
        return GraphSourceDecision(
            mode="pickle",
            pickle_path=ppath,
            pickle_present=True,
            jsonl_structural_ready=jsonl_ready,
            missing_structural_jsonl=missing,
            rebuild_opt_in_required=False,
            rebuild_warning=None,
            detail=f"Portable graph pickle present at {ppath}",
        )

    if jsonl_ready:
        if colab_safe and not allow_jsonl_graph_rebuild:
            warn = (
                "Structural JSONL present but ALLOW_JSONL_GRAPH_REBUILD=False under Colab-safe. "
                "Full JSONL rebuild may exceed ~12GB RAM. Hybrid marked unavailable unless you "
                "set ALLOW_JSONL_GRAPH_REBUILD=True after acknowledging the risk, or provide "
                "knowledge_graph.gpickle."
            )
            return GraphSourceDecision(
                mode="unavailable",
                pickle_path=ppath,
                pickle_present=False,
                jsonl_structural_ready=True,
                missing_structural_jsonl=[],
                rebuild_opt_in_required=True,
                rebuild_warning=warn,
                detail=warn,
            )
        warn = (
            "No portable graph pickle; rebuilding structural graph from full v2 JSONL. "
            "This may exceed ~12GB RAM on free Colab."
            if colab_safe
            else "No portable graph pickle; rebuilding structural graph from full v2 JSONL."
        )
        return GraphSourceDecision(
            mode="jsonl_rebuild",
            pickle_path=ppath,
            pickle_present=False,
            jsonl_structural_ready=True,
            missing_structural_jsonl=[],
            rebuild_opt_in_required=False,
            rebuild_warning=warn if colab_safe else None,
            detail=warn,
        )

    detail = "No graph pickle and structural JSONL incomplete; hybrid unavailable."
    return GraphSourceDecision(
        mode="unavailable",
        pickle_path=ppath,
        pickle_present=False,
        jsonl_structural_ready=False,
        missing_structural_jsonl=missing,
        rebuild_opt_in_required=False,
        rebuild_warning=None,
        detail=detail,
    )


def inventory_artifacts(
    *,
    index_dir: Path,
    graph_pickle_path: Path | None,
    v2_data_dir: Path | None,
) -> list[ArtifactPresence]:
    """List FAISS / graph / overlay artifact presence and sizes."""

    rows: list[ArtifactPresence] = []

    def add(key: str, path: Path, required_for: list[str], notes: str = "") -> None:
        present = path.exists()
        size = _file_size(path) if present and path.is_file() else None
        if present and path.is_dir():
            notes = (notes + "; directory").strip("; ")
        rows.append(
            ArtifactPresence(
                key=key,
                path=path,
                required_for=required_for,
                present=present,
                byte_size=size,
                notes=notes,
            )
        )

    add("index.faiss", index_dir / "index.faiss", ["vector"])
    add("payloads.jsonl", index_dir / "payloads.jsonl", ["vector", "payload_cache_rebuild"])
    cache_path = index_dir / "payload_cache.sqlite"
    cache_notes = ""
    if cache_path.exists():
        cache_notes = "preferred derived cache"
        try:
            from retrieval.sqlite_faiss_store import _check_payload_cache

            st = _check_payload_cache(index_dir)
            if st.is_stale:
                cache_notes = "stale cache — rebuild may run"
            else:
                cache_notes = "fresh cache"
        except Exception:
            cache_notes = "present (freshness check unavailable)"
    else:
        cache_notes = "missing — cold rebuild costly on Colab"
    add("payload_cache.sqlite", cache_path, ["vector"], notes=cache_notes)
    add("id_map.json", index_dir / "id_map.json", ["vector_optional"], notes="optional")

    if graph_pickle_path is not None:
        add(
            "knowledge_graph.gpickle",
            Path(graph_pickle_path),
            ["hybrid_structural"],
            notes="preferred hybrid structural graph",
        )

    if v2_data_dir is not None:
        v2 = Path(v2_data_dir)
        for name in STRUCTURAL_JSONL_NAMES:
            add(name, v2 / name, ["jsonl_rebuild"], notes="rebuild source only")
        for name in OVERLAY_JSONL_NAMES:
            add(name, v2 / name, ["overlay"], notes="optional overlay")

    return rows


def build_load_plan(
    profile: RuntimeProfile,
    *,
    index_dir: Path,
    memory_before: MemorySnapshot | None = None,
) -> LoadPlan:
    """Build preflight LoadPlan for Colab-safe / unconstrained profiles."""

    pickle_path = profile.graph_pickle_path
    v2_dir = profile.v2_data_dir
    artifacts = inventory_artifacts(
        index_dir=index_dir,
        graph_pickle_path=pickle_path,
        v2_data_dir=v2_dir,
    )
    decision = decide_graph_source_mode(
        pickle_path=pickle_path,
        v2_data_dir=v2_dir,
        colab_safe=profile.colab_safe,
        allow_jsonl_graph_rebuild=profile.allow_jsonl_graph_rebuild,
        prefer_graph_pickle=profile.prefer_graph_pickle,
    )

    by_key = {a.key: a for a in artifacts}
    actions: list[ComponentLoadAction] = []
    warnings: list[str] = []

    # FAISS / cache
    if by_key.get("index.faiss") and by_key["index.faiss"].present:
        actions.append(ComponentLoadAction("faiss_index", "load", "index.faiss present"))
    else:
        actions.append(ComponentLoadAction("faiss_index", "skip", "index.faiss missing — vector path blocked"))
        warnings.append("Missing index.faiss")

    cache = by_key.get("payload_cache.sqlite")
    if cache and cache.present and "stale" not in (cache.notes or ""):
        actions.append(ComponentLoadAction("payload_cache", "reuse", cache.notes or "reuse sqlite cache"))
    elif cache and cache.present:
        actions.append(ComponentLoadAction("payload_cache", "warn_rebuild", cache.notes or "stale cache"))
        warnings.append("payload_cache.sqlite stale — cold rebuild from payloads.jsonl can be costly on Colab")
    else:
        actions.append(
            ComponentLoadAction(
                "payload_cache",
                "warn_rebuild",
                "missing — cold rebuild from payloads.jsonl can be costly on Colab",
            )
        )
        warnings.append("payload_cache.sqlite missing — cold rebuild may spike RAM/disk/time")

    actions.append(
        ComponentLoadAction(
            "embedder",
            "load",
            f"model={profile.embedding_model} (must match FAISS; no silent swap)",
        )
    )

    if decision.mode == "pickle":
        actions.append(
            ComponentLoadAction(
                "structural_graph",
                "load",
                f"load_knowledge_graph({decision.pickle_path})",
            )
        )
    elif decision.mode == "jsonl_rebuild":
        actions.append(
            ComponentLoadAction(
                "structural_graph",
                "warn_rebuild" if profile.colab_safe else "load",
                decision.detail,
            )
        )
        if decision.rebuild_warning:
            warnings.append(decision.rebuild_warning)
    else:
        if decision.rebuild_opt_in_required:
            actions.append(
                ComponentLoadAction(
                    "structural_graph",
                    "opt_in_required",
                    decision.detail,
                )
            )
            warnings.append(decision.detail)
        else:
            actions.append(ComponentLoadAction("structural_graph", "skip", decision.detail))
            warnings.append(decision.detail)

    # overlays optional
    overlay_present = any(
        a.present for a in artifacts if a.key in OVERLAY_JSONL_NAMES
    )
    if decision.mode in {"pickle", "jsonl_rebuild"}:
        if overlay_present:
            actions.append(ComponentLoadAction("overlays", "load", "optional validity/authority join"))
        else:
            actions.append(ComponentLoadAction("overlays", "skip", "overlay files missing — structural hybrid still OK"))
    else:
        actions.append(ComponentLoadAction("overlays", "defer", "graph unavailable"))

    actions.append(ComponentLoadAction("generator", "defer", "optional remote API; env-based credentials"))

    if profile.run_payload_csv_export:
        actions.append(ComponentLoadAction("payload_csv_export", "opt_in_required", "RUN_PAYLOAD_CSV_EXPORT=True"))
    else:
        actions.append(ComponentLoadAction("payload_csv_export", "skip", "RUN_PAYLOAD_CSV_EXPORT=False"))

    if profile.run_payload_cache_export:
        actions.append(ComponentLoadAction("payload_cache_export", "opt_in_required", "RUN_PAYLOAD_CACHE_EXPORT=True"))
    else:
        actions.append(ComponentLoadAction("payload_cache_export", "skip", "RUN_PAYLOAD_CACHE_EXPORT=False"))

    if profile.run_benchmark_sample:
        actions.append(
            ComponentLoadAction(
                "benchmark_sample",
                "opt_in_required",
                f"RUN_BENCHMARK_SAMPLE=True size={profile.benchmark_sample_size}",
            )
        )
    else:
        actions.append(ComponentLoadAction("benchmark_sample", "skip", "RUN_BENCHMARK_SAMPLE=False"))

    if profile.enable_graph_guided_prefilter_demo:
        actions.append(
            ComponentLoadAction(
                "graph_guided_prefilter",
                "opt_in_required",
                "ENABLE_GRAPH_GUIDED_PREFILTER_DEMO=True (secondary path)",
            )
        )
    else:
        actions.append(
            ComponentLoadAction(
                "graph_guided_prefilter",
                "skip",
                "ENABLE_GRAPH_GUIDED_PREFILTER_DEMO=False",
            )
        )

    hybrid_expected = decision.mode in {"pickle", "jsonl_rebuild"} and profile.enable_hybrid_expansion

    return LoadPlan(
        profile=profile.name,
        artifacts=artifacts,
        actions=actions,
        graph_source_mode=decision.mode,
        hybrid_expected=hybrid_expected,
        warnings=warnings,
        memory_before=memory_before,
    )


def format_load_plan(plan: LoadPlan) -> str:
    """Human-readable load plan for notebook print."""

    lines = [
        "=== Colab load plan / preflight ===",
        f"Profile: {plan.profile}",
        f"Graph source mode: {plan.graph_source_mode}",
        f"Hybrid expected: {plan.hybrid_expected}",
    ]
    if plan.memory_before is not None:
        lines.append(plan.memory_before.format_line())
    lines.append("Artifacts:")
    for a in plan.artifacts:
        flag = "OK" if a.present else "MISSING"
        size = _fmt_bytes(a.byte_size) if a.present else "—"
        note = f" ({a.notes})" if a.notes else ""
        lines.append(f"  [{flag}] {a.key}: {size}{note}  path={a.path}")
    lines.append("Planned actions:")
    for act in plan.actions:
        lines.append(f"  - {act.component}: {act.action} — {act.detail}")
    if plan.warnings:
        lines.append("Warnings:")
        for w in plan.warnings:
            lines.append(f"  ! {w}")
    return "\n".join(lines)


def capture_memory_snapshot(note: str = "") -> MemorySnapshot:
    """Best-effort process/system memory snapshot (FR-010). Never raises."""

    # 1) psutil
    try:
        import psutil  # type: ignore

        proc = psutil.Process(os.getpid())
        rss = int(proc.memory_info().rss)
        avail = None
        try:
            avail = int(psutil.virtual_memory().available)
        except Exception:
            avail = None
        return MemorySnapshot(
            source="psutil",
            process_rss_bytes=rss,
            available_system_bytes=avail,
            note=note,
        )
    except Exception:
        pass

    # 2) Linux /proc
    try:
        status_path = Path("/proc/self/status")
        if status_path.exists():
            rss = None
            for line in status_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # kB
                    rss = int(parts[1]) * 1024
                    break
            avail = None
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("MemAvailable:"):
                        parts = line.split()
                        avail = int(parts[1]) * 1024
                        break
            return MemorySnapshot(
                source="procfs",
                process_rss_bytes=rss,
                available_system_bytes=avail,
                note=note,
            )
    except Exception:
        pass

    # 3) resource (macOS / Unix max RSS; on macOS often bytes)
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss = int(usage.ru_maxrss)
        # Linux reports kB; macOS bytes
        if platform.system() == "Linux":
            rss *= 1024
        return MemorySnapshot(
            source="resource",
            process_rss_bytes=rss,
            available_system_bytes=None,
            note=note or "ru_maxrss (peak, not necessarily current)",
        )
    except Exception:
        pass

    return MemorySnapshot(
        source="unavailable",
        process_rss_bytes=None,
        available_system_bytes=None,
        note=note or "memory API unavailable; continuing without hard block",
    )


def format_resident_snapshot(snap: ResidentComponentSnapshot) -> str:
    lines = [
        "=== Resident components ===",
        f"  store_loaded: {snap.store_loaded}",
        f"  embedder_loaded: {snap.embedder_loaded}",
        f"  structural_graph_loaded: {snap.structural_graph_loaded}",
        f"  graph_source_mode: {snap.graph_source_mode}",
        f"  overlays_loaded: {snap.overlays_loaded}",
        f"  hybrid_retriever_ready: {snap.hybrid_retriever_ready}",
        f"  generator_configured: {snap.generator_configured}",
        f"  optional_frames_held: {snap.optional_frames_held or []}",
    ]
    return "\n".join(lines)


def session_outcome_label(
    *,
    colab_safe: bool,
    structural_ready: bool,
    loaded_from_pickle: bool,
    hybrid_used: bool,
    vector_ok: bool,
    hybrid_requested: bool = False,
    preflight_failed: bool = False,
) -> SessionOutcomeLabel:
    """Map session state to FR-023 success labels."""

    if preflight_failed:
        return "failed_preflight"
    if hybrid_requested and not structural_ready:
        return "hybrid_unavailable"
    if hybrid_used and structural_ready:
        if colab_safe and loaded_from_pickle:
            return "hybrid_colab_safe_success_pickle"
        if colab_safe:
            return "hybrid_colab_safe_success_pickle"  # still hybrid success; pickle preferred but rebuild allowed via opt-in
        return "unconstrained_success"
    if vector_ok and not hybrid_used:
        if colab_safe:
            return "vector_only_colab_safe_success"
        return "unconstrained_success"
    if not vector_ok:
        return "failed_preflight"
    return "hybrid_unavailable"


def format_session_outcome(label: SessionOutcomeLabel, detail: str = "") -> str:
    messages = {
        "vector_only_colab_safe_success": "Session outcome: vector_only_colab_safe_success — pure vector path OK; graph not used.",
        "hybrid_colab_safe_success_pickle": "Session outcome: hybrid_colab_safe_success_pickle — structural graph loaded (preferably pickle) and hybrid path used.",
        "hybrid_unavailable": "Session outcome: hybrid_unavailable — hybrid requested/intended but graph not loaded (policy/artifacts/RAM).",
        "unconstrained_success": "Session outcome: unconstrained_success — fuller demo profile path completed.",
        "failed_preflight": "Session outcome: failed_preflight — required artifacts or setup incomplete.",
        "failed_oom_or_runtime": "Session outcome: failed_oom_or_runtime — observational failure label.",
    }
    base = messages.get(label, f"Session outcome: {label}")
    if detail:
        return f"{base} {detail}"
    return base


def payload_cache_rebuild_warning(index_dir: Path) -> str | None:
    """Return warning text if payload cache missing/stale; else None."""

    cache = index_dir / "payload_cache.sqlite"
    payloads = index_dir / "payloads.jsonl"
    if not payloads.exists():
        return None
    try:
        from retrieval.sqlite_faiss_store import _check_payload_cache

        st = _check_payload_cache(index_dir)
        if not st.exists or st.is_stale:
            return (
                "WARNING (Colab-safe): payload_cache.sqlite is missing or stale. "
                "Cold rebuild from payloads.jsonl can be costly on ~12GB RAM "
                f"(payloads size ≈ {_fmt_bytes(st.payload_size)}). Prefer shipping a fresh cache."
            )
    except Exception:
        if not cache.exists():
            return (
                "WARNING (Colab-safe): payload_cache.sqlite missing. "
                "Cold rebuild from payloads.jsonl can be costly on Colab."
            )
    return None


def apply_cleanup(ns: dict[str, Any], request: CleanupRequest | None = None) -> list[str]:
    """Best-effort drop of optional heavy objects in a notebook globals dict.

    Returns list of actions taken. Not an OS memory reservation (FR-012).
    """

    req = request or CleanupRequest()
    actions: list[str] = []

    if req.drop_export_frames:
        for key in ("payload_export_df", "export_rows", "comparison_df", "filter_profile_rows"):
            if key in ns and ns[key] is not None:
                ns[key] = None
                actions.append(f"dropped {key}")

    if req.drop_comparison_records:
        for key in ("comparison_record", "comparison_records", "benchmark_summary", "mode_comparison_records"):
            if key in ns and ns[key] is not None:
                ns[key] = None
                actions.append(f"dropped {key}")

    if req.unload_overlays:
        for key in ("overlay_bundle", "document_overlays"):
            if key in ns:
                ns[key] = {} if key == "document_overlays" else None
                actions.append(f"unloaded {key}")
        status = ns.get("graph_load_status")
        if status is not None and hasattr(status, "overlays_ready"):
            status.overlays_ready = False
            actions.append("graph_load_status.overlays_ready=False")

    if req.unload_structural_graph:
        for key in ("kg_graph", "graph_expansion", "hybrid_retriever", "kg_build_result", "kg_pickle_result"):
            if key in ns:
                ns[key] = None
                actions.append(f"unloaded {key}")
        status = ns.get("graph_load_status")
        if status is not None:
            if hasattr(status, "structural_ready"):
                status.structural_ready = False
            if hasattr(status, "graph_source_mode"):
                status.graph_source_mode = "unavailable"
            if hasattr(status, "loaded_from_pickle"):
                status.loaded_from_pickle = False
            actions.append("structural graph marked unavailable — hybrid requires reload")

    if req.run_gc:
        collected = gc.collect()
        actions.append(f"gc.collect() -> {collected}")

    return actions


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convenience for tests/debug; Paths become strings."""

    raw = asdict(obj)

    def convert(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value

    return convert(raw)  # type: ignore[return-value]
