"""Policy search and publishing on real PostgreSQL (spec B.6, Part D): full-text search, the index, publish races.

They need TEST_APP_DATABASE_URL (the compose check points it at the throwaway stack's `loyalty_test` database; CI at its
own). Without it they are SKIPPED with that reason; they never silently pass.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.roles import Identity, Role
from app.persistence.database import make_engine, make_sessions
from app.services import policies, policy_publishing
from app.services.customer_config import CustomerConfig
from tests.conftest import ROOT
from tests.test_policies import ADMIN, CUSTOMER, POLICY_DIR, draft_text

URL = os.environ.get("TEST_APP_DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not URL.startswith("postgresql"), reason="TEST_APP_DATABASE_URL is not set to PostgreSQL"),
]
CONFIG = CustomerConfig.load(CUSTOMER)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = make_engine(URL)
    sessions = make_sessions(engine)
    with sessions() as s:
        policies.load_policy_set(s, CUSTOMER, POLICY_DIR)
    yield sessions
    engine.dispose()


def refs(found: list[policies.Citation]) -> list[str]:
    return [str(c.ref) for c in found]


def test_full_text_search_stems_and_ranks_within_the_version_in_force(factory: sessionmaker[Session]) -> None:
    with factory() as s:
        # Stemming: "postings" and "pending" match the section heading "Pending postings".
        assert refs(policies.search(s, CUSTOMER, "pending posting", date(2026, 8, 1)))[0] == (
            "missing-points-requests@v2#5.1"
        )
        assert "missing-points-requests@v2#7.3" in refs(
            policies.search(s, CUSTOMER, "corporate programs", date(2026, 8, 1))
        )
        assert policies.search(s, CUSTOMER, "corporate programs", date(2026, 6, 1)) == []  # v1 has no such section
        assert policies.search(s, CUSTOMER, "points", date(2024, 1, 1)) == []


@pytest.mark.parametrize("query", ["'; DROP TABLE policy_chunks; --", 'unbalanced "quote', "a & | ! ( :*", "%%%"])
def test_search_text_cannot_break_the_query(factory: sessionmaker[Session], query: str) -> None:
    with factory() as s:
        assert policies.search(s, CUSTOMER, query, date(2026, 8, 1)) == []
        assert s.scalar(text("select count(*) from policy_chunks")) > 0


def test_the_search_uses_the_gin_index_expression(factory: sessionmaker[Session]) -> None:
    with factory() as s:
        s.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(
            s.scalars(
                text(
                    "EXPLAIN SELECT id FROM policy_chunks WHERE to_tsvector('english', heading || ' ' || text) "
                    "@@ websearch_to_tsquery('english', 'points')"
                )
            )
        )
    assert "ix_policy_chunks_search" in plan


def test_two_administrators_publishing_one_draft_publish_it_once(factory: sessionmaker[Session]) -> None:
    with factory() as s:
        draft_id = policy_publishing.create_draft(s, ADMIN, draft_text(), CUSTOMER).id
    outcomes: list[str] = []
    start = threading.Barrier(2)

    def attempt(name: str) -> None:
        start.wait()
        with factory() as s:
            who = Identity(1, name, name, Role.ADMINISTRATOR)
            try:
                policy_publishing.publish(s, who, draft_id, CONFIG)
                outcomes.append("published")
            except policy_publishing.PublishRefused:
                outcomes.append("refused")

    threads = [threading.Thread(target=attempt, args=(f"admin-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["published", "refused"]
    with factory() as s:
        assert s.scalar(text("select count(*) from system_events where action = 'policy_published'")) == 1
