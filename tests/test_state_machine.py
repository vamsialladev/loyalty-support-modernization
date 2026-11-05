"""Every pair of case states, allowed or refused, and reopening with its audit trail (spec B.10; WP-01).

The table below is written out by hand on purpose: it states the spec's machine independently of the code's table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.case_states import TERMINAL, CaseState, InvalidTransition, check_transition
from app.domain.roles import NotPermitted
from app.main import create_app
from app.persistence.models import AdjustmentRequestRow, Case
from app.services import cases as svc
from app.services.instrumentation import events, record
from app.settings import AppSettings
from tests.arm_a import ArmA, Browser, field, make_arm_a

S = CaseState
ALLOWED = {
    (S.NEW, S.INVESTIGATING),
    (S.INVESTIGATING, S.AWAITING_INFORMATION),
    (S.INVESTIGATING, S.PENDING_APPROVAL),
    (S.INVESTIGATING, S.ESCALATED),
    (S.INVESTIGATING, S.RESOLVED),
    (S.AWAITING_INFORMATION, S.INVESTIGATING),
    (S.PENDING_APPROVAL, S.APPROVED),
    (S.PENDING_APPROVAL, S.REJECTED),
    (S.PENDING_APPROVAL, S.INVESTIGATING),
    (S.APPROVED, S.EXECUTING),
    (S.APPROVED, S.ESCALATED),
    (S.APPROVED, S.INVESTIGATING),
    (S.EXECUTING, S.RESOLVED),
    (S.EXECUTING, S.EXECUTION_UNKNOWN),
    (S.EXECUTING, S.APPROVED),
    (S.EXECUTING, S.ESCALATED),
    (S.EXECUTION_UNKNOWN, S.RESOLVED),
    (S.EXECUTION_UNKNOWN, S.APPROVED),
    (S.EXECUTION_UNKNOWN, S.ESCALATED),
    (S.RESOLVED, S.INVESTIGATING),
    (S.ESCALATED, S.INVESTIGATING),
    (S.REJECTED, S.INVESTIGATING),
}
EVERY_PAIR = [(a, b) for a in S for b in S]
K01, MEMBER, STAY = "DV-001", "GR-85640", "BR-6638"
REASON = "The stay was inside the claim window after all."


@pytest.mark.parametrize(("current", "target"), EVERY_PAIR, ids=lambda state: state.name)
def test_every_pair_of_states(current: CaseState, target: CaseState) -> None:
    if (current, target) in ALLOWED:
        check_transition(current, target)
    else:
        with pytest.raises(InvalidTransition):
            check_transition(current, target)


def test_a_reopened_case_cannot_jump_ahead_or_skip_the_approval() -> None:
    for state in TERMINAL:
        for target in (S.APPROVED, S.EXECUTING, S.PENDING_APPROVAL, S.NEW):
            with pytest.raises(InvalidTransition):
                check_transition(state, target)


def test_an_uncertain_execution_cannot_be_closed_or_reinvestigated() -> None:
    for target in (S.INVESTIGATING, S.EXECUTING, S.REJECTED, S.PENDING_APPROVAL):
        with pytest.raises(InvalidTransition):
            check_transition(S.EXECUTION_UNKNOWN, target)


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def wrongly_denied(arm: ArmA, s: Session) -> Case:
    """A case like A-000010: closed as `deny_claim_window` with no evidence, as the Milestone 5 tool allowed. The close
    rules (ADR-0054) now refuse this, so the row is written as the old code wrote it."""
    (case,) = arm.load(s, K01)
    who = arm.who("agent.ana")
    svc.start_work(s, who, case)
    svc.move(case, S.RESOLVED)
    case.resolution_code, case.resolution_note = "deny_claim_window", "Too old."
    record(
        s,
        case,
        who,
        "case_closed",
        resolution="deny_claim_window",
        checklist_outcome="incomplete_evidence",
        override=True,
    )
    s.commit()
    return case


def test_a_wrong_denial_reopens_with_its_audit_trail_kept(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = wrongly_denied(arm, s)
        before = [(e.step, e.action, e.detail) for e in events(s, case)]
        svc.reopen(s, arm.who("agent.ben"), case, REASON)
        assert case.status == S.INVESTIGATING and case.assigned_to == "agent.ben"
        assert case.resolution_code is None and case.resolution_note is None
        after = events(s, case)
        assert [(e.step, e.action, e.detail) for e in after[: len(before)]] == before, "history must not change"
        assert after[-1].action == "case_reopened" and after[-1].actor == "agent.ben"
        assert after[-1].detail == {
            "previous_status": "Resolved",
            "previous_resolution": "deny_claim_window",
            "previous_note": "Too old.",
            "reason": REASON,
        }
        assert REASON in svc.notes_of(s, case)[-1].body


def test_the_next_close_of_a_reopened_case_follows_the_close_rules(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = wrongly_denied(arm, s)
        svc.reopen(s, arm.who("agent.ana"), case, REASON)
        with pytest.raises(svc.WorkflowError, match="evidence is incomplete"):
            svc.close_case(s, arm.who("agent.ana"), case, "deny_claim_window", "still too old, I think", arm.rules)
        who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
        svc.attach_member(s, who, case, systems, MEMBER)
        svc.attach_stay(s, who, case, systems, MEMBER, STAY)
        svc.attach_ledger(s, who, case, systems, MEMBER, show_older=True)
        svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
        request = svc.request_adjustment(s, who, case, arm.rules)
        assert case.status == S.PENDING_APPROVAL and request.points == 14_840


@pytest.mark.parametrize("reason", ["", "   ", "too short", " " * 30 + "x"])
def test_reopening_needs_a_reason_of_twenty_characters(arm: ArmA, reason: str) -> None:
    with arm.sessions() as s:
        case = wrongly_denied(arm, s)
        with pytest.raises(svc.WorkflowError, match="20 characters"):
            svc.reopen(s, arm.who("agent.ana"), case, reason)
        assert case.status == S.RESOLVED and case.resolution_code == "deny_claim_window"


@pytest.mark.parametrize("state", [s for s in S if s not in TERMINAL])
def test_only_a_case_at_rest_can_be_reopened(arm: ArmA, state: CaseState) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        case.status = state.value
        s.commit()
        with pytest.raises(svc.WorkflowError, match="only a resolved, escalated or rejected case"):
            svc.reopen(s, arm.who("agent.ana"), case, REASON)


@pytest.mark.parametrize("state", [S.ESCALATED, S.REJECTED])
def test_escalated_and_rejected_cases_can_be_reopened(arm: ArmA, state: CaseState) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        case.status = state.value
        s.commit()
        svc.reopen(s, arm.who("supervisor.sam"), case, REASON)
        assert case.status == S.INVESTIGATING
        assert events(s, case)[-1].detail["previous_status"] == state.value


@pytest.mark.parametrize("status", ["executed", "execution_conflict"])
def test_only_a_supervisor_reopens_a_case_with_a_credit_applied(arm: ArmA, status: str) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        case.status = S.RESOLVED.value
        s.add(
            AdjustmentRequestRow(
                case_id=case.id,
                member_number=MEMBER,
                stay_id=STAY,
                points=1,
                reason_code="missing_points",
                checklist={},
                requested_by="agent.ana",
                requested_at_utc="2026-01-01T00:00:00Z",
                status=status,
            )
        )
        s.commit()
        with pytest.raises(NotPermitted, match="a supervisor"):
            svc.reopen(s, arm.who("agent.ana"), case, REASON)
        assert case.status == S.RESOLVED
        svc.reopen(s, arm.who("supervisor.sam"), case, REASON)
        assert case.status == S.INVESTIGATING


@pytest.mark.parametrize("username", ["auditor.abe", "admin.ada"])
def test_auditors_and_administrators_cannot_reopen(arm: ArmA, username: str) -> None:
    with arm.sessions() as s:
        case = wrongly_denied(arm, s)
        with pytest.raises(NotPermitted):
            svc.reopen(s, arm.who(username), case, REASON)


def test_reopening_in_the_console(arm: ArmA) -> None:
    with arm.sessions() as s:
        case = wrongly_denied(arm, s)
        case_id = case.id
    client = TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory()))
    b = Browser(client)
    b.login("agent.ana", arm.password)
    page = b.get(f"/cases/{case_id}")
    assert f'action="/cases/{case_id}/reopen"' in page.text
    assert b.post(f"/cases/{case_id}/reopen", reason="short").status_code == 409
    done = b.post(f"/cases/{case_id}/reopen", reason=REASON)
    assert field(done.text, "case-status") == "Investigating"
    assert field(done.text, "message") == "Case reopened."
    assert f'action="/cases/{case_id}/reopen"' not in done.text
    assert "case_reopened" in done.text and "case_closed" in done.text

    assert client.post(f"/cases/{case_id}/reopen", data={"reason": REASON, "csrf": "nope"}).status_code == 403


def test_an_auditor_sees_no_reopen_button(arm: ArmA) -> None:
    with arm.sessions() as s:
        case_id = wrongly_denied(arm, s).id
    b = Browser(TestClient(create_app(AppSettings(database_url=arm.app_url, sim_clock=True), arm.factory())))
    b.login("auditor.abe", arm.password)
    assert "/reopen" not in b.get(f"/cases/{case_id}").text
    assert b.post(f"/cases/{case_id}/reopen", reason=REASON).status_code == 403
