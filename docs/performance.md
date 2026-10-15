# Rendimiento

## Baseline y resultado medido

Baseline en `97b55389cd646cd2014c0ae9f338826cb7bee2c7`, antes de la corrección. Se trabajó sobre `fast-Ryliox`; sin commit ni push.

Entorno observado: Python 3.11.15 en `.venv`, Bun 1.4.3, Node 26.11.1. La interfaz se compiló con las dependencias ya instaladas. No se vaciaron cachés del sistema.

### Arranque local

Comando: `.venv/bin/python main.py --host 127.0.0.1 --port <puerto-loopback-libre>`. Un proceso nuevo por muestra; disponibilidad medida al responder `GET /api/health` con HTTP 200. SQLite de sesión, cola y auditoría, secretos efímeros y salida apuntaron a directorios temporales de supervisión, sin leer las bases existentes ni usar cookies reales. Un warmup, siete muestras, mismo directorio aislado; caché de archivos del SO no controlada.

| Medida | Resultado |
| --- | ---: |
| Warmup (fuera de la muestra) | 449.4 ms |
| Arranque, mediana (n=7) | 370.6 ms |
| p95 por rango más cercano (n=7) | 370.7 ms |
| Mínimo–máximo | 369.7–370.7 ms |

Muestras: 370.7, 370.1, 369.7, 370.6, 370.6, 370.3, 370.6 ms. El proceso de aplicación es nuevo en cada repetición; esto no representa un arranque con caché de SO fría.

### Estado de comprobaciones antes de cambios

- `.venv/bin/python -m pytest`: 462 passed, 110 skipped, 9.01 s; sin fallos. Los skips corresponden a suites opt-in de accesibilidad/E2E, rendimiento lento y seguridad.
- `ruff check .`, `ruff format --check .` y `mypy`: pasan (105 archivos formateados; 45 archivos tipados).
- `bun run typecheck`, `bun run test`, `bun run format:check` y `bun run build`: pasan; 20 pruebas frontend.
- Las pruebas se ejecutaron con rutas de datos efímeras. No se abrió ni modificó `data/*.sqlite3`.

### Interfaz y API: baseline controlado

Benchmark Playwright repetible: `./.venv/bin/python /home/snowflake/.hermes/cache/scratch/ryl-omp-1jjwuzdz/ui_perf_bench.py before --output /home/snowflake/.hermes/cache/scratch/ryl-omp-1jjwuzdz/baseline-97b5538/ui-perf-playwright-before.json`. App real en build de producción, Chromium 154.0.8037.97, Playwright 1.60.0, viewport 390×844. Contexto temporal sin perfil ni service worker; sólo loopback permitido. Las respuestas de búsqueda/capítulos son fixtures deterministas (10 libros y 300 capítulos); no se llamó a O'Reilly. Dos warmups por búsqueda/expansión y 15 muestras; cinco scrolls.

| Ruta observada | Mediana | p95 / máximo | Muestras y datos |
| --- | ---: | ---: | --- |
| Primer paint / FCP | 100 ms | — | TTFB 7.6 ms; HTML 45.9 KB, scripts 644.6 KB, CSS 90.2 KB |
| Navegación móvil al panel Descarga | 655.8 ms | — | De `scrollY=0` a `1047`; desplazamiento suave completo |
| Texto de búsqueda → resultados visibles | 370.5 ms | 377.6 ms | n=15, 10 resultados, sin caché de consulta |
| Consulta repetida en caché → resultados | 365.9 ms | 374.0 ms | n=6; cero fetches nuevos por acierto de caché |
| Expandir 3 → 300 capítulos antiguos | 38.3 ms | 47.6 ms | n=15; el último capítulo apareció; cero long tasks |
| Scroll suave de la lista de 300 capítulos | — | p95 de frame mediano 16.7 ms; máximo 16.8 ms | n=5; se alcanzó el capítulo 300 |

LCP no disponible en esta navegación. La lista volvió a tres filas en cada colapso y preservó `Legacy chapter 0300` al expandir. Resultado de scroll válido sólo para Chromium/headless en esta máquina; no equivale a una medición de GPU o teléfono real.

El microbenchmark de ruta local con dependencias sintéticas registró búsqueda fría de 10 filas (1,293 B): mediana 1.823 ms, p95 2.537 ms, n=7; búsqueda caliente n=30: mediana 1.128 ms, p95 1.659 ms. Capítulos sintéticos de 300 filas (20,316 B): carga fría 2.769 ms; caliente n=30, mediana 1.521 ms, p95 1.897 ms. Estos datos no miden el servicio externo.

### Causa y prioridad

Confirmado: la búsqueda usa `SEARCH_DEBOUNCE_MS = 350`. El flujo completo tarda ~370 ms aun al reutilizar una consulta fresca en caché, sin petición de red nueva; las rutas sintéticas tardan ~1–3 ms. La espera del debounce, no SQLite/serialización ni el render de la lista, domina esa interacción. Corrección: usar de inmediato sólo una respuesta estructuralmente válida, exitosa, no invalidada y menor de 30 s para la consulta exacta. Consultas vacías, nuevas, expiradas, invalidadas o con error conservan los 350 ms y su semántica de refetch. No se cambia el stale time, contrato ni autenticación.

### Corrección: resultados frescos en caché

Se repitió el mismo comando/workload antes y después: `./.venv/bin/python /home/snowflake/.hermes/cache/scratch/ryl-omp-1jjwuzdz/ui_perf_bench.py {before|after} --output <JSON>`. App de producción, contexto Chromium aislado, mismo fixture 10/300, viewport 390×844, dos warmups y n=15 para búsqueda/expansión, n=6 para acierto de caché y n=5 scrolls.

| Interacción | Antes | Después | Resultado |
| --- | ---: | ---: | --- |
| Búsqueda fresca → resultados, mediana (p95; n=15) | 370.5 (377.6) ms | 372.8 (379.8) ms | +2.3 (+2.2) ms; sin mejora material; se conserva el debounce |
| Caché fresca → resultados, mediana (p95; n=6) | 365.9 (374.0) ms | 9.2 (11.3) ms | −356.7 ms / −97.49 % en mediana; −362.7 ms en p95 |
| Fetches añadidos por acierto de caché | 0/6 | 0/6 | Sin peticiones nuevas |
| Expandir 3 → 300 capítulos, mediana (p95; n=15) | 38.3 (47.6) ms | 39.0 (48.2) ms | Sin mejora; sin long tasks en ambas pasadas |
| Scroll de capítulos, p95 frame mediano / máximo (n=5) | 16.7 / 16.8 ms | 16.7 / 16.8 ms | Sin frames >20 ms; capítulo 300 visible |

La navegación móvil suave siguió en ~655 ms (655.8 → 655.3 ms). FCP fue 100 → 108 ms en una pasada por versión; LCP no estuvo disponible, así que no se atribuye efecto de arranque ni carga inicial. El bundle JS subió 705 B (644,595 → 645,300 B); CSS no cambió. Las 15 búsquedas no cacheadas mantuvieron la espera y el fetch esperado. No se aumenta la tasa de peticiones; los aciertos usan únicamente el dato exitoso, fresco y no invalidado del mismo query key.

Repetición tras el build final con el mismo script, viewport 390×844, dos warmups, n=15 búsquedas/expansiones, n=6 aciertos de caché y n=5 scrolls: búsqueda mediana/p95 367.4/376.3 ms; caché 8.05/11.8 ms con cero fetches; expansión 37.9/44.0 ms y cero long tasks; scroll p95 frame mediano/máximo 16.8/16.8 ms, con capítulo 300 visible. FCP 108 ms, LCP no disponible; JS/CSS 645,300/90,228 B. Navegación móvil 652.3 ms, `scrollY` 0 → 1073. El harness sólo permitió loopback y no observó hosts externos.
El servidor se inició con `with_server.py` desde `.../scratch/ryl-omp-1jjwuzdz/final-97b5538` para evitar cargar `.env`; HOME/XDG, datos, salida, auditoría, secretos y temporales se aislaron en esa carpeta. El helper detuvo el servidor al terminar.

Prueba focalizada: `bun run test -- src/components/__tests__/SearchBooksCard.cache.test.tsx`: 7/7 pasan. Comprueba acierto inmediato, URL `?q=python` inmediata y ningún fetch extra al pasar de un acierto asentado a una consulta nueva antes de 350 ms; también cubre búsquedas no cacheadas, invalidadas, expiradas, con error y query vacío.

Validación final: en `frontend/`, `bun run test` pasó 27/27; `bun run lint` y `bun run build` pasaron. En backend, `.venv/bin/python -m pytest` pasó 462 pruebas y omitió 110 suites opt-in; `ruff check .`, `ruff format --check .` y `mypy` pasaron. El test de accesibilidad anterior se migró de mocks de hooks a `QueryClientProvider` real con caché sintética; ambos órdenes entre sus dos archivos y la prueba de caché pasaron 9/9 bajo `vmThreads`.

Los benchmarks no justifican cambiar animaciones o virtualizar capítulos. La expansión p95 fue 47.6 → 48.2 ms con cero long tasks; el scroll conservó frames de 16.7–16.8 ms. El arranque del proceso sólo tiene baseline (370.6 ms); no se volvió a medir porque la corrección no toca el backend y no se afirma mejora de arranque.

Playwright informó React minificado error #418 (mismatch de texto durante hidratación) antes y después; el benchmark no recoge componente ni stack. El bypass no añadió errores de página, pero esa carga/hidratación preexistente queda sin atribución ni corrección.

### Evidencia cruda

`/home/snowflake/.hermes/cache/scratch/ryl-omp-1jjwuzdz/`: `baseline-97b5538/ui-perf-playwright-before.json`, `after-97b5538/ui-perf-playwright-after.json`, `after-97b5538/ui-perf-comparison.json`, `final-97b5538/ui-perf-playwright-final.json`, capturas `ui-home-{before,after}.png` y `ui-chapters-expanded-{before,after}.png`, además de la captura final en `final-97b5538/ui-chapters-expanded-after.png`, `api-baseline.json`, `startup-baseline.json` y logs de procesos/comprobaciones. El script y fixture sintético están en ese directorio. Las comprobaciones iniciales descritas arriba son anteriores a cambios de producto.
