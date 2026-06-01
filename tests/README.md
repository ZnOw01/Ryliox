# Ryliox Test Suite

Comprehensive test suite for the Ryliox application.

## Test Structure

```
tests/
├── conftest.py                          # Global fixtures
├── __init__.py
├── unit/                                # Unit tests (no I/O)
│   ├── test_kernel.py                   # Kernel lifecycle, plugin registry
│   ├── test_schemas.py                  # Pydantic models
│   ├── test_session_store.py            # SQLite cookie storage
│   └── utils/test_files.py              # Filename sanitisation
├── web/
│   ├── test_routes_regressions.py       # Stable error envelopes
│   └── test_rate_limiter_unit.py        # In-process rate limiter
├── plugins/test_epub_plugin.py          # EPUB rendering
├── integration/api/                     # FastAPI TestClient tests
│   ├── test_auth.py
│   ├── test_books.py
│   └── test_downloads.py
├── integration/plugins/
│   └── test_downloader_formats.py
├── e2e/                                 # Playwright (opt-in via `uv sync --extra e2e`)
│   └── test_download_flow.py
├── security/                            # OWASP, secret handling, CSRF
│   ├── test_owasp.py
│   └── test_security.py
├── performance/                         # Rate limit benchmarks
│   └── test_rate_limiting.py
└── a11y/                                # Accessibility smoke tests
    └── test_accessibility.py
```

## Quick Start

```bash
# Run the full suite (unit + integration; security/e2e are opt-in)
uv run pytest

# Faster, fail-fast loop
uv run pytest -x --tb=short -q

# Coverage
uv run pytest --cov=core --cov=plugins --cov=utils --cov=web --cov-report=term-missing

# Opt-in suites
uv sync --extra e2e
uv run pytest tests/e2e -m e2e
uv sync --extra security
uv run pytest tests/security
```

## Conventions

- **Test names** describe behaviour: `test_<unit>_<scenario>_<expected_outcome>`.
- **Fixtures** live in `conftest.py` (root) or local `conftest.py` files.
- **No real network**: HTTP clients are mocked via `httpx.MockTransport` or local fixtures.
- **No real cookies**: tests inject dummy cookies through `SessionStore` with a `tmp_path` DB.
- **No `print()`**: use `caplog` / `capsys` assertions.

## Known Pre-Existing Failures

Some tests document bugs that the refactor surfaced (e.g. Pydantic validation
gaps, missing migration logic, kernel lifecycle quirks). They are kept as
failing tests with a clear name so they act as TODO markers. See
`tests/TESTING.md` (TODO) for the full list once the codebase is stabilised.
