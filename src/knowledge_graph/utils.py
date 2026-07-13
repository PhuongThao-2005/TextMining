from __future__ import annotations

from typing import Any
from retrieval.io_utils import clean_text


def as_int(value: Any, default: int = 0) -> int:
    """Convert a JSON value to int with a stable default."""

    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def as_bool(value: Any, default: bool = False) -> bool:
    """Convert a JSON value to bool with a stable default."""

    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def quality_flags(values: Any) -> tuple[str, ...]:
    """Normalize a JSON list of quality flags into an immutable tuple."""

    if not values:
        return ()
    return tuple(clean_text(item) for item in values if clean_text(item))
