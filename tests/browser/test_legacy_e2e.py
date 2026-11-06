"""Appendix C, Milestone 5: legacy arm A completes a case end to end in the browser (Playwright, Chromium).

Two ways to run:
- **Offline (default):** the test starts the mock customer API and the app with uvicorn on free local ports, both on
  SQLite copies, the mock seeded from a fresh generation. Part of `scripts\\test.ps1`.
- **Against the Compose stack:** set `E2E_BASE_URL`, `E2E_MOCK_API_URL`, `E2E_DATABASE_URL` (host URL of the app
  database), `E2E_MOCK_API_TOKEN` and `E2E_DEMO_PASSWORD`; `scripts\\compose_check.ps1 -Browser` does this.

Skipped, with the reason, when Chromium is not installed (`uv run playwright install chromium`).
The test is the evaluator here, so it may read labels to choose cases; the app never does.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.browser

playwright_api = pytest.importorskip("playwright.sync_api")


@dataclass
class Stack:
    base_url: str
    mock_url: str
    database_url: str
    token: str
    password: str
    datasets: Path
    labels: dict[str, Any]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str, proc: subprocess.Popen[bytes], log: Path, seconds: float = 180) -> None:
    """Wait for a server, allowing for a slow machine. A real failure reports the server's own log."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early (code {proc.returncode}): {log.read_text(errors='replace')}")
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not come up in {seconds:.0f} s: {log.read_text(errors='replace')}")


@pytest.fixture(scope="module")
def chromium() -> Iterator[Any]:
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # the executable is missing or cannot start
            pytest.skip(f"Chromium is not available ({type(exc).__name__}); run: uv run playwright install chromium")
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def stack(
    request: pytest.FixtureRequest, mock_template: dict[str, Any], tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Stack]:
    if os.environ.get("E2E_BASE_URL"):
        yield Stack(
            os.environ["E2E_BASE_URL"].rstrip("/"),
            os.environ["E2E_MOCK_API_URL"].rstrip("/"),
            os.environ["E2E_DATABASE_URL"],
            os.environ["E2E_MOCK_API_TOKEN"],
            os.environ["E2E_DEMO_PASSWORD"],
            mock_template["datasets"],
            mock_template["labels"],
        )
        return

    from alembic import command
    from alembic.config import Config

    from app.adapters.local_demo_identity import ensure_demo_users
    from app.persistence.database import make_engine, make_sessions
    from app.services.policies import load_policy_set
    from tests.conftest import ROOT

    tmp = tmp_path_factory.mktemp("e2e")
    shutil.copyfile(mock_template["path"], tmp / "mock.db")
    app_url = f"sqlite:///{(tmp / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", app_url)
    command.upgrade(cfg, "head")
    password, token = "e2e-" + os.urandom(9).hex(), "e2e-token-" + os.urandom(6).hex()
    with make_sessions(make_engine(app_url))() as s:
        ensure_demo_users(s, password)
        load_policy_set(s, "hg-demo", ROOT / "policies/hg-demo")

    mock_port, app_port = _free_port(), _free_port()
    base_env = {k: v for k, v in os.environ.items() if not k.startswith(("MOCK_API_", "DATABASE_URL"))}
    mock_env = base_env | {
        "MOCK_API_DATABASE_URL": f"sqlite:///{(tmp / 'mock.db').as_posix()}",
        "MOCK_API_TOKEN": token,
        "MOCK_API_SIM_CLOCK": "true",
    }
    seeded_faults = getattr(request.module, "seeded_fault_rules", None)  # a module may ask for a seeded failure
    if seeded_faults is not None:
        rules = tmp / "fault_rules.yaml"
        rules.write_text(seeded_faults(mock_template["labels"]), encoding="utf-8")
        mock_env |= {"MOCK_API_FAULTS": "true", "MOCK_API_FAULT_RULES_FILE": str(rules)}
    app_env = base_env | {
        "DATABASE_URL": app_url,
        "MOCK_API_URL": f"http://127.0.0.1:{mock_port}",
        "MOCK_API_TOKEN": token,
        "MOCK_API_SIM_CLOCK": "true",
    }
    uvicorn = [sys.executable, "-m", "uvicorn", "--factory", "--host", "127.0.0.1", "--log-level", "warning"]
    mock_log, app_log = tmp / "mock.log", tmp / "app.log"
    procs = []
    logs = []
    try:
        for target, port, env, log in (
            ("mock_customer_api.api:create_app", mock_port, mock_env, mock_log),
            ("app.main:create_app", app_port, app_env, app_log),
        ):
            output = log.open("wb")  # a file, not a pipe: nothing can block on a full pipe, and nothing is lost
            logs.append(output)
            procs.append(
                subprocess.Popen(
                    [*uvicorn, target, "--port", str(port)], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT
                )
            )
        _wait(f"http://127.0.0.1:{mock_port}/healthz", procs[0], mock_log)
        _wait(f"http://127.0.0.1:{app_port}/healthz", procs[1], app_log)
        worker_log = tmp / "worker.log"
        output = worker_log.open("wb")
        logs.append(output)
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "app.worker"], cwd=ROOT, env=app_env, stdout=output, stderr=subprocess.STDOUT
            )
        )
        yield Stack(
            f"http://127.0.0.1:{app_port}",
            f"http://127.0.0.1:{mock_port}",
            app_url,
            token,
            password,
            mock_template["datasets"],
            mock_template["labels"],
        )
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=30)
        for output in logs:
            output.close()


def load_dataset_case(stack: Stack, case_id: str) -> int:
    """Put one dataset case in the app's queue (the demo loader) and return its app case ID."""
    from sqlalchemy import select

    from app.persistence.database import make_engine, make_sessions
    from app.persistence.models import Case
    from benchmarks.intake import load_case, read_split

    with make_sessions(make_engine(stack.database_url))() as s:
        load_case(s, next(c for c in read_split("dev", stack.datasets) if c.case_id == case_id))
        case = s.scalars(select(Case).where(Case.source_ref == case_id).order_by(Case.id)).first()
        assert case is not None
        return case.id


def sign_in(page: Any, stack: Stack, username: str) -> None:
    page.goto(f"{stack.base_url}/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(stack.password)
    page.get_by_role("button", name="Sign in").click()
    playwright_api.expect(page.get_by_role("heading", name="Points queue")).to_be_visible()


def sign_out(page: Any) -> None:
    page.get_by_role("button", name="Sign out").click()
    playwright_api.expect(page.get_by_role("heading", name="Sign in")).to_be_visible()


def status(page: Any) -> Any:
    return page.get_by_test_id("case-status")


def test_legacy_arm_completes_a_case_end_to_end_in_the_browser(chromium: Any, stack: Stack) -> None:
    case_id = load_dataset_case(stack, "DV-001")  # K01: Clara Kowalski, BR-6638, 14,840 points owed
    expect = playwright_api.expect
    page = chromium.new_page()
    problems: list[str] = []  # console errors include Content-Security-Policy violations
    page.on("console", lambda msg: problems.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: problems.append(str(exc)))

    sign_in(page, stack, "agent.ana")
    expect(page.get_by_test_id("banner")).to_contain_text("SYNTHETIC DATA")
    page.goto(f"{stack.base_url}/cases/{case_id}")
    expect(page.get_by_text("Confirmation BR-6638")).to_be_visible()
    page.get_by_role("button", name="Start work").click()
    expect(status(page)).to_have_text("Investigating")

    # Screen 1 of 4: member search by exact name + email (the request gives no member number).
    page.get_by_role("link", name="Member search").click()
    page.get_by_label("First name").fill("Clara")
    page.get_by_label("Last name").fill("Kowalski")
    page.get_by_label("Email").fill("clara.kowalski4@example.com")
    assert page.evaluate("typeof window.htmx") == "object", "htmx did not load (blocked by the CSP?)"
    with page.expect_request(lambda r: "/member?" in r.url and r.headers.get("hx-request") == "true"):
        page.get_by_role("button", name="Search members").click()  # HTMX swaps the results in place
    expect(page.get_by_role("cell", name="GR-85640")).to_be_visible()
    page.get_by_role("button", name="Attach to case").click()
    expect(page.get_by_test_id("message")).to_have_text("Evidence attached to the case.")

    # Screen 2: stay search by exact confirmation within the member's stays.
    page.get_by_role("link", name="Stay search").click()
    expect(page.get_by_label("Member number")).to_have_value("GR-85640")
    page.get_by_label("Hotel confirmation number").fill("BR-6638")
    page.get_by_role("button", name="Search stays").click()
    page.get_by_role("button", name="Attach to case").click()

    # Screen 3: the ledger, expanded past the 90-day default to cover the November 2025 checkout.
    page.get_by_role("link", name="Ledger").click()
    page.get_by_label("Show older entries").check()
    page.get_by_role("button", name="Show ledger").click()
    expect(page.get_by_text("all entries")).to_be_visible()
    page.get_by_role("button", name="Attach this view to the case").click()

    # Screen 4: keyword policy search.
    page.get_by_role("link", name="Policy search").click()
    page.get_by_label("Keywords").fill("missing points")
    page.get_by_role("button", name="Search policies").click()
    page.get_by_role("button", name="Attach to case").first.click()

    expect(page.get_by_test_id("checklist-outcome")).to_have_text("adjust")
    expect(page.get_by_test_id("points-owed")).to_have_text("14840")
    page.get_by_role("button", name="Request adjustment of 14840 points").click()
    expect(status(page)).to_have_text("Pending approval")
    sign_out(page)

    sign_in(page, stack, "supervisor.sam")
    page.get_by_role("link", name="Approvals").click()
    page.get_by_role("row").filter(has_text="BR-6638").get_by_role("link").click()
    page.get_by_role("button", name="Approve").click()
    expect(status(page)).to_have_text("Approved")
    page.get_by_role("button", name="Execute adjustment").click()
    expect(page.get_by_test_id("message")).to_contain_text("Queued for the worker")
    # The worker does it; the page updates by itself through htmx (ADR-0055, D1). A slow machine gets a minute.
    expect(status(page)).to_have_text("Resolved", timeout=60_000)
    expect(page.get_by_test_id("resolution")).to_have_text("adjusted")
    adjustment_id = page.get_by_test_id("adjustment-id").first.inner_text()
    page.close()
    assert problems == []

    from app.adapters.mock_customer_api import MockCustomerApiAdapter
    from customer_shapes import CustomerShape

    upstream = MockCustomerApiAdapter(stack.mock_url, stack.token, CustomerShape.load("hg-demo"))
    credits = [e for e in upstream.get_ledger("GR-85640") if e.kind == "adjustment" and e.stay_id == "BR-6638"]
    assert [(e.points, e.entry_id) for e in credits] == [(14_840, f"L-{adjustment_id}")]


def test_a_supervisor_cannot_approve_an_adjustment_they_requested(chromium: Any, stack: Stack) -> None:
    other_k01 = sorted(
        cid
        for cid, lab in stack.labels.items()
        if lab["split"] == "dev" and lab["scenarios"] == ["K01"] and cid != "DV-001"
    )[0]
    lab = stack.labels[other_k01]
    member, stay = lab["claimant_member_number"], lab["facts"]["claimed_stay_ids"][0]
    case_id = load_dataset_case(stack, other_k01)
    expect = playwright_api.expect
    page = chromium.new_page()

    sign_in(page, stack, "supervisor.sam")  # a supervisor working a case as an agent would
    page.goto(f"{stack.base_url}/cases/{case_id}")
    page.get_by_role("button", name="Start work").click()
    page.get_by_role("link", name="Member search").click()
    page.get_by_label("Member number").fill(member)
    page.get_by_role("button", name="Search members").click()
    page.get_by_role("button", name="Attach to case").click()
    page.get_by_role("link", name="Stay search").click()
    page.get_by_label("Hotel confirmation number").fill(stay)
    page.get_by_role("button", name="Search stays").click()
    page.get_by_role("button", name="Attach to case").click()
    page.get_by_role("link", name="Ledger").click()
    page.get_by_label("Show older entries").check()
    page.get_by_role("button", name="Show ledger").click()
    # The page already shows the default 90-day view with its own attach button: wait for the swapped-in full view
    # first, or the click can attach the old one (the checklist then rightly refuses it, ADR-0050).
    expect(page.get_by_text("all entries")).to_be_visible()
    page.get_by_role("button", name="Attach this view to the case").click()
    page.get_by_role("link", name="Policy search").click()
    page.get_by_label("Keywords").fill("missing points")
    page.get_by_role("button", name="Search policies").click()
    page.get_by_role("button", name="Attach to case").first.click()
    expect(page.get_by_test_id("checklist-outcome")).to_have_text("adjust")
    page.get_by_role("button", name="Request adjustment", exact=False).click()
    expect(status(page)).to_have_text("Pending approval")

    expect(page.get_by_test_id("refusal")).to_contain_text("another supervisor must decide")
    expect(page.get_by_role("button", name="Approve")).to_have_count(0)

    # A forged POST with the page's own valid CSRF token is refused by the server too.
    csrf = page.locator('input[name="csrf"]').first.get_attribute("value")
    request_id = _pending_request_id(stack, case_id)
    forged = page.request.post(
        f"{stack.base_url}/adjustments/{request_id}/decide", form={"csrf": csrf or "", "decision": "approve"}
    )
    assert forged.status == 403
    page.reload()
    expect(status(page)).to_have_text("Pending approval")
    page.close()


def _pending_request_id(stack: Stack, case_id: int) -> int:
    from sqlalchemy import select

    from app.persistence.database import make_engine, make_sessions
    from app.persistence.models import AdjustmentRequestRow

    with make_sessions(make_engine(stack.database_url))() as s:
        return s.scalars(select(AdjustmentRequestRow.id).where(AdjustmentRequestRow.case_id == case_id)).one()
