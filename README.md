# Ryliox

<div align="center">

[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Astro](https://img.shields.io/badge/Astro-frontend-ff5d01?style=flat-square&logo=astro&logoColor=white)](https://astro.build/)
[![GitHub stars](https://img.shields.io/github/stars/ZnOw01/Ryliox?style=flat-square&logo=github)](https://github.com/ZnOw01/Ryliox/stargazers)

**Busca libros de O'Reilly Learning y exportalos en PDF o EPUB desde un navegador.**
Incluye cola de descargas persistente, progreso en tiempo real y seleccion de capitulos.

> [!IMPORTANT]
> Requiere una suscripcion activa a [O'Reilly Learning](https://learning.oreilly.com).
> Usa esta herramienta respetando los [terminos de servicio](https://www.oreilly.com/terms/).

</div>

---

## Caracteristicas

| | |
|---|---|
| **Autenticacion** | Login por cookies de sesion, incluye cookies `HttpOnly` |
| **Busqueda** | Por titulo, autor, editorial o ISBN con filtros en tiempo real |
| **Formatos** | EPUB, PDF combinado y PDF por capitulo |
| **Seleccion** | Elige capitulos especificos para PDF; EPUB descarga siempre el libro completo |
| **Cola** | Persistente en SQLite, sobrevive reinicios |
| **Progreso** | Polling (`/api/progress`) y SSE (`/api/progress/stream`) |
| **Frontend** | UI reactiva con Astro + React + Tailwind CSS |

---

## Requisitos

| Herramienta | Version minima |
|---|---|
| Python | 3.11 |
| Bun | 1.2 |
| Docker | 24 (opcional) |

### Instalar Bun

```bash
# Linux / macOS
curl -fsSL https://bun.sh/install | bash

# Windows — PowerShell
powershell -c "irm bun.sh/install.ps1 | iex"

# Verificar
bun --version
```

### Dependencias de sistema para PDF (WeasyPrint)

<details>
<summary>Ver instrucciones por OS</summary>

```bash
# macOS
brew install pango

# Ubuntu / Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

# Arch / Manjaro
sudo pacman -S pango harfbuzz

# Windows
# Instala el GTK runtime:
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

</details>

---

## Inicio rapido

```bash
git clone https://github.com/ZnOw01/Ryliox.git
cd Ryliox
cp .env.example .env       # ajusta si es necesario (ver seccion Configuracion)
python -m launcher
```

El launcher detecta automaticamente si faltan el entorno virtual, dependencias Python o el build del frontend, y los prepara en el primer arranque sin intervencion manual.

Abre **http://localhost:8000** una vez que el servidor este listo.

---

## Launcher

`python -m launcher` sin argumentos abre un menu interactivo persistente:

```text
Selecciona modo:
  1) Aplicacion unificada en :8000 (recomendado)
  2) Detener servicios en ejecucion
  3) Mostrar estado del runtime
  4) Modo Docker
  q) Salir
```

Tambien acepta flags para scripts o CI:

| Flag | Descripcion |
|---|---|
| *(sin flags)* | Menu interactivo |
| `--stop` | Detiene el servidor en ejecucion |
| `--status` | Muestra PID y estado del puerto |
| `--docker` | Levanta via Docker Compose |
| `--backend-only` | Arranca solo la API sin frontend |
| `--rebuild-frontend` | Fuerza recompilacion del bundle Astro |
| `--no-browser` | No abre el navegador automaticamente |

> `python -m web.server` tambien funciona, pero omite las verificaciones del launcher. Usalo solo para debug directo del backend.

---

## Formatos de exportacion

| Formato | Valor `format` | Salida | Seleccion de capitulos |
|---|---|---|---|
| EPUB | `epub` | Un archivo `.epub` | No, siempre libro completo |
| PDF combinado | `pdf` | Un archivo `.pdf` | Si |
| PDF por capitulo | `pdf-chapters` | Carpeta `PDF/` con un `.pdf` por capitulo | Si |

**Notas:**
- `format` acepta `string` o `array`: `"epub"`, `["epub", "pdf"]`, `"all"`.
- `"all"` equivale a `["epub", "pdf"]`.
- `pdf` y `pdf-chapters` se pueden combinar en la misma peticion.

```json
POST /api/download
{
  "book_id": "9781492051367",
  "format": ["epub", "pdf"],
  "chapters": [0, 1, 2],
  "skip_images": false
}
```

---

## Autenticacion con cookies

La forma mas fiable es copiar el header `Cookie` directamente desde DevTools:

1. Abre **DevTools → Network** en `learning.oreilly.com`.
2. Recarga la pagina y selecciona cualquier request.
3. Copia el valor completo del header `Cookie:`.
4. Pegalo en el editor de cookies de la UI o envia `POST /api/cookies`.

`POST /api/cookies` acepta tres formatos:

| Formato | Ejemplo |
|---|---|
| Header HTTP crudo **(recomendado)** | `"a=1; b=2; c=3"` |
| Objeto JSON | `{ "nombre": "valor" }` |
| Array JSON (EditThisCookie) | `[{ "name": "...", "value": "..." }]` |

> Si la sesion sigue siendo invalida, probablemente faltan cookies `HttpOnly` que los exportadores de extensiones no incluyen. Usa siempre el formato de header crudo.
> Las cookies se guardan en disco en `DATA_DIR`. Tratalas como credenciales: no las compartas ni las subas al repositorio.

### Cuando las cookies expiran

**Sintomas:**
- `GET /api/status` devuelve `"valid": false`.
- La busqueda falla con error de autenticacion.
- Descargas en curso pasan a `error` o dejan de avanzar.

**Solucion:**
1. Copia nuevamente el header `Cookie` completo desde DevTools.
2. Reemplaza las cookies en la UI o via `POST /api/cookies`.
3. Pulsa **Actualizar** en la tarjeta de autenticacion.
4. Si habia una descarga en error, reiniciala desde la cola.

---

## Configuracion

Copia `.env.example` a `.env`. La mayoria de valores por defecto funcionan sin cambios.

### Variables que probablemente necesites tocar

| Variable | Default | Cuando cambiarla |
|---|---|---|
| `OUTPUT_DIR` | `.runtime_output` | Si quieres los archivos en una ruta accesible fuera del runtime |
| `REQUEST_TIMEOUT` | `30` | Libros muy grandes; sube a `60` o `90` |
| `REQUEST_DELAY` | `0.5` | Si recibes rate limit; subelo gradualmente a `0.8` o `1.0` |
| `PORT` | `8000` | Si el puerto esta ocupado por otro servicio |

### Referencia completa

| Variable | Default | Descripcion |
|---|---|---|
| `BASE_URL` | `https://learning.oreilly.com` | URL base del sitio |
| `REQUEST_RETRIES` | `2` | Reintentos HTTP en fallo |
| `REQUEST_RETRY_BACKOFF` | `0.5` | Espera entre reintentos (segundos) |
| `DATA_DIR` | `.runtime_data` | Estado de runtime (SQLite, cookies) |
| `HOST` | `127.0.0.1` | Interfaz de escucha |
| `LOG_LEVEL` | `INFO` | Nivel de logs |
| `CORS_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000` | Origenes CORS permitidos |

> Usar `CORS_ORIGINS=*` expone la API publicamente. Solo en desarrollo.
> `HEADERS` no puede sobreescribir `User-Agent`, `Accept`, `Accept-Encoding` ni `Accept-Language`.

---

## Referencia de la API

```text
GET  /api/health
GET  /api/status
GET  /api/search?q={query}
GET  /api/book/{book_id}
GET  /api/book/{book_id}/chapters
POST /api/cookies
POST /api/download
GET  /api/progress
GET  /api/progress/stream        ← SSE
POST /api/cancel
GET  /api/openapi.json
```

Documentacion interactiva en **http://localhost:8000/docs** (Swagger UI).

### Ejemplos de respuesta

<details>
<summary>GET /api/health</summary>

```json
{
  "status": "ok",
  "uptime_seconds": 42.3,
  "version": "dev"
}
```

</details>

<details>
<summary>GET /api/status</summary>

```json
{
  "valid": true,
  "reason": null,
  "has_cookies": true
}
```

</details>

<details>
<summary>GET /api/search?q=python</summary>

```json
{
  "results": [
    {
      "id": "9781492051367",
      "title": "Fluent Python",
      "authors": ["Luciano Ramalho"],
      "publishers": ["O'Reilly Media"],
      "cover_url": "https://..."
    }
  ]
}
```

</details>

<details>
<summary>POST /api/download</summary>

```json
{
  "status": "queued",
  "book_id": "9781492051367",
  "job_id": "job_abc123",
  "queue_position": 0
}
```

</details>

<details>
<summary>GET /api/progress</summary>

```json
{
  "status": "running",
  "job_id": "job_abc123",
  "book_id": "9781492051367",
  "percentage": 63,
  "current_chapter": 7,
  "total_chapters": 12,
  "message": "processing"
}
```

</details>

---

## Troubleshooting

| Problema | Solucion |
|---|---|
| `Frontend build not found` | `python -m launcher --rebuild-frontend` |
| `bun` no encontrado | Instala Bun, abre una terminal nueva y verifica con `bun --version` |
| `403 forbidden_origin` | Envia el `POST` desde `http://localhost:8000` |
| Puerto 8000 ocupado | `python -m launcher --stop` o cambia `PORT` en `.env` |
| Cola trabada en `queued` | Reinicia; si persiste, elimina `.runtime_data/download_jobs.sqlite3` |
| Sesion invalida aun con cookies | Usa el header HTTP crudo desde DevTools (no un exporter) |
| Timeout en libros grandes | Sube `REQUEST_TIMEOUT` a `60`-`90` en `.env` |
| Error al generar PDF | Verifica dependencias del sistema: `pango`, `harfbuzz`, `pangoft2` |
| 401 / 403 a mitad de descarga | Las cookies expiraron; renuevalas y reinicia esa descarga |

---

## Contribuir

1. Haz fork y crea una rama (`feature/*` o `fix/*`).
2. Levanta el entorno local con `python -m launcher`.
3. Ejecuta checks antes de abrir PR:

```bash
# Backend
pytest -q

# Frontend
cd frontend && bun run check && bun run test
```

Si tu cambio toca la API, incluye ejemplos de request/response en el PR.
Ver [CONTRIBUTING.md](./CONTRIBUTING.md) para el flujo completo.

---

## Limitaciones conocidas

- Requiere una cuenta valida y activa de O'Reilly Learning.
- Orientado a libros; no cubre cursos interactivos ni contenido en video.
- Las cookies de sesion expiran y requieren renovacion manual.
- Sin soporte nativo para Windows en el launcher (funciona via Docker).

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ZnOw01/Ryliox&type=Date)](https://star-history.com/#ZnOw01/Ryliox&Date)

---

## Licencia

Distribuido bajo licencia **MIT**. Ver [LICENSE](./LICENSE) para detalle.
