"""Custom exceptions for web2vault."""


class Web2VaultError(Exception):
    """Base exception for web2vault."""


class ConfigError(Web2VaultError):
    """Raised when configuration is missing or invalid."""


class CrawlError(Web2VaultError):
    """Raised when web scraping/crawling fails."""


class LLMError(Web2VaultError):
    """Raised when LLM API calls fail."""


class ChunkingError(Web2VaultError):
    """Raised when content chunking fails."""
