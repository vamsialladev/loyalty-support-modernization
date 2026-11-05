"""The write path on real PostgreSQL, as the app's runtime role (spec D, Appendix C).

Approval invalidation here; idempotency, concurrent execute, duplicates, timeout-after-commit reconciliation and lease
recovery join it with the worker. Without the TEST_*_DATABASE_URL settings these are SKIPPED with that reason.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.domain.case_states import CaseState
from app.domain.roles import Identity, Role
from app.persistence.models import AdjustmentRequestRow, Case
from app.services import approvals, policy_publishing
from app.services import cases as svc
from app.services.customer_config import CustomerConfig
from app.services.instrumentation import events
from app.services.policies import load_policy_set
from app.services.write_path import SharedWritePath, approval_of
from tests.arm_a import ArmA
from tests.conftest import ROOT
from tests.pg_stack import clear_cases, make_pg_arm, needs_postgres
from tests.test_approval_binding import Changed
from tests.test_policies import draft_text

pytestmark = [pytest.mark.postgres, needs_postgres]
K01, MEMBER, STAY = "DV-001", "GR-85640", "BR-6638"  # checkout 2025-11-29: policy v1
LATER_K01, LATER_MEMBER, LATER_STAY = "DV-094", "GR-80622", "BR-4403"  # checkout 2026-07-11: policy v2
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)
CONFIG = CustomerConfig.load("hg-demo")
WP = SharedWritePath()


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
        conn.execute(text("TRUNCATE policy_chunks, policy_versions RESTART IDENTITY CASCADE"))
    with arm_.sessions() as s:
        load_policy_set(s, "hg-demo", ROOT / "policies/hg-demo")
    return arm_


def requested(
    arm: ArmA, s: Session, case_id: str = K01, member: str = MEMBER, stay: str = STAY
) -> tuple[Case, AdjustmentRequestRow]:
    (case,) = arm.load(s, case_id)
    who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
    svc.start_work(s, who, case)
    svc.attach_member(s, who, case, systems, member)
    svc.attach_stay(s, who, case, systems, member, stay)
    svc.attach_ledger(s, who, case, systems, member, show_older=True)
    svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
    return case, svc.request_adjustment(s, who, case, arm.rules)


def approve(arm: ArmA, s: Session, case: Case, row: AdjustmentRequestRow) -> None:
    systems = arm.systems(case.received_at_utc)
    assert WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="").status == "approved"


def retroactive_draft(s: Session) -> int:
    return policy_publishing.create_draft(s, ADMIN, draft_text(effective_from="2026-07-05", wait=14), "hg-demo").id


def test_a_published_policy_invalidates_affected_approvals_in_the_same_transaction(arm: ArmA) -> None:
    with arm.sessions() as s:
        _pending_case, pending = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        old_case, old = requested(arm, s)
        approve(arm, s, old_case, old)
        pending_id, old_id = pending.id, old.id
        draft_id = retroactive_draft(s)
        policy_publishing.publish(s, ADMIN, draft_id, CONFIG)
    with arm.sessions() as s:
        reread = s.get(AdjustmentRequestRow, pending_id)
        kept = s.get(AdjustmentRequestRow, old_id)
        assert reread is not None and kept is not None
        assert (reread.status, reread.invalidated_reason) == ("invalidated", "policy_changed")
        assert kept.status == "approved"
        assert s.scalar(text("select detail from system_events where action = 'policy_published'"))[
            "invalidated_requests"
        ] == [pending_id]


def test_a_publish_that_fails_part_way_changes_nothing(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    with arm.sessions() as s:
        _case, row = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        row_id = row.id
        draft_id = retroactive_draft(s)

    real = approvals.invalidate_for_policy_change

    def fails_after_invalidating(*args: object) -> list[int]:
        real(*args)  # type: ignore[arg-type]
        raise RuntimeError("the process died here")

    monkeypatch.setattr(approvals, "invalidate_for_policy_change", fails_after_invalidating)
    with arm.sessions() as s, pytest.raises(RuntimeError):
        policy_publishing.publish(s, ADMIN, draft_id, CONFIG)
    with arm.sessions() as s:
        reread = s.get(AdjustmentRequestRow, row_id)
        assert reread is not None and reread.status == "pending"
        assert s.scalar(text("select status from policy_versions where version = 3")) == "draft"
        assert (
            s.scalar(
                text("select status from policy_versions where policy_id = 'missing-points-requests' and version = 2")
            )
            == "published"
        )


def test_two_requests_racing_a_publish_end_consistent(arm: ArmA) -> None:
    """Publishing and approving at once: the request ends either approved under the old policy and then invalidated, or
    invalidated first. Never approved under a policy that no longer applies."""
    with arm.sessions() as s:
        case, row = requested(arm, s, LATER_K01, LATER_MEMBER, LATER_STAY)
        row_id, case_id, received = row.id, case.id, case.received_at_utc
        draft_id = retroactive_draft(s)
    start = threading.Barrier(2)
    problems: list[BaseException] = []

    def publish() -> None:
        start.wait()
        with arm.sessions() as s:
            try:
                policy_publishing.publish(s, ADMIN, draft_id, CONFIG)
            except BaseException as exc:
                problems.append(exc)

    def decide() -> None:
        start.wait()
        with arm.sessions() as s:
            try:
                WP.decide(s, arm.who("supervisor.sam"), row_id, arm.systems(received), approve=True, reason="")
            except svc.WorkflowError:
                pass  # the publish got there first and the case was no longer pending
            except BaseException as exc:
                problems.append(exc)

    threads = [threading.Thread(target=publish), threading.Thread(target=decide)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert problems == []
    with arm.sessions() as s:
        final = s.get(AdjustmentRequestRow, row_id)
        final_case = s.get(Case, case_id)
        assert final is not None and final_case is not None
        assert final.status == "invalidated" and final_case.status == CaseState.INVESTIGATING
        assert "approval_invalidated" in [e.action for e in events(s, final_case)]


def test_changed_evidence_invalidates_at_approval_and_execution(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = requested(arm, s)
        changed = Changed(arm.systems(case.received_at_utc), stay={"taxes_cents": 999})
        assert WP.decide(s, arm.who("supervisor.sam"), row.id, changed, approve=True, reason="").status == "invalidated"
        assert approval_of(s, row) is None and case.status == CaseState.INVESTIGATING

        again = svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)
        approve(arm, s, case, again)
        changed = Changed(arm.systems(case.received_at_utc), stay={"taxes_cents": 999})
        assert WP.execute(s, arm.who("supervisor.sam"), again.id, changed).status == "invalidated"
        assert changed.submits == 0 and again.invalidated_reason == "evidence_changed"
