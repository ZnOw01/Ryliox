# RylioX

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![Astro](https://img.shields.io/badge/frontend-Astro-ff5d01)
[![GitHub stars](https://img.shields.io/github/stars/ZnOw01/RylioX?style=social)](https://github.com/ZnOw01/RylioX/stargazers)

App web para buscar libros de O'Reilly Learning y exportarlos en PDF o EPUB, con cola de descargas y progreso en tiempo real.

> Requiere una suscripción válida a O'Reilly. Respeta siempre sus [términos oficiales](https://www.oreilly.com/terms/).

---

## Tabla de contenidos

- [Aviso legal](#aviso-legal)
- [Características](#características)
- [Requisitos](#requisitos)
- [Inicio rápido](#inicio-rápido)
- [Comandos](#comandos)
- [Formatos de exportación](#formatos-de-exportación)
- [Arquitectura](#arquitectura)
- [Configuración](#configuración)
- [Autenticación por cookies](#autenticación-por-cookies)
- [API](#api)
- [Docker](#docker)
- [Troubleshooting](#troubleshooting)
- [Seguridad](#seguridad)
- [Licencia](#licencia)

---

## Aviso legal

- Este proyecto **no está afiliado ni respaldado** por O'Reilly Media.
- Úsalo solo con una cuenta válida y con contenido al que tengas acceso legal.
- Eres responsable del cumplimiento de copyright, propiedad intelectual y términos de servicio.
- Prohibido el uso para redistribución no autorizada o cualquier fin que infrinja derechos de terceros.

---

## Características

- Autenticación mediante cookies de sesión desde UI o API.
- Búsqueda por título, autor o ISBN.
- Descarga completa o selección de capítulos específicos.
- Cola de descargas persistente (SQLite).
- Progreso en vivo vía polling (`/api/progress`) o SSE (`/api/progress/stream`).
- Exportación a EPUB, PDF combinado y PDF por capítulo.
- Revelado de archivos exportados en el gestor de archivos nativo.

---

## Requisitos

- Python 3.11+
- Node.js 18 LTS+
- npm 9+
- Docker 24+ (opcional, solo para modo Docker)

**Dependencias de sistema para PDF (WeasyPrint):**

```bash
# macOS
brew install pango

# Ubuntu / Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

# Windows
# Instala GTK runtime:
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

---

## Inicio rápido

```bash
git clone https://github.com/ZnOw01/RylioX.git
cd RylioX
cp .env.example .env   # edita las variables que necesites
python -m launcher
```

En el primer arranque, el launcher crea `.venv` automáticamente, instala dependencias Python, compila el frontend y abre el navegador en `http://localhost:8000`.

**Instalación manual:**

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..

python -m web.server
```

---

## Comandos

| Comando | Descripción |
|---|---|
| `python -m launcher` | Modo interactivo / app unificada (recomendado) |
| `python -m launcher --backend-only` | Solo API, sin compilar frontend |
| `python -m launcher --rebuild-frontend` | Fuerza recompilación del bundle frontend |
| `python -m launcher --status` | Estado actual de PID y puerto |
| `python -m launcher --stop` | Detiene procesos en el puerto configurado |
| `python -m launcher --docker` | Levanta el stack con Docker Compose |
| `python -m launcher --no-browser` | No abre el navegador automáticamente |
| `python -m web.server` | Backend directo sin launcher (debug) |

---

## Formatos de exportación

| UI | `format` (API) | Salida | Selección de capítulos |
|---|---|---|---|
| EPUB | `epub` | Un archivo `.epub` | No |
| PDF combinado | `pdf` | Un archivo `.pdf` | Sí |
| PDF por capítulo | `pdf-chapters` | Carpeta `PDF/` con un `.pdf` por capítulo | Sí |

- `format` acepta string o lista: `"pdf"` o `["epub", "pdf"]`.
- `"all"` equivale a `["epub", "pdf"]` (no incluye `pdf-chapters`).
- `pdf` y `pdf-chapters` pueden combinarse: `["pdf", "pdf-chapters"]`.

---

## Arquitectura

```
web/        FastAPI: rutas HTTP, schemas Pydantic, middlewares
core/       Kernel, bootstrap de plugins, cola de descargas, sesión
plugins/    Lógica de negocio por dominio (book, chapters, downloader, pdf, output...)
frontend/   Astro + React (UI)
utils/      Helpers compartidos (sanitización de nombres, slugs)
output/     Archivos generados (configurable vía OUTPUT_DIR)
data/       Estado de runtime (cola SQLite, logs, cookies)
```

**Flujo de una descarga:**

```
UI / API  →  POST /api/download
          →  DownloadQueueService encola el job
          →  Worker llama a DownloaderPlugin
          →  DownloaderPlugin orquesta BookPlugin + ChaptersPlugin + PdfPlugin / EpubPlugin
          →  Archivos escritos en output/{slug}/
          →  Progreso disponible en /api/progress o /api/progress/stream
```

---

## Configuración

Copia `.env.example` a `.env` y ajusta lo que necesites. Todas las variables tienen valores por defecto funcionales.

### Servidor

| Variable | Default | Descripción |
|---|---|---|
| `HOST` | `127.0.0.1` | Host en el que escucha el servidor |
| `PORT` | `8000` | Puerto del servidor web |
| `APP_VERSION` | `dev` | Versión mostrada en `/api/health` |
| `LOG_LEVEL` | `INFO` | Nivel de logging: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | `*` | Orígenes CORS permitidos. En producción usa tu dominio real |

### Datos y salida

| Variable | Default | Descripción |
|---|---|---|
| `OUTPUT_DIR` | `./output` | Carpeta donde se guardan los archivos exportados |
| `DATA_DIR` | `./data` | Estado de runtime: cola, logs, sesión |
| `COOKIES_FILE` | `./data/cookies.json` | Archivo de persistencia de cookies de sesión |
| `SESSION_DB_FILE` | `./data/cookies.sqlite3` | Base de datos local de sesión |

### HTTP

| Variable | Default | Descripción |
|---|---|---|
| `BASE_URL` | `https://learning.oreilly.com` | URL base de la API de O'Reilly |
| `REQUEST_DELAY` | `0.5` | Segundos de espera entre requests consecutivos |
| `REQUEST_TIMEOUT` | `30` | Timeout en segundos por request HTTP |
| `REQUEST_RETRIES` | `2` | Reintentos automáticos en error transitorio |
| `REQUEST_RETRY_BACKOFF` | `0.5` | Segundos de backoff entre reintentos |
| `USER_AGENT` | auto | User-Agent explícito. Si se define, anula `ENABLE_FAKE_USERAGENT` |
| `ENABLE_FAKE_USERAGENT` | `false` | Rotar user-agent aleatorio por petición |
| `ACCEPT` | default navegador | Header `Accept` enviado en cada request |
| `ACCEPT_ENCODING` | `gzip, deflate` | Header `Accept-Encoding` |
| `ACCEPT_LANGUAGE` | `en-US,en;q=0.5` | Header `Accept-Language` |
| `HEADERS` | `{}` | JSON con headers adicionales a mezclar. No puede sobreescribir `User-Agent`, `Accept`, `Accept-Encoding` ni `Accept-Language` |

---

## Autenticación por cookies

RylioX necesita las cookies de sesión de tu cuenta O'Reilly. Se aceptan tres formatos en `POST /api/cookies`:

**1. Header `Cookie:` crudo — recomendado**

Copia el valor desde DevTools → Network → cualquier request a O'Reilly → cabecera `Cookie`:

```
Cookie: BrowserCookiesConsent=...; groot_sessionid=...; ...
```

**2. Array JSON de EditThisCookie**

Exporta con la extensión [EditThisCookie](https://www.editthiscookie.com/) y pega el array:

```json
[{"name": "groot_sessionid", "value": "abc123", "domain": ".oreilly.com", ...}]
```

**3. Objeto JSON plano**

```json
{"groot_sessionid": "abc123", "BrowserCookiesConsent": "..."}
```

> Los formatos 2 y 3 pueden omitir cookies `HttpOnly`, lo que resulta en sesión inválida. Si la verificación falla, usa el formato 1.

### Endpoints de sesión

```
GET  /api/status   → Estado actual de autenticación
POST /api/cookies  → Guardar cookies (requiere mismo origen)
GET  /api/cookies  → Ver cookies almacenadas (requiere mismo origen)
```

---

## API

Documentación interactiva: `GET /api/openapi.json`

### Sistema

```
GET  /api/health               Estado, uptime y versión
GET  /api/settings             Configuración actual (directorio de salida)
GET  /api/formats              Formatos disponibles y aliases
POST /api/settings/output-dir  Cambiar directorio de salida
POST /api/reveal               Revelar archivo en el gestor nativo
```

### Libros

```
GET /api/search?q={término}       Buscar libros
GET /api/book/{book_id}           Metadatos de un libro
GET /api/book/{book_id}/chapters  Lista de capítulos con índices
```

### Descargas

```
POST /api/download          Encolar una descarga
GET  /api/progress          Estado actual (polling)
GET  /api/progress/stream   Estado en tiempo real (SSE)
POST /api/cancel            Cancelar descarga activa
```

### Parámetros de `POST /api/download`

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `book_id` | `string` | requerido | ID del libro |
| `format` | `string \| string[]` | `"epub"` | Formato(s) de salida |
| `chapters` | `int[]` | `null` | Índices de capítulos a descargar (1-based, null = todos) |
| `output_dir` | `string` | valor de `OUTPUT_DIR` | Directorio de salida para esta descarga |
| `skip_images` | `bool` | `false` | Omitir descarga de imágenes |

> `chapters` usa índices **1-based**: el primer capítulo es `1`, no `0`.

### Ejemplos

```bash
# Libro completo en EPUB y PDF
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"book_id":"9781492051367","format":["epub","pdf"]}'

# Solo los primeros 3 capítulos en PDF
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"book_id":"9781492051367","format":"pdf","chapters":[1,2,3]}'
```

```powershell
# PowerShell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/download" `
  -ContentType "application/json" `
  -Body '{"book_id":"9781492051367","format":["epub","pdf"]}'
```

### Formato de error

Todos los errores devuelven la misma estructura:

```json
{
  "error": "Descripción legible",
  "code": "codigo_estable_para_maquina",
  "details": {}
}
```

El campo `code` es estable entre versiones y puede usarse para manejo programático.

---

## Docker

```bash
# Desde el launcher
python -m launcher --docker

# Directamente
docker compose up --build -d

# Ver estado y logs
docker compose ps
docker compose logs -f
```

---

## Troubleshooting

**`Frontend build not found`**
```bash
python -m launcher --rebuild-frontend
```

**`npm` no encontrado en PATH**

Instala [Node.js 18+](https://nodejs.org/) y abre una nueva terminal.

**Error al generar PDF (WeasyPrint)**

Instala las dependencias de sistema según tu plataforma (ver [Requisitos](#requisitos)). En Windows asegúrate de que el runtime GTK esté en PATH.

**Sesión inválida tras guardar cookies**

Los formatos 2 y 3 no incluyen cookies `HttpOnly`. Usa el formato 1 (header `Cookie:` crudo desde DevTools → Network).

**`403 forbidden_origin` en endpoints POST**

Los endpoints mutantes requieren que el request provenga del mismo origen (`http://localhost:8000`). Es una protección anti-CSRF intencional.

**Puerto en uso**
```bash
python -m launcher --stop
```

**Cola atascada en `queued`**

Reinicia el servidor. Si persiste:
```bash
rm data/download_jobs.sqlite3
```

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ZnOw01/RylioX&type=Date)](https://star-history.com/#ZnOw01/RylioX&Date)

---

## Seguridad

- Nunca versiones `.env`, `data/`, `output/`, `.run/`, `*.sqlite3` ni `cookies.json`.
- En producción, configura `CORS_ORIGINS` con tu dominio real en vez de `*`.
- Los endpoints POST están protegidos por verificación de mismo origen (anti-CSRF).
- Revisa `.gitignore` antes de hacer push.

---

## Licencia

MIT. Ver [LICENSE](./LICENSE).
