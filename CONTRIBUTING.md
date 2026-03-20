# Contributing to Ryliox

Gracias por tu interes en contribuir.

---

## Levantar el entorno local

```bash
git clone https://github.com/ZnOw01/Ryliox.git
cd Ryliox
cp .env.example .env
python -m launcher
```

El launcher instala dependencias y compila el frontend automaticamente en el primer arranque.
El servidor queda disponible en **http://localhost:8000**.

Si prefieres Docker:

```bash
python -m launcher --docker
```

---

## Flujo de trabajo

1. Crea una rama desde `main` siguiendo la convencion:

   | Tipo | Prefijo | Ejemplo |
   |---|---|---|
   | Nueva funcionalidad | `feature/` | `feature/batch-download` |
   | Correccion de bug | `fix/` | `fix/cookie-expiry-detection` |
   | Documentacion | `docs/` | `docs/api-examples` |
   | Refactor interno | `refactor/` | `refactor/queue-manager` |

2. Haz commits pequenos y enfocados. Formato recomendado:

   ```
   tipo: descripcion corta en infinitivo

   Contexto opcional si el cambio no es obvio.
   ```

   Tipos validos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

   Ejemplos:
   ```
   feat: agregar soporte para descarga por lote
   fix: detectar expiracion de cookies en mid-download
   docs: agregar ejemplos de respuesta en referencia API
   ```

3. Ejecuta los checks locales antes de abrir PR (ver seccion abajo).
4. Abre el PR contra `main` con una descripcion clara.

---

## Checks locales

Ejecuta esto antes de cualquier PR:

```bash
# Backend — tests y cobertura basica
pytest -q

# Frontend — type checking y tests
cd frontend && bun run check && bun run test
```

> El proyecto usa **Bun**, no npm. Usa siempre `bun run` dentro de `frontend/`.

Si tu cambio toca generacion de PDF, verifica que las dependencias del sistema esten instaladas:

```bash
# Ubuntu / Debian
sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
```

---

## Guia por tipo de cambio

### Cambios en la API (backend)

- Incluye ejemplos de request/response actualizados en el PR.
- Si el endpoint es nuevo o modifica el contrato existente, actualiza la seccion de referencia en `README.md`.
- Verifica que `GET /api/openapi.json` refleje el cambio correctamente.

### Cambios en el frontend

- Incluye una captura o GIF corto que muestre el antes/despues.
- Prueba en al menos un navegador basado en Chromium y uno en Firefox.

### Cambios en el sistema de cola o persistencia

- Verifica que la cola sobreviva un reinicio del servidor (SQLite persistente).
- Prueba el escenario de cola con multiples jobs simultaneos si es relevante.

### Solo documentacion

- Verifica que los bloques de codigo y comandos funcionen tal como estan escritos.
- Si tocas ejemplos de respuesta de la API, confirma que coincidan con el comportamiento real.

---

## Reportar bugs

Antes de abrir un issue, revisa el [Troubleshooting del README](./README.md#troubleshooting).

Si el problema persiste, abre un issue incluyendo:

- Version de Ryliox (tag o commit).
- OS y version de Python/Bun.
- Pasos exactos para reproducir.
- Output relevante de logs (`LOG_LEVEL=DEBUG` en `.env` para mas detalle).
- Lo que esperabas vs lo que ocurrio.

---

## Lo que preferimos evitar en PRs

- Mezclar un refactor grande con un bugfix no relacionado — abre PRs separados.
- Cambios de estilo o formato en archivos que no tienen relacion con el fix/feature.
- Agregar dependencias nuevas sin justificacion en la descripcion del PR.
- PRs sin descripcion o con solo el titulo automatico de GitHub.
