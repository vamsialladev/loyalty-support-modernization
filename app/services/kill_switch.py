"""The emergency switch for adjustments (spec B.10; WP-10, ADR-0061).

A database row, so it reaches the web process and every worker without a restart. Claims hold a shared lock on it and
changing it takes an exclusive one, so **once a change to "off" has committed, no new claim can pass**. Investigation
and reconciliation never look at it: they only read. If the row can't be found, adjustments stop.

The limit, stated plainly: a worker past its last check can still land one submission. The switch stops new work. It
can't recall a request already on its way to the customer's system.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.roles import Identity, require_administrator
from app.persistence.models import SystemSwitch
from app.services.cases import WorkflowError
from app.services.instrumentation import record_system

ADJUSTMENTS = "adjustments"
MIN_REASON = 10
MESSAGE = "Adjustments are switched off by an administrator. Investigation still works; nothing was submitted."


def state(s: Session) -> SystemSwitch | None:
    return s.get(SystemSwitch, ADJUSTMENTS)


def is_engaged(s: Session) -> bool:
    """A plain read, for the last look before a submission and for pages."""
    row = s.scalars(
        select(SystemSwitch).where(SystemSwitch.name == ADJUSTMENTS).execution_options(populate_existing=True)
    )
    found = row.first()
    return found is None or found.engaged


def is_engaged_for_claim(s: Session) -> bool:
    """Holds a shared lock until the caller's transaction ends, so a change to "off" waits for this claim to finish."""
    found = s.scalars(
        select(SystemSwitch)
        .where(SystemSwitch.name == ADJUSTMENTS)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    ).first()
    return found is None or found.engaged


def set_engaged(s: Session, who: Identity, engaged: bool, reason: str) -> SystemSwitch:
    require_administrator(who)
    if len(reason.strip()) < MIN_REASON:
        raise WorkflowError(f"give the reason, in at least {MIN_REASON} characters")
    row = s.scalars(
        select(SystemSwitch)
        .where(SystemSwitch.name == ADJUSTMENTS)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        row = SystemSwitch(name=ADJUSTMENTS, engaged=engaged)
        s.add(row)
    row.engaged, row.reason, row.changed_by, row.changed_at_utc = engaged, reason.strip(), who.username, utc_now()
    record_system(s, who, "kill_switch_changed", engaged=engaged, reason=reason.strip())
    s.commit()
    return row
