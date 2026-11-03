"""Who is signing in (ADR-0003): one `IdentityProvider` port, one active adapter per deployment.

Milestone 5 ships the local demo adapter (`app.adapters.local_demo_identity`). The enterprise OIDC adapter (local
Keycloak) arrives in Milestone 9 and the Supabase Auth adapter in Milestone 15; each returns the same `Identity`, so
nothing behind the login changes when the adapter does (`docs/real-system-swap-guide.md`).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.roles import Identity


class IdentityProvider(Protocol):
    def authenticate(self, username: str, password: str) -> Identity | None:
        """The identity for these credentials, or None. Never says whether the username exists."""
        ...

    def lookup(self, user_id: int) -> Identity | None:
        """The current identity for a user ID (None if the account is gone or deactivated)."""
        ...
