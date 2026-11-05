"""The app's business tables (spec B.11; ADR-0046). Alembic revision 0002 creates exactly these.

Milestone 5 starts them for arm A's browser flow; Milestone 6 adds to them (approval binding hash and expiry, jobs,
idempotency records, an append-only audit role) rather than replacing them. Times are UTC text
(`YYYY-MM-DDTHH:MM:SSZ`), like the canonical records.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

LIVE_CREDIT = "status IN ('executing', 'execution_unknown', 'executed', 'execution_conflict')"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    created_at_utc: Mapped[str] = mapped_column(String(20))


class UserSession(Base):
    """A server-side login session. The browser holds a random token; only its SHA-256 is stored here."""

    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at_utc: Mapped[str] = mapped_column(String(20))
    expires_at_utc: Mapped[str] = mapped_column(String(20))
    revoked_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True)
    arm: Mapped[str] = mapped_column(String(8))
    customer_id: Mapped[str] = mapped_column(String(32))
    queue: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(64))
    assigned_to: Mapped[str | None] = mapped_column(String(64), default=None)
    received_at_utc: Mapped[str] = mapped_column(String(20))
    source_ref: Mapped[str | None] = mapped_column(String(64), default=None)
    resolution_code: Mapped[str | None] = mapped_column(String(48), default=None)
    resolution_note: Mapped[str | None] = mapped_column(Text, default=None)
    # The business time to read at, when a test or the benchmark moved it past `received_at_utc` (RFC-0001, fault 5).
    # Nothing in the console or the API can set it.
    sim_now_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at_utc: Mapped[str] = mapped_column(String(20))
    updated_at_utc: Mapped[str] = mapped_column(String(20))

    __table_args__ = (Index("ix_cases_queue_status", "queue", "status"),)


class CaseRequest(Base):
    """A member's message as it arrived: channel, sender, the web form's fields, the text, attachment names."""

    __tablename__ = "case_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    request_ref: Mapped[str | None] = mapped_column(String(64), default=None)
    received_at_utc: Mapped[str] = mapped_column(String(20))
    contact_channel: Mapped[str] = mapped_column(String(32))
    sender_email: Mapped[str | None] = mapped_column(String(255), default=None)
    form_member_number: Mapped[str | None] = mapped_column(String(32), default=None)
    form_confirmation: Mapped[str | None] = mapped_column(String(32), default=None)
    form_name: Mapped[str | None] = mapped_column(String(120), default=None)
    form_property: Mapped[str | None] = mapped_column(String(32), default=None)
    text: Mapped[str] = mapped_column(Text)
    attachment_names: Mapped[list[str]] = mapped_column(JSON, default=list)


class CaseEvidence(Base):
    """A snapshot the agent attached from a legacy screen, re-read on the server at attach time."""

    __tablename__ = "case_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # member | stay | ledger | policy
    source_ref: Mapped[str] = mapped_column(String(128))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    attached_by: Mapped[str] = mapped_column(String(64))
    attached_at_utc: Mapped[str] = mapped_column(String(20))
    sim_time_utc: Mapped[str | None] = mapped_column(String(20), default=None)


class CaseNote(Base):
    __tablename__ = "case_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    author: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    created_at_utc: Mapped[str] = mapped_column(String(20))


class AdjustmentRequestRow(Base):
    """The exact adjustment an agent asked a supervisor to approve. Points come from the rules checklist."""

    __tablename__ = "adjustment_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    member_number: Mapped[str] = mapped_column(String(32))
    stay_id: Mapped[str] = mapped_column(String(32), index=True)
    points: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(48))
    checklist: Mapped[dict[str, Any]] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(64))
    requested_at_utc: Mapped[str] = mapped_column(String(20))
    # pending | approved | rejected | invalidated | executing | executed | execution_unknown | execution_conflict
    # | refused_duplicate
    status: Mapped[str] = mapped_column(String(32))
    # What the proposal rests on (ADR-0059). Empty on rows from before Milestone 6, which must be requested again.
    evidence_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    policy_refs: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    checkout_day: Mapped[str | None] = mapped_column(String(10), default=None)
    invalidated_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    invalidated_reason: Mapped[str | None] = mapped_column(String(48), default=None)

    # One live credit per stay, enforced by the database even if the code has a bug (ADR-0061).
    __table_args__ = (
        Index(
            "uq_adjustment_requests_live_stay",
            "stay_id",
            unique=True,
            postgresql_where=text(LIVE_CREDIT),
            sqlite_where=text(LIVE_CREDIT),
        ),
    )


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_request_id: Mapped[int] = mapped_column(ForeignKey("adjustment_requests.id"))
    # A random public ID, fixed when the decision is stored. The idempotency key is derived from it, so a reset app
    # database (approval row numbers start again at 1) can never reuse a key the loyalty platform has already seen.
    uid: Mapped[str] = mapped_column(String(32), unique=True)
    decided_by: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))  # approved | rejected
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    decided_at_utc: Mapped[str] = mapped_column(String(20))
    expires_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    binding_mac: Mapped[str | None] = mapped_column(String(64), default=None)

    __table_args__ = (UniqueConstraint("adjustment_request_id", name="uq_approvals_one_decision"),)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_request_id: Mapped[int] = mapped_column(ForeignKey("adjustment_requests.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), index=True)
    started_by: Mapped[str] = mapped_column(String(64))
    started_at_utc: Mapped[str] = mapped_column(String(20))
    finished_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    # submitted | applied | unknown | busy | held | conflict | rejected_upstream | refused_duplicate
    # | lookup | lookup_failed | absent | not_applied
    outcome: Mapped[str] = mapped_column(String(32))
    upstream_adjustment_id: Mapped[str | None] = mapped_column(String(64), default=None)
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)


class CaseEvent(Base):
    """One row per action: the audit trail and the E.2 instrumentation (steps, timings, outcomes) in one log."""

    __tablename__ = "case_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    step: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(64))
    actor_kind: Mapped[str] = mapped_column(String(16))  # human | scripted
    action: Mapped[str] = mapped_column(String(48))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    at_utc: Mapped[str] = mapped_column(String(32))  # wall clock, with milliseconds
    sim_time_utc: Mapped[str | None] = mapped_column(String(20), default=None)

    __table_args__ = (UniqueConstraint("case_id", "step", name="uq_case_events_step"),)


class SystemEvent(Base):
    """Audit events that belong to no case: policy publishing, the kill switch, dead jobs (RFC-0001)."""

    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64))
    actor_kind: Mapped[str] = mapped_column(String(16))  # human | scripted | system
    action: Mapped[str] = mapped_column(String(48))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    at_utc: Mapped[str] = mapped_column(String(32))


class PolicyVersionRow(Base):
    """One version of one policy document, as stored. `status` here is the truth; the file's front matter is not."""

    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(32))
    policy_id: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    effective_from: Mapped[str] = mapped_column(String(10))
    effective_to: Mapped[str | None] = mapped_column(String(10), default=None)
    status: Mapped[str] = mapped_column(String(16))  # draft | published | superseded
    sections: Mapped[list[str]] = mapped_column(JSON)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at_utc: Mapped[str] = mapped_column(String(20))
    published_by: Mapped[str | None] = mapped_column(String(64), default=None)
    published_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    regression: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    __table_args__ = (UniqueConstraint("customer_id", "policy_id", "version", name="uq_policy_versions_version"),)


class PolicyChunk(Base):
    """One section of a policy version: the exact excerpt a citation opens (spec B.6). Postgres indexes it for full-text
    search with an expression index in revision 0003 (ADR-0057)."""

    __tablename__ = "policy_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_version_id: Mapped[int] = mapped_column(ForeignKey("policy_versions.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(16))
    heading: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("policy_version_id", "section_id", name="uq_policy_chunks_section"),)


class Job(Base):
    """One unit of durable background work (spec B.12; `app/services/jobs.py`). The payload holds IDs only."""

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(48))
    dedupe_key: Mapped[str] = mapped_column(String(80))
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), default=None)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))  # queued | running | succeeded | dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer)
    run_after_utc: Mapped[str] = mapped_column(String(20))
    lease_owner: Mapped[str | None] = mapped_column(String(64), default=None)
    lease_token: Mapped[str | None] = mapped_column(String(32), default=None)
    lease_expires_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    heartbeat_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
    last_error: Mapped[str | None] = mapped_column(String(64), default=None)
    correlation_id: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at_utc: Mapped[str] = mapped_column(String(20))
    finished_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)

    __table_args__ = (
        Index("ix_jobs_claim", "status", "run_after_utc"),
        Index(
            "uq_jobs_active",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )


class SystemSwitch(Base):
    """The emergency switch for adjustments (`app/services/kill_switch.py`). No row at all counts as "off"."""

    __tablename__ = "system_switches"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    engaged: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    changed_by: Mapped[str | None] = mapped_column(String(64), default=None)
    changed_at_utc: Mapped[str | None] = mapped_column(String(20), default=None)
