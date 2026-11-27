"""The kill switch for provider prompt caching (L3; CACHE-02, ADR-0090).

`FEATURE_PROMPT_CACHE` turns caching on for a deployment (default off). This switch can only turn it **off**, and
without a restart: it's a database row, read at the start of every AI run. A missing row means "not killed", so the
flag alone decides; an administrator's first use of the switch creates the row.

Why off is the only direction it moves: caching never changes what the model reads, so turning it off is always safe.
Reasons to use it: a cost or latency anomaly on the dashboard, a provider incident, or a change being rolled back
(`docs/runbooks/prompt-cache.md`). Every change needs a reason and is audited.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.roles import Identity, require_administrator
from app.persistence.models import SystemSwitch
from app.services.cases import WorkflowError
from app.services.instrumentation import record_system

SWITCH = "prompt_cache"
MIN_REASON = 10


def state(s: Session) -> SystemSwitch | None:
    return s.get(SystemSwitch, SWITCH)


def is_killed(s: Session) -> bool:
    found = s.scalars(
        select(SystemSwitch).where(SystemSwitch.name == SWITCH).execution_options(populate_existing=True)
    ).first()
    return found is not None and found.engaged


def set_killed(s: Session, who: Identity, killed: bool, reason: str) -> SystemSwitch:
    require_administrator(who)
    if len(reason.strip()) < MIN_REASON:
        raise WorkflowError(f"give the reason, in at least {MIN_REASON} characters")
    row = s.scalars(
        select(SystemSwitch)
        .where(SystemSwitch.name == SWITCH)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        row = SystemSwitch(name=SWITCH, engaged=killed)
        s.add(row)
    row.engaged, row.reason, row.changed_by, row.changed_at_utc = killed, reason.strip(), who.username, utc_now()
    record_system(s, who, "prompt_cache_switch_changed", killed=killed, reason=reason.strip())
    s.commit()
    return row
