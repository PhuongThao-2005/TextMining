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
from .prompt_strategy import (
    PROMPT_TEMPLATE_VERSION,
    PromptStrategy,
    build_generation_prompt,
    coerce_prompt_strategy,
    prompt_template_hash,
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
    "PROMPT_TEMPLATE_VERSION",
    "PromptStrategy",
    "build_generation_prompt",
    "coerce_prompt_strategy",
    "prompt_template_hash",
]
