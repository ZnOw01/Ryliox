# Ryliox

<div align="center">

[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Astro](https://img.shields.io/badge/Astro-frontend-ff5d01?style=flat-square&logo=astro&logoColor=white)](https://astro.build/)
[![GitHub stars](https://img.shields.io/github/stars/ZnOw01/RylioX?style=flat-square&logo=github)](https://github.com/ZnOw01/RylioX/stargazers)

**Busca libros de O'Reilly Learning y exportalos en PDF o EPUB desde un navegador.**
Cola de descargas, progreso en tiempo real y soporte para seleccion de capitulos.

> [!IMPORTANT]
> Requiere una suscripcion activa a [O'Reilly Learning](https://learning.oreilly.com).
> Usa esta herramienta respetando siempre los [terminos de servicio oficiales](https://www.oreilly.com/terms/).

</div>

---

## Caracteristicas

| | |
|---|---|
| **Autenticacion** | Login por cookies de sesion (incluye cookies `HttpOnly`) |
| **Busqueda** | Por titulo, autor, editorial o ISBN con filtros en tiempo real |
| **Formatos** | EPUB, PDF combinado y PDF por capitulo |
| **Seleccion** | Elige capitulos especificos para PDF; EPUB siempre descarga el libro completo |
| **Cola** | Persistente en SQLite — sobrevive reinicios |
| **Progreso** | Polling (`/api/progress`) y SSE (`/api/progress/stream`) |
| **Frontend** | UI reactiva con Astro + React + Tailwind CSS |

---

## Requisitos

| Herramienta | Version minima |
|---|---|
| Python | 3.11 |
| Node.js | 18 LTS |
| npm | 9 |
| Docker | 24 (opcional) |

**Dependencias de sistema para PDF (WeasyPrint):**

<details>
<summary>Ver instrucciones por OS</summary>

```bash
# macOS
brew install pango

# Ubuntu / Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

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
cp .env.example .env          # edita con tus valores si es necesario
python -m launcher
```

El launcher detecta automaticamente si el entorno virtual, las dependencias Python y el build del frontend estan listos — si no lo estan, los crea en el primer arranque sin ninguna intervencion manual.

Una vez iniciado, abre **http://localhost:8000** en tu navegador.

---

## Launcher

Ejecutar `python -m launcher` sin argumentos muestra un **menu interactivo persistente** — puedes cambiar de modo sin salir del launcher.

```
Selecciona modo:
  1) Aplicacion unificada en :8000 (recomendado)
  2) Detener servicios en ejecucion
  3) Mostrar estado del runtime
  4) Modo Docker
  q) Salir
```

Tambien acepta flags directos para uso en scripts o CI:

| Flag | Descripcion |
|---|---|
| *(sin flags)* | Menu interactivo |
| `--stop` | Detiene el servidor en ejecucion |
| `--status` | Muestra PID y estado del puerto |
| `--docker` | Levanta via Docker Compose |
| `--backend-only` | Arranca solo la API (sin frontend) |
| `--rebuild-frontend` | Fuerza recompilacion del bundle Astro |
| `--no-browser` | No abre el navegador automaticamente |

> `python -m web.server` tambien funciona pero no ejecuta las verificaciones del launcher. Usalo solo para debug directo del backend.

---

## Formatos de exportacion

| Formato | Valor `format` | Salida | Seleccion de capitulos |
|---|---|---|---|
| EPUB | `epub` | Un archivo `.epub` | No — siempre libro completo |
| PDF combinado | `pdf` | Un archivo `.pdf` | Si |
| PDF por capitulo | `pdf-chapters` | Carpeta `PDF/` con un `.pdf` por capitulo | Si |

**Notas de la API:**
- `format` acepta `string` o `array`: `"epub"`, `["epub", "pdf"]`, `"all"`.
- `"all"` equivale a `["epub", "pdf"]`.
- `pdf` y `pdf-chapters` se pueden combinar en la misma peticion.

**Ejemplo de peticion de descarga:**

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

La forma mas fiable de autenticarse es pegar el header `Cookie` directamente desde DevTools:

1. Abre **DevTools -> Network** en `learning.oreilly.com`
2. Recarga la pagina y selecciona cualquier request
3. Copia el valor completo del header `Cookie:`
4. Pegalo en el editor de cookies de la UI (o manda `POST /api/cookies`)

El endpoint `POST /api/cookies` acepta tres formatos:

| Formato | Ejemplo |
|---|---|
| Header HTTP crudo **(recomendado)** | `"a=1; b=2; c=3"` |
| Objeto JSON | `{ "nombre": "valor" }` |
| Array JSON (EditThisCookie) | `[{ "name": "...", "value": "..." }]` |

> Si la sesion sigue siendo invalida es probable que falten cookies `HttpOnly` que los extension exporters no incluyen. Usa siempre el formato de header crudo desde Network.

---

## Configuracion

Copia `.env.example` a `.env` y ajusta los valores que necesites. Todas las variables tambien se pueden pasar como variables de entorno.

| Variable | Default | Descripcion |
|---|---|---|
| `BASE_URL` | `https://learning.oreilly.com` | URL base del sitio |
| `REQUEST_DELAY` | `0.5` | Segundos entre requests |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP en segundos |
| `REQUEST_RETRIES` | `2` | Reintentos en fallo |
| `REQUEST_RETRY_BACKOFF` | `0.5` | Espera entre reintentos |
| `OUTPUT_DIR` | `./output` | Directorio de salida |
| `DATA_DIR` | `./data` | Estado en tiempo de ejecucion |
| `HOST` | `127.0.0.1` | Interfaz de escucha |
| `PORT` | `8000` | Puerto del servidor |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `CORS_ORIGINS` | `*` | Origenes CORS permitidos |

> `HEADERS` no puede sobreescribir `User-Agent`, `Accept`, `Accept-Encoding` ni `Accept-Language`. Usa sus variables dedicadas en su lugar.

---

## Referencia de la API

```
GET  /api/health
GET  /api/status
GET  /api/search?q={query}
GET  /api/book/{book_id}
GET  /api/book/{book_id}/chapters
POST /api/cookies
POST /api/download
GET  /api/progress
GET  /api/progress/stream        <- SSE
POST /api/cancel
GET  /api/openapi.json
```

La documentacion interactiva completa esta disponible en **http://localhost:8000/docs** (Swagger UI).

---

## Troubleshooting

| Problema | Solucion |
|---|---|
| `Frontend build not found` | `python -m launcher --rebuild-frontend` |
| `npm` no encontrado | Instala Node.js 18+ y abre una terminal nueva |
| `403 forbidden_origin` | Envia el `POST` desde el mismo origen: `http://localhost:8000` |
| Puerto 8000 ocupado | `python -m launcher --stop` |
| Cola trabada en `queued` | Reinicia; si persiste, elimina `data/download_jobs.sqlite3` |
| Sesion invalida aun con cookies | Usa el header HTTP crudo desde DevTools en lugar de un exporter |

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ZnOw01/Ryliox&type=Date)](https://star-history.com/#ZnOw01/Ryliox&Date)

---

## Licencia

Distribuido bajo la licencia **MIT**. Ver [LICENSE](./LICENSE) para mas detalle.
