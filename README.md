# Ryliox

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Astro](https://img.shields.io/badge/frontend-Astro-ff5d01)
[![GitHub stars](https://img.shields.io/github/stars/ZnOw01/RylioX?style=social)](https://github.com/ZnOw01/RylioX/stargazers)

App web para buscar libros de O'Reilly Learning y exportarlos en PDF o EPUB, con cola de descargas y progreso en tiempo real.

Requiere una suscripcion valida a O'Reilly. Respeta siempre sus [terminos oficiales](https://www.oreilly.com/terms/).

## Caracteristicas

- Login por cookies de sesion.
- Busqueda por titulo, autor o ISBN.
- Descarga completa o por capitulos.
- Cola de descargas persistente (SQLite).
- Progreso por polling (`/api/progress`) o SSE (`/api/progress/stream`).
- Exportacion en EPUB, PDF combinado y PDF por capitulo.

## Requisitos

- Python 3.11+
- Node.js 18 LTS+
- npm 9+
- Docker 24+ (opcional)

Dependencias de sistema para PDF (WeasyPrint):

```bash
# macOS
brew install pango

# Ubuntu/Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

# Windows
# Instala GTK runtime:
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

## Inicio rapido

```bash
git clone https://github.com/ZnOw01/Rylliox.git
cd Rylliox
cp .env.example .env
python -m launcher
```

En el primer arranque, el launcher crea `.venv`, instala dependencias Python y compila el frontend.

## Comandos utiles

| Comando | Uso |
|---|---|
| `python -m launcher` | Modo interactivo / app unificada |
| `python -m launcher --backend-only` | Solo API |
| `python -m launcher --rebuild-frontend` | Recompila frontend |
| `python -m launcher --status` | Estado de PID/puerto |
| `python -m launcher --stop` | Detener runtime |
| `python -m launcher --docker` | Levantar por Docker Compose |
| `python -m launcher --no-browser` | No abrir navegador |
| `python -m web.server` | Backend directo (debug) |

## Formatos de exportacion

| UI | `format` API | Salida | Capitulos |
|---|---|---|---|
| EPUB | `epub` | 1 archivo `.epub` | No |
| PDF combinado | `pdf` | 1 archivo `.pdf` | Si |
| PDF por capitulo | `pdf-chapters` | `PDF/*.pdf` | Si |

Notas:
- `format` acepta string o lista.
- `"all"` (string) equivale a `epub,pdf`.
- Puedes combinar `pdf` y `pdf-chapters`.

## Configuracion clave

Archivo: `.env` (basado en `.env.example`).

| Variable | Default |
|---|---|
| `BASE_URL` | `https://learning.oreilly.com` |
| `REQUEST_DELAY` | `0.5` |
| `REQUEST_TIMEOUT` | `30` |
| `REQUEST_RETRIES` | `2` |
| `REQUEST_RETRY_BACKOFF` | `0.5` |
| `OUTPUT_DIR` | `./output` |
| `DATA_DIR` | `./data` |
| `COOKIES_FILE` | `{DATA_DIR}/cookies.json` |
| `SESSION_DB_FILE` | `{DATA_DIR}/session.sqlite3` |
| `HOST` | `127.0.0.1` |
| `PORT` | `8000` |
| `APP_VERSION` | `dev` |
| `LOG_LEVEL` | `INFO` |
| `CORS_ORIGINS` | `*` |

`HEADERS` no puede sobreescribir `User-Agent`, `Accept`, `Accept-Encoding` ni `Accept-Language`.

## Cookies de sesion

`POST /api/cookies` acepta:

1. Header crudo: `Cookie: a=1; b=2` (recomendado)
2. Array JSON tipo EditThisCookie
3. Objeto JSON `{ "cookie": "value" }`

Si da sesion invalida, normalmente faltan cookies `HttpOnly`; usa el formato 1 desde DevTools > Network.

## API rapida

- `GET /api/health`
- `GET /api/status`
- `GET /api/search?q=python`
- `GET /api/book/{book_id}`
- `GET /api/book/{book_id}/chapters`
- `POST /api/download`
- `GET /api/progress`
- `GET /api/progress/stream`
- `POST /api/cancel`
- `GET /api/openapi.json`

Ejemplo de descarga:

```json
{
  "book_id": "9781492051367",
  "format": ["epub", "pdf"],
  "chapters": [0, 1, 2],
  "skip_images": false
}
```

## Troubleshooting

- `Frontend build not found`: `python -m launcher --rebuild-frontend`
- `npm` no encontrado: instala Node.js 18+ y abre una nueva terminal
- `403 forbidden_origin`: manda `POST` desde el mismo origen (`http://localhost:8000`)
- Puerto ocupado: `python -m launcher --stop`
- Cola trabada en `queued`: reinicia y, si sigue igual, borra `data/download_jobs.sqlite3`

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ZnOw01/Rylliox&type=Date)](https://star-history.com/#ZnOw01/Rylliox&Date)

Referencia oficial:
- https://www.star-history.com/blog/how-to-use-github-star-history

## Seguridad

Mantener fuera del repo: `.env`, `data/`, `output/`, `.run/`, `*.sqlite3`, `cookies.json`.

## Licencia

MIT. Ver [LICENSE](./LICENSE).
