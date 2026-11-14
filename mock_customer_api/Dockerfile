# Mock customer API image: service code only. No generator, labels or data inside (ADR-0040); the seed folder is
# mounted read-only at run time. Non-root user. Separate dependency and runtime stages since Milestone 12 (ADR-0074).
FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM python:3.15.0-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /srv
# Debian's security updates at build time: the base tag lags them, and Trivy blocks fixable HIGH/CRITICAL (ADR-0084).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin svc

FROM base AS deps
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --group api --no-install-project

FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
COPY customer_shapes ./customer_shapes
COPY config/customers ./config/customers
COPY mock_customer_api ./mock_customer_api
USER 10001
EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8020/healthz', timeout=5)"]
CMD ["sh", "-c", "alembic -c mock_customer_api/alembic.ini upgrade head && exec uvicorn --factory mock_customer_api.api:serve --host 0.0.0.0 --port 8020"]
