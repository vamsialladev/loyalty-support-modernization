"""Access tokens for the protocol services, checked as an OAuth resource server (spec G.3; RFC-0004; ADR-0071).

MCP 2026-07-28 makes the server a resource server: it MUST validate the token's audience and MUST NOT accept a token
that wasn't issued for it (RFC 8707, RFC 9728). A2A asks the same of every request. So each service has its own
audience, and a token for one is refused by the others. Incoming tokens are never forwarded anywhere.

The tokens come from the identity provider (the local Keycloak in Compose). PyJWT checks them: signature against the
provider's published keys, issuer, audience, expiry, issued-at, subject. Nothing here is our own cryptography.
`alg: none` and symmetric algorithms are refused, and so is an ID token presented as an access token.

The customer a caller may see comes from the verified token, never from a message, and a machine caller is a
read-only auditor (the same as the Milestone 9 machine tokens).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWK, PyJWKSet

from app.domain.roles import Identity, Role
from app.outbound import check_url

ALLOWED_ALGORITHMS = ("RS256", "ES256", "PS256")
REQUIRED_CLAIMS = ["exp", "iat", "sub", "aud", "iss"]
ACCESS_TOKEN_TYPES = (None, "Bearer", "at+jwt")  # Keycloak marks access tokens "Bearer" and ID tokens "ID"
MAX_TOKEN_CHARS = 8192
MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 10.0
SERVICE_PREFIX = "svc-"


class TokenRejected(Exception):
    """Why a token isn't accepted. `status` is 401 for a missing, bad or expired token and 403 for a good token
    without the scope. `reason` goes to the audit log; callers see only the standard error."""

    def __init__(self, reason: str, status: int = 401, scope: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.scope = scope


@dataclass(frozen=True)
class ResourceServer:
    """One protocol service, as the identity provider knows it."""

    name: str  # "mcp", "a2a-specialist": part of the caller's audit name
    issuer: str
    audience: str  # this service's own canonical URL (the RFC 8707 resource)
    scopes: frozenset[str]  # what this service understands; a token needs at least one to be useful here
    customer_claim: str = "customer_id"
    leeway_seconds: int = 30


@dataclass(frozen=True)
class Caller:
    subject: str
    client_id: str
    scopes: frozenset[str]
    customer_id: str
    expires_at: int
    token_id: str | None = None
    service: str = ""

    def identity(self) -> Identity:
        """A machine caller reads, as an auditor does: no case work, no approvals, no configuration."""
        name = f"{SERVICE_PREFIX}{self.service}-{self.client_id}"[:64]
        return Identity(0, name, f"{self.service} client {self.client_id}", Role.AUDITOR, self.customer_id)


class KeySource(Protocol):
    def key_for(self, kid: str | None) -> PyJWK: ...


@dataclass
class StaticKeys:
    """Keys handed over directly: for tests and for a provider whose keys are pinned in configuration."""

    jwks: Mapping[str, Any]

    def key_for(self, kid: str | None) -> PyJWK:
        for key in PyJWKSet.from_dict(dict(self.jwks)).keys:
            if key.key_id == kid:
                return key
        raise TokenRejected("unknown_signing_key")


@dataclass
class IssuerKeys:
    """The provider's published keys, found through its discovery document and fetched only from the issuer's own
    host. An unknown key ID triggers one refetch, which is how key rotation works; never more than one per call."""

    issuer: str
    http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False))
    _keys: PyJWKSet | None = None
    _jwks_uri: str | None = None

    def _get_json(self, url: str) -> dict[str, Any]:
        check_url(url, (self.issuer,))
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise TokenRejected("issuer_unreachable", status=503) from exc
        if response.status_code != 200 or len(response.content) > MAX_RESPONSE_BYTES:
            raise TokenRejected(f"issuer_response_{response.status_code}", status=503)
        data: dict[str, Any] = response.json()
        return data

    def _uri(self) -> str:
        if self._jwks_uri is None:
            found = self._get_json(self.issuer.rstrip("/") + "/.well-known/openid-configuration")
            if found.get("issuer") != self.issuer:
                raise TokenRejected("issuer_mismatch_in_discovery", status=503)
            self._jwks_uri = str(found["jwks_uri"])
        return self._jwks_uri

    def key_for(self, kid: str | None) -> PyJWK:
        for refetch in (False, True):
            if self._keys is None or refetch:
                self._keys = PyJWKSet.from_dict(self._get_json(self._uri()))
            for key in self._keys.keys:
                if key.key_id == kid:
                    return key
        raise TokenRejected("unknown_signing_key")


def _scopes(claims: Mapping[str, Any]) -> frozenset[str]:
    raw = claims.get("scope", "")
    if isinstance(raw, str):
        return frozenset(raw.split())
    if isinstance(raw, list):
        return frozenset(str(s) for s in raw)
    return frozenset()


@dataclass
class TokenVerifier:
    server: ResourceServer
    keys: KeySource
    require_any_scope: bool = True  # False when the SDK in front answers the 403 itself (MCP)

    def verify(self, token: str) -> Caller:
        if not token or len(token) > MAX_TOKEN_CHARS:
            raise TokenRejected("missing_or_oversized_token")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenRejected("malformed_token") from exc
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise TokenRejected("algorithm_not_allowed")
        key = self.keys.key_for(header.get("kid"))
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.server.audience,
                issuer=self.server.issuer,
                leeway=self.server.leeway_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenRejected("expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenRejected("wrong_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenRejected("wrong_issuer") from exc
        except jwt.PyJWTError as exc:
            raise TokenRejected(type(exc).__name__) from exc
        if claims.get("typ") not in ACCESS_TOKEN_TYPES:
            raise TokenRejected("not_an_access_token")
        customer = claims.get(self.server.customer_claim)
        if not isinstance(customer, str) or not customer:
            raise TokenRejected("no_customer_claim")
        scopes = _scopes(claims)
        if self.require_any_scope and not scopes & self.server.scopes:
            raise TokenRejected("no_scope_for_this_service", status=403, scope=" ".join(sorted(self.server.scopes)))
        client_id = str(claims.get("azp") or claims.get("client_id") or claims["sub"])
        return Caller(
            subject=str(claims["sub"]),
            client_id=client_id[:40],
            scopes=scopes,
            customer_id=customer,
            expires_at=int(claims["exp"]),
            token_id=str(claims["jti"]) if claims.get("jti") else None,
            service=self.server.name,
        )


def require_scope(caller: Caller, scope: str) -> None:
    """403 with the scope that would have worked (RFC 6750 `insufficient_scope`)."""
    if scope not in caller.scopes:
        raise TokenRejected("insufficient_scope", status=403, scope=scope)


def bearer(authorization: str | None) -> str:
    """The token from an `Authorization: Bearer` header. Anything else is a missing token."""
    if not authorization:
        raise TokenRejected("missing_token")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise TokenRejected("missing_token")
    return value.strip()


def same_secret(given: str, expected: str) -> bool:
    """Constant-time comparison for shared secrets, such as an A2A callback token."""
    return bool(given) and bool(expected) and secrets.compare_digest(given.encode(), expected.encode())


def www_authenticate(error: TokenRejected, resource_metadata: str | None = None) -> str:
    """The challenge header for a 401 or 403 (RFC 6750 §3; RFC 9728 §5.1)."""
    parts = []
    if error.status == 403:
        parts.append('error="insufficient_scope"')
        if error.scope:
            parts.append(f'scope="{error.scope}"')
    elif error.reason not in ("missing_token", "missing_or_oversized_token"):
        parts.append('error="invalid_token"')
    if resource_metadata:
        parts.append(f'resource_metadata="{resource_metadata}"')
    return "Bearer" + (" " + ", ".join(parts) if parts else "")
