"""OIDC sign-in against a fake provider, with real keys and real token checks (spec C.4; SEC-08, ENT-25).

No network: `httpx.MockTransport` plays the provider. The real Keycloak run is `scripts\\oidc_check.ps1`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import select

from app.adapters.oidc_identity import OidcClient, OidcError, OidcSettings, provision, role_from_claims
from app.main import create_app
from app.persistence.models import SystemEvent, User
from app.settings import AppSettings
from tests.arm_a import ArmA, make_arm_a

ISSUER = "http://idp.test/realms/hotel"
CLIENT = "loyalty-console"
GROUPS = {"loyalty-agents": "agent", "loyalty-supervisors": "supervisor", "loyalty-admins": "administrator"}


def rsa_key() -> Any:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY_1, KEY_2, OTHER_KEY = rsa_key(), rsa_key(), rsa_key()


def jwk(key: Any, kid: str) -> dict[str, Any]:
    return {**json.loads(RSAAlgorithm.to_jwk(key.public_key())), "kid": kid, "use": "sig", "alg": "RS256"}


def token(nonce: str = "n", key: Any = KEY_1, kid: str = "k1", alg: str = "RS256", **over: Any) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT,
        "sub": "user-1",
        "iat": now,
        "exp": now + 300,
        "nonce": nonce,
        "preferred_username": "ana.idp",
        "name": "Ana From IdP",
        "groups": ["/loyalty-agents"],
    }
    claims.update(over)
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


class Provider:
    """A fake provider. `keys` can change, which is how rotation looks from the outside."""

    def __init__(self) -> None:
        self.keys = [jwk(KEY_1, "k1")]
        self.issued: str = ""
        self.token_requests: list[dict[str, list[str]]] = []
        self.jwks_fetches = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/auth",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/certs",
                },
            )
        if path.endswith("/certs"):
            self.jwks_fetches += 1
            return httpx.Response(200, json={"keys": self.keys})
        if path.endswith("/token"):
            self.token_requests.append(parse_qs(request.content.decode()))
            return httpx.Response(200, json={"id_token": self.issued})
        return httpx.Response(404)


def client_for(provider: Provider) -> OidcClient:
    return OidcClient(
        OidcSettings(ISSUER, CLIENT, "a-client-secret-for-tests", "http://app.test/auth/oidc/callback", GROUPS),
        httpx.Client(transport=httpx.MockTransport(provider.handler)),
    )


def test_a_good_token_passes() -> None:
    claims = client_for(Provider()).verify(token(), "n")
    assert claims["sub"] == "user-1"


@pytest.mark.parametrize(
    ("bad", "kwargs"),
    [
        ("wrong issuer", {"iss": "http://evil.test"}),
        ("wrong audience", {"aud": "another-app"}),
        ("expired", {"exp": 1000}),
    ],
)
def test_bad_claims_are_refused(bad: str, kwargs: dict[str, Any]) -> None:
    with pytest.raises(OidcError):
        client_for(Provider()).verify(token(**kwargs), "n")


def test_a_wrong_signature_is_refused() -> None:
    with pytest.raises(OidcError, match="InvalidSignature"):
        client_for(Provider()).verify(token(key=OTHER_KEY), "n")


def test_a_wrong_nonce_is_refused() -> None:
    with pytest.raises(OidcError, match="nonce_mismatch"):
        client_for(Provider()).verify(token(nonce="other"), "n")


def test_alg_none_and_symmetric_algorithms_are_refused() -> None:
    client = client_for(Provider())
    unsigned = jwt.encode({"iss": ISSUER, "aud": CLIENT, "sub": "x"}, key="", algorithm="none", headers={"kid": "k1"})
    with pytest.raises(OidcError, match="algorithm_not_allowed"):
        client.verify(unsigned, "n")
    forged = jwt.encode(
        {"iss": ISSUER}, "a-shared-secret-of-at-least-32-bytes!", algorithm="HS256", headers={"kid": "k1"}
    )
    with pytest.raises(OidcError, match="algorithm_not_allowed"):
        client.verify(forged, "n")


def test_a_malformed_token_is_refused() -> None:
    with pytest.raises(OidcError, match="malformed_token"):
        client_for(Provider()).verify("not-a-token", "n")


def test_key_rotation_refetches_once_and_an_unknown_key_is_refused() -> None:
    provider = Provider()
    client = client_for(provider)
    assert client.verify(token(), "n")
    assert provider.jwks_fetches == 1
    provider.keys = [jwk(KEY_2, "k2")]
    assert client.verify(token(key=KEY_2, kid="k2"), "n")
    assert provider.jwks_fetches == 2
    with pytest.raises(OidcError, match="unknown_signing_key"):
        client.verify(token(key=KEY_1, kid="k1"), "n")


def test_discovery_must_name_the_same_issuer() -> None:
    def lying(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"issuer": "http://evil.test"})

    client = OidcClient(
        OidcSettings(ISSUER, CLIENT, "s", "http://app.test/cb", GROUPS),
        httpx.Client(transport=httpx.MockTransport(lying)),
    )
    with pytest.raises(OidcError, match="issuer_mismatch"):
        client.discovery()


def test_the_start_uses_pkce_state_and_nonce() -> None:
    begun = client_for(Provider()).start()
    query = parse_qs(urlsplit(begun.url).query)
    assert query["code_challenge_method"] == ["S256"] and query["code_challenge"][0] != begun.verifier
    assert query["state"] == [begun.state] and query["nonce"] == [begun.nonce]
    assert len(begun.state) > 30 and begun.state != begun.nonce


def _settings() -> OidcSettings:
    return OidcSettings(ISSUER, CLIENT, "s", "http://app.test/cb", GROUPS)


@pytest.mark.parametrize(
    ("groups", "role"),
    [
        (["/loyalty-agents"], "agent"),
        (["loyalty-supervisors", "loyalty-agents"], "supervisor"),
        (["/loyalty-admins"], "administrator"),
    ],
)
def test_groups_map_to_roles(groups: list[str], role: str) -> None:
    assert role_from_claims({"groups": groups}, _settings()).value == role


@pytest.mark.parametrize("groups", [[], None, ["other-team"], "loyalty-admins"])
def test_no_mapped_group_means_no_access(groups: Any) -> None:
    with pytest.raises(OidcError, match="no_mapped_group"):
        role_from_claims({"groups": groups}, _settings())


# ---------- through the console ----------


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def console(arm: ArmA, provider: Provider) -> TestClient:
    settings = AppSettings(
        database_url=arm.app_url,
        sim_clock=True,
        auth_mode="oidc",
        oidc_issuer_url=ISSUER,
        oidc_client_id=CLIENT,
        oidc_client_secret="a-client-secret-for-tests",
        app_base_url="http://testserver",
    )
    app: FastAPI = create_app(
        settings, arm.factory(), oidc_http=httpx.Client(transport=httpx.MockTransport(provider.handler))
    )
    return TestClient(app, follow_redirects=False)


def sign_in(client: TestClient, provider: Provider, **claims: Any) -> Any:
    start = client.get("/auth/oidc/start")
    assert start.status_code == 303
    query = parse_qs(urlsplit(start.headers["location"]).query)
    provider.issued = token(nonce=query["nonce"][0], **claims)
    return client.get("/auth/oidc/callback", params={"code": "abc", "state": query["state"][0]})


def test_a_whole_sign_in_makes_a_session_with_the_mapped_role(arm: ArmA) -> None:
    provider = Provider()
    client = console(arm, provider)
    page = client.get("/login")
    assert "oidc-start" in page.text and 'name="password"' not in page.text
    done = sign_in(client, provider)
    assert done.status_code == 200 and "url=/queue" in done.text
    assert client.get("/queue").status_code == 200
    assert provider.token_requests[0]["code_verifier"]
    with arm.sessions() as s:
        user = s.scalars(select(User).where(User.username == "ana.idp")).one()
        assert user.role == "agent" and user.external_id == f"{ISSUER}|user-1"


def test_the_provider_changes_a_role_on_the_next_sign_in_and_its_audited(arm: ArmA) -> None:
    provider = Provider()
    client = console(arm, provider)
    sign_in(client, provider)
    sign_in(client, provider, groups=["/loyalty-supervisors"])
    with arm.sessions() as s:
        assert s.scalars(select(User).where(User.username == "ana.idp")).one().role == "supervisor"
        assert s.scalars(select(SystemEvent).where(SystemEvent.action == "role_changed_by_provider")).first()


def test_a_forged_state_is_refused(arm: ArmA) -> None:
    provider = Provider()
    client = console(arm, provider)
    client.get("/auth/oidc/start")
    provider.issued = token()
    done = client.get("/auth/oidc/callback", params={"code": "abc", "state": "forged"})
    assert done.status_code == 401 and "lsm_session" not in client.cookies


def test_a_callback_with_no_start_is_refused(arm: ArmA) -> None:
    done = console(arm, Provider()).get("/auth/oidc/callback", params={"code": "abc", "state": "x"})
    assert done.status_code == 401


def test_no_mapped_group_cant_sign_in_and_its_audited(arm: ArmA) -> None:
    provider = Provider()
    client = console(arm, provider)
    done = sign_in(client, provider, groups=["other-team"])
    assert done.status_code == 401 and "no_mapped_group" not in done.text
    with arm.sessions() as s:
        assert s.scalars(select(User).where(User.username == "ana.idp")).first() is None
        event = s.scalars(select(SystemEvent).where(SystemEvent.action == "sign_in_failed")).one()
        assert event.detail["reason"] == "no_mapped_group"


def test_an_account_deactivated_here_stays_out_whatever_the_provider_says(arm: ArmA) -> None:
    """ENT-24: deprovisioning. The provider disables the user, or an administrator does it here."""
    provider = Provider()
    client = console(arm, provider)
    sign_in(client, provider)
    with arm.sessions() as s:
        user = s.scalars(select(User).where(User.username == "ana.idp")).one()
        user.active = False
        s.commit()
    assert client.get("/queue").status_code == 303  # the running session ended too
    assert sign_in(client, provider).status_code == 401


def test_a_password_cant_sign_in_on_this_deployment(arm: ArmA) -> None:
    client = console(arm, Provider())
    client.get("/login")
    token_value = client.cookies.get("lsm_login_csrf")
    done = client.post("/login", data={"username": "agent.ana", "password": arm.password, "login_csrf": token_value})
    assert done.status_code == 409 and "lsm_session" not in client.cookies


def test_an_oidc_account_has_no_usable_password(arm: ArmA) -> None:
    from app.adapters.local_demo_identity import LocalDemoIdentity

    with arm.sessions() as s:
        claims = {"iss": ISSUER, "sub": "user-9", "preferred_username": "no.pass", "groups": ["/loyalty-agents"]}
        provision(s, claims, _settings())
    assert LocalDemoIdentity(arm.sessions).authenticate("no.pass", "!oidc-no-password") is None


def test_a_username_clash_with_a_local_account_doesnt_take_it_over(arm: ArmA) -> None:
    with arm.sessions() as s:
        claims = {"iss": ISSUER, "sub": "user-7", "preferred_username": "admin.ada", "groups": ["/loyalty-agents"]}
        who = provision(s, claims, _settings())
        assert who.username != "admin.ada" and who.role.value == "agent"
        admin = s.scalars(select(User).where(User.username == "admin.ada")).one()
        assert admin.role == "administrator" and admin.external_id is None
