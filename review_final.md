# Revisión técnica final y plan de remediación de Ryliox

**Fecha:** 2026-07-30
**Commit base revisado:** `6717923`
**Informes contrastados:** `review_codex.md` y `review_opencode.md`
**Estado del plan:** Fase 0 en preparación; fases de implementación pendientes.

## 1. Resumen ejecutivo

Ryliox es un monolito modular bien estructurado para uso local: backend FastAPI/Python, kernel estático de plugins, cola persistente SQLite, frontend Astro/React y empaquetado Docker. El proyecto parte de una base más sólida de lo que sugiere el informe de OpenCode: los linters configurados, el tipado, el frontend y las principales suites backend pasan en el entorno limpio del proyecto.

No se confirmó ninguna vulnerabilidad o avería de prioridad **crítica**. El informe de Codex es la base más fiable porque separa hechos de hipótesis y no convierte automáticamente resultados SAST en vulnerabilidades. OpenCode aportó hallazgos útiles de limpieza y frontend, pero infló severidades y presentó varios falsos positivos como hechos confirmados.

La remediación aprobada evita reescrituras y sobreingeniería. Primero se resolverán defectos pequeños y comprobables; después, integridad de trabajos/archivos, fronteras de despliegue y observabilidad; finalmente se abordará deuda frontend, automatización y documentación. Redis, microservicios, migración general a I/O asíncrono, plugins dinámicos y refactorizaciones visuales masivas quedan descartados mientras no exista una necesidad medida.

## 2. Línea base verificada por Lovelace

Se ejecutaron las herramientas reales después de instalar las dependencias bloqueadas durante las revisiones aisladas. Para evitar que el `PYTHONPATH` de Hermes contaminara el entorno, las comprobaciones Python se ejecutaron con `env -u PYTHONPATH`.

| Validación | Resultado |
|---|---|
| `uv sync --extra all --frozen` | Correcto |
| `bun install --frozen-lockfile` | Correcto |
| Ruff format | 103 archivos correctamente formateados |
| Ruff lint con la configuración del proyecto | Correcto |
| Mypy | Correcto, 46 archivos fuente |
| Tests unitarios backend | 304 aprobados |
| Tests de contrato | 3 aprobados |
| Tests de integración | 71 aprobados, 2 omitidos por requerir `--run-slow` |
| Tests de seguridad | 49 aprobados, 24 omitidos por requerir servidor real |
| Frontend typecheck | Correcto |
| Vitest | 12/12 aprobados |
| Prettier | Correcto |
| Astro build | Correcto; advertencia no bloqueante por import dinámico también importado estáticamente |
| `pip-audit --local` en el entorno limpio | Sin vulnerabilidades conocidas; el paquete local no existe en PyPI y se omite |
| Bandit sobre producción | 0 hallazgos medios/altos; 8 bajos relacionados con uso deliberado de `subprocess` |

La invocación global `pytest -q` quedó detenida después de los diez skips de accesibilidad, aunque las mismas suites ejecutadas por carpeta finalizaron rápidamente. Se registra como problema del runner/aislamiento de la suite y se investigará sin presentar el timeout como fallo funcional del producto.

## 3. Arquitectura actual

### Backend

- `main.py` y `web/server.py`: entrada y servidor FastAPI.
- `web/`: middleware, dependencias, esquemas y rutas REST/SSE.
- `core/`: repositorio SQLite, servicios, sesión cifrada, auditoría HMAC, cliente HTTP, métricas, caché, validadores y kernel.
- `plugins/`: autenticación, libros, capítulos, assets, procesamiento HTML, descarga, EPUB, PDF, output y utilidades opcionales.
- Un worker local consume una cola SQLite y ejecuta el pipeline de descarga.

### Frontend

- Astro genera el shell y los assets estáticos.
- React gestiona la interfaz interactiva.
- Zustand y TanStack Query manejan estado/consultas.
- i18next ofrece locales inglés y español.
- SSE comunica progreso de trabajos.

### Despliegue

- Dockerfile multi-stage compila frontend y backend.
- Compose monta código y volúmenes para un flujo principalmente de desarrollo.
- CI separa backend, frontend y empaquetado.

Esta arquitectura es apropiada para una aplicación local/beta. No se recomienda separarla en servicios ni introducir infraestructura distribuida sin métricas que lo justifiquen.

## 4. Aspectos positivos confirmados

- Capas y responsabilidades razonablemente claras.
- Contratos Pydantic y tipado útiles.
- Persistencia SQLite con WAL y cola recuperable.
- Cookies cifradas con Fernet y soporte de rotación.
- Allowlist y control manual de redirecciones HTTP.
- Validaciones de rutas de salida y defensas frente a traversal.
- Auditoría HMAC, correlación, métricas y health endpoints.
- UI con varias medidas de accesibilidad e i18n con paridad de claves.
- Lockfiles, CI, linters y formatters ya configurados.
- Amplia colección backend: 510 pruebas recolectadas en total.
- README y CONTRIBUTING contienen advertencias de despliegue y tratamiento de secretos.
- No se encontraron secretos reales versionados.

## 5. Coincidencias entre Codex y OpenCode

### 5.1 CSP y fuentes

Ambos detectaron `unsafe-inline` y `unsafe-eval` en `config.py`. Codex añadió la contradicción con Google Fonts. Es un problema **medio**, no crítico: retirar directivas sin preparar el frontend rompería scripts inline. Se aprobará un endurecimiento gradual y probado, no una migración inmediata a nonces.

### 5.2 Accesibilidad/foco duplicado

Existen varias implementaciones de focus trap. Es deuda **baja** hasta que haya pruebas de teclado/focus restore. Se consolidará de forma aislada y conservando compatibilidad interna.

### 5.3 Código y dependencias heredadas

Hay candidatos sin consumidores internos (`advanced-types.ts`, helpers, `TokenPlugin`) y dependencias cuya ubicación puede mejorar. No se eliminarán solo por búsqueda textual: primero se ejecutarán typecheck, tests y búsqueda de exports/entry points.

### 5.4 Cobertura y gates

Hay muchas pruebas backend, pero suites de seguridad/e2e/a11y/performance son opt-in y el frontend solo tiene cinco archivos de tests. Se ampliarán gates por riesgo; no se impondrá de golpe un umbral arbitrario de cobertura.

### 5.5 Configuración global mutable

`config.py` expone globals derivados además del modelo tipado. Antes de refactorizar ese contrato se corregirá `reload()` y se caracterizarán aliases y precedencias.

## 6. Diferencias y contradicciones

- **Severidad:** Codex no confirmó críticos; OpenCode declaró nueve. Se adopta la escala de Codex ajustada con validaciones reales.
- **SAST:** OpenCode trató avisos Bandit/Ruff fuera de configuración como vulnerabilidades/errores. Las ejecuciones reales desmienten esa conclusión.
- **Cobertura:** OpenCode dedujo “cero cobertura” por ausencia de archivos homónimos. Hay tests directos para varios módulos citados; lo correcto es “cobertura no medida”.
- **Caché:** OpenCode recomendó `async with` dentro de `__contains__`, un protocolo síncrono. Esa solución no es válida.
- **CSRF:** OpenCode calificó una fuga crítica, pero la utilidad no tiene caller productivo. Es código inactivo/incompleto.
- **Rendimiento:** OpenCode ofreció cifras de bundle y paint sin medirlas. Quedan como hipótesis.

## 7. Hallazgos exclusivos de Codex aprobados

### Alta, condicionada al despliegue

| ID final | Origen | Hallazgo | Estado |
|---|---|---|---|
| RF-H-01 | RC-H-001 | Compose puede ocultar con un bind mount el `frontend/dist` construido en la imagen | Validar y corregir flujo Docker |
| RF-H-02 | RC-H-002 | `X-Forwarded-*` participa en same-origin sin frontera explícita de proxy confiable | Corregir antes de despliegue remoto |
| RF-H-03 | RC-H-004 | Convenciones de variables planas/anidadas son ambiguas y no están cubiertas por tests | Caracterizar antes de cambiar compatibilidad |

### Media confirmada o altamente probable

| ID final | Hallazgo | Archivos principales |
|---|---|---|
| RF-M-01 | Admisión de cola no atómica | `core/services.py`, `core/repository.py` |
| RF-M-02 | Cleanup elimina cualquier PDF/EPUB viejo del output seleccionado | `web/routes/downloads.py` |
| RF-M-03 | Fallos dejan directorios parciales | `plugins/downloader.py` |
| RF-M-04 | Formato desconocido cae silenciosamente en EPUB | `web/schemas.py`, `plugins/downloader.py` |
| RF-M-05 | Cancelación tardía durante assets y generación | `plugins/downloader.py` |
| RF-M-06 | HTML procesado completo se retiene sin uso posterior | `plugins/downloader.py` |
| RF-M-07 | `config.reload()` omite `extra_headers` | `config.py` |
| RF-M-08 | Métricas de cola/actividad y fuente de configuración son inconsistentes | `core/metrics.py`, `core/services.py` |
| RF-M-09 | Algunas respuestas exponen `str(exc)` | `web/routes/books.py` |
| RF-M-10 | Auditoría no redacta de forma completa listas de objetos | `core/audit.py` |
| RF-M-11 | Límite de respuesta HTTP se aplica después de materializar el body | `core/http_client.py` |
| RF-M-12 | DTO puede lanzar `KeyError` antes de Pydantic | `core/dto.py` |
| RF-M-13 | `book_id` carece de validación en dos rutas | `web/routes/books.py` |

### Baja confirmada

| ID final | Hallazgo |
|---|---|
| RF-L-01 | Timestamp JSON contiene `%f` literal |
| RF-L-02 | Deadline SSE documentado como una hora equivale a unas quince |
| RF-L-03 | Mapa de imágenes puede guardar el path previo al cambio de extensión |
| RF-L-04 | Etiquetas a11y y textos visibles fuera de i18n |
| RF-L-05 | Imagen Open Graph ausente |
| RF-L-06 | README describe paths/capacidades que no coinciden exactamente con el árbol |
| RF-L-07 | Service worker incluye handlers placeholder |
| RF-L-08 | Finales de línea/BOM y política de emojis inconsistentes, sin impacto funcional |

## 8. Hallazgos exclusivos de OpenCode aprobados con severidad corregida

| Hallazgo | Severidad final | Decisión |
|---|---|---|
| Wheel `2.0.0` hardcodeado en CI | Media | Corregir con detección segura de un único wheel |
| `advanced-types.ts` sin imports | Baja | Eliminar solo tras typecheck y búsqueda de exports |
| Keyframes/utilidades CSS duplicados | Baja/media | Consolidación visual separada |
| Dos librerías de iconos | Baja | Cambiar solo si bundle medido justifica el coste |
| `logging.basicConfig` no usa logging estructurado | Baja/media | Unificar entrada sin alterar UX del launcher |
| Toast con ARIA contradictorio y stubs | Media/baja | Corregir con tests de componente |
| `<html lang="es">` y strings fuera de i18n | Baja/media | Corregir de forma incremental |
| EditorConfig 88 frente a Ruff 100 | Baja | Unificar sin reformateo masivo |
| Acciones no fijadas por SHA y auditorías ausentes | Media | Añadir gradualmente |

## 9. Falsos positivos descartados

1. **Inyección SQL en `core/repository.py:476`: descartada.** Las columnas se filtran por `_ALLOWED_UPDATE_COLUMNS` y los valores se parametrizan.
2. **Requests de producción sin timeout: descartado.** `core/http_client.py` usa `httpx.AsyncClient` con timeout; `requests` está en pruebas contra servidor.
3. **Cache cleanup nunca iniciada: descartado.** `web/dependencies.py` inicia y detiene `start_all_cleanup_tasks()`.
4. **Fuga CSRF crítica: descartada como vulnerabilidad productiva.** La clase no tiene caller de producción.
5. **Trece módulos con cero cobertura: no demostrado.** No hubo medición y sí existen tests directos.
6. **`LRUCache.__contains__` como carrera crítica: descartado.** La propuesta de `async with` no aplica a un método síncrono; se deja como posible borde de thread-safety bajo.
7. **Google Fonts sin `display=swap`: descartado.** Ya está presente.
8. **Tokens fijos de pruebas como vulnerabilidad: descartado.** Son fixtures reproducibles sin valor real.
9. **`# nosec` como problema alto: descartado.** Bandit real solo reportó avisos bajos por subprocess con arrays/comandos controlados.
10. **2703 errores Ruff: descartado como métrica.** Se usó `--select ALL`, ignorando la política del proyecto; la configuración real pasa.

## 10. Recomendaciones no aprobadas

No se implementarán en este ciclo:

- Redis/Memcached para rate limiting.
- Separar worker o backend en microservicios.
- Migrar SQLite a `aiosqlite` por preferencia.
- Crear un framework general de migraciones sin necesidad concreta.
- Plugins dinámicos/hot-pluggable reales.
- Cola global de eventos frontend sin bug reproducido.
- Virtualización de resultados sin cardinalidad o jank medidos.
- Nonces CSP en la primera iteración.
- Reescritura global de configuración.
- Conversión de auditoría a I/O asíncrono sin profiling.
- Consolidación simultánea de todos los tokens CSS, iconos y componentes.
- Renombrar `ourn` sin confirmar que no significa “O’Reilly URN”.
- Eliminar APIs públicas solo porque no tienen import interno.
- Umbral alto de cobertura impuesto de una sola vez.

## 11. Priorización final y dependencias

1. **P0 — Reproducibilidad y caracterización:** informes, línea base, timeout global de pytest, configuración efectiva y Docker limpio.
2. **P1 — Correcciones deterministas:** CI wheel, reload, timestamp, formato, DTO, asset path, SSE y pequeñas correcciones frontend.
3. **P2 — Integridad de jobs:** cola atómica, staging, cleanup, cancelación y métricas. Staging precede la política de cleanup.
4. **P3 — Fronteras de despliegue:** Compose, proxy, validación de IDs y errores públicos. Requiere caracterización de topología.
5. **P4 — Seguridad/recursos/observabilidad:** streaming HTTP, auditoría recursiva, health y CSP gradual.
6. **P5 — Frontend y limpieza:** tests, a11y/i18n, CSS/código muerto, iconos solo con medición.
7. **P6 — Automatización y documentación:** CI opt-in por riesgo, auditorías, SECURITY.md, README y auditoría final.

## 12. Plan de implementación por fases

### Fase 0 — Línea base, informes y caracterización

**Estado:** completada el 2026-07-30.
**Evidencia:** los tres informes quedaron versionados; dependencias backend/frontend se instalaron desde lockfiles; Ruff, Mypy, frontend, auditoría y suites backend por carpeta se ejecutaron. El timeout de la invocación global de pytest quedó registrado como pendiente reproducible, mientras las suites aisladas pasan.

**Archivos afectados:**
- `review_codex.md`, `review_opencode.md`, `review_final.md`
- tests nuevos de configuración/Docker/proxy si son viables
- posible ajuste exclusivo al aislamiento de tests si se confirma el timeout global

**Cambios:**
- Versionar los tres informes.
- Registrar comandos y resultados reales.
- Reproducir `pytest -q` por orden/aislamiento y corregir solo si existe un problema del test runner.
- Caracterizar nombres de variables mediante entorno y `.env` temporal.
- Probar Compose con `frontend/dist` ausente.
- Añadir tests de forwarded headers y formato inválido si aún no se implementa la corrección.

**Riesgos:** introducir tests dependientes del host/Docker; falsos fallos por orden global.
**Dependencias:** ninguna.
**Pruebas:** Ruff, Mypy, suites por carpeta, frontend completo, `docker compose config` y smoke Docker cuando esté disponible.
**Criterios de aceptación:** informes completos versionados; baseline reproducible; timeout global explicado o registrado con test mínimo; árbol sin artefactos accidentales.
**Comandos:**
```bash
env -u PYTHONPATH uv sync --extra all --frozen
env -u PYTHONPATH uv run ruff format --check .
env -u PYTHONPATH uv run ruff check .
env -u PYTHONPATH uv run mypy
env -u PYTHONPATH uv run pytest tests/unit tests/contract tests/integration -q
cd frontend && bun install --frozen-lockfile && bun run typecheck && bun run test && bun run format:check && bun run build
docker compose config --quiet
```
**Reversión:** revertir el commit de documentación/tests de caracterización; no tocar datos de usuario.
**Commit propuesto:** `docs(review): add independent audits and verified remediation plan`

### Fase 1 — Correcciones pequeñas y deterministas

**Estado:** pendiente.
**Objetivo:** resolver defectos aislados con bajo riesgo y pruebas directas.

**Archivos:** `.github/workflows/ci.yml`, `config.py`, `core/logging_config.py`, `core/dto.py`, `web/schemas.py`, `plugins/downloader.py`, `plugins/assets.py`, `web/routes/downloads.py`, Toast/i18n y tests asociados.

**Cambios:**
- Wheel dinámico y validación de que existe exactamente uno.
- Conservar `extra_headers` tras `config.reload()`.
- Timestamp ISO-8601 correcto.
- Formatos inválidos devuelven validación 422; no fallback silencioso.
- Dejar que Pydantic produzca `ValidationError`.
- Usar el path canónico devuelto por descarga de imagen.
- Deadline SSE basado en tiempo real.
- Resolver ARIA contradictorio y retirar/implementar stubs de Toast.
- Extraer textos visibles seleccionados a i18n.

**Riesgos:** clientes que enviaban formatos inválidos; snapshots UI; nombre dinámico del wheel con múltiples artefactos.
**Dependencias:** Fase 0.
**Pruebas:** unitarias específicas, contratos API, Vitest del Toast/i18n y build.
**Criterios:** cada bug tiene regresión; no cambia API válida; CI usa un wheel inequívoco.
**Comandos:** comandos de Fase 0 más tests focalizados y `uv build`.
**Reversión:** revertir el commit completo; cada cambio es independiente de datos persistidos.
**Commit propuesto:** `fix: resolve deterministic validation and tooling defects`

### Fase 2 — Integridad de cola, artefactos y cancelación

**Estado:** pendiente.
**Objetivo:** garantizar límites de cola y outputs completos sin borrar archivos ajenos.

**Archivos:** `core/repository.py`, `core/services.py`, `plugins/downloader.py`, `plugins/output.py`, `web/routes/downloads.py`, DTOs/tests.

**Cambios:**
- `enqueue_if_capacity` transaccional.
- Staging por `job_id` y publicación atómica al completar.
- Cleanup solo de artefactos registrados/gestionados.
- Cleanup de staging en error/cancelación.
- Cancelación entre assets y antes/después de formatos.
- Eliminar retención innecesaria de HTML manteniendo contador/contrato.
- Gauges derivados de transiciones reales.

**Riesgos:** locks SQLite más largos; compatibilidad de outputs existentes; rename entre filesystems; cancelación durante librerías no cancelables.
**Dependencias:** staging antes de cleanup; operación atómica antes de métricas finales.
**Pruebas:** concurrencia de enqueue, fallos inyectados por fase, archivos ajenos preservados, cancelación por fase, reinicio de cola.
**Criterios:** nunca exceder capacidad; no publicar parciales; no borrar archivos no gestionados; estados y métricas coherentes.
**Comandos:** Ruff/Mypy, suites unit/integration, tests concurrentes focalizados y smoke de una descarga con mocks.
**Reversión:** revertir commit; no migrar destructivamente la base; mantener lectura de outputs previos.
**Commit propuesto:** `fix(queue): make job admission and artifact lifecycle atomic`

### Fase 3 — Fronteras de despliegue y API

**Estado:** pendiente.
**Objetivo:** hacer coherente el despliegue soportado y endurecer entradas/respuestas.

**Archivos:** `docker-compose.yml`, posible perfil Compose adicional, `web/dependencies.py`, `web/routes/books.py`, `web/server.py`, configuración, README y tests.

**Cambios:**
- Separar runtime reproducible de mounts de desarrollo o retirar el mount que oculta `dist`.
- Definir y documentar proxy confiable; no aceptar forwarded headers de clientes directos.
- Validar `book_id` en las dos rutas faltantes.
- Sustituir `str(exc)` por códigos/mensajes públicos y request ID.
- Rate limit de sesión admin solo si la topología remota se mantiene soportada.
- Caracterizar y documentar aliases de entorno sin romper instalaciones.

**Riesgos:** proxies legítimos mal configurados; rechazo de IDs históricos; cambios del flujo Docker local.
**Dependencias:** caracterización Fase 0 y contratos Fase 1.
**Pruebas:** checkout limpio Docker, forwarded headers confiables/no confiables, IDs malformados, excepciones con datos sensibles y compatibilidad de env.
**Criterios:** `docker compose up --build` sirve UI/health sin dist local; cabeceras falsificadas no alteran origen; respuestas no filtran detalles.
**Comandos:** pruebas backend, `docker compose config`, build/up, `curl` a `/` y `/api/health`.
**Reversión:** restaurar Compose anterior y configuración; mantener aliases legacy mientras se documenta deprecación.
**Commit propuesto:** `fix(security): harden deployment trust boundaries and input validation`

### Fase 4 — Recursos, auditoría, health y CSP

**Estado:** pendiente.
**Objetivo:** reducir riesgos de memoria y mejorar observabilidad sin cambiar arquitectura.

**Archivos:** `core/http_client.py`, `web/server.py`, `core/audit.py`, `web/routes/system.py`, `config.py`, `frontend/src/pages/index.astro`, tests.

**Cambios:**
- Lectura streaming con límite temprano de respuestas HTTP.
- Benchmark del buffering de requests; cambiar solo si demuestra presión relevante.
- Sanitización recursiva de dict/list/tuple con profundidad/tamaño acotados.
- Separar liveness local de dependency health; evitar detalles internos.
- CSP: eliminar `unsafe-eval` si build/runtime lo permiten; autoalojar fuentes o permitir orígenes exactos; usar report-only antes de nonces.
- Optimizar auditoría al arranque solo si una prueba de log grande demuestra necesidad.

**Riesgos:** cambios en semántica de retries/streams; redacción excesiva; CSP que rompa UI; probes menos sensibles al upstream.
**Dependencias:** frontera de despliegue de Fase 3.
**Pruebas:** transport fake por chunks, cierre de response, payloads de auditoría anidados, upstream lento/caído, pruebas browser/CSP.
**Criterios:** aborto temprano de body excesivo; ningún secreto anidado en logs; liveness rápido sin red; UI sin violaciones CSP bloqueantes.
**Comandos:** backend completo, Bandit, pip-audit, frontend build y smoke en navegador/headers.
**Reversión:** revertir commit; mantener CSP anterior configurable para rollback temporal documentado.
**Commit propuesto:** `fix(observability): bound resource use and sanitize operational data`

### Fase 5 — Frontend, accesibilidad y limpieza conservadora

**Estado:** pendiente.
**Objetivo:** mejorar mantenibilidad y UX sin rediseño visual.

**Archivos:** componentes, `frontend/src/lib`, estilos, locales, assets PWA/OG y `package.json` si procede.

**Cambios:**
- Tests para cliente API, sesión, progreso, Toast y foco.
- Consolidar focus trap manteniendo reexports necesarios.
- Corregir labels/`lang`/textos fuera de i18n.
- Eliminar `advanced-types.ts` y placeholders solo tras confirmar ausencia de consumidores.
- Consolidar duplicación CSS en tareas pequeñas y con comparación visual.
- Medir bundle; unificar iconos únicamente si el beneficio es material.
- Añadir o retirar referencia a OG image.
- Eliminar handlers PWA no implementados si no existe contrato real.

**Riesgos:** regresiones visuales/a11y; imports públicos; cambios de snapshots; iconos no equivalentes.
**Dependencias:** contratos API estabilizados en fases anteriores.
**Pruebas:** Vitest, typecheck, Prettier, build, Playwright/a11y y comparación visual/teclado.
**Criterios:** cero imports rotos; accesibilidad no empeora; cada eliminación respaldada por búsqueda y tests; sin cambio visual accidental.
**Comandos:** frontend completo, análisis de bundle si se toca iconografía y smoke browser.
**Reversión:** revertir por subcambio visual; evitar eliminación y migración de iconos en el mismo commit si el diff crece demasiado.
**Commit propuesto:** `refactor(frontend): consolidate accessible UI utilities and remove verified dead code`

### Fase 6 — CI, seguridad documental y validación final

**Estado:** pendiente.
**Objetivo:** convertir las validaciones útiles en gates mantenibles y cerrar documentación.

**Archivos:** `.github/workflows/ci.yml`, posible Dependabot, `SECURITY.md`, README, CONTRIBUTING, tests README, `.gitattributes` y configuración mínima.

**Cambios:**
- Fijar Actions por SHA con comentarios de versión.
- Añadir `pip-audit` y secret scanning con baseline revisado.
- Ejecutar suites opt-in en jobs separados según riesgo/frecuencia.
- Añadir cobertura informativa primero; umbral solo después de línea base estable.
- Investigar/corregir timeout de `pytest -q` global.
- Unificar line length y normalización LF sin commit masivo de formato.
- Documentar seguridad, topología, configuración, tests reales, outputs y decisiones descartadas.
- Actualizar este archivo con estados resuelto/pendiente/descartado y resultados finales.

**Riesgos:** CI lento/flaky; falsos positivos de secret scanning; cambios de EOL ruidosos.
**Dependencias:** todas las fases previas.
**Pruebas:** CI en PR, ejecución local de comandos equivalentes, auditorías y build Docker.
**Criterios:** todos los gates verdes o skips justificados; historial claro; documentación coincide con código; árbol limpio.
**Comandos:** suite completa por jobs, Ruff/Mypy, frontend, Bandit, pip-audit, Docker smoke y `git diff --check`.
**Reversión:** retirar únicamente el job inestable manteniendo el hallazgo documentado; no desactivar tests existentes para lograr verde.
**Commit propuesto:** `ci: enforce reproducible quality and security checks`

## 13. Estado de hallazgos

### Resueltos

- Fase 0: revisiones independientes, contraste final, instalación reproducible y línea base técnica verificadas.
- Falsos positivos de OpenCode enumerados y descartados con evidencia.
- No se han corregido todavía defectos de producción; comienzan en la Fase 1.

### Pendientes aprobados

RF-H-01 a RF-H-03, RF-M-01 a RF-M-13, RF-L-01 a RF-L-08 y los hallazgos OpenCode aprobados en la sección 8.

### Pendientes de validación

- Impacto real del mount Compose.
- Topología de proxy soportada.
- Convenciones exactas de `.env` frente a variables del proceso y Compose.
- Necesidad práctica de cambiar buffering de requests.
- Coste de auditoría en logs grandes.
- Beneficio medido de unificar iconos/virtualizar listas.
- Causa del timeout de la suite global.

### Descartados

Los falsos positivos de la sección 9 y las propuestas de sobreingeniería de la sección 10.

## 14. Reglas de ejecución

Para cada fase:

1. Partir de `main` limpio y actualizado.
2. Crear rama `review/phase-N-<tema>`.
3. Encargar cambios delimitados a Codex u OpenCode; el otro puede revisar cuando aporte independencia.
4. Revisar personalmente el diff completo.
5. Ejecutar pruebas focalizadas y gates generales aplicables.
6. Comprobar secretos, temporales, lockfiles y archivos accidentales.
7. Actualizar este documento con estado y evidencia.
8. Crear un único commit relacionado con la fase.
9. Publicar la rama en GitHub y abrir PR.
10. No iniciar la siguiente fase hasta cumplir criterios o revertir/corregir.

## 15. Resultado esperado al cierre

- Tres informes versionados.
- Una rama/PR y un commit verificable por fase completada.
- Bugs funcionales y riesgos de despliegue resueltos sin reescritura innecesaria.
- Tests suficientes para proteger los cambios.
- CI y documentación alineados con el comportamiento real.
- Lista final de resueltos, pendientes validados y descartados.
- `git status` limpio y ausencia de secretos/artefactos accidentales.
