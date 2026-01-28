"""CLI entry point for web2vault."""

import sys

import click

from .config import load_config
from .crawler import crawl_url, scrape_url
from .exceptions import ConfigError, CrawlError, Web2VaultError
from .generators import run_all_generators
from .llm import get_llm_provider
from .utils import derive_folder_name
from .vault_index import VaultIndex
from .writer import write_bundle


@click.command()
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "--provider",
    type=click.Choice(["claude", "openai"]),
    default=None,
    help="LLM provider (default: claude, or LLM_PROVIDER env var)",
)
@click.option(
    "--vault-path",
    type=click.Path(),
    default=None,
    help="Path to Obsidian vault (default: ./vault_output or OBSIDIAN_VAULT_PATH env var)",
)
@click.option(
    "--crawl-depth",
    type=int,
    default=None,
    help="Crawl depth (0 = single page, default: 0)",
)
@click.option(
    "--max-pages",
    type=int,
    default=None,
    help="Maximum pages to crawl (default: 1)",
)
@click.option(
    "--output-name",
    type=str,
    default=None,
    help="Custom name for the output folder and note titles",
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="LLM model to use (default: claude-sonnet-4-20250514 or gpt-4o)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def main(urls, provider, vault_path, crawl_depth, max_pages, output_name, model, verbose):
    """Scrape URL(s) and generate Obsidian study notes.

    Provide one or more URLs to scrape and convert into a full set of
    Obsidian-compatible study notes using an LLM.

    Example: web2vault https://en.wikipedia.org/wiki/Bessie_Coleman
    """
    # Load config
    try:
        config = load_config(
            vault_path=vault_path,
            provider=provider,
            model=model,
            crawl_depth=crawl_depth,
            max_pages=max_pages,
            verbose=verbose,
        )
    except ConfigError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(2)

    if verbose:
        click.echo(f"Provider: {config.llm_provider} ({config.default_model})")
        click.echo(f"Vault path: {config.vault_path}")

    # Initialize LLM
    try:
        llm = get_llm_provider(config)
    except Exception as e:
        click.echo(f"Failed to initialize LLM provider: {e}", err=True)
        sys.exit(2)

    # Scan existing vault notes for cross-linking context
    vault_index = VaultIndex.scan(config.vault_path)
    if verbose and len(vault_index):
        click.echo(f"Found {len(vault_index)} existing notes in vault")

    had_errors = False
    total_failure = True

    for url in urls:
        click.echo(f"\nProcessing: {url}")

        # Scrape
        try:
            if config.crawl_depth > 0 or config.max_pages > 1:
                pages = crawl_url(url, config)
                if verbose:
                    click.echo(f"  Crawled {len(pages)} page(s)")
                # Merge all pages into one ScrapedContent
                scraped = pages[0]
                if len(pages) > 1:
                    combined_md = "\n\n---\n\n".join(
                        f"# {p.title}\n\nSource: {p.url}\n\n{p.markdown}"
                        for p in pages
                    )
                    scraped.markdown = combined_md
            else:
                scraped = scrape_url(url, config)

            if verbose:
                click.echo(f"  Title: {scraped.title}")
                click.echo(f"  Content length: {len(scraped.markdown)} chars")
        except CrawlError as e:
            click.echo(f"  Scraping failed: {e}", err=True)
            had_errors = True
            continue

        # Build vault context for cross-linking, excluding current output folder
        current_folder = output_name or derive_folder_name(scraped.title, scraped.url)
        filtered_index = VaultIndex.scan(config.vault_path, exclude_folder=current_folder)
        vault_context = filtered_index.format_for_prompt()

        # Generate notes
        try:
            bundle = run_all_generators(
                scraped, llm, verbose=verbose, output_name=output_name,
                vault_context=vault_context,
            )
        except Web2VaultError as e:
            click.echo(f"  Generation failed: {e}", err=True)
            had_errors = True
            continue

        if bundle.errors:
            had_errors = True

        # Write to vault
        try:
            output_dir = write_bundle(bundle, config.vault_path)
            total_failure = False
            note_count = len(bundle.notes)
            click.echo(f"  Wrote {note_count} notes to: {output_dir}")
            if bundle.errors:
                click.echo(f"  ({len(bundle.errors)} generator(s) failed partially)")
        except OSError as e:
            click.echo(f"  Failed to write files: {e}", err=True)
            had_errors = True

    # Exit code
    if total_failure:
        sys.exit(2)
    elif had_errors:
        sys.exit(1)
    else:
        click.echo("\nDone!")
        sys.exit(0)
