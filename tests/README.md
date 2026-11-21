# Ryliox Test Suite

Comprehensive test suite for the Ryliox application.

## Test Structure

```
tests/
├── conftest.py                          # Global fixtures and markers
├── contract/                            # HTTP & OpenAPI contracts
│   └── test_http_contracts.py
├── unit/                                # Unit tests
│   ├── test_kernel.py
│   ├── test_schemas.py
│   ├── test_dto.py
│   ├── test_contracts.py
│   ├── test_session_store.py
│   ├── test_phase1_regressions.py
│   ├── core/
│   │   ├── test_audit.py
│   │   ├── test_http_client.py
│   │   ├── test_logging_config.py
│   │   ├── test_operational_hardening.py
│   │   ├── test_queue_integrity.py
│   │   └── test_session_store.py
│   ├── plugins/
│   │   ├── test_assets_plugin.py
│   │   ├── test_auth_plugin.py
│   │   ├── test_book_plugin.py
│   │   ├── test_chapters_plugin.py
│   │   ├── test_downloader_plugin.py
│   │   ├── test_epub_plugin.py
│   │   ├── test_html_processor_plugin.py
│   │   └── test_output_plugin.py
│   ├── utils/
│   │   └── test_files.py
│   └── web/
│       ├── test_dependencies_paths.py
│       ├── test_rate_limiter_unit.py
│       ├── test_routes_regressions.py
│       └── test_security_middleware.py
├── integration/
│   ├── api/                             # FastAPI TestClient endpoint integration
│   │   ├── test_auth.py
│   │   ├── test_books.py
│   │   └── test_downloads.py
│   └── plugins/
│       └── test_downloader_formats.py
├── security/                            # OWASP, secret handling, live security
│   ├── test_owasp.py
│   └── test_security.py
├── performance/                         # Rate limit benchmarks & load tests
│   ├── locustfile.py
│   └── test_rate_limiting.py
├── e2e/                                 # Playwright E2E smoke tests
│   ├── test_app_smoke.py
│   └── test_download_flow.py
└── a11y/                                # Accessibility smoke tests
    └── test_accessibility.py
```

## Quick Start

```bash
# Run the full suite (unit + integration; security/e2e are opt-in)
uv run pytest

# Faster, fail-fast loop
uv run pytest -x --tb=short -q

# Opt-in suites
uv sync --extra e2e
uv run pytest tests/e2e -m e2e
uv sync --extra security
uv run pytest tests/security --run-security
```

## Conventions

- **Test names** describe behaviour: `test_<unit>_<scenario>_<expected_outcome>`.
- **Fixtures** live in `conftest.py` (root) or local `conftest.py` files.
- **No real network**: HTTP clients are mocked via `httpx.MockTransport` or local fixtures.
- **No real cookies**: tests inject dummy cookies through `SessionStore` with a `tmp_path` DB.
- **No `print()`**: use `caplog` / `capsys` assertions.

## Opt-In Suites

Security, performance, and e2e suites are opt-in because they may require extra
dependencies, a live server, browser tooling, or slower runtime flags. Unit,
contract, and focused integration tests should pass without external network
access.

Line coverage is not currently configured. Do not report a coverage percentage
until `pytest-cov` (and frontend coverage) are declared and run in CI.
