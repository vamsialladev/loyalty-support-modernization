"""The app: health and readiness, the server-rendered console for arms A and B, and the JSON API.

Run: `uvicorn --factory app.main:serve --port 8010` (JSON logs; `create_app` alone leaves logging as it is).
- `/healthz`: the process is up.
- `/readyz`: the app database answers and is at this code's schema revision, and the customer systems answer.
- `/login`, `/queue`, `/cases/...`, `/approvals`, `/metrics`, `/day-one`: the console (`app/web/console.py`).
- `/api/v1/...`: the JSON API, with the same permissions (`app/api/router.py`).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import httpx
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.router import install_api
from app.observability import ops_metrics, tracing
from app.observability.logs import configure_logging
from app.persistence.database import make_engine, make_sessions
from app.services.systems import SystemsFactory, mock_systems_factory
from app.settings import AppSettings
from app.web.console import install_console

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("app.readiness")
_URL_PASSWORD = re.compile(r"(://[^:/\s]+:)[^@\s]+@")
_NAMED_SECRET = re.compile(r"(?i)((?:password|passwd|token|secret)[\"']?\s*[=:]\s*[\"']?)[^\s\"',]+")


def mask_secrets(message: str) -> str:
    return _NAMED_SECRET.sub(r"\1***", _URL_PASSWORD.sub(r"\1***@", message))[:500]


def create_app(
    settings: AppSettings | None = None,
    systems_factory: SystemsFactory | None = None,
    oidc_http: httpx.Client | None = None,
) -> FastAPI:
    settings = settings or AppSettings.from_env()
    provider = tracing.configure_process(tracing.APP)
    engine = make_engine(settings.database_url)
    tracing.instrument_engine(engine)  # one span per statement, never its parameters (ADR-0077)
    schema_head = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    # The default docs pages load scripts the CSP refuses, and list every console route. The API's own contract is
    # published.
    app = FastAPI(
        title="Loyalty Support Modernization (SYNTHETIC)",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        checks: dict[str, str] = {}
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                current = MigrationContext.configure(conn).get_current_revision()
                checks["database"] = "ok" if current == schema_head else "not_migrated"
        except Exception as exc:
            checks["database"] = "unreachable"
            log.warning("readiness: database check failed: %s: %s", type(exc).__name__, mask_secrets(str(exc)))
        try:
            resp = httpx.get(f"{settings.mock_api_url}/readyz", timeout=2.0)
            checks["customer_systems"] = "ok" if resp.status_code == 200 else resp.json().get("status", "not_ready")
        except (httpx.HTTPError, ValueError):
            checks["customer_systems"] = "unreachable"
        ready = all(v == "ok" for v in checks.values())
        return JSONResponse({"status": "ready" if ready else "not_ready", **checks}, status_code=200 if ready else 503)

    app.state.oidc_http = oidc_http
    systems_for = systems_factory or mock_systems_factory(settings)
    install_console(app, settings, make_sessions(engine), systems_for)
    install_api(app, settings, systems_for)
    if settings.feature_ag_ui:  # spec G.2: each protocol behind its own flag; imported only when on
        from protocols.ag_ui.routes import install_ag_ui

        install_ag_ui(app, settings)
    tracing.instrument_fastapi(app, provider)
    return app


def serve() -> FastAPI:
    """The process entry point (`uvicorn --factory app.main:serve`): JSON logs, scrubbed, then the app."""
    configure_logging(tracing.APP)
    ops_metrics.install(tracing.APP, None, {}, os.environ)  # HTTP server metrics, if an OTLP endpoint is set
    return create_app()
