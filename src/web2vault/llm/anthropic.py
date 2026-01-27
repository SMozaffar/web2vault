"""Claude/Anthropic LLM provider."""

import time
from typing import Optional

import anthropic

from ..exceptions import LLMError
from .base import LLMProvider

# Max output tokens by model family
_MODEL_MAX_OUTPUT = {
    "claude-sonnet-4": 16_384,
    "claude-opus-4": 16_384,
    "claude-3-5-sonnet": 8_192,
    "claude-3-5-haiku": 8_192,
}

_DEFAULT_MAX_OUTPUT = 16_384


def _get_model_max_output(model: str) -> int:
    """Determine max output tokens for a given model string."""
    for prefix, limit in _MODEL_MAX_OUTPUT.items():
        if model.startswith(prefix):
            return limit
    return _DEFAULT_MAX_OUTPUT


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_output = _get_model_max_output(model)

    @property
    def max_input_tokens(self) -> int:
        return 180_000

    @property
    def default_max_output_tokens(self) -> int:
        return self._max_output

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        tokens = min(
            max_output_tokens or self._max_output,
            self._max_output,
        )
        last_error = None
        for attempt in range(3):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return response.content[0].text
            except anthropic.RateLimitError as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
            except anthropic.APIError as e:
                raise LLMError(f"Anthropic API error: {e}") from e
        raise LLMError(f"Rate limited after 3 attempts: {last_error}")
