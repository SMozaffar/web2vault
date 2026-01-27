"""LLM provider factory."""

from ..config import Config
from .anthropic import AnthropicProvider
from .base import LLMProvider
from .openai import OpenAIProvider


def get_llm_provider(config: Config) -> LLMProvider:
    """Create and return the configured LLM provider."""
    if config.llm_provider == "claude":
        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=config.default_model,
        )
    return OpenAIProvider(
        api_key=config.openai_api_key,
        model=config.default_model,
    )
