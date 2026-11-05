"""The job queue on real PostgreSQL, as the app's runtime role (spec B.12, Part D, Appendix C: lease recovery).

Real threads, real `SKIP LOCKED`, the database's own clock, and a real process that dies hard. Without the
TEST_*_DATABASE_URL settings these are SKIPPED with that reason.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.database import make_engine, make_sessions
from app.persistence.models import Job
from app.services import jobs
from app.services.jobs import ClaimedJob
from app.worker import Worker
from tests.conftest import ROOT
from tests.pg_stack import APP_URL, OWNER_URL, needs_postgres

pytestmark = [pytest.mark.postgres, needs_postgres]


@pytest.fixture(scope="module")
def owner() -> Iterator[Engine]:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", OWNER_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = make_engine(OWNER_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(owner: Engine) -> Iterator[sessionmaker[Session]]:
    with owner.begin() as conn:
        conn.execute(text("TRUNCATE jobs, system_events RESTART IDENTITY CASCADE"))
    engine = make_engine(APP_URL)
    yield make_sessions(engine)
    engine.dispose()


def add_many(factory: sessionmaker[Session], count: int, kind: str = "work") -> None:
    with factory() as s:
        for i in range(count):
            job = Job(
                kind=kind,
                dedupe_key=f"{kind}:{i}",
                payload={"i": i},
                status=jobs.QUEUED,
                attempts=0,
                max_attempts=3,
                run_after_utc="2000-01-01T00:00:00Z",
                created_at_utc="2000-01-01T00:00:00Z",
            )
            s.add(job)
        s.commit()


def run_threads(count: int, target: object) -> list[BaseException]:
    errors: list[BaseException] = []
    start = threading.Barrier(count)

    def wrapped() -> None:
        try:
            start.wait()
            target()  # type: ignore[operator]
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=wrapped) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    return errors


def test_eight_workers_claim_fifty_jobs_each_exactly_once(factory: sessionmaker[Session]) -> None:
    add_many(factory, 50)
    claimed: list[int] = []
    lock = threading.Lock()

    def claimer() -> None:
        while True:
            with factory() as s:
                job = jobs.claim(s, threading.current_thread().name, 60)
                if job is None:
                    return
                with lock:
                    claimed.append(job.id)
                assert jobs.complete(s, job)

    assert run_threads(8, claimer) == []
    assert Counter(claimed).most_common(1)[0][1] == 1 and len(claimed) == 50
    with factory() as s:
        assert s.scalar(text("select count(*) from jobs where status = 'succeeded'")) == 50


def test_skip_locked_does_not_wait_on_a_locked_job(factory: sessionmaker[Session]) -> None:
    add_many(factory, 2)
    with factory() as holder, factory() as other:
        held = holder.scalars(select(Job).order_by(Job.id).limit(1).with_for_update()).one()
        started = time.monotonic()
        job = jobs.claim(other, "other", 60)
        assert time.monotonic() - started < 5
        assert job is not None and job.id != held.id
        holder.rollback()


def test_twenty_concurrent_enqueues_of_one_job_add_one(factory: sessionmaker[Session]) -> None:
    ids: list[int] = []

    def enqueue() -> None:
        with factory() as s:
            job = jobs.enqueue(s, "execute_adjustment", {"request": 1})
            s.commit()
            ids.append(job.id)

    assert run_threads(20, enqueue) == []
    assert len(set(ids)) == 1 and len(ids) == 20
    with factory() as s:
        assert s.scalar(text("select count(*) from jobs")) == 1


def test_a_lost_lease_is_recovered_on_the_database_clock(factory: sessionmaker[Session]) -> None:
    add_many(factory, 1)
    with factory() as s:
        first = jobs.claim(s, "dead-worker", 1)
        assert first is not None and not first.recovered
        assert jobs.claim(s, "other", 60) is None
    time.sleep(2.2)
    with factory() as s:
        second = jobs.claim(s, "other", 60)
        assert second is not None and second.recovered and second.attempt == 2
        assert jobs.complete(s, first) is False, "the old worker can record nothing"
        assert jobs.complete(s, second) is True
    with factory() as s:
        assert s.scalar(text("select count(*) from system_events where action = 'job_recovered'")) == 1


def test_a_heartbeat_keeps_a_slow_job_from_being_taken(factory: sessionmaker[Session]) -> None:
    add_many(factory, 1)
    started, finish = threading.Event(), threading.Event()
    taken: list[ClaimedJob] = []

    def slow(_s: Session, _j: ClaimedJob) -> None:
        started.set()
        assert finish.wait(30)

    worker = Worker(factory, {"work": slow}, lease_seconds=2, heartbeat_seconds=0.3)
    thread = threading.Thread(target=worker.run_once)
    thread.start()
    assert started.wait(30)
    deadline = time.monotonic() + 4  # twice the lease
    while time.monotonic() < deadline:
        with factory() as s:
            found = jobs.claim(s, "thief", 2)
            if found:
                taken.append(found)
        time.sleep(0.2)
    finish.set()
    thread.join(30)
    assert taken == []
    with factory() as s:
        assert s.scalar(text("select status from jobs")) == "succeeded"


def test_a_real_process_that_dies_mid_job_is_recovered(factory: sessionmaker[Session], tmp_path: Path) -> None:
    add_many(factory, 1, kind="crash_me")
    marker = tmp_path / "started"
    done = subprocess.run(
        [sys.executable, "-m", "tests.crash_worker", APP_URL, str(marker)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 9, done.stderr[-500:]
    assert marker.exists()
    with factory() as s:
        stuck = s.scalars(select(Job)).one()
        assert (stuck.status, stuck.attempts) == (jobs.RUNNING, 1), "the dead process recorded nothing"
    time.sleep(2.2)  # its lease was one second

    seen: list[ClaimedJob] = []
    Worker(factory, {"crash_me": lambda _s, job: seen.append(job)}, lease_seconds=60).run_once()
    assert len(seen) == 1 and seen[0].recovered and seen[0].attempt == 2
    with factory() as s:
        assert s.scalar(text("select status from jobs")) == "succeeded"


def test_a_job_that_keeps_failing_goes_dead_and_stays_visible(factory: sessionmaker[Session]) -> None:
    add_many(factory, 1)

    def fail(_s: Session, _j: ClaimedJob) -> None:
        raise jobs.Retry("upstream_down", after_seconds=0)

    worker = Worker(factory, {"work": fail})
    assert worker.drain() == 3
    with factory() as s:
        (dead,) = jobs.dead_jobs(s)
        assert (dead.attempts, dead.last_error) == (3, "upstream_down")
        assert s.scalar(text("select count(*) from system_events where action = 'job_dead'")) == 1
