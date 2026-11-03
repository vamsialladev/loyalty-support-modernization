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
    command.upgrade(cfg, "0001")  # a volume from an earlier milestone: migrated, but behind this code
    assert client.get("/readyz").json()["database"] == "not_migrated"
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
            401,
            json={"code": "unauthorized", "title": "Missing or invalid bearer token"},
            headers={"content-type": "application/problem+json"},
        )

    monkeypatch.setattr(seed_cli.httpx, "post", refused)
    assert seed_cli.main([]) == 1


def test_seed_on_a_loaded_mock_still_migrates_and_creates_accounts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An existing volume from an earlier milestone: mock data loaded, app database behind, no demo accounts."""
    import app.seed as seed_cli
    from app.adapters.local_demo_identity import LocalDemoIdentity
    from app.persistence.database import make_engine, make_sessions

    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0001")  # the Milestone 4 schema
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("MOCK_API_TOKEN", "fake-token-for-test")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "fake-demo-password-1234")

    def already_loaded(url: str, **kw: Any) -> httpx.Response:
        return httpx.Response(
            409,
            json={"code": "already_seeded", "title": "Data is already loaded; use reset to reload"},
            headers={"content-type": "application/problem+json"},
        )

    monkeypatch.setattr(seed_cli.httpx, "post", already_loaded)
    assert seed_cli.main([]) == 0
    assert seed_cli.main([]) == 0, "running it a second time must also succeed"
    out = capsys.readouterr()
    assert "mock data already loaded, skipped" in out.out and "agent.ana" in out.out and out.err == ""
    assert "fake-demo-password-1234" not in out.out
    identity = LocalDemoIdentity(make_sessions(make_engine(url)))
    assert identity.authenticate("agent.ana", "fake-demo-password-1234") is not None


def test_domain_code_imports_no_web_database_http_or_model_sdk() -> None:
    import ast

    banned = {"fastapi", "starlette", "sqlalchemy", "httpx", "requests", "psycopg", "anthropic", "openai", "alembic"}
    for path in (ROOT / "app/domain").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not (names & banned), f"{path.name} imports {names & banned}"
