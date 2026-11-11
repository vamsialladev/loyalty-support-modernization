"""With every protocol flag off, the app is what it was before Milestone 11 (spec G.2: the core application stays
usable with every lab disabled; RFC-0004's one rule)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.settings import AppSettings
from tests.conftest import ROOT

PROTOCOL_PATHS = ("/mcp", "/ag-ui", "/a2a", "/.well-known/agent-card.json", "/.well-known/oauth-protected-resource")


def test_every_protocol_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("FEATURE_MCP", "FEATURE_A2A", "FEATURE_AG_UI"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    settings = AppSettings.from_env()
    assert not (settings.feature_mcp or settings.feature_a2a or settings.feature_ag_ui)


def test_the_app_serves_no_protocol_route_with_the_flags_off(tmp_path: Path) -> None:
    from app.main import create_app

    app = create_app(AppSettings(database_url=f"sqlite:///{(tmp_path / 'a.db').as_posix()}"))
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not [p for p in paths if p.startswith(PROTOCOL_PATHS)]
    client = TestClient(app)
    for path in PROTOCOL_PATHS:
        assert client.get(path).status_code == 404, path


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:  # module level only: a lazy import behind a flag is allowed
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_core_module_imports_the_protocols_package_at_load_time() -> None:
    """The core never depends on a protocol package being installed; the domain never imports one at all."""
    banned = ("protocols.", "mcp", "a2a", "ag_ui")
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        if any(n == "protocols" or n.startswith(banned) for n in _top_level_imports(path)):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
    for path in (ROOT / "app" / "domain").rglob("*.py"):
        assert "protocols" not in path.read_text(encoding="utf-8").replace("protocol_", ""), path


def test_the_core_image_doesnt_install_the_protocol_packages() -> None:
    dockerfile = (ROOT / "Dockerfile.app").read_text(encoding="utf-8")
    assert "--no-default-groups --group api" in dockerfile
    assert "--group protocols" not in dockerfile
