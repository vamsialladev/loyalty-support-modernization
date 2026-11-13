"""The AG-UI live view against an independent client: the official `@ag-ui/client` (spec G.5, G.13; Appendix C, M11).

Opt in, because it needs Node and the pinned npm package in a folder of its own:

    cd <scratch>\\agui; npm init -y; npm install --save-exact --ignore-scripts @ag-ui/client@1.0.4
    $env:RUN_INTEROP = "1"; $env:AG_UI_CLIENT_DIR = "<scratch>\\agui"
    uv run pytest tests/interop/test_ag_ui_client.py -s

The console runs as a real HTTP server on a free local port with synthetic cases. `tests/interop/ag_ui_client.mjs`
uses the client's own `HttpAgent`: its SSE parser, its event schemas and its event-order checks, none of which are our
code. The session cookie and CSRF token come from a normal console sign-in made for this run.

Four runs: watch a finished investigation; start one (CSRF, case worker) while a worker processes it; start one with
no worker, so the watch window closes with RUN_ERROR; and one with no session (401).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.persistence.models import Case, Job
from app.settings import AppSettings
from app.web.console import SESSION_COOKIE
from benchmarks.intake import load_case, read_split
from protocols.ag_ui.routes import install_ag_ui
from tests.arm_a import ArmA, Browser, make_arm_a
from tests.conftest import ROOT
from tests.test_ag_ui import investigated, reference, work

CLIENT_VERSION = "1.0.4"
CLIENT_DIR = Path(os.environ.get("AG_UI_CLIENT_DIR", ""))
SCRIPT = Path(__file__).with_name("ag_ui_client.mjs")
EVIDENCE = ROOT / "security" / "evidence" / "ag-ui-client-run.txt"

pytestmark = [
    pytest.mark.interop,
    pytest.mark.skipif(os.environ.get("RUN_INTEROP") != "1", reason="opt-in: set RUN_INTEROP=1 (needs Node)"),
    pytest.mark.skipif(shutil.which("node") is None, reason="node isn't installed"),
    pytest.mark.skipif(
        not (CLIENT_DIR / "node_modules" / "@ag-ui" / "client").is_dir(), reason="AG_UI_CLIENT_DIR has no @ag-ui/client"
    ),
]


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_arm_c(arm: ArmA, scenario: str) -> int:
    """Each run needs its own case; `load_case` loads a benchmark item once, so each uses another scenario."""
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == arm.scenario(scenario))
    with arm.sessions() as s:
        return load_case(s, item, arm="C")[0].id


def client_run(
    base: str, case_id: int, thread: str, cookie: str, csrf: str = "", start: bool = False
) -> dict[str, Any]:
    env = {
        **os.environ,
        "AG_UI_CLIENT_DIR": str(CLIENT_DIR),
        "AGUI_URL": f"{base}/ag-ui/cases/{case_id}/runs",
        "AGUI_THREAD": thread,
        "AGUI_RUN_ID": uuid.uuid4().hex,
        "AGUI_START": "1" if start else "0",
        "AGUI_COOKIE": cookie,
        "AGUI_CSRF": csrf,
    }
    done = subprocess.run(  # a fixed command: our script, the pinned package, a local URL
        ["node", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return dict(json.loads(done.stdout.strip().splitlines()[-1]))


def jobs_for(arm: ArmA, case_id: int) -> int:
    with arm.sessions() as s:
        return int(s.scalar(select(func.count()).select_from(Job).where(Job.case_id == case_id)) or 0)


def test_the_official_ag_ui_client_reads_the_live_view(arm: ArmA) -> None:
    finished_case = investigated(arm)
    live_case = load_arm_c(arm, "K02")
    window_case = load_arm_c(arm, "K05")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    settings = AppSettings(database_url=arm.app_url, sim_clock=True)
    app = create_app(settings, arm.factory())
    install_ag_ui(app, AppSettings(database_url=arm.app_url), poll_seconds=0.1, watch_seconds=6.0)
    browser = Browser(TestClient(app))
    browser.login("agent.ana", arm.password, landing="Points queue")
    cookie = f"{SESSION_COOKIE}={browser.client.cookies.get(SESSION_COOKIE)}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)

    stop = threading.Event()

    def keep_working() -> None:
        while not stop.is_set():
            work(arm)
            time.sleep(0.2)

    try:
        watched = client_run(base, finished_case, reference(arm, finished_case), cookie)
        worker = threading.Thread(target=keep_working, daemon=True)
        worker.start()
        started = client_run(base, live_case, reference(arm, live_case), cookie, browser.csrf, start=True)
        stop.set()
        worker.join(timeout=10)
        windowed = client_run(base, window_case, reference(arm, window_case), cookie, browser.csrf, start=True)
        anonymous = client_run(base, finished_case, reference(arm, finished_case), "")
    finally:
        stop.set()
        server.should_exit = True
        thread.join(timeout=10)

    with arm.sessions() as s:
        live_status = s.get(Case, live_case).status  # type: ignore[union-attr]
    lines = [
        "AG-UI live view against @ag-ui/client (an independent client; spec G.5, Appendix C M11)",
        f"Date: {datetime.now(UTC).date().isoformat()}",
        "Command: $env:RUN_INTEROP='1'; $env:AG_UI_CLIENT_DIR='<scratch>\\agui'; "
        "uv run pytest tests/interop/test_ag_ui_client.py -s",
        f"Client: {watched['client']} (HttpAgent, Node {watched['node']}); its own SSE parser, schemas, order checks",
        "Server: protocols/ag_ui/ on ag-ui-protocol 1.0.0, AG-UI 1.0, HTTP POST + SSE, 127.0.0.1; synthetic cases",
        "Session: a console sign-in (agent.ana) made for this run; cookie and CSRF passed through the environment",
        "",
        f"1. Watch a finished run: events = {watched['types']}; RUN_ERROR = {watched['runError']}; "
        f"failure = {watched['failed']}",
        f"2. Start a run (CSRF, case worker, worker running): events = {started['types']}; "
        f"RUN_ERROR = {started['runError']}; failure = {started['failed']}; jobs for the case = "
        f"{jobs_for(arm, live_case)}; case status after = {live_status}",
        f"3. Start with no worker, 6 s window: events = {windowed['types']}; RUN_ERROR = {windowed['runError']}; "
        f"failure = {windowed['failed']}",
        f"4. No session: events = {anonymous['types']}; failure = {anonymous['failed']}",
    ]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    assert watched["client"] == f"@ag-ui/client@{CLIENT_VERSION}"
    assert watched["failed"] is None and watched["runError"] is None
    assert watched["types"][0] == "RUN_STARTED" and watched["types"][-1] == "RUN_FINISHED"
    assert started["failed"] is None and started["types"][-1] == "RUN_FINISHED" and jobs_for(arm, live_case) == 1
    assert windowed["runError"] is not None and windowed["runError"]["code"] == "watch_window_ended"
    assert "RUN_FINISHED" not in windowed["types"]
    assert anonymous["failed"] is not None and "401" in anonymous["failed"] and anonymous["types"] == []
