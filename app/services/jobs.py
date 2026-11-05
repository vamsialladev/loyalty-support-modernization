"""The durable job queue (spec B.12, Appendix B; JOB-01, ADR-0060): a Postgres table, no other system.

Failure semantics, plainly:
- **At least once.** A job can run twice: a worker can die after doing the work and before recording it. Handlers must
  make that safe. The write path does, with its state machine and the idempotency key derived from the approval.
- **One active job per key.** A partial unique index allows one queued or running job per (kind, case).
- **Leases, on the database's clock.** A worker that stops heartbeating loses its job to the next claim, whose
  `recovered` flag says so. Each claim gets a new token, and a worker holding an old token can't record anything.
- **Bounded.** Attempts are counted at claim. After `max_attempts` a job goes dead and stays visible; nothing retries it
  unless a person requeues it. `Defer` waits without using an attempt.

Payloads hold IDs only: no personal data, and nothing that can go stale.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import correlation
from app.domain.business_time import format_utc, parse_utc
from app.domain.roles import Identity, Role
from app.persistence.models import Job
from app.services.instrumentation import record_system

QUEUED, RUNNING, SUCCEEDED, DEAD = "queued", "running", "succeeded", "dead"
DEFAULT_MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS, BACKOFF_CAP_SECONDS = 2.0, 300.0
SYSTEM = Identity(
    0, "system-worker", "Worker", Role.AGENT
)  # never signs in; marks what the worker did in the audit log

Clock = Callable[[Session], str]


class Retry(Exception):
    """Try again later; uses an attempt. `after_seconds` overrides the backoff (for example a `Retry-After`)."""

    def __init__(self, code: str, after_seconds: float | None = None) -> None:
        super().__init__(code)
        self.code, self.after_seconds = code, after_seconds


class Defer(Exception):
    """Not now, and not a failure (for example the kill switch): wait without using an attempt."""

    def __init__(self, code: str, after_seconds: float) -> None:
        super().__init__(code)
        self.code, self.after_seconds = code, after_seconds


class GiveUp(Exception):
    """Retrying can't help: the job goes dead now."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    kind: str
    token: str
    payload: Mapping[str, Any]
    case_id: int | None
    correlation_id: str | None
    attempt: int
    recovered: bool  # the previous worker lost its lease: it may or may not have done the work


def db_now(s: Session) -> str:
    """The database's clock, so workers on machines with different clocks agree about leases."""
    if s.get_bind().dialect.name == "postgresql":
        query = """SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')"""
    else:
        query = "SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
    return str(s.scalar(text(query)))


def later(now: str, seconds: float) -> str:
    return format_utc(parse_utc(now) + timedelta(seconds=seconds))


def backoff_seconds(job_id: int, attempt: int) -> float:
    """Exponential up to a cap, plus up to 25% jitter. The jitter comes from the job and attempt, so it spreads jobs out
    and a test can state exactly what it will be."""
    delay = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2.0 ** (attempt - 1))
    digest = hashlib.sha256(f"{job_id}:{attempt}".encode()).digest()
    return delay + delay * 0.25 * (digest[0] / 255)


def dedupe_key(kind: str, case_id: int | None) -> str:
    return f"{kind}:{case_id if case_id is not None else 'system'}"


def active_job(s: Session, key: str) -> Job | None:
    return s.scalars(select(Job).where(Job.dedupe_key == key, Job.status.in_((QUEUED, RUNNING)))).first()


def active_case_job(s: Session, case_id: int) -> Job | None:
    return s.scalars(select(Job).where(Job.case_id == case_id, Job.status.in_((QUEUED, RUNNING)))).first()


def enqueue(
    s: Session,
    kind: str,
    payload: Mapping[str, Any],
    *,
    case_id: int | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    delay_seconds: float = 0,
    clock: Clock = db_now,
) -> Job:
    """Add a job in the caller's transaction, so it commits or rolls back with the state change that needs it. If one is
    already active for this kind and case, that one is returned and nothing is added."""
    key = dedupe_key(kind, case_id)
    found = active_job(s, key)
    if found is not None:
        return found
    now = clock(s)
    job = Job(
        kind=kind,
        dedupe_key=key,
        case_id=case_id,
        payload=dict(payload),
        status=QUEUED,
        attempts=0,
        max_attempts=max_attempts,
        run_after_utc=later(now, delay_seconds),
        correlation_id=correlation.current() or correlation.new_id(),
        created_at_utc=now,
    )
    try:
        with s.begin_nested():
            s.add(job)
            s.flush()
    except IntegrityError:  # another transaction added the same job first
        found = active_job(s, key)
        assert found is not None
        return found
    return job


def claim(s: Session, worker_id: str, lease_seconds: float, clock: Clock = db_now) -> ClaimedJob | None:
    """The next job that is due, or whose lease has run out. `SKIP LOCKED` lets many workers claim at once without
    waiting on each other. Commits. Returns None when nothing is due."""
    now = clock(s)
    while True:
        job = s.scalars(
            select(Job)
            .where(
                or_(
                    and_(Job.status == QUEUED, Job.run_after_utc <= now),
                    and_(Job.status == RUNNING, Job.lease_expires_utc <= now),
                )
            )
            .order_by(Job.run_after_utc, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            s.commit()
            return None
        recovered = job.status == RUNNING
        if recovered and job.attempts >= job.max_attempts:
            _go_dead(s, job, "lease_lost_attempts_used", now)
            s.commit()
            continue
        job.status, job.lease_owner, job.lease_token = RUNNING, worker_id, uuid.uuid4().hex
        job.lease_expires_utc, job.heartbeat_at_utc = later(now, lease_seconds), now
        job.attempts += 1
        if recovered:
            record_system(s, SYSTEM, "job_recovered", job=job.id, kind=job.kind, case=job.case_id, attempt=job.attempts)
        claimed = ClaimedJob(
            job.id,
            job.kind,
            job.lease_token,
            dict(job.payload),
            job.case_id,
            job.correlation_id,
            job.attempts,
            recovered,
        )
        s.commit()
        return claimed


def _owned(job: ClaimedJob) -> Any:
    return and_(Job.id == job.id, Job.lease_token == job.token, Job.status == RUNNING)


def heartbeat(s: Session, job: ClaimedJob, lease_seconds: float, clock: Clock = db_now) -> bool:
    """Extend the lease. False means another worker took the job: the caller must not record anything."""
    now = clock(s)
    result = s.execute(
        update(Job).where(_owned(job)).values(lease_expires_utc=later(now, lease_seconds), heartbeat_at_utc=now)
    )
    s.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


def complete(s: Session, job: ClaimedJob, clock: Clock = db_now) -> bool:
    now = clock(s)
    result = s.execute(
        update(Job).where(_owned(job)).values(status=SUCCEEDED, finished_at_utc=now, lease_token=None, last_error=None)
    )
    s.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


def retry_later(
    s: Session, job: ClaimedJob, code: str, after_seconds: float | None = None, clock: Clock = db_now
) -> str:
    """Queue it again, or send it dead if its attempts are used. Returns what happened: requeued, dead or lost."""
    row = s.get(Job, job.id, with_for_update=True, populate_existing=True)
    if row is None or row.lease_token != job.token or row.status != RUNNING:
        s.rollback()
        return "lost"
    now = clock(s)
    if row.attempts >= row.max_attempts:
        _go_dead(s, row, code, now)
        s.commit()
        return "dead"
    wait = after_seconds if after_seconds is not None else backoff_seconds(row.id, row.attempts)
    row.status, row.run_after_utc, row.last_error, row.lease_token = QUEUED, later(now, wait), code, None
    row.lease_owner, row.lease_expires_utc = None, None
    s.commit()
    return "requeued"


def defer(s: Session, job: ClaimedJob, code: str, after_seconds: float, clock: Clock = db_now) -> bool:
    now = clock(s)
    result = s.execute(
        update(Job)
        .where(_owned(job))
        .values(
            status=QUEUED,
            attempts=Job.attempts - 1,
            run_after_utc=later(now, after_seconds),
            last_error=code,
            lease_token=None,
            lease_owner=None,
            lease_expires_utc=None,
        )
    )
    s.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


def give_up(s: Session, job: ClaimedJob, code: str, clock: Clock = db_now) -> bool:
    row = s.get(Job, job.id, with_for_update=True, populate_existing=True)
    if row is None or row.lease_token != job.token or row.status != RUNNING:
        s.rollback()
        return False
    _go_dead(s, row, code, clock(s))
    s.commit()
    return True


def _go_dead(s: Session, job: Job, code: str, now: str) -> None:
    job.status, job.last_error, job.finished_at_utc = DEAD, code, now
    job.lease_token, job.lease_owner, job.lease_expires_utc = None, None, None
    record_system(s, SYSTEM, "job_dead", job=job.id, kind=job.kind, case=job.case_id, code=code, attempts=job.attempts)


def dead_jobs(s: Session, limit: int = 100) -> list[Job]:
    return list(s.scalars(select(Job).where(Job.status == DEAD).order_by(Job.id.desc()).limit(limit)))


def requeue_dead(s: Session, who: Identity, job_id: int, clock: Clock = db_now) -> Job:
    """A person decided to try a dead job again. Refused if another job for the same work is already active."""
    job = s.get(Job, job_id, with_for_update=True)
    if job is None or job.status != DEAD:
        raise ValueError(f"job {job_id} is not a dead job")
    if active_job(s, job.dedupe_key) is not None:
        raise ValueError(f"another job for {job.dedupe_key} is already active")
    job.status, job.attempts, job.run_after_utc = QUEUED, 0, clock(s)
    job.finished_at_utc = None
    record_system(s, who, "job_requeued", job=job.id, kind=job.kind, case=job.case_id)
    s.commit()
    return job
