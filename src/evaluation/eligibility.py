"""Eligibility filtering for frozen QA benchmark rows.

Mirrors the skip logic in ``scripts/evaluate_retrieval.py``: every row is
classified into exactly one of eligible / skipped_unanswerable /
skipped_missing_ground_truth. No row is ever silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EligibleCase:
    """A QA benchmark row that has usable ground-truth chunk IDs."""

    qa_id: str
    question: str
    category: str | None
    difficulty: str | None
    answer_type: str | None
    ground_truth_chunk_ids: set[str]
    ground_truth_document_ids: set[str]
    ground_truth_provision_ids: set[str]
    raw_row: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilitySummary:
    """Outcome of classifying every benchmark row."""

    total_rows: int
    eligible: list[EligibleCase]
    skipped_unanswerable: int
    skipped_missing_ground_truth: int


def _qa_id(row: dict[str, Any], index: int) -> str:
    return str(row.get("qa_id") or row.get("id") or f"qa-{index:06d}")


def _is_unanswerable(row: dict[str, Any]) -> bool:
    answer_type = str(row.get("answer_type") or "").lower()
    category = str(row.get("category") or "").lower()
    return answer_type == "unanswerable" or category == "unanswerable"


def select_eligible_cases(rows: list[dict[str, Any]], sample_limit: int | None) -> EligibilitySummary:
    """Classify every benchmark row and apply an optional sample cap.

    Every row is classified into exactly one of: eligible,
    skipped_unanswerable, skipped_missing_ground_truth. ``sample_limit``
    caps the number of eligible cases collected (rows examined after the
    cap is reached are not counted at all, matching
    ``scripts/evaluate_retrieval.py``'s ``--limit`` behavior).
    """

    eligible: list[EligibleCase] = []
    skipped_unanswerable = 0
    skipped_missing_ground_truth = 0
    total_rows = 0

    for index, row in enumerate(rows, start=1):
        if sample_limit is not None and len(eligible) >= sample_limit:
            break

        total_rows += 1

        if _is_unanswerable(row):
            skipped_unanswerable += 1
            continue

        ground_truth = row.get("ground_truth") or {}
        chunk_ids = {str(cid) for cid in (ground_truth.get("chunk_ids") or []) if cid}
        if not chunk_ids:
            skipped_missing_ground_truth += 1
            continue

        document_ids = {str(did) for did in (ground_truth.get("document_ids") or []) if did}
        provision_ids = {str(pid) for pid in (ground_truth.get("provision_ids") or []) if pid}

        eligible.append(
            EligibleCase(
                qa_id=_qa_id(row, index),
                question=str(row.get("question") or ""),
                category=row.get("category"),
                difficulty=row.get("difficulty"),
                answer_type=row.get("answer_type"),
                ground_truth_chunk_ids=chunk_ids,
                ground_truth_document_ids=document_ids,
                ground_truth_provision_ids=provision_ids,
                raw_row=row,
            )
        )

    return EligibilitySummary(
        total_rows=total_rows,
        eligible=eligible,
        skipped_unanswerable=skipped_unanswerable,
        skipped_missing_ground_truth=skipped_missing_ground_truth,
    )
