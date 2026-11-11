"""A stand-in identity provider for offline protocol tests: an RSA key made per test run, its JWKS, and tokens shaped
like Keycloak's client-credentials access tokens. The real Keycloak run is recorded in `security/evidence/`."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from protocols.common.tokens import ResourceServer, StaticKeys, TokenVerifier

ISSUER = "http://127.0.0.1:8090/realms/hotel"
MCP_AUDIENCE = "http://127.0.0.1:8030/mcp"


@dataclass
class TestIssuer:
    __test__ = False  # not a test class, despite the name

    kid: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    key: Any = field(default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048))

    def jwks(self) -> dict[str, Any]:
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        public.update(kid=self.kid, use="sig", alg="RS256")
        return {"keys": [public]}

    def token(
        self,
        *,
        audience: str | list[str] = MCP_AUDIENCE,
        scope: str = "loyalty.read",
        customer_id: str | None = "hg-demo",
        issuer: str = ISSUER,
        client_id: str = "claude-desktop",
        expires_in: int = 300,
        issued_ago: int = 0,
        typ: str | None = "Bearer",
        kid: str | None = None,
        algorithm: str = "RS256",
        drop: tuple[str, ...] = (),
        **extra: Any,
    ) -> str:
        now = int(time.time()) - issued_ago
        claims: dict[str, Any] = {
            "iss": issuer,
            "aud": audience,
            "sub": f"service-account-{client_id}",
            "azp": client_id,
            "iat": now,
            "exp": now + expires_in,
            "jti": uuid.uuid4().hex,
            "scope": scope,
            "typ": typ,
            "customer_id": customer_id,
            **extra,
        }
        claims = {k: v for k, v in claims.items() if v is not None and k not in drop}
        if algorithm == "none":
            return jwt.encode(claims, None, algorithm="none")
        if algorithm == "HS256":
            return jwt.encode(claims, "a-shared-secret-of-thirty-two-chars!", algorithm="HS256")
        return jwt.encode(claims, self.key, algorithm=algorithm, headers={"kid": kid or self.kid})


def verifier_for(
    issuer: TestIssuer, *, name: str = "mcp", audience: str = MCP_AUDIENCE, scopes: tuple[str, ...] = ()
) -> TokenVerifier:
    server = ResourceServer(name, ISSUER, audience, frozenset(scopes or ("loyalty.read", "loyalty.case.read")))
    return TokenVerifier(server, StaticKeys(issuer.jwks()))
