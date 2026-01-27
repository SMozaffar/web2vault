"""Deep dive note generator with multi-pass prompt chaining.

Uses a 3-step process:
1. Generate a detailed outline of all sections/subsections
2. Expand each major section independently with full detail
3. Assemble into one comprehensive document
"""

import click

from .base import NoteGenerator


class DeepDiveGenerator(NoteGenerator):
    @property
    def note_type(self) -> str:
        return "deep_dive"

    @property
    def filename(self) -> str:
        return "Deep Dive"

    def _system_prompt(self) -> str:
        return (
            "You are an expert educator creating comprehensive, in-depth study notes "
            "for an Obsidian vault. Your notes should be thorough enough to serve as "
            "a standalone study resource — the reader should not need to visit the "
            "original source.\n\n"
            "Write in an objective, third-person, informational style. Do not use "
            "first-person voice, reference the author or their opinions, or mirror "
            "the perspective of the original source. Present all information as "
            "factual, standalone documentation.\n\n"
            "Output ONLY the markdown body (no YAML frontmatter, "
            "no top-level # title heading). Use [[wikilinks]] for cross-references "
            "to concepts that could be their own note."
        )

    def _user_prompt(self, content: str, title: str, url: str) -> str:
        # Used as fallback for chunk-based generation
        return (
            f"Create a comprehensive, in-depth study document on '{title}' ({url}).\n\n"
            "Requirements:\n"
            "- Cover EVERY major topic, subtopic, and detail from the source material\n"
            "- Use ## headings for major sections and ### for subsections\n"
            "- Explain each concept thoroughly with full context, background, and connections\n"
            "- Include specific details: names, dates, numbers, examples, and evidence\n"
            "- Draw connections between different topics and ideas\n"
            "- Use [[wikilinks]] for important terms, people, and related concepts\n"
            "- Use bullet points, numbered lists, and block quotes where appropriate\n"
            "- Include a ## Connections & Implications section at the end\n"
            "- Be EXHAUSTIVE — leave nothing out. This should be a complete reference\n"
            "- Do NOT include YAML frontmatter or a top-level # title heading\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    def _generate_body(
        self,
        content: str,
        title: str,
        url: str,
        verbose: bool = False,
    ) -> str:
        """Multi-pass prompt-chained generation for comprehensive deep dives."""
        # Step 1: Generate a detailed outline
        if verbose:
            click.echo("    Step 1/3: Generating detailed outline...")

        outline = self._llm.generate(
            self._outline_system_prompt(),
            self._outline_user_prompt(content, title, url),
            max_output_tokens=4096,
        )

        # Step 2: Parse sections from outline
        sections = self._parse_outline_sections(outline)

        if not sections:
            # Fallback: if outline parsing fails, do a single comprehensive pass
            if verbose:
                click.echo("    Outline parsing failed, using single-pass fallback...")
            return self._llm.generate(
                self._system_prompt(),
                self._user_prompt(content, title, url),
                max_output_tokens=self._max_output_tokens,
            )

        if verbose:
            click.echo(f"    Step 2/3: Expanding {len(sections)} sections...")

        # Step 3: Expand each section with full detail
        # Fit content to context window, accounting for outline + section overhead
        fitted_content = self._fit_content_to_context(
            content, outline, "prompt overhead buffer" * 50
        )

        expanded_sections = []
        for i, section in enumerate(sections):
            if verbose:
                click.echo(
                    f"    Expanding section {i + 1}/{len(sections)}: {section['heading']}"
                )
            section_content = self._llm.generate(
                self._expand_system_prompt(),
                self._expand_user_prompt(
                    fitted_content, title, url, section, outline
                ),
                max_output_tokens=self._max_output_tokens,
            )
            expanded_sections.append(section_content)

        if verbose:
            click.echo("    Step 3/3: Assembling final document...")

        # Assemble all sections
        return "\n\n".join(expanded_sections)

    def _outline_system_prompt(self) -> str:
        return (
            "You are an expert educator planning a comprehensive study document. "
            "Your task is to create a DETAILED hierarchical outline that identifies "
            "every major topic, subtopic, and key point from the source material. "
            "This outline will be used to generate full content for each section, "
            "so be thorough in identifying what should be covered.\n\n"
            "Output the outline using markdown heading syntax:\n"
            "- ## for major sections\n"
            "- ### for subsections\n"
            "- Bullet points under each heading listing the key points to cover\n\n"
            "Do NOT write full prose — just headings and bullet points."
        )

    def _outline_user_prompt(self, content: str, title: str, url: str) -> str:
        return (
            f"Create a detailed outline for a comprehensive study document about "
            f"'{title}' ({url}).\n\n"
            "Requirements:\n"
            "- Identify EVERY major topic and subtopic from the content\n"
            "- Use ## for major sections (aim for 4-10 major sections)\n"
            "- Use ### for subsections within each major section\n"
            "- Under each heading, list bullet points of key details to cover\n"
            "- Include sections for: background/context, main topics, "
            "connections between ideas, and implications/significance\n"
            "- Order sections logically for a reader learning this material\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    def _expand_system_prompt(self) -> str:
        return (
            "You are an expert educator writing one section of a comprehensive "
            "study document for an Obsidian vault. Write this section with full "
            "depth and detail — the reader should gain thorough understanding "
            "from your writing alone.\n\n"
            "Write in an objective, third-person, informational style. Do not use "
            "first-person voice, reference the author, or mirror the perspective "
            "of the original source. Present information as factual documentation.\n\n"
            "Rules:\n"
            "- Write comprehensive prose with full explanations\n"
            "- Include specific details: names, dates, numbers, examples\n"
            "- Use [[wikilinks]] for important terms and concepts\n"
            "- Use ### subheadings to organize content within the section\n"
            "- Use bullet points, numbered lists, and block quotes where appropriate\n"
            "- Be thorough — do not summarize or abbreviate\n"
            "- Output ONLY this section's content (keep the ## heading)\n"
            "- Do NOT include YAML frontmatter or a top-level # title heading"
        )

    def _expand_user_prompt(
        self,
        content: str,
        title: str,
        url: str,
        section: dict,
        full_outline: str,
    ) -> str:
        return (
            f"Write the following section of a comprehensive study document about "
            f"'{title}' ({url}).\n\n"
            f"SECTION TO WRITE:\n{section['heading']}\n"
            f"Key points to cover:\n{section['points']}\n\n"
            f"FULL DOCUMENT OUTLINE (for context on how this section fits):\n"
            f"{full_outline}\n\n"
            "Write this section with complete depth and detail. Include all "
            "relevant information from the source material below. Do not just "
            "summarize — explain thoroughly.\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    @staticmethod
    def _parse_outline_sections(outline: str) -> list[dict]:
        """Parse an outline into sections with headings and bullet points."""
        sections = []
        current_heading = None
        current_points = []

        for line in outline.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## ") and not stripped.startswith("### "):
                # Save previous section
                if current_heading:
                    sections.append({
                        "heading": current_heading,
                        "points": "\n".join(current_points),
                    })
                current_heading = stripped
                current_points = []
            elif current_heading:
                # Accumulate everything under the current section
                if stripped:
                    current_points.append(line)

        # Don't forget the last section
        if current_heading:
            sections.append({
                "heading": current_heading,
                "points": "\n".join(current_points),
            })

        return sections
