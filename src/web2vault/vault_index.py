"""Vault index scanner for cross-linking existing notes.

Scans all .md files in an Obsidian vault directory, extracts note titles,
headings, and tags, and formats them as context for LLM prompt injection
so generators can create [[wikilinks]] to existing notes.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VaultNote:
    """A single note found in the vault."""

    title: str
    folder: str
    headings: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class VaultIndex:
    """Index of existing vault notes for cross-linking."""

    def __init__(self, notes: list[VaultNote] | None = None):
        self.notes: list[VaultNote] = notes or []

    @classmethod
    def scan(cls, vault_path: Path, exclude_folder: str = "") -> "VaultIndex":
        """Scan all .md files in vault_path and build an index.

        Args:
            vault_path: Root directory of the Obsidian vault.
            exclude_folder: Folder name to skip (e.g. the current run's output).

        Returns:
            A VaultIndex containing all discovered notes.
        """
        notes: list[VaultNote] = []
        vault_path = Path(vault_path)

        if not vault_path.is_dir():
            return cls(notes)

        for md_file in vault_path.rglob("*.md"):
            # Skip files inside the exclude folder
            if exclude_folder:
                try:
                    md_file.relative_to(vault_path / exclude_folder)
                    # If relative_to succeeds, the file is inside exclude_folder
                    continue
                except ValueError:
                    pass

            note = _parse_note(md_file, vault_path)
            if note:
                notes.append(note)

        return cls(notes)

    def format_for_prompt(self) -> str:
        """Format the index as compact text for LLM prompt injection.

        Returns:
            A string listing all notes with their topics, or empty string
            if no notes exist.
        """
        if not self.notes:
            return ""

        lines = []
        for note in self.notes:
            line = f"- [[{note.title}]]"
            if note.headings:
                topics = ", ".join(note.headings)
                line += f" — Topics: {topics}"
            lines.append(line)

        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.notes)


def _parse_note(md_file: Path, vault_root: Path) -> VaultNote | None:
    """Parse a single markdown file into a VaultNote.

    Extracts title from YAML frontmatter or first # heading (falls back to
    filename), ## headings as topics, and tags from frontmatter.
    """
    try:
        text = md_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    folder = str(md_file.parent.relative_to(vault_root))
    title = None
    tags: list[str] = []

    # Parse YAML frontmatter (between --- markers)
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        # Extract title
        title_match = re.search(r"^title:\s*(.+)$", frontmatter, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip().strip("\"'")

        # Extract tags (supports both list and inline formats)
        tags_match = re.search(
            r"^tags:\s*\[(.+?)\]", frontmatter, re.MULTILINE
        )
        if tags_match:
            tags = [t.strip().strip("\"'") for t in tags_match.group(1).split(",")]
        else:
            # YAML list format: tags:\n  - tag1\n  - tag2
            tags_block = re.search(
                r"^tags:\s*\n((?:\s+-\s+.+\n?)+)", frontmatter, re.MULTILINE
            )
            if tags_block:
                tags = [
                    line.strip().removeprefix("- ").strip().strip("\"'")
                    for line in tags_block.group(1).strip().split("\n")
                    if line.strip()
                ]

    # Fallback title: first # heading
    if not title:
        h1_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()

    # Fallback title: filename without extension
    if not title:
        title = md_file.stem

    # Extract ## headings as topics
    headings = re.findall(r"^##\s+(.+)$", text, re.MULTILINE)
    headings = [h.strip() for h in headings]

    return VaultNote(
        title=title,
        folder=folder,
        headings=headings,
        tags=tags,
    )
