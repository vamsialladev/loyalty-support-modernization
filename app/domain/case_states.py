"""Case states and the transitions the server allows (spec B.10). Pure: no web, database or HTTP code.

Milestone 5 defines every B.10 state and the transitions arm A uses. Milestone 6 completes the machine (reopening,
the full transition test set, a diagram in `docs/workflow.md`) without renaming anything (ADR-0046).
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
    S.PENDING_APPROVAL: frozenset({S.APPROVED, S.REJECTED}),
    # Approved -> Escalated: the shared write path refused to execute (another case already credited the stay).
    S.APPROVED: frozenset({S.EXECUTING, S.ESCALATED}),
    # Executing -> Approved: the upstream refused the request outright, so nothing was applied and it may be re-run.
    S.EXECUTING: frozenset({S.RESOLVED, S.EXECUTION_UNKNOWN, S.APPROVED}),
    # Reconciliation decides: found upstream -> Resolved; confirmed absent -> Approved (safe to resubmit, same key).
    S.EXECUTION_UNKNOWN: frozenset({S.RESOLVED, S.APPROVED}),
    S.RESOLVED: frozenset(),
    S.ESCALATED: frozenset(),
    S.REJECTED: frozenset(),
}

TERMINAL = frozenset(state for state, targets in TRANSITIONS.items() if not targets)


class InvalidTransition(Exception):
    def __init__(self, current: CaseState, target: CaseState) -> None:
        super().__init__(f"a case in '{current}' cannot move to '{target}'")
        self.current, self.target = current, target


def check_transition(current: CaseState, target: CaseState) -> None:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(current, target)
