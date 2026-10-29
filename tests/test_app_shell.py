"""The app placeholder: health, readiness (database migrated, customer systems reachable) and the seed command."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from tests.conftest import ROOT


def app_client(monkeypatch: pytest.MonkeyPatch, url: str, mock_url: str = "http://127.0.0.1:9") -> TestClient:
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("MOCK_API_URL", mock_url)
    from app.main import create_app

    return TestClient(create_app())


def test_healthz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = app_client(monkeypatch, f"sqlite:///{(tmp_path / 'a.db').as_posix()}")
    assert client.get("/healthz").json()["status"] == "ok"


def test_readyz_needs_migrations_and_customer_systems(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    client = app_client(monkeypatch, url)
    first = client.get("/readyz")
    assert first.status_code == 503
    assert first.json()["database"] == "not_migrated" and first.json()["customer_systems"] == "unreachable"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    assert client.get("/readyz").json()["database"] == "ok"


def test_seed_command_migrates_then_calls_the_mock(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import app.seed as seed_cli

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(seed_cli.command, "upgrade", lambda cfg, rev: calls.append({"upgrade": rev}))
    monkeypatch.setenv("MOCK_API_TOKEN", "fake-token-for-test")

    def ok(url: str, **kw: Any) -> httpx.Response:
        calls.append({"url": url, "params": kw["params"]})
        return httpx.Response(200, json={"counts": {"members": 3}})

    monkeypatch.setattr(seed_cli.httpx, "post", ok)
    assert seed_cli.main(["--dataset", "demo", "--reset"]) == 0
    assert calls[0] == {"upgrade": "head"} and calls[1]["params"] == {"dataset": "v1", "reset": "true"}
    out = capsys.readouterr().out
    assert "members" in out and "fake-token-for-test" not in out

    def refused(url: str, **kw: Any) -> httpx.Response:
        return httpx.Response(
            409,
            json={"code": "already_seeded", "title": "Data is already loaded"},
            headers={"content-type": "application/problem+json"},
        )

    monkeypatch.setattr(seed_cli.httpx, "post", refused)
    assert seed_cli.main([]) == 1


def test_domain_code_imports_no_web_database_http_or_model_sdk() -> None:
    import ast

    banned = {"fastapi", "starlette", "sqlalchemy", "httpx", "requests", "psycopg", "anthropic", "openai", "alembic"}
    for path in (ROOT / "app/domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not (names & banned), f"{path.name} imports {names & banned}"
