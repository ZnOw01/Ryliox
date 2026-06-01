# Ryliox

> Export any O'Reilly Learning Platform book to EPUB or PDF, with a modern web
> UI to search, preview, and queue downloads. Designed for personal and
> educational use — see the [Disclaimer](#disclaimer) below.

Ryliox is a from-scratch refactor of [Mosaibah/oreilly-ingest](https://github.com/Mosaibah/oreilly-ingest).
It unifies two previously parallel code bases (a stdlib `http.server` and a
half-wired FastAPI implementation) into a single FastAPI backend, with a
modern Astro/React frontend served from the same origin.

## Features

- **EPUB 3 and PDF** — export complete books with images, styles and TOC.
- **O'Reilly V2 API** — fast, reliable, supports the same auth flow as the
  official web reader.
- **Queue + progress streaming** — Server-Sent Events push live progress
  per job; multiple downloads can run in series.
- **Modern frontend** — Astro 5 + React 19 + Radix, with i18n (English /
  Spanish), framer-motion transitions, and a fully accessible design.
- **Hardened by default** — OWASP-aware security headers, CSRF tokens,
  rate-limiting, immutable audit log, encrypted secret storage, Prometheus
  metrics, structured logging, and a typed configuration layer.

## Quick start

### Docker

```bash
git clone https://github.com/ryliox/ryliox.git
cd ryliox
docker compose up -d
# open http://localhost:8000
```

### Local development (uv + bun)

```bash
git clone https://github.com/ryliox/ryliox.git
cd ryliox
uv sync --extra dev
bun run dev
```

The launcher (`python -m launcher`) drives the local workflow: it creates
the Python venv with `uv`, installs / builds the frontend with `bun`, and
spawns `uvicorn web.server:app`. Pass `--no-browser` to skip the auto-open
or `--docker` to use Compose instead of running the stack locally.

Requires **Python 3.11 → 3.13** and **Node ≥ 22.12 (even minor)**. PDF
export uses WeasyPrint, which on Windows needs the [GTK3 runtime][gtk].

[gtk]: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

## Setting up cookies

1. Open the web UI and click **Set cookies**.
2. Recommended: paste the full JSON export from the *EditThisCookie*
   extension. It includes the HttpOnly `orm-rt` cookie that O'Reilly needs
   to refresh the session after the JWT expires.
3. Fallback: the in-page *browser console* helper only reads
   `document.cookie`, so `orm-rt` will be missing and the session may
   expire within minutes.

## Architecture

```
┌───────────────────────────────┐
│  frontend/  (Astro 5 + React) │  served by FastAPI as static files
└───────────────────────────────┘
              ▲
              │ JSON / SSE
              │
┌───────────────────────────────┐
│  web/  FastAPI application    │  create_app()  ←  web/server.py
│  ├── routes/   (auth, books,  │
│  │             downloads, …)  │
│  ├── api_utils, dependencies, │
│  └── schemas (Pydantic)       │
└───────────────────────────────┘
              ▲
              │  dependency-injected
              │
┌───────────────────────────────┐
│  core/                        │
│  ├── services + repository    │  download queue (DTOs, mappers, UoW)
│  ├── kernel + http_client     │  plugin microkernel
│  ├── audit, secrets, session, │
│  │   cache, process_manager   │
│  └── validators               │
└───────────────────────────────┘
              ▲
              │
┌───────────────────────────────┐
│  plugins/  (auth, book, …)    │  registered into the kernel at startup
└───────────────────────────────┘
```

### Public API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET`  | `/api/status` | Auth + cookie status |
| `GET`  | `/api/search?q=` | Find books |
| `GET`  | `/api/book/{id}` | Book metadata |
| `GET`  | `/api/book/{id}/chapters` | Chapter list |
| `POST` | `/api/download` | Queue a download |
| `GET`  | `/api/progress?job_id=` | Job progress (JSON) |
| `GET`  | `/api/progress/stream` | Job progress (SSE) |
| `POST` | `/api/cancel` | Cancel a job |
| `POST` | `/api/cookies` | Save session cookies |
| `GET`  | `/api/health` | Liveness probe |
| `GET`  | `/api/health/detailed` | Disk, memory, SQLite, external APIs |
| `GET`  | `/metrics` | Prometheus exposition |
| `GET`  | `/api/docs` | Swagger UI (development only) |

## Configuration

All settings live in a single Pydantic `BaseSettings` model loaded from
`.env`. See [`.env.example`](.env.example) for the full list of variables
and the [OWASP production checklist](.env.example#production-checklist).

| Group | Env prefix | Notes |
| ----- | ---------- | ----- |
| Server | `HOST`, `PORT`, `APP_VERSION` | Bind + bind interface |
| HTTP | `REQUEST_*`, `USER_AGENT`, `ACCEPT_*` | Outbound client tuning |
| Security | `ENVIRONMENT`, `ENABLE_*`, `CSP_POLICY`, `ALLOWED_HOSTS` | OWASP A02 / A05 |
| Rate limit | `RATE_LIMIT_*`, `API_RATE_LIMIT_*` | OWASP A04 |
| Secrets | `SECRET_MASTER_PASSWORD`, `SECRET_ROTATION_DAYS` | OWASP A02 / A07 |
| Audit | `AUDIT_*` | OWASP A09 |
| Cache | `CACHE_*` | LRU caches per resource type |

To override a value at runtime, set the corresponding environment variable
and restart, or call `config.reload()` from a test.

## Development

```bash
uv sync --extra dev
uv run ruff check .            # lint
uv run ruff format --check .   # format
uv run mypy                    # static types
uv run pytest tests/unit -q    # fast unit tests
uv run pytest tests/integration -q  # API integration tests
```

The CI matrix (`.github/workflows/ci.yml`) runs **ruff**, **mypy**,
**pytest** (Python 3.11 / 3.12 / 3.13), **pip-audit**, **bandit** and
**detect-secrets** on every push and pull request.

## Project layout

```
config.py                – Pydantic Settings + legacy module-level constants
main.py                  – thin entry point: parses args, calls web.server.run_server
launcher/                – local CLI (replaces the old 850-line launcher.py)
web/                     – FastAPI application
  server.py              – create_app() factory + run_server()
  routes/                – auth, books, downloads, metrics, system
  api_utils.py           – error envelope, SSE helpers
  dependencies.py        – FastAPI providers, OWASP guards
  schemas.py             – Pydantic request / response models
core/                    – domain layer
  services.py            – DownloadQueueService
  repository.py          – DownloadJobRepository (UoW)
  dto.py / mappers.py    – DTO + mapper contracts
  interfaces.py          – Protocols (IDownloadJobRepository, IUnitOfWork)
  kernel.py              – microkernel + create_default_kernel
  http_client.py         – Akamai-aware HTTP client
  audit.py, secrets.py,  – OWASP-aligned infra
  session_store.py,      – SQLite session/cookie storage
  cache.py,              – LRU caches per resource type
  process_manager.py     – PID/port management for the launcher
  validators.py          – input/output validation
plugins/                 – pluggable functionality (auth, book, …, epub, pdf, …)
utils/files.py           – filename sanitisation, slugify, accent removal
frontend/                – Astro 5 + React 19 frontend (separate npm project)
tests/                   – unit, integration, e2e, security, performance, contract, a11y
```

## License

MIT.

## Credits

Inspired by [lorenzodifuccia/safaribooks](https://github.com/lorenzodifuccia/safaribooks)
and the original [Mosaibah/oreilly-ingest](https://github.com/Mosaibah/oreilly-ingest)
project.

## Disclaimer

Ryliox is for personal and educational use only. By using it you agree to
the [O'Reilly Terms of Service](https://www.oreilly.com/terms/). The
authors are not affiliated with O'Reilly Media and assume no liability for
how the tool is used.
