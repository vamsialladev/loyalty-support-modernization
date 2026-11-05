"""Local demo sign-in (spec C.4; ADR-0045): accounts in the app database, argon2id password hashes.

Offline default for the portfolio profile. Not enterprise identity: no MFA, no recovery flow, no lockout yet (login
rate limiting, deactivation and recovery are Milestone 9, SEC-07). The OIDC adapter replaces it in that profile.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.clock import utc_now
from app.domain.roles import Identity, Role
from app.persistence.models import User

_HASHER = PasswordHasher()  # argon2id with the library's current recommended parameters
# Verified when the username is unknown, so a wrong username costs the same time as a wrong password.
_DUMMY_HASH = _HASHER.hash("not-a-real-password-used-only-for-timing")

DEMO_USERS: tuple[tuple[str, str, Role], ...] = (
    ("agent.ana", "Ana (agent)", Role.AGENT),
    ("agent.ben", "Ben (agent)", Role.AGENT),
    ("supervisor.sam", "Sam (supervisor)", Role.SUPERVISOR),
    ("supervisor.sky", "Sky (supervisor)", Role.SUPERVISOR),
    ("admin.ada", "Ada (administrator)", Role.ADMINISTRATOR),
    ("auditor.abe", "Abe (auditor)", Role.AUDITOR),
)


def _identity(user: User) -> Identity:
    return Identity(user.id, user.username, user.display_name, Role(user.role))


class LocalDemoIdentity:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def authenticate(self, username: str, password: str) -> Identity | None:
        with self._sessions() as s:
            user = s.scalars(select(User).where(User.username == username.strip())).first()
        try:
            _HASHER.verify(user.password_hash if user else _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            return None
        if user is None or not user.active:
            return None
        return _identity(user)

    def lookup(self, user_id: int) -> Identity | None:
        with self._sessions() as s:
            user = s.get(User, user_id)
        return _identity(user) if user is not None and user.active else None


def ensure_demo_users(s: Session, password: str) -> list[str]:
    """Create the demo accounts, or reset their password and role. Returns the usernames (never the password)."""
    if len(password) < 12:
        raise ValueError("DEMO_USER_PASSWORD must be at least 12 characters")
    names = []
    for username, display, role in DEMO_USERS:
        user = s.scalars(select(User).where(User.username == username)).first()
        if user is None:
            user = User(username=username, created_at_utc=utc_now())
            s.add(user)
        user.display_name, user.role, user.active = display, role.value, True
        user.password_hash = _HASHER.hash(password)
        names.append(username)
    s.commit()
    return names
