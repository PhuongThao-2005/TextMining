"""Local environment bootstrap shared by UI and command-line checks."""
from __future__ import annotations

import os
from pathlib import Path

RUNTIME_OVERRIDE_KEYS = frozenset(
    {
        "HF_HUB_OFFLINE",
        "GRAPH_PICKLE_PATH",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
        "TORCH_HOME",
        "XDG_CACHE_HOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    }
)

PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

DEAD_LOCAL_PROXY_VALUES = frozenset(
    {
        "http://127.0.0.1:9",
        "https://127.0.0.1:9",
    }
)


def load_local_env(project_root: Path, *, path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from the project `.env` file.

    Runtime switches intentionally override inherited shell values so teammates
    can fix local cache/proxy behavior without touching source code. Secrets
    still keep process-environment precedence.
    """
    env_path = path or project_root / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or (key not in RUNTIME_OVERRIDE_KEYS and key in os.environ):
            continue
        if key in RUNTIME_OVERRIDE_KEYS and value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def configure_local_cache_dirs(project_root: Path) -> None:
    """Keep model and Torch caches inside the repository by default."""
    cache_root = project_root / ".cache"
    defaults = {
        "XDG_CACHE_HOME": cache_root,
        "HF_HOME": cache_root / "huggingface",
        "TRANSFORMERS_CACHE": cache_root / "huggingface" / "hub",
        "SENTENCE_TRANSFORMERS_HOME": cache_root / "sentence-transformers",
        "TORCH_HOME": cache_root / "torch",
    }
    for key, path in defaults.items():
        os.environ.setdefault(key, str(path))
        configured = Path(os.environ[key])
        resolved = configured if configured.is_absolute() else project_root / configured
        os.environ[key] = str(resolved)
        resolved.mkdir(parents=True, exist_ok=True)


def clear_dead_local_proxy_settings() -> None:
    """Remove the local blackhole proxy used by some shells to disable network."""
    if os.environ.get("HF_HUB_OFFLINE") == "1":
        return
    for key in PROXY_KEYS:
        if os.environ.get(key, "").rstrip("/") in DEAD_LOCAL_PROXY_VALUES:
            os.environ.pop(key, None)


def apply_local_environment(project_root: Path) -> None:
    """Apply local `.env`, cache defaults, and safe proxy cleanup."""
    load_local_env(project_root)
    configure_local_cache_dirs(project_root)
    clear_dead_local_proxy_settings()
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("HF_HUB_OFFLINE", "0")


__all__ = [
    "DEAD_LOCAL_PROXY_VALUES",
    "PROXY_KEYS",
    "RUNTIME_OVERRIDE_KEYS",
    "apply_local_environment",
    "clear_dead_local_proxy_settings",
    "configure_local_cache_dirs",
    "load_local_env",
]
