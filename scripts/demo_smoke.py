"""A happy-path check of a running public demo (SEC-18, LIVE-02; ADR-0087), local or hosted.

    uv run python scripts/demo_smoke.py http://127.0.0.1:58010
    uv run python scripts/demo_smoke.py https://<your-service>.onrender.com     (after the owner's deploy)

Signs in with the demo buttons, creates a case from a synthetic request, starts its investigation, waits for the
worker's result, and checks the demo label, the absence of password sign-in and of any admin route. Prints PASS/FAIL
lines; never prints a secret. Free hosting may take about a minute to wake: the first request waits for it.
"""

from __future__ import annotations

import re
import sys
import time

import httpx

LABEL = "Public demo: mock AI, synthetic data."


def local_client(base: str) -> httpx.Client:
    """The demo sets Secure cookies (as it must), and an HTTP client won't send those back over plain http. On a
    local http://127.0.0.1 run only, this carries them by hand. A hosted demo is HTTPS and needs none of it."""
    jar: dict[str, str] = {}
    client = httpx.Client(base_url=base, timeout=30, follow_redirects=False)

    def keep(response: httpx.Response) -> None:
        for header in response.headers.get_list("set-cookie"):
            name, _, rest = header.partition("=")
            value = rest.split(";", 1)[0]
            if "max-age=0" in header.lower() or not value.strip(chr(34)):
                jar.pop(name.strip(), None)
            else:
                jar[name.strip()] = value
        client.headers["cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())

    client.event_hooks["response"] = [keep]
    return client


def make_client(base: str) -> httpx.Client:
    if base.startswith(("http://127.0.0.1", "http://localhost")):
        return local_client(base)
    return httpx.Client(base_url=base, timeout=30, follow_redirects=False)


def main(base: str) -> int:
    results: list[bool] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  (' + detail + ')') if detail else ''}")

    deadline = time.monotonic() + 180  # a sleeping free service wakes in about a minute
    while True:
        try:
            if httpx.get(f"{base}/healthz", timeout=30).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            check("the demo answers /healthz", False, "no answer within 3 minutes")
            return 1
        time.sleep(5)
    check("the demo answers /healthz", True)
    with make_client(base) as client:
        page = client.get("/login")
        check("the sign-in page shows the demo label and buttons", LABEL in page.text and "demo-agent" in page.text)
        check("there is no password sign-in", 'name="password"' not in page.text)
        token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
        signed = client.post("/demo/sign-in", data={"role": "agent", "login_csrf": token.group(1) if token else ""})
        queue = client.get("/queue")
        check(
            "signing in as the demo agent opens the queue",
            signed.status_code == 303 and queue.status_code == 200 and LABEL in queue.text,
            f"sign-in {signed.status_code}, queue {queue.status_code}",
        )
        csrf = client.get("/api/v1/me").json()["csrf_token"]
        body = {
            "received_at_utc": "2026-06-18T13:44:00Z",
            "contact_channel": "email",
            "text": "Hi, my points for my stay last month never arrived. Member GR-00042.",
            "arm": "B",
            "form_member_number": "GR-00042",
        }
        created = client.post("/api/v1/cases", json=body, headers={"X-CSRF-Token": csrf})
        check("a case can be created", created.status_code == 201, f"HTTP {created.status_code}")
        if created.status_code == 201:
            case_id = created.json()["id"]
            started = client.post(f"/api/v1/cases/{case_id}/investigation", headers={"X-CSRF-Token": csrf})
            check("its investigation starts", started.status_code == 202, f"HTTP {started.status_code}")
            state, finished = "queued", time.monotonic() + 90
            while state in ("queued", "running") and time.monotonic() < finished:
                time.sleep(1)
                state = client.get(f"/api/v1/cases/{case_id}").json()["investigation"]
            check("the worker finishes it", state == "none", f"state {state}")
        check("no admin page is open to a demo user", client.get("/admin").status_code in (403, 404))
        supervisor = make_client(base)
        page = supervisor.get("/login")
        token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
        supervisor.post("/demo/sign-in", data={"role": "supervisor", "login_csrf": token.group(1) if token else ""})
        approvals = supervisor.get("/approvals")
        check("the demo supervisor opens the approvals queue", approvals.status_code == 200)
        supervisor.close()
    with make_client(base) as other:
        page = other.get("/login")
        token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
        admin = other.post("/demo/sign-in", data={"role": "admin", "login_csrf": token.group(1) if token else ""})
        check("there is no demo administrator", admin.status_code == 404)
    passed = sum(results)
    print(f"\n{passed} of {len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:58010"))
