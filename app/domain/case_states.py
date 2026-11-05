"""Case states and the transitions the server allows (spec B.10). Pure: no web, database or HTTP code.

Every allowed and refused pair is tested (`tests/test_state_machine.py`); the diagram is in `docs/workflow.md`.
State names are the ones Milestone 5 stored (ADR-0046).
"""

from __future__ import annotations

from enum import StrEnum


class CaseState(StrEnum):
    NEW = "New"
    INVESTIGATING = "Investigating"
    AWAITING_INFORMATION = "Awaiting information"
    PENDING_APPROVAL = "Pending approval"
    APPROVED = "Approved"
    EXECUTING = "Executing"
    RESOLVED = "Resolved"
    ESCALATED = "Escalated"
    REJECTED = "Rejected"
    EXECUTION_UNKNOWN = "Execution unknown"


S = CaseState

TRANSITIONS: dict[CaseState, frozenset[CaseState]] = {
    S.NEW: frozenset({S.INVESTIGATING}),
    S.INVESTIGATING: frozenset({S.PENDING_APPROVAL, S.AWAITING_INFORMATION, S.ESCALATED, S.RESOLVED}),
    S.AWAITING_INFORMATION: frozenset({S.INVESTIGATING}),
    # Pending approval -> Investigating: the evidence or the policy changed, so the approval can't stand (ADR-0055, D2).
    S.PENDING_APPROVAL: frozenset({S.APPROVED, S.REJECTED, S.INVESTIGATING}),
    # Approved -> Escalated: the shared write path refused to execute (another case already credited the stay).
    # Approved -> Investigating: the approval was invalidated or expired. It's never revived: a new request follows.
    S.APPROVED: frozenset({S.EXECUTING, S.ESCALATED, S.INVESTIGATING}),
    # Executing -> Approved: the upstream refused the request outright, so nothing was applied and it may be re-run.
    # Executing -> Escalated: a key conflict or a different record came back, so something else was applied.
    S.EXECUTING: frozenset({S.RESOLVED, S.EXECUTION_UNKNOWN, S.APPROVED, S.ESCALATED}),
    # Reconciliation decides: found and matching -> Resolved; found and different -> Escalated; confirmed absent ->
    # Approved (safe to resubmit, same key). Nothing else leaves this state: it never hides the uncertainty.
    S.EXECUTION_UNKNOWN: frozenset({S.RESOLVED, S.APPROVED, S.ESCALATED}),
    # Reopening, with a reason and an audit trail (spec B.10; `cases.reopen`).
    S.RESOLVED: frozenset({S.INVESTIGATING}),
    S.ESCALATED: frozenset({S.INVESTIGATING}),
    S.REJECTED: frozenset({S.INVESTIGATING}),
}

# Where work rests: nothing more happens unless someone reopens the case.
TERMINAL = frozenset({S.RESOLVED, S.ESCALATED, S.REJECTED})


class InvalidTransition(Exception):
    def __init__(self, current: CaseState, target: CaseState) -> None:
        super().__init__(f"a case in '{current}' cannot move to '{target}'")
        self.current, self.target = current, target


def check_transition(current: CaseState, target: CaseState) -> None:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(current, target)
