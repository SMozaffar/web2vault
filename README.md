# web2vault

A CLI tool that scrapes web pages and generates structured study notes for [Obsidian](https://obsidian.md) using LLMs (Claude or GPT).

Given a URL, web2vault extracts the page content and produces a folder of interconnected notes in your Obsidian vault:

- **Summary** -- condensed overview with key takeaways
- **Deep Dive** -- exhaustive, multi-pass exploration of the topic
- **Q&A** -- question-and-answer pairs covering all major points
- **Practice Questions** -- quizzes (multiple choice, true/false, short answer) with hidden answers using Obsidian callout syntax
- **Raw Note** -- the original scraped markdown for reference

Notes include YAML frontmatter (title, source URL, tags, date) and wikilinks for cross-referencing within your vault.

### Vault-Aware Cross-Linking

Before generating notes, web2vault scans your existing vault for `.md` files and extracts their titles and topics. This context is injected into LLM prompts so the generated notes automatically create `[[wikilinks]]` to related existing notes. The more notes in your vault, the more interconnected new notes become -- no manual linking required.

### Math Rendering

Generated notes use Obsidian-compatible LaTeX syntax for mathematical content: `$...$` for inline math and `$$...$$` for display equations. This renders natively in Obsidian without plugins.

### Smart Tagging

Each note is tagged with `web2vault`, the note type (e.g. `summary`, `deep_dive`), and a subject tag derived from the page title for easy filtering and discovery.

## Quickstart

### Prerequisites

- Python 3.9+
- A [Firecrawl](https://firecrawl.dev) API key
- An [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) API key

### Install

```bash
git clone https://github.com/YOUR_USERNAME/web2vault.git
cd web2vault
pip install -e .
```

### Configure

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

```
FIRECRAWL_API_KEY=fc-...
ANTHROPIC_API_KEY=sk-ant-...       # required if using Claude (default)
OPENAI_API_KEY=sk-...              # required if using OpenAI
OBSIDIAN_VAULT_PATH=/path/to/vault
LLM_PROVIDER=claude                # "claude" or "openai"
```

### Run

```bash
# Single URL
web2vault https://en.wikipedia.org/wiki/Bessie_Coleman

# Multiple URLs
web2vault https://example.com/page1 https://example.com/page2

# With options
web2vault https://example.com \
  --provider openai \
  --vault-path ~/my-vault \
  --crawl-depth 1 \
  --max-pages 5 \
  --output-name "My Notes" \
  --verbose
```

| Flag | Description | Default |
|---|---|---|
| `--provider` | LLM provider (`claude` or `openai`) | `claude` |
| `--vault-path` | Output directory | `OBSIDIAN_VAULT_PATH` env var |
| `--crawl-depth` | Recursively crawl linked pages to this depth | `0` (single page) |
| `--max-pages` | Max pages when crawling | `1` |
| `--output-name` | Custom folder/title name | Derived from page title |
| `--model` | Override the default model | `claude-sonnet-4-20250514` / `gpt-4o` |
| `--verbose` | Show detailed progress | Off |

## How it works

1. **Scan Vault** -- Existing `.md` files are scanned for titles and topics to enable cross-linking.
2. **Scrape** -- Firecrawl extracts the page as clean markdown.
3. **Chunk** -- Large content is split at heading boundaries to fit within LLM context windows.
4. **Generate** -- Each generator (summary, deep dive, Q&A, practice) runs multi-pass prompts against the LLM, with vault context and math formatting instructions injected.
5. **Format & Write** -- Notes are formatted with YAML frontmatter (including subject tags) and saved as `.md` files in an organized folder inside your vault.

## Roadmap

- [x] **Vault-aware cross-linking** -- Scans existing vault notes and injects their titles/topics into LLM prompts so generated notes create `[[wikilinks]]` to related existing notes automatically.
- [x] **Math rendering** -- Obsidian-compatible LaTeX formatting (`$...$` inline, `$$...$$` display) is enforced via prompt instructions across all generators.
- [x] **Smart tagging** -- Notes are tagged with a subject-derived tag in addition to `web2vault` and the note type.
- [ ] **GitHub repo ingestion** -- Clone a repo and convert its files into text input for note generation. Includes research into minimizing input token usage (e.g., filtering files, summarizing boilerplate).
- [ ] **Vectorization / RAG** -- Index previously generated notes so the tool can search over existing vault content for deeper semantic matching beyond title/heading cross-linking.

## License

MIT
