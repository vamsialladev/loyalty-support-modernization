# App image: the arm A console, health, readiness, migrations and the quickstart seed command.
# No labels, generator or data inside (ADR-0040). Non-root user.
FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM python:3.12.10-slim-bookworm
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/opt/venv/bin:$PATH
WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --group api --no-install-project

COPY customer_shapes ./customer_shapes
COPY config/customers ./config/customers
COPY config/legacy ./config/legacy
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin svc
USER 10001
EXPOSE 8010
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8010"]
