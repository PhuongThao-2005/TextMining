"""Answer generation helpers for OpenAI-compatible reasoning-capable clients."""

from .citations import (
    CITATION_CONTRACT_VERSION, CitationReference, CitationSource, CitationValidationResult,
    aggregate_citation_metrics, citation_contract_hash, format_sources_for_prompt,
    prepare_citation_sources, validate_answer_citations,
)

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
    INSUFFICIENT_CONTEXT_ANSWER,
    PROMPT_TEMPLATE_VERSION,
    PromptStrategy,
    build_generation_prompt,
    coerce_prompt_strategy,
    prompt_template_hash,
)

__all__ = [
    "CITATION_CONTRACT_VERSION", "CitationReference", "CitationSource", "CitationValidationResult",
    "aggregate_citation_metrics", "citation_contract_hash", "format_sources_for_prompt",
    "prepare_citation_sources", "validate_answer_citations",
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
    "INSUFFICIENT_CONTEXT_ANSWER",
    "PromptStrategy",
    "build_generation_prompt",
    "coerce_prompt_strategy",
    "prompt_template_hash",
]
