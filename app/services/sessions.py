"""Server-side login sessions and CSRF tokens (spec C.4, C.7; ADR-0045).

The browser gets a random session token in an HttpOnly cookie; the database keeps only its SHA-256, the user, a CSRF
token, and the expiry. Logout revokes the row. Every state-changing request must carry the session's CSRF token
(form field or `X-CSRF-Token` header). The role is read from the user record on every request, never from the
browser.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.roles import Identity
from app.persistence.models import UserSession
from app.ports.identity import IdentityProvider

SESSION_HOURS = 8


@dataclass(frozen=True)
class ActiveSession:
    identity: Identity
    csrf_token: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def start(s: Session, identity: Identity, now: datetime | None = None) -> tuple[str, str]:
    """A new session for a signed-in user. Returns (session token for the cookie, CSRF token)."""
    now = now or datetime.now(UTC)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    s.add(
        UserSession(
            token_hash=_hash(token),
            user_id=identity.user_id,
            csrf_token=csrf,
            created_at_utc=_ts(now),
            expires_at_utc=_ts(now + timedelta(hours=SESSION_HOURS)),
        )
    )
    s.commit()
    return token, csrf


def resolve(
    s: Session, provider: IdentityProvider, token: str | None, now: datetime | None = None
) -> ActiveSession | None:
    if not token:
        return None
    row = s.get(UserSession, _hash(token))
    now_text = _ts(now or datetime.now(UTC))
    if row is None or row.revoked_at_utc is not None or row.expires_at_utc <= now_text:
        return None
    identity = provider.lookup(row.user_id)
    if identity is None:
        return None
    return ActiveSession(identity, row.csrf_token)


def revoke(s: Session, token: str | None) -> None:
    if not token:
        return
    row = s.get(UserSession, _hash(token))
    if row is not None and row.revoked_at_utc is None:
        row.revoked_at_utc = utc_now()
        s.commit()


def csrf_ok(active: ActiveSession, submitted: str | None) -> bool:
    return bool(submitted) and hmac.compare_digest(active.csrf_token.encode(), (submitted or "").encode())
