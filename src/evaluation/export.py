"""Safe export of canonical run artifacts to durable notebook storage."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .artifacts import CANONICAL_ARTIFACTS, ArtifactError, load_run_artifacts


@dataclass(frozen=True)
class ExportResult:
    directory: Path
    archive: Path | None
    files: tuple[str, ...]


def export_run_artifacts(
    run_dir: Path,
    export_root: Path,
    *,
    create_zip: bool = True,
    sensitive_values: Sequence[str] = (),
) -> ExportResult:
    """Copy only canonical artifacts, refusing overwrite or credential leakage."""

    artifacts = load_run_artifacts(run_dir, require_completed=True)
    run_id = str(artifacts.manifest.get("run_id") or run_dir.name)
    target = export_root.resolve() / run_id
    archive = export_root.resolve() / f"{run_id}.zip"
    if target.exists() or (create_zip and archive.exists()):
        raise ArtifactError(f"Export already exists; refusing to overwrite: {target}")
    source_paths = [run_dir.resolve() / name for name in CANONICAL_ARTIFACTS.values()]
    for source in source_paths:
        if source.is_file():
            text = source.read_text(encoding="utf-8", errors="ignore")
            if any(value and value in text for value in sensitive_values) or _has_authenticated_url(text):
                raise ArtifactError(f"Potential credential detected; export stopped before copying {source.name}.")
    export_root.resolve().mkdir(parents=True, exist_ok=True)
    target.mkdir()
    copied: list[str] = []
    try:
        for source in source_paths:
            if source.is_file():
                shutil.copy2(source, target / source.name)
                copied.append(source.name)
        archive_path: Path | None = None
        if create_zip:
            archive_path = Path(shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=target))
        return ExportResult(target, archive_path, tuple(copied))
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _has_authenticated_url(text: str) -> bool:
    import re

    return re.search(r"https?://[^/@\s:]+:[^/@\s]+@", text, flags=re.IGNORECASE) is not None
