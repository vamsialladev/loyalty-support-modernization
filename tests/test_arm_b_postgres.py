"""Arm B on real PostgreSQL, as the runtime role: the group's supervisor limit under real locks (ADR-0062).

Two agents request adjustments in one group at the same moment. Each alone is under the limit; together they aren't.
They must not both pass. Without the TEST_*_DATABASE_URL settings this is SKIPPED with that reason.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.clock import utc_now
from app.persistence.models import AdjustmentRequestRow, Case, Recommendation
from app.services import cases as svc
from app.services import conventional
from tests.arm_a import ArmA
from tests.pg_stack import clear_cases, make_pg_arm, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]
ROUNDS = 8
LIVE = ("pending", "approved", "executing", "execution_unknown", "executed", "execution_conflict")


@pytest.fixture(scope="module")
def pg(generated: Path) -> Iterator[tuple[ArmA, Engine]]:
    arm, owner = make_pg_arm(generated)
    yield arm, owner
    owner.dispose()


@pytest.fixture
def arm(pg: tuple[ArmA, Engine]) -> ArmA:
    arm_, owner = pg
    clear_cases(owner)
    return arm_


def seed(arm: ArmA, group: str, points: tuple[int, ...]) -> list[int]:
    ids = []
    with arm.sessions() as s:
        who = arm.who("agent.ana")
        for n, owed in enumerate(points):
            request = svc.IntakeRequest(received_at_utc="2026-10-01T12:00:00Z", contact_channel="email", text="Points.")
            case = svc.create_case(s, who, request, arm="B", group_ref=group)
            conventional.start_investigation(s, who, case)
            s.add(
                Recommendation(
                    case_id=case.id,
                    author="engine",
                    member_number="GR-85640",
                    stay_id=f"{group}-{n}",
                    status="eligible",
                    action="adjust",
                    points_owed=owed,
                    earned_points=owed,
                    credited_points=0,
                    reasons=[],
                    citations=[],
                    flags=[],
                    evidence_hash="a" * 64,
                    checkout_day="2026-08-01",
                    created_at_utc=utc_now(),
                )
            )
            s.commit()
            ids.append(case.id)
    return ids


def race(arm: ArmA, case_ids: list[int]) -> list[str]:
    barrier = threading.Barrier(len(case_ids))
    results: list[str] = []
    who = arm.who("agent.ana")

    def go(case_id: int) -> None:
        with arm.sessions() as s:
            case = s.get(Case, case_id)
            assert case is not None
            barrier.wait(timeout=30)
            try:
                results.append(conventional.request_adjustment(s, who, case).status)
            except svc.WorkflowError:
                results.append("refused")

    threads = [threading.Thread(target=go, args=(c,)) for c in case_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def test_two_agents_in_one_group_never_both_pass_the_limit(arm: ArmA) -> None:
    for round_ in range(ROUNDS):
        ids = seed(arm, f"B-RACE{round_}", (15000, 15000))
        results = race(arm, ids)
        assert sorted(results) in (["escalated", "requested"], ["escalated", "refused"]), results
        with arm.sessions() as s:
            rows = s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id.in_(ids))).all()
            assert not [r for r in rows if r.status in LIVE], [r.status for r in rows]
            states = [c.status for c in s.scalars(select(Case).where(Case.id.in_(ids)))]
            assert states == ["Escalated", "Escalated"]


def test_a_double_click_makes_one_request(arm: ArmA) -> None:
    for round_ in range(ROUNDS):
        (case_id,) = seed(arm, f"B-DOUBLE{round_}", (5000,))
        results = race(arm, [case_id, case_id])
        assert sorted(results) == ["refused", "requested"], results
        with arm.sessions() as s:
            rows = s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id == case_id)).all()
            assert len(rows) == 1
