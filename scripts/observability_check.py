"""The checks behind `scripts\\observability_check.ps1` (OPS-04, ADR-0080). Run by that script, against its stack.

1. Make traffic: sign in, open pages, one failed sign-in, one denied page.
2. Prometheus has the worker's gauges and the app's HTTP server metrics.
3. Tempo has a trace from the app, and the worker's job polling makes no traces of its own.
4. Grafana loaded the dashboards and the alert rules, and every rule names a runbook that exists in `docs/runbooks/`.
5. No series label and no stored trace attribute holds a planted email or the demo password.

Prints one PASS / FAIL line per check, never a secret value.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
APP = os.environ["OBS_APP_URL"]
GRAFANA = os.environ["OBS_GRAFANA_URL"]
PROMETHEUS = os.environ["OBS_PROMETHEUS_URL"]
TEMPO = os.environ["OBS_TEMPO_URL"]
PASSWORD = os.environ["OBS_DEMO_PASSWORD"]
PLANTED_EMAIL = "planted.observer@mail.test"
GAUGES = (
    "loyalty_jobs_queued",
    "loyalty_jobs_oldest_age_seconds",
    "loyalty_jobs_dead",
    "loyalty_ai_spend_USD",
    "loyalty_ai_cap_USD",
    "loyalty_app_up",
)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  (' + detail + ')') if detail else ''}")
    return ok


def sign_in(client: httpx.Client, username: str, password: str) -> int:
    page = client.get("/login")
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    form = {"username": username, "password": password, "login_csrf": token.group(1) if token else ""}
    return client.post("/login", data=form).status_code


def traffic() -> None:
    with httpx.Client(base_url=APP, timeout=20, follow_redirects=False) as client:
        sign_in(client, PLANTED_EMAIL, "not-the-password")  # a failed sign-in, with an email typed as the username
    with httpx.Client(base_url=APP, timeout=20, follow_redirects=True) as agent:
        check("demo agent signs in", sign_in(agent, "agent.ana", PASSWORD) == 200)
        for _ in range(3):
            agent.get("/queue")
        check("an agent is refused the metrics page", agent.get("/metrics").status_code == 403)
        agent.get(f"/queue?q={PLANTED_EMAIL}")
    with httpx.Client(base_url=APP, timeout=20, follow_redirects=True) as supervisor:
        sign_in(supervisor, "supervisor.sam", PASSWORD)
        supervisor.get("/metrics")


def prom(query: str) -> list[dict[str, Any]]:
    resp = httpx.get(f"{PROMETHEUS}/api/v1/query", params={"query": query}, timeout=20)
    resp.raise_for_status()
    return list(resp.json()["data"]["result"])


def metric_names() -> list[str]:
    resp = httpx.get(f"{PROMETHEUS}/api/v1/label/__name__/values", timeout=20)
    resp.raise_for_status()
    return list(resp.json()["data"])


def wait_for(names: tuple[str, ...], seconds: int = 120) -> list[str]:
    found: list[str] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = metric_names()
        if all(n in found for n in names):  # exact names: a unit suffix must not slip past (_ratio, ADR-0080)
            break
        time.sleep(5)
    return found


def grafana(path: str, **params: Any) -> Any:
    resp = httpx.get(f"{GRAFANA}{path}", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def plant_dead_job() -> None:
    """One dead job of a kind no handler knows, through the app's own role, so 'Jobs giving up' must fire."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sys.path.insert(0, str(ROOT))  # run as a script from scripts/, so the repository root isn't on the path
    from app.persistence.models import Job

    with Session(create_engine(os.environ["OBS_DATABASE_URL"])) as s:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        s.add(
            Job(
                kind="observability_check_planted",
                dedupe_key="observability_check_planted",
                payload={},
                status="dead",
                attempts=1,
                max_attempts=1,
                run_after_utc=stamp,
                last_error="planted",
                created_at_utc=stamp,
                finished_at_utc=stamp,
            )
        )
        s.commit()


def main() -> int:
    plant_dead_job()
    traffic()
    names = wait_for((*GAUGES, "http_server_duration_milliseconds_count"))
    loyalty = sorted(n for n in names if n.startswith("loyalty_"))
    http = sorted(n for n in names if n.startswith("http_server"))
    print("metric names: " + ", ".join(loyalty + http))
    for gauge in GAUGES:
        check(f"Prometheus has {gauge}", gauge in names)
    check("Prometheus has the app's HTTP server metrics", bool(http), ", ".join(http[:3]))
    by_action: dict[str, float] = {}
    deadline = time.monotonic() + 60  # the gauges export every few seconds; the first export may predate the traffic
    while time.monotonic() < deadline:
        refusals = prom('sum by (action) ({__name__=~"loyalty_security_refusals.*"})')
        by_action = {r["metric"].get("action"): float(r["value"][1]) for r in refusals}
        if by_action.get("sign_in_failed", 0) >= 1 and by_action.get("authorization_denied", 0) >= 1:
            break
        time.sleep(5)
    check(
        "the failed sign-in and the denied page are counted",
        by_action.get("sign_in_failed", 0) >= 1 and by_action.get("authorization_denied", 0) >= 1,
        json.dumps(by_action),
    )

    series = json.dumps(prom('{__name__=~"loyalty_.*|http_server.*"}'))
    check(
        "no series holds the planted email or the demo password", PLANTED_EMAIL not in series and PASSWORD not in series
    )

    found: list[dict[str, Any]] = []
    deadline = time.monotonic() + 90  # spans are batched, then indexed: allow for both
    while not found and time.monotonic() < deadline:
        search = httpx.get(
            f"{TEMPO}/api/search", params={"q": '{resource.service.name="loyalty-app"}', "limit": 20}, timeout=20
        )
        found = search.json().get("traces") or []
        if not found:
            time.sleep(5)
    check("Tempo has traces from the app", bool(found), f"{len(found)} found")
    if found:
        one = httpx.get(f"{TEMPO}/api/traces/{found[0]['traceID']}", timeout=20).json()
        text = json.dumps(one)
        check(
            "a stored trace holds no planted email, password or query string",
            PLANTED_EMAIL not in text and PASSWORD not in text and "q=planted" not in text,
        )

    worker = httpx.get(
        f"{TEMPO}/api/search", params={"q": '{resource.service.name="loyalty-worker"}', "limit": 50}, timeout=20
    ).json()
    polls = [t for t in worker.get("traces") or [] if t.get("rootTraceName") in ("SELECT", "UPDATE")]
    check("the worker's job polling makes no traces of its own", not polls, f"{len(polls)} one-statement traces")

    dashboards = grafana("/api/search", type="dash-db")
    titles = sorted(d["title"] for d in dashboards if d.get("folderTitle") == "Loyalty support")
    check("Grafana loaded the Loyalty support dashboards", bool(titles), ", ".join(titles))

    # The panels run through Grafana's Prometheus plugin, not Prometheus directly: query it the same way.
    body = {
        "from": "now-5m",
        "to": "now",
        "queries": [{"refId": "A", "datasource": {"uid": "prometheus"}, "expr": "max(loyalty_jobs_queued)"}],
    }
    answer = httpx.post(f"{GRAFANA}/api/ds/query", json=body, timeout=20)
    frames = answer.json().get("results", {}).get("A", {}) if answer.status_code == 200 else {}
    check(
        "a dashboard query runs through Grafana's Prometheus datasource",
        answer.status_code == 200 and not frames.get("error") and bool(frames.get("frames")),
        f"HTTP {answer.status_code}",
    )

    rules = grafana("/api/prometheus/grafana/api/v1/rules")
    loaded = [r for g in rules["data"]["groups"] for r in g["rules"]]
    check("Grafana loaded the alert rules", len(loaded) >= 6, f"{len(loaded)} rules")
    missing = []
    for rule in loaded:
        url = (rule.get("annotations") or {}).get("runbook_url", "")
        if not url.startswith("docs/runbooks/") or not (ROOT / url).is_file():
            missing.append(rule.get("name", "?"))
    check("every alert rule names a runbook that exists", not missing, ", ".join(missing))
    # Grafana installs its datasource plugins about a minute after it starts; a rule evaluated before that reports
    # "plugin not registered" until its next clean evaluation, so wait for one (found in the check, ADR-0080).
    deadline = time.monotonic() + 180
    while True:
        loaded = [r for g in grafana("/api/prometheus/grafana/api/v1/rules")["data"]["groups"] for r in g["rules"]]
        broken = [r.get("name") for r in loaded if r.get("health") == "error"]  # "nodata" is a quiet stack
        if not broken or time.monotonic() > deadline:
            break
        time.sleep(10)
    for rule in loaded:
        print(f"  rule {rule.get('name')}: health={rule.get('health')} state={rule.get('state')}")
    check("every alert rule evaluates without an error", not broken, ", ".join(map(str, broken)))

    # The planted dead job: "Jobs giving up" must fire, so an alert is shown to work, not just to load.
    deadline, state = time.monotonic() + 180, ""
    while time.monotonic() < deadline:
        groups = grafana("/api/prometheus/grafana/api/v1/rules")["data"]["groups"]
        state = next((r.get("state", "") for g in groups for r in g["rules"] if r.get("name") == "Jobs giving up"), "")
        if state == "firing":
            break
        time.sleep(10)
    check("a planted dead job makes 'Jobs giving up' fire", state == "firing", f"state {state or 'not found'}")
    silent = next((r.get("state", "") for g in groups for r in g["rules"] if r.get("name") == "App not reporting"), "")
    check(
        "a running, idle app raises no 'App not reporting' alarm", silent in ("inactive", "normal"), f"state {silent}"
    )

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
