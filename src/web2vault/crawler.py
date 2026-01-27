"""Firecrawl SDK wrapper for web scraping."""

import time

from firecrawl import FirecrawlApp

from .config import Config
from .exceptions import CrawlError
from .models import ScrapedContent


def _retry(func, max_attempts: int = 3, base_delay: float = 2.0):
    """Execute func with exponential backoff retry."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_error


def scrape_url(url: str, config: Config) -> ScrapedContent:
    """Scrape a single URL and return structured content."""
    app = FirecrawlApp(api_key=config.firecrawl_api_key)

    try:
        result = _retry(lambda: app.scrape(
            url,
            formats=["markdown"],
        ))
    except Exception as e:
        raise CrawlError(f"Failed to scrape {url}: {e}") from e

    if not result:
        raise CrawlError(f"Empty response from Firecrawl for {url}")

    markdown = result.markdown if hasattr(result, "markdown") else result.get("markdown", "")
    metadata_obj = result.metadata if hasattr(result, "metadata") else result.get("metadata", {})
    
    # Convert Pydantic model to dict if needed
    if hasattr(metadata_obj, "model_dump"):
        metadata = metadata_obj.model_dump()
    elif hasattr(metadata_obj, "dict"):
        metadata = metadata_obj.dict()
    else:
        metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    
    title = metadata.get("title") or metadata.get("og_title") or ""

    if not markdown:
        raise CrawlError(f"No markdown content returned for {url}")

    return ScrapedContent(
        url=url,
        title=title,
        markdown=markdown,
        metadata=metadata,
    )


def crawl_url(url: str, config: Config) -> list[ScrapedContent]:
    """Crawl a URL and its linked pages up to configured depth/limit."""
    if config.crawl_depth == 0 and config.max_pages == 1:
        return [scrape_url(url, config)]

    app = FirecrawlApp(api_key=config.firecrawl_api_key)

    try:
        result = _retry(lambda: app.crawl(
            url,
            limit=config.max_pages,
            max_discovery_depth=config.crawl_depth or 1,
        ))
    except Exception as e:
        raise CrawlError(f"Failed to crawl {url}: {e}") from e

    if not result:
        raise CrawlError(f"Invalid crawl response for {url}")

    pages = []
    # Result is a list of Document objects from Firecrawl v2
    for page in result:
        markdown = page.markdown if hasattr(page, "markdown") else page.get("markdown", "")
        if not markdown:
            continue
        metadata_obj = page.metadata if hasattr(page, "metadata") else page.get("metadata", {})
        
        # Convert Pydantic model to dict if needed
        if hasattr(metadata_obj, "model_dump"):
            metadata = metadata_obj.model_dump()
        elif hasattr(metadata_obj, "dict"):
            metadata = metadata_obj.dict()
        else:
            metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
        
        page_url = page.url if hasattr(page, "url") else page.get("url", url)
        title = metadata.get("title") or metadata.get("og_title") or ""
        pages.append(ScrapedContent(
            url=page_url,
            title=title,
            markdown=markdown,
            metadata=metadata,
        ))

    if not pages:
        raise CrawlError(f"No pages with content found when crawling {url}")

    return pages
