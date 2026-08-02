"""OpenAI-compatible generator client with reasoning/answer parsing.

Provider-specific reasoning is parsed for compatibility but never included in
the final answer returned to evaluation artifacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from .prompt_strategy import PromptStrategy, build_generation_prompt
from .citations import format_sources_for_prompt, prepare_citation_sources

THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
OPEN_THINK_RE = re.compile(r"<think>", re.IGNORECASE)
CLOSE_THINK_RE = re.compile(r"</think>", re.IGNORECASE)
FINAL_ANSWER_RE = re.compile(
    r"(?:final\s+answer|answer|câu\s+trả\s+lời\s+cuối\s+cùng|trả\s+lời)\s*:\s*",
    re.IGNORECASE,
)

# Backward-compatible public constant. New code should call build_generation_prompt.
ANSWER_PROMPT = build_generation_prompt(
    question="{question}",
    answer_type="",
    context="{context}",
    strategy=PromptStrategy.BASE,
)


@dataclass(frozen=True)
class GeneratorConfig:
    base_url: str
    api_key: str
    model_name: str

    def is_complete(self) -> bool:
        return bool(self.base_url and self.api_key and self.model_name)

    def masked_key(self) -> str:
        key = self.api_key or ""
        if len(key) > 8:
            return f"{key[:4]}...{key[-4:]}"
        return "***"


@dataclass(frozen=True)
class RawGenerationResponse:
    content: str
    reasoning_field: str | None


@dataclass(frozen=True)
class ParsedAnswer:
    answer: str
    reasoning: str | None
    reasoning_available: bool
    reasoning_source: str  # "field" | "think_block" | "not_returned"


@dataclass(frozen=True)
class GenerationOutcome:
    qa_id: str | None
    parsed: ParsedAnswer | None
    skipped_empty_context: bool
    error: str | None


class GeneratorClient:
    """Thin wrapper around any OpenAI-compatible chat completions API."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        # Keep raw key only for redacting SDK errors; never log/print it.
        self.model = model
        self._base_url = base_url
        self._api_key = api_key
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package is required for GeneratorClient. Install with: pip install openai"
            ) from exc
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_output_tokens: int = 1024,
        timeout_seconds: float = 60.0,
        max_retries: int = 0,
    ) -> RawGenerationResponse:
        response: Any = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_output_tokens,
                    timeout=timeout_seconds,
                )
                break
            except Exception as exc:
                if attempt < max_retries:
                    continue
                message = _redact_secrets(str(exc), [self._api_key])
                raise RuntimeError(
                    f"Generator call failed after {attempt + 1} attempt(s): {message}"
                ) from None

        assert response is not None
        message = response.choices[0].message
        content = (getattr(message, "content", None) or "").strip()
        reasoning_field = _extract_reasoning_field(message)
        return RawGenerationResponse(content=content, reasoning_field=reasoning_field)


def _extract_reasoning_field(message: Any) -> str | None:
    for attr in ("reasoning_content", "reasoning"):
        value = getattr(message, attr, None)
        if value is None and isinstance(message, dict):
            value = message.get(attr)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _redact_secrets(text: str, secrets: Sequence[str]) -> str:
    """Best-effort redaction so exception strings never echo a raw API key."""
    redacted = text
    for secret in secrets:
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "***")
    return redacted


def parse_generation_response(raw: RawGenerationResponse) -> ParsedAnswer:
    """Split final answer from reasoning across the three supported response shapes."""
    content = raw.content or ""
    field = (raw.reasoning_field or "").strip() or None

    safe_answer, block_reasoning, had_think_block = _safe_final_answer(content)
    if field:
        return ParsedAnswer(
            answer=safe_answer,
            reasoning=field,
            reasoning_available=True,
            reasoning_source="field",
        )

    if had_think_block:
        return ParsedAnswer(
            answer=safe_answer,
            reasoning=block_reasoning,
            reasoning_available=bool(block_reasoning),
            reasoning_source="think_block" if block_reasoning else "not_returned",
        )

    return ParsedAnswer(
        answer=safe_answer,
        reasoning=None,
        reasoning_available=False,
        reasoning_source="not_returned",
    )


def _safe_final_answer(content: str) -> tuple[str, str | None, bool]:
    """Remove reasoning blocks, including safely handling malformed open tags."""

    matches = list(THINK_BLOCK_RE.finditer(content))
    reasoning = "\n".join(
        match.group(1).strip() for match in matches if match.group(1).strip()
    ) or None
    answer = THINK_BLOCK_RE.sub("", content)
    unmatched = OPEN_THINK_RE.search(answer)
    if unmatched:
        prefix = answer[: unmatched.start()].strip()
        remainder = answer[unmatched.end() :]
        marker = FINAL_ANSWER_RE.search(remainder)
        suffix = remainder[marker.end() :].strip() if marker else ""
        answer = "\n".join(part for part in (prefix, suffix) if part)
    unmatched_closes = list(CLOSE_THINK_RE.finditer(answer))
    if unmatched_closes:
        answer = answer[unmatched_closes[-1].end() :]
    answer = OPEN_THINK_RE.sub("", answer)
    answer = CLOSE_THINK_RE.sub("", answer).strip()
    return answer, reasoning, bool(matches)


def format_context_for_prompt(chunks: Sequence[Any]) -> str:
    """Build citation-bearing CONTEXT blocks from retrieved chunks."""
    return format_sources_for_prompt(prepare_citation_sources(chunks, max_text_chars=None))


def generate_answer(
    client: GeneratorClient | None,
    query: str,
    chunks: Sequence[Any],
    *,
    qa_id: str | None = None,
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_output_tokens: int = 1024,
    timeout_seconds: float = 60.0,
    max_retries: int = 0,
    answer_type: str = "",
    prompt_strategy: PromptStrategy | str | None = None,
) -> GenerationOutcome:
    """Generate a parsed answer from retrieved chunks, or record skip/error state."""
    if not chunks:
        return GenerationOutcome(
            qa_id=qa_id,
            parsed=None,
            skipped_empty_context=True,
            error=None,
        )
    if client is None:
        return GenerationOutcome(
            qa_id=qa_id,
            parsed=None,
            skipped_empty_context=False,
            error="Generator is not configured. Set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME.",
        )

    try:
        context = format_context_for_prompt(chunks)
        prompt = build_generation_prompt(
            question=query,
            answer_type=answer_type,
            context=context,
            strategy=prompt_strategy,
        )
        raw = client.generate(
            prompt,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        parsed = parse_generation_response(raw)
        return GenerationOutcome(
            qa_id=qa_id,
            parsed=parsed,
            skipped_empty_context=False,
            error=None,
        )
    except Exception as exc:
        return GenerationOutcome(
            qa_id=qa_id,
            parsed=None,
            skipped_empty_context=False,
            error=str(exc),
        )
