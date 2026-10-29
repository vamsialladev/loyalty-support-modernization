"""Canonical, customer-neutral records the app works with, whatever system they came from (ADR-0033).

Timestamps are UTC text (`YYYY-MM-DDTHH:MM:SSZ`), dates `YYYY-MM-DD`, money integer cents.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Member:
    member_number: str
    first_name: str
    last_name: str
    email: str
    phone: str
    tier: str
    status: str
    date_of_birth: str | None = None
    home_region: str | None = None
    enrolled_on: str | None = None
    merged_into: str | None = None


@dataclass(frozen=True)
class StayRecord:
    record_id: str
    stay_id: str
    property: str
    member_on_booking: bool
    arrival_date: str
    nights: int
    checkout_at_utc: str
    status: str
    source_code: str
    rate_code: str
    room_revenue_cents: int
    member_number: str | None = None
    channel: str | None = None
    partner_confirmation: str | None = None
    taxes_cents: int = 0
    fees_cents: int = 0
    guest_name: str = ""


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    member_number: str
    kind: str
    points: int
    posted_at_utc: str
    stay_id: str | None = None
    reverses_entry_id: str | None = None


@dataclass(frozen=True)
class PendingPosting:
    item_id: str
    member_number: str
    stay_id: str
    points: int
    queued_at_utc: str
    expected_post_at_utc: str
    posts_entry_id: str


@dataclass(frozen=True)
class AdjustmentRequest:
    member_number: str
    stay_id: str
    points: int
    reason_code: str
    requested_by: str
    note: str | None = None


@dataclass(frozen=True)
class AdjustmentResult:
    adjustment_id: str
    idempotency_key: str
    member_number: str
    stay_id: str
    points: int
    status: str
    created_at_utc: str
    ledger_entry_id: str
    reason_code: str | None = None
    requested_by: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    subject: str
    body: str
    created_at_utc: str
    member_number: str | None = None


def required_fields(record_type: type) -> tuple[str, ...]:
    """Fields without defaults: an upstream record missing any of them is a schema mismatch."""
    from dataclasses import MISSING

    return tuple(f.name for f in fields(record_type) if f.default is MISSING and f.default_factory is MISSING)
