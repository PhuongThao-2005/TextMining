from __future__ import annotations

import os
from pathlib import Path

from service.local_env import apply_local_environment, clear_dead_local_proxy_settings, load_local_env


def test_local_env_can_clear_inherited_proxy(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HF_HUB_OFFLINE=0\nHTTP_PROXY=\nHTTPS_PROXY=\n", encoding="utf-8")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

    load_local_env(tmp_path, path=env_file)

    assert "HTTP_PROXY" not in os.environ
    assert "HTTPS_PROXY" not in os.environ


def test_dead_proxy_cleanup_respects_offline_mode(monkeypatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")

    clear_dead_local_proxy_settings()

    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:9"


def test_apply_local_environment_uses_project_cache_defaults(monkeypatch, tmp_path: Path) -> None:
    for key in ("XDG_CACHE_HOME", "HF_HOME", "TRANSFORMERS_CACHE", "SENTENCE_TRANSFORMERS_HOME", "TORCH_HOME"):
        monkeypatch.delenv(key, raising=False)

    apply_local_environment(tmp_path)

    assert (tmp_path / ".cache" / "huggingface").is_dir()
    assert (tmp_path / ".cache" / "sentence-transformers").is_dir()
