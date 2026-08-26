# Changelog

All notable changes to Ryliox are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security
- **Same-Origin header spoofing protection**: validated that `X-Forwarded-*` headers are only respected when originating from an authorized local proxy or loopback host.
- **Admin authentication hardening**: dynamic per-request loopback checks and strict validation preventing empty bearer token bypass.
- **Cryptographic audit log integrity**: upgraded HMAC integrity digest to full 64-character SHA-256 (256-bit).
- **DoS defense**: bounded in-memory rate limiter capacity with LRU eviction.
- **SSRF protection**: enforced URL validation on external API health check probes.

### Added
- **Standalone Locust load testing**: created `tests/performance/locustfile.py` for isolated CLI benchmarking without polluting pytest test discovery.
- **Environment variable aliases**: supported flat standard UNIX variables (`PORT`, `HOST`, `LOG_LEVEL`, `OUTPUT_DIR`, etc.) via Pydantic `AliasChoices`.
- **CI Python matrix**: added test matrix for Python 3.11, 3.12, and 3.13.

### Fixed
- **Test suite stability**: isolated `gevent` from pytest collection, eliminating test suite timeouts and hangs.
- **Launcher environment verification**: aligned `_ALLOWED_RUNTIME_PACKAGES` with `pyproject.toml` runtime dependencies, resolving infinite virtual environment re-creation loops.
- **Frontend accessibility & dark mode**: eliminated hardcoded gray styles in `Button.tsx` and `Badge.tsx`, added WAI-ARIA arrow key navigation to `FormatSelector.tsx`, and message cycling in `AriaLiveRegion.tsx`.
- **SSE streaming optimization**: eliminated unnecessary stream tear-down on status transitions in `useDownloadManager.ts`.
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
- `python -m launcher` now has a committed package entry point, uses `.run/venv`
  instead of a potentially stale `.venv`, and no longer releases the same port
  twice in interactive mode.
- Simplified the launcher command surface by dropping the unused backend-only
  mode and documenting the SQLite-first cookie store.
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
