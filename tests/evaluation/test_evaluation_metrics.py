from evaluation.metrics import (
    aggregate,
    exact_match,
    hit_at_k,
    jaccard_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
    rouge_l,
    token_f1,
)


def test_retrieval_metrics_ranked_ids():
    retrieved = ["c3", "c1", "c2", "c4"]
    relevant = {"c1", "c2"}

    assert recall_at_k(retrieved, relevant, 1) == 0.0
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert hit_at_k(retrieved, relevant, 2) == 1.0
    assert mrr_at_k(retrieved, relevant, 10) == 0.5
    assert 0.0 < ndcg_at_k(retrieved, relevant, 3) < 1.0
    assert jaccard_at_k(retrieved, relevant, 3) == 2 / 3


def test_answer_metrics_vietnamese_normalization():
    assert exact_match("Có.", "có") == 1.0
    assert token_f1("người lao động được nghỉ hằng tuần", "lao động nghỉ hằng tuần") > 0.7
    assert rouge_l("quy định về xử phạt hành chính", "xử phạt hành chính") > 0.7


def test_aggregate_skips_non_applicable_metric_values():
    rows = [{"recall@5": 1.0}, {"recall@5": None}, {}]

    summary = aggregate(rows, ["recall@5"])

    assert summary["count"] == 3
    assert summary["recall@5"] == 1.0
    assert summary["metric_denominators"]["recall@5"] == 1

