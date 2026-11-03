"""Who may do what (spec B.10 roles). Pure rules; the services call them, the browser never decides.

Milestone 5 has the two roles arm A's browser flow needs. Administrator and auditor arrive with Milestones 6 and 9.
A role comes only from the server-side session (`app.services.sessions`), never from a form field or a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    AGENT = "agent"
    SUPERVISOR = "supervisor"


@dataclass(frozen=True)
class Identity:
    user_id: int
    username: str
    display_name: str
    role: Role


class NotPermitted(Exception):
    """The caller's role or relationship to the record does not allow the action."""


def require_case_worker(who: Identity) -> None:
    if who.role not in (Role.AGENT, Role.SUPERVISOR):
        raise NotPermitted("only agents and supervisors work cases")


def approval_refusal(who: Identity, requested_by: str) -> str | None:
    """Why `who` may not approve, reject or execute an adjustment requested by `requested_by`, or None if they may.

    Spec B.10: supervisor approval is required, and the creator cannot approve their own adjustment.
    """
    if who.role is not Role.SUPERVISOR:
        return "only a supervisor can decide on an adjustment"
    if who.username == requested_by:
        return "you requested this adjustment, so another supervisor must decide on it"
    return None
