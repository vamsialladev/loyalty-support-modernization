"""The app: health and readiness, plus the server-rendered console for arm A (Milestone 5).

Run: `uvicorn --factory app.main:create_app --port 8010`.
- `/healthz`: the process is up.
- `/readyz`: the app database answers and is at this code's schema revision, and the customer systems answer.
- `/login`, `/queue`, `/cases/...`, `/approvals`: the Jinja2 + HTMX console (`app/web/console.py`).
"""

from __future__ import annotations

from pathlib import Path

import httpx
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.persistence.database import make_engine, make_sessions
from app.settings import AppSettings
from app.web.console import SystemsFactory, install_console, mock_systems_factory

ROOT = Path(__file__).resolve().parent.parent


def create_app(settings: AppSettings | None = None, systems_factory: SystemsFactory | None = None) -> FastAPI:
    settings = settings or AppSettings.from_env()
    engine = make_engine(settings.database_url)
    schema_head = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    app = FastAPI(title="Loyalty Support Modernization (SYNTHETIC)", version=__version__)

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
        except Exception:
            checks["database"] = "unreachable"
        try:
            resp = httpx.get(f"{settings.mock_api_url}/readyz", timeout=2.0)
            checks["customer_systems"] = "ok" if resp.status_code == 200 else resp.json().get("status", "not_ready")
        except (httpx.HTTPError, ValueError):
            checks["customer_systems"] = "unreachable"
        ready = all(v == "ok" for v in checks.values())
        return JSONResponse({"status": "ready" if ready else "not_ready", **checks}, status_code=200 if ready else 503)

    install_console(app, settings, make_sessions(engine), systems_factory or mock_systems_factory(settings))
    return app
