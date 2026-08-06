from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any


_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: Any) -> str:
    text = "" if text is None else str(text)
    text = unicodedata.normalize("NFC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def tokenize(text: Any) -> list[str]:
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


def exact_match(prediction: str, reference: str) -> float:
    return 1.0 if normalize_text(prediction) == normalize_text(reference) else 0.0


def token_f1(prediction: str, reference: str) -> float:
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0
    overlap = Counter(pred_tokens) & Counter(ref_tokens)
    common = sum(overlap.values())
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def rouge_l(prediction: str, reference: str) -> float:
    pred_tokens = tokenize(prediction)
    ref_tokens = tokenize(reference)
    if not pred_tokens and not ref_tokens:
        return 1.0
    if not pred_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_len(pred_tokens, ref_tokens)
    precision = lcs / len(pred_tokens)
    recall = lcs / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _lcs_len(a: list[str], b: list[str]) -> int:
    prev = [0] * (len(b) + 1)
    for token_a in a:
        curr = [0]
        for j, token_b in enumerate(b, start=1):
            curr.append(prev[j - 1] + 1 if token_a == token_b else max(prev[j], curr[-1]))
        prev = curr
    return prev[-1]


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)


def hit_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    return 1.0 if relevant_ids and set(retrieved_ids[:k]) & relevant_ids else 0.0


def mrr_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    for index, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in relevant_ids:
            return 1.0 / index
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    dcg = 0.0
    for index, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in relevant_ids:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant_ids), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def jaccard_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    retrieved = set(retrieved_ids[:k])
    union = retrieved | relevant_ids
    if not union:
        return 0.0
    return len(retrieved & relevant_ids) / len(union)


def aggregate(rows: list[dict[str, Any]], metric_keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows)}
    denominators: dict[str, int] = {}
    for key in metric_keys:
        values = [
            float(row[key])
            for row in rows
            if row.get(key) is not None
        ]
        denominators[key] = len(values)
        out[key] = sum(values) / len(values) if values else 0.0
    out["metric_denominators"] = denominators
    return out


def aggregate_by(rows: list[dict[str, Any]], field: str, metric_keys: list[str]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "unknown")].append(row)
    return {name: aggregate(group, metric_keys) for name, group in sorted(groups.items())}


def is_unanswerable_text(text: str) -> bool:
    norm = normalize_text(text)
    markers = [
        "không có đủ thông tin",
        "không đủ thông tin",
        "không đủ căn cứ",
        "không tìm thấy",
        "không có thông tin",
        "khong co du thong tin",
        "khong du thong tin",
        "khong du can cu",
        "khong duoc neu",
        "khong tim thay",
        "khong co thong tin",
    ]
    return any(marker in norm for marker in markers)

