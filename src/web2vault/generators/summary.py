"""Summary note generator."""

from .base import NoteGenerator


class SummaryGenerator(NoteGenerator):
    @property
    def note_type(self) -> str:
        return "summary"

    @property
    def filename(self) -> str:
        return "Summary"

    def _system_prompt(self) -> str:
        return (
            "You are an expert note-taker creating detailed study notes for an "
            "Obsidian vault. Generate a thorough, well-structured summary that "
            "captures the essential information from the provided web content. "
            "The summary should be comprehensive enough that a reader understands "
            "the full scope of the material without visiting the source.\n\n"
            "Write in an objective, third-person, informational style. Do not use "
            "first-person voice, reference the author or their opinions, or mirror "
            "the perspective of the original source. Present all information as "
            "factual, standalone documentation.\n\n"
            "Output ONLY the markdown body (no YAML frontmatter, no top-level # title "
            "heading)."
        ) + self._math_formatting_instructions() + self._vault_linking_instructions()

    def _user_prompt(self, content: str, title: str, url: str) -> str:
        return (
            f"Create a detailed summary of the following content from '{title}' ({url}).\n\n"
            "Requirements:\n"
            "- Write a thorough overview that covers ALL major points from the content\n"
            "- Use ## headings to organize the summary into logical sections\n"
            "- Each section should have multiple well-developed paragraphs\n"
            "- Include specific details, examples, and key facts — not just vague generalities\n"
            "- Write in clear, accessible language suitable for study notes\n"
            "- End with a '## Key Takeaways' section with 8-15 bullet points covering "
            "the most important insights\n"
            "- Be thorough — this should be a substantive summary, not a brief abstract\n"
            "- Do NOT include YAML frontmatter or a top-level # title heading\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )
