"""A2A task state on real PostgreSQL, as the app's runtime role (migration 0011; spec G.4; ADR-0058).

SQLite and Postgres have behaved differently before (Milestone 9), so the one-open-task rule is checked where it
would run: a partial unique index the database enforces, not just a query the code makes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.persistence.models import A2aTask, Case
from app.services import conventional
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath
from app.worker import Worker
from protocols.a2a.coordinator import CoordinatorConfig, request_evidence
from protocols.a2a.specialist import SCOPE, SpecialistConfig, build_app
from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier
from tests.arm_a import ArmA
from tests.pg_stack import clear_cases, make_pg_arm, needs_postgres
from tests.protocol_tokens import ISSUER, TestIssuer

pytestmark = [pytest.mark.postgres, needs_postgres]
K01 = "DV-001"
SPECIALIST = "http://127.0.0.1:8041"


@pytest.fixture(scope="module")
def pg(generated: Path) -> Iterator[tuple[ArmA, Engine]]:
    arm, owner = make_pg_arm(generated)
    yield arm, owner
    owner.dispose()


@pytest.fixture
def arm(pg: tuple[ArmA, Engine]) -> ArmA:
    clear_cases(pg[1])
    return pg[0]


def investigated(arm: ArmA) -> int:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        conventional.start_investigation(s, arm.who("agent.ana"), case)
        cid = case.id
    Worker(arm.sessions, build_handlers(SharedWritePath("hg-demo"), arm.factory(), None)).drain()
    return cid


def task(case_id: int, state: str = "submitted") -> A2aTask:
    return A2aTask(
        case_id=case_id,
        requested_by="svc-a2a-coordinator",
        peer=SPECIALIST,
        state=state,
        created_at_utc="2026-11-11T00:00:00Z",
    )


def test_the_database_allows_only_one_open_task_per_case(arm: ArmA) -> None:
    cid = investigated(arm)
    with arm.sessions() as s:
        s.add(task(cid))
        s.commit()
    with arm.sessions() as s:
        s.add(task(cid))
        with pytest.raises(IntegrityError):
            s.commit()
    with arm.sessions() as s:  # finished tasks don't count
        s.add(task(cid, "completed"))
        s.add(task(cid, "timed_out"))
        s.commit()


def test_the_runtime_role_can_move_a_task_to_its_final_state(arm: ArmA) -> None:
    cid = investigated(arm)
    with arm.sessions() as s:
        row = task(cid)
        s.add(row)
        s.commit()
        row.state = "completed"
        s.commit()
        assert s.get(A2aTask, row.id).state == "completed"  # type: ignore[union-attr]


def test_the_coordinator_path_works_on_postgres(arm: ArmA) -> None:
    cid = investigated(arm)
    with arm.sessions() as s:
        before = s.get(Case, cid).status  # type: ignore[union-attr]
    idp = TestIssuer()
    verifier = TokenVerifier(
        ResourceServer("a2a-specialist", ISSUER, SPECIALIST, frozenset({SCOPE})), StaticKeys(idp.jwks())
    )
    app = build_app(SpecialistConfig(SPECIALIST, ISSUER, "hg-demo"), verifier, lambda: arm.systems())
    tok = idp.token(audience=SPECIALIST, scope=SCOPE)
    config = CoordinatorConfig(SPECIALIST, "hg-demo")
    result = asyncio.run(request_evidence(arm.sessions, cid, config, lambda: tok, httpx.ASGITransport(app=app)))
    assert result["state"] == "completed"
    with arm.sessions() as s:
        assert s.get(Case, cid).status == before  # type: ignore[union-attr]  # evidence for review, no state change
