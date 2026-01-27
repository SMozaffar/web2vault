"""Abstract base class for note generators."""

import re
from abc import ABC, abstractmethod

import click

from ..chunker import chunk_content, needs_chunking
from ..llm.base import LLMProvider
from ..models import GeneratedNote, ScrapedContent
from ..utils import estimate_tokens


class NoteGenerator(ABC):
    """Base class for all note generators.

    Subclasses must define note_type, filename, _system_prompt, and _user_prompt.
    Override _generate_body for multi-pass / prompt-chained strategies.
    """

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    @property
    @abstractmethod
    def note_type(self) -> str:
        """Identifier for this note type."""

    @property
    @abstractmethod
    def filename(self) -> str:
        """Output filename (without .md)."""

    @abstractmethod
    def _system_prompt(self) -> str:
        """System prompt for the LLM."""

    @abstractmethod
    def _user_prompt(self, content: str, title: str, url: str) -> str:
        """User prompt for the LLM."""

    @property
    def _max_output_tokens(self) -> int:
        """Max output tokens per LLM call. Override for different limits."""
        return self._llm.default_max_output_tokens

    def _reduce_system_prompt(self) -> str:
        """System prompt for merging chunked results."""
        return (
            "You are combining multiple partial note sections into a single, "
            "cohesive, comprehensive document for an Obsidian vault. "
            "Your job is to:\n"
            "1. Merge all sections into one well-structured document\n"
            "2. Remove exact duplicates but KEEP all unique information\n"
            "3. Ensure smooth transitions and logical flow between sections\n"
            "4. Maintain all markdown formatting, [[wikilinks]], and heading hierarchy\n"
            "5. Preserve the depth and detail of each section — do NOT summarize or shorten\n"
            "6. Output ONLY the final merged markdown body (no YAML frontmatter, no title heading)"
        )

    def _reduce_user_prompt(self, title: str, combined: str) -> str:
        """User prompt for merging chunked results."""
        return (
            f"Merge these partial note sections about '{title}' into one cohesive document. "
            "Keep ALL unique content from every section — do not summarize or shorten anything. "
            "Remove only exact duplicates. Maintain heading hierarchy and formatting.\n\n"
            f"{combined}"
        )

    def generate(
        self,
        scraped: ScrapedContent,
        verbose: bool = False,
        display_name: str = "",
    ) -> GeneratedNote:
        """Generate a note from scraped content, handling chunking if needed.

        Args:
            scraped: The scraped web content.
            verbose: Enable detailed progress output.
            display_name: Custom name for note titles. Falls back to scraped.title.
        """
        content = scraped.markdown
        name = display_name or scraped.title

        if needs_chunking(content, self._llm.max_input_tokens):
            body = self._generate_from_chunks(scraped, verbose)
        else:
            body = self._generate_body(
                content, scraped.title, scraped.url, verbose
            )

        body = self._clean_output(body, name)

        note_type_label = self.note_type.replace("_", " ").title()
        return GeneratedNote(
            filename=self.filename,
            title=f"{name} - {note_type_label}",
            note_type=self.note_type,
            content=body,
            tags=self._default_tags(),
        )

    def _generate_body(
        self,
        content: str,
        title: str,
        url: str,
        verbose: bool = False,
    ) -> str:
        """Generate the note body from content that fits in one context window.

        Override this method for multi-pass / prompt-chained generation strategies.
        """
        return self._llm.generate(
            self._system_prompt(),
            self._user_prompt(content, title, url),
            max_output_tokens=self._max_output_tokens,
        )

    def _generate_from_chunks(
        self,
        scraped: ScrapedContent,
        verbose: bool = False,
    ) -> str:
        """Handle large input by chunking, generating per-chunk, and reducing."""
        chunks = chunk_content(scraped.markdown, self._llm.max_input_tokens)
        if verbose:
            click.echo(f"    Content split into {len(chunks)} chunks")

        partial_results = []
        for i, chunk in enumerate(chunks):
            if verbose:
                click.echo(f"    Processing chunk {i + 1}/{len(chunks)}...")
            result = self._generate_body(
                chunk, scraped.title, scraped.url, verbose
            )
            partial_results.append(result)

        if len(partial_results) == 1:
            return partial_results[0]

        return self._reduce_results(partial_results, scraped.title, verbose)

    def _reduce_results(
        self,
        partial_results: list[str],
        title: str,
        verbose: bool = False,
    ) -> str:
        """Merge multiple partial results into one cohesive document."""
        combined = "\n\n---\n\n".join(partial_results)
        available = self._llm.max_input_tokens - 10_000

        if estimate_tokens(combined) <= available:
            if verbose:
                click.echo("    Merging all partial results...")
            return self._llm.generate(
                self._reduce_system_prompt(),
                self._reduce_user_prompt(title, combined),
                max_output_tokens=self._max_output_tokens,
            )

        # Hierarchically reduce in pairs when combined is too large
        if verbose:
            click.echo(
                f"    Hierarchically merging {len(partial_results)} results..."
            )
        while len(partial_results) > 1:
            merged = []
            for i in range(0, len(partial_results), 2):
                if i + 1 < len(partial_results):
                    pair = (
                        partial_results[i]
                        + "\n\n---\n\n"
                        + partial_results[i + 1]
                    )
                    merged.append(
                        self._llm.generate(
                            self._reduce_system_prompt(),
                            self._reduce_user_prompt(title, pair),
                            max_output_tokens=self._max_output_tokens,
                        )
                    )
                else:
                    merged.append(partial_results[i])
            partial_results = merged

        return partial_results[0]

    def _clean_output(self, text: str, title: str) -> str:
        """Sanitize LLM output: strip frontmatter, duplicate headings, etc."""
        if not text:
            return text

        # Strip leading/trailing whitespace
        text = text.strip()

        # Remove YAML frontmatter if the LLM accidentally included it
        text = re.sub(
            r"^---\s*\n.*?\n---\s*\n?",
            "",
            text,
            count=1,
            flags=re.DOTALL,
        )
        text = text.strip()

        # Remove a top-level title heading if it duplicates the note title.
        # The formatter adds its own # heading, so a duplicate would appear twice.
        # Only match exactly one '#' (level-1 heading), not ## or deeper.
        h1_match = re.match(r"^(#)\s+(.+)", text)
        if h1_match and len(h1_match.group(1)) == 1:
            heading_text = h1_match.group(2).strip()
            title_normalized = title.lower().strip()
            heading_normalized = heading_text.lower().strip()
            if (
                heading_normalized == title_normalized
                or title_normalized.startswith(heading_normalized)
                or heading_normalized.startswith(title_normalized)
                or self.note_type in heading_normalized
            ):
                first_line_end = text.find("\n")
                text = text[first_line_end + 1 :].strip() if first_line_end != -1 else ""

        # Collapse 3+ consecutive blank lines into 2
        text = re.sub(r"\n{4,}", "\n\n\n", text)

        # Remove trailing whitespace on each line
        text = "\n".join(line.rstrip() for line in text.split("\n"))

        return text.strip()

    def _fit_content_to_context(
        self, content: str, *other_parts: str
    ) -> str:
        """Truncate content so that content + other_parts fit in the context window.

        Used by multi-pass generators where each LLM call includes the source
        content plus additional context (outline, section info, etc.). Ensures
        the combined prompt won't exceed the model's input limit.
        """
        # Reserve tokens for system prompt and output generation
        overhead = 10_000
        other_tokens = sum(estimate_tokens(p) for p in other_parts)
        available = self._llm.max_input_tokens - overhead - other_tokens

        if available <= 0:
            available = 10_000  # minimum floor

        content_tokens = estimate_tokens(content)
        if content_tokens <= available:
            return content

        # Truncate content to fit (approximate: 4 chars per token)
        max_chars = available * 4
        truncated = content[:max_chars]
        # Try to cut at a paragraph boundary
        last_para = truncated.rfind("\n\n")
        if last_para > max_chars // 2:
            truncated = truncated[:last_para]
        return truncated + "\n\n[Content truncated to fit context window]"

    def _default_tags(self) -> list[str]:
        return ["web2vault", self.note_type]
