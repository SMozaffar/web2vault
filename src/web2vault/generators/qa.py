"""Q&A note generator with multi-pass prompt chaining.

Uses a 2-step process:
1. Identify all major topics and the questions to ask about each
2. Generate detailed Q&A pairs for each topic group
"""

import click

from .base import NoteGenerator


class QAGenerator(NoteGenerator):
    @property
    def note_type(self) -> str:
        return "qa"

    @property
    def filename(self) -> str:
        return "Q-and-A"

    def _system_prompt(self) -> str:
        return (
            "You are an expert educator creating comprehensive study Q&A pairs "
            "for an Obsidian vault. Generate thorough question and answer pairs "
            "that cover every important aspect of the material. Answers should be "
            "detailed and educational, not just one-line responses.\n\n"
            "Write in an objective, third-person, informational style. Do not use "
            "first-person voice, reference the author, or mirror the perspective "
            "of the original source. Present information as factual documentation.\n\n"
            "Output ONLY the markdown body (no YAML frontmatter, no top-level # title "
            "heading). Use [[wikilinks]] in answers when referencing key concepts."
        )

    def _user_prompt(self, content: str, title: str, url: str) -> str:
        # Used as fallback for chunk-based generation
        return (
            f"Create comprehensive question and answer pairs about '{title}' ({url}).\n\n"
            "Requirements:\n"
            "- Generate 25-40+ Q&A pairs covering ALL major topics and key details\n"
            "- Mix question types: factual recall, conceptual understanding, "
            "analytical/comparison, and application questions\n"
            "- Format each pair as:\n"
            "  **Q: [question]**\n\n"
            "  A: [detailed, multi-sentence answer with full explanation]\n\n"
            "- Answers should be thorough — typically 2-5 sentences with context and explanation\n"
            "- Use [[wikilinks]] in answers for important concepts, terms, and people\n"
            "- Organize by topic using ## headings for each topic group\n"
            "- Progress from foundational to more advanced questions within each group\n"
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
        """Multi-pass generation: identify topics, then generate Q&A per topic."""
        # Step 1: Identify topics and plan questions
        if verbose:
            click.echo("    Step 1/2: Identifying topics for Q&A coverage...")

        topic_plan = self._llm.generate(
            self._topic_plan_system_prompt(),
            self._topic_plan_user_prompt(content, title, url),
            max_output_tokens=3072,
        )

        # Step 2: Parse topics
        topics = self._parse_topics(topic_plan)

        if not topics:
            # Fallback to single-pass
            if verbose:
                click.echo("    Topic parsing failed, using single-pass fallback...")
            return self._llm.generate(
                self._system_prompt(),
                self._user_prompt(content, title, url),
                max_output_tokens=self._max_output_tokens,
            )

        if verbose:
            click.echo(f"    Step 2/2: Generating Q&A for {len(topics)} topics...")

        # Fit content to context window, accounting for topic/prompt overhead
        fitted_content = self._fit_content_to_context(
            content, topic_plan, "prompt overhead buffer" * 50
        )

        # Generate Q&A pairs for each topic
        all_sections = []
        for i, topic in enumerate(topics):
            if verbose:
                click.echo(
                    f"    Generating Q&A for topic {i + 1}/{len(topics)}: {topic['name']}"
                )
            section = self._llm.generate(
                self._qa_section_system_prompt(),
                self._qa_section_user_prompt(fitted_content, title, url, topic),
                max_output_tokens=self._max_output_tokens,
            )
            all_sections.append(section)

        return "\n\n".join(all_sections)

    def _topic_plan_system_prompt(self) -> str:
        return (
            "You are planning a comprehensive Q&A study document. Identify all "
            "major topics from the source material that should be covered with "
            "question-and-answer pairs.\n\n"
            "Output a numbered list of topics. For each topic, list 3-8 specific "
            "questions that should be asked. Format:\n\n"
            "1. **Topic Name**\n"
            "   - Question about aspect A\n"
            "   - Question about aspect B\n"
            "   - ...\n\n"
            "Be thorough — every important concept should be covered."
        )

    def _topic_plan_user_prompt(self, content: str, title: str, url: str) -> str:
        return (
            f"Identify all major topics from '{title}' ({url}) that should be "
            "covered in a comprehensive Q&A study document.\n\n"
            "List 5-12 distinct topics, each with 3-8 planned questions.\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    def _qa_section_system_prompt(self) -> str:
        return (
            "You are an expert educator writing Q&A pairs for one topic section "
            "of a study document in an Obsidian vault.\n\n"
            "Write in an objective, third-person, informational style. Do not "
            "reference the author or use first-person voice.\n\n"
            "Rules:\n"
            "- Start with ## heading for the topic\n"
            "- Write 5-10 detailed Q&A pairs for this topic\n"
            "- Format: **Q: [question]**\\n\\nA: [detailed answer]\n"
            "- Answers should be 2-5 sentences with full explanations\n"
            "- Use [[wikilinks]] for important concepts\n"
            "- Mix factual, conceptual, and analytical questions\n"
            "- Do NOT include YAML frontmatter or a top-level # title heading"
        )

    def _qa_section_user_prompt(
        self, content: str, title: str, url: str, topic: dict,
    ) -> str:
        return (
            f"Write Q&A pairs for the following topic from '{title}' ({url}).\n\n"
            f"TOPIC: {topic['name']}\n"
            f"Planned questions:\n{topic['questions']}\n\n"
            "Write 5-10 detailed Q&A pairs covering this topic thoroughly. "
            "Answers should be educational and complete.\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    @staticmethod
    def _parse_topics(plan: str) -> list[dict]:
        """Parse the topic plan into a list of topic dicts."""
        topics = []
        current_name = None
        current_questions = []

        for line in plan.split("\n"):
            stripped = line.strip()
            # Match numbered topic lines like "1. **Topic Name**"
            if stripped and stripped[0].isdigit() and "**" in stripped:
                if current_name:
                    topics.append({
                        "name": current_name,
                        "questions": "\n".join(current_questions),
                    })
                # Extract topic name from between ** markers
                start = stripped.find("**")
                end = stripped.find("**", start + 2)
                if start != -1 and end != -1:
                    current_name = stripped[start + 2 : end]
                else:
                    current_name = stripped.split(".", 1)[-1].strip().strip("*")
                current_questions = []
            elif current_name and stripped.startswith("-"):
                current_questions.append(stripped)

        if current_name:
            topics.append({
                "name": current_name,
                "questions": "\n".join(current_questions),
            })

        return topics
