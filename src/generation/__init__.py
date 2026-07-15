"""Answer generation helpers for OpenAI-compatible reasoning-capable clients."""

from .reasoning_client import (
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

__all__ = [
    "ANSWER_PROMPT",
    "GenerationOutcome",
    "GeneratorClient",
    "GeneratorConfig",
    "ParsedAnswer",
    "RawGenerationResponse",
    "format_context_for_prompt",
    "generate_answer",
    "parse_generation_response",
]
