"""Protocol access tokens from a real local Keycloak, checked by our verifier (RFC-0004; threat T20).

    powershell -ExecutionPolicy Bypass -File scripts\\protocol_token_check.ps1

Run by that script after a throwaway Keycloak is up. Creates two machine clients (one for the MCP server, one for the
A2A specialist), gets a client-credentials token for each, and checks with `protocols.common.tokens` against the real
discovery document and keys: each token is accepted by its own service and refused by the other; the customer and
scopes come from the token; a disabled client can't get a new token. Prints pass or fail per check, never a token or
a secret.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from protocol_clients import admin_client, client_credentials_token, create_machine_client, set_enabled  # noqa: E402

from protocols.common.tokens import IssuerKeys, ResourceServer, TokenRejected, TokenVerifier  # noqa: E402

KEYCLOAK = os.environ["KEYCLOAK_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
ISSUER = f"{KEYCLOAK}/realms/hotel"
MCP_AUDIENCE = "http://127.0.0.1:8030/mcp"
A2A_AUDIENCE = "http://127.0.0.1:8041"
results: list[tuple[str, bool]] = []


def check(name: str, passed: bool) -> None:
    results.append((name, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {name}")


def refused(verifier: TokenVerifier, token: str) -> str:
    try:
        verifier.verify(token)
    except TokenRejected as exc:
        return exc.reason
    return "accepted"


def main() -> int:
    admin = admin_client(KEYCLOAK, ADMIN_PASSWORD)
    mcp_client = create_machine_client(admin, "mcp-check-client", MCP_AUDIENCE, ("loyalty.read",), "hg-demo")
    a2a_client = create_machine_client(
        admin, "a2a-check-coordinator", A2A_AUDIENCE, ("reservation.evidence",), "cedarpoint"
    )
    keys = IssuerKeys(ISSUER, httpx.Client(timeout=10, follow_redirects=False))
    mcp = TokenVerifier(
        ResourceServer("mcp", ISSUER, MCP_AUDIENCE, frozenset({"loyalty.read", "loyalty.case.read"})), keys
    )
    a2a = TokenVerifier(
        ResourceServer("a2a-specialist", ISSUER, A2A_AUDIENCE, frozenset({"reservation.evidence"})), keys
    )

    mcp_token = client_credentials_token(KEYCLOAK, mcp_client).json()["access_token"]
    a2a_token = client_credentials_token(KEYCLOAK, a2a_client).json()["access_token"]

    caller = mcp.verify(mcp_token)
    check("MCP token accepted by the MCP verifier (real discovery and keys)", True)
    check("customer comes from the token: hg-demo", caller.customer_id == "hg-demo")
    check("scope comes from the token: loyalty.read", "loyalty.read" in caller.scopes)
    check("caller is a read-only service identity", caller.identity().role.value == "auditor")
    check("MCP token refused by the A2A specialist (wrong audience)", refused(a2a, mcp_token) == "wrong_audience")
    a2a_customer = a2a.verify(a2a_token).customer_id
    check("A2A token accepted by the specialist, customer cedarpoint", a2a_customer == "cedarpoint")
    check("A2A token refused by the MCP server (wrong audience)", refused(mcp, a2a_token) == "wrong_audience")
    tampered = mcp_token[:-6] + ("AAAAAA" if not mcp_token.endswith("AAAAAA") else "BBBBBB")
    check("a token with a changed signature is refused", refused(mcp, tampered) != "accepted")

    set_enabled(admin, mcp_client.client_id, False)
    check("a disabled client can't get a new token", client_credentials_token(KEYCLOAK, mcp_client).status_code != 200)
    still = refused(mcp, mcp_token)
    # Honest limit: a token issued before the client was disabled stays valid until it expires (no introspection).
    print(f"NOTE  a token issued before disabling the client: {still} (valid until it expires; short lifetimes matter)")

    failed = [name for name, ok in results if not ok]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
