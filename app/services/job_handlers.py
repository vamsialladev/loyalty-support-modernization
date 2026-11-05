"""What the worker does with write-path jobs (spec B.10, B.12; WP-09, MOCK-09, JOB-03; ADR-0061).

A job can run twice (ADR-0060). These are safe to repeat because `SharedWritePath` only moves a case through its state
machine under a row lock, and every submission of one approval carries the same idempotency key.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.domain.case_states import CaseState
from app.domain.roles import Identity, NotPermitted, Role
from app.persistence.models import AdjustmentRequestRow, Case, ExecutionAttempt, Job, User
from app.ports.customer_systems import CustomerSystems
from app.services import jobs
from app.services.cases import WorkflowError, read_time
from app.services.instrumentation import record
from app.services.jobs import ClaimedJob, Defer, GiveUp, Retry
from app.services.write_path import EXECUTE_JOB, RECONCILE_JOB, RecheckFailed, SharedWritePath, load_request

log = logging.getLogger(__name__)
HELD_RETRY_SECONDS = 15.0
UNKNOWN_RETRY_SECONDS = 20.0
RECONCILE_MAX_ATTEMPTS = 12  # about 4 minutes at the retry interval; then a person decides, and the case stays unknown
MAX_SUBMISSIONS_PER_APPROVAL = 3

Handler = Callable[[Session, ClaimedJob], None]
SystemsFor = Callable[[str | None], CustomerSystems]


def _requester(s: Session, job: ClaimedJob) -> Identity:
    """The person who asked, as they are now. A deactivated account or a changed role stops the job."""
    user = s.get(User, job.payload["user_id"], populate_existing=True)
    if user is None or not user.active:
        raise GiveUp("requester_inactive")
    return Identity(user.id, user.username, user.display_name, Role(user.role))


def _enqueue_reconcile(s: Session, row: AdjustmentRequestRow, user_id: int) -> None:
    jobs.enqueue(
        s,
        RECONCILE_JOB,
        {"request_id": row.id, "user_id": user_id},
        case_id=row.case_id,
        max_attempts=RECONCILE_MAX_ATTEMPTS,
    )


def _submissions(s: Session, row: AdjustmentRequestRow) -> int:
    query = select(ExecutionAttempt).where(
        ExecutionAttempt.adjustment_request_id == row.id, ExecutionAttempt.outcome == "unknown"
    )
    return len(s.scalars(query).all())


def build_handlers(write_path: SharedWritePath, systems_for: SystemsFor) -> dict[str, Handler]:
    def after_absent(s: Session, row: AdjustmentRequestRow, user_id: int) -> None:
        """Reconciliation found nothing. Try again under the same key, a bounded number of times, then leave it
        `Approved` for a person."""
        case = s.get(Case, row.case_id)
        assert case is not None
        if _submissions(s, row) < MAX_SUBMISSIONS_PER_APPROVAL:
            jobs.enqueue(
                s,
                EXECUTE_JOB,
                {"request_id": row.id, "user_id": user_id},
                case_id=row.case_id,
                delay_seconds=jobs.backoff_seconds(row.id, 1),
            )
        else:
            record(s, case, jobs.SYSTEM, "execution_gave_up", submissions=_submissions(s, row))
        s.commit()

    def execute(s: Session, job: ClaimedJob) -> None:
        request_id, user_id = int(job.payload["request_id"]), int(job.payload["user_id"])
        row, case = load_request(s, request_id)
        if job.recovered or CaseState(case.status) is CaseState.EXECUTING:
            # The worker before this one died. It may have submitted, so what it was doing can't simply be repeated.
            write_path.recover_interrupted(s, request_id)
            s.refresh(case)
            if CaseState(case.status) is CaseState.EXECUTION_UNKNOWN:
                _enqueue_reconcile(s, row, user_id)
                s.commit()
                return
            if CaseState(case.status) is not CaseState.APPROVED:
                return
        try:
            result = write_path.execute(s, _requester(s, job), request_id, systems_for(read_time(case)))
        except NotPermitted as exc:
            raise GiveUp("not_permitted") from exc
        except RecheckFailed as exc:
            raise Retry("recheck_read_failed") from exc
        except WorkflowError:
            log.info("job %s has nothing to do: the case moved on", job.id)
            return
        if result.status == "held":
            raise Defer("kill_switch", HELD_RETRY_SECONDS)
        if result.status == "retry":
            raise Retry("upstream_busy", result.retry_after_seconds)
        if result.status == "unknown":
            _enqueue_reconcile(s, row, user_id)
            s.commit()
        elif result.status == "not_applied":
            after_absent(s, row, user_id)

    def reconcile(s: Session, job: ClaimedJob) -> None:
        request_id, user_id = int(job.payload["request_id"]), int(job.payload["user_id"])
        row, case = load_request(s, request_id)
        if CaseState(case.status) is CaseState.EXECUTING:
            write_path.recover_interrupted(s, request_id)
            s.refresh(case)
        if CaseState(case.status) is not CaseState.EXECUTION_UNKNOWN:
            return
        result = write_path.reconcile_as_system(s, request_id, systems_for(read_time(case)))
        if result.status == "unknown":
            raise Retry("still_unknown", UNKNOWN_RETRY_SECONDS)
        if result.status == "not_applied":
            after_absent(s, row, user_id)

    return {EXECUTE_JOB: execute, RECONCILE_JOB: reconcile}


def sweep_stranded(s: Session) -> list[int]:
    """Queue a reconciliation for a case stuck in `Executing` or `Execution unknown` with no job on it (MOCK-09).

    A dead job isn't retried here: that would make its retries unbounded. If it died after the latest attempt, the case
    stays unknown and visible until a person requeues it."""
    stuck = s.scalars(
        select(AdjustmentRequestRow)
        .join(Case, Case.id == AdjustmentRequestRow.case_id)
        .where(
            Case.status.in_((CaseState.EXECUTING.value, CaseState.EXECUTION_UNKNOWN.value)),
            AdjustmentRequestRow.status.in_(("executing", "execution_unknown")),
            ~exists().where(Job.case_id == Case.id, Job.status.in_((jobs.QUEUED, jobs.RUNNING))),
        )
    ).all()
    queued = []
    for row in stuck:
        latest = s.scalars(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.adjustment_request_id == row.id)
            .order_by(ExecutionAttempt.id.desc())
            .limit(1)
        ).first()
        since = latest.started_at_utc if latest else ""
        dead_since = s.scalars(
            select(Job).where(
                Job.case_id == row.case_id,
                Job.kind == RECONCILE_JOB,
                Job.status == jobs.DEAD,
                Job.finished_at_utc >= since,
            )
        ).first()
        if dead_since is None:
            user = s.scalars(select(User).where(User.username == (latest.started_by if latest else ""))).first()
            _enqueue_reconcile(s, row, user.id if user else 0)
            queued.append(row.id)
    s.commit()
    return queued
