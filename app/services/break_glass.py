"""Break-glass: emergency administrator access, time-limited, with a reason, alerted and audited (spec E6; ENT-26,
ADR-0093).

Granted out of band, from the command line on a machine that can reach the database, never from the console:

    python -m app.services.break_glass grant --user ana --by sam --minutes 30 --reason "INC-12: kill switch stuck on"
    python -m app.services.break_glass revoke --grant 7 --by sam --reason "INC-12 resolved"
    python -m app.services.break_glass list

The rules, every one deterministic and tested (`tests/test_break_glass.py`):
- **At most 60 minutes,** and at least 1. It's never extended: no command does that. It ends by expiring or by being
  revoked, and only a new grant can follow it. A second grant while one is open is refused.
- **A reason** of at least 15 characters. It's kept on the grant and in the audit row, and never exported to the SIEM.
- **Two people:** the grantor is a different, active supervisor or administrator of the same customer, and doesn't hold
  an open grant themselves, so an elevated person can't hand access on.
- **Who can be raised:** an active agent or supervisor. An auditor stays independent; an administrator needs none; a
  service or system account is never raised.
- **Never in the public demo** (`PUBLIC_DEMO_MODE`): refused here, and ignored by the session check.
- **Raised means administrator,** read on every request by `app.services.sessions.resolve`. An administrator manages
  configuration (the kill switch, policy publishing) and doesn't work cases, so a grant can't approve or post money.
  Everything done under it carries the grant's ID in the audit trail.
- **Audited and alerted:** granted, refused, revoked and expired are security events (`app.services.security_events`).
  An expiry is recorded on the person's first request after it, or by `list`; the grant row holds the time either way.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.roles import Identity, Role
from app.persistence.models import BreakGlassGrant, User
from app.services import jobs
from app.services.instrumentation import SCRIPTED_PREFIX, SERVICE_PREFIX, SYSTEM_PREFIX, record_system

MAX_MINUTES = 60
MIN_REASON = 15
GRANTORS = (Role.SUPERVISOR, Role.ADMINISTRATOR)
RAISABLE = (Role.AGENT, Role.SUPERVISOR)
NOT_PEOPLE = (SYSTEM_PREFIX, SERVICE_PREFIX, SCRIPTED_PREFIX)


class Refused(Exception):
    """A grant or revocation that the rules don't allow. `code` is recorded; the message is for the operator."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Active:
    grant_id: int
    expires_at_utc: str


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _operator(username: str) -> Identity:
    """The audit actor for a command-line step: the named grantor, whatever their role."""
    return Identity(0, username, username, Role.ADMINISTRATOR)


def _user(s: Session, username: str) -> User | None:
    return s.scalar(select(User).where(User.username == username))


def _open_grant(s: Session, user_id: int) -> BreakGlassGrant | None:
    return s.scalar(
        select(BreakGlassGrant)
        .where(BreakGlassGrant.user_id == user_id, BreakGlassGrant.ended_at_utc.is_(None))
        .order_by(BreakGlassGrant.id.desc())
    )


def _expire(s: Session, grant: BreakGlassGrant, username: str) -> None:
    grant.ended_at_utc, grant.end_reason, grant.ended_by = grant.expires_at_utc, "expired", jobs.SYSTEM.username
    record_system(s, jobs.SYSTEM, "break_glass_expired", grant=grant.id, username=username)


def _refuse(s: Session, by: str, code: str, message: str, **detail: object) -> Refused:
    record_system(s, _operator(by or "unknown"), "break_glass_refused", kind=code, **detail)
    s.commit()
    return Refused(code, message)


def grant(
    s: Session,
    *,
    user: str,
    by: str,
    minutes: int,
    reason: str,
    public_demo: bool,
    now: datetime | None = None,
) -> BreakGlassGrant:
    """A new grant, or `Refused` with the reason. Every outcome is written to the audit trail."""
    now = now or datetime.now(UTC)
    reason = (reason or "").strip()
    if public_demo:
        raise _refuse(s, by, "public_demo", "break-glass is off in the public demo", username=user)
    if not 1 <= minutes <= MAX_MINUTES:
        raise _refuse(s, by, "minutes", f"a grant lasts 1 to {MAX_MINUTES} minutes", username=user)
    if len(reason) < MIN_REASON:
        raise _refuse(s, by, "reason", f"a reason of at least {MIN_REASON} characters is required", username=user)
    if user == by:
        raise _refuse(s, by, "self", "no one can grant break-glass to themselves", username=user)
    grantor, grantee = _user(s, by), _user(s, user)
    if grantor is None or not grantor.active or Role(grantor.role) not in GRANTORS:
        raise _refuse(s, by, "grantor", "the grantor must be an active supervisor or administrator", username=user)
    if grantee is None or not grantee.active:
        raise _refuse(s, by, "grantee", "the person must have an active account", username=user)
    if grantee.username.startswith(NOT_PEOPLE) or Role(grantee.role) not in RAISABLE:
        raise _refuse(s, by, "grantee", "only an active agent or supervisor can be raised", username=user)
    if grantor.customer_id != grantee.customer_id:
        raise _refuse(s, by, "customer", "the grantor and the person must belong to the same customer", username=user)
    held = _open_grant(s, grantor.id)
    if held is not None and held.expires_at_utc > _ts(now):
        raise _refuse(s, by, "grantor_elevated", "someone under break-glass can't grant it", username=user)
    current = _open_grant(s, grantee.id)
    if current is not None:
        if current.expires_at_utc > _ts(now):
            raise _refuse(
                s, by, "already_open", "this person already has an open grant: revoke it or let it expire first",
                username=user, grant=current.id,
            )  # fmt: skip
        _expire(s, current, grantee.username)
    row = BreakGlassGrant(
        user_id=grantee.id,
        granted_by=grantor.username,
        reason=reason,
        granted_at_utc=_ts(now),
        expires_at_utc=_ts(now + timedelta(minutes=minutes)),
    )
    s.add(row)
    s.flush()
    record_system(
        s, _operator(grantor.username), "break_glass_granted",
        grant=row.id, username=grantee.username, minutes=minutes, expires_at_utc=row.expires_at_utc, reason=reason,
    )  # fmt: skip
    s.commit()
    return row


def revoke(s: Session, *, grant_id: int, by: str, reason: str, now: datetime | None = None) -> BreakGlassGrant:
    """End an open grant now. The revoker is an active supervisor or administrator, not under break-glass."""
    now = now or datetime.now(UTC)
    reason = (reason or "").strip()
    row = s.get(BreakGlassGrant, grant_id)
    revoker = _user(s, by)
    if row is None or row.ended_at_utc is not None:
        raise _refuse(s, by, "not_open", "no open grant with that number", grant=grant_id)
    if revoker is None or not revoker.active or Role(revoker.role) not in GRANTORS:
        raise _refuse(s, by, "revoker", "the revoker must be an active supervisor or administrator", grant=grant_id)
    held = _open_grant(s, revoker.id)
    if held is not None and held.expires_at_utc > _ts(now):
        raise _refuse(s, by, "revoker_elevated", "someone under break-glass can't revoke a grant", grant=grant_id)
    if len(reason) < MIN_REASON:
        raise _refuse(s, by, "reason", f"a reason of at least {MIN_REASON} characters is required", grant=grant_id)
    row.ended_at_utc, row.end_reason, row.ended_by = _ts(now), "revoked", revoker.username
    record_system(s, _operator(revoker.username), "break_glass_revoked", grant=row.id, reason=reason)
    s.commit()
    return row


def active_for(s: Session, identity: Identity, now: datetime | None = None) -> Active | None:
    """The person's open, unexpired grant, or None. An open grant past its time is closed and recorded here."""
    if identity.username.startswith(NOT_PEOPLE):
        return None
    row = _open_grant(s, identity.user_id)
    if row is None:
        return None
    if row.expires_at_utc <= _ts(now or datetime.now(UTC)):
        _expire(s, row, identity.username)
        s.commit()
        return None
    return Active(row.id, row.expires_at_utc)


def expire_due(s: Session, now: datetime | None = None) -> int:
    """Close and record every open grant past its time. Returns how many were closed."""
    now_text = _ts(now or datetime.now(UTC))
    rows = s.scalars(
        select(BreakGlassGrant).where(
            BreakGlassGrant.ended_at_utc.is_(None), BreakGlassGrant.expires_at_utc <= now_text
        )
    ).all()
    for row in rows:
        person = s.get(User, row.user_id)
        _expire(s, row, person.username if person else str(row.user_id))
    s.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.break_glass")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("grant", help="grant emergency administrator access")
    g.add_argument("--user", required=True)
    g.add_argument("--by", required=True, help="the grantor's username: a different supervisor or administrator")
    g.add_argument("--minutes", type=int, default=30, help=f"1 to {MAX_MINUTES}")
    g.add_argument("--reason", required=True)
    r = sub.add_parser("revoke", help="end an open grant now")
    r.add_argument("--grant", type=int, required=True)
    r.add_argument("--by", required=True)
    r.add_argument("--reason", required=True)
    sub.add_parser("list", help="close expired grants, then list the open ones")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    settings = AppSettings.from_env()
    with make_sessions(make_engine(settings.database_url))() as s:
        try:
            if args.command == "grant":
                row = grant(
                    s, user=args.user, by=args.by, minutes=args.minutes, reason=args.reason,
                    public_demo=settings.public_demo_mode,
                )  # fmt: skip
                print(f"granted #{row.id} to {args.user} until {row.expires_at_utc} (UTC)")
            elif args.command == "revoke":
                row = revoke(s, grant_id=args.grant, by=args.by, reason=args.reason)
                print(f"revoked #{row.id}")
            else:
                closed = expire_due(s)
                rows = s.scalars(select(BreakGlassGrant).where(BreakGlassGrant.ended_at_utc.is_(None))).all()
                print(f"closed {closed} expired grant(s); open: {len(rows)}")
                for row in rows:
                    print(f"  #{row.id} user {row.user_id} by {row.granted_by} until {row.expires_at_utc} (UTC)")
        except Refused as refusal:
            print(f"refused ({refusal.code}): {refusal}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
