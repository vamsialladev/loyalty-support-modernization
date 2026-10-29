"""Tables of the mock customer systems. Columns use canonical names; the API renders the customer's names.

Timestamps are stored as canonical UTC text (`YYYY-MM-DDTHH:MM:SSZ`), which sorts correctly as text and behaves the
same on PostgreSQL and SQLite (used by the in-process contract tests). Alembic owns the schema (`migrations/`).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

TS = String(20)
DATE = String(10)


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"
    member_number: Mapped[str] = mapped_column(String(16), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), index=True)
    phone: Mapped[str] = mapped_column(String(40), index=True)
    date_of_birth: Mapped[str] = mapped_column(DATE)
    tier: Mapped[str] = mapped_column(String(16))
    home_region: Mapped[str] = mapped_column(String(40))
    enrolled_on: Mapped[str] = mapped_column(DATE)
    status: Mapped[str] = mapped_column(String(16))
    merged_into: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Stay(Base):
    __tablename__ = "stays"
    record_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stay_id: Mapped[str] = mapped_column(String(16), index=True)
    customer_id: Mapped[str] = mapped_column(String(32))
    property: Mapped[str] = mapped_column(String(32))
    member_number: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    member_on_booking: Mapped[bool] = mapped_column(Boolean)
    arrival_date: Mapped[str] = mapped_column(DATE)
    nights: Mapped[int] = mapped_column(Integer)
    checkout_at_utc: Mapped[str] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_code: Mapped[str] = mapped_column(String(32))
    rate_code: Mapped[str] = mapped_column(String(32))
    partner_confirmation: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    room_revenue_cents: Mapped[int] = mapped_column(Integer)
    taxes_cents: Mapped[int] = mapped_column(Integer)
    fees_cents: Mapped[int] = mapped_column(Integer)
    guest_name: Mapped[str] = mapped_column(String(160))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    entry_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_number: Mapped[str] = mapped_column(String(16), index=True)
    stay_id: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(16))
    points: Mapped[int] = mapped_column(Integer)
    posted_at_utc: Mapped[str] = mapped_column(TS, index=True)
    reverses_entry_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PostingQueueItem(Base):
    __tablename__ = "posting_queue"
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_number: Mapped[str] = mapped_column(String(16))
    stay_id: Mapped[str] = mapped_column(String(16), index=True)
    points: Mapped[int] = mapped_column(Integer)
    queued_at_utc: Mapped[str] = mapped_column(TS)
    expected_post_at_utc: Mapped[str] = mapped_column(TS)
    posts_entry_id: Mapped[str] = mapped_column(String(32))


class IdempotencyRecord(Base):
    """One row per idempotency key, committed in the same transaction as the operation (ADR-0039)."""

    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[str] = mapped_column(Text)
    created_at_utc: Mapped[str] = mapped_column(TS)


class Adjustment(Base):
    __tablename__ = "adjustments"
    adjustment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(200), ForeignKey("idempotency_records.key"), unique=True, index=True
    )
    member_number: Mapped[str] = mapped_column(String(16), index=True)
    stay_id: Mapped[str] = mapped_column(String(16), index=True)
    points: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(80))
    created_at_utc: Mapped[str] = mapped_column(TS)
    ledger_entry_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))


class Ticket(Base):
    __tablename__ = "tickets"
    ticket_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at_utc: Mapped[str] = mapped_column(TS)


SEEDED_TABLES = [Member, Stay, LedgerEntry, PostingQueueItem]
ALL_TABLES = [Adjustment, IdempotencyRecord, Ticket, PostingQueueItem, LedgerEntry, Stay, Member]


def make_engine(url: str) -> Engine:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
