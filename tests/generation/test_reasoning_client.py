"""Unit tests for reasoning-capable generation client (no live network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from generation.reasoning_client import (
    ANSWER_PROMPT,
    GenerationOutcome,
    GeneratorClient,
    GeneratorConfig,
    ParsedAnswer,
    RawGenerationResponse,
    format_context_for_prompt,
    generate_answer,
    parse_generation_response,
)


def test_masked_key_never_leaks_raw_value() -> None:
    long_cfg = GeneratorConfig(
        base_url="https://example.com/v1",
        api_key="sk-abcdefghijklmnop",
        model_name="m",
    )
    short_cfg = GeneratorConfig(base_url="x", api_key="short", model_name="m")
    empty_cfg = GeneratorConfig(base_url="", api_key="", model_name="")

    assert long_cfg.masked_key() == "sk-a...mnop"
    assert "abcdefghijklmnop" not in long_cfg.masked_key()
    assert short_cfg.masked_key() == "***"
    assert empty_cfg.masked_key() == "***"
    assert long_cfg.is_complete() is True
    assert empty_cfg.is_complete() is False
    assert GeneratorConfig("u", "k", "").is_complete() is False


def test_parse_generation_response_from_field() -> None:
    raw = RawGenerationResponse(
        content="Final answer text",
        reasoning_field="Step-by-step reasoning here",
    )
    parsed = parse_generation_response(raw)
    assert parsed == ParsedAnswer(
        answer="Final answer text",
        reasoning="Step-by-step reasoning here",
        reasoning_available=True,
        reasoning_source="field",
    )


def test_parse_generation_response_from_think_block() -> None:
    content = (
        "<think>\nI compare articles 35 and 36.\n</think>\n"
        "Người lao động có quyền đơn phương chấm dứt hợp đồng."
    )
    raw = RawGenerationResponse(content=content, reasoning_field=None)
    parsed = parse_generation_response(raw)
    assert parsed.reasoning_source == "think_block"
    assert parsed.reasoning_available is True
    assert parsed.reasoning == "I compare articles 35 and 36."
    assert "think" not in parsed.answer.lower()
    assert "Người lao động" in parsed.answer


def test_parse_generation_response_not_returned() -> None:
    raw = RawGenerationResponse(content="Bare answer only.", reasoning_field=None)
    parsed = parse_generation_response(raw)
    assert parsed == ParsedAnswer(
        answer="Bare answer only.",
        reasoning=None,
        reasoning_available=False,
        reasoning_source="not_returned",
    )


def test_parse_generation_response_unterminated_think_tag() -> None:
    raw = RawGenerationResponse(
        content="<think>I started reasoning but never closed it\nStill more text",
        reasoning_field=None,
    )
    parsed = parse_generation_response(raw)
    assert parsed.reasoning_source == "not_returned"
    assert parsed.reasoning is None
    assert parsed.reasoning_available is False
    assert parsed.answer.startswith("<think>")


def test_format_context_and_prompt_include_reasoning_instruction() -> None:
    chunk = SimpleNamespace(
        chunk_id="c1",
        citation_anchor="Điều 35",
        citation_label=None,
        title="Bộ luật Lao động",
        chunk_text="Nội dung điều 35...",
    )
    context = format_context_for_prompt([chunk])
    assert "Điều 35" in context
    assert "Bộ luật Lao động" in context
    assert "Nội dung điều 35" in context

    prompt = ANSWER_PROMPT.format(question="Câu hỏi?", context=context)
    assert "suy luận" in prompt.lower() or "reasoning" in prompt.lower()
    assert "CONTEXT" in prompt
    assert "Câu hỏi?" in prompt


class _FakeCompletions:
    def __init__(self, message: SimpleNamespace) -> None:
        self._message = message

    def create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=self._message)])


class _FakeChat:
    def __init__(self, message: SimpleNamespace) -> None:
        self.completions = _FakeCompletions(message)


class _FakeOpenAI:
    def __init__(self, message: SimpleNamespace) -> None:
        self.chat = _FakeChat(message)


def test_generator_client_maps_reasoning_field(monkeypatch: pytest.MonkeyPatch) -> None:
    message = SimpleNamespace(
        content="  Answer body  ",
        reasoning_content="  Why this answer  ",
    )

    import generation.reasoning_client as mod

    class _OpenAI:
        def __init__(self, **kwargs):
            self.chat = _FakeChat(message)

    monkeypatch.setattr(mod, "OpenAI", _OpenAI, raising=False)
    # Bypass import inside __init__ by injecting after construction carefully.
    client = object.__new__(GeneratorClient)
    client.model = "test-model"
    client._base_url = "https://example.com/v1"
    client._api_key = "sk-secret-key-value"
    client.client = _FakeOpenAI(message)

    raw = GeneratorClient.generate(client, "prompt")
    assert raw.content == "Answer body"
    assert raw.reasoning_field == "Why this answer"


def test_generate_answer_skips_empty_context() -> None:
    outcome = generate_answer(client=None, query="q", chunks=[], qa_id="qa-1")
    assert outcome == GenerationOutcome(
        qa_id="qa-1",
        parsed=None,
        skipped_empty_context=True,
        error=None,
    )


def test_generate_answer_records_error_without_raw_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BoomClient:
        model = "m"
        _api_key = "sk-super-secret-key"

        def generate(self, prompt: str, *, temperature: float = 0.0):
            raise RuntimeError(f"auth failed for key sk-super-secret-key")

    chunk = SimpleNamespace(
        chunk_id="c1",
        citation_anchor="A1",
        citation_label=None,
        title="T",
        chunk_text="text",
    )
    # Patch generate_answer path through a client that raises with raw key; our
    # generate_answer wraps generic exceptions as error strings. Ensure redaction
    # happens inside GeneratorClient.generate instead.
    import generation.reasoning_client as mod

    client = object.__new__(GeneratorClient)
    client.model = "m"
    client._base_url = "https://example.com"
    client._api_key = "sk-super-secret-key"

    class _BoomCompletions:
        def create(self, **kwargs):
            raise RuntimeError("401 unauthorized sk-super-secret-key")

    client.client = SimpleNamespace(chat=SimpleNamespace(completions=_BoomCompletions()))

    with pytest.raises(RuntimeError) as excinfo:
        client.generate("prompt")
    assert "sk-super-secret-key" not in str(excinfo.value)
    assert "***" in str(excinfo.value)

    outcome = generate_answer(client, "q", [chunk], qa_id="qa-2")
    assert outcome.skipped_empty_context is False
    assert outcome.parsed is None
    assert outcome.error is not None
    assert "sk-super-secret-key" not in outcome.error
