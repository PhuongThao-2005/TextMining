"""Deterministic prompt strategies for grounded legal-RAG answers."""
from __future__ import annotations

import hashlib
from enum import Enum


class PromptStrategy(str, Enum):
    BASE = "base"
    REASONING = "reasoning"


PROMPT_TEMPLATE_VERSION = "legal-grounded-answer-v2-citations"
INSUFFICIENT_CONTEXT_ANSWER = "Không có đủ thông tin trong ngữ cảnh được cung cấp."

_SHARED_TEMPLATE = """You are a Vietnamese legal retrieval-augmented answering system.
Use only the supplied CONTEXT. Do not invent facts outside it.
If the context is insufficient, answer exactly:
"{insufficient_context_answer}"

{strategy_instruction}

Output contract:
- Return only the final answer; never reveal hidden reasoning or chain-of-thought.
- For answer_type "boolean", the first line must be exactly "Có" or "Không";
  any explanation follows a line beginning "Giải thích:".
- For answer_type "unanswerable", return only the insufficient-context statement.
- Otherwise answer concisely in Vietnamese.
- Cite supporting context for every factual claim with only the supplied source IDs, using [1], [2], or [1][3].
- Put citations immediately after the supported claim. Never invent a source number.
- Do not add a bibliography. Cite only a source that supports the claim.

QUESTION:
{question}

ANSWER_TYPE:
{answer_type}

CONTEXT:
{context}

FINAL ANSWER:"""

_STRATEGY_INSTRUCTIONS = {
    PromptStrategy.BASE: "Answer the question directly from the context.",
    PromptStrategy.REASONING: (
        "Reason internally over the context before answering, but return only the final "
        "grounded answer in the same output format."
    ),
}


def coerce_prompt_strategy(value: PromptStrategy | str | None) -> PromptStrategy:
    """Resolve a configured strategy, defaulting old configs to the safe base prompt."""

    if value is None or value == "":
        return PromptStrategy.BASE
    if isinstance(value, PromptStrategy):
        return value
    try:
        return PromptStrategy(value)
    except ValueError as exc:
        expected = ", ".join(strategy.value for strategy in PromptStrategy)
        raise ValueError(f"Unknown prompt strategy {value!r}; expected one of: {expected}.") from exc


def build_generation_prompt(
    *,
    question: str,
    answer_type: str,
    context: str,
    strategy: PromptStrategy | str | None = None,
) -> str:
    """Build a stable prompt with shared context and output formatting."""

    selected = coerce_prompt_strategy(strategy)
    return _SHARED_TEMPLATE.format(
        insufficient_context_answer=INSUFFICIENT_CONTEXT_ANSWER,
        strategy_instruction=_STRATEGY_INSTRUCTIONS[selected],
        question=question.strip(),
        answer_type=answer_type.strip(),
        context=context.strip(),
    )


def prompt_template_hash(strategy: PromptStrategy | str | None = None) -> str:
    """Return a deterministic identity for the selected rendered template shape."""

    selected = coerce_prompt_strategy(strategy)
    template = _SHARED_TEMPLATE.format(
        insufficient_context_answer=INSUFFICIENT_CONTEXT_ANSWER,
        strategy_instruction=_STRATEGY_INSTRUCTIONS[selected],
        question="{question}",
        answer_type="{answer_type}",
        context="{context}",
    )
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


__all__ = [
    "PROMPT_TEMPLATE_VERSION",
    "INSUFFICIENT_CONTEXT_ANSWER",
    "PromptStrategy",
    "build_generation_prompt",
    "coerce_prompt_strategy",
    "prompt_template_hash",
]
