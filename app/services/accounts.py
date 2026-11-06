"""Accounts: deactivation, recovery, machine tokens and the access review (spec C.4, C.5; SEC-07, ENT-27).

Tokens are shown once and stored only as hashes. Recovery revokes every session of that account. Every change is a
system event.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.business_time import format_utc
from app.domain.roles import Identity, Role, require_administrator
from app.persistence.models import ApiToken, RecoveryToken, User, UserSession
from app.services.instrumentation import record_system

RECOVERY_MINUTES = 30
MIN_PASSWORD = 12
API_TOKEN_DAYS = 7
_HASHER = PasswordHasher()


class AccountError(Exception):
    """Shown to the person: what can't be done, without saying more than that."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _later(minutes: int = 0, days: int = 0) -> str:
    return format_utc(datetime.now(UTC) + timedelta(minutes=minutes, days=days))


def revoke_sessions(s: Session, user_id: int) -> None:
    s.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at_utc.is_(None))
        .values(revoked_at_utc=utc_now())
    )


def users_of(s: Session, who: Identity) -> list[User]:
    require_administrator(who)
    query = select(User).where(User.customer_id == who.customer_id).order_by(User.username)
    return [u for u in s.scalars(query) if not u.username.startswith("scripted-")]


def set_active(s: Session, who: Identity, user_id: int, active: bool) -> None:
    """Deactivating ends every session at once: `sessions.resolve` re-reads the account on each request."""
    require_administrator(who)
    user = s.get(User, user_id)
    if user is None or user.customer_id != who.customer_id:
        raise AccountError("there's no such account")
    if user.id == who.user_id:
        raise AccountError("you can't change your own account here")
    user.active = active
    if not active:
        revoke_sessions(s, user.id)
    record_system(s, who, "account_activated" if active else "account_deactivated", username=user.username)
    s.commit()


def issue_recovery(s: Session, who: Identity, user_id: int) -> str:
    """An administrator hands this to the person out of band. It's one use and short-lived, and isn't stored in
    clear."""
    require_administrator(who)
    user = s.get(User, user_id)
    if user is None or user.customer_id != who.customer_id:
        raise AccountError("there's no such account")
    if user.external_id:
        raise AccountError("this account signs in through the identity provider")
    token = secrets.token_urlsafe(32)
    s.add(
        RecoveryToken(
            token_hash=_hash(token),
            user_id=user.id,
            created_by=who.username,
            created_at_utc=utc_now(),
            expires_at_utc=_later(minutes=RECOVERY_MINUTES),
        )
    )
    record_system(s, who, "recovery_issued", username=user.username)
    s.commit()
    return token


def redeem_recovery(s: Session, token: str, new_password: str) -> None:
    """The same message for a wrong, used or expired token, so none can be told from another."""
    if len(new_password) < MIN_PASSWORD:
        raise AccountError(f"use at least {MIN_PASSWORD} characters")
    row = s.get(RecoveryToken, _hash(token))
    if row is None or row.used_at_utc is not None or row.expires_at_utc <= utc_now():
        raise AccountError("this recovery link isn't valid. Ask an administrator for a new one")
    user = s.get(User, row.user_id)
    if user is None or not user.active:
        raise AccountError("this recovery link isn't valid. Ask an administrator for a new one")
    user.password_hash = _HASHER.hash(new_password)
    row.used_at_utc = utc_now()
    revoke_sessions(s, user.id)
    actor = Identity(user.id, user.username, user.display_name, Role(user.role), user.customer_id)
    record_system(s, actor, "recovery_used", username=user.username)
    s.commit()


# ---------- machine tokens: read-only, short-lived, separate from people (spec C.4, workload identity) ----------


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at_utc: str


def issue_api_token(s: Session, who: Identity, name: str, days: int = API_TOKEN_DAYS) -> IssuedToken:
    require_administrator(who)
    if not name.strip() or len(name) > 64:
        raise AccountError("give the token a short name")
    token = "lsm_" + secrets.token_urlsafe(32)
    expires = _later(days=max(1, min(days, 30)))
    s.add(
        ApiToken(
            token_hash=_hash(token),
            name=name.strip(),
            customer_id=who.customer_id,
            created_by=who.username,
            created_at_utc=utc_now(),
            expires_at_utc=expires,
        )
    )
    record_system(s, who, "api_token_issued", name=name.strip(), expires=expires)
    s.commit()
    return IssuedToken(token, expires)


def api_tokens_of(s: Session, who: Identity) -> list[ApiToken]:
    require_administrator(who)
    query = select(ApiToken).where(ApiToken.customer_id == who.customer_id).order_by(ApiToken.created_at_utc)
    return list(s.scalars(query))


def revoke_api_token(s: Session, who: Identity, name: str) -> None:
    require_administrator(who)
    query = select(ApiToken).where(
        ApiToken.customer_id == who.customer_id, ApiToken.name == name, ApiToken.revoked_at_utc.is_(None)
    )
    for row in s.scalars(query):
        row.revoked_at_utc = utc_now()
    record_system(s, who, "api_token_revoked", name=name)
    s.commit()


def identity_for_api_token(s: Session, token: str | None) -> Identity | None:
    """A machine reads as an auditor. It has no CSRF token, so it can't reach anything that changes state."""
    if not token:
        return None
    row = s.get(ApiToken, _hash(token))
    if row is None or row.revoked_at_utc is not None or row.expires_at_utc <= utc_now():
        return None
    return Identity(0, f"svc-{row.name}"[:64], row.name, Role.AUDITOR, row.customer_id)


# ---------- the periodic access review (ENT-27) ----------


def access_review_rows(s: Session, who: Identity) -> list[dict[str, str]]:
    require_administrator(who)
    rows = []
    for user in users_of(s, who):
        last = s.scalars(
            select(UserSession.created_at_utc)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at_utc.desc())
            .limit(1)
        ).first()
        rows.append(
            {
                "username": user.username,
                "role": user.role,
                "active": "yes" if user.active else "no",
                "source": "identity provider" if user.external_id else "local",
                "last_sign_in_utc": last or "never",
            }
        )
    return rows
