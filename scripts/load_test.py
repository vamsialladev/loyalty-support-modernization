"""A bounded load test against a running stack (spec F.1; OPS-01; ADR-0083). Run by `scripts\\load_test.ps1`.

The profile is declared in `docs/load-profile.md`. Each stage runs for a fixed time with a fixed number of virtual
users. **Agents** sign in to the JSON API and repeat: create a case from a synthetic dataset request, start its
investigation, open the queue, and read the case until the worker has finished. **Supervisors** read the approvals
queue and the metrics page. It measures:

- API latency per endpoint (p50, p95, p99), throughput and failures by status;
- investigation latency: from "start" to the worker's result, the user-visible wait;
- the queue's depth and oldest age, sampled from the app's database during each stage.

Writes `performance/reports/<date>-local.md` and the raw samples as CSV next to it. Local laptop, mock customer API,
mock AI: **not production capacity.** Synthetic data only.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # run as a script from scripts/

from benchmarks.intake import read_split  # noqa: E402

REPORTS = ROOT / "performance" / "reports"
LABEL = "Local laptop, Docker Desktop, mock customer API, mock AI, synthetic data: not production capacity."


@dataclass(frozen=True)
class Stage:
    name: str
    agents: int
    supervisors: int
    seconds: int


@dataclass
class Sample:
    stage: str
    kind: str  # api | investigation | queue
    name: str
    status: int
    ms: float
    at: float


@dataclass
class Results:
    samples: list[Sample] = field(default_factory=list)
    queue: list[tuple[str, float, int, float]] = field(default_factory=list)  # stage, t, depth, oldest_s
    db: dict[str, dict[str, Any]] = field(default_factory=dict)


def requests_pool() -> list[dict[str, Any]]:
    pool = []
    for case in read_split("dev") + read_split("validation"):
        r = case.requests[0]
        pool.append(
            {
                "received_at_utc": r.received_at_utc,
                "contact_channel": r.contact_channel
                if r.contact_channel in ("phone_note", "email", "web_form")
                else "email",
                "text": r.text[:20000],
                "arm": "B",
                "sender_email": r.sender_email,
                "form_member_number": r.form_member_number,
                "form_confirmation": r.form_confirmation,
                "form_name": r.form_name,
            }
        )
    return pool


async def sign_in(client: httpx.AsyncClient, username: str, password: str) -> str:
    page = await client.get("/login")
    token = re.search(r'name="login_csrf" value="([^"]+)"', page.text)
    form = {"username": username, "password": password, "login_csrf": token.group(1) if token else ""}
    await client.post("/login", data=form)
    me = await client.get("/api/v1/me")
    me.raise_for_status()
    return str(me.json()["csrf_token"])


async def timed(results: Results, stage: str, name: str, call: Any) -> httpx.Response | None:
    start = time.perf_counter()
    try:
        resp: httpx.Response = await call
    except httpx.HTTPError as exc:
        results.samples.append(Sample(stage, "api", name, 0, (time.perf_counter() - start) * 1000, time.time()))
        print(f"  {name}: {type(exc).__name__}")
        return None
    results.samples.append(
        Sample(stage, "api", name, resp.status_code, (time.perf_counter() - start) * 1000, time.time())
    )
    return resp


async def agent(
    base: str,
    user: str,
    password: str,
    stage: Stage,
    pool: list[dict[str, Any]],
    results: Results,
    deadline: float,
    seed: int,
) -> None:
    rng = random.Random(seed)  # noqa: S311 - which synthetic request to send, not a secret
    async with httpx.AsyncClient(base_url=base, timeout=30, follow_redirects=True) as client:
        csrf = await sign_in(client, user, password)
        headers = {"X-CSRF-Token": csrf}
        while time.monotonic() < deadline:
            created = await timed(
                results,
                stage.name,
                "POST /api/v1/cases",
                client.post("/api/v1/cases", json=rng.choice(pool), headers=headers),
            )
            if created is None or created.status_code != 201:
                await asyncio.sleep(1)
                continue
            case_id = created.json()["id"]
            started_at = time.perf_counter()
            started = await timed(
                results,
                stage.name,
                "POST /api/v1/cases/{id}/investigation",
                client.post(f"/api/v1/cases/{case_id}/investigation", headers=headers),
            )
            await timed(results, stage.name, "GET /queue", client.get("/queue"))
            if started is None or started.status_code != 202:
                continue
            while time.monotonic() < deadline + 120:  # finish the case in hand, bounded
                detail = await timed(
                    results, stage.name, "GET /api/v1/cases/{id}", client.get(f"/api/v1/cases/{case_id}")
                )
                if (
                    detail is not None
                    and detail.status_code == 200
                    and detail.json()["investigation"] not in ("queued", "running")
                ):
                    ms = (time.perf_counter() - started_at) * 1000
                    state = detail.json()["investigation"]
                    results.samples.append(Sample(stage.name, "investigation", state, 200, ms, time.time()))
                    break
                await asyncio.sleep(0.5)


async def supervisor(base: str, user: str, password: str, stage: Stage, results: Results, deadline: float) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=30, follow_redirects=True) as client:
        await sign_in(client, user, password)
        while time.monotonic() < deadline:
            await timed(results, stage.name, "GET /approvals", client.get("/approvals"))
            await timed(results, stage.name, "GET /metrics", client.get("/metrics"))
            await asyncio.sleep(2)


def sample_queue(database_url: str) -> tuple[int, float]:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT count(*), coalesce(extract(epoch FROM now() - min(created_at_utc::timestamptz)), 0) "
                "FROM jobs WHERE status IN ('queued', 'running')"
            )
        ).one()
    engine.dispose()
    return int(row[0]), float(row[1])


async def queue_watch(database_url: str, stage: Stage, results: Results, deadline: float) -> None:
    while time.monotonic() < deadline:
        depth, oldest = await asyncio.to_thread(sample_queue, database_url)
        results.queue.append((stage.name, time.time(), depth, oldest))
        await asyncio.sleep(2)


def db_snapshot(database_url: str) -> dict[str, Any]:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    with engine.connect() as conn:
        connections = conn.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        ).scalar()
        stats = conn.execute(
            text(
                "SELECT xact_commit, xact_rollback, blks_read, blks_hit, deadlocks FROM pg_stat_database "
                "WHERE datname = current_database()"
            )
        ).one()
        tables = conn.execute(
            text(
                "SELECT relname, seq_scan, idx_scan, n_live_tup FROM pg_stat_user_tables "
                "WHERE relname IN ('cases','case_events','jobs','case_requests','recommendations') ORDER BY relname"
            )
        ).all()
    engine.dispose()
    return {
        "connections": int(connections or 0),
        "commits": int(stats[0]),
        "rollbacks": int(stats[1]),
        "cache_hit": round(stats[3] / max(1, stats[2] + stats[3]), 4),
        "deadlocks": int(stats[4]),
        "tables": {
            r[0]: {"seq_scan": int(r[1] or 0), "idx_scan": int(r[2] or 0), "rows": int(r[3] or 0)} for r in tables
        },
    }


async def run_stage(
    base: str, password: str, database_url: str, stage: Stage, pool: list[dict[str, Any]], results: Results
) -> None:
    print(f"== stage {stage.name}: {stage.agents} agents, {stage.supervisors} supervisors, {stage.seconds} s")
    deadline = time.monotonic() + stage.seconds
    agents = ["agent.ana", "agent.ben"]
    supervisors = ["supervisor.sam", "supervisor.sky"]
    tasks = [agent(base, agents[i % 2], password, stage, pool, results, deadline, seed=i) for i in range(stage.agents)]
    tasks += [
        supervisor(base, supervisors[i % 2], password, stage, results, deadline) for i in range(stage.supervisors)
    ]
    tasks.append(queue_watch(database_url, stage, results, deadline + 60))
    await asyncio.gather(*tasks)
    results.db[stage.name] = await asyncio.to_thread(db_snapshot, database_url)


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def report(stages: list[Stage], results: Results, started: str, finished: str) -> str:
    lines = [
        f"# Load test, {started[:10]} (local)",
        "",
        f"> **{LABEL}** Profile: `docs/load-profile.md`. Command: `scripts\\load_test.ps1`.",
        "> Raw samples: the CSV next to this file.",
        "> Started " + started + ", finished " + finished + ".",
        "",
        "## API latency and throughput",
        "",
        "| Stage | Endpoint | Requests | Failures | p50 ms | p95 ms | p99 ms |",
        "|---|---|---|---|---|---|---|",
    ]
    by: dict[tuple[str, str], list[Sample]] = defaultdict(list)
    for s in results.samples:
        if s.kind == "api":
            by[(s.stage, s.name)].append(s)
    for stage in stages:
        for (name_stage, endpoint), samples in sorted(by.items()):
            if name_stage != stage.name:
                continue
            ms = [s.ms for s in samples]
            failures = sum(1 for s in samples if s.status == 0 or s.status >= 400)
            lines.append(
                f"| {stage.name} | `{endpoint}` | {len(samples)} | {failures} | {pct(ms, 50):.0f} | "
                f"{pct(ms, 95):.0f} | {pct(ms, 99):.0f} |"
            )
    lines += [
        "",
        "| Stage | Users | Seconds | API requests | Requests/s | Failure rate | Statuses |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage in stages:
        samples = [s for s in results.samples if s.kind == "api" and s.stage == stage.name]
        failures = sum(1 for s in samples if s.status == 0 or s.status >= 400)
        statuses = Counter(s.status for s in samples)
        rate = len(samples) / stage.seconds
        share = failures / len(samples) if samples else 0
        lines.append(
            f"| {stage.name} | {stage.agents} + {stage.supervisors} | {stage.seconds} | {len(samples)} | "
            f"{rate:.1f} | {share:.2%} | {dict(sorted(statuses.items()))} |"
        )
    lines += [
        "",
        "## Investigation latency (start to the worker's result)",
        "",
        "| Stage | Investigations finished | p50 s | p95 s | max s | Ended as |",
        "|---|---|---|---|---|---|",
    ]
    for stage in stages:
        inv = [s for s in results.samples if s.kind == "investigation" and s.stage == stage.name]
        secs = [s.ms / 1000 for s in inv]
        ended = dict(Counter(s.name for s in inv))
        lines.append(
            f"| {stage.name} | {len(inv)} | {pct(secs, 50):.1f} | {pct(secs, 95):.1f} | "
            f"{max(secs) if secs else float('nan'):.1f} | {ended} |"
        )
    lines += [
        "",
        "## Queue (sampled every 2 s from the app database)",
        "",
        "| Stage | Samples | Max depth | Max oldest job, s | Mean depth |",
        "|---|---|---|---|---|",
    ]
    for stage in stages:
        q = [r for r in results.queue if r[0] == stage.name]
        lines.append(
            f"| {stage.name} | {len(q)} | {max((r[2] for r in q), default=0)} | "
            f"{max((r[3] for r in q), default=0):.0f} | {statistics.mean([r[2] for r in q]) if q else 0:.1f} |"
        )
    lines += [
        "",
        "## Postgres (after each stage; cumulative counters)",
        "",
        "| Stage | Connections | Commits | Rollbacks | Cache hit | Deadlocks | Seq scans on `case_events` |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage in stages:
        d = results.db.get(stage.name, {})
        seq = d.get("tables", {}).get("case_events", {}).get("seq_scan", "")
        lines.append(
            f"| {stage.name} | {d.get('connections', '')} | {d.get('commits', '')} | {d.get('rollbacks', '')} | "
            f"{d.get('cache_hit', '')} | {d.get('deadlocks', '')} | {seq} |"
        )
    lines += [
        "",
        "`pg_stat_statements` isn't loaded in the stack, so per-query timings aren't in this report; the table",
        "scan counters above stand in for them.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/load_test.py")
    parser.add_argument("--base", default=os.environ.get("LOAD_APP_URL", "http://127.0.0.1:48010"))
    parser.add_argument(
        "--stages",
        default="baseline:2:1:120,x4:8:2:120,x10:20:4:120",
        help="name:agents:supervisors:seconds, comma-separated",
    )
    args = parser.parse_args(argv)
    password = os.environ["LOAD_DEMO_PASSWORD"]
    database_url = os.environ["LOAD_DATABASE_URL"]
    stages = [Stage(n, int(a), int(s), int(t)) for n, a, s, t in (x.split(":") for x in args.stages.split(","))]
    pool = requests_pool()
    results = Results()
    started = datetime.now(UTC).isoformat(timespec="seconds")
    for stage in stages:
        asyncio.run(run_stage(args.base, password, database_url, stage, pool, results))
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    REPORTS.mkdir(parents=True, exist_ok=True)
    day = started[:10]
    (REPORTS / f"{day}-local.md").write_text(report(stages, results, started, finished), encoding="utf-8", newline="\n")
    with (REPORTS / f"{day}-local-samples.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["stage", "kind", "name", "status", "ms", "unix_time"])
        for s in results.samples:
            writer.writerow([s.stage, s.kind, s.name, s.status, f"{s.ms:.1f}", f"{s.at:.3f}"])
    (REPORTS / f"{day}-local-db.json").write_text(json.dumps(results.db, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote performance/reports/{day}-local.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
