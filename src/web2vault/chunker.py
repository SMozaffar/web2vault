"""Content chunking for LLM context limits.

Uses a map-reduce pattern: split on markdown heading boundaries,
process chunks independently, merge with a reduce LLM call.
"""

import re

from .utils import estimate_tokens


def split_by_headings(markdown: str, max_tokens: int) -> list[str]:
    """Split markdown into chunks at heading boundaries, each under max_tokens.

    Tries to split at ## headings first, then # headings, then by paragraphs.
    """
    if estimate_tokens(markdown) <= max_tokens:
        return [markdown]

    # Split at ## headings
    sections = re.split(r"(?=^## )", markdown, flags=re.MULTILINE)
    chunks = _merge_sections(sections, max_tokens)

    if all(estimate_tokens(c) <= max_tokens for c in chunks):
        return chunks

    # Some chunks still too large; split those at # headings
    refined = []
    for chunk in chunks:
        if estimate_tokens(chunk) > max_tokens:
            sub = re.split(r"(?=^# )", chunk, flags=re.MULTILINE)
            refined.extend(_merge_sections(sub, max_tokens))
        else:
            refined.append(chunk)

    # Last resort: split by paragraphs
    final = []
    for chunk in refined:
        if estimate_tokens(chunk) > max_tokens:
            final.extend(_split_by_paragraphs(chunk, max_tokens))
        else:
            final.append(chunk)

    return final


def _merge_sections(sections: list[str], max_tokens: int) -> list[str]:
    """Merge small adjacent sections to minimize chunk count."""
    chunks = []
    current = ""
    for section in sections:
        if not section.strip():
            continue
        combined = current + section
        if estimate_tokens(combined) <= max_tokens:
            current = combined
        else:
            if current.strip():
                chunks.append(current)
            current = section
    if current.strip():
        chunks.append(current)
    if not chunks:
        return [current] if current.strip() else []
    return chunks


def _split_by_paragraphs(text: str, max_tokens: int) -> list[str]:
    """Split text by double newlines (paragraphs)."""
    paragraphs = re.split(r"\n\n+", text)
    return _merge_sections(paragraphs, max_tokens)


def needs_chunking(content: str, max_input_tokens: int) -> bool:
    """Check whether content needs to be chunked for the LLM."""
    # Reserve tokens for system prompt + output
    available = max_input_tokens - 10_000
    return estimate_tokens(content) > available


def chunk_content(content: str, max_input_tokens: int) -> list[str]:
    """Chunk content to fit within LLM context limits."""
    available = max_input_tokens - 10_000
    if estimate_tokens(content) <= available:
        return [content]
    return split_by_headings(content, available)
