"""Authorization and limits on real PostgreSQL, as the runtime role: the actual access path (spec C.5; TEST-02).

Without the TEST_*_DATABASE_URL settings these are SKIPPED with that reason.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from app.domain.roles import Identity, Role
from app.persistence.models import Case, RateLimit
from app.services import cases as svc
from app.services import rate_limit
from tests.arm_a import ArmA
from tests.pg_stack import clear_cases, make_pg_arm, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]
OTHER = "other-co"


@pytest.fixture(scope="module")
def pg(generated: Path) -> Iterator[tuple[ArmA, Engine]]:
    arm, owner = make_pg_arm(generated)
    yield arm, owner
    owner.dispose()


@pytest.fixture
def arm(pg: tuple[ArmA, Engine]) -> ArmA:
    arm_, owner = pg
    clear_cases(owner)
    with owner.begin() as conn:
        conn.execute(text("DELETE FROM rate_limits"))
    return arm_


def _request() -> svc.IntakeRequest:
    return svc.IntakeRequest(received_at_utc="2026-07-01T10:00:00Z", contact_channel="email", text="Points.")


def test_another_customers_case_doesnt_exist_on_the_real_path(arm: ArmA) -> None:
    other = Identity(0, "intake", "Intake", Role.AGENT, OTHER)
    with arm.sessions() as s:
        theirs = svc.create_case(s, other, _request(), customer_id=OTHER, arm="B")
        ours = svc.create_case(s, arm.who("agent.ana"), _request(), arm="B")
        who = arm.who("supervisor.sam")
        assert [c.id for c in svc.list_cases(s, who)] == [ours.id]
        with pytest.raises(svc.CaseNotFound):
            svc.get_case(s, who, theirs.id)


def test_the_runtime_role_still_cant_change_the_audit_log(arm: ArmA) -> None:
    with arm.sessions() as s:
        svc.create_case(s, arm.who("agent.ana"), _request(), arm="B")
    with arm.sessions() as s, pytest.raises(DBAPIError):
        s.execute(text("DELETE FROM case_events"))
        s.commit()


def test_concurrent_requests_cant_slip_past_a_limit(arm: ArmA) -> None:
    """Row locks count every hit, so 20 at once against a limit of 5 let exactly 5 through."""
    allowed: list[int] = []
    denied: list[int] = []
    barrier = threading.Barrier(20)

    def go(n: int) -> None:
        with arm.sessions() as s:
            barrier.wait(timeout=30)
            try:
                rate_limit.hit(s, "race", 5, 3600)
                allowed.append(n)
            except rate_limit.RateLimited:
                denied.append(n)

    threads = [threading.Thread(target=go, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(allowed) == 5 and len(denied) == 15
    with arm.sessions() as s:
        assert s.scalars(select(RateLimit.hits).where(RateLimit.key == "race")).one() == 20


def test_personal_data_removal_works_as_the_runtime_role(arm: ArmA) -> None:
    from app.services import retention

    with arm.sessions() as s:
        who = arm.who("agent.ana")
        case = svc.create_case(s, who, _request(), arm="B")
        svc.add_note(s, who, case, "A note.")
        case_id = case.id
        case.status = "Resolved"
        case.updated_at_utc = "2000-01-01T00:00:00Z"
        s.commit()
        assert retention.apply_retention(s, arm.who("admin.ada"), "hg-demo", days=30).removed == 1
        found = s.get(Case, case_id)
        assert found is not None and found.personal_data_removed_at_utc
