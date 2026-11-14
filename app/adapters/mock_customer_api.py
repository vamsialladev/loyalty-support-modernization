"""Adapter for the mock customer API (implements `CustomerSystems`). A real loyalty platform gets a sibling adapter.

What it guarantees to the rest of the app:
- Every failure is a typed `CustomerSystemError`; no raw HTTP, JSON or driver error escapes.
- Reads retry only transient failures (429, 503, timeouts), a bounded number of times, honouring `Retry-After`.
- Writes (adjustments) are never retried after a timeout or a lost response: that raises `UncertainOutcome`, and the
  caller must reconcile with `find_adjustment` first (spec B.10). 429/503 are retried with the same idempotency key.
- Responses are mapped from the customer's upstream names to canonical records; a missing field or unknown code is a
  `SchemaMismatch`, never a guess. A multi-page read that fails part way raises `PartialResult`.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

from app import correlation
from app.adapters.circuit import CircuitBreaker
from app.domain.customer_records import (
    AdjustmentRequest,
    AdjustmentResult,
    LedgerEntry,
    Member,
    PendingPosting,
    StayRecord,
    Ticket,
    required_fields,
)
from app.ports.customer_systems import (
    AuthenticationFailed,
    CustomerSystemError,
    IdempotencyConflict,
    MalformedResponse,
    PartialResult,
    RateLimited,
    RecordNotFound,
    RequestRejected,
    SchemaMismatch,
    TemporarilyUnavailable,
    UncertainOutcome,
    UpstreamTimeout,
)
from customer_shapes import CustomerShape, ShapeError

T = TypeVar("T")
MAX_RETRY_WAIT_SECONDS = 5.0
# The answers that mean the system itself is failing, which is what the breaker counts (ADR-0081). RateLimited isn't:
# the system is up and asking us to slow down, and the retry waits as asked.
UNHEALTHY = (TemporarilyUnavailable, UpstreamTimeout, UncertainOutcome)


class MockCustomerApiAdapter:
    def __init__(
        self,
        base_url: str,
        token: str,
        shape: CustomerShape,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 2.0,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
        sim_time: str | None = None,
        fault: str | None = None,
        page_size: int = 100,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.breaker = breaker  # the production wiring passes one (app/services/systems.py); tests mostly don't
        self.shape = shape
        self.max_retries = max_retries
        self.sleep = sleep
        self.sim_time = sim_time
        self.fault = fault
        self.page_size = page_size
        self._token = token
        self.client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    # ---------- reads ----------

    def get_member(self, member_number: str) -> Member:
        return self._record("member", Member, self._request("GET", f"/v1/members/{member_number}"))

    def find_members(
        self, *, email: str | None = None, phone: str | None = None, family_name: str | None = None
    ) -> list[Member]:
        filters = (("emailAddress", email), ("phoneNumber", phone), ("familyName", family_name))
        params = {k: v for k, v in filters if v}
        return self._items("member", Member, self._request("GET", "/v1/members", params=params))

    def get_stay_records(self, stay_id: str) -> list[StayRecord]:
        return self._items("stay", StayRecord, self._request("GET", f"/v1/stays/{stay_id}"))

    def find_stays(
        self, *, member_number: str | None = None, partner_confirmation: str | None = None
    ) -> list[StayRecord]:
        params = {k: v for k, v in (("loyaltyId", member_number), ("partnerConfirmation", partner_confirmation)) if v}
        return self._items("stay", StayRecord, self._request("GET", "/v1/stays", params=params))

    def get_ledger(self, member_number: str) -> list[LedgerEntry]:
        entries: list[LedgerEntry] = []
        cursor: str | None = None
        page = 0
        while True:
            params = {"limit": str(self.page_size), **({"cursor": cursor} if cursor else {})}
            try:
                body = self._request("GET", f"/v1/members/{member_number}/ledger", params=params)
            except (TemporarilyUnavailable, UpstreamTimeout, RateLimited) as err:
                if page == 0:
                    raise
                raise PartialResult(f"ledger read failed after {page} page(s): {err}", code="partial_result") from err
            entries.extend(self._items("ledger_entry", LedgerEntry, body))
            cursor = body.get("nextCursor") if isinstance(body, dict) else None
            page += 1
            if not cursor:
                return entries

    def get_pending_postings(self, stay_id: str) -> list[PendingPosting]:
        body = self._request("GET", "/v1/posting-queue", params={"confirmationNumber": stay_id})
        return self._items("posting_queue_item", PendingPosting, body)

    def find_adjustment(self, idempotency_key: str) -> AdjustmentResult | None:
        body = self._request("GET", "/v1/adjustments", params={"idempotencyKey": idempotency_key})
        found = self._items("adjustment", AdjustmentResult, body)
        return found[0] if found else None

    # ---------- writes ----------

    def create_ticket(self, *, subject: str, body: str, member_number: str | None = None) -> Ticket:
        payload = self.shape.to_upstream("ticket", {"subject": subject, "body": body, "member_number": member_number})
        return self._record("ticket", Ticket, self._request("POST", "/v1/tickets", json_body=payload))

    def submit_adjustment(self, request: AdjustmentRequest, idempotency_key: str) -> AdjustmentResult:
        payload = self.shape.to_upstream(
            "adjustment",
            {
                "member_number": request.member_number,
                "stay_id": request.stay_id,
                "points": request.points,
                "reason_code": request.reason_code,
                "note": request.note,
                "requested_by": request.requested_by,
            },
        )
        body = self._request(
            "POST", "/v1/adjustments", json_body=payload, write=True, headers={"Idempotency-Key": idempotency_key}
        )
        return self._record("adjustment", AdjustmentResult, body)

    # ---------- plumbing ----------

    def _headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        correlation_id = correlation.current() or uuid.uuid4().hex
        headers = {"Authorization": f"Bearer {self._token}", "X-Correlation-ID": correlation_id}
        if self.sim_time:
            headers["X-Sim-Time"] = self.sim_time
        if self.fault:
            headers["X-Mock-Fault"] = self.fault
        return {**headers, **(extra or {})}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        write: bool = False,
    ) -> Any:
        attempt = 0
        while True:
            if self.breaker is not None and not self.breaker.allow():
                # Nothing is sent, so this is safe even for a write, and the caller's own retry rules apply.
                raise TemporarilyUnavailable("the customer system is failing; calls are paused", code="circuit_open")
            err = self._attempt(method, path, params, json_body, headers, write)
            if self.breaker is not None:
                if isinstance(err, UNHEALTHY):
                    self.breaker.record_failure()
                else:
                    self.breaker.record_success()  # an answer, even "not found", means the system is up
            if not isinstance(err, CustomerSystemError):
                return err
            if err.retryable and attempt < self.max_retries:
                wait = err.retry_after_seconds if isinstance(err, RateLimited) else 0.2 * 2**attempt
                self.sleep(min(wait, MAX_RETRY_WAIT_SECONDS))
                attempt += 1
                continue
            raise err

    def _attempt(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None,
        json_body: dict[str, Any] | None,
        headers: dict[str, str] | None,
        write: bool,
    ) -> Any:
        """The parsed body on success, or the typed error (returned, so `_request` decides about retries)."""
        try:
            resp = self.client.request(method, path, params=params, json=json_body, headers=self._headers(headers))
        except httpx.ConnectError as exc:  # nothing was sent: safe to retry, even a write
            return TemporarilyUnavailable(f"cannot connect: {exc}", code="connect_error")
        except httpx.TimeoutException as exc:
            if write:
                return UncertainOutcome(f"write timed out; outcome unknown: {exc}", code="timeout")
            return UpstreamTimeout(f"read timed out: {exc}", code="timeout")
        except httpx.TransportError as exc:
            if write:
                return UncertainOutcome(f"connection lost during write; outcome unknown: {exc}", code="transport")
            return TemporarilyUnavailable(f"transport error: {exc}", code="transport")
        corr = resp.headers.get("X-Correlation-ID")
        status = resp.status_code
        if status in (200, 201):
            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                return MalformedResponse(f"response is not valid JSON: {exc}", code="malformed", correlation_id=corr)
        code, detail = self._problem(resp)
        if status in (401, 403):
            return AuthenticationFailed(detail, code=code, correlation_id=corr)
        if status == 404:
            return RecordNotFound(detail, code=code, correlation_id=corr)
        if status == 409:
            return IdempotencyConflict(detail, code=code, correlation_id=corr)
        if status in (400, 422):
            return RequestRejected(detail, code=code, correlation_id=corr)
        if status == 429:
            retry = float(resp.headers.get("Retry-After", "1"))
            return RateLimited(detail, retry_after_seconds=retry, code=code, correlation_id=corr)
        if status == 503:
            return TemporarilyUnavailable(detail, code=code, correlation_id=corr)
        if write:  # 500, 502, 504 after a write was sent: it may have been applied
            return UncertainOutcome(
                f"{status} after a write; outcome unknown: {detail}", code=code, correlation_id=corr
            )
        if status == 504:
            return UpstreamTimeout(detail, code=code, correlation_id=corr)
        return TemporarilyUnavailable(f"{status}: {detail}", code=code, correlation_id=corr)

    @staticmethod
    def _problem(resp: httpx.Response) -> tuple[str, str]:
        try:
            body = resp.json()
            return str(body.get("code", "")), str(body.get("detail") or body.get("title") or resp.reason_phrase)
        except (json.JSONDecodeError, ValueError, AttributeError):
            return "", resp.reason_phrase

    def _record(self, entity: str, record_type: type[T], body: Any) -> T:
        if not isinstance(body, dict):
            raise MalformedResponse(f"expected an object for {entity}", code="malformed")
        try:
            values = self.shape.to_canonical(entity, body, required_fields(record_type))
        except ShapeError as exc:
            raise SchemaMismatch(str(exc), code="schema_mismatch") from exc
        try:
            return record_type(**values)
        except TypeError as exc:
            raise SchemaMismatch(f"{entity}: {exc}", code="schema_mismatch") from exc

    def _items(self, entity: str, record_type: type[T], body: Any) -> list[T]:
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise MalformedResponse(f"expected an object with an items list for {entity}", code="malformed")
        return [self._record(entity, record_type, item) for item in body["items"]]
