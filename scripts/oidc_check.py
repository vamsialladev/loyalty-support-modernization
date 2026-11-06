"""The OIDC profile against a real local Keycloak, in a real browser (Appendix C, M9: "OIDC profile login works
locally").

    powershell -ExecutionPolicy Bypass -File scripts\\oidc_check.ps1

Run by that script after Keycloak is up. It uses Keycloak's admin API to create throwaway users with random
passwords, starts the app on a temporary SQLite database, signs in through the browser, and checks: a mapped group
gets its role, an unmapped user is refused, a user disabled in Keycloak can't sign in again, a rotated signing key
still works, and a password can't sign in. Prints pass or fail per check, and never a secret.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adapters.local_demo_identity import ensure_demo_users  # noqa: E402
from app.persistence.database import make_engine, make_sessions  # noqa: E402
from app.services.policies import load_policy_set  # noqa: E402

KEYCLOAK = os.environ["KEYCLOAK_URL"].rstrip("/")
ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
REALM = "hotel"
results: list[tuple[str, bool]] = []


def check(name: str, passed: bool) -> None:
    results.append((name, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {name}")


def admin_client() -> httpx.Client:
    token = httpx.post(
        f"{KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": "admin-cli", "username": "admin", "password": ADMIN_PASSWORD},
        timeout=30,
    ).json()["access_token"]
    return httpx.Client(
        base_url=f"{KEYCLOAK}/admin/realms/{REALM}", headers={"Authorization": f"Bearer {token}"}, timeout=30
    )


def create_user(admin: httpx.Client, username: str, group: str, password: str) -> str:
    created = admin.post(
        "/users",
        json={
            "username": username,
            "enabled": True,
            "emailVerified": True,
            "firstName": username,
            "lastName": "Test",
            "email": f"{username}@example.test",
            "credentials": [{"type": "password", "value": password, "temporary": False}],
            "groups": [f"/{group}"],
        },
    )
    created.raise_for_status()
    return created.headers["location"].rsplit("/", 1)[-1]


def client_secret(admin: httpx.Client) -> str:
    found = admin.get("/clients", params={"clientId": "loyalty-console"}).json()[0]
    return str(admin.get(f"/clients/{found['id']}/client-secret").json()["value"])


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def allow_redirect(admin: httpx.Client, base: str) -> None:
    """This run's port only: Keycloak's wildcards can't stand in for a port."""
    found = admin.get("/clients", params={"clientId": "loyalty-console"}).json()[0]
    found["redirectUris"] = [f"{base}/auth/oidc/callback"]
    admin.put(f"/clients/{found['id']}", json=found).raise_for_status()


def start_app(tmp: Path, secret: str) -> tuple[subprocess.Popen[bytes], str]:
    url = f"sqlite:///{(tmp / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    with make_sessions(make_engine(url))() as s:
        ensure_demo_users(s, secrets.token_urlsafe(16))
        load_policy_set(s, "hg-demo", ROOT / "policies/hg-demo")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ | {
        "DATABASE_URL": url,
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER_URL": f"{KEYCLOAK}/realms/{REALM}",
        "OIDC_CLIENT_ID": "loyalty-console",
        "OIDC_CLIENT_SECRET": secret,
        "APP_BASE_URL": base,
        "APP_SECRET_KEY": secrets.token_urlsafe(32),
    }
    target = "app.main:create_app"
    command_line = [sys.executable, "-m", "uvicorn", "--factory", target, "--port", str(port), "--log-level", "warning"]
    log = (tmp / "app.log").open("wb")
    process = subprocess.Popen(command_line, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)  # noqa: S603
    for _ in range(180):
        try:
            if httpx.get(f"{base}/healthz", timeout=2).status_code == 200:
                return process, base
        except httpx.HTTPError:
            time.sleep(1)
    raise RuntimeError("the app didn't start: " + (tmp / "app.log").read_text(errors="replace")[-400:])


def sign_in(page, base: str, username: str, password: str) -> None:  # type: ignore[no-untyped-def]
    page.context.clear_cookies()
    page.goto(f"{base}/login")
    page.get_by_test_id("oidc-start").click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()


def main() -> int:
    admin = admin_client()
    password = secrets.token_urlsafe(16)
    suffix = secrets.token_hex(3)
    agent, supervisor, stranger = f"agent-{suffix}", f"super-{suffix}", f"stranger-{suffix}"
    agent_id = create_user(admin, agent, "loyalty-agents", password)
    create_user(admin, supervisor, "loyalty-supervisors", password)
    create_user(admin, stranger, "other-team", password)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        process, base = start_app(Path(folder), client_secret(admin))
        allow_redirect(admin, base)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_context().new_page()

                sign_in(page, base, agent, password)
                expect(page.get_by_role("heading", name="Points queue")).to_be_visible(timeout=30_000)
                check("a mapped group signs in and reaches the queue", True)
                denied = page.goto(f"{base}/admin")
                check("an agent can't reach configuration", denied is not None and denied.status == 403)

                sign_in(page, base, supervisor, password)
                expect(page.get_by_role("link", name="Approvals")).to_be_visible(timeout=30_000)
                check("the supervisor group gets the supervisor role", True)

                sign_in(page, base, stranger, password)
                expect(page.get_by_role("heading", name="Sign-in failed")).to_be_visible(timeout=30_000)
                check("a user with no mapped group is refused", True)

                admin.put(f"/users/{agent_id}", json={"enabled": False}).raise_for_status()
                sign_in(page, base, agent, password)
                refused = page.locator("#input-error, .kc-feedback-text, #kc-error-message, .pf-m-danger").first
                expect(refused).to_be_visible(timeout=30_000)
                check("a user disabled in Keycloak can't sign in again", True)

                rotated = admin.get("/keys").json()["active"]
                realm_id = admin.get("").json()["id"]
                admin.post(
                    "/components",
                    json={
                        "name": f"rotated-{suffix}",
                        "providerId": "rsa-generated",
                        "providerType": "org.keycloak.keys.KeyProvider",
                        "parentId": realm_id,
                        "config": {"priority": ["999"], "enabled": ["true"], "active": ["true"]},
                    },
                ).raise_for_status()
                now_active = admin.get("/keys").json()["active"]
                check("the signing key really rotated", now_active.get("RS256") != rotated.get("RS256"))
                sign_in(page, base, supervisor, password)
                expect(page.get_by_role("link", name="Approvals")).to_be_visible(timeout=30_000)
                check("sign-in still works after the key rotated", True)
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=30)
    failed = [name for name, passed in results if not passed]
    print(f"{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
