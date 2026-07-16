from evaluation.eligibility import select_eligible_cases


def _row(qa_id, question="q", category=None, answer_type=None, chunk_ids=None, document_ids=None, provision_ids=None):
    return {
        "qa_id": qa_id,
        "question": question,
        "category": category,
        "answer_type": answer_type,
        "ground_truth": {
            "chunk_ids": chunk_ids or [],
            "document_ids": document_ids or [],
            "provision_ids": provision_ids or [],
        },
    }


def test_unanswerable_rows_are_skipped_and_not_scored():
    rows = [
        _row("qa-1", answer_type="unanswerable"),
        _row("qa-2", category="unanswerable"),
        _row("qa-3", chunk_ids=["c1"]),
    ]

    summary = select_eligible_cases(rows, sample_limit=None)

    assert summary.skipped_unanswerable == 2
    assert summary.skipped_missing_ground_truth == 0
    assert len(summary.eligible) == 1
    assert summary.eligible[0].qa_id == "qa-3"


def test_missing_ground_truth_chunk_ids_are_skipped():
    rows = [
        _row("qa-1", chunk_ids=[]),
        _row("qa-2", chunk_ids=["c1"]),
    ]

    summary = select_eligible_cases(rows, sample_limit=None)

    assert summary.skipped_missing_ground_truth == 1
    assert len(summary.eligible) == 1
    assert summary.eligible[0].qa_id == "qa-2"


def test_sample_limit_truncates_eligible_cases():
    rows = [_row(f"qa-{i}", chunk_ids=[f"c{i}"]) for i in range(5)]

    summary = select_eligible_cases(rows, sample_limit=2)

    assert len(summary.eligible) == 2
    assert summary.total_rows == 2


def test_every_row_is_classified_exactly_once():
    rows = [
        _row("qa-1", answer_type="unanswerable"),
        _row("qa-2", chunk_ids=[]),
        _row("qa-3", chunk_ids=["c1"]),
        _row("qa-4", chunk_ids=["c2"]),
    ]

    summary = select_eligible_cases(rows, sample_limit=None)

    assert summary.total_rows == len(rows)
    assert summary.total_rows == (
        len(summary.eligible) + summary.skipped_unanswerable + summary.skipped_missing_ground_truth
    )


def test_eligible_case_carries_ground_truth_sets():
    rows = [
        _row(
            "qa-1",
            chunk_ids=["c1", "c2"],
            document_ids=["d1"],
            provision_ids=["p1"],
        )
    ]

    summary = select_eligible_cases(rows, sample_limit=None)

    case = summary.eligible[0]
    assert case.ground_truth_chunk_ids == {"c1", "c2"}
    assert case.ground_truth_document_ids == {"d1"}
    assert case.ground_truth_provision_ids == {"p1"}
