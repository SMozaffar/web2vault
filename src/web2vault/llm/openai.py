"""OpenAI LLM provider."""

import time
from typing import Optional

import openai

from ..exceptions import LLMError
from .base import LLMProvider

_DEFAULT_MAX_OUTPUT = 16_384


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._max_output = _DEFAULT_MAX_OUTPUT
        # Newer models (o1, o3, gpt-4.1, gpt-5, etc.) require
        # max_completion_tokens instead of max_tokens. We auto-detect
        # on the first call and cache the result.
        self._use_max_completion_tokens = not self._is_legacy_model(model)

    @property
    def max_input_tokens(self) -> int:
        if "gpt-4o" in self._model:
            return 120_000
        if "gpt-3.5" in self._model:
            return 14_000
        # Newer models (gpt-4.1, gpt-5, o-series) generally have large contexts
        return 120_000

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
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        last_error = None
        for attempt in range(3):
            try:
                response = self._call_api(tokens, messages)
                return response.choices[0].message.content or ""
            except openai.RateLimitError as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
            except openai.APIError as e:
                raise LLMError(f"OpenAI API error: {e}") from e
        raise LLMError(f"Rate limited after 3 attempts: {last_error}")

    def _call_api(self, tokens: int, messages: list):
        """Call the OpenAI API, auto-detecting max_tokens vs max_completion_tokens."""
        token_param = (
            "max_completion_tokens"
            if self._use_max_completion_tokens
            else "max_tokens"
        )
        try:
            return self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **{token_param: tokens},
            )
        except openai.BadRequestError as e:
            # If the parameter is unsupported, toggle and retry once
            if "unsupported_parameter" in str(e).lower() or "Unsupported parameter" in str(e):
                self._use_max_completion_tokens = not self._use_max_completion_tokens
                alt_param = (
                    "max_completion_tokens"
                    if self._use_max_completion_tokens
                    else "max_tokens"
                )
                return self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    **{alt_param: tokens},
                )
            raise

    @staticmethod
    def _is_legacy_model(model: str) -> bool:
        """Check if the model uses the legacy max_tokens parameter."""
        legacy_prefixes = ("gpt-3.5", "gpt-4o", "gpt-4-turbo", "gpt-4-")
        return any(model.startswith(p) for p in legacy_prefixes)
