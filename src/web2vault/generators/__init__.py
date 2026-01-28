"""Generator registry and orchestrator."""

from typing import Optional

import click

from ..llm.base import LLMProvider
from ..models import GeneratedNote, NoteBundle, ScrapedContent
from ..utils import derive_folder_name
from .deep_dive import DeepDiveGenerator
from .practice import PracticeGenerator
from .qa import QAGenerator
from .summary import SummaryGenerator


def _make_raw_note(scraped: ScrapedContent, display_name: str) -> GeneratedNote:
    """Create the raw scraped content note (no LLM tokens used)."""
    return GeneratedNote(
        filename="_Raw",
        title=f"{display_name} - Raw Content",
        note_type="raw",
        content=scraped.markdown,
        tags=["web2vault", "raw"],
    )


def run_all_generators(
    scraped: ScrapedContent,
    llm: LLMProvider,
    verbose: bool = False,
    output_name: Optional[str] = None,
    vault_context: str = "",
) -> NoteBundle:
    """Run all generators and return a NoteBundle."""
    folder = output_name or derive_folder_name(scraped.title, scraped.url)
    display_name = output_name or scraped.title or folder
    bundle = NoteBundle(
        source_url=scraped.url,
        source_title=display_name,
        folder_name=folder,
    )

    # Raw content note (no LLM tokens — just saves the scraped markdown)
    bundle.notes.append(_make_raw_note(scraped, display_name))

    generators = [
        SummaryGenerator(llm, vault_context=vault_context),
        DeepDiveGenerator(llm, vault_context=vault_context),
        QAGenerator(llm, vault_context=vault_context),
        PracticeGenerator(llm, vault_context=vault_context),
    ]

    label_map = {
        "summary": "Summary",
        "deep_dive": "Deep Dive",
        "qa": "Q&A",
        "practice": "Practice Questions",
    }

    for i, gen in enumerate(generators):
        label = label_map.get(gen.note_type, gen.note_type)
        try:
            click.echo(f"  [{i + 1}/{len(generators)}] Generating {label}...")
            note = gen.generate(
                scraped, verbose=verbose, display_name=display_name
            )
            bundle.notes.append(note)
            if verbose:
                click.echo(f"    Done: {len(note.content)} chars")
        except Exception as e:
            error_msg = f"Failed to generate {label}: {e}"
            bundle.errors.append(error_msg)
            click.echo(f"  Warning: {error_msg}", err=True)

    return bundle
