"""One identity provider's discovery document and signing keys, shared by console sign-in (`oidc_identity`) and the
protocol token check (`protocols.common.tokens`). Before Milestone 12 each had its own copy (TD-51).

`issuer` is the public issuer: the discovery document's `issuer` and every token's `iss` must equal it.
`fetch_url` is where this process reaches the provider, when that differs from the issuer. In Compose, a container
reaches Keycloak at `http://keycloak:8080/realms/hotel` while tokens name `http://127.0.0.1:8090/realms/hotel`
(TD-52, ADR-0073). Documents and keys are fetched only from that one base, so a discovery document can't send us
anywhere else (SSRF guard, `app.outbound.check_url`). An unknown key ID triggers one refetch, which is how key
rotation works; never more than one per call.

Errors are `DiscoveryFailed` with a `kind`; each caller maps it to its own error and wording.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from jwt import PyJWK, PyJWKSet

from app.outbound import check_url

MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 10.0

FailureKind = Literal["unreachable", "bad_response", "issuer_mismatch", "unknown_key"]


class DiscoveryFailed(Exception):
    def __init__(self, kind: FailureKind, status_code: int | None = None) -> None:
        super().__init__(kind if status_code is None else f"{kind}:{status_code}")
        self.kind: FailureKind = kind
        self.status_code = status_code


@dataclass
class ProviderMetadata:
    issuer: str
    http: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False))
    fetch_url: str = ""
    _document: dict[str, Any] | None = None
    _keys: PyJWKSet | None = None

    @property
    def base(self) -> str:
        """Where documents and keys are fetched from: the fetch URL if set, else the issuer."""
        return (self.fetch_url or self.issuer).rstrip("/")

    def get_json(self, url: str) -> dict[str, Any]:
        check_url(url, (self.base,))
        try:
            response = self.http.get(url)
        except httpx.HTTPError as exc:
            raise DiscoveryFailed("unreachable") from exc
        if response.status_code != 200 or len(response.content) > MAX_RESPONSE_BYTES:
            raise DiscoveryFailed("bad_response", response.status_code)
        data: dict[str, Any] = response.json()
        return data

    def document(self) -> dict[str, Any]:
        if self._document is None:
            found = self.get_json(self.base + "/.well-known/openid-configuration")
            if found.get("issuer") != self.issuer:
                raise DiscoveryFailed("issuer_mismatch")
            self._document = found
        return self._document

    def key_for(self, kid: str | None) -> PyJWK:
        for refetch in (False, True):
            if self._keys is None or refetch:
                self._keys = PyJWKSet.from_dict(self.get_json(str(self.document()["jwks_uri"])))
            for key in self._keys.keys:
                if key.key_id == kid:
                    return key
        raise DiscoveryFailed("unknown_key")
