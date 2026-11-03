"""Boundaries Milestone 5 must keep (spec B.1, E.1, F9; ADR-0043, ADR-0046, ADR-0048, ADR-0051).

- Arm A's legacy layer is pure apart from the customer-systems port: no web, database, HTTP or model SDK.
- Nothing under `app/` imports `benchmarks/`, so a benchmark-only variant (A as-is, Milestone 10) can never be
  reached from the console, the API or a deployment profile.
- The demo-case loader never opens a label file.
- Alembic revision 0002 creates exactly the tables in `app/persistence/models.py`.
- The vendored htmx file is the one whose hash is recorded.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import ROOT

BANNED = {"fastapi", "starlette", "sqlalchemy", "httpx", "requests", "psycopg", "anthropic", "openai", "alembic"}
HTMX_SHA256 = "d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    return names


def test_legacy_arm_imports_no_web_database_http_or_model_sdk() -> None:
    for path in (ROOT / "app/arms").rglob("*.py"):
        top = {name.split(".")[0] for name in imports(path)}
        assert not (top & BANNED), f"{path.name} imports {top & BANNED}"


def test_nothing_in_the_app_imports_the_benchmark_tooling() -> None:
    for path in (ROOT / "app").rglob("*.py"):
        assert not [n for n in imports(path) if n.split(".")[0] in {"benchmarks", "evaluations"}], path


def test_the_demo_loader_reads_requests_and_never_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    from benchmarks.intake import read_split

    opened: list[str] = []
    real_read_text = Path.read_text

    def watching(self: Path, *args: Any, **kwargs: Any) -> str:
        opened.append(self.as_posix())
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", watching)
    monkeypatch.setattr(builtins, "open", lambda *a, **k: pytest.fail(f"unexpected open {a[0]!r}"))
    cases = read_split("dev")
    assert opened == [(ROOT / "benchmarks/datasets/v1/dev.jsonl").as_posix()]
    assert len(cases) == 100
    request = cases[0].requests[0]
    assert not hasattr(request, "language") and not hasattr(request, "scenarios")


def test_migration_0002_matches_the_table_definitions(tmp_path: Path) -> None:
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    from app.persistence.models import Base

    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    with create_engine(url).connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(cfg, "0001")


def test_vendored_htmx_matches_its_recorded_hash() -> None:
    path = ROOT / "app/web/static/vendor/htmx-2.0.11.min.js"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == HTMX_SHA256
    readme = (ROOT / "app/web/static/vendor/README.md").read_text(encoding="utf-8")
    assert HTMX_SHA256 in readme and "2.0.11" in readme


def test_templates_have_no_inline_script_or_style() -> None:
    for path in (ROOT / "app/web/templates").glob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "<script>" not in text and "style=" not in text and " on" + "click=" not in text, path.name
        assert "<script" not in text or 'src="/static/' in text, path.name
