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
WP = SharedWritePath(settle_seconds=0)  # the settle window has its own tests in test_execution.py


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
    WP.decide(s, arm.who(approver), request.id, arm.systems(case.received_at_utc), approve=True, reason="")
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
        WP.decide(s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc), approve=True, reason="")
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
            WP.decide(
                s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc), approve=True, reason=""
            )
        WP.decide(s, arm.who("supervisor.sky"), request.id, arm.systems(case.received_at_utc), approve=True, reason="")
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
                WP.decide(s, arm.who(agent), request.id, arm.systems(case.received_at_utc), approve=True, reason="")
        WP.decide(s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc), approve=True, reason="")
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
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, lost).status == "unknown"  # one lookup isn't enough
        assert case.status == CaseState.EXECUTION_UNKNOWN
        assert WP.check_status(s, arm.who("supervisor.sam"), request_id, lost).status == "not_applied"
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
            WP.decide(
                s, arm.who("supervisor.sam"), request.id, arm.systems(case.received_at_utc), approve=False, reason=" "
            )
        WP.decide(
            s,
            arm.who("supervisor.sam"),
            request.id,
            arm.systems(case.received_at_utc),
            approve=False,
            reason="Folio shows a different rate.",
        )
        assert case.status == CaseState.REJECTED and case.resolution_code == "rejected"
        with pytest.raises(svc.WorkflowError, match="already been decided"):
            WP.decide(
                s, arm.who("supervisor.sky"), request.id, arm.systems(case.received_at_utc), approve=True, reason=""
            )
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


RULE_BASED_CODES = [
    "no_adjustment_credited",
    "wait_until",
    "not_checked_out",
    "deny_channel_ineligible",
    "deny_claim_window",
]


@pytest.mark.parametrize("code", RULE_BASED_CODES)
def test_a_rule_based_close_is_refused_while_evidence_is_incomplete_whatever_the_note(arm: ArmA, code: str) -> None:
    """The A-000010 path (TD-17, ADR-0054): a rule-based denial with nothing attached and a note to get it through."""
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        with pytest.raises(svc.WorkflowError, match="evidence is incomplete"):
            svc.close_case(
                s, arm.who("agent.ana"), case, code, "A long and confident note, with no evidence.", arm.rules
            )
        assert case.status == CaseState.INVESTIGATING and case.resolution_code is None
        assert "case_closed" not in [e.action for e in events(s, case)]


def test_a_rule_based_close_is_refused_with_part_of_the_evidence(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        who = arm.who("agent.ana")
        svc.start_work(s, who, case)
        svc.attach_member(s, who, case, arm.systems(case.received_at_utc), MEMBER)
        with pytest.raises(svc.WorkflowError, match="evidence is incomplete"):
            svc.close_case(s, who, case, "deny_claim_window", "Member found, the rest not checked.", arm.rules)


def test_a_rule_based_close_that_agrees_with_complete_evidence_needs_no_note(arm: ArmA) -> None:
    """Not every close got harder: the fix only refuses a close with nothing behind it."""
    with arm.sessions() as s:
        (case,) = arm.load(s, arm.scenario("K05"))
        who = arm.who("agent.ana")
        svc.start_work(s, who, case)
        systems = arm.systems(case.received_at_utc)
        facts = arm.labels[case.source_ref]
        member, stay = facts["claimant_member_number"], facts["facts"]["claimed_stay_ids"][0]
        svc.attach_member(s, who, case, systems, member)
        svc.attach_stay(s, who, case, systems, member, stay)
        svc.attach_ledger(s, who, case, systems, member, show_older=True)
        svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
        assert svc.checklist_for(s, case, arm.rules).outcome is Outcome.NOT_CHECKED_OUT
        svc.close_case(s, who, case, "not_checked_out", "", arm.rules)
        closed = events(s, case)[-1]
        assert closed.detail["override"] is False and closed.detail["checklist_outcome"] == "not_checked_out"


def test_a_rule_based_close_against_complete_evidence_stays_an_override(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case)
        with pytest.raises(svc.WorkflowError, match="override"):
            svc.close_case(s, arm.who("agent.ana"), case, "deny_claim_window", "", arm.rules)
        svc.close_case(s, arm.who("agent.ana"), case, "deny_claim_window", "Supervisor said to deny.", arm.rules)
        closed = events(s, case)[-1]
        assert closed.detail["override"] is True and closed.detail["checklist_outcome"] == "adjust"


def test_deny_not_found_needs_a_logged_search(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        who = arm.who("agent.ana")
        svc.start_work(s, who, case)
        with pytest.raises(svc.WorkflowError, match="search the member screen first"):
            svc.close_case(s, who, case, "deny_not_found", "Could not find this member.", arm.rules)
        assert case.status == CaseState.INVESTIGATING


def test_deny_not_found_is_allowed_after_a_member_search_that_found_nothing(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        who = arm.who("agent.ana")
        svc.start_work(s, who, case)
        svc.log_search(s, case, who, "member", "member number", 0)
        svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        closed = events(s, case)[-1]
        assert case.resolution_code == "deny_not_found" and closed.detail["override"] is False


def test_deny_not_found_is_refused_when_the_latest_search_found_the_record(arm: ArmA) -> None:
    """A typo followed by the right number: the first empty search doesn't count any more."""
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        who = arm.who("agent.ana")
        svc.start_work(s, who, case)
        svc.log_search(s, case, who, "member", "member number", 0)
        svc.log_search(s, case, who, "member", "member number", 1)
        with pytest.raises(svc.WorkflowError, match="search the member screen first"):
            svc.close_case(s, who, case, "deny_not_found", "", arm.rules)


def test_deny_not_found_looks_at_the_screen_of_the_missing_record(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        who = arm.who("agent.ana")
        systems = arm.systems(case.received_at_utc)
        svc.start_work(s, who, case)
        svc.log_search(s, case, who, "member", "member number", 0)  # a typo, before the right number
        svc.attach_member(s, who, case, systems, MEMBER)
        with pytest.raises(svc.WorkflowError, match="search the stay screen first"):
            svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        svc.log_search(s, case, who, "stay", "confirmation number", 0)
        svc.close_case(s, who, case, "deny_not_found", "", arm.rules)
        assert case.resolution_code == "deny_not_found"


def test_deny_not_found_is_refused_when_member_and_stay_are_attached(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        investigate(arm, s, case)
        svc.log_search(s, case, arm.who("agent.ana"), "stay", "confirmation number", 0)
        with pytest.raises(svc.WorkflowError, match="both attached"):
            svc.close_case(s, arm.who("agent.ana"), case, "deny_not_found", "Was not there at first.", arm.rules)


@pytest.mark.parametrize("note", ["", "too short", " " * 30, "x" * 19 + "   "])
def test_deny_other_refuses_a_note_under_20_characters(arm: ArmA, note: str) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        with pytest.raises(svc.WorkflowError, match="at least 20 characters"):
            svc.close_case(s, arm.who("agent.ana"), case, "deny_other", note, arm.rules)
        assert case.status == CaseState.INVESTIGATING


def test_deny_other_with_20_characters_is_a_logged_override_even_without_evidence(arm: ArmA) -> None:
    with arm.sessions() as s:
        (case,) = arm.load(s, K01)
        svc.start_work(s, arm.who("agent.ana"), case)
        svc.close_case(s, arm.who("agent.ana"), case, "deny_other", "x" * 20, arm.rules)
        closed = events(s, case)[-1]
        assert case.resolution_code == "deny_other"
        assert closed.detail["override"] is True and closed.detail["checklist_outcome"] == "incomplete_evidence"


def test_the_console_only_offers_the_codes_the_evidence_allows() -> None:
    assert svc.close_codes_for(Outcome.INCOMPLETE) == ["deny_not_found", "deny_other"]
    assert svc.close_codes_for(Outcome.ADJUST) == list(svc.CLOSE_CODES)
    assert set(RULE_BASED_CODES) | set(svc.EVIDENCE_FREE_CODES) == set(svc.CLOSE_CODES)  # no new code slips past


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


def test_every_state_is_reachable_and_terminal_states_only_reopen() -> None:
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
        check_transition(CaseState.RESOLVED, CaseState.APPROVED)
