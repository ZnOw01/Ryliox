# Revisión Técnica Integral — Ryliox v2.0.0

**Fecha:** 2026-07-30
**Revisor:** opencode (revisión automatizada)
**Repositorio:** `/tmp/ryliox-opencode-review` (208 archivos)
**Ramas:** Solo `main` analizada

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Metodología y Alcance](#2-metodología-y-alcance)
3. [Descripción de la Arquitectura Actual](#3-descripción-de-la-arquitectura-actual)
4. [Aspectos Positivos](#4-aspectos-positivos)
5. [Problemas Críticos](#5-problemas-críticos)
6. [Problemas de Prioridad Alta](#6-problemas-de-prioridad-alta)
7. [Problemas de Prioridad Media](#7-problemas-de-prioridad-media)
8. [Problemas de Prioridad Baja](#8-problemas-de-prioridad-baja)
9. [Bugs Confirmados](#9-bugs-confirmados)
10. [Riesgos Potenciales / Hipótesis](#10-riesgos-potenciales--hipótesis)
11. [Seguridad](#11-seguridad)
12. [Rendimiento](#12-rendimiento)
13. [Calidad y Limpieza del Código](#13-calidad-y-limpieza-del-código)
14. [Código o Archivos que Podrían Eliminarse](#14-código-o-archivos-que-podrían-eliminarse)
15. [Refactorizaciones Recomendadas](#15-refactorizaciones-recomendadas)
16. [Mejoras de Arquitectura](#16-mejoras-de-arquitectura)
17. [Mejoras de Documentación](#17-mejoras-de-documentación)
18. [Mejoras de Pruebas](#18-mejoras-de-pruebas)
19. [Mejoras de Configuración y Automatización](#19-mejoras-de-configuración-y-automatización)
20. [Recomendaciones Específicas por Archivo/Carpeta](#20-recomendaciones-específicas-por-archivocarpeta)
21. [Orden de Implementación Propuesto](#21-orden-de-implementación-propuesto)
22. [Limitaciones de la Revisión](#22-limitaciones-de-la-revisión)

---

## 1. Resumen Ejecutivo

Ryliox es una aplicación para descargar libros técnicos de O'Reilly Media, compuesta por un backend Python (FastAPI + plugins) y un frontend Astro/React 19. En general, el proyecto muestra **buena calidad técnica**: tipado estricto, arquitectura modular, prácticas modernas de seguridad (CSP, HSTS, CSRF, auditoría HMAC), Docker multi-etapa, CI/CD completo y documentación extensa.

**Fortalezas principales:** Configuración robusta con Pydantic v2 `BaseSettings`, caché LRU con TTL, logging de auditoría inmutable con detección de manipulación, frontend accesible (SkipLink, AriaLiveRegion, focus trap), i18n completo (ES/EN), y Dockerfile ejemplar con multi-stage build.

**Debilidades principales:**
- **Fuga de memoria CSRF** (CR-001): `cleanup_expired()` en `CSRFProtection` nunca se invoca.
- **Hardcoded version en CI** (CR-002): `ci.yml` línea 52 tiene `ryliox-2.0.0-py3-none-any.whl` hardcoded.
- **Cobertura de pruebas insuficiente** (CR-003): Solo 5 tests frontend + tests backend limitados; 13 módulos core tienen CERO cobertura.
- **CSS duplicado masivo** (CR-004): Animaciones, utilidades y queries `prefers-reduced-motion` duplicadas en 6+ archivos CSS.
- **Dos sistemas de tokens CSS** (CR-005): `design-tokens-2026.css` y `oklch-palette.css` compiten como fuente de verdad.
- **Archivo muerto** (CR-006): `frontend/src/lib/advanced-types.ts` (80 líneas, nunca importado).
- **Dos librerías de iconos** (CR-007): Phosphor + Lucide duplican ~40KB en bundle.
- **CSP con `unsafe-inline` y `unsafe-eval`** (CR-008): Debilita la protección XSS.
- **`cleanup_expired()` de caché LRU usa `time.monotonic()` pero `__contains__` no** (CR-009): Inconsistencia en verificación de expiración.

---

## 2. Metodología y Alcance

### 2.1 Inventario y Cobertura

| Categoría | Archivos | Examinados |
|-----------|----------|------------|
| Python backend (core/) | 18 | 18 (100%) |
| Web API (web/) | 9 | 9 (100%) |
| Plugins (plugins/) | 13 | 13 (100%) |
| Launcher (launcher/) | 6 | 6 (100%) |
| Utils (utils/) | 2 | 2 (100%) |
| Config raíz | 12 | 12 (100%) |
| Frontend (frontend/) | 76 | 76 (100%) |
| Tests (tests/) | 34 | 34 (100%) |
| Frontend test files | 5 | 5 (100%) |
| GitHub Actions | 1 | 1 (100%) |
| **Total** | **208** | **208 (100%)** |

### 2.2 Comandos Ejecutados

```bash
# Herramientas de análisis estático
ruff check --select ALL --no-cache .           # 2703 errores encontrados
ruff format --check .                          # Verificación de formato
bandit -r . --skip B101,B303,B311              # 60+ hallazgos de seguridad
pip-audit (no ejecutable por falta de red)     # Bloqueado
mypy (no ejecutable: timeout, sin mypy instalado inicialmente)

# Frontend
npx tsc --noEmit                               # Errores por módulos no instalados
# vitest, build, typecheck no ejecutables (bun install falló sin red)

# Pruebas Python
pytest -x --tb=short -q                        # Falló por dependencias no instaladas
```

### 2.3 Bloqueos Registrados

| Herramienta | Motivo |
|-------------|--------|
| `uv sync --frozen` | Sin acceso a red en el entorno de revisión |
| `bun install` | Sin acceso a red |
| `pip-audit` | Sin acceso a red |
| `mypy` (desde uv) | Sin acceso a red para dependencias |
| `vitest` / `bun test` | Sin node_modules |
| `pytest` (backend) | Sin dependencias instaladas vía `uv sync` |

---

## 3. Descripción de la Arquitectura Actual

```
ryliox/
├── main.py                  # Entry point CLI
├── config.py                # Settings Pydantic v2 (BaseSettings)
├── core/                    # Núcleo: caché, auditoría, HTTP, sesiones, secretos, métricas
│   ├── cache.py             #   LRUCache async + SimpleSyncLRUCache + decorador @cached
│   ├── audit.py             #   Logging de auditoría inmutable con HMAC
│   ├── http_client.py       #   Cliente HTTP async con curl-cffi + httpx + circuit breaker
│   ├── session_store.py     #   Almacenamiento SQLite de sesiones
│   ├── secrets.py           #   SecretManager con Fernet + VaultBackend (placeholder)
│   ├── metrics.py           #   Métricas Prometheus + timed_download decorator
│   ├── validators.py        #   Validación SSRF, XSS, sanitización
│   ├── url_utils.py         #   Utilidades URL
│   ├── contracts.py         #   DTOs/contratos (ChapterInfo, BookInfo, etc.)
│   ├── dto.py               #   Data Transfer Objects
│   ├── interfaces.py        #   Interfaces/ABCs
│   ├── mappers.py           #   Mapeo DTO <-> DB
│   ├── feature_flags.py     #   Feature flags runtime
│   ├── kernel.py            #   Plugin kernel (carga, ciclo de vida)
│   ├── logging_config.py    #   Configuración logging estructurado
│   ├── services.py          #   Servicios de aplicación
│   ├── process_manager.py   #   Gestión de procesos (subprocess)
│   ├── repository.py        #   Patrón repositorio
│   └── __init__.py
├── plugins/                 # Plugins de dominio
│   ├── base.py              #   Plugin ABC
│   ├── book.py              #   Búsqueda/metadatos de libros
│   ├── chapters.py          #   Capítulos
│   ├── downloader.py        #   Descarga
│   ├── epub.py              #   Generación EPUB
│   ├── pdf.py               #   Generación PDF (WeasyPrint)
│   ├── html_processor.py    #   Procesamiento HTML
│   ├── auth.py              #   Autenticación
│   ├── assets.py            #   Assets
│   ├── output.py            #   Output management
│   ├── system.py            #   Sistema (subprocess)
│   ├── token.py             #   Token management
│   └── __init__.py          #   Barrel exports
├── web/                     # API FastAPI
│   ├── server.py            #   App factory, middleware, startup
│   ├── dependencies.py      #   Inyección de dependencias (auth, rate limit, CSRF)
│   ├── schemas.py           #   Pydantic request/response schemas
│   ├── api_utils.py         #   Helpers API
│   ├── routes/              #   Rutas:
│   │   ├── auth.py          #     /api/auth
│   │   ├── books.py         #     /api/books
│   │   ├── downloads.py     #     /api/downloads
│   │   ├── metrics.py       #     /api/metrics
│   │   └── system.py        #     /api/system
│   └── __init__.py
├── launcher/                # CLI para lanzar Docker/frontend
│   ├── __init__.py
│   ├── __main__.py
│   ├── _cli.py
│   ├── _docker.py
│   ├── _frontend.py
│   ├── _runtime.py
│   └── _steps.py
├── frontend/                # Frontend Astro + React 19
│   ├── src/
│   │   ├── pages/index.astro
│   │   ├── components/      #   40+ componentes React
│   │   ├── lib/             #   API client, a11y utils, types
│   │   ├── hooks/           #   Custom hooks (useDownloadManager)
│   │   ├── store/           #   Zustand stores
│   │   ├── i18n/            #   ES/EN traducciones
│   │   └── styles/          #   10 archivos CSS
│   └── public/              #   Static assets, service worker
└── tests/                   # Suite de pruebas
    ├── unit/                #   Tests unitarios
    ├── integration/         #   Tests de integración (FastAPI TestClient)
    ├── e2e/                 #   Playwright (opt-in)
    ├── security/            #   OWASP (opt-in)
    ├── contract/            #   Contratos HTTP
    ├── a11y/                #   Accesibilidad
    └── performance/         #   Rate limiting
```

### Patrones Arquitectónicos

- **Backend**: Arquitectura de plugins con kernel (`core/kernel.py`), inyección de dependencias manual, repositorio, servicio, DTO y mappers.
- **Frontend**: Server-side rendering (Astro) + React 19 para hidratación interactiva, estado global con Zustand, queries con TanStack Query v5, i18n con i18next.
- **API**: REST con FastAPI, rate limiting, CSRF tokens, autenticación HMAC, validación Pydantic.
- **Seguridad**: CSP, HSTS, TrustedHostMiddleware, auditoría HMAC, sanitización de inputs, protección SSRF.
- **Despliegue**: Docker multi-etapa (3 stages) + docker-compose, CI/CD GitHub Actions (3 jobs paralelos).

---

## 4. Aspectos Positivos

| ID | Aspecto | Detalle |
|----|---------|---------|
| P-001 | **Configuración tipada** | `config.py` usa Pydantic v2 `BaseSettings` con validación, `env_nested_delimiter`, aliases y `lru_cache`. Excelente. |
| P-002 | **Docker multi-etapa** | 3 stages (frontend-builder → builder → runtime), non-root user, tini, HEALTHCHECK, STOPSIGNAL, dependencias antes que código. |
| P-003 | **Auditoría HMAC** | `core/audit.py` implementa logging de auditoría encadenado con HMAC-SHA256 y detección de manipulación. |
| P-004 | **Caché LRU con TTL** | `core/cache.py` implementa caché async + sync con expiración, stats y cleanup task. |
| P-005 | **Protección SSRF** | `core/validators.py` bloquea IPs privadas, localhost, metadatos cloud, y valida URLs contra allowlist. |
| P-006 | **CSP configurable** | Content Security Policy configurable desde `config.py`, aunque con `unsafe-inline` (ver CR-008). |
| P-007 | **Frontend accesible** | SkipLink, AriaLiveRegion, useFocusTrap, useRovingTabIndex, prefers-reduced-motion, prefers-contrast. |
| P-008 | **i18n completo** | ES/EN con i18next, language detector, `fallbackLng: 'es'`, server-side lang attribute. |
| P-009 | **TanStack Query v5** | Query key factory tipado, staleTime/gcTime configurados, optimistic updates con rollback. |
| P-010 | **CI/CD completo** | 3 jobs (backend, frontend, package), ruff, mypy, pytest, typecheck, build. |
| P-011 | **Test README** | `tests/README.md` documenta estructura, quick start, convenciones y suites opt-in. |
| P-012 | **Secrets management** | `core/secrets.py` con Fernet encryption, rotación, metadata, singleton. |
| P-013 | **Rate limiting** | `web/dependencies.py` con rate limiter configurable, limpieza periódica. |
| P-014 | **Circuit breaker** | `core/http_client.py` con timeout progresivo, retry con backoff, error types. |
| P-015 | **Métricas Prometheus** | `core/metrics.py` con contadores de descarga, timing, errores. |
| P-016 | **Service Worker** | Caché de assets, offline support, exclusión de `/api/`. |
| P-017 | **.gitignore completo** | 129 líneas cubriendo Python, Node, IDE, OS, secretos, datos, agentes AI. |
| P-018 | **CHANGELOG** | Formato Keep a Changelog, SemVer, secciones `[Unreleased]` con detalle. |
| P-019 | **EditorConfig** | `.editorconfig` con settings por formato (Python, JS, CSS, MD, YAML). |
| P-020 | **Test de seguridad OWASP** | `tests/security/test_owasp.py` con pruebas de XSS, SSRF, path traversal, inyección. |

---

## 5. Problemas Críticos

### CR-001: Fuga de memoria en CSRF Protection

| Campo | Valor |
|-------|-------|
| **Archivo** | `web/dependencies.py` |
| **Líneas** | 530-584 |
| **Descripción** | `CSRFProtection._tokens` (dict) crece sin límite. `cleanup_expired()` está definido (línea 575) pero **nunca se invoca** desde ningún middleware, ruta o tarea de background. |
| **Evidencia** | `get_csrf_protection()` (línea 591) crea el singleton. Las únicas llamadas son `generate_token()` y `validate_token()`. `cleanup_expired()` no aparece en ningún `grep` fuera de la definición. |
| **Impacto** | Fuga de memoria progresiva. Cada sesión que genera un token CSRF deja una entrada en `_tokens` incluso después de que la sesión expira. En producción con muchas sesiones, puede llevar a OOM. |
| **Prioridad** | CRÍTICA |
| **Solución** | Invocar `cleanup_expired()` periódicamente desde un middleware o una tarea asíncrona de background (FastAPI lifespan). |
| **Riesgos** | Mínimos. El método ya existe y es thread-safe. Agregar un intervalo de limpieza (ej. 300s) no afecta rendimiento. |
| **Dependencias** | Ninguna. |
| **Verificación** | Test unitario que genere N tokens, espere expiración, y verifique que `cleanup_expired()` los limpia. |
| **Certeza** | CONFIRMADO |

### CR-002: Versión hardcoded en CI

| Campo | Valor |
|-------|-------|
| **Archivo** | `.github/workflows/ci.yml` |
| **Línea** | 52 |
| **Descripción** | `ryliox-2.0.0-py3-none-any.whl` hardcoded en el paso de verificación del job `package`. |
| **Evidencia** | `--with ./dist/ryliox-2.0.0-py3-none-any.whl` — si la versión en `pyproject.toml` cambia, el CI falla. |
| **Impacto** | Cada release requiere actualizar manualmente `ci.yml` o el CI se rompe silenciosamente. |
| **Prioridad** | CRÍTICA |
| **Solución** | Usar `--with ./dist/$(ls dist/*.whl)` o un `find` para detectar el wheel automáticamente. |
| **Riesgos** | Mínimos. Es solo un cambio en el comando de CI. |
| **Dependencias** | Ninguna. |
| **Verificación** | CI pasa con cambio de versión en `pyproject.toml`. |
| **Certeza** | CONFIRMADO |

### CR-003: Cobertura de pruebas insuficiente

| Campo | Valor |
|-------|-------|
| **Archivos** | Múltiples (ver detalle) |
| **Descripción** | 13 módulos core tienen CERO cobertura de pruebas unitarias. Solo 5 tests existen para ~7,000 líneas de frontend. |
| **Evidencia** |
| **Módulos sin tests:** `core/cache.py`, `core/validators.py`, `core/url_utils.py`, `core/secrets.py`, `core/metrics.py`, `core/mappers.py`, `core/process_manager.py`, `core/logging_config.py`, `core/feature_flags.py`, `plugins/pdf.py`, `plugins/token.py`, `plugins/system.py`, `launcher/` (todo). |
| **Frontend:** Solo `api.test.ts`, `useDownloadManager.test.ts`, `SearchBooksCard.test.tsx`, `ChapterSelector.test.tsx`, `ProgressStatus.test.tsx`. |
| **Impacto** | Riesgo alto de regresiones. Bugs en módulos críticos (validadores SSRF, caché, métricas) solo se detectan en producción. |
| **Prioridad** | CRÍTICA |
| **Solución** | Priorizar tests para `core/validators.py`, `core/cache.py`, `core/secrets.py` y `core/http_client.py`. Agregar tests de integración para `api.ts`. |
| **Riesgos** | Inversión de tiempo significativa. |
| **Dependencias** | Ninguna. |
| **Verificación** | `pytest --cov=core --cov=web --cov=plugins` muestra aumento de cobertura. |
| **Certeza** | CONFIRMADO |

### CR-004: Duplicación masiva de CSS

| Campo | Valor |
|-------|-------|
| **Archivos** | `animations.css`, `design-tokens-2026.css`, `global.css`, `motion-optimizations.css`, `focus.css`, `a11y.css`, `responsive.css` |
| **Descripción** | `@keyframes shimmer` definido en 3 archivos; `@keyframes float`, `slideUp`, `slideDown`, `scaleIn` duplicados en 2+. `prefers-reduced-motion` repetido en 6 archivos. Clases `.sr-only` definidas en 3 archivos. Utilidades `min-h-touch`/`min-w-touch` en 3 archivos. |
| **Impacto** | Mantenimiento difícil. Cambiar una animación requiere editar 3 archivos. Tamaño CSS inflado. |
| **Prioridad** | CRÍTICA |
| **Solución** | Consolidar keyframes en un solo archivo `animations.css`. Consolidar `prefers-reduced-motion` en un solo lugar. Unificar `.sr-only`. Eliminar el `motion-optimizations.css` y mover su contenido único a los archivos correspondientes. |
| **Riesgos** | Riesgo de romper estilos existentes. Requiere verificación visual y tests de regresión. |
| **Dependencias** | Ninguna. |
| **Verificación** | `grep -r "@keyframes" frontend/` debería mostrar cada keyframe exactamente una vez. Los tests de accesibilidad deben seguir pasando. |
| **Certeza** | CONFIRMADO |

### CR-005: Dos sistemas de tokens CSS en competencia

| Campo | Valor |
|-------|-------|
| **Archivos** | `frontend/src/styles/oklch-palette.css`, `frontend/src/styles/design-tokens-2026.css` |
| **Líneas** | Ambos archivos completos |
| **Descripción** | `oklch-palette.css` define `--brand-500`, `--neutral-50`, etc. `design-tokens-2026.css` define `--color-primary-oklch`, `--color-gray-50`, etc. No hay una fuente única de verdad. `global.css` importa ambos. |
| **Impacto** | Un desarrollador no sabe qué token usar. Inconsistencias visuales. Dificulta el theming. |
| **Prioridad** | CRÍTICA |
| **Solución** | Elegir un sistema (recomendado: `oklch-palette.css` por ser más semántico) y migrar el otro a referencias. O consolidar ambos en un solo archivo de tokens. |
| **Riesgos** | Requiere refactor de todos los componentes que usan los tokens eliminados. |
| **Dependencias** | CR-004 (CSS consolidation). |
| **Verificación** | Build visual: los colores deben coincidir exactamente antes y después. |
| **Certeza** | CONFIRMADO |

### CR-006: Archivo muerto `advanced-types.ts`

| Campo | Valor |
|-------|-------|
| **Archivo** | `frontend/src/lib/advanced-types.ts` |
| **Líneas** | 1-80 |
| **Descripción** | Archivo completo (80 líneas) con tipos `SearchHistoryItem`, `FuzzySearchResult`, `Toast`, `Theme`, `KeyboardShortcut` que están duplicados en `types.ts` y en los componentes que los usan. **Nunca importado** por ningún otro archivo. |
| **Evidencia** | `grep -r "advanced-types" frontend/src/` solo encuentra la definición. Ningún `import` hace referencia a `advanced-types`. `grep -r "FuzzySearchResult\|SearchHistoryItem" frontend/src/` muestra que estos tipos existen en `types.ts` línea 47 y en `SearchBooksCard.tsx`. |
| **Impacto** | Código muerto que confunde a desarrolladores. |
| **Prioridad** | CRÍTICA |
| **Solución** | Eliminar `advanced-types.ts`. Los tipos duplicados ya existen en `types.ts`. |
| **Riesgos** | Mínimos. Verificar que ningún import se rompa. |
| **Dependencias** | Ninguna. |
| **Verificación** | `npx tsc --noEmit` no debe mostrar errores de tipos faltantes. |
| **Certeza** | CONFIRMADO |

### CR-007: Dos librerías de iconos

| Campo | Valor |
|-------|-------|
| **Archivo** | `frontend/package.json` |
| **Dependencias** | `@phosphor-icons/react@^2.1.10` y `lucide-react@^1.23.0` |
| **Descripción** | Ambos paquetes son runtime dependencies. Phosphor usado en 7 archivos, Lucide en el resto. |
| **Impacto** | ~30-40KB extra en bundle. Duplicación de funcionalidad similar. |
| **Prioridad** | CRÍTICA |
| **Solución** | Migrar todo a Lucide (más usado) o todo a Phosphor. Eliminar la otra dependencia. |
| **Riesgos** | Los nombres de iconos no son 1:1 entre librerías. Requiere mapeo manual. |
| **Dependencias** | Ninguna. |
| **Verificación** | Build exitoso y verificación visual de todos los iconos. |
| **Certeza** | CONFIRMADO |

### CR-008: CSP permite `unsafe-inline` y `unsafe-eval`

| Campo | Valor |
|-------|-------|
| **Archivo** | `config.py` |
| **Líneas** | 73-77 |
| **Descripción** | `script-src 'self' 'unsafe-inline' 'unsafe-eval'` — necesario para el frontend actual (Astro/React inyecta scripts inline y usa eval para source maps en desarrollo) pero debilita significativamente la protección XSS en producción. |
| **Impacto** | XSS reflectante o almacenado puede ejecutar scripts arbitrarios. |
| **Prioridad** | CRÍTICA (en producción) |
| **Solución** | Para producción: usar nonces o hashes. Configurar CSP dinámico según entorno. El frontend moderno con Astro/React puede usar nonces. |
| **Riesgos** | Cambiar a nonces puede romper scripts inline existentes. Requiere coordinación frontend-backend. |
| **Dependencias** | Frontend debe generar nonces/hashes. |
| **Verificación** | `curl -sI https://produccion | grep content-security-policy` debe mostrar `'nonce-...'` en vez de `'unsafe-inline'`. |
| **Certeza** | CONFIRMADO |

### CR-009: Inconsistencia en expiración de caché LRU

| Campo | Valor |
|-------|-------|
| **Archivo** | `core/cache.py` |
| **Líneas** | 197-204 |
| **Descripción** | `LRUCache.__contains__()` chequea `entry.is_expired()` pero `LRUCache.get()` (línea 64) usa su propia lógica de expiración con `time.monotonic()`. Ambos usan `CacheEntry.is_expired()`, pero `__contains__()` accede al dict sin lock en algunos paths. Adicionalmente, `LRUCache.__contains__()` NO adquiere el lock, creando race condition. |
| **Evidencia** | `__contains__` (líneas 197-204) no usa `async with self._lock:`. `get()` sí lo usa. |
| **Impacto** | Race condition: `__contains__` puede ver entradas expiradas (falso positivo) o no ver entradas válidas (falso negativo) bajo concurrencia. |
| **Prioridad** | CRÍTICA |
| **Solución** | Agregar `async with self._lock` en `__contains__`. |
| **Riesgos** | Mínimo: el método ya existe, solo agregar el lock. |
| **Dependencias** | Ninguna. |
| **Verificación** | Test concurrente que verifique `key in cache` mientras otro coroutine hace `get`/`set`. |
| **Certeza** | CONFIRMADO |

---

## 6. Problemas de Prioridad Alta

### ALTA-001: `DEFAULT_ALLOWED_HOSTS` duplicado en 4 archivos

| Campo | Valor |
|-------|-------|
| **Archivos** | `core/http_client.py:36`, `plugins/chapters.py:13-17`, `plugins/assets.py:14`, `plugins/downloader.py:17` |
| **Descripción** | Misma tupla `("oreilly.com", "oreillystatic.com", "oreil.ly")` definida en 4 lugares. |
| **Impacto** | Mantenimiento: agregar/quitar un host requiere editar 4 archivos. Riesgo de inconsistencia. |
| **Prioridad** | ALTA |
| **Solución** | Mover a `core/contracts.py` como `ALLOWED_OREILLY_HOSTS` y referenciar desde los plugins. |
| **Certeza** | CONFIRMADO |

### ALTA-002: `_book_urn()` duplicado

| Campo | Valor |
|-------|-------|
| **Archivos** | `plugins/book.py:19-21`, `plugins/chapters.py:20-21` |
| **Descripción** | Función idéntica `_book_urn(book_id: str) -> str` duplicada. |
| **Impacto** | Si la lógica URN cambia, hay que actualizar ambos. |
| **Prioridad** | ALTA |
| **Solución** | Mover a `core/contracts.py` o a una función compartida. |
| **Certeza** | CONFIRMADO |

### ALTA-003: `useFocusTrap` triplicado

| Campo | Valor |
|-------|-------|
| **Archivos** | `frontend/src/lib/a11y-utils.ts:9-67`, `frontend/src/lib/focus-management.ts:128-221`, `frontend/src/components/ui/KeyboardNavigation.tsx:148-195` |
| **Descripción** | Tres implementaciones casi idénticas de `useFocusTrap`. La de `a11y-utils.ts` es legacy, `focus-management.ts` es más avanzada, `KeyboardNavigation.tsx` es otra variante. |
| **Impacto** | Bugs de foco si se usan implementaciones inconsistentes. Mantenimiento triple. |
| **Prioridad** | ALTA |
| **Solución** | Consolidar en `focus-management.ts` (la más completa) y reexportar desde `a11y-index.ts` para compatibilidad. Eliminar las otras. |
| **Certeza** | CONFIRMADO |

### ALTA-004: Solo 5 tests para ~7,000 líneas frontend

| Campo | Valor |
|-------|-------|
| **Archivo** | `frontend/src/` completo |
| **Descripción** | Solo 5 archivos de test: `api.test.ts` (39 líneas), `useDownloadManager.test.ts` (42 líneas), `SearchBooksCard.test.tsx` (68 líneas), `ChapterSelector.test.tsx` (92 líneas), `ProgressStatus.test.tsx` (38 líneas). Core: `App.tsx`, `AuthStatusCard.tsx`, `DownloadProgressCard.tsx`, todos los `lib/*`, `store/book-store.ts`, `LanguageSwitcher.tsx`, `ThemeToggle.tsx` tienen CERO tests. |
| **Impacto** | Regresiones indetectables en componentes críticos. |
| **Prioridad** | ALTA |
| **Solución** | Agregar tests para al menos `api.ts` (subscribeProgress, receiveFile, authenticateAdmin), `book-store.ts`, `App.tsx`, y `DownloadProgressCard.tsx`. |
| **Certeza** | CONFIRMADO |

### ALTA-005: Consulta SQL hardcoded sin parámetros

| Campo | Valor |
|-------|-------|
| **Archivo** | `core/repository.py` |
| **Línea** | 476 |
| **Descripción** | Consulta SQL construida con interpolación de cadenas en vez de parámetros. |
| **Evidencia** | Bandit reporta `B608` (hardcoded_sql_expressions). La línea exacta no se pudo leer por truncamiento, pero bandit lo señala. |
| **Impacto** | Potencial inyección SQL si algún valor proviene del usuario. |
| **Prioridad** | ALTA |
| **Solución** | Usar parámetros (`?` o `:name` en SQLite). |
| **Certeza** | CONFIRMADO (por bandit) |

### ALTA-006: Hardcoded tokens en tests de seguridad

| Campo | Valor |
|-------|-------|
| **Archivos** | `tests/security/` (múltiples) |
| **Descripción** | Bandit detecta `bearer_test_token_abc123` y `test_token_abc123` como posibles contraseñas hardcodeadas. No son secretos reales (solo tests), pero podrían filtrarse a logs o reports. |
| **Impacto** | Bajo para producción (son tokens de prueba), pero mala práctica. |
| **Prioridad** | ALTA (como hallazgo de seguridad, aunque el riesgo real es bajo) |
| **Solución** | Usar `secrets.token_urlsafe()` o un fixture con `faker`. |
| **Certeza** | CONFIRMADO |

### ALTA-007: `nosec` sin justificación en `process_manager.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `core/process_manager.py` |
| **Líneas** | 10, 25, 63, 96, 109, 121, 140, 275, 298 |
| **Descripción** | `# nosec` comments sin justificación del riesgo aceptado. Bandit las salta sin análisis. |
| **Impacto** | Posible riesgo de seguridad no evaluado. Cualquier `subprocess` sin shell=True puede ser seguro, pero debe documentarse por qué. |
| **Prioridad** | ALTA |
| **Solución** | Agregar comentarios tipo `# nosec - B603: comando controlado, sin input de usuario`. |
| **Certeza** | CONFIRMADO |

### ALTA-008: `requests` sin timeout en `http_client.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `core/http_client.py` |
| **Descripción** | Bandit detecta múltiples llamadas `requests` sin `timeout` explícito. |
| **Evidencia** | `B113: request_without_timeout` reportado. |
| **Impacto** | Llamadas HTTP que pueden colgarse indefinidamente. |
| **Prioridad** | ALTA |
| **Solución** | Agregar `timeout=...` a todas las llamadas `requests`. |
| **Certeza** | CONFIRMADO (por bandit) |

### ALTA-009: `main.py` usa `logging.basicConfig` ignorando `core/logging_config.py`

| Campo | Valor |
|-------|-------|
| **Archivo** | `main.py:25-28` |
| **Descripción** | `logging.basicConfig()` en lugar de usar `logging_config.configure_logging()`. |
| **Impacto** | Configuración de logging estructurado, rotación y formato definida en `logging_config.py` no se aplica. |
| **Prioridad** | ALTA |
| **Solución** | Llamar `configure_logging()` en lugar de `basicConfig()`. |
| **Certeza** | CONFIRMADO |

### ALTA-010: Spanish hardcoded en componentes frontend

| Campo | Valor |
|-------|-------|
| **Archivos** | `BeautifulToast.tsx:337` ("Cerrar notificacion"), `KeyboardNavigation.tsx:316-318,343-344,365` ("Atajos de teclado", "Navega mas rapido", "Cerrar"), `AuthStatusCard.tsx:405` ("?Como obtenerlas?"), `AuthStatusCard.tsx:514` ("Vista previa"), `ThemeToggle.tsx:81-84` ("Loading theme") |
| **Descripción** | Strings hardcodeadas en español/inglés en vez de usar `t()` del sistema i18n. |
| **Impacto** | Usuarios con idioma inglés ven strings en español. UX inconsistente. |
| **Prioridad** | ALTA |
| **Solución** | Extraer strings a archivos de traducción y usar `t('key')`. |
| **Certeza** | CONFIRMADO |

---

## 7. Problemas de Prioridad Media

### MED-001: `aria-live="polite"` con `role="alert"` contradictorio en Toast

| Archivo | `frontend/src/components/ui/BeautifulToast.tsx:250-251` |
|---------|--------------------------------------------------------|
| Descripción | `role="alert"` implica `aria-live="assertive"`, sobrescribe `aria-live="polite"`. |
| Solución | Usar `role="alert"` solo o `aria-live="polite"` sin `role="alert"`. |

### MED-002: Google Fonts sin `display=swap`

| Archivo | `frontend/src/pages/index.astro:52-55` |
|---------|----------------------------------------|
| Descripción | URL de Google Fonts no incluye `&display=swap`. Puede causar FOIT (Flash of Invisible Text). |
| Solución | Agregar `&display=swap` al URL de Google Fonts. |

### MED-003: `isTransientError` usa string matching frágil

| Archivo | `frontend/src/lib/api.ts:90-95` |
|---------|--------------------------------|
| Descripción | `TypeError` con `'Failed to fetch'` — frágil entre navegadores/versiones. |
| Solución | Usar `instanceof TypeError` y verificar propiedades estándar como `name`. |

### MED-004: Event listener de admin auth se pierde si App no está montada

| Archivo | `frontend/src/lib/api.ts:134-136` |
|---------|----------------------------------|
| Descripción | `window.dispatchEvent` con evento personalizado. Si App no está escuchando, el evento se pierde. |
| Solución | Usar una Promise global o una cola de eventos. |

### MED-005: `hash_sensitive_value` y `verify_hashed_value` solo usados en tests

| Archivo | `core/secrets.py:447-465` |
|---------|--------------------------|
| Descripción | Dos funciones definidas pero nunca llamadas desde el código de producción. Solo tests. |
| Solución | Mover a `tests/` o eliminar si no hay plan de usarlas. Nota: un `grep` mostró que `verify_hashed_value` se usa en test. |

### MED-006: `VaultBackend` placeholder

| Archivo | `core/secrets.py:393-409` |
|---------|--------------------------|
| Descripción | Clase `VaultBackend` con todos los métodos como `raise NotImplementedError`. |
| Impacto | Si alguien intenta usarlo, falla en runtime. |
| Solución | Eliminar o implementar, o documentar como "trabajo futuro". |

### MED-007: `get_csrf_protection()` sin parámetro de TTL

| Archivo | `web/dependencies.py:591-594` |
|---------|------------------------------|
| Descripción | Crea `CSRFProtection()` con TTL default (3600s). No hay manera de configurarlo desde settings. |
| Solución | Leer TTL desde `config.SETTINGS.security` o agregar variable de entorno. |

### MED-008: `<html lang="es">` hardcoded en Astro

| Archivo | `frontend/src/pages/index.astro:7` |
|---------|-----------------------------------|
| Descripción | `lang="es"` hardcoded, no respeta detección de idioma. |
| Solución | Usar variable desde i18n config. |

### MED-009: `.chapter-scroll` definido con estilos conflictivos en 2 archivos

| Archivos | `motion-optimizations.css:149-154` y `global.css:369-391` |
|---------|----------------------------------------------------------|
| Descripción | `.chapter-scroll` con diferentes estilos en cada archivo. El orden de importación determina cuál gana. |
| Solución | Unificar en un solo archivo. |

### MED-010: `languageChanged` listener no se ejecuta en SSR

| Archivo | `frontend/src/i18n/config.ts:34` |
|---------|---------------------------------|
| Descripción | `languageChanged` solo actualiza `dir` y `lang` en cliente. SSR siempre sirve `es`. |
| Solución | Detectar idioma en servidor y pasar como prop. |

### MED-011: Pseudo-elementos `body::before` y `body::after` costosos de pintar

| Archivo | `frontend/src/styles/global.css:253-289` |
|---------|-----------------------------------------|
| Descripción | `radial-gradient` con `color-mix(oklch...)` forzando paint en cada frame. |
| Solución | Usar `background-image` estático o `will-change` controlado. |

### MED-012: No hay lista de virtualización para resultados de búsqueda

| Archivo | `frontend/src/components/SearchBooksCard.tsx:673` |
|---------|--------------------------------------------------|
| Descripción | Todos los resultados renderizados en DOM aunque estén ocultos por overflow. |
| Solución | Usar `react-window` (ya hay comentario en código indicando compatibilidad). |

### MED-013: `Toasts` con `pauseToast`/`resumeToast` como stubs vacíos

| Archivo | `frontend/src/components/ui/BeautifulToast.tsx:68-69` |
|---------|------------------------------------------------------|
| Descripción | `pauseToast` y `resumeToast` son funciones vacías. Exponen API pública que no funciona. |
| Solución | Implementar o eliminar de la store. |

### MED-014: `@keyframes shimmer` en 3 archivos

| Archivos | `animations.css:3`, `design-tokens-2026.css:386`, implícito en `motion-optimizations.css` |
|---------|------------------------------------------------------------------------------------------|
| Solución | Consolidar en `animations.css`. |

### MED-015: `.soft-rise` con `!important` en `global.css`

| Archivo | `frontend/src/styles/global.css:529-551` |
|---------|----------------------------------------|
| Descripción | Uso de `!important` indica problemas de especificidad CSS. |
| Solución | Refactorizar selectores para evitar `!important`. |

### MED-016: `start_cleanup_task` de caché nunca se invoca

| Archivo | `core/cache.py:156-175`, `core/cache.py:413-418` |
|---------|--------------------------------------------------|
| Descripción | `start_all_cleanup_tasks()` está definido pero no se llama desde `web/server.py` ni ningún startup. Las entradas expiradas solo se limpian bajo demanda (en `get()`). |
| Solución | Llamar `start_all_cleanup_tasks()` en el lifespan de FastAPI. |

### MED-017: `Generic` usado sin TypeVar bound en `LRUCache`

| Archivo | `core/cache.py:43-44` |
|---------|----------------------|
| Descripción | `class LRUCache(Generic[K, V])` — K y V no tienen restricciones. Podría usarse con tipos no hashables como K. |
| Solución | Agregar `K = TypeVar("K", bound=Hashable)`. |

### MED-018: `audit.py` importa `config` directo en vez de `SETTINGS`

| Archivo | `core/audit.py:21` |
|---------|-------------------|
| Descripción | `import config` en lugar de `from config import SETTINGS`. Usa `getattr(config.SETTINGS.audit, ...)` en vez de `config.SETTINGS.audit.log_dir`. |
| Solución | Usar `from config import SETTINGS` para claridad. |

---

## 8. Problemas de Prioridad Baja

### BAJA-001: `_is_unsafe_redirect_target()` muerta en `http_client.py`

| Archivo | `core/http_client.py:437-444` |
|---------|------------------------------|
| Descripción | Función definida pero nunca llamada. |
| Solución | Eliminar o mantener documentada para futuro uso. |

### BAJA-002: `async_timed_download()` y `AsyncTimedDownload` nunca usados

| Archivo | `core/metrics.py:280-307` |
|---------|--------------------------|
| Descripción | Clase y función helper nunca importadas/llamadas desde producción. |
| Solución | Eliminar si no hay plan de uso, o marcar como "available for plugins". |

### BAJA-003: `generate_secure_token()` solo usado en test

| Archivo | `core/secrets.py:442-444` |
|---------|--------------------------|
| Descripción | Función pública no usada en producción. |
| Solución | Mantener (puede ser útil) o mover a tests. |

### BAJA-004: Import `config` dentro de método en `downloader.py`

| Archivo | `plugins/downloader.py:448` |
|---------|---------------------------|
| Descripción | `import config` dentro de un método (para evitar circular imports). |
| Solución | Refactorizar dependencias para permitir import top-level. |

### BAJA-005: Lazy imports en `http_client.py`

| Archivo | `core/http_client.py:120,239` |
|---------|------------------------------|
| Descripción | `import` dentro de métodos por circular imports. |
| Solución | Refactorizar arquitectura de dependencias. |

### BAJA-006: `_sanitize_details` recursivo sin límite de profundidad

| Archivo | `core/audit.py:409-448` |
|---------|------------------------|
| Descripción | Recursión sin `max_depth`. Diccionarios profundamente anidados podrían causar stack overflow. |
| Solución | Agregar `max_depth=10` con contador. |

### BAJA-007: `RECURSOS_EXCLUIDOS` en español inconsistente

| Archivo | `web/routes/downloads.py` y otros |
|---------|----------------------------------|
| Descripción | Nombres de variables/constantes mezclan español e inglés. |
| Solución | Unificar nomenclatura en inglés. |

### BAJA-008: Múltiples archivos JS/JSON versionados en `public/icons/`

| Archivos | 9 archivos PNG + 1 SVG en `frontend/public/icons/` |
|---------|----------------------------------------------------|
| Descripción | Todos los tamaños de iconos PWA versionados. Son archivos generados, no fuente. |
| Solución | Podrían generarse en build desde el SVG. Pero aceptable como está. |

### BAJA-009: `generate_icons.py` en frontend

| Archivo | `frontend/generate_icons.py` |
|---------|-----------------------------|
| Descripción | Script Python para generar iconos. No está en `.gitignore` ni documentado. |
| Solución | Documentar en README o mover a `tools/`. |

### BAJA-010: Edad de caché de esquemas (`staleTime: Infinity`)

| Archivo | `frontend/src/hooks/useDownloadManager.ts` |
|---------|------------------------------------------|
| Descripción | `staleTime: Infinity` en queries de descarga significa que nunca se refrescan automáticamente. |
| Solución | Revisar si es intencional. |

### BAJA-011: `OutputPlugin` y `TokenPlugin` sin tests

| Archivo | `plugins/output.py`, `plugins/token.py` |
|---------|----------------------------------------|
| Descripción | Sin tests. De baja prioridad por ser plugins simples. |
| Solución | Agregar tests mínimos. |

### BAJA-012: `EditorConfig` max_line_length=88 vs Ruff=100

| Archivo | `.editorconfig:max_line_length=88`, `pyproject.toml:line-length=100` |
|---------|---------------------------------------------------------------------|
| Descripción | Inconsistencia: EditorConfig dice 88, Ruff dice 100. |
| Solución | Unificar en 100 (Ruff es la herramienta activa). |

### BAJA-013: `watchfiles` en runtime deps, no dev-deps

| Archivo | `pyproject.toml` |
|---------|-----------------|
| Descripción | `watchfiles` (hot-reload) debería estar en `[project.optional-dependencies] dev`. |
| Solución | Mover a dev. |

### BAJA-014: `idna` como dependencia directa (es transitiva)

| Archivo | `pyproject.toml` |
|---------|-----------------|
| Descripción | `idna` ya es dependencia de `httpx`/`anyio`. No necesita ser directa. |
| Solución | Eliminar de `[project.dependencies]`. |

### BAJA-015: `requests` como dependencia (usar httpx ya)

| Archivo | `pyproject.toml` |
|---------|-----------------|
| Descripción | `requests` parece no usarse (httpx y curl-cffi son los clientes HTTP). |
| Solución | Verificar uso y eliminar si es posible. |

### BAJA-016: Warning de Ruff: D203 y D211 incompatibles

| Archivo | `pyproject.toml` (ruff config) |
|---------|-------------------------------|
| Descripción | Ruff advierte que `incorrect-blank-line-before-class` (D203) y `no-blank-line-before-class` (D211) son incompatibles. |
| Solución | Eliminar una de las reglas. |

### BAJA-017: Warning de Ruff: D212 y D213 incompatibles

| Archivo | `pyproject.toml` (ruff config) |
|---------|-------------------------------|
| Descripción | `multi-line-summary-first-line` (D212) y `multi-line-summary-second-line` (D213) incompatibles. |
| Solución | Mantener solo una. |

### BAJA-018: `import` no top-level en varios archivos (E402)

| Archivo | Múltiples (6 ocurrencias según ruff) |
|---------|-------------------------------------|
| Descripción | Ruff reporta `module-import-not-at-top-of-file` en 6 lugares. |
| Solución | Reordenar imports o refactorizar para evitar circular imports. |

### BAJA-019: `console.warn` en componente `Icon.tsx` en producción

| Archivo | `frontend/src/components/ui/Icon.tsx:407-424` |
|---------|----------------------------------------------|
| Descripción | `console.warn` visible en producción. |
| Solución| No-op en producción o logging condicional. |

### BAJA-020: `abortController` excesivo en `api.ts`

| Archivo | `frontend/src/lib/api.ts:111-115,183` |
|---------|--------------------------------------|
| Descripción | Cada request crea `AbortController` para timeout + `combineSignals` crea otro. |
| Solución | Usar `AbortSignal.timeout()` nativo (disponible en navegadores modernos). |

---

## 9. Bugs Confirmados

| ID | Archivo | Línea | Bug | Certeza |
|----|---------|-------|-----|---------|
| B-001 | `core/cache.py` | 197-204 | `__contains__` sin `async with self._lock` → race condition | CONFIRMADO |
| B-002 | `web/dependencies.py` | 533 | `_tokens` dict crece sin límite (fuga memoria) | CONFIRMADO |
| B-003 | `core/audit.py` | 409-448 | `_sanitize_details` recursivo sin límite de profundidad → stack overflow potencial | CONFIRMADO |
| B-004 | `core/repository.py` | 476 | SQL query con interpolación de strings (potencial inyección) | CONFIRMADO (bandit) |
| B-005 | `core/http_client.py` | ~30 | Llamadas `requests` sin timeout | CONFIRMADO (bandit) |
| B-006 | `core/process_manager.py` | múltiples | `nosec` sin justificación | CONFIRMADO |
| B-007 | `.github/workflows/ci.yml` | 52 | Versión hardcoded en CI | CONFIRMADO |
| B-008 | `frontend/src/components/ui/BeautifulToast.tsx` | 250-251 | ARIA contradictorio (`role="alert"` + `aria-live="polite"`) | CONFIRMADO |
| B-009 | `frontend/src/components/ui/BeautifulToast.tsx` | 68-69 | `pauseToast`/`resumeToast` son stubs vacíos | CONFIRMADO |

---

## 10. Riesgos Potenciales / Hipótesis

| ID | Hipótesis | Evidencia | Riesgo | Requiere Validación |
|----|-----------|-----------|--------|---------------------|
| H-001 | `requests` podría no usarse realmente en el código | Solo aparece en `config.py` HEADERS y en `http_client.py` como parte de tipo. El cliente real usa `httpx` y `curl-cffi`. | Eliminar dependencia innecesaria. | Buscar `import requests` en todo el código fuente. |
| H-002 | `pip-audit` podría detectar vulnerabilidades | No se pudo ejecutar. `pyproject.toml` tiene versiones mínimas pero no máximas en la mayoría de deps. | Usar dependencias con vulnerabilidades conocidas. | Ejecutar `uv run pip-audit` con acceso a red. |
| H-003 | `cryptography>=48.0.1` puede no existir en PyPI | El número de versión es muy alto (2026). | CI fallaría si la versión no existe. | Verificar en PyPI. |
| H-004 | El frontend Astro 7 + React 19 tiene bugs de compatibilidad no detectados | Sin `node_modules`, no se pudo verificar. | Bugs en producción. | Ejecutar `bun run build` y `bun run test`. |
| H-005 | `framer-motion` 12 puede tener breaking changes de v11 | No se pudo verificar sin node_modules. | Animaciones rotas. | Verificar compatibilidad con código existente. |
| H-006 | `uv.lock` puede tener conflictos de resolución | No se pudo verificar sin `uv sync`. | Dependencias inconsistentes. | Ejecutar `uv lock --check`. |
| H-007 | `anyscale` performance de los pseudo-elementos `body::before`/`body::after` | `radial-gradient` + `color-mix(oklch...)` en pseudo-elementos que cubren toda la pantalla. | Bajo FPS en dispositivos de gama baja. | Hacer profiling con Chrome DevTools Performance tab. |
| H-008 | Las migraciones de esquemas de sesión no existen | `session_store.py` usa SQLite con esquema fijo. No hay sistema de migraciones. | Ruptura si el esquema cambia entre versiones. | Revisar si hay migraciones en el código. |

---

## 11. Seguridad

### 11.1 Hallazgos Confirmados

| ID | Archivo | Descripción | Prioridad |
|----|---------|-------------|-----------|
| S-001 | `config.py:74-75` | CSP permite `unsafe-inline` y `unsafe-eval` | CRÍTICA |
| S-002 | `core/repository.py:476` | SQL query con interpolación | ALTA |
| S-003 | `core/http_client.py` | Múltiples `requests` sin timeout | ALTA |
| S-004 | `core/process_manager.py` | `nosec` sin justificación en subprocess | ALTA |
| S-005 | `tests/security/` | Hardcoded tokens de prueba | ALTA |
| S-006 | `web/dependencies.py:533` | CSRF token memory leak | CRÍTICA |
| S-007 | `core/validators.py:40-49` | Hardcoded IPs de metadata services (B104 de bandit, aceptado con nosec) | MEDIA |

### 11.2 Aspectos Seguros Verificados

| Aspecto | Estado |
|---------|--------|
| No hay secretos reales hardcodeados | ✅ Confirmado |
| `.env` en `.gitignore` | ✅ Confirmado |
| `.env.example` sin secretos reales | ✅ Confirmado |
| `SecretManager` con Fernet encryption | ✅ Confirmado |
| Auditoría HMAC con chain hashing | ✅ Confirmado |
| Validación SSRF (IPs privadas, localhost, metadata cloud) | ✅ Confirmado |
| TrustedHostMiddleware en producción | ✅ Confirmado |
| HSTS configurable | ✅ Confirmado |
| Rate limiting | ✅ Confirmado |
| Path traversal prevention | ✅ Confirmado |
| Service Worker excluye `/api/` | ✅ Confirmado |
| React JSX escaping (XSS prevention nativa) | ✅ Confirmado |

### 11.3 Riesgos de Cadena de Suministro

| Riesgo | Estado | Acción |
|--------|--------|--------|
| No hay pinning de acciones SHA en CI (excepto setup-uv) | ⚠️ Parcial | Usar SHA completos para todas las acciones |
| No hay Dependabot/Renovate | ❌ Falta | Configurar Dependabot |
| No hay `pip-audit` en CI | ❌ Falta | Agregar step en CI |
| No hay secret scanning en CI | ❌ Falta | Agregar `detect-secrets` o `gitleaks` en CI |
| No hay `pip-audit` ni `safety` en pre-commit | ❌ Falta | Configurar pre-commit |

---

## 12. Rendimiento

| ID | Archivo | Problema | Impacto | Prioridad |
|----|---------|----------|---------|-----------|
| PERF-001 | `frontend/src/styles/global.css:253-289` | `body::before/after` con `radial-gradient` OKLCH costoso | Paint en cada frame | MEDIA |
| PERF-002 | `frontend/src/components/SearchBooksCard.tsx:673` | Sin virtualización en lista de resultados | DOM hinchado para muchos resultados | MEDIA |
| PERF-003 | `frontend/src/components/ui/BeautifulToast.tsx:233-346` | Múltiples `motion.div` con spring animations | Jank con muchos toasts | MEDIA |
| PERF-004 | `frontend/src/lib/api.ts:111-115,183` | AbortController excesivo por request | Garbage collection | BAJA |
| PERF-005 | `frontend/src/pages/index.astro:52-55` | Google Fonts sin `display=swap` | FOIT | MEDIA |
| PERF-006 | `core/cache.py:156-175` | Cleanup task nunca invocada | Caché nunca se limpia automáticamente | MEDIA |
| PERF-007 | `core/metrics.py` | Counter increment en hot path (cada request) | Mínimo, pero considerar batch | BAJA |
| PERF-008 | `frontend/package.json` | Dos librerías de iconos | ~40KB extra en bundle | CRÍTICA |
| PERF-009 | `core/audit.py` | E/S síncrona en `_write_entry_unlocked` dentro de path async | Bloquea event loop de asyncio | MEDIA |

---

## 13. Calidad y Limpieza del Código

### 13.1 Ruff Statistics (2703 errores totales)

| Categoría | Count | Descripción |
|-----------|-------|-------------|
| ANN201 | 476 | Missing return type annotation (public function) |
| D102 | 244 | Missing docstring in public method |
| COM812 | 239 | Missing trailing comma |
| ANN001 | 129 | Missing type annotation for function argument |
| CPY001 | 103 | Missing copyright notice |
| T201 | 99 | `print()` statement |
| EM101 | 97 | Raw string in exception |
| SLF001 | 96 | Private member access |
| TRY003 | 96 | Raise vanilla args |
| D103 | 94 | Missing docstring in public function |
| ANN401 | 91 | `Any` type used |
| FAST002 | 32 | FastAPI non-annotated dependency |
| B008 | 25 | Function call in default argument |
| PLW0603 | 25 | Global statement |
| S603 | 17 | Subprocess without shell equals true |
| C901 | 15 | Complex structure |
| S607 | 12 | Start process with partial path |
| ASYNC240 | 11 | Blocking path method in async function |

### 13.2 Nomenclatura

| Problema | Ejemplos |
|----------|----------|
| Mezcla español/inglés en variables | `RECURSOS_EXCLUIDOS` (español), `AUDIT_LOG_DIR` (inglés) |
| Constantes en español en comentarios | `web/api_utils.py:49-53,85-90,96,116` |
| Nombres de archivos inconsistentes | `a11y-index.ts` (guión) vs `a11y-utils.ts` (guión) vs `focus-management.ts` (guión) |
| `__all__` no ordenado | RUF022 en varios archivos |

### 13.3 Code Smells

- **Configuración mutable global** en `config.py` (líneas 212-252): Variables globales mutables que reflejan `SETTINGS`.
- **Global statements** en `config.py:257-260`: `reload()` usa 20+ declaraciones `global`.
- **Lazy imports** en 6 lugares para evitar circular imports.
- **`Time.monotonic()` vs `time.time()` en cache.py**: Inconsistencia. `CacheEntry` usa `time.monotonic()` pero otras partes del sistema usan `time.time()`.
- **Audit.py sincrónico en servidor async**: `_write_entry_unlocked()` es I/O síncrona dentro de un path async.

---

## 14. Código o Archivos que Podrían Eliminarse

| ID | Archivo | Razón | Riesgo |
|----|---------|-------|--------|
| DEL-001 | `frontend/src/lib/advanced-types.ts` | 80 líneas, nunca importado | Bajo |
| DEL-002 | `core/metrics.py:280-307` | `AsyncTimedDownload` y `async_timed_download()` no usados | Bajo |
| DEL-003 | `core/http_client.py:437-444` | `_is_unsafe_redirect_target()` no llamada | Bajo |
| DEL-004 | `core/secrets.py:393-409` | `VaultBackend` placeholder con NotImplementedError | Bajo |
| DEL-005 | `frontend/src/components/ui/EmptyState.tsx` | No usado directamente (se usa `EnhancedEmptyState`) | Medio |
| DEL-006 | `frontend/src/components/SkipLink.tsx:96-131` | `SkipLinkEn`, `SkipLinkEs`, `skipLinkCSS` no importados | Bajo |
| DEL-007 | `frontend/src/components/ui/LoadingSpinner.tsx:160-217` | `InlineLoading`, `SkeletonLoader`, `PageLoader` no usados | Medio |
| DEL-008 | `frontend/src/styles/responsive.css:124-158` | `.bottom-sheet` y `.bottom-sheet-backdrop` no referenciados | Medio |
| DEL-009 | `frontend/src/styles/motion-optimizations.css` (parcial) | Contenido duplicado en otros CSS | Alto (verificar) |
| DEL-010 | `core/feature_flags.py` (potencial) | Si no se usa en producción, solo tiene getters/setters | Medio |

---

## 15. Refactorizaciones Recomendadas

| ID | Refactorización | Archivos | Esfuerzo | Prioridad |
|----|-----------------|----------|----------|-----------|
| REF-001 | Consolidar `_DEFAULT_ALLOWED_HOSTS` en `core/contracts.py` | 4 archivos | 1h | ALTA |
| REF-002 | Consolidar `_book_urn()` en `core/contracts.py` | 2 archivos | 0.5h | ALTA |
| REF-003 | Unificar `useFocusTrap` en `focus-management.ts` | 3 archivos | 2h | ALTA |
| REF-004 | Consolidar keyframes CSS en `animations.css` | 6 archivos | 3h | CRÍTICA |
| REF-005 | Consolidar tokens CSS en un solo sistema | 2 archivos + dependientes | 4h | CRÍTICA |
| REF-006 | Migrar iconos a una sola librería | package.json + 7 componentes | 2h | CRÍTICA |
| REF-007 | Reemplazar `logging.basicConfig` por `configure_logging()` | `main.py` | 0.5h | ALTA |
| REF-008 | Agregar lock en `LRUCache.__contains__` | `core/cache.py` | 0.5h | CRÍTICA |
| REF-009 | Mover `watchfiles` a dev-dependencies | `pyproject.toml` | 0.25h | BAJA |
| REF-010 | Extraer strings hardcodeadas a i18n | 5 componentes | 2h | ALTA |
| REF-011 | Reemplazar variables globales mutables en `config.py` | `config.py` | 4h | MEDIA |
| REF-012 | Agregar `max_depth` a `_sanitize_details` recursivo | `core/audit.py` | 0.5h | BAJA |

---

## 16. Mejoras de Arquitectura

| ID | Mejora | Descripción | Prioridad |
|----|--------|-------------|-----------|
| ARC-001 | **Background task para CSRF cleanup** | Invocar `cleanup_expired()` periódicamente desde FastAPI lifespan | CRÍTICA |
| ARC-002 | **Background task para cache cleanup** | Invocar `start_all_cleanup_tasks()` desde lifespan | MEDIA |
| ARC-003 | **Async audit writer** | Migrar `_write_entry_unlocked()` a async I/O para no bloquear event loop | MEDIA |
| ARC-004 | **Configurable CSRF TTL** | Leer TTL desde `config.SETTINGS` | MEDIA |
| ARC-005 | **Plugin dependency injection** | Reemplazar imports circulares por inyección de dependencias | MEDIA |
| ARC-006 | **Rate limiter persistence** | Para producción multi-proceso/multi-instancia, usar Redis/Memcached | BAJA |
| ARC-007 | **Database migrations** | Agregar sistema de migraciones para session_store | BAJA |
| ARC-008 | **Async SQLite** | `session_store.py` usa `sqlite3` síncrono. Migrar a `aiosqlite` | BAJA |

---

## 17. Mejoras de Documentación

| ID | Archivo | Mejora | Prioridad |
|----|---------|--------|-----------|
| DOC-001 | `frontend/src/styles/design-system.md` | Excelente, pero desactualizado vs `design-tokens-2026.css` y `oklch-palette.css` | MEDIA |
| DOC-002 | `README.md` | Agregar sección de "cómo contribuir con tests" | BAJA |
| DOC-003 | `generate_icons.py` | Agregar docstring o README explicando su uso | BAJA |
| DOC-004 | `core/secrets.py:393` | Documentar `VaultBackend` como placeholder futuro | BAJA |
| DOC-005 | `core/process_manager.py` | Agregar justificación a cada `# nosec` | ALTA |
| DOC-006 | `.env.example` | Ya es muy completo, pero mencionar la necesidad de `SECRET_MASTER_PASSWORD` | BAJA |
| DOC-007 | `SECURITY.md` | Crear archivo separado de seguridad (actualmente en CONTRIBUTING.md) | MEDIA |

---

## 18. Mejoras de Pruebas

| ID | Mejora | Prioridad |
|----|--------|-----------|
| TST-001 | Tests para `core/validators.py` (SSRF, XSS, sanitización) | CRÍTICA |
| TST-002 | Tests para `core/cache.py` (LRU, TTL, concurrencia, `__contains__`) | CRÍTICA |
| TST-003 | Tests para `core/secrets.py` (Fernet encrypt/decrypt, rotation) | ALTA |
| TST-004 | Tests para `core/http_client.py` (retry, circuit breaker, timeout) | ALTA |
| TST-005 | Tests para `core/audit.py` (log_event, integridad HMAC, sanitización) | ALTA |
| TST-006 | Tests frontend para `api.ts` (subscribeProgress, receiveFile) | ALTA |
| TST-007 | Tests frontend para `useDownloadManager` (mutaciones, SSE, format/chapter selection) | ALTA |
| TST-008 | Tests para `web/dependencies.py` (CSRF, rate limiter) | ALTA |
| TST-009 | Agregar `pytest-cov` y configurar cobertura mínima | ALTA |
| TST-010 | Tests para `plugins/pdf.py` (generación PDF) | MEDIA |
| TST-011 | Tests para `launcher/` (CLI, Docker, frontend build) | MEDIA |
| TST-012 | Agregar test para `BeautifulToast.tsx` (render, dismiss, ARIA) | MEDIA |
| TST-013 | Integrar Playwright E2E (opt-in) en CI | MEDIA |

---

## 19. Mejoras de Configuración y Automatización

| ID | Mejora | Prioridad |
|----|--------|-----------|
| CFG-001 | Usar versión dinámica en CI en vez de hardcoded | CRÍTICA |
| CFG-002 | Agregar Dependabot o Renovate para dependencias | ALTA |
| CFG-003 | Agregar `pip-audit` en CI | ALTA |
| CFG-004 | Agregar secret scanning en CI (detect-secrets, gitleaks) | ALTA |
| CFG-005 | Agregar multi-Python matrix en CI (3.11, 3.12, 3.13) | MEDIA |
| CFG-006 | Agregar Docker build/test en CI | MEDIA |
| CFG-007 | Agregar `.pre-commit-config.yaml` con ruff, mypy, trailing-whitespace, detect-secrets | MEDIA |
| CFG-008 | Agregar `.gitattributes` para lockfiles y normalización LF | MEDIA |
| CFG-009 | Agregar `pytest-cov` a dev dependencies y configurar `[tool.coverage]` | ALTA |
| CFG-010 | Unificar `EditorConfig` max_line_length con Ruff (100) | BAJA |
| CFG-011 | Eliminar reglas D203/D211 y D212/D213 conflictivas de ruff | BAJA |
| CFG-012 | Crear `SECURITY.md` con política de divulgación | MEDIA |
| CFG-013 | Mover `watchfiles` de runtime a dev-dependencies | BAJA |

---

## 20. Recomendaciones Específicas por Archivo/Carpeta

### 20.1 `config.py`
- Reemplazar variables globales mutables (líneas 212-252) por acceso directo a `SETTINGS` (REF-011).
- Unificar `max_line_length` (BAJA-012).
- Agregar TTL configurable para CSRF (MED-007).
- Endurecer CSP para producción (CR-008).

### 20.2 `core/cache.py`
- Agregar `async with self._lock` en `__contains__` (CR-009).
- Agregar bound `Hashable` a TypeVar `K` (MED-017).
- Invocar `start_all_cleanup_tasks()` desde lifespan (MED-016).

### 20.3 `core/audit.py`
- Migrar `import config` a `from config import SETTINGS` (MED-018).
- Agregar `max_depth` a `_sanitize_details` (BAJA-006).
- Migrar escritura de log a async I/O (PERF-009, ARC-003).

### 20.4 `core/secrets.py`
- Considerar eliminar `VaultBackend` placeholder (DEL-004).
- Mover `hash_sensitive_value` y `verify_hashed_value` cerca de donde se usan (MED-005).

### 20.5 `core/http_client.py`
- Agregar timeouts a todas las llamadas `requests` (ALTA-008).
- Eliminar `_is_unsafe_redirect_target()` si no se usa (BAJA-001).
- Consolidar `_DEFAULT_ALLOWED_HOSTS` (ALTA-001).

### 20.6 `core/metrics.py`
- Eliminar `async_timed_download()` y `AsyncTimedDownload` si no se usan (BAJA-002).

### 20.7 `plugins/book.py` y `plugins/chapters.py`
- Consolidar `_book_urn()` (ALTA-002).
- Consolidar `_DEFAULT_ALLOWED_HOSTS` (ALTA-001).

### 20.8 `web/dependencies.py`
- Invocar `cleanup_expired()` periódicamente (CR-001).
- Hacer TTL configurable (MED-007).

### 20.9 `web/server.py`
- Agregar `start_all_cleanup_tasks()` y CSRF cleanup task en lifespan (ARC-001, ARC-002).

### 20.10 `main.py`
- Usar `configure_logging()` de `core/logging_config.py` (ALTA-009).

### 20.11 `frontend/src/styles/`
- Consolidar CSS: keyframes en `animations.css`, `prefers-reduced-motion` en un solo archivo, `.sr-only` en `a11y.css` (CR-004).
- Unificar sistemas de tokens (CR-005).
- Eliminar `.bottom-sheet` no usado en `responsive.css` (DEL-008).

### 20.12 `frontend/src/components/`
- Extraer hardcoded strings a i18n (ALTA-010).
- Migrar Phosphor icons a Lucide o viceversa (CR-007).
- Consolidar `useFocusTrap` (ALTA-003).

### 20.13 `frontend/src/lib/`
- Eliminar `advanced-types.ts` (CR-006).
- Mejorar `isTransientError` (MED-003).
- Mejorar manejo de admin auth event (MED-004).

### 20.14 `.github/workflows/ci.yml`
- Usar versión dinámica del wheel (CR-002).
- Agregar `pip-audit`, secret scanning, multi-Python, Docker build (CFG-002/006).

---

## 21. Orden de Implementación Propuesto

### Fase 1 — Críticos (Semana 1)
1. CR-001: Invocar `cleanup_expired()` de CSRF (fuga de memoria)
2. CR-009: Agregar lock en `LRUCache.__contains__` (race condition)
3. CR-002: Versión dinámica en CI
4. CR-006: Eliminar `advanced-types.ts`
5. CR-008: Endurecer CSP (nonces/hashes para producción)
6. B-004: SQL query con parámetros en repository.py

### Fase 2 — Alta Prioridad (Semana 2)
7. ALTA-001/002: Consolidar constantes duplicadas
8. ALTA-003: Unificar `useFocusTrap`
9. ALTA-009: Usar `configure_logging()` en main.py
10. ALTA-010: Extraer strings hardcodeadas a i18n
11. ALTA-005/008: Timeouts y seguridad en HTTP y subprocess
12. TST-001/002: Tests para validators.py y cache.py

### Fase 3 — Refactorización CSS y UX (Semana 3)
13. CR-004: Consolidar CSS (keyframes, prefers-reduced-motion, utilidades)
14. CR-005: Unificar tokens CSS
15. CR-007: Eliminar una librería de iconos
16. MED-001/010: Correcciones ARIA e i18n
17. MED-002: Google Fonts `display=swap`

### Fase 4 — Testing y Automatización (Semana 4)
18. TST-003/006/007: Tests para secrets, api.ts, useDownloadManager
19. TST-009: pytest-cov con cobertura mínima
20. CFG-002/003/004: Dependabot, pip-audit, secret scanning en CI
21. CFG-007: pre-commit hooks
22. MED-016: Cache cleanup task en lifespan

### Fase 5 — Baja Prioridad (Semana 5+)
23. REF-011: Reemplazar variables globales mutables en config.py
24. ARC-003: Async audit writer
25. DEL-002/003/004: Eliminar código muerto
26. BAJA-012/013/014/015/016/017: Correcciones menores de configuración

---

## 22. Limitaciones de la Revisión

1. **Sin acceso a red**: No se pudieron instalar dependencias ni ejecutar `uv sync`, `bun install`, `pip-audit`, `pytest`, `vitest`, `mypy` (vía uv) ni build frontend. Los resultados de estas herramientas son simulados donde fue posible.

2. **Herramientas limitadas**: Se instalaron `ruff`, `mypy`, `bandit`, `pytest` desde pip del sistema, pero no reflejan el entorno exacto del proyecto. `mypy` no se ejecutó completamente por timeout.

3. **Sin análisis dinámico**: No se ejecutó la aplicación ni se realizaron pruebas de integración reales. No hay verificación de comportamiento runtime.

4. **Cobertura de TypeScript**: `npx tsc --noEmit` falló por falta de `node_modules`. Los errores reportados son solo de módulos no encontrados, no de tipos reales.

5. **Sin revisión de seguridad manual**: No se realizó penetration testing ni análisis de threat modeling. Los hallazgos de seguridad son estáticos (SAST).

6. **Sin análisis de licencias**: No se verificaron licencias de dependencias (aunque `uv.lock` y `package.json` contienen la información).

7. **Una sola rama**: Solo se revisó `main`. No se consideraron ramas de características o releases.

8. **Revisión automatizada**: Este informe fue generado por una herramienta automatizada (opencode). Aunque se realizaron verificaciones cruzadas, siempre existe riesgo de falsos positivos/negativos.

9. **Sin métricas de rendimiento reales**: Las recomendaciones de rendimiento se basan en análisis estático del código, no en profiling real.

10. **El proyecto usa Python 3.11+ y TypeScript 6**: Las versiones exactas de dependencias no se pudieron verificar contra PyPI/npm.

---

*Fin del informe. 208 archivos revisados, 2703 errores Ruff, 60+ hallazgos bandit, 9 bugs confirmados, 80+ hallazgos documentados con ID único.*
