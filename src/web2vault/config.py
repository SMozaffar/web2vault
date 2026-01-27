"""Configuration loading and validation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .exceptions import ConfigError


@dataclass
class Config:
    """Application configuration."""

    firecrawl_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    vault_path: Path = field(default_factory=lambda: Path.cwd() / "vault_output")
    llm_provider: str = "claude"
    model: str = ""
    crawl_depth: int = 0
    max_pages: int = 1
    verbose: bool = False

    @property
    def default_model(self) -> str:
        if self.model:
            return self.model
        if self.llm_provider == "claude":
            return "claude-sonnet-4-20250514"
        return "gpt-4o"

    def validate(self) -> None:
        """Validate required configuration."""
        if not self.firecrawl_api_key:
            raise ConfigError(
                "FIRECRAWL_API_KEY is required. Set it in .env or environment."
            )
        if self.llm_provider == "claude" and not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is required when using Claude provider."
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ConfigError(
                "OPENAI_API_KEY is required when using OpenAI provider."
            )
        if self.llm_provider not in ("claude", "openai"):
            raise ConfigError(
                f"Unknown LLM provider: {self.llm_provider}. Use 'claude' or 'openai'."
            )
        if self.crawl_depth < 0:
            raise ConfigError("crawl_depth cannot be negative.")
        if self.max_pages < 1:
            raise ConfigError("max_pages must be at least 1.")


def load_config(
    vault_path: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    crawl_depth: Optional[int] = None,
    max_pages: Optional[int] = None,
    verbose: bool = False,
) -> Config:
    """Load config from .env and apply CLI overrides."""
    load_dotenv()

    config = Config(
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        vault_path=Path(vault_path) if vault_path else Path(
            os.getenv("OBSIDIAN_VAULT_PATH", str(Path.cwd() / "vault_output"))
        ),
        llm_provider=provider or os.getenv("LLM_PROVIDER", "claude"),
        model=model or "",
        crawl_depth=crawl_depth if crawl_depth is not None else 0,
        max_pages=max_pages if max_pages is not None else 1,
        verbose=verbose,
    )

    config.validate()
    return config
