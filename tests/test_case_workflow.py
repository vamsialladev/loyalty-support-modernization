"""Arm A's case workflow and the thin shared write path, on a seeded mock customer API (spec B.8, B.10; ADR-0044).

Separation of duties, the cross-case duplicate check (D10, platform), uncertain outcomes reconciled by key before
any retry, and the state machine. Each test gets its own copy of the mock database and a fresh app database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.arms.legacy.checklist import Outcome
from app.domain.case_states import TERMINAL, TRANSITIONS, CaseState, InvalidTransition, check_transition
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult
from app.domain.roles import NotPermitted
from app.persistence.models import Case
from app.ports.customer_systems import CustomerSystems, TemporarilyUnavailable, UncertainOutcome
from app.services import cases as svc
from app.services.instrumentation import events
from app.services.write_path import SharedWritePath, attempts_of
from tests.arm_a import ArmA, make_arm_a

K01 = "DV-001"  # Clara Kowalski, GR-85640, BR-6638, 14,840 points
MEMBER, STAY = "GR-85640", "BR-6638"
WP = SharedWritePath()


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def investigate(arm: ArmA, s: Session, case: Case, agent: str = "agent.ana") -> None:
    who = arm.who(agent)
    systems = arm.systems(case.received_at_utc)
    svc.start_work(s, who, case)
    svc.attach_member(s, who, case, systems, MEMBER)
    svc.attach_stay(s, who, case, systems, MEMBER, STAY)
    svc.attach_ledger(s, who, case, systems, MEMBER, show_older=True)
    svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")


def to_approved(arm: ArmA, s: Session, case: Case, agent: str = "agent.ana", approver: str = "supervisor.sam") -> int:
    investigate(arm, s, case, agent)
    request = svc.request_adjustment(s, arm.who(agent), case, arm.rules)
    WP.decide(s, arm.who(approver), request.id, approve=True, reason="")
    return request.id


def adjustments_on_ledger(arm: ArmA) -> list[Any]:
    return [e for e in arm.systems().get_ledger(MEMBER) if e.kind == "adjustment" and e.stay_id == STAY]


def test_k01_completes_end_to_end_through_the_services(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        assert case.queue == "points" and case.status == CaseState.NEW
        investigate(arm, s, case)
        checklist = svc.checklist_for(s, case, arm.rules)
        assert checklist.outcome is Outcome.ADJUST and checklist.points_owed == 14_840
        request = svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)
        assert case.status == CaseState.PENDING_APPROVAL and request.points == 14_840
        WP.decide(s, arm.who("supervisor.sam"), request.id, approve=True, reason="")
        result = WP.execute(s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc))
        assert result.status == "applied"
        assert case.status == CaseState.RESOLVED and case.resolution_code == "adjusted"
        actions = [e.action for e in events(s, case)]
        assert actions[0] == "case_created" and actions[-1] == "adjustment_executed"
        assert [e.step for e in events(s, case)] == list(range(1, len(actions) + 1))
    (credit,) = adjustments_on_ledger(arm)
    assert credit.points == 14_840


def test_the_requester_cannot_approve_their_own_adjustment(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case, agent="supervisor.sam")
        request = svc.request_adjustment(s, arm.who("supervisor.sam"), case, arm.rules)
        with pytest.raises(NotPermitted, match="another supervisor"):
            WP.decide(s, arm.who("supervisor.sam"), request.id, approve=True, reason="")
        WP.decide(s, arm.who("supervisor.sky"), request.id, approve=True, reason="")
        with pytest.raises(NotPermitted):
            WP.execute(s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc))
        assert (
            WP.execute(s, arm.who("supervisor.sky"), request.id, arm.systems(case.received_at_utc)).status == "applied"
        )


def test_an_agent_can_neither_approve_nor_execute(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case)
        request = svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)
        for agent in ("agent.ana", "agent.ben"):
            with pytest.raises(NotPermitted, match="only a supervisor"):
                WP.decide(s, arm.who(agent), request.id, approve=True, reason="")
        WP.decide(s, arm.who("supervisor.sam"), request.id, approve=True, reason="")
        with pytest.raises(NotPermitted):
            WP.execute(s, arm.who("agent.ben"), request.id, arm.systems(case.received_at_utc))
        assert case.status == CaseState.APPROVED


def test_d10_a_second_case_for_the_same_stay_is_refused_at_execution(arm: ArmA) -> None:
    """Two contacts, two cases (the legacy intake doesn't link them); both approved; only one credit."""
    with arm.sessions() as s:
        (first,) = arm.load(s, K01)
        req = svc.requests_of(s, first)[0]
        phoned = svc.IntakeRequest(req.received_at_utc, "phone_note", req.text, req.sender_email)
        second = svc.create_case(s, arm.who("agent.ben"), phoned)
        first_id = to_approved(arm, s, first)
        second_id = to_approved(arm, s, second, agent="agent.ben", approver="supervisor.sky")
        assert (
            WP.execute(s, arm.who("supervisor.sam"), first_id, arm.systems(first.received_at_utc)).status == "applied"
        )
        refused = WP.execute(s, arm.who("supervisor.sky"), second_id, arm.systems(second.received_at_utc))
        assert refused.status == "refused_duplicate" and first.reference in refused.message
        assert second.status == CaseState.ESCALATED and second.resolution_code == "duplicate_prevented"
    assert len(adjustments_on_ledger(arm)) == 1


def test_an_adjustment_already_on_the_ledger_blocks_execution(arm: ArmA) -> None:
    """Another tool credited the stay with its own key: the platform accepts any new key, so the app must refuse."""
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        request_id = to_approved(arm, s, case)
        arm.systems(case.received_at_utc).submit_adjustment(
            AdjustmentRequest(MEMBER, STAY, 14_840, "missing_points", "someone-else"), "other-tool-key-1"
        )
        result = WP.execute(s, arm.who("supervisor.sam"), request_id, arm.systems(case.received_at_utc))
        assert result.status == "refused_duplicate" and "ledger already shows" in result.message
    assert len(adjustments_on_ledger(arm)) == 1


def test_commit_then_lost_is_reconciled_by_key_without_a_second_credit(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        request_id = to_approved(arm, s, case)
        lossy = arm.systems(case.received_at_utc, fault="commit_then_lost")
        result = WP.execute(s, arm.who("supervisor.sam"), request_id, lossy)
        assert result.status == "applied" and "Reconciled" in result.message
        assert case.status == CaseState.RESOLVED
        row = svc.adjustment_requests_of(s, case)[0]
        attempts = attempts_of(s, row)
        assert [a.outcome for a in attempts] == ["unknown", "applied"]
        assert len({a.idempotency_key for a in attempts}) == 1
        actions = [e.action for e in events(s, case)]
        assert actions.index("execution_unknown") < actions.index("reconciled_applied")
    assert len(adjustments_on_ledger(arm)) == 1


class Flaky:
    """A customer-systems wrapper that fails chosen calls once, then behaves normally."""

    def __init__(self, inner: CustomerSystems, *, lose_submit: bool = False, fail_lookup: bool = False) -> None:
        self.inner, self.lose_submit, self.fail_lookup = inner, lose_submit, fail_lookup
        self.submits = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
        self.submits += 1
        if self.lose_submit:
            raise UncertainOutcome("timed out before sending", code="timeout")  # nothing reached the platform
        return self.inner.submit_adjustment(request, key)

    def find_adjustment(self, key: str) -> AdjustmentResult | None:
        if self.fail_lookup:
            self.fail_lookup = False
            raise TemporarilyUnavailable("lookup down", code="unavailable")
        return self.inner.find_adjustment(key)


def test_an_unknown_outcome_stays_unknown_until_a_status_check_succeeds(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        request_id = to_approved(arm, s, case)
        flaky = Flaky(arm.systems(case.received_at_utc, fault="commit_then_lost"), fail_lookup=True)
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, flaky).status == "unknown"
        assert case.status == CaseState.EXECUTION_UNKNOWN
        # Execute again reconciles first; it never resubmits blindly.
        again = Flaky(arm.systems(case.received_at_utc))
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, again).status == "applied"
        assert again.submits == 0 and case.status == CaseState.RESOLVED
    assert len(adjustments_on_ledger(arm)) == 1


def test_reconciled_as_not_applied_returns_to_approved_and_reuses_the_key(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        request_id = to_approved(arm, s, case)
        lost = Flaky(arm.systems(case.received_at_utc), lose_submit=True)
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, lost).status == "not_applied"
        assert case.status == CaseState.APPROVED
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, arm.systems(case.received_at_utc)).status == (
            "applied"
        )
        keys = {a.idempotency_key for a in attempts_of(s, svc.adjustment_requests_of(s, case)[0])}
        assert len(keys) == 1
        with pytest.raises(svc.WorkflowError, match="only an approved"):
            WP.execute(s, arm.who("supervisor.sam"), request_id, arm.systems(case.received_at_utc))
    assert len(adjustments_on_ledger(arm)) == 1


def test_rejection_needs_a_reason_and_ends_the_case(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case)
        request = svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)
        with pytest.raises(svc.WorkflowError, match="reason"):
            WP.decide(s, arm.who("supervisor.sam"), request.id, approve=False, reason=" ")
        WP.decide(s, arm.who("supervisor.sam"), request.id, approve=False, reason="Folio shows a different rate.")
        assert case.status == CaseState.REJECTED and case.resolution_code == "rejected"
        with pytest.raises(svc.WorkflowError, match="already been decided"):
            WP.decide(s, arm.who("supervisor.sky"), request.id, approve=True, reason="")
    assert adjustments_on_ledger(arm) == []


def test_the_agent_cannot_request_what_the_checklist_does_not_support(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        with pytest.raises(svc.WorkflowError, match="incomplete_evidence"):
            svc.request_adjustment(s, arm.who("agent.ana"), case, arm.rules)


def test_closing_against_the_checklist_is_an_override_that_needs_a_note(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case)
        with pytest.raises(svc.WorkflowError, match="override"):
            svc.close_case(s, arm.who("agent.ana"), case, "deny_other", "", arm.rules)
        svc.close_case(s, arm.who("agent.ana"), case, "deny_other", "Member asked to withdraw the claim.", arm.rules)
        closed = events(s, case)[-1]
        assert closed.action == "case_closed" and closed.detail["override"] is True
        assert closed.detail["checklist_outcome"] == "adjust"


def test_request_information_sends_a_ticket_and_waits_for_the_member(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        ticket = svc.request_information(
            s, arm.who("agent.ana"), case, arm.systems(case.received_at_utc), "Please send the confirmation number."
        )
        assert ticket.startswith("TCK-") and case.status == CaseState.AWAITING_INFORMATION
        with pytest.raises(svc.WorkflowError):
            svc.attach_member(s, arm.who("agent.ana"), case, arm.systems(case.received_at_utc), MEMBER)
        svc.resume(s, arm.who("agent.ana"), case)
        assert case.status == CaseState.INVESTIGATING


def test_escalation_needs_a_reason(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        with pytest.raises(svc.WorkflowError):
            svc.escalate(s, arm.who("agent.ana"), case, "")
        svc.escalate(s, arm.who("agent.ana"), case, "Two PMS records disagree.")
        assert case.status == CaseState.ESCALATED


def test_d20_a_refund_mention_lands_in_billing_and_cannot_be_worked_here(arm: ArmA) -> None:
    # D20 has a refund variant and a noise-complaint variant; only the word "refund" triggers the legacy rule.
    refund = sorted(
        cid
        for cid, lab in arm.labels.items()
        if lab["split"] == "dev" and lab["scenarios"] == ["D20"] and "refund_request" in lab["out_of_scope_items"]
    )[0]
    with arm.sessions() as s:
        (case,) = arm.load(s, refund)
        assert case.queue == "billing"
        with pytest.raises(svc.WorkflowError, match="billing queue"):
            svc.start_work(s, arm.who("agent.ana"), case)
        assert case not in svc.list_cases(s, arm.who("agent.ana"))


def test_d10_dataset_pairs_become_two_cases(arm: ArmA) -> None:
    with arm.sessions() as s:
        cases = arm.load(s, arm.scenario("D10"))
        assert len(cases) == 2 and len({c.source_ref for c in cases}) == 1
        assert arm.load(s, arm.scenario("D10")) == []  # loading again skips requests already loaded


def test_attach_rereads_the_record_on_the_server(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        with pytest.raises(svc.WorkflowError, match="no member"):
            svc.attach_member(s, arm.who("agent.ana"), case, arm.systems(case.received_at_utc), "GR-00000")
        with pytest.raises(svc.WorkflowError, match="no stay"):
            svc.attach_stay(s, arm.who("agent.ana"), case, arm.systems(case.received_at_utc), MEMBER, "BR-0000")
        with pytest.raises(svc.WorkflowError, match="not in the index"):
            svc.attach_policy(s, arm.who("agent.ana"), case, arm.index, "made-up#1")


def test_every_state_is_reachable_and_terminal_states_are_final() -> None:
    reachable, frontier = {CaseState.NEW}, [CaseState.NEW]
    while frontier:
        for target in TRANSITIONS[frontier.pop()]:
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    assert reachable == set(CaseState)
    assert {CaseState.RESOLVED, CaseState.ESCALATED, CaseState.REJECTED} == TERMINAL
    with pytest.raises(InvalidTransition):
        check_transition(CaseState.NEW, CaseState.APPROVED)
    with pytest.raises(InvalidTransition):
        check_transition(CaseState.RESOLVED, CaseState.INVESTIGATING)
