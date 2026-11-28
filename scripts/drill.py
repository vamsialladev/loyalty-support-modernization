"""Milestone 13b drills against a running throwaway stack (ROLL-02; `docs/drills.md`). Runs in GitHub Actions
(`.github/workflows/drills.yml`), never against the live demo, Cloud Run or Neon.

    uv run python scripts/drill.py d7 --env-file .env.ci --out drill-output

The stack is the one CI's Compose job starts: `docker compose -p ci --env-file .env.ci up --build -d --wait`, then the
demo seed. Every value in `.env.ci` is a throwaway made for that run (`scripts/update-local-env.ps1`). This script
reads the demo accounts' password from it, uses it only against 127.0.0.1, and never prints or saves it. Postings are
counted read-only in the stack's own mock-API database, through `docker compose exec`.

Each drill writes `<out>/<drill>.json` (what it did, what it saw, each check and whether it passed) and prints one line
per check. The exit code is 0 only if every check passed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
APP = "http://127.0.0.1:8010"
DATASET = ROOT / "benchmarks" / "datasets" / "v1"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    return values


def browser(base: str) -> httpx.Client:
    """The app sets Secure cookies in some profiles, and an HTTP client won't send those over plain http. Against
    127.0.0.1 only, this carries them by hand (as `scripts/demo_smoke.py` does)."""
    jar: dict[str, str] = {}
    client = httpx.Client(base_url=base, timeout=30, follow_redirects=False)

    def keep(response: httpx.Response) -> None:
        for header in response.headers.get_list("set-cookie"):
            name, _, rest = header.partition("=")
            value = rest.split(";", 1)[0]
            if "max-age=0" in header.lower() or not value.strip('"'):
                jar.pop(name.strip(), None)
            else:
                jar[name.strip()] = value
        client.headers["cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())

    client.event_hooks["response"] = [keep]
    return client


@dataclass
class Person:
    username: str
    client: httpx.Client
    csrf: str

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self.client.request(method, f"/api/v1{path}", json=body, headers={"X-CSRF-Token": self.csrf})

    def form(self, path: str, data: dict[str, str]) -> httpx.Response:
        return self.client.post(path, data={**data, "csrf": self.csrf})


def sign_in(username: str, password: str) -> Person:
    client = browser(APP)
    page = client.get("/login")
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    response = client.post(
        "/login", data={"username": username, "password": password, "login_csrf": token.group(1) if token else ""}
    )
    if response.status_code not in (302, 303):
        raise RuntimeError(f"sign-in as {username} failed: HTTP {response.status_code}")
    me = client.get("/api/v1/me", headers={})
    me.raise_for_status()
    return Person(username, client, me.json()["csrf_token"])


@dataclass
class Report:
    drill: str
    started_utc: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    steps: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def step(self, what: str, **seen: Any) -> None:
        self.steps.append({"at": round(time.monotonic(), 2), "what": what, **seen})
        print(f"  step: {what} {json.dumps(seen, default=str)}", flush=True)

    def check(self, name: str, ok: bool, **seen: Any) -> None:
        self.checks.append({"check": name, "passed": ok, **seen})
        print(f"{'PASS' if ok else 'FAIL'}  {name} {json.dumps(seen, default=str)}", flush=True)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c["passed"] for c in self.checks)

    def save(self, out: Path) -> Path:
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.drill}.json"
        body = {"drill": self.drill, "started_utc": self.started_utc, "passed": self.passed}
        path.write_text(json.dumps({**body, "steps": self.steps, "checks": self.checks}, indent=2) + "\n", "utf-8")
        return path


def read_json(person: Person, path: str) -> Any:
    response = person.api("GET", path)
    response.raise_for_status()
    return response.json()


def wait_until(probe: Callable[[], Any], ok: Callable[[Any], bool], seconds: float, every: float = 1.0) -> Any:
    deadline = time.monotonic() + seconds
    while True:
        value = probe()
        if ok(value) or time.monotonic() > deadline:
            return value
        time.sleep(every)


def adjustable_cases(limit: int = 12) -> list[dict[str, Any]]:
    """Dev cases labelled "adjusted", with one message and no attachment, in file order: a drill needs real ones."""
    labels = {
        row["case_id"]: row
        for row in map(json.loads, (DATASET / "labels" / "dev.jsonl").read_text(encoding="utf-8").splitlines())
    }
    picked = []
    for row in map(json.loads, (DATASET / "dev.jsonl").read_text(encoding="utf-8").splitlines()):
        label = labels.get(row["case_id"], {})
        requests = row["requests"]
        if label.get("expected_outcome") == "adjusted" and len(requests) == 1 and not requests[0]["attachments"]:
            picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def approved_adjustments(agent: Person, supervisor: Person, wanted: int, report: Report) -> list[dict[str, Any]]:
    """Work dev cases through arm B until `wanted` adjustments are approved and waiting to be executed."""
    approved: list[dict[str, Any]] = []
    for row in adjustable_cases():
        if len(approved) >= wanted:
            break
        request = row["requests"][0]
        made = agent.api(
            "POST",
            "/cases",
            {
                "received_at_utc": request["received_at_utc"],
                "contact_channel": request["contact_channel"],
                "text": request["text"],
                "arm": "B",
                "sender_email": request.get("sender_email"),
            },
        )
        made.raise_for_status()
        case_id = made.json()["id"]
        agent.api("POST", f"/cases/{case_id}/investigation").raise_for_status()
        detail = wait_until(
            partial(read_json, agent, f"/cases/{case_id}"),
            lambda d: d["investigation"] in ("none", "failed"),
            90,
        )
        asked = agent.api("POST", f"/cases/{case_id}/adjustment-request")
        if asked.status_code != 201 or not asked.json().get("adjustment"):
            report.step("case skipped: no adjustment to request", case=row["case_id"], http=asked.status_code)
            continue
        adjustment = asked.json()["adjustment"]
        decided = supervisor.api("POST", f"/adjustments/{adjustment['id']}/decision", {"decision": "approve"})
        decided.raise_for_status()
        report.step(
            "adjustment approved",
            case=row["case_id"],
            request_id=adjustment["id"],
            points=adjustment["points"],
            investigation=detail["investigation"],
        )
        approved.append(adjustment)
    return approved


@dataclass(frozen=True)
class Stack:
    """The throwaway Compose stack CI started: `docker compose -p <project> --env-file <file>`."""

    project: str
    env_file: Path
    db_user: str
    app_db: str = "loyalty"

    def compose(self, *args: str) -> list[str]:
        return ["docker", "compose", "-p", self.project, "--env-file", str(self.env_file), *args]

    def psql(self, database: str, sql: str, **values: str) -> str:
        """A read-only query in the stack's own Postgres, as its superuser over the container's local socket. Values
        are bound as psql variables (`:'name'`), never pasted into the SQL."""
        bind = [arg for name, value in values.items() for arg in ("-v", f"{name}={value}")]
        command = self.compose("exec", "-T", "db", "psql", "-U", self.db_user, "-d", database, "-tA", *bind)
        done = subprocess.run(command, input=sql, capture_output=True, text=True, check=True)  # noqa: S603
        return done.stdout.strip()


def postings(stack: Stack, member: str, stay: str) -> int:
    """Adjustment entries for this stay in the member's ledger on the customer's system (the mock API's database)."""
    sql = (
        "SELECT count(*) FROM ledger_entries"
        " WHERE member_number = :'member' AND stay_id = :'stay' AND kind = 'adjustment';"
    )
    return int(stack.psql("mock_customer_api", sql, member=member, stay=stay))


def drill_d7(env: dict[str, str], stack: Stack, report: Report, out: Path) -> None:
    """D7, emergency execution shutdown: the kill switch stops every execution, nothing posts while it's on, and each
    approved adjustment posts exactly once after it's released."""
    password = env["DEMO_USER_PASSWORD"]
    agent, supervisor, admin = (sign_in(u, password) for u in ("agent.ana", "supervisor.sam", "admin.ada"))
    waiting = approved_adjustments(agent, supervisor, 2, report)
    report.check("two approved adjustments to work with", len(waiting) == 2, found=len(waiting))
    if len(waiting) < 2:
        return

    def count() -> dict[int, int]:
        return {a["id"]: postings(stack, a["member_number"], a["stay_id"]) for a in waiting}

    before = count()

    engaged_at = time.monotonic()
    on = admin.form("/admin/kill-switch", {"engage": "on", "reason": "D7 drill: emergency execution shutdown"})
    report.step("kill switch engaged", http=on.status_code)
    refused = [supervisor.api("POST", f"/adjustments/{a['id']}/execution") for a in waiting]
    first_refusal = round(time.monotonic() - engaged_at, 2)
    report.check(
        "every execution is refused while the switch is on",
        all(r.status_code == 409 for r in refused),
        http=[r.status_code for r in refused],
        seconds_from_switch_to_first_refusal=first_refusal,
    )
    time.sleep(10)  # give any worker that might have slipped through time to post
    during = count()
    report.check("nothing posts while the switch is on", during == before, before=before, during=during)

    off = admin.form("/admin/kill-switch", {"engage": "off", "reason": "D7 drill: shutdown over"})
    report.step("kill switch released", http=off.status_code)
    queued = [supervisor.api("POST", f"/adjustments/{a['id']}/execution") for a in waiting]
    report.check(
        "executions are accepted once it's released",
        all(r.status_code == 202 for r in queued),
        http=[r.status_code for r in queued],
    )
    final = [
        wait_until(
            partial(read_json, supervisor, f"/adjustments/{a['id']}"),
            lambda d: d["status"] not in ("approved", "executing"),
            120,
        )
        for a in waiting
    ]
    report.check("each adjustment ends executed", all(f["status"] == "executed" for f in final),
                 statuses=[f["status"] for f in final])  # fmt: skip
    again = [supervisor.api("POST", f"/adjustments/{a['id']}/execution") for a in waiting]
    time.sleep(5)
    after = count()
    report.check(
        "each posts exactly once, and a repeat execute posts nothing more",
        all(after[k] - before[k] == 1 for k in after),
        before=before,
        after=after,
        repeat_http=[r.status_code for r in again],
    )
    events = read_json(admin, "/security/events")  # Elastic Common Schema documents: the action is event.action
    actions = [e.get("event", {}).get("action") for e in events]
    switches = actions.count("kill_switch_changed")
    report.check(
        "both switches are audited security events", switches >= 2, found=switches, actions_seen=sorted(set(actions))
    )


def job_state(stack: Stack, case_id: int) -> str:
    """The execute job's status and lease owner for this case, from the stack's app database (read-only)."""
    sql = (
        "SELECT coalesce(max(status || ':' || coalesce(lease_owner, '-')), 'none') FROM jobs"
        " WHERE kind = 'execute_adjustment' AND case_id = :'case';"
    )
    return stack.psql(stack.app_db, sql, case=str(case_id))


def drill_d3(env: dict[str, str], stack: Stack, report: Report, out: Path) -> None:
    """D3, worker crash: the worker is killed while it holds an execute job's lease; a replacement recovers the job once
    the lease runs out, and the adjustment posts exactly once.

    To hold the worker inside the job, the customer's system is paused first: the worker claims the job, then waits on
    its re-check read (about 2 s before it would time out). The kill lands there, before anything was submitted. The
    case where a submission reached the system and the answer was lost is D5's."""
    password = env["DEMO_USER_PASSWORD"]
    agent, supervisor = (sign_in(u, password) for u in ("agent.ana", "supervisor.sam"))
    waiting = approved_adjustments(agent, supervisor, 1, report)
    report.check("one approved adjustment to work with", len(waiting) == 1, found=len(waiting))
    if not waiting:
        return
    adjustment = waiting[0]
    before = postings(stack, adjustment["member_number"], adjustment["stay_id"])

    run(stack.compose("pause", "mock-api"))
    report.step("customer system paused")
    queued = supervisor.api("POST", f"/adjustments/{adjustment['id']}/execution")
    report.check("the execution is queued", queued.status_code == 202, http=queued.status_code)
    claimed = wait_until(
        partial(job_state, stack, adjustment["case_id"]), lambda s: s.startswith("running:"), 20, every=0.2
    )
    run(stack.compose("kill", "-s", "SIGKILL", "worker"))
    killed_at = time.monotonic()
    report.check("the worker was killed while it held the job", claimed.startswith("running:"), job=claimed)
    run(stack.compose("unpause", "mock-api"))
    time.sleep(3)
    report.step(
        "worker killed, customer system resumed",
        job=job_state(stack, adjustment["case_id"]),
        postings_so_far=postings(stack, adjustment["member_number"], adjustment["stay_id"]) - before,
    )

    run(stack.compose("up", "-d", "--no-deps", "worker"))
    report.step("replacement worker started")
    final = wait_until(
        partial(read_json, supervisor, f"/adjustments/{adjustment['id']}"),
        lambda d: d["status"] not in ("approved", "executing"),
        150,
        every=2,
    )
    recovered_after = round(time.monotonic() - killed_at, 1)
    after = postings(stack, adjustment["member_number"], adjustment["stay_id"])
    report.check(
        "the replacement finishes the job: executed",
        final["status"] == "executed",
        status=final["status"],
        seconds_from_kill=recovered_after,
    )
    report.check("exactly one posting", after - before == 1, before=before, after=after)
    audit = read_json(supervisor, f"/cases/{adjustment['case_id']}/audit")
    actions = [e.get("action") for e in audit]
    report.check(
        "the timeline shows one execution",
        actions.count("adjustment_executed") == 1,
        actions=actions[-8:],
    )


def with_faults(stack: Stack, out: Path, rules: list[dict[str, Any]]) -> None:
    """Recreate only the mock API with seeded fault rules (`docker-compose.drills.yml`). The rule file lives in the
    drill's own output folder, so it's kept with the run's artifact."""
    folder = out / "rules"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "rules.yaml").write_text(json.dumps({"rules": rules}, indent=2) + "\n", encoding="utf-8")  # JSON is YAML
    overrides = ["-f", str(ROOT / "docker-compose.yml"), "-f", str(ROOT / "docker-compose.drills.yml")]
    base = stack.compose()
    run([*base[:2], *overrides, *base[2:], "up", "-d", "--no-deps", "--force-recreate", "--wait", "mock-api"])


def drill_d5(env: dict[str, str], stack: Stack, report: Report, out: Path) -> None:
    """D5, uncertain adjustment: the customer's system applies the adjustment, then the gateway times out (504), so
    the app can't know whether it posted. The case must go to "execution unknown" (never "failed", never a blind
    retry), and reconciliation must settle it by a status lookup, with exactly one posting."""
    password = env["DEMO_USER_PASSWORD"]
    agent, supervisor = (sign_in(u, password) for u in ("agent.ana", "supervisor.sam"))
    waiting = approved_adjustments(agent, supervisor, 1, report)
    report.check("one approved adjustment to work with", len(waiting) == 1, found=len(waiting))
    if not waiting:
        return
    adjustment = waiting[0]
    before = postings(stack, adjustment["member_number"], adjustment["stay_id"])
    # Every call about this stay matches; only the adjustment submission acts on this fault (reads ignore it). The
    # reconciliation's status lookup is by idempotency key, with no stay, so it isn't matched and tells the truth.
    with_faults(stack, out, [{"fault": "commit_then_lost", "stay_suffix": adjustment["stay_id"]}])
    report.step("customer system restarted with commit_then_lost for this stay", stay=adjustment["stay_id"])

    queued = supervisor.api("POST", f"/adjustments/{adjustment['id']}/execution")
    report.check("the execution is queued", queued.status_code == 202, http=queued.status_code)
    started = time.monotonic()
    seen: list[str] = []

    def status() -> str:
        value = str(read_json(supervisor, f"/adjustments/{adjustment['id']}")["status"])
        if not seen or seen[-1] != value:
            seen.append(value)
        return value

    final = wait_until(status, lambda s: s not in ("approved", "executing", "execution_unknown"), 180, every=0.5)
    settled_after = round(time.monotonic() - started, 1)
    after = postings(stack, adjustment["member_number"], adjustment["stay_id"])
    # The audit trail is the record: a status polled every 0.5 s can miss a state that lasts under a second (the first
    # run, 46094877745, saw only approved -> executed while the timeline held execution_unknown; M13b row 4).
    audit = read_json(supervisor, f"/cases/{adjustment['case_id']}/audit")
    actions = [e.get("action") for e in audit]
    at = {e.get("action"): e.get("at_utc") for e in audit}
    order = [a for a in actions if a in ("execution_started", "execution_unknown", "reconciled_applied")]
    report.check(
        "the case went to execution unknown, then reconciliation, in that order",
        order == ["execution_started", "execution_unknown", "reconciled_applied"],
        order=order,
        statuses_polled=seen,
        unknown_at=at.get("execution_unknown"),
        reconciled_at=at.get("reconciled_applied"),
    )
    report.check(
        "no blind retry and nothing marked failed",
        actions.count("execution_started") == 1 and not any("failed" in str(a) for a in actions),
        actions=actions[-8:],
    )
    report.check("reconciliation settles it as executed", final == "executed", final=final, seconds=settled_after)
    report.check("exactly one posting", after - before == 1, before=before, after=after)
    report.check("the timeline has one execution", actions.count("adjustment_executed") == 1, actions=actions[-8:])


def job_attempts(stack: Stack, case_id: int) -> int:
    sql = "SELECT coalesce(max(attempts), 0) FROM jobs WHERE kind = 'investigate_case' AND case_id = :'case';"
    return int(stack.psql(stack.app_db, sql, case=str(case_id)))


def drill_d2(env: dict[str, str], stack: Stack, report: Report, out: Path) -> None:
    """D2, customer API outage: the customer's system goes down (the container stops) while investigations are asked
    for. Nothing may show evidence it didn't read, the app must stay up and say the system is unreachable, and the
    queued investigations must finish on their own (retry with backoff) once it's back."""
    password = env["DEMO_USER_PASSWORD"]
    agent = sign_in("agent.ana", password)
    run(stack.compose("stop", "mock-api"))
    down_at = time.monotonic()
    report.step("customer system stopped")
    ready = httpx.get(f"{APP}/readyz", timeout=10)
    report.check(
        "readiness says the customer system is unreachable",
        ready.status_code == 503 and ready.json().get("customer_systems") == "unreachable",
        http=ready.status_code,
        body=ready.json(),
    )
    cases = []
    for row in adjustable_cases(3):
        request = row["requests"][0]
        made = agent.api(
            "POST",
            "/cases",
            {
                "received_at_utc": request["received_at_utc"],
                "contact_channel": request["contact_channel"],
                "text": request["text"],
                "arm": "B",
                "sender_email": request.get("sender_email"),
            },
        )
        made.raise_for_status()
        case_id = made.json()["id"]
        asked = agent.api("POST", f"/cases/{case_id}/investigation")
        cases.append((row["case_id"], case_id, asked.status_code))
    report.check("the app takes the requests while the system is down", all(c[2] == 202 for c in cases),
                 http=[c[2] for c in cases])  # fmt: skip
    time.sleep(15)
    during = [read_json(agent, f"/cases/{case_id}") for _, case_id, _ in cases]
    report.check(
        "no case shows evidence or a proposal it couldn't read",
        all(d["evidence"] is None and d["recommendation"] is None for d in during),
        investigation=[d["investigation"] for d in during],
    )
    attempts = [job_attempts(stack, case_id) for _, case_id, _ in cases]
    report.check("the investigations are being retried", all(a >= 2 for a in attempts), attempts=attempts)

    run(stack.compose("start", "mock-api"))
    outage = round(time.monotonic() - down_at, 1)
    report.step("customer system started again", outage_seconds=outage)
    back = wait_until(lambda: httpx.get(f"{APP}/readyz", timeout=10).status_code, lambda code: code == 200, 120, 2)
    report.check("readiness recovers", back == 200, http=back)
    finished = [
        wait_until(
            partial(read_json, agent, f"/cases/{case_id}"),
            lambda d: (
                d["investigation"] in ("none", "failed")
                and (d["evidence"] is not None or d["investigation"] == "failed")
            ),
            150,
            every=2,
        )
        for _, case_id, _ in cases
    ]
    recovered_after = round(time.monotonic() - down_at, 1)
    report.check(
        "every investigation finishes on its own once the system is back",
        all(d["investigation"] == "none" and d["evidence"] is not None for d in finished),
        investigation=[d["investigation"] for d in finished],
        attempts=[job_attempts(stack, case_id) for _, case_id, _ in cases],
        seconds_from_outage_start=recovered_after,
    )


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603


DRILLS: dict[str, Callable[[dict[str, str], Stack, Report, Path], None]] = {
    "d2": drill_d2,
    "d3": drill_d3,
    "d5": drill_d5,
    "d7": drill_d7,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/drill.py")
    parser.add_argument("drill", choices=sorted(DRILLS))
    parser.add_argument("--env-file", type=Path, default=Path(".env.ci"))
    parser.add_argument("--project", default="ci", help="the Compose project CI started")
    parser.add_argument("--out", type=Path, default=Path("drill-output"))
    args = parser.parse_args(argv)
    env = read_env(args.env_file)
    stack = Stack(args.project, args.env_file, env.get("POSTGRES_USER", "loyalty"), env.get("POSTGRES_DB", "loyalty"))
    report = Report(args.drill)
    try:
        DRILLS[args.drill](env, stack, report, args.out)
    except Exception as error:  # the drill itself broke: record it as a failed check, with its type and message
        report.check("the drill ran to the end", False, error=f"{type(error).__name__}: {error}"[:500])
    path = report.save(args.out)
    print(f"\n{sum(c['passed'] for c in report.checks)} of {len(report.checks)} checks passed; saved {path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
