"""A disposable world for one benchmark run: a seeded mock customer API and an empty app database (RFC-0003).

Every run starts from the same seeded copy, so no run can see another's credits. The app talks to the mock API over its
normal HTTP interface, in one process. Only the evaluator may read the mock API's database directly, to see the final
ledger after every scheduled posting has landed (the settlement horizon, `docs/hypotheses.md` section 1).
"""

from __future__ import annotations

import secrets
import shutil
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.persistence.database import make_engine, make_sessions
from app.ports.customer_systems import CustomerSystems
from app.services.policies import load_policy_set
from customer_shapes import CustomerShape
from mock_customer_api import db as mock_db
from mock_customer_api.api import create_app as create_mock_app
from mock_customer_api.seed import seed
from mock_customer_api.settings import Settings as MockSettings

ROOT = Path(__file__).resolve().parent.parent
CUSTOMER = "hg-demo"
SystemsFactory = Callable[[str | None], CustomerSystems]


def seed_template(seed_dir: Path, folder: Path) -> Path:
    """Migrate and seed the mock API's database once. Each run gets its own copy."""
    path = folder / "mock-template.db"
    url = f"sqlite:///{path.as_posix()}"
    config = Config(str(ROOT / "mock_customer_api/alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = mock_db.make_engine(url)
    seed(mock_db.make_sessions(engine), seed_dir)
    engine.dispose()
    return path


@dataclass
class World:
    sessions: sessionmaker[Session]
    app_engine: Engine
    mock_engine: Engine
    mock_client: TestClient
    token: str
    secret_key: str  # a throwaway per world: approvals are bound as usual, and nothing outlives the run

    def systems(self, sim_time: str | None = None, fault: str | None = None) -> CustomerSystems:
        return MockCustomerApiAdapter(
            "http://mock",
            self.token,
            CustomerShape.load(CUSTOMER),
            client=self.mock_client,  # type: ignore[arg-type]
            sim_time=sim_time,
            fault=fault,
            sleep=lambda _: None,
        )

    def final_points(self, stays: set[str]) -> dict[str, int]:
        """The ledger per stay at the settlement horizon: every entry, across every profile, with no date limit."""
        with mock_db.make_sessions(self.mock_engine)() as s:
            query = (
                select(mock_db.LedgerEntry.stay_id, func.sum(mock_db.LedgerEntry.points))
                .where(mock_db.LedgerEntry.stay_id.in_(stays))
                .group_by(mock_db.LedgerEntry.stay_id)
            )
            return {str(stay): int(points or 0) for stay, points in s.execute(query)}

    def points_by(self, stay: str, moment: str) -> int:
        """What the member could see for a stay at a moment, whichever profile it's on."""
        with mock_db.make_sessions(self.mock_engine)() as s:
            query = select(func.sum(mock_db.LedgerEntry.points)).where(
                mock_db.LedgerEntry.stay_id == stay, mock_db.LedgerEntry.posted_at_utc <= moment
            )
            return int(s.scalar(query) or 0)

    def adjustments_per_stay(self, stays: set[str]) -> Counter[str]:
        with mock_db.make_sessions(self.mock_engine)() as s:
            rows = s.scalars(select(mock_db.Adjustment.stay_id).where(mock_db.Adjustment.stay_id.in_(stays)))
            return Counter(str(stay) for stay in rows)

    def close(self) -> None:
        self.mock_client.close()
        self.app_engine.dispose()
        self.mock_engine.dispose()


def drop_the_duplicate_index(engine: Engine) -> None:
    """A as-is only, on a disposable database: the legacy path has no one-live-credit-per-stay rule."""
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX uq_adjustment_requests_live_stay"))


def make_world(template: Path, folder: Path) -> World:
    folder.mkdir(parents=True, exist_ok=True)
    mock_path = folder / "mock.db"
    shutil.copyfile(template, mock_path)
    mock_url = f"sqlite:///{mock_path.as_posix()}"
    token = secrets.token_urlsafe(24)
    settings = MockSettings(
        database_url=mock_url, token=token, faults_enabled=True, sim_clock_enabled=True, timeout_fault_seconds=0.01
    )
    mock_engine = mock_db.make_engine(mock_url)
    client = TestClient(create_mock_app(settings, mock_engine), base_url="http://mock")

    app_url = f"sqlite:///{(folder / 'app.db').as_posix()}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", app_url)
    command.upgrade(config, "head")
    engine = make_engine(app_url)
    sessions = make_sessions(engine)
    with sessions() as s:
        load_policy_set(s, CUSTOMER, ROOT / "policies" / CUSTOMER)
    return World(sessions, engine, mock_engine, client, token, secrets.token_urlsafe(32))
