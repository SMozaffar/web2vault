"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate a completion given system and user prompts.

        Args:
            system_prompt: System-level instructions for the LLM.
            user_prompt: User-level content/request.
            max_output_tokens: Override the default max output tokens.

        Returns the text content of the response.
        """

    @property
    @abstractmethod
    def max_input_tokens(self) -> int:
        """Maximum input tokens supported by the model."""

    @property
    @abstractmethod
    def default_max_output_tokens(self) -> int:
        """Default maximum output tokens for this provider."""
