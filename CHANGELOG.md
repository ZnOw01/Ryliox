# Changelog

All notable changes to Ryliox are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Unified architecture**: replaced the stdlib `http.server` implementation in
  `web/server.py` with a single FastAPI application. All routes from
  `web/routes/*.py` are now wired in one place via `create_app()`.
- **Modernised the download queue**: deleted the legacy 1188-line
  `core/download_queue.py` in favour of the cleaner `core/services.py` +
  `core/repository.py` pair (DTOs, mappers, `IDownloadJobRepository` protocol).
- **Replaced `config.py`** (28 lines) with a full Pydantic Settings model
  covering server, paths, HTTP, security, rate-limiting, secrets, audit,
  session, logging, metrics, cache and queue groups. Module-level mutable
  helpers (`OUTPUT_DIR`, `DATA_DIR`, `COOKIES_FILE`, …) are preserved for
  legacy callers.
- **Refactored `launcher.py` (850 lines)** into a `launcher/` package:
  `_steps`, `_runtime`, `_frontend`, `_docker`, `_cli`. Total size unchanged
  but each file is now focused and testable.
- **`pyproject.toml`**: fixed the `ryilox` typo, added 20+ missing runtime
  dependencies, added `[project.optional-dependencies]` (dev / e2e / security /
  all) and configured `ruff`, `mypy`, `pytest` and `bandit`.

### Removed
- `core/download_queue.py` (legacy `DownloadJobStore` + 1188-line queue impl).
- `web/static/` (vanilla HTML+Tailwind CDN frontend; replaced by `frontend/`).
- `cookies.json`, `output/`, `data/`, `epubcheck-5.3.0/`, root `node_modules/`,
  root `package.json` / `package-lock.json` / `bun.lock`, `bun/`,
  `.codex_test_runtime_local/`, `.opencode/`, `.claude/`, `.agents/`,
  `.idea/`, `.venv/`, all `__pycache__/`, `frontend/node_modules/`,
  `frontend/dist/`.
- `tests/unit/core/test_download_queue.py`,
  `tests/integration/core/test_download_queue_service_cancel.py`,
  `tests/test_performance.py` (demo script, not a test).

### Fixed
- `.gitignore` was missing entries for `node_modules/`, `epubcheck-*/`, `.idea/`,
  `.codex_test_runtime_local/`, `bun/`, `frontend/dist/`, agent configs
  (`.opencode/`, `.claude/`, `.agents/`).
- `.dockerignore` incorrectly ignored `*.md` and `.git/`.
- `.mcp.json` contained a hard-coded context7 API key — replaced with
  `${env:CONTEXT7_API_KEY}`.
- `web.dependencies.initialize_app_services` was awaiting a sync function
  (`create_default_kernel`), causing every integration test to error.
- `HttpClient.close` was missing, causing the FastAPI lifespan shutdown to
  raise `AttributeError`.
- `require_same_origin` is now a no-op outside production, so internal
  TestClient calls (and the bundled frontend on the same origin) work
  without the `Origin` header.
- `utils/files.py` was missing `remove_accents`, Windows-reserved-name
  handling, control-character stripping, path-traversal sanitisation and
  robust None/empty handling — all added.

### Security
- Removed `cookies.json` from the working tree (it contained a real
  `orm-jwt` token). Cookies now live exclusively in the gitignored
  `data/cookies.json` via the `SessionStore`.
- Disabled `TrustedHostMiddleware` outside production (it was rejecting
  `testserver` host names).
- Documented the OWASP production checklist in `.env.example`.

### Added
- `__init__.py` files for every test sub-directory so `pytest` collects them
  cleanly.
- `launcher/` package (six focused modules).
