# AGENTS.md — Loker Scraper Project Rules

## Project Overview

This is **Tools Scraping Info Loker Indonesia** — a Python application that scrapes contact info (phone numbers & emails) from Indonesian job portals. It uses Playwright for headless browser automation and Gradio for the web UI.

## Tech Stack

- **Language**: Python 3.10+ (async programming with `asyncio` & `playwright.async_api`)
- **Web Automation**: Playwright (Chromium headless)
- **UI Framework**: Gradio (runs on port 7860)
- **Parsing**: BeautifulSoup4 (supplementary HTML/text parsing)
- **Target Deployment**: Ubuntu VPS (IDCloudHost / Biznet GIO)

## Build, Run & Test Commands

### Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

### Run the Application
```bash
python app.py
```

### Run in Background (VPS)
```bash
nohup python app.py > scraper.log 2>&1 &
```

### Testing
```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_scraper.py

# Run a single test function
pytest tests/test_scraper.py::test_extract_phone_numbers

# Run with verbose output
pytest -v tests/test_scraper.py

# Run with async support (if using pytest-asyncio)
pytest -v --tb=short tests/
```

### Linting & Formatting
```bash
# Format check with black
black --check .

# Format all files
black .

# Lint with ruff
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Type check with mypy
mypy .
```

## Code Style Guidelines

### Imports
- Group imports in this order: standard library, third-party, local modules.
- Use `from __future__ import annotations` at the top when needed.
- Use absolute imports over relative imports.
- Never use wildcard imports (`from module import *`).

### Formatting
- Line length: **88 characters** (Black default).
- Use **double quotes** for strings.
- Use **4 spaces** for indentation — no tabs.
- Trailing commas in multi-line collections.
- Blank line at end of every file.

### Types & Type Hints
- All function signatures must include type hints for parameters and return types.
- Use `async def` for all Playwright/network operations.
- Prefer `str | None` over `Optional[str]` (Python 3.10+ union syntax).
- Use `list[str]`, `dict[str, str]` over `List[str]`, `Dict[str, str]`.

### Naming Conventions
- **Files/Modules**: `snake_case.py` (e.g., `scraper_karir.py`, `contact_extractor.py`)
- **Functions**: `snake_case` (e.g., `extract_phone_numbers`, `scroll_to_bottom`)
- **Classes**: `PascalCase` (e.g., `ScraperEngine`, `ContactResult`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`, `MAX_SCROLL_ITERATIONS`)
- **Async functions**: prefix with verb describing action (e.g., `fetch_page`, `parse_contacts`)

### Error Handling
- Always wrap Playwright operations in `try/except` blocks.
- Use specific exceptions (`playwright.async_api.TimeoutError`, `playwright.async_api.Error`).
- Log errors with meaningful messages — include the URL being scraped.
- Never silently swallow exceptions; at minimum log them.
- Return empty results on failure rather than raising to the caller.

### Async Patterns
- Use `async with` for browser/page context management.
- Always close pages and browsers in `finally` blocks.
- Use `asyncio.sleep()` for delays — never `time.sleep()`.
- Keep async functions focused on one concern each.

## Scraping Heuristics

### Auto-Scrolling Logic
1. Compare `document.body.scrollHeight` before and after each scroll.
2. Stop scrolling if height is unchanged for **3 consecutive iterations**.
3. Respect a configurable maximum scroll limit.

### Link Harvesting (Directory Pages)
- **Do NOT** extract contacts from directory/listing pages.
- Search for `<a>` elements whose URLs contain semantic patterns: `/job/`, `/loker/`, `/vacancy/`.
- Collect detail page URLs first, then visit each one individually.

### Contact Extraction (Detail Pages)
- Use `document.body.innerText` to get all raw text globally.
- **Do NOT** lock CSS selectors to specific visual elements — sites have diverse layouts.
- Extract phone numbers using Indonesian patterns: `+62`, `08xx`, `62xx`.
- Extract email addresses with standard regex patterns.

## Anti-Blocking & Rate Limiting

- **User-Agent**: Rotate realistic User-Agent strings (Windows/Chrome latest).
- **Random Delays**: Insert 1.5–3 second random delays between page navigations.
- **Proxies**: Support rotating residential proxies (Webshare, ProxyScrape) for Indonesia IPs.
- Never send requests in rapid succession to the same domain.

## Project Structure (Target)

```
ScrappingWebLoker/
├── app.py                    # Gradio UI entry point
├── requirements.txt          # Python dependencies
├── scrapers/
│   ├── __init__.py
│   ├── base.py               # Base scraper class with shared logic
│   ├── scraper_karir.py      # Per-portal scraper modules
│   └── contact_extractor.py  # Phone & email extraction utilities
├── utils/
│   ├── __init__.py
│   ├── browser.py            # Playwright browser factory
│   └── anti_block.py         # User-Agent rotation, proxy config
├── tests/
│   ├── test_scraper.py
│   └── test_contact_extractor.py
└── AGENTS.md
```

## Key Dependencies (requirements.txt)

```
playwright
gradio
beautifulsoup4
```

## Important Notes

- All UI text and log messages should be in **Bahasa Indonesia**.
- The Gradio interface must be user-friendly with clear labels and progress indicators.
- Each portal scraper should inherit from a common base class for consistency.
- Always handle network timeouts gracefully — job portals can be slow or unresponsive.
