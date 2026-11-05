"""The worker process (spec B.12; JOB-01, ADR-0060). One job at a time per process; run more for more throughput.

    python -m app.worker                 # run until SIGTERM or SIGINT
    python -m app.worker --list-dead     # IDs, kinds and error codes only
    python -m app.worker --requeue 12    # a person decides to try a dead job again

Graceful shutdown: on a signal it stops claiming, finishes the job in hand, then exits 0. A hard kill leaves the job's
lease to run out, and the next claim recovers it. Reads DATABASE_URL, MOCK_API_URL, MOCK_API_TOKEN, APP_SECRET_KEY.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app import correlation
from app.domain.roles import Identity, Role
from app.services import jobs
from app.services.jobs import ClaimedJob, Clock, Defer, GiveUp, Retry

log = logging.getLogger("app.worker")
Handler = Callable[[Session, ClaimedJob], None]
Sweep = Callable[[Session], object]
DEFAULT_LEASE_SECONDS = 60.0  # longer than any single upstream call's timeouts and retries
DEFAULT_POLL_SECONDS = 1.0
DEFAULT_SWEEP_SECONDS = 30.0
MAX_CLAIM_BACKOFF_SECONDS = 60.0


class Worker:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        handlers: Mapping[str, Handler],
        *,
        worker_id: str | None = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        heartbeat_seconds: float | None = None,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        sweep: Sweep | None = None,
        sweep_seconds: float = DEFAULT_SWEEP_SECONDS,
        clock: Clock = jobs.db_now,
        health_file: Path | None = None,
    ) -> None:
        self.sessions, self.handlers = sessions, handlers
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds if heartbeat_seconds is not None else lease_seconds / 3
        self.poll_seconds, self.sweep, self.sweep_seconds = poll_seconds, sweep, sweep_seconds
        self.clock, self.health_file = clock, health_file
        self._stop = threading.Event()
        self._last_sweep: float | None = None

    def request_stop(self) -> None:
        """Stop claiming. The job in hand finishes first."""
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    # ---------- one job ----------

    def run_once(self) -> bool:
        """Claim and run one job. True if there was one."""
        with self.sessions() as s:
            job = jobs.claim(s, self.worker_id, self.lease_seconds, self.clock)
        if job is None:
            return False
        with correlation.correlated(job.correlation_id):
            log.info("job start id=%s kind=%s attempt=%s recovered=%s", job.id, job.kind, job.attempt, job.recovered)
            stop_beat = threading.Event()
            beat = threading.Thread(target=self._heartbeat_loop, args=(job, stop_beat), daemon=True)
            beat.start()
            try:
                self._run(job)
            finally:
                stop_beat.set()
                beat.join()
        return True

    def _run(self, job: ClaimedJob) -> None:
        handler = self.handlers.get(job.kind)
        with self.sessions() as s:
            if handler is None:
                jobs.give_up(s, job, "unknown_kind", self.clock)
                log.error("job dead id=%s kind=%s code=unknown_kind", job.id, job.kind)
                return
            try:
                handler(s, job)
            except Retry as exc:
                s.rollback()
                outcome = jobs.retry_later(s, job, exc.code, exc.after_seconds, self.clock)
                log.warning("job %s id=%s kind=%s code=%s", outcome, job.id, job.kind, exc.code)
            except Defer as exc:
                s.rollback()
                jobs.defer(s, job, exc.code, exc.after_seconds, self.clock)
                log.info("job deferred id=%s kind=%s code=%s", job.id, job.kind, exc.code)
            except GiveUp as exc:
                s.rollback()
                jobs.give_up(s, job, exc.code, self.clock)
                log.error("job dead id=%s kind=%s code=%s", job.id, job.kind, exc.code)
            except Exception as exc:  # an unknown failure is retried, bounded; its type is logged, never its message
                s.rollback()
                code = type(exc).__name__
                outcome = jobs.retry_later(s, job, code, None, self.clock)
                log.exception("job %s id=%s kind=%s code=%s", outcome, job.id, job.kind, code)
            else:
                if jobs.complete(s, job, self.clock):
                    log.info("job done id=%s kind=%s", job.id, job.kind)
                else:
                    log.warning("job lease lost before it finished id=%s kind=%s", job.id, job.kind)

    def _heartbeat_loop(self, job: ClaimedJob, stop: threading.Event) -> None:
        while not stop.wait(self.heartbeat_seconds):
            self._touch_health()
            try:
                with self.sessions() as s:
                    if not jobs.heartbeat(s, job, self.lease_seconds, self.clock):
                        log.warning("job lease lost id=%s kind=%s", job.id, job.kind)
                        return
            except Exception:  # a missed heartbeat only risks losing the lease, which is safe
                log.exception("heartbeat failed id=%s", job.id)

    # ---------- the loop ----------

    def _touch_health(self) -> None:
        if self.health_file is not None:
            self.health_file.touch()

    def _maybe_sweep(self) -> None:
        if self.sweep is None:
            return
        if self._last_sweep is not None and time.monotonic() - self._last_sweep < self.sweep_seconds:
            return
        self._last_sweep = time.monotonic()
        try:
            with self.sessions() as s:
                self.sweep(s)
        except Exception:
            log.exception("sweep failed")

    def run_forever(self) -> None:
        log.info("worker started id=%s", self.worker_id)
        failures = 0
        while not self.stopping:
            self._maybe_sweep()
            try:
                did_work = self.run_once()
                self._touch_health()  # only after the database answered: "healthy" must mean it can work
                failures = 0
            except Exception:  # the database went away: wait longer each time, so the log can't flood
                failures += 1
                log.exception("claim failed")
                self._stop.wait(min(MAX_CLAIM_BACKOFF_SECONDS, self.poll_seconds * 2**failures))
                continue
            if not did_work:
                self._stop.wait(self.poll_seconds)
        log.info("worker stopped id=%s", self.worker_id)

    def drain(self, limit: int = 100) -> int:
        """Run jobs until none is due. For the scripted agent and tests, which have no separate worker process."""
        done = 0
        while done < limit and self.run_once():
            done += 1
        return done


def build_handlers(settings: Any) -> tuple[dict[str, Handler], Sweep | None]:
    """The write path's jobs, reading the customer systems the same way the console does."""
    from app.services.job_handlers import build_handlers as write_path_handlers
    from app.services.job_handlers import sweep_stranded
    from app.services.systems import mock_systems_factory
    from app.services.write_path import SharedWritePath

    write_path = SharedWritePath(settings.customer_id, secret_key=settings.secret_key or None)
    return write_path_handlers(write_path, mock_systems_factory(settings)), sweep_stranded


OPERATOR = Identity(0, "worker-cli", "Worker command line", Role.ADMINISTRATOR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    parser.add_argument("--list-dead", action="store_true")
    parser.add_argument("--requeue", type=int, metavar="JOB_ID")
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = AppSettings.from_env()
    sessions = make_sessions(make_engine(settings.database_url))
    if args.list_dead:
        with sessions() as s:
            for job in jobs.dead_jobs(s):
                print(f"{job.id} {job.kind} case={job.case_id} attempts={job.attempts} code={job.last_error}")
        return 0
    if args.requeue is not None:
        with sessions() as s:
            job = jobs.requeue_dead(s, OPERATOR, args.requeue)
            print(f"requeued {job.id} {job.kind}")
        return 0

    handlers, sweep = build_handlers(settings)
    health = settings.worker_health_file
    worker = Worker(sessions, handlers, sweep=sweep, health_file=Path(health) if health else None)
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: worker.request_stop())
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
