"""Check whether the Streamlit UI can run a production question."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from service.local_env import apply_local_environment  # noqa: E402
from service.qa_service import list_interactive_configs, load_ui_config_registry  # noqa: E402
from service.ui_runtime import scan_production_readiness  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "configs" / "ablation_configs.yaml"
ENV_KEYS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_BASE_MODEL",
    "LLM_LARGER_MODEL",
    "BM25_SERVICE_URL",
    "BM25_INDEX_DIR",
    "BM25_INDEX_VERSION",
    "BM25_API_KEY",
    "HF_HUB_OFFLINE",
    "HF_HOME",
    "SENTENCE_TRANSFORMERS_HOME",
    "TORCH_HOME",
    "HTTP_PROXY",
    "HTTPS_PROXY",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="Agent-None-PlainRAG")
    parser.add_argument("--all", action="store_true", help="Show readiness for every interactive config.")
    args = parser.parse_args()

    apply_local_environment(PROJECT_ROOT)
    registry = load_ui_config_registry(CONFIG_PATH)
    configs = [option.name for option in list_interactive_configs(registry, project_root=PROJECT_ROOT)] if args.all else [args.config]

    print("Environment:")
    for key in ENV_KEYS:
        print(f"  {key}: {'set' if os.environ.get(key) else 'missing'}")

    all_ready = True
    for config_name in configs:
        readiness = scan_production_readiness(registry, config_name, project_root=PROJECT_ROOT)
        all_ready = all_ready and readiness.ready
        print()
        print(f"Config: {config_name}")
        print(f"  ready: {readiness.ready}")
        print(f"  backend: {readiness.retriever_backend or 'N/A'}")
        print(f"  artifact: {readiness.selected_artifact.index_dir if readiness.selected_artifact else 'N/A'}")
        if readiness.blockers:
            print("  blockers:")
            for blocker in readiness.blockers:
                print(f"    - {blocker}")
        if readiness.warnings:
            print("  warnings:")
            for warning in readiness.warnings:
                print(f"    - {warning}")

    return 0 if all_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
