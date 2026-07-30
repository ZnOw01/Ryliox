# Revisión técnica exhaustiva de Ryliox

Fecha: 2026-07-30
Commit revisado: 6717923 docs: overhaul README...
Modo: independiente, de solo lectura, sin consultar conclusiones de otros revisores.

Este informe distingue entre:

- **Observado:** hecho comprobado directamente en el árbol, configuración o una ejecución local.
- **Inferencia:** consecuencia razonable que no pudo confirmarse en ejecución.
- **Certeza:** Confirmado significa que el defecto está en el código/configuración observada; Hipótesis significa que requiere una prueba de integración, despliegue o entorno adicional.

No se exponen valores de secretos. Cuando una observación involucra credenciales o cookies, se describe solo su presencia, flujo o riesgo.

## 1. Resumen ejecutivo

Ryliox es una aplicación monolítica modular con backend FastAPI/Python, kernel de plugins, cola persistente en SQLite y frontend Astro/React/Tailwind compilado dentro de una imagen Docker. La base es razonablemente clara y contiene buenas defensas para un proyecto beta: persistencia de trabajos, cifrado de cookies con Fernet, allowlist de hosts y redirecciones HTTP, validación de rutas de salida, comprobaciones de origen, cabeceras de seguridad, auditoría con HMAC, contratos Pydantic, pruebas por capas y lockfiles.

La revisión cubrió los 208 archivos versionados del commit indicado, no una muestra. El inventario suma 43.399 líneas. Los 105 archivos Python pudieron parsearse mediante AST; git diff --check y la sintaxis JSON/YAML aplicable pasaron; docker compose config --quiet pasó. No fue posible ejecutar la suite real ni el toolchain frontend porque el checkout no contiene entorno instalado y no se permitió crear uno. uv lock --check quedó bloqueado por una caché del sistema de solo lectura. Esos bloqueos están documentados y no se presentan como resultados de tests.

No se confirmó un hallazgo de prioridad crítica en esta revisión estática. Sí hay varios riesgos de prioridad alta que deben resolverse antes de considerar fiable un despliegue remoto o el flujo Docker de primera ejecución:

1. Compose documenta el montaje de frontend/dist, pero esa carpeta no existe en el checkout y el bind mount puede ocultar el frontend construido dentro de la imagen.
2. La comprobación same-origin acepta X-Forwarded-* sin verificar que procedan de un proxy de confianza; en una topología expuesta directamente puede falsificarse el origen.
3. Tres rutas de libros no aplican el validador de book_id, aunque después ese valor se inserta en URLs remotas y claves de caché.
4. .env.example documenta variables planas que el modelo de configuración anidado no consume como parecen indicar los nombres.
5. El middleware de límite de cuerpo y el cliente HTTP materializan cuerpos completos en memoria; el coste se multiplica con concurrencia.

Entre los problemas confirmados de prioridad media destacan la condición de carrera de admisión de la cola, la eliminación de archivos antiguos que no necesariamente fueron generados por la aplicación, la retención de directorios parciales tras errores, formatos inválidos tratados como EPUB, métricas de cola/actividad inconsistentes, un health check SQLite que inspecciona un atributo inexistente en SessionStore, pérdida de cabeceras extra al recargar configuración y crecimiento de memoria al restaurar el log de auditoría.

## 2. Metodología y alcance

### Inventario y cobertura

Se usó Git como fuente de verdad para no omitir archivos no obvios. El resultado fue:

| Tipo | Archivos |
| --- | ---: |
| Python | 105 |
| TSX | 32 |
| TypeScript | 21 |
| CSS | 9 |
| JSON | 7 |
| Markdown | 6 |
| PNG | 9 |
| YAML | 2 |
| JavaScript/MJS/MTS/Astro/SVG | 6 |
| Lockfiles | 2 |
| Configuración raíz y otros | 11 |
| **Total** | **208** |

Distribución por zona: frontend/ 87 archivos, tests/ 51, core/ 19, web/ 11, plugins/ 14, launcher/ 7, utils/ 2, .github/ 1 y 16 archivos en raíz. Se inspeccionaron estructura, imports, referencias, contratos, configuración, documentación, tests y recursos estáticos de todas esas zonas. Los archivos generados ausentes (frontend/dist, node_modules, .venv, etc.) se trataron como evidencia operativa, no como archivos omitidos.

### Comandos y validaciones ejecutados

Comandos de inventario y estado:

- git status --short --branch: árbol limpio, rama main alineada con origin/main.
- git ls-files | wc -l: 208.
- git ls-files con conteo por extensión y carpeta.
- wc -l sobre todos los archivos versionados: 43.399 líneas.
- rg para imports, símbolos declarados, referencias cruzadas, rutas, secretos candidatos, TODOs, emojis y configuración.
- file para codificación, BOM y finales de línea.

Validaciones estáticas:

- Script Python de AST sobre los 105 .py: parsed=105 bad=0.
- Validación JSON de .mcp.json, frontend/package.json, frontend/public/manifest.json y ambos locales: OK.
- Parser YAML Ruby sobre .github/workflows/ci.yml y docker-compose.yml: OK.
- git diff --check: exit 0.
- docker compose config --quiet: exit 0.

Intentos que no pudieron completarse:

- Importar config en un Python limpio: falló con ModuleNotFoundError: No module named 'pydantic'.
- uv lock --check: falló antes de validar el lockfile porque uv no pudo crear un temporal en /home/snowflake/.cache/uv/, que es de solo lectura.
- bun run typecheck: cross-env: command not found, exit 127.
- bun run test: cross-env: command not found, exit 127.
- bun run format:check: prettier: command not found, exit 127.

No se ejecutó uv sync, instalación de Bun, pytest, ruff, mypy, un build frontend ni docker compose build/up, porque crearían entornos/cache/imágenes o exigirían dependencias ausentes; además, el encargo prohíbe modificar el checkout y solo autoriza escribir este informe.

También se intentó el preflight de la revisión profunda de seguridad disponible en el entorno. El runtime reportó blocked: esperaba native_multi_agent_v2 y encontró runtime nativo/v1. La remediación propuesta requería cambiar la configuración del entorno de Codex; no se hizo. Por tanto, este informe contiene una auditoría manual completa del repositorio, pero no afirma haber ejecutado ese escáner profundo.

## 3. Descripción de la arquitectura actual

### Backend

main.py/web/server.py levantan FastAPI. web/ concentra middleware, dependencias, rutas y esquemas. core/ contiene configuración, contratos, DTOs, cachés, cliente HTTP, kernel, repositorio, cola, sesión cifrada, auditoría, métricas, secretos y servicios. plugins/ implementa autenticación, libros, capítulos, assets, procesamiento HTML, descarga, EPUB, PDF, salida y tokenización. utils/ agrupa helpers de rutas y nombres.

El kernel registra plugins en core/kernel.py; la composición es estática durante el arranque. La cola usa SQLite y un worker en un hilo del proceso; el worker ejecuta el pipeline asíncrono con un runner de asyncio. Los resultados se escriben como EPUB/PDF en un directorio validado. La sesión de cookies se conserva en SQLite cifrado, con migración de formatos legados.

### Frontend

frontend/src/pages/index.astro sirve el shell y carga la aplicación React. Los componentes, hooks, store, cliente API, i18n y utilidades de accesibilidad viven bajo frontend/src. Astro/Tailwind producen frontend/dist; el runtime Python sirve esa salida y ofrece fallback JSON para desarrollo.

El cliente usa REST para configuración, sesión, búsqueda y cola, y SSE para progreso. Hay PWA con manifest, service worker e iconos. Los locales inglés y español tienen paridad observada de 241 claves.

### Distribución y ejecución

Dockerfile usa build multi-stage: Bun compila el frontend y una etapa Python prepara el runtime. docker-compose.yml está orientado a desarrollo, monta el código y un frontend/dist preconstruido, y persiste data, output y configuración en volúmenes. CI separa backend, frontend y empaquetado.

La separación es modular dentro de un solo proceso, no distribuida: la cola, las métricas singleton, la caché y el kernel comparten memoria y SQLite. Esto simplifica el uso local, pero limita el escalado horizontal y hace importante que el health check, el estado de configuración y las transiciones de la cola sean exactos.

## 4. Aspectos positivos

- La estructura por capas es comprensible y evita mezclar en las rutas la mayor parte de la lógica de descarga.
- El kernel, los protocolos y los contratos hacen posible sustituir plugins en tests y reducen acoplamiento directo.
- La cola persistente conserva trabajos entre reinicios y usa transacciones SQLite/WAL.
- La sesión de cookies usa cifrado autenticado, archivos de clave con permisos restrictivos y soporta rotación.
- core/http_client.py aplica allowlist de hosts, controla redirecciones manualmente y limita tamaños declarados.
- Hay defensas de path traversal en capítulos, salida, assets y generación PDF.
- La aplicación exige token de administración para binds no locales y documenta con claridad el riesgo del modo local.
- Auditoría, correlación por request/job, métricas Prometheus y health endpoints proporcionan buena base operativa.
- Pydantic se usa para esquemas de API y DTOs, y la configuración está tipada.
- Hay tests unitarios, contract, integración, seguridad OWASP, e2e, accesibilidad y rendimiento, aunque varios grupos son opt-in.
- CI usa uv sync --frozen, lockfiles y checks de formato/tipos para backend, además de typecheck/test/format/build frontend.
- La validación estática ejecutada en esta revisión no detectó errores de sintaxis Python, JSON o YAML.
- La UI incluye skip link, landmarks, etiquetas, live regions, foco y controles de teclado; la paridad de traducciones es buena.
- La documentación incluye advertencias explícitas sobre no exponer el puerto local y sobre redacción de cookies/tokens en contribuciones.

## 5. Problemas críticos

No se confirmó un problema de prioridad crítica. Los hallazgos de mayor impacto están clasificados como alta prioridad porque requieren una condición de despliegue, concurrencia o entrada concreta para materializarse, pero deben atenderse antes de exposición remota.

## 6. Problemas de prioridad alta

### RC-H-001 — El Compose puede ocultar el frontend construido

- **Archivo/carpeta:** docker-compose.yml, Dockerfile, README.md.
- **Línea/sección aproximada:** docker-compose.yml:4-8, 42-45; README, sección Docker.
- **Descripción y evidencia:** Compose declara que frontend/dist debe estar preconstruido y monta ./frontend/dist:/app/frontend/dist:ro. En el checkout revisado frontend/dist no existe. La imagen multi-stage sí construye una salida, pero el bind mount la cubre al arrancar; Docker puede crear el origen vacío o fallar según el estado del host.
- **Motivo:** el comando documentado docker compose up -d no reproduce necesariamente el artefacto que la imagen acaba de construir.
- **Impacto:** primera ejecución con UI ausente, fallback inesperado, contenedor unhealthy o comportamiento distinto entre hosts.
- **Prioridad:** alta.
- **Solución recomendada:** elegir una sola fuente: eliminar el bind mount del runtime y usar el dist de la imagen, o añadir un paso explícito y reproducible que construya frontend/dist antes de up; actualizar README y Compose juntos.
- **Riesgos de aplicar la solución:** quitar el montaje reduce la comodidad de desarrollo; añadir el build aumenta tiempo y requisitos locales.
- **Dependencias:** decisión de separar perfil dev y perfil runtime; revisar healthcheck y flujo launcher.
- **Verificación:** en checkout limpio ejecutar docker compose up -d, comprobar curl -fsS http://127.0.0.1:8000/ y una ruta de asset compilado; repetir con frontend/dist ausente.
- **Certeza:** Hipótesis de fallo en runtime; la configuración y la ausencia del directorio están confirmadas, pero no se levantó el contenedor.

### RC-H-002 — Confianza implícita en cabeceras X-Forwarded-* para same-origin

- **Archivo/carpeta:** web/dependencies.py, Dockerfile.
- **Línea/sección aproximada:** web/dependencies.py:270-330; comando Uvicorn con --proxy-headers.
- **Descripción y evidencia:** _is_same_origin toma x-forwarded-host, x-forwarded-proto y x-forwarded-port antes que los valores directos. No hay una lista de proxies de confianza ni una condición que elimine dichas cabeceras cuando la conexión no proviene de uno.
- **Motivo:** la comprobación de origen se usa como defensa para métodos mutantes. Un cliente que pueda alcanzar el servidor directamente puede enviar cabeceras que hagan coincidir un Origin arbitrario con el host calculado.
- **Impacto:** debilitamiento potencial de CSRF/same-origin y posibilidad de ejecutar operaciones mutantes desde un origen controlado si el servicio se despliega detrás de una topología incorrecta.
- **Prioridad:** alta.
- **Solución recomendada:** configurar proxies confiables explícitos y aceptar X-Forwarded-* solo desde sus IPs; de lo contrario usar request.url/Host directo. Documentar el contrato de proxy junto con --proxy-headers.
- **Riesgos de aplicar la solución:** detrás de un proxy legítimo pueden fallar clientes si no se configura su IP; comparar solo host sin esquema rompería despliegues HTTPS.
- **Dependencias:** configuración de infraestructura, TrustedHostMiddleware, CORS y política de cookies.
- **Verificación:** prueba ASGI que envíe Origin distinto junto con X-Forwarded-* desde un cliente no confiable; debe responder 403. Prueba equivalente desde proxy confiable debe continuar funcionando.
- **Certeza:** Hipótesis de explotación; la confianza implícita está confirmada y la explotabilidad depende de la topología.

### RC-H-003 — book_id no se valida en todas las rutas que lo usan

- **Archivo/carpeta:** web/routes/books.py, web/dependencies.py, plugins/chapters.py.
- **Línea/sección aproximada:** web/routes/books.py:106-120, 207-224; web/dependencies.py:334-356; plugins/chapters.py:20-48.
- **Descripción y evidencia:** existe validate_book_id_dependency, pero book_chapters y book_info reciben book_id: str sin Depends(validate_book_id_dependency). ChaptersPlugin lo transforma directamente mediante _book_urn(book_id) y lo inserta en query/path remotos. El frontend codifica la URL, pero el API también acepta llamadas directas.
- **Motivo:** la validación debe aplicarse en el borde de cada ruta, no solo en otro flujo como el schema de descarga.
- **Impacto:** entradas con caracteres de control, separadores o formas inesperadas pueden contaminar URLs upstream, claves de caché, logs y mensajes; el cliente HTTP reduce SSRF, pero no sustituye la validación semántica del identificador.
- **Prioridad:** alta.
- **Solución recomendada:** usar la dependencia en las rutas de libro/capítulos y centralizar la normalización de URN. Codificar componentes de URL donde corresponda.
- **Riesgos de aplicar la solución:** puede rechazar IDs históricos que hoy se aceptan; revisar fixtures y compatibilidad antes de imponer el patrón.
- **Dependencias:** contratos BookInfo/ChapterInfo, tests de rutas y caché.
- **Verificación:** tests HTTP con IDs vacíos, .., slashes, %2F, CR/LF y URNs válidos; comprobar que los válidos conservan la URL esperada y los demás devuelven 400 sin llamada HTTP.
- **Certeza:** Confirmado que falta la validación; el impacto exacto upstream es hipótesis.

### RC-H-004 — El .env.example no refleja el modelo de configuración anidado

- **Archivo/carpeta:** .env.example, config.py, docker-compose.yml, CI.
- **Línea/sección aproximada:** .env.example:15-180; config.py:145-205.
- **Descripción y evidencia:** el ejemplo documenta BASE_URL, REQUEST_DELAY, OUTPUT_DIR, HOST, PORT, ENVIRONMENT, MAX_REQUEST_SIZE_MB, ENABLE_METRICS y otros nombres planos. Settings configura grupos (server, paths, http, security, metrics, etc.) con env_nested_delimiter=__; solo algunos grupos tienen aliases explícitos (PATHS, SECURITY, AUDIT, SESSION). La composición usa JSON SECURITY, SERVER y PATHS, mientras el ejemplo enseña otra convención.
- **Motivo:** una persona que copie el archivo puede creer que está cambiando valores que el modelo ignora y recibir silenciosamente defaults.
- **Impacto:** despliegues con límites, host, rutas, seguridad o métricas distintas de lo esperado; riesgo operativo y de seguridad por falsa configuración.
- **Prioridad:** alta.
- **Solución recomendada:** escoger una convención, preferiblemente documentar RYLIOX_SERVER__HOST, RYLIOX_SECURITY__ENVIRONMENT, RYLIOX_PATHS__OUTPUT_DIR, etc.; si se mantienen aliases planos, mapearlos explícitamente y añadir tests de precedencia.
- **Riesgos de aplicar la solución:** cambiar nombres rompe instalaciones existentes; mantener aliases aumenta superficie y complejidad.
- **Dependencias:** Docker, launcher, CI, .env.example, README y tests de configuración.
- **Verificación:** con una dependencia instalada, cargar un .env temporal con cada nombre y afirmar el valor efectivo; prohibir nombres documentados que no tengan efecto o marcarlos como legacy.
- **Certeza:** Confirmado por la estructura de settings y la discrepancia documental; no se ejecutó Pydantic por dependencia ausente.

### RC-H-005 — El límite de cuerpo materializa hasta 10 MB por request

- **Archivo/carpeta:** web/server.py.
- **Línea/sección aproximada:** web/server.py:282-319.
- **Descripción y evidencia:** RequestBodyLimitMiddleware recibe chunks y acumula toda la lista messages antes de devolver un receive replayable. Rechaza Content-Length mayor que el máximo, pero una petición chunked puede mantener hasta el límite en memoria por conexión.
- **Motivo:** limitar el tamaño final no evita multiplicar memoria por conexiones concurrentes ni obliga al consumidor a procesar por streaming.
- **Impacto:** presión de memoria, latencia y posible agotamiento de workers si el servicio recibe muchas solicitudes chunked cercanas a 10 MB.
- **Prioridad:** alta.
- **Solución recomendada:** preferir límites en reverse proxy; en aplicación usar un wrapper que cuente bytes y exponga un buffer acotado solo cuando FastAPI necesite replay, o limitar concurrencia/cuerpo por endpoint.
- **Riesgos de aplicar la solución:** un wrapper incorrecto puede romper lecturas repetidas de Starlette; requiere pruebas con cuerpos incompletos y chunked.
- **Dependencias:** proxy, timeouts, límites de Uvicorn y endpoints multipart/JSON.
- **Verificación:** prueba ASGI concurrente con requests chunked de tamaño límite y sobrelímite; medir RSS y confirmar 413 sin acumular más del límite.
- **Certeza:** Confirmado el buffering; la clasificación como DoS depende de concurrencia y despliegue.

## 7. Problemas de prioridad media

### RC-M-001 — Condición de carrera en la capacidad de la cola

- **Archivo/carpeta:** core/services.py, core/repository.py.
- **Línea/sección aproximada:** core/services.py:174-190; core/repository.py:375, 423-446.
- **Descripción y evidencia:** enqueue consulta count_queued, compara con _max_queued_jobs y después llama a save en una operación separada. Dos hilos/request concurrentes pueden observar el mismo conteo y ambos insertar.
- **Motivo:** la decisión de admisión y la inserción deben ser atómicas.
- **Impacto:** la cola puede superar el límite configurado; también se registran tamaños y posiciones incorrectos.
- **Prioridad:** media.
- **Solución recomendada:** añadir al repositorio una operación transaccional enqueue_if_capacity, con BEGIN IMMEDIATE, recuento e inserción bajo el mismo lock/transaction.
- **Riesgos de aplicar la solución:** lock más largo puede aumentar SQLITE_BUSY; se debe conservar timeout y rollback.
- **Dependencias:** DTO, métricas de cola y tests concurrentes.
- **Verificación:** lanzar más threads que la capacidad contra una base temporal y afirmar que el número de estados queued no excede el límite.
- **Certeza:** Confirmado.

### RC-M-002 — Limpieza de archivos que no identifica propiedad de la aplicación

- **Archivo/carpeta:** web/routes/downloads.py.
- **Línea/sección aproximada:** web/routes/downloads.py:181-219.
- **Descripción y evidencia:** cleanup_old_files_task recorre directamente output_dir.glob("*.pdf") y glob("*.epub"); elimina cualquier fichero superior a 24 horas sin comprobar job, manifest, prefijo o subdirectorio de Ryliox.
- **Motivo:** el directorio puede contener archivos colocados por el usuario, una exportación manual o una aplicación distinta.
- **Impacto:** pérdida de datos no intencionada al terminar una descarga.
- **Prioridad:** media.
- **Solución recomendada:** guardar artefactos bajo una subcarpeta/job directory gestionada por Ryliox y mantener un manifest/registro; limpiar solo paths registrados como outputs de trabajos terminales.
- **Riesgos de aplicar la solución:** archivos antiguos generados por versiones previas podrían quedar sin limpiar; hacer una migración explícita, no una purga amplia.
- **Dependencias:** OutputPlugin, DownloadResult, retención de jobs y documentación del directorio.
- **Verificación:** crear un .epub viejo no registrado y otro registrado en una base temporal; ejecutar cleanup y comprobar que solo desaparece el segundo.
- **Certeza:** Confirmado.

### RC-M-003 — Fallos posteriores dejan artefactos parciales

- **Archivo/carpeta:** plugins/downloader.py.
- **Línea/sección aproximada:** plugins/downloader.py:347-353, 369-487.
- **Descripción y evidencia:** se crea book_dir antes de portada, capítulos, assets y formatos. La limpieza explícita aparece en la rama de cancelación _cleanup_on_cancel; las excepciones de red, HTML, CSS, EPUB o PDF llegan al servicio sin un finally equivalente que elimine el directorio incompleto.
- **Motivo:** el pipeline escribe progresivamente en un destino final sin distinguir staging de resultado publicado.
- **Impacto:** basura, consumo creciente de disco y riesgo de que usuarios confundan un output parcial con un libro válido.
- **Prioridad:** media.
- **Solución recomendada:** usar staging por job y renombrar atómicamente al completar; en error eliminar staging, conservando un log de ruta si la eliminación falla.
- **Riesgos de aplicar la solución:** renombrado puede cruzar filesystem; revisar compatibilidad con PDF/EPUB y con la función de revelar archivos.
- **Dependencias:** OutputPlugin, respuesta de jobs y cleanup.
- **Verificación:** inyectar fallo en cada fase y comprobar que no queda output publicado ni staging huérfano.
- **Certeza:** Confirmado.

### RC-M-004 — Formatos desconocidos se ignoran y el vacío cae en EPUB

- **Archivo/carpeta:** plugins/downloader.py, rutas/schema de descarga.
- **Línea/sección aproximada:** plugins/downloader.py:195-214.
- **Descripción y evidencia:** el pipeline filtra formatos a epub/pdf y, si no queda ninguno, asigna [epub]. Un typo como epbu no produce 400; genera un formato distinto del solicitado.
- **Motivo:** una entrada inválida debe fallar claramente. El fallback solo es seguro cuando la ausencia de formatos está diferenciada de una lista no válida.
- **Impacto:** resultado funcionalmente incorrecto, confusión y consumo innecesario de red/CPU.
- **Prioridad:** media.
- **Solución recomendada:** distinguir None/lista vacía intencional de valores desconocidos; devolver 422 con los formatos permitidos.
- **Riesgos de aplicar la solución:** clientes antiguos que envían strings no reconocidos necesitarán actualización.
- **Dependencias:** DownloadRequest, DTO, frontend y tests contract.
- **Verificación:** tests para None, [], [epub], [pdf], [epbu] y mezcla válida/inválida.
- **Certeza:** Confirmado.

### RC-M-005 — Se conserva HTML procesado completo sin consumidor real

- **Archivo/carpeta:** plugins/downloader.py.
- **Línea/sección aproximada:** plugins/downloader.py:371, 401-418, 494.
- **Descripción y evidencia:** chapters_data guarda una tupla con el HTML procesado completo por capítulo, pero la búsqueda de referencias muestra que posteriormente solo se usa len(chapters_data) para chapters_count. Los archivos XHTML ya se escribieron en oebps.
- **Motivo:** duplicar el contenido de todos los capítulos mantiene memoria proporcional al tamaño del libro.
- **Impacto:** picos de memoria en libros grandes y más presión de GC sin valor funcional observado.
- **Prioridad:** media.
- **Solución recomendada:** conservar únicamente un contador, o una estructura mínima que el plugin EPUB realmente necesite después de confirmar el contrato.
- **Riesgos de aplicar la solución:** una extensión externa podría inspeccionar el atributo aunque no haya referencias internas; revisar API pública antes de eliminar.
- **Dependencias:** EpubPlugin, tests de generación y posibles plugins externos.
- **Verificación:** prueba con HTML grande midiendo RSS antes/después y afirmar que chapters_count y EPUB son iguales.
- **Certeza:** Confirmado dentro del repositorio; compatibilidad externa es hipótesis.

### RC-M-006 — Cancelación no se comprueba durante assets y generación

- **Archivo/carpeta:** plugins/downloader.py.
- **Línea/sección aproximada:** plugins/downloader.py:376-487.
- **Descripción y evidencia:** se llama check_cancel() antes de cada capítulo, pero los bucles de CSS, imágenes, portada y generación EPUB/PDF no tienen un mecanismo equivalente; el callback de progreso solo reporta.
- **Motivo:** el usuario puede cancelar mientras una descarga de assets o render PDF espera red/CPU.
- **Impacto:** cancelación tardía, trabajo innecesario, archivos parciales y peor UX.
- **Prioridad:** media.
- **Solución recomendada:** pasar un callback cancelable a plugins de assets y consultar el evento entre cada asset y antes/después de cada formato; hacer que librerías largas tengan timeout/cancelación donde sea posible.
- **Riesgos de aplicar la solución:** interrupciones a mitad de una escritura requieren cleanup robusto; no cancelar una operación no cancelable dejando un estado incoherente.
- **Dependencias:** RC-M-003, AssetsPlugin, PdfPlugin y estado de la cola.
- **Verificación:** test que active cancelación durante cada fase y compruebe estado cancelled, cleanup y ausencia de ejecución del siguiente formato.
- **Certeza:** Confirmado.

### RC-M-007 — Validación DNS acepta el primer resultado seguro

- **Archivo/carpeta:** core/validators.py.
- **Línea/sección aproximada:** core/validators.py:175-201.
- **Descripción y evidencia:** _resolve_and_validate_dns recorre getaddrinfo, retorna cuando encuentra la primera dirección no bloqueada y no rechaza explícitamente un hostname que también resuelva a una dirección privada.
- **Motivo:** un hostname multirespuesta o un rebinding puede cambiar la dirección usada por el cliente después de la validación.
- **Impacto:** bypass potencial de la protección SSRF en determinadas respuestas DNS/redes.
- **Prioridad:** media.
- **Solución recomendada:** rechazar si cualquier dirección resuelta está en rangos prohibidos y conectar al destino validado, o usar una allowlist de hosts de negocio sin resolver entradas arbitrarias.
- **Riesgos de aplicar la solución:** CDNs con mezcla de IPv4/IPv6 pueden bloquearse; validar todas las direcciones puede aumentar latencia.
- **Dependencias:** HttpClient, redirecciones y política de allowlist.
- **Verificación:** resolver un hostname controlado con A segura y A privada; comprobar rechazo y prueba de DNS rebinding con un resolver simulado.
- **Certeza:** Hipótesis de explotación; la lógica parcial está confirmada.

### RC-M-008 — Timeout DNS puede esperar al executor

- **Archivo/carpeta:** core/validators.py.
- **Línea/sección aproximada:** core/validators.py:206-227.
- **Descripción y evidencia:** se crea un ThreadPoolExecutor dentro de un context manager y se espera con asyncio.wait_for. Si el future excede el tiempo, al salir del context manager el executor puede esperar a que termine su worker, de modo que el timeout lógico no libera de inmediato el hilo/event loop.
- **Motivo:** el timeout de una operación bloqueante debe incluir también su cleanup real.
- **Impacto:** requests concurrentes pueden acumular hilos bloqueados y superar la latencia esperada.
- **Prioridad:** media.
- **Solución recomendada:** usar un executor compartido acotado y no esperar workers bloqueados en la ruta de timeout; aplicar timeout de socket y política de cancelación explícita.
- **Riesgos de aplicar la solución:** abandonar threads no cancelables aumenta trabajo residual; debe limitarse el tamaño del pool.
- **Dependencias:** límites de request y validate_url async.
- **Verificación:** resolver que bloquee más que el timeout, medir tiempo total y número de threads, y probar concurrencia alta.
- **Certeza:** Hipótesis.

### RC-M-009 — config.reload() pierde extra_headers

- **Archivo/carpeta:** config.py.
- **Línea/sección aproximada:** config.py:245-252 frente a 255-282.
- **Descripción y evidencia:** la inicialización de HEADERS incluye la expansión de SETTINGS.http.extra_headers. El mismo diccionario reconstruido por reload() omite esa expansión.
- **Motivo:** el comportamiento después de recargar configuración difiere del arranque.
- **Impacto:** tests, rotación o herramientas que llamen reload() pierden cabeceras upstream y pueden fallar autenticación, trazabilidad o compatibilidad.
- **Prioridad:** media.
- **Solución recomendada:** extraer un helper único para construir headers y usarlo en import y reload.
- **Riesgos de aplicar la solución:** headers duplicados o prefijos X- incorrectos si el contrato de extra_headers no se documenta.
- **Dependencias:** HttpClient, tests de config y nombres de variables.
- **Verificación:** configurar un header extra, importar y luego llamar config.reload(); comparar ambos diccionarios.
- **Certeza:** Confirmado.

### RC-M-010 — Métricas de actividad y cola no representan el estado real

- **Archivo/carpeta:** core/metrics.py, core/services.py.
- **Línea/sección aproximada:** core/metrics.py:45-55; core/services.py:174-190, 413, 490.
- **Descripción y evidencia:** MetricsManager decide habilitación leyendo os.getenv("ENABLE_METRICS"), mientras existe SETTINGS.metrics.enabled. Además, enqueue actualiza queue size solo al añadir; no hay decremento tras claim/completado, y el servicio llama set_active_downloads(0) en terminales sin una transición observada a 1.
- **Motivo:** hay dos fuentes de configuración y las métricas no se actualizan en todos los estados.
- **Impacto:** dashboards muestran queue size/active downloads incorrectos y pueden ocultar saturación.
- **Prioridad:** media.
- **Solución recomendada:** leer la configuración tipada y actualizar gauges en cada transición persistida, recalculando desde el repositorio cuando sea necesario.
- **Riesgos de aplicar la solución:** recalcular en cada transición añade queries; los gauges deben ser idempotentes tras reinicio.
- **Dependencias:** RC-M-001, state machine del repositorio y health/monitoring.
- **Verificación:** prueba de ciclo queued→running→completed/failed/cancelled, consulta /api/metrics y comprueba valores; prueba con RYLIOX_METRICS__ENABLED=false.
- **Certeza:** Confirmado.

### RC-M-011 — Health check SQLite inspecciona un atributo inexistente

- **Archivo/carpeta:** web/routes/system.py, core/repository.py, core/session_store.py.
- **Línea/sección aproximada:** web/routes/system.py:375-401.
- **Descripción y evidencia:** el health check considera activa una conexión de SessionStore si getattr(session_store, "_conn", None) existe. SessionStore usa _connection() y crea conexiones por operación; no mantiene _conn. El repositorio sí tiene _conn, pero el resultado global puede quedar en cero si no está inicializado.
- **Motivo:** se está inspeccionando implementación interna que no coincide entre stores, no verificando salud efectiva.
- **Impacto:** falso healthy=false, alertas falsas y posibles fallos del healthcheck de despliegue aun cuando SQLite responda.
- **Prioridad:** media.
- **Solución recomendada:** exponer un método de probe que ejecute SELECT 1/consulta ligera bajo los locks y reporte disponibilidad, no el número de atributos internos.
- **Riesgos de aplicar la solución:** el probe abre I/O en cada llamada; aplicar timeout y no incluirlo en rutas públicas demasiado frecuentes.
- **Dependencias:** endpoint /api/health, Compose healthcheck y lifecycle de stores.
- **Verificación:** arrancar con base válida y comprobar health detallado; simular corrupción/bloqueo y comprobar que sí se detecta.
- **Certeza:** Confirmado.

### RC-M-012 — La creación de sesión admin no está en la lista de rate limiting

- **Archivo/carpeta:** web/server.py.
- **Línea/sección aproximada:** web/server.py:62-69, 425-451.
- **Descripción y evidencia:** el middleware limita un conjunto fijo de endpoints; /api/admin/session no aparece en la lista observada. El endpoint compara un token y establece la cookie de sesión.
- **Motivo:** el endpoint de login es precisamente el punto que debe absorber intentos de fuerza bruta, aunque el token tenga longitud mínima.
- **Impacto:** más intentos por IP, consumo de HMAC/logs y mayor margen para tokens humanos débiles; el impacto depende de que el servicio sea remoto.
- **Prioridad:** media.
- **Solución recomendada:** rate limit específico por IP y, si procede, backoff por fallos para este endpoint; no loguear el token.
- **Riesgos de aplicar la solución:** NATs pueden agrupar usuarios legítimos; ofrecer límites separados para local, proxy autenticado y remoto.
- **Dependencias:** confianza en IP proxy, mensajes 429 y UI de autenticación.
- **Verificación:** enviar N intentos inválidos desde una misma IP y afirmar 429; comprobar que un intento válido posterior funciona dentro del límite.
- **Certeza:** Hipótesis de abuso remoto; la ausencia en la lista está confirmada.

### RC-M-013 — Exposición de detalles de excepciones en respuestas HTTP

- **Archivo/carpeta:** web/routes/books.py.
- **Línea/sección aproximada:** web/routes/books.py:100-111, 155-176, 232-245.
- **Descripción y evidencia:** errores de búsqueda y capítulos incluyen details: str(exc) y, en algunas ramas, str(exc) como error. Esas excepciones pueden contener URLs remotas, parámetros, respuestas o información de librerías.
- **Motivo:** los detalles internos deben quedarse en logs correlacionados, especialmente en un API que puede exponerse detrás de proxy.
- **Impacto:** exposición de estructura upstream, datos de sesión indirectos o información útil para ataques; también acopla el frontend a mensajes no estables.
- **Prioridad:** media.
- **Solución recomendada:** devolver códigos y mensajes estables; mantener la excepción completa en logs sanitizados y un request ID para soporte.
- **Riesgos de aplicar la solución:** se pierde contexto útil al depurar; documentar cómo buscar el request ID.
- **Dependencias:** ErrorCode, logging y UI de errores.
- **Verificación:** simular excepciones con URLs, cookies o paths y verificar que la respuesta no los contiene.
- **Certeza:** Hipótesis de contenido sensible; la inclusión de la excepción está confirmada.

### RC-M-014 — Restaurar la cadena de auditoría carga todo el log activo

- **Archivo/carpeta:** core/audit.py.
- **Línea/sección aproximada:** _restore_chain_state, aproximadamente core/audit.py:278-288.
- **Descripción y evidencia:** la restauración lee las líneas activas a una lista antes de reconstruir estado; la verificación de integridad sí tiene recorrido streaming, pero esa ruta de arranque no.
- **Motivo:** el log de auditoría es append-only y puede crecer durante meses; el uso de memoria no está limitado por retención si el archivo activo no rota.
- **Impacto:** arranque lento o agotamiento de memoria al restaurar un log grande.
- **Prioridad:** media.
- **Solución recomendada:** leer solo la última entrada válida y metadatos de conteo, o rotar/compactar con un checkpoint HMAC verificable; conservar la verificación completa como tarea separada.
- **Riesgos de aplicar la solución:** un checkpoint incorrecto podría romper la cadena; probar recuperación ante truncamiento y corrupción.
- **Dependencias:** política de retención, verify_integrity, HMAC y despliegue.
- **Verificación:** generar un log grande, medir RSS/tiempo de arranque y comprobar que el siguiente hash conserva la cadena.
- **Certeza:** Confirmado.

### RC-M-015 — Redacción de auditoría no recorre listas de objetos ni todas las claves de cookies

- **Archivo/carpeta:** core/audit.py.
- **Línea/sección aproximada:** core/audit.py:409-448.
- **Descripción y evidencia:** _sanitize_details recurre en diccionarios, pero para listas deja intactos los elementos que no son strings. La lista de claves sensibles no incluye explícitamente cookie/cookies. Un detalle con lista de diccionarios puede conservar valores secretos.
- **Motivo:** los detalles de auditoría son una frontera de persistencia; sanitizar por tipo superficial no basta.
- **Impacto:** exposición de cookies/tokens en audit log y en el mirror de logging si un caller pasa estructuras anidadas.
- **Prioridad:** media.
- **Solución recomendada:** sanitizador recursivo común para dict/list/tuple con claves sensibles normalizadas y límites de profundidad/tamaño; añadir tests de cookies anidadas.
- **Riesgos de aplicar la solución:** redacción demasiado amplia reduce utilidad diagnóstica; preservar tipos simples y documentar claves.
- **Dependencias:** todos los callers de audit.log, migración de logs y tests OWASP.
- **Verificación:** pasar {"cookies":[{"name":"x","value":"..."}]} y estructuras profundas; afirmar que nunca aparecen los valores en archivo ni logger.
- **Certeza:** Hipótesis de que un caller entregue esa forma; el hueco de sanitización está confirmado.

### RC-M-016 — El frontend no incluye credenciales de forma uniforme para API externa

- **Archivo/carpeta:** frontend/src/lib/api.ts, configuración Astro/CORS.
- **Línea/sección aproximada:** frontend/src/lib/api.ts:168-181, 225-286; frontend/astro.config.mjs.
- **Descripción y evidencia:** authenticateAdmin usa credentials: include, pero request() no lo establece. EventSource de progreso tampoco permite configurar withCredentials en la instancia usada. La configuración admite PUBLIC_API_BASE externa y el backend configura CORS con credenciales.
- **Motivo:** con frontend y API en orígenes distintos, el navegador no enviará la cookie de sesión como en same-origin.
- **Impacto:** login visualmente exitoso pero llamadas REST/SSE posteriores reciben 401 o no progresan en despliegues separados.
- **Prioridad:** media.
- **Solución recomendada:** usar credentials: include en todas las requests cuando el modo externo lo requiera y crear EventSource con { withCredentials: true } o sustituirlo por fetch-streaming; revisar CORS y SameSite.
- **Riesgos de aplicar la solución:** credenciales cross-origin amplían superficie; solo habilitarlas con allowlist exacta y HTTPS.
- **Dependencias:** RC-H-002, cookies, CORS y documentación de PUBLIC_API_BASE.
- **Verificación:** frontend en origen A y API en origen B con cookie válida; comprobar REST y SSE autenticados, y que un origen no permitido falle.
- **Certeza:** Hipótesis de fallo cross-origin; las opciones de fetch observadas están confirmadas.

### RC-M-017 — CSP bloquea las fuentes externas declaradas y permite unsafe-eval

- **Archivo/carpeta:** config.py, .env.example, frontend/src/pages/index.astro.
- **Línea/sección aproximada:** config.py:70-78; .env.example:65-71; index.astro:45-55.
- **Descripción y evidencia:** el frontend enlaza fonts.googleapis.com y fonts.gstatic.com. La CSP por defecto permite style-src self y no declara font-src/style-src para Google; al mismo tiempo incluye script-src unsafe-eval.
- **Motivo:** la política efectiva contradice el HTML y debilita la defensa XSS.
- **Impacto:** fuentes no cargan en un despliegue con headers activos; añadir dominios sin revisar puede aumentar el riesgo, y unsafe-eval permite patrones de ejecución que una CSP estricta bloquearía.
- **Prioridad:** media.
- **Solución recomendada:** autoalojar fuentes o declarar únicamente los orígenes exactos necesarios (style-src, font-src) y eliminar unsafe-eval tras verificar Astro/React; mantener unsafe-inline solo con justificación.
- **Riesgos de aplicar la solución:** estilos o build pueden romperse; comprobar hashes/nonces y modo producción.
- **Dependencias:** frontend build, headers de seguridad y política de privacidad.
- **Verificación:** navegador con CSP report-only y luego enforce, revisar consola y ejecutar tests de carga de estilos; verificar que scripts no necesitan eval.
- **Certeza:** Confirmada la discrepancia; el efecto visual depende de headers realmente activos.

### RC-M-018 — El cliente HTTP materializa la respuesta antes de aplicar el límite

- **Archivo/carpeta:** core/http_client.py.
- **Línea/sección aproximada:** _enforce_response_limit, aproximadamente core/http_client.py:392-398.
- **Descripción y evidencia:** el límite se calcula con len(response.content) después de que httpx ya ha leído y materializado el cuerpo completo. El valor máximo configurado es 50 MB.
- **Motivo:** un límite posterior evita persistir una respuesta excesiva, pero no evita su coste de memoria.
- **Impacto:** múltiples respuestas grandes upstream pueden multiplicar memoria; un servidor externo lento o malicioso puede mantener buffers grandes.
- **Prioridad:** media.
- **Solución recomendada:** usar httpx.stream, contar bytes durante lectura y abortar al superar el límite; conservar límites separados para texto, JSON, imagen y book.
- **Riesgos de aplicar la solución:** streaming cambia la interfaz y manejo de retries; garantizar cierre de response en todos los paths.
- **Dependencias:** plugins de assets/capítulos y tests HTTP.
- **Verificación:** transporte fake que entregue un body mayor al límite por chunks; confirmar abort temprano, cierre del stream y excepción estable.
- **Certeza:** Confirmado el orden de materialización; el impacto de concurrencia es hipótesis.

### RC-M-019 — get_cookies() pierde multiplicidad por nombre

- **Archivo/carpeta:** core/session_store.py.
- **Línea/sección aproximada:** core/session_store.py:485-489.
- **Descripción y evidencia:** get_cookie_records() conserva dominio/path, pero get_cookies() aplana a dict[name] = value. Dos cookies con el mismo nombre en dominios o paths distintos se pisan según el orden de consulta.
- **Motivo:** el modelo de almacenamiento reconoce atributos RFC, pero una API de lectura destruye parte del contrato.
- **Impacto:** autenticación intermitente o cookies incorrectas enviadas al upstream; la UI no puede representar fielmente la sesión.
- **Prioridad:** media.
- **Solución recomendada:** usar registros completos como API primaria y reservar el dict plano para un caso explícitamente “por nombre”; al construir el jar, mantener dominio/path.
- **Riesgos de aplicar la solución:** clientes existentes esperan dict[str,str]; añadir endpoint/versión o adaptador de compatibilidad.
- **Dependencias:** frontend cookie editor, HttpClient y migraciones.
- **Verificación:** guardar dos registros de mismo nombre con distinto dominio/path; comprobar lectura, serialización y envío correcto.
- **Certeza:** Confirmado.

### RC-M-020 — DTO lanza KeyError en vez de error de validación

- **Archivo/carpeta:** core/dto.py.
- **Línea/sección aproximada:** core/dto.py:58-75.
- **Descripción y evidencia:** DownloadJobDTO.model_validate({}) ejecuta data["book_id"] antes de Pydantic. La ausencia de un campo requerido produce KeyError, no ValidationError.
- **Motivo:** sobreescribir model_validate debe preservar la semántica del framework.
- **Impacto:** callers que capturan ValidationError pueden obtener 500 o errores no normalizados ante datos corruptos de DB/API.
- **Prioridad:** media.
- **Solución recomendada:** no indexar claves requeridas antes de delegar; dejar que Pydantic valide o usar data.get y conservar el error estructurado.
- **Riesgos de aplicar la solución:** puede cambiar mensajes de error y fixtures; es el comportamiento esperado y debe actualizarse el contrato.
- **Dependencias:** repositorio, migraciones y tests DTO.
- **Verificación:** tests para {}, {"book_id": None} y tipos erróneos; afirmar ValidationError y respuesta API estable.
- **Certeza:** Confirmado.

### RC-M-021 — Health detallado depende de una llamada externa secuencial

- **Archivo/carpeta:** web/routes/system.py.
- **Línea/sección aproximada:** _check_external_apis, aproximadamente web/routes/system.py:328-372.
- **Descripción y evidencia:** cada health detallado crea un httpx.AsyncClient nuevo y ejecuta un GET a config.BASE_URL con timeout de 10 s, secuencialmente. También devuelve URL y str(e) en el modelo de salud.
- **Motivo:** la disponibilidad del sitio upstream y la apertura de un health endpoint local son preocupaciones distintas.
- **Impacto:** probes y orquestadores pueden tardar 10 s o declarar el servicio no saludable por una caída externa; creación frecuente de clientes añade sockets/I/O.
- **Prioridad:** media.
- **Solución recomendada:** separar liveness/readiness/dependency health, reutilizar cliente o aplicar cache TTL, y devolver errores categorizados sin detalles internos.
- **Riesgos de aplicar la solución:** health menos sensible a cambios upstream; documentar qué endpoint debe usar el orquestador.
- **Dependencias:** RC-M-011, Compose y monitorización.
- **Verificación:** mock upstream lento/caído y medir latencia de liveness/readiness; comprobar que el servicio local sigue healthy según la política elegida.
- **Certeza:** Confirmado el patrón; prioridad operacional depende del uso del endpoint.

### RC-M-022 — Extras de dependencias y lock reproducible requieren corrección/validación

- **Archivo/carpeta:** pyproject.toml, uv.lock, frontend lockfiles.
- **Línea/sección aproximada:** pyproject.toml:25-80.
- **Descripción y evidencia:** hay dependencias directas de red que no aparecen como imports de la aplicación (requests, urllib3, certifi, charset-normalizer, idna, fake-useragent, entre otras); varias parecen heredadas de una implementación anterior o de un allowlist del launcher. El extra all declara ryliox[dev,e2e,security], una referencia al propio proyecto que puede producir ciclo o resolver de forma inesperada.
- **Motivo:** dependencias innecesarias amplían cadena de suministro, tiempo de instalación y superficie de vulnerabilidades; un extra cíclico compromete reproducibilidad.
- **Impacto:** actualizaciones de seguridad más costosas, lock ambiguo y entornos que instalan paquetes no usados.
- **Prioridad:** media.
- **Solución recomendada:** ejecutar uv tree/imports en un entorno limpio, identificar consumidores transitivos y eliminar solo directas no necesarias; definir all como unión explícita de requisitos o confirmar con uv lock.
- **Riesgos de aplicar la solución:** un paquete puede ser usado dinámicamente por launcher, plugins o integración externa; no eliminar por grep aislado.
- **Dependencias:** launcher/_runtime.py, lockfile y CI.
- **Verificación:** en entorno desechable ejecutar uv lock --check, uv sync --extra all, uv tree --outdated, tests completos y smoke de launcher; comparar wheel/imports.
- **Certeza:** Hipótesis de inutilidad/ciclo; la declaración y ausencia de imports directos observados están confirmadas.

### RC-M-023 — CI no ejecuta de forma predeterminada las suites de seguridad, e2e, a11y ni performance

- **Archivo/carpeta:** .github/workflows/ci.yml, tests/conftest.py, tests/README.md.
- **Línea/sección aproximada:** CI test pytest sin flags; tests/conftest.py options --run-slow, --run-e2e, --run-performance, --run-security; README de tests, aproximadamente líneas 40-69.
- **Descripción y evidencia:** los grupos opt-in están saltados por defecto y CI ejecuta solo pytest sin esos flags. La documentación indica además que no hay cobertura configurada. CI tampoco invoca bandit, pip-audit o detect-secrets, aunque existen como extra.
- **Motivo:** el nombre Full test matrix de README no describe lo que protege el gate principal.
- **Impacto:** regresiones de seguridad, accesibilidad, browser e integración pueden pasar sin bloquear merges; no existe tendencia cuantitativa de cobertura.
- **Prioridad:** media.
- **Solución recomendada:** jobs separados y explícitos con dependencias/evidencias adecuadas: unit/contract cada PR, integración controlada, security estático, a11y/e2e programado o en cambios de frontend, performance nocturno; publicar cobertura sin imponer un umbral irreal inicialmente.
- **Riesgos de aplicar la solución:** CI más lento/flaky; aislar suites con servicios, retries mínimos y artifacts de diagnóstico.
- **Dependencias:** disponibilidad de browsers, credentials de prueba y fixtures.
- **Verificación:** revisar el summary de Actions y hacer que un test de cada suite falle en una rama de prueba; comprobar que el job correspondiente falla.
- **Certeza:** Confirmado.

## 8. Problemas de prioridad baja

### RC-L-001 — Timestamp JSON contiene literalmente %f

- **Archivo/carpeta:** core/logging_config.py.
- **Línea/sección aproximada:** core/logging_config.py:42.
- **Descripción y evidencia:** time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", ...) usa time.strftime, que no sustituye %f por microsegundos.
- **Motivo:** logs que parecen ISO-8601 pero contienen un marcador literal rompen parsers y ordenación temporal precisa.
- **Impacto:** ingestión o búsqueda de logs menos fiable.
- **Prioridad:** baja.
- **Solución recomendada:** usar datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").
- **Riesgos de aplicar la solución:** cambiar formato que consumidores ya parsean; anunciar la nueva versión del esquema.
- **Dependencias:** dashboards y collectors.
- **Verificación:** formatear un LogRecord y afirmar que el timestamp no contiene %f y es parseable.
- **Certeza:** Confirmado.

### RC-L-002 — Límite temporal del SSE no coincide con el comentario

- **Archivo/carpeta:** web/routes/downloads.py.
- **Línea/sección aproximada:** progress_stream, web/routes/downloads.py:283-289.
- **Descripción y evidencia:** max_iterations = 3600, mientras el heartbeat es cada 15 segundos; el comentario dice 1 hora máximo, pero el límite permite aproximadamente 15 horas.
- **Motivo:** el límite está expresado en iteraciones, no en tiempo monotónico.
- **Impacto:** conexiones abandonadas pueden vivir mucho más de lo esperado y consumir tareas/sockets.
- **Prioridad:** baja.
- **Solución recomendada:** usar deadline monotónico explícito o calcular ceil(3600 / heartbeat) para una hora real.
- **Riesgos de aplicar la solución:** clientes con descargas legítimas mayores necesitarán reconexión.
- **Dependencias:** frontend SSE y estado persistente del job.
- **Verificación:** fake clock o test de stream que avance 3601 heartbeats y compruebe cierre en el deadline documentado.
- **Certeza:** Confirmado.

### RC-L-003 — Mapa de assets puede apuntar a una extensión inexistente

- **Archivo/carpeta:** plugins/assets.py.
- **Línea/sección aproximada:** plugins/assets.py:51-64, 80-87.
- **Descripción y evidencia:** download_image puede cambiar save_path según magic bytes; download_all_images ignora el Path devuelto y registra el path original. Si la URL no tiene extensión y el contenido es PNG, el mapa apunta al nombre que no se escribió.
- **Motivo:** el valor de retorno ya contiene la ruta canónica.
- **Impacto:** callers futuros que usen el mapa fallarán o referenciarán un archivo ausente.
- **Prioridad:** baja.
- **Solución recomendada:** registrar el resultado retornado y omitir/registrar explícitamente las descargas None.
- **Riesgos de aplicar la solución:** cambia el mapa para consumidores que dependían del nombre original; el comportamiento correcto debe documentarse.
- **Dependencias:** HtmlProcessor, EPUB y tests de assets.
- **Verificación:** fake HTTP con URL .bin y bytes PNG; afirmar que el mapa contiene el .png existente.
- **Certeza:** Confirmado.

### RC-L-004 — Defensa de host de assets está definida pero no se aplica en sus métodos públicos

- **Archivo/carpeta:** plugins/assets.py, plugins/chapters.py.
- **Línea/sección aproximada:** plugins/assets.py:46-64, 175-183; plugins/chapters.py:109-119.
- **Descripción y evidencia:** _ensure_safe_asset_url y _sanitize_remote_url existen, pero las rutas principales llaman directamente a HttpClient. La allowlist del cliente sí es una defensa real, pero la defensa local no se aplica si el plugin se instancia con un transport/client permitido de forma amplia.
- **Motivo:** los plugins tienen contratos públicos que deberían conservar una frontera mínima independiente.
- **Impacto:** una reutilización futura o test mal configurado puede descargar hosts no previstos; es una oportunidad de hardening.
- **Prioridad:** baja.
- **Solución recomendada:** aplicar una función común en métodos públicos y eliminar helpers solo después de centralizar la política; permitir URLs relativas mediante resolución controlada.
- **Riesgos de aplicar la solución:** puede bloquear CDN legítimos o romper URLs relativas; alinear allowlists con HttpClient.
- **Dependencias:** RC-M-007, HTTP client y fuentes upstream.
- **Verificación:** fake client que acepte cualquier host y prueba de cada método con host permitido/no permitido.
- **Certeza:** Hipótesis de impacto; el código no llama esos helpers y la defensa del cliente está confirmada.

### RC-L-005 — Sanitización de SVG basada solo en detección de contenido

- **Archivo/carpeta:** plugins/assets.py.
- **Línea/sección aproximada:** plugins/assets.py:29-43.
- **Descripción y evidencia:** contenido que empieza por <svg, <?xml o <html se clasifica como .svg, sin sanitización de elementos, referencias externas o scripts.
- **Motivo:** SVG es un formato activo en algunos lectores y puede transportar contenido no esperado.
- **Impacto:** EPUB generado puede contener markup ejecutable o rastreo en lectores vulnerables; depende del lector y de la confianza en upstream.
- **Prioridad:** baja.
- **Solución recomendada:** aceptar raster por defecto, sanitizar SVG con allowlist o convertirlo a imagen segura; no confiar solo en Content-Type/magic.
- **Riesgos de aplicar la solución:** pérdida de gráficos vectoriales legítimos y cambios visuales.
- **Dependencias:** compatibilidad EPUB, Pillow y política de contenido.
- **Verificación:** fixture SVG con script/event handler/external href; comprobar que se rechaza o queda sanitizado y que un SVG legítimo conserva su apariencia.
- **Certeza:** Hipótesis.

### RC-L-006 — Token plugin registrado sin dependencia declarada ni consumidor observado

- **Archivo/carpeta:** plugins/token.py, core/kernel.py, pyproject.toml.
- **Línea/sección aproximada:** plugins/token.py:1-45; core/kernel.py:119-139.
- **Descripción y evidencia:** TokenPlugin importa tiktoken de forma lazy, se registra como plugin, pero tiktoken no está en dependencias y no se encontraron consumidores del plugin fuera del registro. Si se invoca count_tokens, depende de una importación que fallará.
- **Motivo:** una feature registrada debe estar instalada o declararse opcional explícitamente.
- **Impacto:** fallo de runtime si un caller selecciona token; ruido y superficie mantenida sin uso en el producto.
- **Prioridad:** baja.
- **Solución recomendada:** eliminar el registro si no forma parte del producto, o declarar extra token y devolver un error/estado explícito si no está instalado.
- **Riesgos de aplicar la solución:** integraciones externas pueden depender del nombre del plugin; comprobar API pública.
- **Dependencias:** catálogo de plugins y documentación.
- **Verificación:** test de kernel que enumere plugins y test de count_tokens con instalación base y extra.
- **Certeza:** Confirmado el registro y la dependencia ausente; no se conoce uso externo.

### RC-L-007 — El contrato público usa el campo tipográfico ourn

- **Archivo/carpeta:** core/contracts.py, plugins/book.py, plugins/chapters.py, web/schemas.py.
- **Línea/sección aproximada:** core/contracts.py:14; usos en plugins y schemas.
- **Descripción y evidencia:** el campo se llama ourn de forma consistente donde se propaga, aunque el concepto parece ser urn.
- **Motivo:** el typo se convierte en contrato de datos, dificulta onboarding y aumenta riesgo de errores al integrar.
- **Impacto:** consumidores externos deben aprender un nombre incorrecto; renombrarlo sin compatibilidad rompería serializaciones.
- **Prioridad:** baja.
- **Solución recomendada:** introducir alias de lectura/escritura urn, mantener ourn deprecado durante una migración y actualizar documentación/fixtures.
- **Riesgos de aplicar la solución:** cambios incompatibles en Pydantic y datos persistidos.
- **Dependencias:** contratos, API schemas y EPUB plugin.
- **Verificación:** tests con ambos nombres, warnings de deprecación y snapshot de payloads.
- **Certeza:** Confirmado como cuestión de calidad; la intención del autor es inferida.

### RC-L-008 — Etiquetas de accesibilidad hardcodeadas en inglés

- **Archivo/carpeta:** frontend/src/components/LanguageSwitcher.tsx.
- **Línea/sección aproximada:** líneas 20 y 26.
- **Descripción y evidencia:** aria-label="Language selector" y Switch to ... no usan t() aunque la aplicación está internacionalizada.
- **Motivo:** una persona que use la UI en español puede recibir nombres de control en inglés.
- **Impacto:** inconsistencia UX y menor claridad para lectores de pantalla.
- **Prioridad:** baja.
- **Solución recomendada:** añadir claves de i18n para el grupo, acción y nombres de idioma; conservar nombres propios según locale.
- **Riesgos de aplicar la solución:** cambios de longitud pueden afectar layout; revisar ambos idiomas.
- **Dependencias:** locales y tests a11y.
- **Verificación:** cambiar idioma y leer el árbol accesible o afirmar las etiquetas traducidas con test React.
- **Certeza:** Confirmado.

### RC-L-009 — Open Graph apunta a un asset que no existe

- **Archivo/carpeta:** frontend/src/pages/index.astro, frontend/public.
- **Línea/sección aproximada:** index.astro:27, 36.
- **Descripción y evidencia:** og:image y twitter:image apuntan a /og-image.png; el archivo no está en frontend/public.
- **Motivo:** los metadatos publicados deben referenciar recursos reales.
- **Impacto:** previews sociales sin imagen y errores 404.
- **Prioridad:** baja.
- **Solución recomendada:** añadir un asset versionado optimizado o eliminar las etiquetas hasta disponer de uno.
- **Riesgos de aplicar la solución:** aumentar peso del bundle/imagen; optimizar dimensiones y formato.
- **Dependencias:** branding y pipeline frontend.
- **Verificación:** build y curl de /og-image.png; validadores Open Graph.
- **Certeza:** Confirmado que el archivo está ausente; la preview se deduce.

### RC-L-010 — Documentación contradice el estado del repositorio

- **Archivo/carpeta:** README.md.
- **Línea/sección aproximada:** estructura de proyecto y roadmap, aproximadamente líneas 329-341.
- **Descripción y evidencia:** el árbol documenta epubcheck/ aunque la carpeta no está versionada; el roadmap marca EPUB validation como no implementado. También promociona hot-pluggable plugins aunque el registro de core/kernel.py es estático.
- **Motivo:** onboarding y expectativas de arquitectura deben corresponder al código actual.
- **Impacto:** usuarios buscan archivos inexistentes y asumen descubrimiento dinámico que no existe.
- **Prioridad:** baja.
- **Solución recomendada:** documentar el registro estático actual, renombrar “composable plugins” si es más exacto y eliminar epubcheck/ del árbol hasta que exista.
- **Riesgos de aplicar la solución:** cambios de marketing/documentación sin efecto funcional; revisar enlaces externos.
- **Dependencias:** diseño futuro del kernel y roadmap.
- **Verificación:** script que valide paths referenciados en README o revisión manual en cada cambio de estructura.
- **Certeza:** Confirmado.

### RC-L-011 — Finales de línea, BOM y estilo textual inconsistentes

- **Archivo/carpeta:** múltiples Python/TSX/CSS/config frontend.
- **Línea/sección aproximada:** archivos reportados por file; .editorconfig.
- **Descripción y evidencia:** file mostró mezcla de CRLF/LF y BOM en al menos frontend/postcss.config.js y frontend/src/env.d.ts, mientras .editorconfig declara LF. El problema no impide parseo, pero el formato no es uniforme.
- **Motivo:** diffs ruidosos, herramientas distintas y riesgo de cambios masivos involuntarios.
- **Impacto:** mantenimiento y revisión menos fiables.
- **Prioridad:** baja.
- **Solución recomendada:** normalizar gradualmente solo archivos tocados, añadir .gitattributes/check de finales de línea y no reformatear el repositorio completo sin una decisión separada.
- **Riesgos de aplicar la solución:** un commit de normalización grande oscurece cambios funcionales.
- **Dependencias:** formatter/CI.
- **Verificación:** git ls-files -z | xargs -0 file y un check que rechace BOM/CRLF fuera de excepciones.
- **Certeza:** Confirmado.

### RC-L-012 — Emojis y mensajes de presentación no siguen una política uniforme

- **Archivo/carpeta:** README, CONTRIBUTING, CHANGELOG, comentarios y UI/documentación.
- **Línea/sección aproximada:** múltiples; el conteo estático encontró aproximadamente 149 ocurrencias en fuente/documentación/logs.
- **Descripción y evidencia:** hay emojis en tablas, títulos, comentarios, mensajes y documentación. Algunos son parte del branding/UI y otros aparecen en mensajes técnicos o logs.
- **Motivo:** el usuario solicitó revisar emojis; sin una convención, la mezcla dificulta consistencia, búsquedas y consumo de logs.
- **Impacto:** bajo en funcionalidad; potencialmente molesto en terminales, parsers, accesibilidad o mensajes de soporte.
- **Prioridad:** baja.
- **Solución recomendada:** conservar emojis intencionales de marca/UI, retirarlos de logs, errores y contratos, y documentar una guía de estilo.
- **Riesgos de aplicar la solución:** eliminar símbolos de UI puede reducir affordance; cambiar snapshots de tests.
- **Dependencias:** i18n, README y logging.
- **Verificación:** lint/text check para logs y revisión visual de ambas variantes de UI.
- **Certeza:** Confirmado el conteo; la necesidad de eliminar cada ocurrencia es criterio de producto.

### RC-L-013 — Service worker contiene handlers de producto sin implementación

- **Archivo/carpeta:** frontend/public/service-worker.js.
- **Línea/sección aproximada:** líneas 68-92.
- **Descripción y evidencia:** el handler sync llama a doBackgroundSync() que solo hace console.log; el handler push muestra notificaciones pero no se observa registro/permiso/flujo backend correspondiente.
- **Motivo:** código future implementation expuesto en producción puede crear expectativas y comportamiento parcial.
- **Impacto:** logs innecesarios, superficie de mantenimiento y posibles notificaciones si un tercero activa el evento.
- **Prioridad:** baja.
- **Solución recomendada:** eliminar handlers no soportados o implementar el contrato completo; conservar únicamente caching/offline realmente probado.
- **Riesgos de aplicar la solución:** eliminarlo rompe una integración futura no documentada; comprobar manifest y roadmap.
- **Dependencias:** PWA, backend de notificaciones y UX offline.
- **Verificación:** tests de service worker para install/fetch/offline y ausencia de side effects no soportados si se eliminan.
- **Certeza:** Confirmado que sync es placeholder; el impacto adicional es hipótesis.

### RC-L-014 — Utilidades de accesibilidad y foco están duplicadas

- **Archivo/carpeta:** frontend/src/lib/a11y-index.ts, frontend/src/lib/a11y-utils.ts, frontend/src/lib/focus-management.ts, frontend/src/components/KeyboardNavigation.tsx.
- **Línea/sección aproximada:** barrel y KeyboardNavigation.tsx:147-195.
- **Descripción y evidencia:** hay helpers de accesibilidad/foco en varias ubicaciones y KeyboardNavigation define otro useFocusTrap. El barrel a11y-index.ts no aparece importado fuera de sí mismo en la búsqueda realizada.
- **Motivo:** varias implementaciones para el mismo comportamiento pueden divergir en focus restore, escape y cleanup.
- **Impacto:** bugs a11y difíciles de reproducir y código mantenido sin consumidor.
- **Prioridad:** baja.
- **Solución recomendada:** elegir una implementación canónica, migrar imports y retirar el barrel solo después de confirmar consumidores externos.
- **Riesgos de aplicar la solución:** romper imports públicos no visibles en el repositorio; mantener un alias de deprecación si el package se consume externamente.
- **Dependencias:** tests a11y y componentes de modal/dialog.
- **Verificación:** rg de referencias, bun run test y auditoría manual con teclado/lector de pantalla.
- **Certeza:** Hipótesis de código eliminable; el conjunto de referencias internas observado es limitado.

### RC-L-015 — Estado de caché y ciclo del kernel tienen bordes de thread-safety

- **Archivo/carpeta:** core/cache.py, core/kernel.py.
- **Línea/sección aproximada:** core/cache.py:193-204; core/kernel.py:35-56.
- **Descripción y evidencia:** __len__/__contains__ acceden a la caché async sin el lock que usan operaciones mutantes; Kernel.__aexit__ cambia _entered después de cerrar, por lo que una excepción durante close puede dejar estado aparente de entrada.
- **Motivo:** helpers de consulta y lifecycle deben conservar las mismas invariantes que el camino principal.
- **Impacto:** resultados de caché inconsistentes bajo concurrencia y reentrada/cierre ambiguo en errores.
- **Prioridad:** baja.
- **Solución recomendada:** proteger lecturas con el mismo lock y hacer try/finally para limpiar estado del kernel.
- **Riesgos de aplicar la solución:** más contención de caché; cerrar dos veces puede ocultar el error original si no se diseña con cuidado.
- **Dependencias:** tests async y lifecycle de app.
- **Verificación:** tests concurrentes de hit/miss, close que lanza y segunda entrada/salida.
- **Certeza:** Hipótesis.

## 9. Bugs confirmados

Los siguientes son defectos observados directamente, independientemente de que su impacto final sea alto o bajo:

- RC-H-003: falta validación de book_id en rutas.
- RC-M-001: admisión de cola no atómica.
- RC-M-002: cleanup elimina extensiones sin comprobar propiedad.
- RC-M-003: error de descarga deja directorio parcial.
- RC-M-004: formato desconocido cae en EPUB.
- RC-M-005: HTML procesado duplicado en memoria.
- RC-M-006: cancelación ausente en fases largas.
- RC-M-009: reload omite cabeceras extra.
- RC-M-010: gauges/configuración de métricas inconsistentes.
- RC-M-011: health SQLite usa _conn inexistente en SessionStore.
- RC-M-014: restore de auditoría carga el archivo activo completo.
- RC-M-019: aplanado de cookies pierde dominio/path.
- RC-M-020: DownloadJobDTO.model_validate puede producir KeyError.
- RC-L-001: timestamp literal %f.
- RC-L-002: duración SSE real no coincide con comentario.
- RC-L-003: mapa de asset apunta al path original tras cambiar extensión.
- RC-L-006: plugin de tokens registrado sin dependencia base.
- RC-L-007: typo ourn en contrato.
- RC-L-008: labels a11y no traducidas.
- RC-L-009: imagen OG ausente.
- RC-L-010: paths/claims documentales no corresponden al árbol.
- RC-L-011: finales de línea/BOM inconsistentes.
- RC-L-012: política de emojis ausente/inconsistente.
- RC-L-013: handlers PWA placeholder.

## 10. Riesgos potenciales/hipótesis que requieren validación

Estas observaciones no deben convertirse en afirmaciones de vulnerabilidad sin las pruebas indicadas:

- RC-H-001: impacto exacto del bind mount depende del comportamiento Docker del host y del fallback servido.
- RC-H-002: explotación de forwarded headers depende de si existe un proxy que filtre cabeceras y de cómo se publica el puerto.
- RC-H-004: Pydantic no pudo importarse en este entorno; hay que confirmar qué aliases planos consume realmente una versión limpia.
- RC-H-005: DoS práctico depende de concurrencia, límites del proxy y recursos del worker.
- RC-M-007: bypass DNS requiere respuesta multivaluada/rebinding y conocer cómo conecta finalmente httpx.
- RC-M-008: espera residual depende del comportamiento del resolver y del executor.
- RC-M-012: fuerza bruta remota depende de que el servidor se exponga y de la entropía efectiva del token.
- RC-M-013: fuga sensible depende del texto concreto de excepciones upstream.
- RC-M-015: fuga de cookie requiere que un caller pase listas/datos con esa forma.
- RC-M-016: fallo solo se materializa cuando frontend y API tienen distinto origen y la política de cookies/CORS lo permite.
- RC-M-018: presión de memoria depende del número/tamaño de respuestas simultáneas.
- RC-M-021: efecto operacional depende de qué probe usa el orquestador.
- RC-M-022: el ciclo del extra all requiere uv lock en un entorno con caché escribible.
- RC-L-004: la defensa primaria actual del HttpClient puede hacer que el hueco no sea explotable en producción.
- RC-L-005: el riesgo de SVG depende del lector EPUB/PDF y del contenido upstream.
- RC-L-014 y RC-L-015: el impacto depende de consumidores externos y concurrencia real.

## 11. Seguridad

### Superficie y controles observados

- La API local está deliberadamente sin autenticación completa; README advierte que el endpoint de cookies puede devolver valores almacenados y que no debe exponerse el puerto.
- Para binds no locales, el servidor exige token admin de longitud mínima y claves de sesión/auditoría de producción.
- Hay sesión admin derivada mediante HMAC, cabecera bearer, cookie HttpOnly/configurable y same-origin para métodos mutantes.
- HttpClient mantiene allowlist de hosts y revisa redirecciones; esto es una defensa importante contra SSRF.
- Se validan paths de output y se comprueba que capítulos/assets no escapen sus raíces.
- Cookies se cifran en SQLite; se observa cuidado con permisos de archivos de clave.
- Auditoría usa HMAC y redacción, aunque tiene el hueco de estructuras anidadas de RC-M-015.
- No se encontró un valor de secreto expuesto en el árbol revisado. .mcp.json referencia una variable de entorno para Context7, no su valor.
- No existe SECURITY.md versionado; la guía de contribución sí pide redacción de tokens/cookies.

### Hallazgos relacionados

Los riesgos prioritarios son RC-H-002 (trust boundary de proxy), RC-H-003 (validación de identificador), RC-H-004 (configuración silenciosamente inefectiva), RC-H-005/RC-M-018 (agotamiento de memoria), RC-M-007 (DNS), RC-M-012 (login sin rate limit), RC-M-013 (detalles de excepción), RC-M-015 (redacción), RC-M-016 (credenciales cross-origin), RC-M-017 (CSP) y RC-L-005 (SVG).

También conviene revisar antes de un despliegue remoto:

- fijar acciones de GitHub por SHA, especialmente actions/checkout@v4 y oven-sh/setup-bun@v2, siguiendo la misma disciplina que ya se usa para setup-uv;
- ejecutar bandit, pip-audit y detect-secrets en CI, con exclusiones justificadas y revisión de falsos positivos;
- declarar explícitamente la confianza en proxy y la política de Host, Origin, Forwarded y CORS;
- evitar devolver paths absolutos de output a clientes remotos salvo que el contrato lo necesite;
- añadir SECURITY.md con modelo de despliegue, disclosure y límites del modo local;
- revisar el .mcp.json y mantener solo integraciones externas necesarias para desarrollo.

## 12. Rendimiento

Los principales costes potenciales son:

- RC-H-005: buffering de hasta 10 MB por request concurrente.
- RC-M-018: respuesta upstream completa antes de aplicar límite de 50 MB.
- RC-M-005: duplicación de HTML procesado por capítulo.
- RC-M-006: cancelación tardía durante I/O/CPU.
- RC-M-008: threads de resolución DNS que pueden sobrevivir al timeout lógico.
- RC-M-014: lectura completa del audit log al arranque.
- RC-M-021: cliente HTTP nuevo y GET externo secuencial por health probe.
- RC-L-002: conexiones SSE potencialmente demasiado largas.

Aspectos favorables: cache TTL con tamaños máximos, límites de assets por libro, retries y timeouts en HTTP, asyncio.to_thread para operaciones de filesystem en rutas de background, SQLite WAL y separación del worker de la ruta HTTP. Debe medirse antes de cambiar arquitectura: un worker local puede ser suficiente para el caso de uso beta, pero no para múltiples procesos/replicas sin coordinación de jobs.

## 13. Calidad y limpieza del código

- La legibilidad general es buena en módulos nuevos: nombres descriptivos, docstrings y tipos en zonas críticas.
- La complejidad se concentra en core/repository.py, core/audit.py, web/dependencies.py, web/server.py y plugins/downloader.py; conviene dividir por invariantes, no aplicar una reescritura masiva.
- config.py mantiene constantes mutables por compatibilidad aunque la documentación describe Settings como inmutable. Esa dualidad es fuente de RC-H-004 y RC-M-009.
- pyproject.toml desactiva numerosas reglas Ruff y excluye frontend completo. Algunas exclusiones son razonables, pero B904, SQL y subprocess deben revisarse por módulos, no globalmente.
- mypy permite definiciones sin tipo y ignore_missing_imports; el gate es útil pero no representa tipado estricto.
- El código usa algunos helpers de compatibilidad (to_dict, from_dict, aliases antiguos) que parecen conservar APIs legadas; deben retirarse solo tras confirmar consumidores.
- El contador de emojis (~149) y la mezcla CRLF/BOM están tratados en RC-L-011/RC-L-012.
- Hay imports/dependencias potencialmente heredados (RC-M-022), pero no se recomienda borrar por intuición.
- Los logs tienen correlación y redacción en varias capas; deben corregirse timestamp (RC-L-001), request IDs no acotados y exposición de excepciones (RC-M-013).

## 14. Código o archivos que podrían eliminarse

No se recomienda eliminar ningún archivo de producción de forma inmediata. Estas son candidaturas condicionadas, con referencias comprobadas y la validación necesaria:

| Candidatura | Evidencia interna | Condición para eliminar |
| --- | --- | --- |
| frontend/src/lib/a11y-index.ts | No se hallaron imports internos fuera del propio barrel. | Confirmar consumidores externos; migrar/exportar desde un punto canónico y ejecutar a11y. Relacionado con RC-L-014. |
| plugins/chapters.py::_sanitize_remote_url | No se hallaron llamadas internas. | Sustituir por una defensa común aplicada en el método público; no borrarlo dejando solo una defensa accidental. RC-L-004. |
| TokenPlugin/registro token | Registrado en kernel, sin consumidor interno y sin tiktoken base. | Decidir si es API pública; retirar registro y tests/documentación o crear extra/dependencia. RC-L-006. |
| Handlers sync/placeholder de service-worker.js | doBackgroundSync solo registra un mensaje; push carece de flujo observado. | Confirmar ausencia de roadmap/consumidores; eliminar o implementar completo. RC-L-013. |
| Dependencias directas de red no importadas | rg no las encontró en módulos de aplicación, pero algunas pueden ser transitivas/dinámicas/launcher. | Ejecutar uv tree, análisis de imports dinámicos y smoke de launcher antes de cambiar pyproject.toml/lock. RC-M-022. |
| Helpers CSRFProtection/SSRFProtection no cableados a rutas | Tienen tests y existen como utilidades; no son basura segura de borrar. | No eliminar: integrar o documentar su relación con require_same_origin/HttpClient, y solo después retirar duplicación. |
| frontend/dist | Ausente y normalmente generado. | No añadirlo ni eliminar nada: corregir el contrato Compose de RC-H-001. |

Antes de cualquier eliminación se debe conservar un commit de referencia, buscar imports dinámicos/entry points, ejecutar tests de contrato y comprobar que no hay consumidores fuera del repositorio.

## 15. Refactorizaciones recomendadas

1. **Configuración:** una única función para construir constantes derivadas (HEADERS, paths, timeouts), un esquema de aliases explícito y un test de precedencia. Retirar gradualmente globals mutables.
2. **Admisión de jobs:** mover capacidad + insert a una operación atómica del repositorio; devolver un resultado de transición que actualice métricas y auditoría una sola vez.
3. **Pipeline de descarga:** introducir staging por job, un contexto de cleanup y un CancellationToken/callback para cada fase. Mantener formatos como enum/validator.
4. **Política HTTP/URL:** centralizar validación de host, resolución DNS, redirecciones, límites streaming y contenido; el plugin no debe tener versiones divergentes de la política.
5. **Errores:** separar mensaje público, código estable, contexto interno y request ID. Redactar excepciones antes de logger/audit.
6. **Auditoría:** hacer recursiva la redacción, limitar profundidad/bytes y restaurar desde checkpoint/tail.
7. **Frontend API:** encapsular credentials, CORS mode y SSE en un cliente consistente; probar same-origin y cross-origin por separado.
8. **Accesibilidad:** consolidar focus trap y labels traducibles sin borrar exports hasta cerrar la migración.

## 16. Mejoras de arquitectura

- Mantener el monolito para el caso local, pero definir explícitamente que la cola singleton/SQLite no soporta múltiples replicas sin un mecanismo de ownership/locking compartido.
- Separar liveness local de dependencia upstream. El proceso debe poder reiniciarse/ser monitorizado aun cuando O'Reilly esté caído.
- Usar un directorio de staging por job_id y publicar outputs solo después de validación; esto simplifica cleanup, cancelación y consistencia.
- Hacer del repositorio la fuente de verdad de estados y métricas derivadas, evitando contadores mutables solo en memoria.
- Convertir el kernel en registro estático documentado ahora; añadir descubrimiento dinámico solo si existe una necesidad real y un contrato de plugin versionado.
- Definir una trust boundary de proxy: quién termina TLS, quién puede establecer forwarded headers, cómo se obtiene IP cliente y qué endpoints son públicos/locales.
- Separar configuración pública de configuración secreta y validar al arranque cualquier variable desconocida o alias ambiguo en entornos de producción.
- Para crecimiento, considerar un worker/proceso separado únicamente cuando métricas reales muestren que el hilo asyncio bloquea el API; primero corregir límites, cancelación y staging.

## 17. Mejoras de documentación

- Corregir el flujo Docker de una orden (RC-H-001) y declarar diferencia entre perfil dev con mounts y perfil runtime autocontenido.
- Reescribir .env.example con nombres anidados efectivos y ejemplos JSON donde proceda (RC-H-004).
- Cambiar hot-pluggable por el comportamiento real o documentar el mecanismo de registro (RC-L-010).
- Retirar epubcheck/ del árbol documentado o añadirlo cuando exista; alinear roadmap y CI.
- Cambiar Full test matrix por una tabla que indique qué suite corre en cada job y cuáles requieren flags (RC-M-023).
- Documentar que la API local no autentica, el alcance del proxy de confianza, los formatos válidos y la semántica de PUBLIC_API_BASE.
- Documentar retención y propiedad de data/, output/, audit logs y artefactos de jobs.
- Añadir una guía de errores con ErrorCode y request ID, sin recomendar mostrar excepciones internas.
- Añadir SECURITY.md y una guía corta de threat model/deployment.
- Definir política de emojis: branding/UI permitidos, logs/errores/contratos solo texto estable.

## 18. Mejoras de pruebas

### Pruebas que deben añadirse

- Configuración: cada variable documentada, precedencia env/.env/defaults, aliases legacy y config.reload() incluyendo extra_headers.
- Queue: concurrencia de enqueue, capacidad exacta, reinicio, doble transición y métricas queued/running/terminal.
- URL/seguridad: IDs malformados en todas las rutas, forwarded headers desde proxy confiable/no confiable, DNS con múltiples IPs, redirect a host prohibido, SVG activo y redacción anidada.
- HTTP: streaming que supera max_response_size, cierre de responses, retries y timeouts.
- Descargas: fallo en portada/capítulo/CSS/imagen/EPUB/PDF, cancelación por fase, staging cleanup y formato inválido.
- Filesystem: cleanup no elimina archivos no registrados, traversal en nombres/refs CSS y reveal fuera de root.
- Health: liveness sin upstream, readiness con SQLite real, DB bloqueada/corrupta y errores no filtrados.
- Session: cookies con mismo nombre/dominio/path, rotación de clave, expiración y datos inválidos.
- Frontend: API en distinto origen, credentials en REST/SSE, etiquetas a11y por locale, foco y asset OG.
- PWA: cache install/fetch, API excluida, offline navigation y ausencia de handlers placeholder si se eliminan.

### Estado observado de tests

La estructura es amplia: hay tests de contratos/DTO/schemas, unitarios de core/plugins, integración de auth/books/downloads, regresiones de rutas, OWASP/security, a11y, e2e y performance. Sin embargo, no se pudo recoger pytest --collect-only ni ejecutar tests por falta de pydantic/pytest instalado, y CI omite suites opt-in. El informe no atribuye a esos tests un resultado que no se haya observado.

## 19. Mejoras de configuración y automatización

- Añadir un job de dependencias limpio que ejecute uv lock --check, uv sync --frozen, uv tree y una auditoría de vulnerabilidades.
- Ejecutar bandit, pip-audit y detect-secrets en CI, con exclusiones justificadas y revisión de falsos positivos.
- Publicar coverage de backend/frontend y usar umbrales por etapas, comenzando por evitar regresiones.
- Crear jobs explícitos para pytest --run-security, --run-e2e, --run-performance y a11y, con servicios y artifacts aislados.
- Añadir matriz Python 3.11/3.12/3.13, al menos nightly si el coste de cada PR es alto.
- Fijar actions y runtime Bun por SHA o política equivalente; añadir timeout-minutes, concurrency para PR y permisos mínimos por job.
- Mantener lockfiles sincronizados y verificar que el package wheel no depende de archivos no incluidos.
- Añadir check de BOM/CRLF, ruff format --check, Prettier y TypeScript (ya definidos) como gates que se puedan ejecutar de forma reproducible.
- Para Compose, separar dev editable de runtime reproducible y usar healthcheck de liveness corregido.
- Validar configuración al arranque: producción debe rechazar combinaciones inseguras, aliases desconocidos críticos y CORS wildcard con credenciales.

## 20. Recomendaciones específicas por archivo/carpeta

| Archivo/carpeta | Recomendación |
| --- | --- |
| config.py | Unificar construcción de estado y reload; corregir extra_headers; probar modelo anidado. RC-H-004, RC-M-009, RC-M-017. |
| .env.example | Reescribir nombres efectivos, especialmente RYLIOX_*__*; no presentar defaults inseguros como producción. RC-H-004. |
| web/server.py | Trust boundary forwarded headers, rate limit de admin session, acotar request ID y revisar buffering. RC-H-002, RC-H-005, RC-M-012. |
| web/dependencies.py | Aplicar una dependencia de book_id en todas las rutas; separar helpers de tests de controles activos. RC-H-003, RC-L-004. |
| web/routes/books.py | No devolver str(exc); usar códigos públicos y request ID. RC-H-003, RC-M-013. |
| web/routes/downloads.py | Cleanup por artefactos propios, deadline SSE y transiciones de métricas. RC-M-002, RC-L-002, RC-M-010. |
| core/repository.py | Exponer operaciones atómicas de capacidad, probes y transiciones con métricas derivadas. RC-M-001, RC-M-011. |
| core/services.py | Encapsular lifecycle queued/running/terminal, cancelación y active gauge. RC-M-001, RC-M-006, RC-M-010. |
| core/http_client.py | Implementar response streaming con límite y mantener cierre/retry correcto. RC-M-018. |
| core/validators.py | Revisar DNS multi-IP y executor timeout; centralizar URL policy. RC-M-007, RC-M-008. |
| core/session_store.py | Mantener registros completos y validar nombre/atributos de cookie. RC-M-019. |
| core/audit.py | Redacción recursiva y restore acotado; añadir tests de cookies. RC-M-014, RC-M-015. |
| core/dto.py | Delegar campos requeridos a Pydantic y reducir aliases cuando expire compatibilidad. RC-M-020. |
| core/logging_config.py | Corregir timestamp y mantener mensajes sin secretos/emojis decorativos. RC-L-001, RC-L-012. |
| plugins/downloader.py | Staging, cleanup final, formatos explícitos, cancelación por fase y eliminar buffer no usado. RC-M-003 a RC-M-006. |
| plugins/assets.py | Usar path retornado, sanitizar/limitar SVG y aplicar política de host. RC-L-003 a RC-L-005. |
| plugins/chapters.py | Codificar URN/query y retirar o aplicar helper de sanitización. RC-H-003, RC-L-004. |
| core/kernel.py/plugins/token.py | Documentar registro estático y decidir contrato de token plugin. RC-L-006, RC-L-015. |
| frontend/src/lib/api.ts | Credentials consistente, SSE cross-origin explícito y cleanup de listeners de AbortSignal. RC-M-016. |
| frontend/src/pages/index.astro | Corregir OG image y CSP/fonts; mantener PWA solo con capacidades soportadas. RC-M-017, RC-L-009. |
| frontend/src/components/LanguageSwitcher.tsx | Traducir labels ARIA y títulos. RC-L-008. |
| frontend/src/lib/*a11y*, KeyboardNavigation.tsx | Consolidar focus utilities después de confirmar API pública. RC-L-014. |
| frontend/public/service-worker.js | Implementar o quitar sync/push placeholders. RC-L-013. |
| README.md/tests/README.md | Alinear arquitectura, Compose, árbol, roadmap y matriz real. RC-H-001, RC-L-010, RC-M-023. |
| .github/workflows/ci.yml | Añadir suites y security jobs, fijar acciones, timeout/concurrency/matriz. RC-M-023. |
| pyproject.toml/uv.lock | Confirmar extra all, depurar directas sin uso y ejecutar auditoría lock en entorno escribible. RC-M-022. |

## 21. Orden de implementación propuesto

1. **Despliegue seguro y reproducible:** resolver RC-H-001, RC-H-002 y RC-H-004; documentar proxy, CORS, cookies y Compose.
2. **Validación de entradas y salida:** resolver RC-H-003, RC-M-013, validación DNS y streaming de HTTP (RC-M-007, RC-M-018).
3. **Integridad de jobs:** resolver admisión atómica, staging/cleanup, formatos y cancelación (RC-M-001 a RC-M-006).
4. **Observabilidad confiable:** corregir health, métricas, auditoría y timestamps (RC-M-009 a RC-M-015, RC-L-001).
5. **Contrato de sesión/frontend:** corregir cookies por dominio, credentials cross-origin, CSP/fonts y labels a11y.
6. **Higiene de dependencias y CI:** validar lock, extra all, eliminar directas solo con evidencia, ejecutar seguridad y suites opt-in.
7. **Limpieza de bajo riesgo:** assets OG, PWA placeholders, documentación, finales de línea y política de emojis.
8. **Revisión de arquitectura posterior a métricas:** decidir si hace falta separar worker/proceso o ampliar el kernel; no hacerlo antes de medir.

Tras cada etapa: añadir test de regresión, ejecutar la validación relevante y revisar que no se han alterado secretos, paths o lockfiles accidentalmente.

## 22. Limitaciones de la revisión

- No se pudo instalar dependencias ni crear .venv, node_modules, cache alternativa o artefactos de build, por la restricción de solo lectura y la autorización de escritura limitada al informe.
- No se ejecutaron pytest, ruff, mypy, TypeScript, Prettier ni tests de navegador. Los comandos frontend intentados fallaron porque sus ejecutables no estaban instalados; no se interpretan como fallos del código.
- uv lock --check no llegó a validar semánticamente el lockfile: uv intentó crear un temporal en una caché del sistema de solo lectura. La exactitud del lock debe comprobarse en CI/entorno limpio.
- No se levantó Docker ni se hizo un build/runtime end-to-end; por eso RC-H-001 y varios efectos de health/CSP/CORS están clasificados como hipótesis operativas, aunque sus precondiciones de configuración sí están confirmadas.
- No se dispuso de cookies, token admin, DNS controlado, proxy inverso, servicio upstream ni entorno de producción. No se validó autenticación real, SSRF en red, redirecciones externas, rendimiento bajo carga ni lectores EPUB concretos.
- El conteo de emojis es una búsqueda estática aproximada y no decide cuáles forman parte intencional del branding.
- La revisión de dependencias no sustituye una base de advisories actualizada ni pip-audit; se requiere ejecutar esa herramienta con red y lock validado.
- No se modificó ningún archivo existente, configuración, código, lockfile ni commit. La única escritura realizada por esta revisión es este informe Markdown.
