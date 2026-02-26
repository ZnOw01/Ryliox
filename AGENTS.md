# Repository Guidelines

## Requirements

| Tool | Minimum version |
|---|---|
| Python | 3.11 |
| Node.js | 18 LTS |
| npm | 9 |
| Docker (optional) | 24 |

---

## First-time Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd <repo>

# 2. Create your local env file (never commit this)
cp .env.example .env   # edit with your values

# 3. Launch — the launcher handles venv + frontend build automatically
python -m launcher
```

> On first run the launcher creates `.venv/`, installs Python dependencies,
> and builds the Astro frontend automatically. No manual steps needed.

---

## Runtime Commands

```bash
python -m launcher                    # Interactive menu (default)
python -m launcher                    # Unified app on :8000 (recommended)
python -m launcher --stop             # Stop a running server
python -m launcher --status           # Show PID and port status
python -m launcher --docker           # Start via Docker Compose
python -m launcher --backend-only     # API only, no frontend (debug)
python -m launcher --rebuild-frontend # Force Astro rebuild before start
python -m launcher --no-browser       # Skip auto-opening the browser
```

> `python -m web.server` also works but bypasses the launcher setup checks.
> Use it only for direct backend debugging.

---

## Project Layout

```text
.
├── launcher.py              # Entry point — setup + server orchestration
├── config.py                # All runtime settings (env vars + .env)
├── web/
│   └── server.py            # FastAPI app and API routes
├── core/
│   ├── kernel.py            # Plugin registration and bootstrapping
│   ├── process_manager.py   # PID tracking, port management
│   └── ...                  # Shared HTTP client, types
├── plugins/                 # Feature logic (auth, search, chapters,
│                            #   assets, output formats, downloader)
├── frontend/                # Astro + React client
│   ├── src/
│   └── dist/                # Built output (generated, do not edit)
├── utils/                   # Shared helpers and utilities
├── data/                    # Runtime state — gitignored
│   ├── cookies.json         # Session cookies (never commit)
│   ├── session.sqlite3      # Auth session DB (never commit)
│   ├── download_jobs.sqlite3 # Download queue (auto-cleared on start)
│   └── logs/                # Per-job error logs (auto-cleared on start)
├── output/                  # Generated books and exports — gitignored
└── .run/                    # Launcher PID and log files — gitignored
```

**Rule:** plugin *behavior* stays in `plugins/`; plugin *registration* stays in `core/kernel.py`.

---

## Configuration Reference

All settings can be set via environment variables or in a `.env` file at the project root.
See `.env.example` for a ready-to-copy template.

| Variable | Default | Description |
|---|---|---|
| `BASE_URL` | `https://learning.oreilly.com` | Target site base URL |
| `REQUEST_DELAY` | `0.5` | Seconds between requests (≥ 0) |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds (≥ 1) |
| `REQUEST_RETRIES` | `2` | Retry attempts on failure (≥ 0) |
| `REQUEST_RETRY_BACKOFF` | `0.5` | Seconds between retries (≥ 0) |
| `OUTPUT_DIR` | `./output` | Where exported books are saved |
| `DATA_DIR` | `./data` | Runtime state directory |
| `COOKIES_FILE` | `{DATA_DIR}/cookies.json` | Session cookie storage |
| `SESSION_DB_FILE` | `{DATA_DIR}/session.sqlite3` | Auth session database |
| `USER_AGENT` | *(random fallback)* | Override the HTTP User-Agent |
| `ENABLE_FAKE_USERAGENT` | `false` | Use `fake-useragent` library for UA rotation |
| `HEADERS` | `{}` | Extra HTTP headers as JSON (cannot override protected headers) |
| `ACCEPT` | *(browser-like default)* | `Accept` header value |
| `ACCEPT_ENCODING` | `gzip, deflate` | `Accept-Encoding` header value |
| `ACCEPT_LANGUAGE` | `en-US,en;q=0.5` | `Accept-Language` header value |

> `HEADERS` cannot override `User-Agent`, `Accept`, `Accept-Encoding`, or `Accept-Language`.
> Use their dedicated variables instead.

---

## Data and Output

| Path | Contents | Committed? |
|---|---|---|
| `output/` | Generated books and exports | No |
| `data/` | Runtime state (queue DB, error logs) | No |
| `data/cookies.json` | Session cookies | **Never** |
| `data/session.sqlite3` | Auth session database | **Never** |

### Supported Export Formats

| Format | Mode | Notes |
|---|---|---|
| PDF | `combined` | All chapters in a single file |
| PDF | `separate` | One file per chapter |
| EPUB | `combined` | Single file; separate mode not supported |

---

## Code Style

- **Indentation:** 4 spaces (PEP 8).
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for module-level constants.
- **Type hints** and short docstrings are required for all public functions and non-obvious logic.
- **Imports:** stdlib → third-party → local, separated by blank lines.

---

## Validation Checklist

Before opening a PR, confirm these flows work end-to-end. Start the server with
`python -m launcher` and test each manually or with `curl`:

```bash
curl http://localhost:8000/api/status
curl "http://localhost:8000/api/search?q=python"
```

- [ ] `GET /api/status` returns `200`
- [ ] `GET /api/search?q=python` returns results
- [ ] PDF download — `combined` mode completes without error
- [ ] PDF download — `separate` mode completes without error
- [ ] EPUB download — `combined` mode completes without error

---

## Security

**Never commit** any of the following:

```gitignore
# Already in .gitignore — verify with `git status` before every push
.env
data/
output/
.run/
*.sqlite3
cookies.json
```

Add the same sensitive paths to `.dockerignore` if building a Docker image.
Run `git status` and confirm none of these appear as staged or untracked before pushing.
