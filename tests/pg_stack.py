"""Real-PostgreSQL test helpers: the app database (migrated as the owner, used as the runtime role), a seeded mock API.

The same `ArmA` shape the SQLite tests use, so a test reads the same on both. Needs TEST_APP_DATABASE_URL,
TEST_APP_OWNER_DATABASE_URL and TEST_MOCK_API_DATABASE_URL; `needs_postgres` skips with that reason if they are absent.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.local_demo_identity import ensure_demo_users
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.rules import LegacyRules
from app.persistence.database import make_engine, make_sessions
from app.services.policies import load_policy_set
from mock_customer_api import db as mock_db
from mock_customer_api.api import create_app as create_mock_app
from mock_customer_api.seed import seed as seed_mock
from mock_customer_api.settings import Settings as MockSettings
from tests.arm_a import ArmA
from tests.conftest import ARM_A_TOKEN, ROOT, read_jsonl

APP_URL = os.environ.get("TEST_APP_DATABASE_URL", "")
OWNER_URL = os.environ.get("TEST_APP_OWNER_DATABASE_URL", "")
MOCK_URL = os.environ.get("TEST_MOCK_API_DATABASE_URL", "")
needs_postgres = pytest.mark.skipif(
    not all(url.startswith("postgresql") for url in (APP_URL, OWNER_URL, MOCK_URL)),
    reason="TEST_APP_DATABASE_URL, TEST_APP_OWNER_DATABASE_URL and TEST_MOCK_API_DATABASE_URL must point at PostgreSQL",
)
# Everything a case writes. The owner clears them between tests; the runtime role can't.
CASE_TABLES = (
    "case_events",
    "system_events",
    "execution_attempts",
    "approvals",
    "adjustment_requests",
    "case_notes",
    "case_evidence",
    "case_requests",
    "cases",
)


def migrate_app_database() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", OWNER_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def make_pg_arm(generated: Path) -> tuple[ArmA, Engine]:
    """Migrate and seed both databases. Returns the arm and the owner's engine, for clearing rows between tests."""
    migrate_app_database()
    sessions: sessionmaker[Session] = make_sessions(make_engine(APP_URL))
    password = secrets.token_urlsafe(16)
    with sessions() as s:
        ensure_demo_users(s, password)
        load_policy_set(s, "hg-demo", ROOT / "policies/hg-demo")

    cfg = Config(str(ROOT / "mock_customer_api/alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", MOCK_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    mock_engine = mock_db.make_engine(MOCK_URL)
    seed_mock(mock_db.make_sessions(mock_engine), generated / "seed_data/v1")
    settings = MockSettings(
        database_url=MOCK_URL,
        token=ARM_A_TOKEN,
        faults_enabled=True,
        sim_clock_enabled=True,
        timeout_fault_seconds=0.01,
    )
    client = TestClient(create_mock_app(settings, mock_engine), base_url="http://mock")
    labels: dict[str, Any] = {
        row["case_id"]: row for row in read_jsonl(generated / "benchmarks/datasets/v1/labels/dev.jsonl")
    }
    arm = ArmA(
        sessions,
        client,
        APP_URL,
        password,
        labels,
        generated / "benchmarks/datasets/v1",
        LegacyRules.load("hg-demo"),
        KeywordIndex.load(),
    )
    return arm, make_engine(OWNER_URL)


def clear_cases(owner: Engine) -> None:
    with owner.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(CASE_TABLES)} RESTART IDENTITY CASCADE"))
