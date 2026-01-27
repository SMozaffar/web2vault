"""YAML frontmatter and Obsidian markdown formatting."""

from datetime import datetime
from typing import Optional

from .models import GeneratedNote


def format_frontmatter(
    note: GeneratedNote,
    source_url: str,
    folder_name: str,
    created: Optional[datetime] = None,
) -> str:
    """Generate YAML frontmatter for a note."""
    created = created or datetime.now()

    lines = [
        "---",
        f"title: \"{_escape_yaml(note.title)}\"",
        f"type: {note.note_type}",
        f"source: \"{_escape_yaml(source_url)}\"",
    ]
    if note.tags:
        lines.append("tags:")
        for tag in note.tags:
            lines.append(f"  - {tag}")
    else:
        lines.append("tags: []")
    lines.extend([
        f"created: {created.strftime('%Y-%m-%d')}",
        "---",
    ])
    return "\n".join(lines)


def format_note(
    note: GeneratedNote,
    source_url: str,
    folder_name: str,
    created: Optional[datetime] = None,
) -> str:
    """Format a complete note with frontmatter and content."""
    frontmatter = format_frontmatter(note, source_url, folder_name, created)
    heading = f"# {note.title}"
    return f"{frontmatter}\n\n{heading}\n\n{note.content}\n"


def _escape_yaml(text: str) -> str:
    """Escape special characters for YAML string values."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", " ")
    return text
