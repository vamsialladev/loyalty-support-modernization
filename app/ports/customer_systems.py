"""The customer's systems of record, as the app sees them: loyalty platform, PMS and ticketing (spec B.3).

The mock customer API implements this through `app.adapters.mock_customer_api`; a real loyalty platform gets a sibling
adapter (`docs/real-system-swap-guide.md`). Errors are the typed exceptions below, never raw HTTP or driver errors.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.customer_records import (
    AdjustmentRequest,
    AdjustmentResult,
    LedgerEntry,
    Member,
    PendingPosting,
    StayRecord,
    Ticket,
)


class CustomerSystemError(Exception):
    """Base for every failure talking to a customer system. `retryable` says whether a retry is safe and useful."""

    retryable = False

    def __init__(self, message: str, *, code: str = "", correlation_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.correlation_id = correlation_id


class AuthenticationFailed(CustomerSystemError):
    """401/403: the credential is wrong, expired or lacks permission. Never retried."""


class RecordNotFound(CustomerSystemError):
    """404: the record doesn't exist in the system of record."""


class RequestRejected(CustomerSystemError):
    """400/422: the system refused the request as invalid. Never retried."""


class IdempotencyConflict(CustomerSystemError):
    """409: the idempotency key was already used for a different request body."""


class RateLimited(CustomerSystemError):
    """429: slow down. Retryable after `retry_after_seconds`."""

    retryable = True

    def __init__(self, message: str, *, retry_after_seconds: float, **kwargs: str | None) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after_seconds = retry_after_seconds


class TemporarilyUnavailable(CustomerSystemError):
    """503: transient outage before the request was processed. Retryable."""

    retryable = True


class UpstreamTimeout(CustomerSystemError):
    """A read timed out. Retryable for reads."""

    retryable = True


class UncertainOutcome(CustomerSystemError):
    """A write timed out or the response was lost: it may or may not have been applied. Never retry blindly;
    look up the status by idempotency key first (spec B.10: reconciliation before any retry)."""


class MalformedResponse(CustomerSystemError):
    """The response wasn't valid JSON or wasn't the expected structure."""


class SchemaMismatch(CustomerSystemError):
    """The response parsed but doesn't match the contract (missing field, unknown code). The upstream may have
    changed its API; the adapter refuses to guess."""


class PartialResult(CustomerSystemError):
    """A multi-page read failed part way. Never treat the pages received as the whole result."""


class CustomerSystems(Protocol):
    def get_member(self, member_number: str) -> Member: ...

    def find_members(self, *, email: str | None = None, phone: str | None = None) -> list[Member]: ...

    def get_stay_records(self, stay_id: str) -> list[StayRecord]: ...

    def find_stays(
        self, *, member_number: str | None = None, partner_confirmation: str | None = None
    ) -> list[StayRecord]: ...

    def get_ledger(self, member_number: str) -> list[LedgerEntry]: ...

    def get_pending_postings(self, stay_id: str) -> list[PendingPosting]: ...

    def create_ticket(self, *, subject: str, body: str, member_number: str | None = None) -> Ticket: ...

    def submit_adjustment(self, request: AdjustmentRequest, idempotency_key: str) -> AdjustmentResult: ...

    def find_adjustment(self, idempotency_key: str) -> AdjustmentResult | None: ...
