"""Lightweight process memory probes for Colab / notebook RAM budgeting.

Uses ``psutil`` when available; falls back to Windows/Linux OS counters so
notebooks still get a useful RSS reading without an extra dependency.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MemorySnapshot:
    """Point-in-time process RSS (and optional system memory)."""

    label: str
    rss_bytes: int
    rss_mb: float
    available_mb: float | None = None
    percent: float | None = None
    backend: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rss_psutil() -> tuple[int, float | None, float | None, str] | None:
    try:
        import psutil  # type: ignore
    except ImportError:
        return None
    proc = psutil.Process(os.getpid())
    rss = int(proc.memory_info().rss)
    vm = psutil.virtual_memory()
    return rss, float(vm.available) / (1024 * 1024), float(vm.percent), "psutil"


def _rss_resource() -> tuple[int, None, None, str] | None:
    try:
        import resource
    except ImportError:
        return None
    # Linux: ru_maxrss is KB; macOS: bytes. Prefer current RSS via /proc when possible.
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        rss = int(usage)
    else:
        rss = int(usage) * 1024
    return rss, None, None, "resource"


def _rss_proc_status() -> tuple[int, None, None, str] | None:
    status = "/proc/self/status"
    if not os.path.exists(status):
        return None
    try:
        with open(status, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    # VmRSS:   12345 kB
                    parts = line.split()
                    return int(parts[1]) * 1024, None, None, "proc"
    except OSError:
        return None
    return None


def process_rss_bytes() -> tuple[int, str]:
    """Return (rss_bytes, backend_name)."""
    for getter in (_rss_psutil, _rss_proc_status, _rss_resource):
        result = getter()
        if result is None:
            continue
        rss, _avail, _pct, backend = result
        return int(rss), backend
    return 0, "unavailable"


def snapshot_memory(label: str = "rss") -> MemorySnapshot:
    """Capture a process RSS snapshot with optional system availability."""
    ps = _rss_psutil()
    if ps is not None:
        rss, avail_mb, percent, backend = ps
        return MemorySnapshot(
            label=label,
            rss_bytes=rss,
            rss_mb=round(rss / (1024 * 1024), 1),
            available_mb=None if avail_mb is None else round(avail_mb, 1),
            percent=percent,
            backend=backend,
        )
    rss, backend = process_rss_bytes()
    return MemorySnapshot(
        label=label,
        rss_bytes=rss,
        rss_mb=round(rss / (1024 * 1024), 1),
        available_mb=None,
        percent=None,
        backend=backend,
    )


def print_memory(label: str = "rss") -> MemorySnapshot:
    """Print a one-line memory probe and return the snapshot."""
    snap = snapshot_memory(label)
    extra = ""
    if snap.available_mb is not None:
        extra = f" | system_available={snap.available_mb:.0f} MB ({snap.percent}%)"
    print(f"[mem] {snap.label}: process_rss={snap.rss_mb:.1f} MB ({snap.backend}){extra}")
    return snap
