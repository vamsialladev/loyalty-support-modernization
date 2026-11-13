"""Protocol callers are checked as an OAuth resource server would check them (spec G.3, G.13; RFC-0004; threat T20).

Each case is one way a token can be wrong. Every one is refused, with the status the standards ask for: 401 for a
missing, bad or expired token, 403 for a good token without the scope.
"""

from __future__ import annotations

import httpx
import pytest

from app.domain.roles import Role
from app.services.instrumentation import actor_kind
from protocols.common.tokens import (
    IssuerKeys,
    TokenRejected,
    bearer,
    require_scope,
    same_secret,
    www_authenticate,
)
from tests.protocol_tokens import ISSUER, MCP_AUDIENCE, TestIssuer, verifier_for


@pytest.fixture(scope="module")
def idp() -> TestIssuer:
    return TestIssuer()


def test_a_good_token_becomes_a_read_only_caller_in_the_tokens_customer(idp: TestIssuer) -> None:
    caller = verifier_for(idp).verify(idp.token(customer_id="cedarpoint"))
    who = caller.identity()
    assert caller.customer_id == "cedarpoint" and caller.client_id == "claude-desktop"
    assert who.role is Role.AUDITOR and who.customer_id == "cedarpoint"
    assert who.username == "svc-mcp-claude-desktop" and actor_kind(who) == "service"


@pytest.mark.parametrize(
    ("make", "reason"),
    [
        (lambda i: i.token(expires_in=-120), "expired"),
        (lambda i: i.token(audience="http://127.0.0.1:8040/a2a"), "wrong_audience"),
        (lambda i: i.token(issuer="http://evil.example/realms/hotel"), "wrong_issuer"),
        (lambda i: i.token(customer_id=None), "no_customer_claim"),
        (lambda i: i.token(typ="ID"), "not_an_access_token"),
        (lambda i: i.token(algorithm="none"), "algorithm_not_allowed"),
        (lambda i: i.token(algorithm="HS256"), "algorithm_not_allowed"),
        (lambda i: i.token(kid="someone-elses-key"), "unknown_signing_key"),
        (lambda i: i.token(drop=("exp",)), "MissingRequiredClaimError"),
        (lambda i: i.token(drop=("sub",)), "MissingRequiredClaimError"),
        (lambda i: "not.a.jwt", "malformed_token"),
        (lambda i: "", "missing_or_oversized_token"),
        (lambda i: "x" * 9000, "missing_or_oversized_token"),
    ],
)
def test_every_bad_token_is_refused_with_401(idp: TestIssuer, make, reason: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TokenRejected) as refused:
        verifier_for(idp).verify(make(idp))
    assert refused.value.reason == reason and refused.value.status == 401


def test_a_token_signed_by_another_key_with_our_key_id_is_refused(idp: TestIssuer) -> None:
    impostor = TestIssuer(kid=idp.kid)  # same key ID, different key
    with pytest.raises(TokenRejected) as refused:
        verifier_for(idp).verify(impostor.token())
    assert refused.value.reason == "InvalidSignatureError"


def test_a_token_for_another_service_is_refused_even_with_the_right_scope(idp: TestIssuer) -> None:
    """No token passthrough: the A2A specialist's token doesn't open the MCP server, and the reverse."""
    a2a_token = idp.token(audience="http://127.0.0.1:8041", scope="loyalty.read reservation.evidence")
    with pytest.raises(TokenRejected) as refused:
        verifier_for(idp).verify(a2a_token)
    assert refused.value.reason == "wrong_audience"
    a2a = verifier_for(idp, name="a2a-specialist", audience="http://127.0.0.1:8041", scopes=("reservation.evidence",))
    with pytest.raises(TokenRejected):
        a2a.verify(idp.token())


def test_an_audience_list_is_accepted_when_it_includes_this_service(idp: TestIssuer) -> None:
    assert verifier_for(idp).verify(idp.token(audience=["account", MCP_AUDIENCE])).customer_id == "hg-demo"


def test_a_token_without_any_scope_for_this_service_is_403(idp: TestIssuer) -> None:
    with pytest.raises(TokenRejected) as refused:
        verifier_for(idp).verify(idp.token(scope="openid profile"))
    assert refused.value.status == 403


def test_insufficient_scope_names_the_scope_that_would_work(idp: TestIssuer) -> None:
    caller = verifier_for(idp).verify(idp.token(scope="loyalty.read"))
    require_scope(caller, "loyalty.read")
    with pytest.raises(TokenRejected) as refused:
        require_scope(caller, "loyalty.case.read")
    header = www_authenticate(refused.value, "http://127.0.0.1:8030/.well-known/oauth-protected-resource/mcp")
    assert refused.value.status == 403
    assert header == (
        'Bearer error="insufficient_scope", scope="loyalty.case.read", '
        'resource_metadata="http://127.0.0.1:8030/.well-known/oauth-protected-resource/mcp"'
    )


def test_challenge_headers_for_missing_and_invalid_tokens() -> None:
    assert www_authenticate(TokenRejected("missing_token"), "https://x/m") == 'Bearer resource_metadata="https://x/m"'
    assert www_authenticate(TokenRejected("expired")) == 'Bearer error="invalid_token"'


@pytest.mark.parametrize("header", [None, "", "Basic dXNlcjpwYXNz", "Bearer", "Bearer   ", "Token abc"])
def test_only_a_bearer_header_carries_a_token(header: str | None) -> None:
    with pytest.raises(TokenRejected):
        bearer(header)


def test_bearer_reads_the_token() -> None:
    assert bearer("Bearer abc.def.ghi") == "abc.def.ghi"
    assert bearer("bearer abc") == "abc"


def test_shared_secrets_compare_in_constant_time_and_never_match_empty() -> None:
    assert same_secret("s3cret-token", "s3cret-token")
    assert not same_secret("s3cret-token", "s3cret-tokem")
    assert not same_secret("", "")


def _issuer_keys(idp: TestIssuer, discovery_issuer: str = ISSUER, calls: list[str] | None = None) -> IssuerKeys:
    seen = calls if calls is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"issuer": discovery_issuer, "jwks_uri": f"{ISSUER}/certs"})
        return httpx.Response(200, json=idp.jwks())

    return IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)))


def test_keys_come_from_the_issuers_discovery_and_an_unknown_key_refetches_once(idp: TestIssuer) -> None:
    calls: list[str] = []
    keys = _issuer_keys(idp, calls=calls)
    assert keys.key_for(idp.kid).key_id == idp.kid
    with pytest.raises(TokenRejected):
        keys.key_for("rotated-away")
    assert calls.count("/realms/hotel/certs") == 2  # first fetch, then one refetch for the unknown key
    assert calls.count("/realms/hotel/.well-known/openid-configuration") == 1


def test_a_discovery_document_naming_another_issuer_is_refused(idp: TestIssuer) -> None:
    with pytest.raises(TokenRejected) as refused:
        _issuer_keys(idp, discovery_issuer="http://evil.example/realms/hotel").key_for(idp.kid)
    assert refused.value.reason == "issuer_mismatch_in_discovery"


INTERNAL = "http://keycloak:8080/realms/hotel"  # how a container reaches the same provider (TD-52, ADR-0073)


def test_a_container_fetches_keys_by_service_name_but_still_needs_the_public_issuer(idp: TestIssuer) -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": f"{INTERNAL}/certs"})
        return httpx.Response(200, json=idp.jwks())

    keys = IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)), fetch_url=INTERNAL)
    assert keys.key_for(idp.kid).key_id == idp.kid
    assert set(hosts) == {"keycloak"}  # never the public host, which a container can't reach


def test_with_a_fetch_url_a_document_naming_another_issuer_is_still_refused(idp: TestIssuer) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"issuer": INTERNAL, "jwks_uri": f"{INTERNAL}/certs"})

    keys = IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)), fetch_url=INTERNAL)
    with pytest.raises(TokenRejected) as refused:
        keys.key_for(idp.kid)
    assert refused.value.reason == "issuer_mismatch_in_discovery" and refused.value.status == 503


def test_with_a_fetch_url_keys_on_the_public_or_any_other_host_are_not_fetched(idp: TestIssuer) -> None:
    for jwks_uri in (f"{ISSUER}/certs", "http://169.254.169.254/latest/meta-data"):

        def handler(request: httpx.Request, uri: str = jwks_uri) -> httpx.Response:
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": uri})

        keys = IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)), fetch_url=INTERNAL)
        with pytest.raises(Exception, match="isn't a configured destination"):
            keys.key_for(idp.kid)


def test_an_unreachable_provider_is_a_503_not_a_crash(idp: TestIssuer) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    keys = IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)), fetch_url=INTERNAL)
    with pytest.raises(TokenRejected) as refused:
        keys.key_for(idp.kid)
    assert (refused.value.reason, refused.value.status) == ("issuer_unreachable", 503)


def test_settings_fall_back_from_the_protocol_fetch_url_to_the_oidc_one(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import AppSettings

    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
    monkeypatch.setenv("OIDC_FETCH_URL", INTERNAL)
    monkeypatch.delenv("PROTOCOL_TOKEN_ISSUER", raising=False)
    monkeypatch.delenv("PROTOCOL_TOKEN_FETCH_URL", raising=False)
    assert AppSettings.from_env().protocol_token_fetch_url == INTERNAL
    monkeypatch.setenv("PROTOCOL_TOKEN_ISSUER", "http://other-idp/realms/x")  # another issuer: don't borrow its URL
    assert AppSettings.from_env().protocol_token_fetch_url == ""


def test_keys_are_never_fetched_from_another_host(idp: TestIssuer) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": "http://169.254.169.254/latest/meta-data"})

    keys = IssuerKeys(ISSUER, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(Exception, match="isn't a configured destination"):
        keys.key_for(idp.kid)
