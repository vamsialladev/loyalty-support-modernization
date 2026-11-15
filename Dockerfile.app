# App image: the console, health, readiness, the migrate service's command and the quickstart seed command.
# No labels, generator or data inside (ADR-0040). Non-root user. Milestone 12 (DEL-01, ADR-0074): separate dependency
# and runtime stages, so uv and the build cache stay out of what runs; a `protocols` target for the MCP server and the
# A2A specialist (the core image still has no protocol SDKs); the default target is the core app, last below.
FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM python:3.12.16-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /srv
# Debian's security updates at build time: the base tag lags them, and Trivy blocks fixable HIGH/CRITICAL (ADR-0084).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin svc

# Dependencies only. uv lives in these stages and never reaches a runtime image.
FROM base AS deps
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --group api --no-install-project

FROM deps AS deps-protocols
RUN uv sync --frozen --no-default-groups --group api --group protocols --no-install-project

# Service code, shared by both runtime targets.
FROM base AS code
COPY customer_shapes ./customer_shapes
COPY config/customers ./config/customers
COPY config/legacy ./config/legacy
COPY config/conventional ./config/conventional
COPY config/ai ./config/ai
COPY config/prompts ./config/prompts
COPY config/policy-regression ./config/policy-regression
COPY policies ./policies
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# `docker compose --profile labs`: MCP server or A2A specialist (the command picks which). Healthchecks are in Compose.
FROM code AS protocols
COPY --from=deps-protocols /opt/venv /opt/venv
COPY protocols ./protocols
USER 10001
CMD ["python", "-m", "protocols.mcp.server"]

FROM code AS app
COPY --from=deps /opt/venv /opt/venv
USER 10001
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8010/healthz', timeout=5)"]
CMD ["uvicorn", "--factory", "app.main:serve", "--host", "0.0.0.0", "--port", "8010"]
