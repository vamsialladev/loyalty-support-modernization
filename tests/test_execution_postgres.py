"""Execution on real PostgreSQL, as the runtime role, against the mock API on real PostgreSQL (spec D, Appendix C).

Appendix C, Milestone 6: idempotency atomicity, concurrent execute, duplicate prevention, timeout-after-commit
reconciliation, lease recovery (approval invalidation is in `tests/test_write_path_postgres.py`). Plus the kill switch
under concurrent requests. Real threads and real locks; the crash tests use a real process over real HTTP.
Without the TEST_*_DATABASE_URL settings these are SKIPPED with that reason.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.domain.case_states import CaseState
from app.domain.customer_records import AdjustmentRequest, AdjustmentResult
from app.domain.roles import Identity, Role
from app.persistence.database import make_engine
from app.persistence.models import AdjustmentRequestRow, Case, ExecutionAttempt, Job
from app.ports.customer_systems import CustomerSystems, UncertainOutcome
from app.services import cases as svc
from app.services import jobs, kill_switch, policies
from app.services.instrumentation import events
from app.services.job_handlers import build_handlers
from app.services.write_path import SharedWritePath, attempts_of, load_request
from app.worker import Worker
from customer_shapes import CustomerShape
from tests.arm_a import ArmA
from tests.conftest import ARM_A_TOKEN, ROOT
from tests.pg_stack import APP_URL, MOCK_URL, clear_cases, make_pg_arm, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]
WP = SharedWritePath(settle_seconds=0)
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)
SHAPE = CustomerShape.load("hg-demo")
K01_CASES = ("DV-001", "DV-012", "DV-034", "DV-037", "DV-038", "DV-039")
REASON = "Pausing while a data problem is checked."


@pytest.fixture(scope="module")
def pg(generated: Path) -> Iterator[tuple[ArmA, Engine]]:
    arm, owner = make_pg_arm(generated)
    yield arm, owner
    owner.dispose()


@pytest.fixture
def arm(pg: tuple[ArmA, Engine]) -> ArmA:
    arm_, owner = pg
    clear_cases(owner)
    engine = make_engine(MOCK_URL)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM adjustments"))
        conn.execute(text("DELETE FROM idempotency_records"))
        conn.execute(text("DELETE FROM ledger_entries WHERE entry_id LIKE 'L-ADJ-%'"))
    engine.dispose()
    with arm_.sessions() as s:
        kill_switch.set_engaged(s, ADMIN, False, "A clean start for this test.")
    return arm_


def fresh(arm: ArmA, sim_time: str | None = None, fault: str | None = None) -> CustomerSystems:
    """An adapter with its own client, so threads share nothing but the mock API and its database."""
    client = TestClient(arm.mock_client.app, base_url="http://mock")
    return MockCustomerApiAdapter(
        "http://mock", ARM_A_TOKEN, SHAPE, client=client, sim_time=sim_time, fault=fault, sleep=lambda _: None
    )


def prepared(
    arm: ArmA, s: Session, case_id: str = "DV-001", *, approve: bool = True
) -> tuple[Case, AdjustmentRequestRow]:
    facts = arm.labels[case_id]["facts"]
    member, stay = facts["claimant"], facts["claimed_stay_ids"][0]
    (case,) = arm.load(s, case_id)
    who, systems = arm.who("agent.ana"), arm.systems(case.received_at_utc)
    svc.start_work(s, who, case)
    svc.attach_member(s, who, case, systems, member)
    svc.attach_stay(s, who, case, systems, member, stay)
    svc.attach_ledger(s, who, case, systems, member, show_older=True)
    svc.attach_policy(s, who, case, arm.index, "missing-points-requests#3")
    row = svc.request_adjustment(s, who, case, arm.rules)
    if approve:
        assert WP.decide(s, arm.who("supervisor.sam"), row.id, systems, approve=True, reason="").status == "approved"
    return case, row


def upstream_credits(arm: ArmA, stay: str | None = None) -> list[tuple[str, int]]:
    engine = make_engine(MOCK_URL)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT stay_id, points FROM ledger_entries WHERE kind = 'adjustment'")).all()
    engine.dispose()
    return [(r[0], r[1]) for r in rows if stay is None or r[0] == stay]


def run_threads(count: int, target: Callable[[int], None]) -> list[BaseException]:
    errors: list[BaseException] = []
    start = threading.Barrier(count)

    def wrapped(index: int) -> None:
        try:
            start.wait()
            target(index)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(180)
    return errors


# ---------- concurrent execute ----------


def test_ten_concurrent_executes_of_one_approval_credit_once(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
    outcomes: list[str] = []
    who = arm.who("supervisor.sam")

    def execute(_i: int) -> None:
        with arm.sessions() as s:
            try:
                outcomes.append(WP.execute(s, who, request_id, fresh(arm, received)).status)
            except svc.WorkflowError:
                outcomes.append("moved_on")

    assert run_threads(10, execute) == []
    counts = Counter(outcomes)
    assert counts["applied"] == 1, counts
    assert set(counts) <= {"applied", "in_flight", "moved_on"}, counts
    assert len(upstream_credits(arm, stay)) == 1
    with arm.sessions() as s:
        reread = s.get(AdjustmentRequestRow, request_id)
        assert reread is not None and reread.status == "executed"
        attempts = attempts_of(s, reread)
        assert [a.outcome for a in attempts] == ["applied"] and len({a.idempotency_key for a in attempts}) == 1


def test_ten_concurrent_clicks_queue_one_job_and_one_credit(arm: ArmA) -> None:
    with arm.sessions() as s:
        _case, row = prepared(arm, s)
        request_id, stay = row.id, row.stay_id
    who = arm.who("supervisor.sam")

    def click(_i: int) -> None:
        with arm.sessions() as s:
            WP.request_execution(s, who, request_id)

    assert run_threads(10, click) == []
    with arm.sessions() as s:
        assert len(s.scalars(select(Job)).all()) == 1
    Worker(arm.sessions, build_handlers(WP, lambda t: fresh(arm, t))).drain()
    assert len(upstream_credits(arm, stay)) == 1
    with arm.sessions() as s:
        assert load_request(s, request_id)[1].status == CaseState.RESOLVED


def test_concurrent_events_on_one_case_number_their_steps_without_a_gap(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, _row = prepared(arm, s, approve=False)
        case_id = case.id
    who = arm.who("agent.ana")

    def note(i: int) -> None:
        with arm.sessions() as s:
            found = s.get(Case, case_id)
            assert found is not None
            svc.add_note(s, who, found, f"note {i}")

    assert run_threads(12, note) == []
    with arm.sessions() as s:
        found = s.get(Case, case_id)
        assert found is not None
        steps = [e.step for e in events(s, found)]
        assert steps == list(range(1, len(steps) + 1))


# ---------- duplicate prevention ----------


def two_approved_cases_for_one_stay(arm: ArmA) -> tuple[int, int, str, str]:
    with arm.sessions() as s:
        first, first_row = prepared(arm, s)
        req = svc.requests_of(s, first)[0]
        phoned = svc.IntakeRequest(req.received_at_utc, "phone_note", req.text, req.sender_email)
        second = svc.create_case(s, arm.who("agent.ben"), phoned)
        who, systems = arm.who("agent.ben"), arm.systems(first.received_at_utc)
        facts = arm.labels["DV-001"]["facts"]
        member, stay = facts["claimant"], facts["claimed_stay_ids"][0]
        svc.start_work(s, who, second)
        svc.attach_member(s, who, second, systems, member)
        svc.attach_stay(s, who, second, systems, member, stay)
        svc.attach_ledger(s, who, second, systems, member, show_older=True)
        svc.attach_policy(s, who, second, arm.index, "missing-points-requests#3")
        second_row = svc.request_adjustment(s, who, second, arm.rules)
        WP.decide(s, arm.who("supervisor.sky"), second_row.id, systems, approve=True, reason="")
        return first_row.id, second_row.id, first.received_at_utc, stay


def race_two(arm: ArmA, first: int, second: int, received: str) -> list[str]:
    outcomes: list[str] = []
    people = [arm.who("supervisor.sam"), arm.who("supervisor.sky")]

    def execute(i: int) -> None:
        with arm.sessions() as s:
            outcomes.append(WP.execute(s, people[i], (first, second)[i], fresh(arm, received)).status)

    assert run_threads(2, execute) == []
    return outcomes


def test_two_approvals_racing_for_one_stay_credit_once(arm: ArmA) -> None:
    """D10, at once. Different approvals mean different keys, so upstream idempotency can't help: it's the app's job."""
    first, second, received, stay = two_approved_cases_for_one_stay(arm)
    outcomes = race_two(arm, first, second, received)
    assert sorted(outcomes) == ["applied", "refused_duplicate"], outcomes
    assert len(upstream_credits(arm, stay)) == 1


def test_the_database_holds_even_if_the_duplicate_check_has_a_bug(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    """The check across cases is switched off here. Only the partial unique index stands between two credits."""
    first, second, received, stay = two_approved_cases_for_one_stay(arm)
    monkeypatch.setattr(SharedWritePath, "_duplicate", lambda *_args: None)
    outcomes = race_two(arm, first, second, received)
    assert len(upstream_credits(arm, stay)) == 1, outcomes
    assert sorted(outcomes) == ["applied", "refused_duplicate"], outcomes
    with arm.sessions() as s:
        refused = next(
            r for r in (s.get(AdjustmentRequestRow, i) for i in (first, second)) if r and r.status != "executed"
        )
        assert refused.status == "refused_duplicate"
        assert load_request(s, refused.id)[1].status == CaseState.ESCALATED


# ---------- idempotency atomicity and timeout after commit ----------


class SubmitFault:
    """Reads go through normally; the submission carries a mock API fault, once."""

    def __init__(self, reads: CustomerSystems, faulty: CustomerSystems) -> None:
        self.reads, self.faulty, self.used = reads, faulty, False
        self.keys: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.reads, name)

    def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
        self.keys.append(key)
        if not self.used:
            self.used = True
            return self.faulty.submit_adjustment(request, key)
        return self.reads.submit_adjustment(request, key)


class LookupFails(SubmitFault):
    """As above, and the status lookup can't get through, so the case stays unknown."""

    def find_adjustment(self, key: str) -> AdjustmentResult | None:
        raise UncertainOutcome("lookup down", code="timeout")


def worker_with_fault(arm: ArmA, received: str, fault: str) -> tuple[Worker, SubmitFault]:
    systems = SubmitFault(fresh(arm, received), fresh(arm, received, fault))
    return Worker(arm.sessions, build_handlers(WP, lambda _t: systems)), systems  # type: ignore[arg-type,return-value]


def make_due(arm: ArmA) -> None:
    with arm.sessions() as s:
        s.execute(text("UPDATE jobs SET run_after_utc = '2000-01-01T00:00:00Z' WHERE status = 'queued'"))
        s.commit()


def test_timeout_after_commit_is_reconciled_with_one_credit(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
        WP.request_execution(s, arm.who("supervisor.sam"), request_id)
    worker, systems = worker_with_fault(arm, received, "commit_then_lost")
    worker.drain()
    with arm.sessions() as s:
        reread, found = load_request(s, request_id)
        assert found.status == CaseState.RESOLVED and reread.status == "executed"
        assert [a.outcome for a in attempts_of(s, reread)] == ["unknown", "applied"]
        actions = [e.action for e in events(s, found)]
        assert actions.index("execution_unknown") < actions.index("reconciled_applied")
    assert len(systems.keys) == 1, "reconciled by key; never submitted again"
    assert len(upstream_credits(arm, stay)) == 1


def test_a_failure_before_upstream_commit_writes_nothing_and_a_retry_applies_once(arm: ArmA) -> None:
    """Idempotency atomicity across both systems: the crash leaves no partial record, and the same key then applies."""
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
        WP.request_execution(s, arm.who("supervisor.sam"), request_id)
    worker, systems = worker_with_fault(arm, received, "crash_before_commit")
    worker.drain()
    assert upstream_credits(arm, stay) == [], "nothing committed upstream"
    with arm.sessions() as s:  # two lookups found nothing; the resubmission waits for its backoff
        assert load_request(s, request_id)[1].status == CaseState.APPROVED
    for _ in range(6):
        make_due(arm)
        worker.drain()
    with arm.sessions() as s:
        reread, found = load_request(s, request_id)
        assert found.status == CaseState.RESOLVED and reread.status == "executed"
    assert len(systems.keys) == 2 and len(set(systems.keys)) == 1, "the same key both times"
    assert len(upstream_credits(arm, stay)) == 1


def test_two_workers_racing_a_reconciliation_settle_it_once(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
        blocked = LookupFails(fresh(arm, received), fresh(arm, received, "commit_then_lost"))
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, blocked).status == "unknown"
    outcomes: list[str] = []

    def reconcile(_i: int) -> None:
        with arm.sessions() as s:
            outcomes.append(WP.reconcile_as_system(s, request_id, fresh(arm, received)).status)

    assert run_threads(6, reconcile) == []
    assert "applied" in outcomes and set(outcomes) <= {"applied", "in_flight"}, outcomes
    with arm.sessions() as s:
        found = load_request(s, request_id)[1]
        assert found.status == CaseState.RESOLVED
        assert [e.action for e in events(s, found)].count("adjustment_executed") == 1
    assert len(upstream_credits(arm, stay)) == 1


# ---------- lease recovery: a real process dies ----------


@pytest.fixture(scope="module")
def mock_server(pg: tuple[ArmA, Engine], tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("MOCK_API_")}
    env |= {
        "MOCK_API_DATABASE_URL": MOCK_URL,
        "MOCK_API_TOKEN": ARM_A_TOKEN,
        "MOCK_API_SIM_CLOCK": "true",
    }
    log = (tmp_path_factory.mktemp("mock-server") / "mock.log").open("wb")
    command = [sys.executable, "-m", "uvicorn", "--factory", "mock_customer_api.api:create_app", "--port", str(port)]
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/healthz", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    yield url
    process.terminate()
    process.wait(timeout=30)
    log.close()


def die_during_execution(moment: str, mock_url: str) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "tests.crash_execution", moment, APP_URL, mock_url, ARM_A_TOKEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=os.environ.copy(),
    )
    assert done.returncode == 9, done.stdout[-400:] + done.stderr[-800:]


@pytest.mark.parametrize(("moment", "submissions"), [("after", 1), ("before", 1)])
def test_a_worker_killed_during_execution_is_recovered_with_one_credit(
    arm: ArmA, mock_server: str, moment: str, submissions: int
) -> None:
    """`after`: the platform committed and the worker died before recording it. `before`: it died about to submit.
    Either way the next worker can't know which, so it reconciles first and the stay ends with exactly one credit."""
    with arm.sessions() as s:
        _case, row = prepared(arm, s)
        request_id, stay = row.id, row.stay_id
        WP.request_execution(s, arm.who("supervisor.sam"), request_id)
    die_during_execution(moment, mock_server)

    with arm.sessions() as s:
        reread, found = load_request(s, request_id)
        assert found.status == CaseState.EXECUTING and reread.status == "executing", "the dead process recorded nothing"
        assert s.scalars(select(Job)).one().status == jobs.RUNNING
    assert len(upstream_credits(arm, stay)) == (1 if moment == "after" else 0)

    time.sleep(2.2)  # its lease was one second
    next_worker = Worker(arm.sessions, build_handlers(WP, lambda t: fresh(arm, t)))
    for _ in range(8):
        make_due(arm)
        next_worker.drain()
    with arm.sessions() as s:
        reread, found = load_request(s, request_id)
        assert found.status == CaseState.RESOLVED, [e.action for e in events(s, found)]
        actions = [e.action for e in events(s, found)]
        assert "execution_unknown" in actions
        unknown = s.scalars(select(ExecutionAttempt).where(ExecutionAttempt.error_code == "worker_lost")).all()
        assert len(unknown) == 1
        assert len({a.idempotency_key for a in attempts_of(s, reread)}) == 1
    assert len(upstream_credits(arm, stay)) == submissions


# ---------- the kill switch under concurrency ----------


def test_turning_the_switch_off_waits_for_a_claim_in_progress_then_stops_new_ones(arm: ArmA) -> None:
    claim = arm.sessions()
    assert kill_switch.is_engaged_for_claim(claim) is False  # a claim in progress holds the shared lock
    finished = threading.Event()

    def turn_off() -> None:
        with arm.sessions() as s:
            kill_switch.set_engaged(s, ADMIN, True, REASON)
        finished.set()

    thread = threading.Thread(target=turn_off)
    thread.start()
    assert not finished.wait(1.0), "it must wait for the claim that already passed the check"
    claim.commit()
    claim.close()
    assert finished.wait(30), "and go through as soon as that claim ends"
    thread.join(30)
    with arm.sessions() as s:
        assert kill_switch.is_engaged_for_claim(s) is True


def test_while_off_twenty_concurrent_requests_change_nothing_and_reads_keep_working(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
        member = row.member_number
        kill_switch.set_engaged(s, ADMIN, True, REASON)
    who = arm.who("supervisor.sam")
    refused: list[int] = []
    read: list[int] = []

    def act(i: int) -> None:
        with arm.sessions() as s:
            if i % 2 == 0:
                with pytest.raises(svc.WorkflowError, match="switched off"):
                    WP.request_execution(s, who, request_id)
                refused.append(i)
            else:
                # Read-only investigation: customer records and policy search.
                systems = fresh(arm, received)
                assert systems.get_member(member).member_number == member
                assert systems.get_ledger(member) is not None
                assert policies.search(s, "hg-demo", "claim", date(2026, 8, 1))
                read.append(i)

    assert run_threads(20, act) == []
    assert (len(refused), len(read)) == (10, 10)
    with arm.sessions() as s:
        assert s.scalars(select(Job)).first() is None
        assert load_request(s, request_id)[1].status == CaseState.APPROVED
    assert upstream_credits(arm, stay) == []


def test_the_switch_turned_off_under_load_stops_submissions_and_holds_the_rest(arm: ArmA) -> None:
    """Six jobs, three workers, the switch thrown as the first submission happens. What passed the last check can land
    (the stated limit: at most one per worker). Everything else waits, with no attempts used, and nothing is lost."""
    with arm.sessions() as s:
        for case_id in K01_CASES:
            _case, row = prepared(arm, s, case_id)
            WP.request_execution(s, arm.who("supervisor.sam"), row.id)
    switched, started = threading.Event(), threading.Event()
    lock = threading.Lock()
    during: list[bool] = []

    class Watched:
        def __init__(self, inner: CustomerSystems) -> None:
            self.inner = inner

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

        def submit_adjustment(self, request: AdjustmentRequest, key: str) -> AdjustmentResult:
            with lock:
                during.append(switched.is_set())
            started.set()
            return self.inner.submit_adjustment(request, key)

    def systems(sim_time: str | None) -> Any:
        return Watched(fresh(arm, sim_time))

    def work(i: int) -> None:
        if i == 3:
            assert started.wait(120)
            with arm.sessions() as s:
                kill_switch.set_engaged(s, ADMIN, True, REASON)
            switched.set()
            return
        Worker(arm.sessions, build_handlers(WP, systems)).drain(limit=30)

    assert run_threads(4, work) == []
    late = sum(during)
    assert late <= 3, f"{late} submissions began after the switch was off; the limit is one in flight per worker"
    with arm.sessions() as s:
        resolved = s.scalars(select(Case).where(Case.status == CaseState.RESOLVED.value)).all()
        approved = s.scalars(select(Case).where(Case.status == CaseState.APPROVED.value)).all()
        assert len(resolved) + len(approved) == len(K01_CASES)
        assert len(upstream_credits(arm)) == len(resolved) == len(during)
        held = s.scalars(select(Job).where(Job.status == jobs.QUEUED)).all()
        assert len(held) == len(approved) and all(j.attempts == 0 and j.last_error == "kill_switch" for j in held)
        kill_switch.set_engaged(s, ADMIN, False, "The data problem was a false alarm.")
    make_due(arm)
    Worker(arm.sessions, build_handlers(WP, lambda t: fresh(arm, t))).drain(limit=30)
    with arm.sessions() as s:
        assert s.scalars(select(Case).where(Case.status != CaseState.RESOLVED.value)).first() is None
    assert len(upstream_credits(arm)) == len(K01_CASES), "each exactly once"


def test_reconciliation_still_settles_a_case_while_the_switch_is_off(arm: ArmA) -> None:
    with arm.sessions() as s:
        case, row = prepared(arm, s)
        request_id, received, stay = row.id, case.received_at_utc, row.stay_id
        blocked = LookupFails(fresh(arm, received), fresh(arm, received, "commit_then_lost"))
        assert WP.execute(s, arm.who("supervisor.sam"), request_id, blocked).status == "unknown"
        assert load_request(s, request_id)[1].status == CaseState.EXECUTION_UNKNOWN
        WP.request_execution(s, arm.who("supervisor.sam"), request_id)  # a status check, allowed while the switch is on
        kill_switch.set_engaged(s, ADMIN, True, REASON)
    Worker(arm.sessions, build_handlers(WP, lambda t: fresh(arm, t))).drain()
    with arm.sessions() as s:
        assert load_request(s, request_id)[1].status == CaseState.RESOLVED
    assert len(upstream_credits(arm, stay)) == 1
