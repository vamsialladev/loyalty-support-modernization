"""Helpers for the arm A tests: a fresh mock customer API and app database per test, and a signed-in browser client.

Test code may read labels (it is the evaluator); the app and the scripted agent never do.
"""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.local_demo_identity import ensure_demo_users
from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.domain.roles import Identity, Role
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import Case, User
from app.ports.customer_systems import CustomerSystems
from benchmarks.intake import load_case, read_split
from customer_shapes import CustomerShape
from mock_customer_api import db as mock_db
from mock_customer_api.api import create_app as create_mock_app
from mock_customer_api.settings import Settings as MockSettings
from tests.conftest import ARM_A_TOKEN, ROOT

SHAPE = CustomerShape.load("hg-demo")


@dataclass
class ArmA:
    sessions: sessionmaker[Session]
    mock_client: TestClient
    app_url: str
    password: str
    labels: dict[str, Any]
    datasets: Path
    rules: LegacyRules
    index: KeywordIndex

    def systems(self, sim_time: str | None = None, fault: str | None = None) -> CustomerSystems:
        return MockCustomerApiAdapter(
            "http://mock",
            ARM_A_TOKEN,
            SHAPE,
            client=self.mock_client,
            sim_time=sim_time,
            fault=fault,
            sleep=lambda _: None,
        )

    def factory(self) -> Callable[[str | None], CustomerSystems]:
        return lambda sim_time: self.systems(sim_time)

    def who(self, username: str) -> Identity:
        with self.sessions() as s:
            user = s.scalars(select(User).where(User.username == username)).one()
            return Identity(user.id, user.username, user.display_name, Role(user.role))

    def load(self, s: Session, case_id: str, split: str = "dev") -> list[Case]:
        item = next(c for c in read_split(split, self.datasets) if c.case_id == case_id)
        return load_case(s, item)

    def scenario(self, code: str, split: str = "dev", nth: int = 0) -> str:
        ids = sorted(cid for cid, lab in self.labels.items() if lab["split"] == split and lab["scenarios"] == [code])
        return ids[nth]


def make_arm_a(template: dict[str, Any], tmp_path: Path) -> ArmA:
    mock_path = tmp_path / "mock.db"
    shutil.copyfile(template["path"], mock_path)
    mock_url = f"sqlite:///{mock_path.as_posix()}"
    mock_settings = MockSettings(
        database_url=mock_url,
        token=ARM_A_TOKEN,
        faults_enabled=True,
        sim_clock_enabled=True,
        timeout_fault_seconds=0.01,
    )
    mock_client = TestClient(create_mock_app(mock_settings, mock_db.make_engine(mock_url)), base_url="http://mock")

    app_url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", app_url)
    command.upgrade(cfg, "head")
    sessions = make_sessions(make_engine(app_url))
    password = secrets.token_urlsafe(16)
    with sessions() as s:
        ensure_demo_users(s, password)
    return ArmA(
        sessions,
        mock_client,
        app_url,
        password,
        template["labels"],
        template["datasets"],
        LegacyRules.load("hg-demo"),
        KeywordIndex.load(),
    )


class Browser:
    """A TestClient that signs in through the real login form and keeps the CSRF token from the last page."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.csrf = ""

    def login(self, username: str, password: str) -> None:
        self.client.cookies.clear()
        page = self.client.get("/login")
        token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
        assert token
        resp = self.client.post(
            "/login", data={"username": username, "password": password, "login_csrf": token.group(1)}
        )
        assert resp.status_code == 200 and "Points queue" in resp.text, resp.text[:300]
        self.csrf = self._csrf(resp.text)

    @staticmethod
    def _csrf(html: str) -> str:
        match = re.search(r'name="csrf" value="([^"]+)"', html)
        return match.group(1) if match else ""

    def get(self, url: str, **params: Any) -> Any:
        resp = self.client.get(url, params=params)
        self.csrf = self._csrf(resp.text) or self.csrf
        return resp

    def post(self, url: str, **data: Any) -> Any:
        return self.client.post(url, data={"csrf": self.csrf, **data})


def field(html: str, testid: str) -> str:
    match = re.search(rf'data-testid="{testid}">([^<]+)<', html)
    return match.group(1).strip() if match else ""
