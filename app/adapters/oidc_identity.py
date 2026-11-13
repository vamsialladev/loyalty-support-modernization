"""Sign-in through an OpenID Connect provider, such as the local Keycloak profile (spec C.4; SEC-08, ENT-25).

Authorization code flow with PKCE, state and nonce. Token checks come from PyJWT, a maintained library, with no
cryptography of our own: signature against the provider's published keys, issuer, audience, expiry, nonce. A key the
app doesn't know triggers one refetch of the provider's keys, which is how rotation works. `alg: none` and symmetric
algorithms are refused.

Roles come from the provider's groups through `config/customers/<id>.yaml`. No mapped group means no access.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.oidc_discovery import DiscoveryFailed, ProviderMetadata
from app.clock import utc_now
from app.domain.roles import Identity, Role
from app.outbound import check_url
from app.persistence.models import User
from app.services.instrumentation import record_system

ALLOWED_ALGORITHMS = ("RS256", "ES256", "PS256")
# argon2 can't verify this, so no password can ever sign in to such an account.
NO_PASSWORD = "!oidc-no-password"  # noqa: S105
TIMEOUT_SECONDS = 10.0


class OidcError(Exception):
    """The reason is for the log and the audit event. The person sees only that sign-in failed."""


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    group_roles: dict[str, str]
    customer_id: str = "hg-demo"
    groups_claim: str = "groups"
    fetch_url: str = ""  # where this process reaches the provider, if not at the issuer URL (TD-52)


@dataclass(frozen=True)
class LoginStart:
    url: str
    state: str
    nonce: str
    verifier: str


_REASONS = {
    "unreachable": "provider_unreachable",
    "issuer_mismatch": "issuer_mismatch_in_discovery",
    "unknown_key": "unknown_signing_key",
}


def _oidc_error(failed: DiscoveryFailed) -> OidcError:
    if failed.kind == "bad_response":
        return OidcError(f"unexpected_response:{failed.status_code}")
    return OidcError(_REASONS[failed.kind])


class OidcClient:
    """Discovery and keys come from `app.adapters.oidc_discovery`, shared with the protocol services (TD-51)."""

    def __init__(self, settings: OidcSettings, http: httpx.Client | None = None) -> None:
        self.settings = settings
        self.http = http or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
        self._provider = ProviderMetadata(settings.issuer, self.http, settings.fetch_url)

    def discovery(self) -> dict[str, Any]:
        try:
            return self._provider.document()
        except DiscoveryFailed as failed:
            raise _oidc_error(failed) from failed

    def start(self) -> LoginStart:
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return LoginStart(f"{self.discovery()['authorization_endpoint']}?{urlencode(params)}", state, nonce, verifier)

    def exchange(self, code: str, verifier: str) -> str:
        endpoint = self.discovery()["token_endpoint"]
        check_url(endpoint, (self._provider.base,))
        try:
            response = self.http.post(
                endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.redirect_uri,
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                    "code_verifier": verifier,
                },
            )
        except httpx.HTTPError as exc:
            raise OidcError("provider_unreachable") from exc
        if response.status_code != 200:
            raise OidcError(f"token_endpoint:{response.status_code}")
        token = response.json().get("id_token")
        if not token:
            raise OidcError("no_id_token")
        return str(token)

    def _key_for(self, token: str) -> Any:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise OidcError("malformed_token") from exc
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise OidcError("algorithm_not_allowed")
        try:  # an unknown key means the provider rotated: the helper fetches once more
            return self._provider.key_for(header.get("kid"))
        except DiscoveryFailed as failed:
            raise _oidc_error(failed) from failed

    def verify(self, token: str, nonce: str) -> dict[str, Any]:
        key = self._key_for(token)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.settings.client_id,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise OidcError(type(exc).__name__) from exc
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("nonce_mismatch")
        return claims


def role_from_claims(claims: dict[str, Any], settings: OidcSettings) -> Role:
    """The strongest mapped role wins. An unmapped user has no access: deny by default (ENT-25)."""
    groups = claims.get(settings.groups_claim) or []
    names = {str(g).strip("/") for g in groups} if isinstance(groups, list) else set()
    mapped = {Role(settings.group_roles[g]) for g in names if g in settings.group_roles}
    for role in (Role.ADMINISTRATOR, Role.SUPERVISOR, Role.AUDITOR, Role.AGENT):
        if role in mapped:
            return role
    raise OidcError("no_mapped_group")


def provision(s: Session, claims: dict[str, Any], settings: OidcSettings) -> Identity:
    """Find or create the local row that sessions and the audit log point at. The provider decides the role on each
    sign-in. An account deactivated here stays out, whatever the provider says."""
    role = role_from_claims(claims, settings)
    external_id = f"{claims['iss']}|{claims['sub']}"
    user = s.scalars(select(User).where(User.external_id == external_id)).first()
    username = str(claims.get("preferred_username") or claims["sub"])[:60]
    if user is None:
        taken = s.scalars(select(User).where(User.username == username)).first()
        user = User(
            username=username if taken is None else f"oidc-{hashlib.sha256(external_id.encode()).hexdigest()[:16]}",
            display_name=str(claims.get("name") or username)[:120],
            role=role.value,
            password_hash=NO_PASSWORD,
            external_id=external_id,
            customer_id=settings.customer_id,
            created_at_utc=utc_now(),
        )
        s.add(user)
        s.flush()
    if not user.active:
        raise OidcError("account_deactivated")
    if user.role != role.value:
        record_system(s, _identity(user), "role_changed_by_provider", previous=user.role, now=role.value)
        user.role = role.value
    s.commit()
    return _identity(user)


def _identity(user: User) -> Identity:
    return Identity(user.id, user.username, user.display_name, Role(user.role), user.customer_id)
