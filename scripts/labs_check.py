"""The protocol services running in Compose (`--profile labs`) with one public issuer (TD-52, ADR-0073).

    powershell -ExecutionPolicy Bypass -File scripts\\labs_check.ps1

Run by that script after the throwaway labs stack is up. It proves what TD-52 was about: a token requested from the
host and a token requested from inside a container carry the same issuer, and the services in containers accept
both, because they fetch keys from http://keycloak:8080 while checking `iss` against the public issuer. Also checks
TD-53 live (a wrong Content-Type gets 415). Prints pass or fail per check, never a token or a secret.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from protocol_clients import admin_client, client_credentials_token, create_machine_client  # noqa: E402

KEYCLOAK = os.environ["KEYCLOAK_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
MCP_URL = os.environ["LABS_MCP_URL"]  # http://127.0.0.1:<port>/mcp, also the MCP audience
A2A_URL = os.environ["LABS_A2A_URL"]  # http://127.0.0.1:<port>, also the A2A audience
MCP_CONTAINER = os.environ["LABS_MCP_CONTAINER"]
PUBLIC_ISSUER = f"{KEYCLOAK}/realms/hotel"
DOCKER = shutil.which("docker") or "docker"
results: list[tuple[str, bool]] = []

# Runs inside the MCP container: a client-credentials token from Keycloak by its service name. Prints only `iss`;
# the token itself goes to a file in the container's /tmp, which the host reads back with `docker exec cat`.
IN_CONTAINER = """
import base64, json, os, httpx
r = httpx.post("http://keycloak:8080/realms/hotel/protocol/openid-connect/token", timeout=10, data={
    "grant_type": "client_credentials", "client_id": os.environ["LABS_CLIENT_ID"],
    "client_secret": os.environ["LABS_CLIENT_SECRET"]})
r.raise_for_status()
token = r.json()["access_token"]
open("/tmp/labs-token", "w").write(token)
part = token.split(".")[1]
print(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["iss"])
"""


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {name}{f'  ({detail})' if detail else ''}")


def issuer_of(token: str) -> str:
    part = token.split(".")[1]
    return str(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["iss"])


def mcp_initialize(token: str | None) -> int:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "labs-check", "version": "1"},
        },
    }
    return httpx.post(MCP_URL, json=body, headers=headers, timeout=20).status_code


def main() -> int:
    admin = admin_client(KEYCLOAK, ADMIN_PASSWORD)
    mcp_client = create_machine_client(admin, "labs-check-mcp", MCP_URL, ("loyalty.read",), "hg-demo")
    a2a_client = create_machine_client(admin, "labs-check-a2a", A2A_URL, ("reservation.evidence",), "hg-demo")

    discovery = httpx.get(f"{PUBLIC_ISSUER}/.well-known/openid-configuration", timeout=10).json()
    check("discovery from the host names the public issuer", discovery["issuer"] == PUBLIC_ISSUER)

    host_token = client_credentials_token(KEYCLOAK, mcp_client).json()["access_token"]
    check("a token requested from the host names the public issuer", issuer_of(host_token) == PUBLIC_ISSUER)

    env = {**os.environ, "LABS_CLIENT_ID": mcp_client.client_id, "LABS_CLIENT_SECRET": mcp_client.secret}
    inside = subprocess.run(  # noqa: S603 - fixed docker command; the secret travels in the environment, not argv
        [
            DOCKER,
            "exec",
            "-e",
            "LABS_CLIENT_ID",
            "-e",
            "LABS_CLIENT_SECRET",
            MCP_CONTAINER,
            "python",
            "-c",
            IN_CONTAINER,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    container_issuer = inside.stdout.strip()
    check(
        "a token requested inside a container (http://keycloak:8080) names the same public issuer",
        inside.returncode == 0 and container_issuer == PUBLIC_ISSUER,
        container_issuer or inside.stderr.strip()[-200:],
    )
    container_token = subprocess.run(  # noqa: S603
        [DOCKER, "exec", MCP_CONTAINER, "cat", "/tmp/labs-token"],  # noqa: S108 - a path inside the container
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout.strip()

    check("MCP in a container refuses a call with no token", mcp_initialize(None) == 401)
    status = mcp_initialize(host_token)
    check("MCP in a container accepts the host's token (keys fetched by service name)", status == 200, str(status))
    status = mcp_initialize(container_token) if container_token else 0
    check("MCP in a container accepts the container's token", status == 200, str(status))

    card = httpx.get(f"{A2A_URL}/.well-known/agent-card.json", timeout=10)
    check("A2A specialist's card is public", card.status_code == 200)
    a2a_token = client_credentials_token(KEYCLOAK, a2a_client).json()["access_token"]
    send = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {}}
    auth = {"Authorization": f"Bearer {a2a_token}", "A2A-Version": "1.0"}
    reply = httpx.post(A2A_URL, json=send, headers=auth, timeout=20)
    check("A2A specialist in a container accepts its own token", reply.status_code == 200, str(reply.status_code))
    check(
        "A2A specialist refuses the MCP token (wrong audience)",
        httpx.post(
            A2A_URL, json=send, headers={**auth, "Authorization": f"Bearer {host_token}"}, timeout=20
        ).status_code
        == 401,
    )
    wrong = httpx.post(A2A_URL, content=json.dumps(send), headers={**auth, "Content-Type": "text/plain"}, timeout=20)
    check("A2A specialist refuses a body that isn't JSON (TD-53)", wrong.status_code == 415, str(wrong.status_code))

    failed = [name for name, ok in results if not ok]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
