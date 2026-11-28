"""After a database restore: end every access the backup still holds as live (ROLL-03; ADR-0096).

A restore brings back the database as it was at the backup. Any session, API token or break-glass grant revoked after
that comes back as live. Drill D4 proved it: a session revoked after the backup worked again after the restore
(verification log M13b row 11). The restore can't know which were revoked since, so this ends them all:

- every open **session**: everyone signs in again;
- every unrevoked **API token**: each integration gets a new one;
- every open **break-glass grant**.

It records one audit event, `restore_access_sealed`, with the counts. That's a security event. Run it before the app
takes traffic:

    python -m app.services.after_restore --reason "restored from the 2026-11-28 backup"

What it can't do: an account deactivated after the backup is active again. With SSO the identity provider decides who
signs in, so this matters only for local accounts, which an administrator re-checks (`docs/backup-restore.md`).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.persistence.models import ApiToken, BreakGlassGrant, UserSession
from app.services import jobs
from app.services.instrumentation import record_system

MIN_REASON = 10


@dataclass(frozen=True)
class Sealed:
    sessions: int
    api_tokens: int
    break_glass_grants: int


def seal_access(s: Session, reason: str) -> Sealed:
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        raise ValueError(f"say which backup was restored, in at least {MIN_REASON} characters")
    now = utc_now()

    def ended(statement: Any) -> int:
        return int(getattr(s.execute(statement), "rowcount", 0) or 0)

    sealed = Sealed(
        ended(update(UserSession).where(UserSession.revoked_at_utc.is_(None)).values(revoked_at_utc=now)),
        ended(update(ApiToken).where(ApiToken.revoked_at_utc.is_(None)).values(revoked_at_utc=now)),
        ended(
            update(BreakGlassGrant)
            .where(BreakGlassGrant.ended_at_utc.is_(None))
            .values(ended_at_utc=now, end_reason="revoked", ended_by=jobs.SYSTEM.username)
        ),
    )
    record_system(
        s,
        jobs.SYSTEM,
        "restore_access_sealed",
        sessions=sealed.sessions,
        api_tokens=sealed.api_tokens,
        break_glass_grants=sealed.break_glass_grants,
        reason=reason,
    )
    s.commit()
    return sealed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.after_restore")
    parser.add_argument("--reason", required=True, help="which backup was restored, and why")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    settings = AppSettings.from_env()
    with make_sessions(make_engine(settings.database_url))() as s:
        sealed = seal_access(s, args.reason)
    print(
        f"ended {sealed.sessions} session(s), {sealed.api_tokens} API token(s) and "
        f"{sealed.break_glass_grants} break-glass grant(s); everyone signs in again"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
