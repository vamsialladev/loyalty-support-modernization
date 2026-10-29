"""App placeholder (Milestone 4): health and readiness only. Business endpoints arrive in Milestones 5-7.

Run: `uvicorn --factory app.main:create_app --port 8010`.
- `/healthz`: the process is up.
- `/readyz`: the app database answers and is migrated, and the customer systems answer (mock API `/readyz`).
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, inspect, text

from app import __version__


def create_app() -> FastAPI:
    database_url = os.environ["DATABASE_URL"]
    mock_url = os.environ.get("MOCK_API_URL", "http://localhost:8020")
    engine = create_engine(database_url, pool_pre_ping=True)
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
                checks["database"] = "ok" if inspect(conn).has_table("alembic_version") else "not_migrated"
        except Exception:
            checks["database"] = "unreachable"
        try:
            resp = httpx.get(f"{mock_url}/readyz", timeout=2.0)
            checks["customer_systems"] = "ok" if resp.status_code == 200 else resp.json().get("status", "not_ready")
        except (httpx.HTTPError, ValueError):
            checks["customer_systems"] = "unreachable"
        ready = all(v == "ok" for v in checks.values())
        return JSONResponse({"status": "ready" if ready else "not_ready", **checks}, status_code=200 if ready else 503)

    return app
