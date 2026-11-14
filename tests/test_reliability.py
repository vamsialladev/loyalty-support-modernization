"""Reliability (OPS-05, ADR-0081): circuit breakers for the customer systems and the model provider, backpressure on
new investigations, and the adjustment-execution flag."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.adapters.circuit import CLOSED, HALF_OPEN, OPEN, CircuitBreaker, GuardedModel
from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.persistence.models import AdjustmentRequestRow, CaseEvent, ExecutionAttempt, Job
from app.ports.customer_systems import RecordNotFound, TemporarilyUnavailable
from app.ports.model_provider import ModelTurn, ProviderRejected, ProviderUnavailable
from app.services import conventional, jobs
from app.services.cases import WorkflowError
from app.services.write_path import EXECUTION_OFF_MESSAGE, SharedWritePath
from app.settings import AppSettings
from benchmarks.agents.conventional_scripted import ScriptedConventionalAgent
from benchmarks.intake import load_case, read_split
from tests.arm_a import SHAPE, ArmA, make_arm_a
from tests.conftest import ARM_A_TOKEN
from tests.test_api import Api


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


# ---------- the breaker itself ----------


def test_the_breaker_opens_after_repeated_failures_within_its_window() -> None:
    clock = Clock()
    breaker = CircuitBreaker("t", failure_threshold=3, window_seconds=10, cooldown_seconds=30, clock=clock)
    breaker.record_failure()
    breaker.record_failure()
    clock.now += 11  # the first two have left the window
    breaker.record_failure()
    assert breaker.state == CLOSED and breaker.allow()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == OPEN and not breaker.allow()
    assert breaker.retry_after_seconds() == pytest.approx(30)


def test_after_its_cooldown_one_trial_call_decides() -> None:
    clock = Clock()
    breaker = CircuitBreaker("t", failure_threshold=1, cooldown_seconds=30, clock=clock)
    breaker.record_failure()
    clock.now += 30
    assert breaker.state == HALF_OPEN
    assert breaker.allow() and not breaker.allow()  # one trial at a time
    breaker.record_failure()  # the trial failed: open for another cooldown
    assert breaker.state == OPEN and not breaker.allow()
    clock.now += 30
    assert breaker.allow()
    breaker.record_success()
    assert breaker.state == CLOSED and breaker.allow() and breaker.allow()


# ---------- the customer systems ----------


def _adapter(arm: ArmA, breaker: CircuitBreaker, fault: str | None = None) -> MockCustomerApiAdapter:
    return MockCustomerApiAdapter(
        "http://mock", ARM_A_TOKEN, SHAPE, client=arm.mock_client, fault=fault, sleep=lambda _: None, breaker=breaker
    )


def test_a_failing_customer_system_opens_the_breaker_and_calls_stop_going_out(arm: ArmA) -> None:
    breaker = CircuitBreaker("customer_api:test", failure_threshold=3, cooldown_seconds=60)
    failing = _adapter(arm, breaker, fault="unavailable")
    with pytest.raises(TemporarilyUnavailable):
        failing.get_member("GR-00001")  # three attempts (one call plus two retries), each a 503
    assert breaker.state == OPEN
    sent: list[str] = []
    healthy = _adapter(arm, breaker)
    original = arm.mock_client.request
    arm.mock_client.request = lambda *a, **k: sent.append(a[1]) or original(*a, **k)  # type: ignore[method-assign]
    try:
        with pytest.raises(TemporarilyUnavailable) as caught:
            healthy.get_member("GR-00001")
    finally:
        arm.mock_client.request = original  # type: ignore[method-assign]
    assert caught.value.code == "circuit_open" and sent == []  # refused here, nothing sent


def test_a_not_found_answer_is_the_system_working_and_never_opens_the_breaker(arm: ArmA) -> None:
    breaker = CircuitBreaker("customer_api:test", failure_threshold=1)
    adapter = _adapter(arm, breaker)
    for _ in range(3):
        with pytest.raises(RecordNotFound):
            adapter.get_member("GR-99999")
    assert breaker.state == CLOSED


def test_the_production_wiring_shares_one_breaker_per_customer_system() -> None:
    from app.services.systems import mock_systems_factory

    make = mock_systems_factory(AppSettings(database_url="sqlite://", mock_api_url="http://mock-a:8020"))
    first, second = make(None), make(None)
    assert isinstance(first, MockCustomerApiAdapter) and isinstance(second, MockCustomerApiAdapter)
    assert first.breaker is not None and first.breaker is second.breaker


# ---------- the model provider ----------


class _Model:
    name, model_id, is_mock = "anthropic", "claude-test", False

    def __init__(self, error: Exception | None = None) -> None:
        self.error, self.calls = error, 0

    def complete(self, *_a: Any, **_k: Any) -> ModelTurn:
        self.calls += 1
        if self.error:
            raise self.error
        return ModelTurn("end_turn")

    def read_image(self, *_a: Any, **_k: Any) -> Any:
        raise NotImplementedError


def test_a_model_outage_opens_the_breaker_and_later_calls_fail_at_once() -> None:
    inner = _Model(ProviderUnavailable("overloaded"))
    guarded = GuardedModel(inner, CircuitBreaker("model:test", failure_threshold=2))
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            guarded.complete("s", [], [], 10, 1)
    with pytest.raises(ProviderUnavailable, match="circuit open"):
        guarded.complete("s", [], [], 10, 1)
    assert inner.calls == 2  # the third never reached the provider
    assert (guarded.name, guarded.model_id, guarded.is_mock) == ("anthropic", "claude-test", False)


def test_a_rejected_request_means_the_provider_is_up() -> None:
    clock = Clock()
    breaker = CircuitBreaker("model:test", failure_threshold=1, cooldown_seconds=5, clock=clock)
    breaker.record_failure()
    clock.now += 5
    guarded = GuardedModel(_Model(ProviderRejected("bad key")), breaker)
    with pytest.raises(ProviderRejected):
        guarded.complete("s", [], [], 10, 1)  # the half-open trial: answered, if only to refuse
    assert breaker.state == CLOSED


# ---------- backpressure ----------


def test_new_investigations_are_refused_past_the_limit_and_the_case_is_unchanged(
    arm: ArmA, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_QUEUED_INVESTIGATIONS", "1")
    cases = [c for c in read_split("dev", arm.datasets) if c.case_id in ("DV-001", "DV-002")]
    with arm.sessions() as s:
        first = load_case(s, cases[0], arm="B")[0]
        second = load_case(s, cases[1], arm="B")[0]
        conventional.start_investigation(s, arm.who("agent.ana"), first)
        with pytest.raises(jobs.Busy) as busy:
            conventional.start_investigation(s, arm.who("agent.ana"), second)
        s.refresh(second)
        assert second.status == "New" and second.assigned_to is None
        assert busy.value.retry_after_seconds > 0
        queued = s.scalars(select(Job).where(Job.kind == conventional.INVESTIGATE_JOB)).all()
        assert [j.case_id for j in queued] == [first.id]
        second_id = second.id
    api = Api(arm, "agent.ana")
    resp = api.post(f"/cases/{second_id}/investigation")
    assert resp.status_code == 503, resp.text
    assert resp.json()["code"] == "busy" and int(resp.headers["Retry-After"]) > 0


def test_work_already_queued_is_never_refused(arm: ArmA, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only new investigations wait. A case already being investigated asks again and gets its own job back."""
    monkeypatch.setenv("MAX_QUEUED_INVESTIGATIONS", "1")
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        case = load_case(s, item, arm="B")[0]
        job = conventional.start_investigation(s, arm.who("agent.ana"), case)
        assert conventional.start_investigation(s, arm.who("agent.ana"), case).id == job.id


# ---------- the execution flag ----------


def test_with_execution_off_an_approved_adjustment_is_held_and_nothing_is_sent(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        case = load_case(s, item, arm="B")[0]
        off = SharedWritePath("hg-demo", execution_enabled=False)
        ScriptedConventionalAgent(s, arm.factory(), write_path=off).run(case)
        s.refresh(case)
        assert case.status == "Approved"  # approved, then held: never Executing, never Resolved
        request_id = s.scalar(select(AdjustmentRequestRow.id).where(AdjustmentRequestRow.case_id == case.id))
        assert request_id is not None
        with pytest.raises(WorkflowError, match="switched off"):
            off.request_execution(s, arm.who("supervisor.sam"), request_id)
        attempts = s.scalars(select(ExecutionAttempt).where(ExecutionAttempt.adjustment_request_id == request_id))
        actions = {e.action for e in s.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id))}
    assert list(attempts) == []  # no attempt means no call to the loyalty platform
    assert "execution_started" not in actions and "adjustment_executed" not in actions
    assert "nothing was sent" in EXECUTION_OFF_MESSAGE
    # With execution on, the same case resolves (tests/test_ops_monitoring.py and the scripted-agent tests).


def test_the_flag_is_on_unless_set_otherwise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.delenv("FEATURE_ADJUSTMENT_EXECUTION", raising=False)
    assert AppSettings.from_env().feature_adjustment_execution is True
    monkeypatch.setenv("FEATURE_ADJUSTMENT_EXECUTION", "false")
    assert AppSettings.from_env().feature_adjustment_execution is False
    production = (Path(__file__).resolve().parent.parent / "config/environments/production.env").read_text()
    assert "FEATURE_ADJUSTMENT_EXECUTION=false" in production
