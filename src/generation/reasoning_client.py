"""OpenAI-compatible generator client with reasoning/answer parsing.

Extracted from the FAISS retrieval notebook so prompt construction and the
three-way reasoning extraction (dedicated field, <think> block, or explicit
"not returned") are unit-testable without live API calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

ANSWER_PROMPT = """Bạn là trợ lý pháp lý tiếng Việt trong hệ thống RAG.

Hãy trả lời QUESTION dựa trên CONTEXT được cung cấp.

Nguyên tắc:
- Chỉ dùng thông tin có trong CONTEXT, không dùng kiến thức bên ngoài.
- Không bịa thêm căn cứ, điều kiện, ngoại lệ hoặc số điều nếu CONTEXT không nêu.
- Nếu CONTEXT không đủ thông tin để trả lời, hãy nói: "Không có đủ thông tin trong ngữ cảnh được cung cấp."
- Nếu CONTEXT chỉ trả lời được một phần câu hỏi, hãy nói rõ phạm vi đó.

Cách trả lời:
- Trả lời tự nhiên, rõ ràng, bằng tiếng Việt có dấu.
- Ưu tiên trả lời trực tiếp trước, giải thích ngắn sau nếu cần.
- Khi có căn cứ pháp lý trong CONTEXT, hãy nêu căn cứ ở cuối câu trả lời.
- Không trình bày quá trình suy luận nội bộ.

QUESTION:
{question}

CONTEXT:
{context}

Trả lời:"""


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

    def generate(self, prompt: str, *, temperature: float = 0.0) -> RawGenerationResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
        except Exception as exc:
            # Re-raise without leaking credentials that SDKs sometimes echo.
            message = _redact_secrets(str(exc), [self._api_key])
            raise RuntimeError(f"Generator call failed: {message}") from None

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

    if field:
        return ParsedAnswer(
            answer=content.strip(),
            reasoning=field,
            reasoning_available=True,
            reasoning_source="field",
        )

    match = THINK_BLOCK_RE.search(content)
    if match:
        reasoning = match.group(1).strip()
        answer = THINK_BLOCK_RE.sub("", content).strip()
        return ParsedAnswer(
            answer=answer,
            reasoning=reasoning or None,
            reasoning_available=bool(reasoning),
            reasoning_source="think_block" if reasoning else "not_returned",
        )

    # Unterminated <think> (open without close) falls through here intentionally.
    return ParsedAnswer(
        answer=content.strip(),
        reasoning=None,
        reasoning_available=False,
        reasoning_source="not_returned",
    )


def format_context_for_prompt(chunks: Sequence[Any]) -> str:
    """Build citation-bearing CONTEXT blocks from retrieved chunks."""
    blocks: list[str] = []
    for rank, chunk in enumerate(chunks, start=1):
        citation = (
            getattr(chunk, "citation_anchor", None)
            or getattr(chunk, "citation_label", None)
            or getattr(chunk, "chunk_id", None)
            or f"chunk-{rank}"
        )
        title = getattr(chunk, "title", "") or ""
        text = getattr(chunk, "chunk_text", None)
        if text is None and isinstance(chunk, dict):
            citation = chunk.get("citation_anchor") or chunk.get("citation_label") or chunk.get("chunk_id") or citation
            title = chunk.get("title") or title
            text = chunk.get("chunk_text") or ""
        blocks.append(f"[{rank}] {citation} - {title}\n{text}")
    return "\n\n".join(blocks)


def generate_answer(
    client: GeneratorClient | None,
    query: str,
    chunks: Sequence[Any],
    *,
    qa_id: str | None = None,
    temperature: float = 0.0,
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
        prompt = ANSWER_PROMPT.format(question=query, context=context)
        raw = client.generate(prompt, temperature=temperature)
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
