"""Create the FAISS manifest required by the Streamlit production UI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_path in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from service.qa_service import load_ui_config_registry  # noqa: E402

CONFIG_PATH = PROJECT_ROOT / "configs" / "ablation_configs.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="Agent-None-PlainRAG")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing manifest.")
    args = parser.parse_args()

    registry = load_ui_config_registry(CONFIG_PATH)
    if args.config not in registry:
        print(f"Unknown config: {args.config}", file=sys.stderr)
        return 2

    config = registry[args.config]
    dense = config.get("retrieval", {}).get("dense", {})
    if dense.get("backend") != "faiss":
        print(f"{args.config} does not use a FAISS dense index.", file=sys.stderr)
        return 2

    index_dir = _resolve_path(dense.get("index_path", "data/faiss_index"))
    index_path = index_dir / "index.faiss"
    payloads_path = index_dir / "payloads.jsonl"
    manifest_path = index_dir / "index_manifest.json"

    missing = [path for path in (index_path, payloads_path) if not path.is_file()]
    if missing:
        for path in missing:
            print(f"Missing required artifact: {_display_path(path)}", file=sys.stderr)
        return 1
    if manifest_path.exists() and not args.force:
        print(f"Manifest already exists: {_display_path(manifest_path)}")
        print("Use --force to overwrite it.")
        return 0

    payload = {
        "index_path": _display_path(index_dir),
        "embedding_model": dense.get("model"),
        "corpus_version": config.get("corpus", {}).get("version"),
        "index_version": dense.get("index_version"),
        "payload_count": _jsonl_count(payloads_path),
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {_display_path(manifest_path)}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _resolve_path(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _jsonl_count(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
