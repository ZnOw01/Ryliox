# Ryliox

<div align="center">

[![License: GPLv3+](https://img.shields.io/badge/license-GPLv3%2B-blue?style=flat-square)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Astro](https://img.shields.io/badge/Astro-frontend-ff5d01?style=flat-square&logo=astro&logoColor=white)](https://astro.build/)

**Exporta libros de O'Reilly Learning en PDF o EPUB con cola, progreso en tiempo real y selección de capítulos.**

</div>

> [!IMPORTANT]
> Ryliox requiere una suscripción activa a [O'Reilly Learning](https://learning.oreilly.com).
> Úsalo de forma responsable y respetando los [términos de servicio de O'Reilly](https://www.oreilly.com/terms/).

## Qué hace

- Busca libros por título, autor, editorial o ISBN.
- Exporta en EPUB, PDF combinado o PDF por capítulo.
- Permite seleccionar capítulos específicos para exportaciones PDF.
- Mantiene una cola persistente de descargas en SQLite.
- Reporta progreso en tiempo real mediante SSE.

## Requisitos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11 |
| uv | reciente |
| Node.js | 22.12.0 o 24.x |
| Bun | 1.3+ |
| Docker | 24 (opcional) |

### Dependencias de PDF

Ryliox usa WeasyPrint para generar PDF. Instala las librerías del sistema necesarias antes del primer uso:

```bash
# macOS
brew install pango

# Ubuntu/Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0

# Windows
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

## Instalación rápida

```bash
git clone https://github.com/ZnOw01/Ryliox.git
cd Ryliox
cp .env.example .env
python -m launcher
```

El launcher crea `.venv/`, instala dependencias Python y construye el frontend automáticamente cuando hace falta.

Abre `http://localhost:8000` en tu navegador.

## Uso básico

### 1. Autenticación

1. Abre DevTools en `learning.oreilly.com`.
2. Ve a la pestaña `Network`.
3. Copia el encabezado `Cookie` completo de una petición autenticada.
4. Pégalo en la interfaz de Ryliox.

### 2. Descarga

1. Busca un libro por título o ISBN.
2. Elige el formato de salida.
3. Selecciona capítulos si vas a generar PDF.
4. Inicia la descarga y sigue el estado desde la cola.

## Comandos principales

```bash
python -m launcher                    # Inicio recomendado
python -m launcher --status           # Estado del servidor
python -m launcher --stop             # Detener servidor
python -m launcher --backend-only     # Solo API
python -m launcher --docker           # Docker Compose
python -m launcher --rebuild-frontend # Forzar rebuild del frontend
python -m launcher --no-browser       # No abrir navegador automáticamente
```

## API

Endpoints principales:

```text
GET  /api/status
GET  /api/search?q={query}
GET  /api/book/{id}
GET  /api/book/{id}/chapters
POST /api/cookies
POST /api/download
GET  /api/progress
GET  /api/progress/stream
POST /api/cancel
```

La documentación OpenAPI está disponible en `http://localhost:8000/docs` cuando la aplicación corre en modo no productivo.

## Configuración

Toda la configuración runtime vive en variables de entorno o en `.env`. Revisa [.env.example](./.env.example) para la referencia completa.

Variables habituales:

| Variable | Default | Descripción |
|---|---|---|
| `BASE_URL` | `https://learning.oreilly.com` | URL base del sitio objetivo |
| `REQUEST_DELAY` | `0.5` | Retardo entre peticiones |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP en segundos |
| `OUTPUT_DIR` | `./output` | Carpeta de exportaciones |
| `DATA_DIR` | `./data` | Estado runtime y bases SQLite |
| `PORT` | `8000` | Puerto HTTP local |
| `ENVIRONMENT` | `development` | Modo de ejecución |

## Desarrollo

Guía de contribución: [CONTRIBUTING.md](./CONTRIBUTING.md)

Validaciones mínimas antes de publicar cambios:

```bash
curl http://localhost:8000/api/status
curl "http://localhost:8000/api/search?q=python"
pytest
```

En el frontend también conviene ejecutar:

```bash
cd frontend
bun install --frozen-lockfile
bun run check
bun run lint
bun run build
```

## Resolución de problemas

| Problema | Acción recomendada |
|---|---|
| El frontend no existe o quedó desactualizado | `python -m launcher --rebuild-frontend` |
| El puerto 8000 está ocupado | `python -m launcher --stop` |
| La sesión fue rechazada | Vuelve a copiar el header `Cookie` completo desde O'Reilly |
| La cola quedó en estado inconsistente | Detén la app y elimina `data/download_jobs.sqlite3` |

## Licencia

Ryliox se distribuye bajo la **GNU General Public License v3.0 o posterior**.

- Puedes usar, estudiar, modificar y redistribuir el proyecto bajo los términos de la GPL.
- Si distribuyes versiones modificadas, debes mantener la misma licencia.
- El software se entrega **sin garantía**.

Consulta el texto completo en [LICENSE](./LICENSE).
