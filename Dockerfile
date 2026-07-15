# =============================================================================
# Ryliox - Production Dockerfile
# =============================================================================
# Multi-stage build: frontend + Python dependencies + minimal runtime.
# =============================================================================

ARG PYTHON_VERSION=3.11

# -----------------------------------------------------------------------------
# Stage 1: Frontend builder
# -----------------------------------------------------------------------------
FROM oven/bun:1.3.11 AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build

# -----------------------------------------------------------------------------
# Stage 2: Builder — install Python dependencies in an isolated venv
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV VIRTUAL_ENV=/opt/venv \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libcairo2-dev \
        libpango1.0-dev \
        libgdk-pixbuf2.0-dev \
        libffi-dev \
        pkg-config \
        shared-mime-info \
        curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

# -----------------------------------------------------------------------------
# Stage 3: Runtime — minimal image with non-root user
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_USER=appuser
ARG APP_UID=1001
ARG APP_GID=1001

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONFAULTHANDLER=1 \
    APP_HOME=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/app/data \
    OUTPUT_DIR=/app/output \
    SECURITY={"environment":"production"}

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libharfbuzz0b \
        libgdk-pixbuf2.0-0 \
        libcairo2 \
        libffi8 \
        shared-mime-info \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_GID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --home-dir ${APP_HOME} --shell /sbin/nologin ${APP_USER}

WORKDIR ${APP_HOME}

RUN mkdir -p ${DATA_DIR}/logs ${OUTPUT_DIR} \
    && chown -R ${APP_USER}:${APP_USER} ${APP_HOME}

# Copy the venv and the application code from the builder
COPY --from=builder --chown=${APP_USER}:${APP_USER} /opt/venv /opt/venv
COPY --from=builder --chown=${APP_USER}:${APP_USER} /app /app
COPY --from=frontend-builder --chown=${APP_USER}:${APP_USER} /app/frontend/dist /app/frontend/dist

USER ${APP_USER}

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/api/health || exit 1

STOPSIGNAL SIGTERM

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "web.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
