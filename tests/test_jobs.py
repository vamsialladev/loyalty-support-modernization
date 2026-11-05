"""The job queue and worker loop, on SQLite with a test clock (spec B.12; JOB-01 to JOB-03).

Concurrency, real leases and a real process death are in `tests/test_worker_postgres.py`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app import correlation
from app.domain.roles import Identity, Role
from app.persistence.database import make_engine, make_sessions
from app.persistence.models import Job, SystemEvent
from app.services import jobs
from app.services.jobs import ClaimedJob, Defer, GiveUp, Retry
from app.worker import Worker, main
from tests.conftest import ROOT

START = "2026-11-04T12:00:00Z"
ADMIN = Identity(1, "admin.ada", "Ada", Role.ADMINISTRATOR)


class TestClock:
    __test__ = False

    def __init__(self) -> None:
        self.now = START

    def __call__(self, _s: Session) -> str:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = jobs.later(self.now, seconds)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = make_engine(url)
    yield make_sessions(engine)
    engine.dispose()


@pytest.fixture
def clock() -> TestClock:
    return TestClock()


def add(factory: sessionmaker[Session], clock: TestClock, kind: str = "work", **kw: Any) -> int:
    with factory() as s:
        job = jobs.enqueue(s, kind, {"thing": 1}, clock=clock, **kw)
        s.commit()
        return job.id


def row(factory: sessionmaker[Session], job_id: int) -> Job:
    with factory() as s:
        found = s.get(Job, job_id)
        assert found is not None
        return found


def actions(factory: sessionmaker[Session]) -> list[str]:
    with factory() as s:
        return [e.action for e in s.scalars(select(SystemEvent).order_by(SystemEvent.id))]


# ---------- enqueue ----------


def test_a_job_commits_or_rolls_back_with_its_caller(factory: sessionmaker[Session], clock: TestClock) -> None:
    with factory() as s:
        jobs.enqueue(s, "work", {}, clock=clock)
        s.rollback()
        assert s.scalar(text("select count(*) from jobs")) == 0


def test_one_active_job_per_kind_and_case(factory: sessionmaker[Session], clock: TestClock) -> None:
    first = add(factory, clock)
    assert add(factory, clock) == first
    assert add(factory, clock, kind="other") != first
    with factory() as s:
        assert s.scalar(text("select count(*) from jobs")) == 2


def test_the_database_refuses_a_second_active_job_even_past_the_code(
    factory: sessionmaker[Session], clock: TestClock
) -> None:
    from sqlalchemy.exc import IntegrityError

    add(factory, clock)
    with factory() as s, pytest.raises(IntegrityError):
        s.add(
            Job(
                kind="work",
                dedupe_key="work:system",
                payload={},
                status="queued",
                attempts=0,
                max_attempts=1,
                run_after_utc=START,
                created_at_utc=START,
            )
        )
        s.flush()


def test_a_finished_job_can_be_queued_again(factory: sessionmaker[Session], clock: TestClock) -> None:
    first = add(factory, clock)
    Worker(factory, {"work": lambda _s, _j: None}, clock=clock).drain()
    assert row(factory, first).status == jobs.SUCCEEDED
    assert add(factory, clock) != first


def test_a_correlation_id_is_inherited_or_made(factory: sessionmaker[Session], clock: TestClock) -> None:
    with correlation.correlated("from-the-request"):
        first = add(factory, clock)
    assert row(factory, first).correlation_id == "from-the-request"
    second = add(factory, clock, kind="other")
    made = row(factory, second).correlation_id
    assert made and made != "from-the-request"


# ---------- claiming ----------


def test_jobs_are_claimed_when_due_in_order(factory: sessionmaker[Session], clock: TestClock) -> None:
    later = add(factory, clock, kind="later", delay_seconds=60)
    soon = add(factory, clock, kind="soon")
    with factory() as s:
        first = jobs.claim(s, "w", 30, clock)
        assert first is not None and first.id == soon and first.attempt == 1 and not first.recovered
        assert jobs.claim(s, "w", 30, clock) is None
        assert jobs.complete(s, first, clock)
        clock.advance(60)
        second = jobs.claim(s, "w", 30, clock)
        assert second is not None and second.id == later


def test_a_lost_lease_is_recovered_and_flagged(factory: sessionmaker[Session], clock: TestClock) -> None:
    job_id = add(factory, clock)
    with factory() as s:
        first = jobs.claim(s, "dead-worker", 30, clock)
        assert first is not None
        clock.advance(29)
        assert jobs.claim(s, "other", 30, clock) is None, "the lease still holds"
        clock.advance(1)
        second = jobs.claim(s, "other", 30, clock)
        assert second is not None and second.id == job_id
        assert second.recovered and second.attempt == 2 and second.token != first.token
    assert "job_recovered" in actions(factory)


def test_a_worker_that_lost_its_lease_can_record_nothing(factory: sessionmaker[Session], clock: TestClock) -> None:
    add(factory, clock)
    with factory() as s:
        first = jobs.claim(s, "slow", 30, clock)
        clock.advance(31)
        second = jobs.claim(s, "fast", 30, clock)
        assert first is not None and second is not None
        assert jobs.heartbeat(s, first, 30, clock) is False
        assert jobs.complete(s, first, clock) is False
        assert jobs.retry_later(s, first, "x", None, clock) == "lost"
        assert jobs.defer(s, first, "x", 5, clock) is False
        assert jobs.give_up(s, first, "x", clock) is False
        assert jobs.complete(s, second, clock) is True
    with factory() as s:
        assert s.scalars(select(Job)).one().status == jobs.SUCCEEDED


def test_a_heartbeat_extends_the_lease(factory: sessionmaker[Session], clock: TestClock) -> None:
    add(factory, clock)
    with factory() as s:
        job = jobs.claim(s, "w", 30, clock)
        assert job is not None
        clock.advance(20)
        assert jobs.heartbeat(s, job, 30, clock) is True
        clock.advance(20)
        assert jobs.claim(s, "other", 30, clock) is None, "the heartbeat moved the lease"
        clock.advance(11)
        assert jobs.claim(s, "other", 30, clock) is not None


def test_a_job_that_keeps_losing_its_lease_goes_dead(factory: sessionmaker[Session], clock: TestClock) -> None:
    job_id = add(factory, clock, max_attempts=2)
    with factory() as s:
        assert jobs.claim(s, "a", 30, clock) is not None
        clock.advance(31)
        assert jobs.claim(s, "b", 30, clock) is not None
        clock.advance(31)
        assert jobs.claim(s, "c", 30, clock) is None
    dead = row(factory, job_id)
    assert (dead.status, dead.last_error, dead.attempts) == (jobs.DEAD, "lease_lost_attempts_used", 2)


# ---------- retries ----------


def test_backoff_doubles_is_capped_and_can_be_stated_exactly() -> None:
    assert [round(jobs.BACKOFF_BASE_SECONDS * 2 ** (a - 1)) for a in (1, 2, 3)] == [2, 4, 8]
    for attempt in range(1, 15):
        wait = jobs.backoff_seconds(7, attempt)
        base = min(jobs.BACKOFF_CAP_SECONDS, jobs.BACKOFF_BASE_SECONDS * 2 ** (attempt - 1))
        assert base <= wait <= base * 1.25
        assert jobs.backoff_seconds(7, attempt) == wait
    assert jobs.backoff_seconds(7, 3) != jobs.backoff_seconds(8, 3), "jitter spreads jobs apart"
    assert jobs.backoff_seconds(1, 100) <= jobs.BACKOFF_CAP_SECONDS * 1.25


def test_a_failing_job_retries_with_backoff_then_goes_dead(factory: sessionmaker[Session], clock: TestClock) -> None:
    calls: list[int] = []

    def fail(_s: Session, job: ClaimedJob) -> None:
        calls.append(job.attempt)
        raise Retry("upstream_down")

    job_id = add(factory, clock, max_attempts=3)
    worker = Worker(factory, {"work": fail}, clock=clock)
    assert worker.run_once() is True
    first = row(factory, job_id)
    assert (first.status, first.attempts, first.last_error) == (jobs.QUEUED, 1, "upstream_down")
    assert first.run_after_utc > clock.now
    assert worker.run_once() is False, "not due yet"
    clock.advance(10)
    assert worker.run_once() is True
    clock.advance(10)
    assert worker.run_once() is True
    clock.advance(1000)
    assert worker.run_once() is False, "bounded: no fourth attempt"
    assert calls == [1, 2, 3]
    dead = row(factory, job_id)
    assert (dead.status, dead.last_error) == (jobs.DEAD, "upstream_down")
    assert actions(factory) == ["job_dead"]


def test_retry_after_is_honoured(factory: sessionmaker[Session], clock: TestClock) -> None:
    def rate_limited(_s: Session, _j: ClaimedJob) -> None:
        raise Retry("rate_limited", after_seconds=120)

    job_id = add(factory, clock)
    Worker(factory, {"work": rate_limited}, clock=clock).run_once()
    assert row(factory, job_id).run_after_utc == jobs.later(START, 120)


def test_defer_waits_without_using_an_attempt(factory: sessionmaker[Session], clock: TestClock) -> None:
    def held(_s: Session, _j: ClaimedJob) -> None:
        raise Defer("held", 30)

    job_id = add(factory, clock, max_attempts=1)
    worker = Worker(factory, {"work": held}, clock=clock)
    for _ in range(5):
        assert worker.run_once() is True
        deferred = row(factory, job_id)
        assert (deferred.status, deferred.attempts, deferred.last_error) == (jobs.QUEUED, 0, "held")
        clock.advance(31)


def test_give_up_goes_dead_at_once(factory: sessionmaker[Session], clock: TestClock) -> None:
    def hopeless(_s: Session, _j: ClaimedJob) -> None:
        raise GiveUp("not_permitted")

    job_id = add(factory, clock)
    Worker(factory, {"work": hopeless}, clock=clock).run_once()
    dead = row(factory, job_id)
    assert (dead.status, dead.attempts, dead.last_error) == (jobs.DEAD, 1, "not_permitted")


def test_an_unknown_kind_goes_dead(factory: sessionmaker[Session], clock: TestClock) -> None:
    job_id = add(factory, clock, kind="nobody-handles-this")
    Worker(factory, {}, clock=clock).run_once()
    assert (row(factory, job_id).status, row(factory, job_id).last_error) == (jobs.DEAD, "unknown_kind")


def test_an_unexpected_error_is_retried_and_rolled_back(
    factory: sessionmaker[Session], clock: TestClock, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(s: Session, _j: ClaimedJob) -> None:
        s.execute(text("update jobs set max_attempts = 99"))
        raise ValueError("a message holding GR-12345 that must not be stored")

    job_id = add(factory, clock)
    with caplog.at_level(logging.INFO):
        Worker(factory, {"work": boom}, clock=clock).run_once()
    failed = row(factory, job_id)
    assert (failed.status, failed.last_error) == (jobs.QUEUED, "ValueError")
    assert failed.max_attempts == jobs.DEFAULT_MAX_ATTEMPTS, "the handler's writes were rolled back"


# ---------- dead jobs ----------


def test_a_person_can_requeue_a_dead_job(factory: sessionmaker[Session], clock: TestClock) -> None:
    def hopeless(_s: Session, _j: ClaimedJob) -> None:
        raise GiveUp("x")

    job_id = add(factory, clock)
    Worker(factory, {"work": hopeless}, clock=clock).run_once()
    with factory() as s:
        assert [j.id for j in jobs.dead_jobs(s)] == [job_id]
        jobs.requeue_dead(s, ADMIN, job_id, clock)
    again = row(factory, job_id)
    assert (again.status, again.attempts, again.finished_at_utc) == (jobs.QUEUED, 0, None)
    assert actions(factory)[-1] == "job_requeued"
    with factory() as s, pytest.raises(ValueError, match="not a dead job"):
        jobs.requeue_dead(s, ADMIN, job_id, clock)


def test_a_dead_job_is_not_requeued_over_an_active_one(factory: sessionmaker[Session], clock: TestClock) -> None:
    def hopeless(_s: Session, _j: ClaimedJob) -> None:
        raise GiveUp("x")

    job_id = add(factory, clock)
    Worker(factory, {"work": hopeless}, clock=clock).run_once()
    add(factory, clock)
    with factory() as s, pytest.raises(ValueError, match="already active"):
        jobs.requeue_dead(s, ADMIN, job_id, clock)


def test_the_command_line_lists_and_requeues_without_printing_payloads(
    factory: sessionmaker[Session],
    clock: TestClock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def hopeless(_s: Session, _j: ClaimedJob) -> None:
        raise GiveUp("not_permitted")

    job_id = add(factory, clock)
    Worker(factory, {"work": hopeless}, clock=clock).run_once()
    with factory() as s:
        url = str(s.get_bind().engine.url)  # type: ignore[union-attr]
    monkeypatch.setenv("DATABASE_URL", url)
    assert main(["--list-dead"]) == 0
    out = capsys.readouterr().out
    assert f"{job_id} work case=None attempts=1 code=not_permitted" in out and "thing" not in out
    assert main(["--requeue", str(job_id)]) == 0
    assert "requeued" in capsys.readouterr().out
    assert row(factory, job_id).status == jobs.QUEUED


# ---------- the loop ----------


def test_stopping_finishes_the_job_in_hand_then_claims_nothing(
    factory: sessionmaker[Session], clock: TestClock
) -> None:
    started, release = threading.Event(), threading.Event()
    done: list[str] = []

    def slow(_s: Session, job: ClaimedJob) -> None:
        started.set()
        assert release.wait(10)
        done.append(job.kind)

    add(factory, clock, kind="first")
    second = add(factory, clock, kind="second")
    worker = Worker(factory, {"first": slow, "second": slow}, clock=clock, poll_seconds=0.01)
    thread = threading.Thread(target=worker.run_forever)
    thread.start()
    assert started.wait(10)
    worker.request_stop()
    release.set()
    thread.join(10)
    assert not thread.is_alive()
    assert done == ["first"]
    assert row(factory, second).status == jobs.QUEUED, "stopping means claiming nothing new"


def test_the_correlation_id_applies_during_the_job_and_not_after(
    factory: sessionmaker[Session], clock: TestClock
) -> None:
    seen: list[str | None] = []
    with correlation.correlated("cid-1"):
        add(factory, clock)
    Worker(factory, {"work": lambda _s, _j: seen.append(correlation.current())}, clock=clock).drain()
    assert seen == ["cid-1"] and correlation.current() is None


def test_the_sweep_runs_on_its_interval_and_a_failing_one_does_not_stop_the_worker(
    factory: sessionmaker[Session], clock: TestClock
) -> None:
    calls: list[int] = []

    def sweep(_s: Session) -> None:
        calls.append(1)
        raise RuntimeError("sweep broke")

    worker = Worker(factory, {}, clock=clock, sweep=sweep, sweep_seconds=3600, poll_seconds=0.01)
    worker._maybe_sweep()
    worker._maybe_sweep()
    assert calls == [1]


def test_the_health_file_is_touched(factory: sessionmaker[Session], clock: TestClock, tmp_path: Path) -> None:
    health = tmp_path / "alive"
    worker = Worker(factory, {}, clock=clock, health_file=health, poll_seconds=0.01)
    thread = threading.Thread(target=worker.run_forever)
    thread.start()
    worker.request_stop()
    thread.join(10)
    assert health.exists()
