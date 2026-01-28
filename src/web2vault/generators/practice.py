"""Practice questions note generator with multi-pass prompt chaining.

Uses a 2-step process:
1. Identify topics and plan question distribution
2. Generate practice questions for each topic
"""

import re

import click

from .base import NoteGenerator


class PracticeGenerator(NoteGenerator):
    @property
    def note_type(self) -> str:
        return "practice"

    @property
    def filename(self) -> str:
        return "Practice Questions"

    def _system_prompt(self) -> str:
        return (
            "You are an expert educator creating practice quiz questions for an "
            "Obsidian vault. Generate a thorough set of practice questions with "
            "hidden answers using Obsidian callout syntax. Questions should test "
            "understanding at multiple levels: recall, comprehension, application, "
            "and analysis.\n\n"
            "Write in an objective, third-person, informational style. Do not "
            "reference the author or use first-person voice.\n\n"
            "Output ONLY the markdown body (no YAML frontmatter, no top-level # title heading)."
        ) + self._math_formatting_instructions() + self._vault_linking_instructions()

    def _user_prompt(self, content: str, title: str, url: str) -> str:
        # Used as fallback for chunk-based generation
        return (
            f"Create a comprehensive set of practice quiz questions about '{title}' ({url}).\n\n"
            "Requirements:\n"
            "- Generate 25-40 practice questions covering ALL major topics\n"
            "- Mix of question types:\n"
            "  - Multiple choice (4 options A-D)\n"
            "  - True/False with explanation\n"
            "  - Short answer requiring 2-3 sentence responses\n"
            "  - Fill-in-the-blank\n"
            "- Label each question type in bold (e.g., **Multiple Choice**, **True/False**)\n"
            "- Number all questions sequentially\n"
            "- Hide answers using Obsidian collapsed callout syntax:\n"
            "  > [!answer]- Click to reveal answer\n"
            "  > **Answer:** The answer with explanation...\n\n"
            "- Organize by topic using ## headings\n"
            "- Include questions at varying difficulty levels\n"
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
        """Multi-pass generation: plan topics then generate questions per topic."""
        # Step 1: Plan topics and question distribution
        if verbose:
            click.echo("    Step 1/2: Planning question topics and distribution...")

        plan = self._llm.generate(
            self._plan_system_prompt(),
            self._plan_user_prompt(content, title, url),
            max_output_tokens=3072,
        )

        # Step 2: Parse topic plan
        topics = self._parse_topics(plan)

        if not topics:
            if verbose:
                click.echo("    Topic parsing failed, using single-pass fallback...")
            return self._llm.generate(
                self._system_prompt(),
                self._user_prompt(content, title, url),
                max_output_tokens=self._max_output_tokens,
            )

        if verbose:
            click.echo(f"    Step 2/2: Generating questions for {len(topics)} topics...")

        # Fit content to context window, accounting for topic/prompt overhead
        fitted_content = self._fit_content_to_context(
            content, plan, "prompt overhead buffer" * 50
        )

        # Generate questions per topic
        all_sections = []
        question_number = 1
        for i, topic in enumerate(topics):
            if verbose:
                click.echo(
                    f"    Generating questions for topic {i + 1}/{len(topics)}: {topic['name']}"
                )
            section = self._llm.generate(
                self._section_system_prompt(),
                self._section_user_prompt(
                    fitted_content, title, url, topic, question_number
                ),
                max_output_tokens=self._max_output_tokens,
            )
            all_sections.append(section)
            # Estimate next starting question number
            question_number += topic.get("count", 5)

        return "\n\n".join(all_sections)

    def _plan_system_prompt(self) -> str:
        return (
            "You are planning a comprehensive practice quiz. Identify all major "
            "topics from the source material and plan how many questions of each "
            "type to create for each topic.\n\n"
            "Output a numbered list:\n"
            "1. **Topic Name** (N questions: X multiple choice, Y true/false, Z short answer)\n"
            "   - Key concept to test A\n"
            "   - Key concept to test B\n"
            "   - ...\n\n"
            "Aim for 25-40 total questions across all topics."
        )

    def _plan_user_prompt(self, content: str, title: str, url: str) -> str:
        return (
            f"Plan a comprehensive practice quiz for '{title}' ({url}).\n\n"
            "Identify 5-10 distinct topics and plan 3-8 questions per topic.\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    def _section_system_prompt(self) -> str:
        return (
            "You are an expert educator writing practice questions for one topic "
            "section of a quiz document in an Obsidian vault.\n\n"
            "Write in an objective, third-person, informational style. Do not "
            "reference the author or use first-person voice.\n\n"
            "Rules:\n"
            "- Start with ## heading for the topic\n"
            "- Number questions sequentially starting from the given number\n"
            "- Label each question type in bold\n"
            "- For multiple choice: provide 4 options (A-D)\n"
            "- For true/false: include explanation in the answer\n"
            "- For short answer: require 2-3 sentence responses\n"
            "- Hide ALL answers using Obsidian collapsed callout syntax:\n"
            "  > [!answer]- Click to reveal answer\n"
            "  > **Answer:** The answer with explanation\n\n"
            "- Do NOT include YAML frontmatter or a top-level # title heading"
        ) + self._math_formatting_instructions() + self._vault_linking_instructions()

    def _section_user_prompt(
        self,
        content: str,
        title: str,
        url: str,
        topic: dict,
        start_number: int,
    ) -> str:
        return (
            f"Write practice quiz questions for the following topic from '{title}' ({url}).\n\n"
            f"TOPIC: {topic['name']}\n"
            f"Key concepts to test:\n{topic['concepts']}\n\n"
            f"Start numbering from question {start_number}.\n"
            "Generate 4-8 questions for this topic with a mix of types.\n\n"
            "SOURCE CONTENT:\n\n"
            f"{content}"
        )

    @staticmethod
    def _parse_topics(plan: str) -> list[dict]:
        """Parse the topic plan into a list of topic dicts."""
        topics = []
        current_name = None
        current_concepts = []
        current_count = 5  # default

        for line in plan.split("\n"):
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and "**" in stripped:
                if current_name:
                    topics.append({
                        "name": current_name,
                        "concepts": "\n".join(current_concepts),
                        "count": current_count,
                    })
                start = stripped.find("**")
                end = stripped.find("**", start + 2)
                if start != -1 and end != -1:
                    current_name = stripped[start + 2 : end]
                else:
                    current_name = stripped.split(".", 1)[-1].strip().strip("*")
                # Try to extract question count from parenthetical
                count_match = re.search(r"\((\d+)\s+questions?", stripped)
                current_count = int(count_match.group(1)) if count_match else 5
                current_concepts = []
            elif current_name and stripped.startswith("-"):
                current_concepts.append(stripped)

        if current_name:
            topics.append({
                "name": current_name,
                "concepts": "\n".join(current_concepts),
                "count": current_count,
            })

        return topics
