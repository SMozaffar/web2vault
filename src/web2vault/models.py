"""Data models for web2vault."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScrapedContent:
    """Represents content scraped from a URL."""

    url: str
    title: str
    markdown: str
    metadata: dict = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.now)


@dataclass
class GeneratedNote:
    """A single generated note file."""

    filename: str
    title: str
    note_type: str  # summary, deep_dive, qa, practice, glossary, moc, raw
    content: str  # markdown body (without frontmatter)
    tags: list[str] = field(default_factory=list)


@dataclass
class NoteBundle:
    """Collection of all notes generated for a scrape."""

    source_url: str
    source_title: str
    folder_name: str
    notes: list[GeneratedNote] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)
