# Changelog

All notable changes to Ryliox are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- `docker compose up` works again. The image did not build on Debian trixie,
  and the app then crashed at import because comma-separated host lists were
  not accepted.
- `.env` and the documented variables (`PORT`, `LOG_LEVEL`, `DATA_DIR`,
  `REQUEST_DELAY`, `RATE_LIMIT_MAX_REQUESTS`, `RYLIOX_QUEUE__*`,
  `RYLIOX_CACHE__*`, …) now take effect. Generic names such as `TIMEOUT`,
  `LEVEL` or `ENABLED` no longer change settings.
- Every state file, the audit log included, follows `DATA_DIR`.
- The launcher no longer deletes the download queue on start, and it starts
  on a machine with no Python packages installed.
- The interface renders in Plus Jakarta Sans and JetBrains Mono. The fonts are
  served by the app, so the Content-Security-Policy no longer blocks them.
- No React hydration error on load. The page starts in Spanish, the language
  it is prerendered in, and switches to the visitor's language afterwards.
- With the server stopped, a reload no longer shows a cached page claiming the
  service is active. The service worker is retired and removes itself from
  browsers that installed it.
- Text that came from the server in English (format descriptions, the
  rejected-cookies error) and a few hard-coded strings now follow the UI
  language.
- Secondary text meets WCAG AA contrast on every surface, in both themes.

### Removed
- `core/secrets.py`, `core/feature_flags.py` and the `/api/feature-flags`
  routes, `plugins/token.py`, and other code nothing called.
- Settings that had no effect, and their `.env.example` entries: HTTPS
  redirect, CSRF, cookie flags, secret storage, API rate limits, cache
  headers, fake user agent, `APP_VERSION`.
- Unused dependencies: 16 direct Python runtime dependencies (the lock goes
  from 126 to 109 packages); on the frontend, Phosphor icons, the PostCSS
  pipeline, the language detector, the Radix visually-hidden package and the
  frontend copy of Playwright.
- The Open Graph tags that pointed at a domain and an image that do not exist.

## [2.0.0] - 2026-08-26

### Security
- **Same-Origin header spoofing protection**: validated that `X-Forwarded-*` headers are only respected when originating from an authorized local proxy or loopback host.
- **Admin authentication hardening**: dynamic per-request loopback checks and strict validation preventing empty bearer token bypass.
- **Cryptographic audit log integrity**: upgraded HMAC integrity digest to full 64-character SHA-256 (256-bit).
- **DoS defense**: bounded in-memory rate limiter capacity with LRU eviction.
- **SSRF protection**: enforced URL validation on external API health check probes.
- Removed `cookies.json` from the working tree (it contained a real
  `orm-jwt` token). Cookies now live exclusively in the gitignored
  `data/cookies.json` via the `SessionStore`.
- Disabled `TrustedHostMiddleware` outside production (it was rejecting
  `testserver` host names).
- Documented the OWASP production checklist in `.env.example`.

### Added
- **Standalone Locust load testing**: created `tests/performance/locustfile.py` for isolated CLI benchmarking without polluting pytest test discovery.
- **Environment variable aliases**: supported flat standard UNIX variables (`PORT`, `HOST`, `LOG_LEVEL`, `OUTPUT_DIR`, etc.).
- **CI Python matrix**: added test matrix for Python 3.11, 3.12, and 3.13.
- `__init__.py` files for every test sub-directory so `pytest` collects them
  cleanly.
- `launcher/` package (six focused modules).

### Fixed
- **Test suite stability**: isolated `gevent` from pytest collection, eliminating test suite timeouts and hangs.
- **Launcher environment verification**: aligned `_ALLOWED_RUNTIME_PACKAGES` with `pyproject.toml` runtime dependencies, resolving infinite virtual environment re-creation loops.
- **Frontend accessibility & dark mode**: eliminated hardcoded gray styles in `Button.tsx` and `Badge.tsx`, added WAI-ARIA arrow key navigation to `FormatSelector.tsx`, and message cycling in `AriaLiveRegion.tsx`.
- **SSE streaming optimization**: eliminated unnecessary stream tear-down on status transitions in `useDownloadManager.ts`.
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

### Changed
- **Unified architecture**: replaced the stdlib `http.server` implementation in
  `web/server.py` with a single FastAPI application. All routes from
  `web/routes/*.py` are now wired in one place via `create_app()`.
- **Modernised the download queue**: deleted the legacy 1188-line
  `core/download_queue.py` in favour of the cleaner `core/services.py` +
  `core/repository.py` pair (DTOs, mappers, `IDownloadJobRepository` protocol).
- **Replaced `config.py`** (28 lines) with a full Pydantic Settings model
  covering server, paths, HTTP, security, rate-limiting, secrets, audit,
  session, logging, metrics, cache and queue groups.
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

[Unreleased]: https://github.com/ZnOw01/Ryliox/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/ZnOw01/Ryliox/releases/tag/v2.0.0
