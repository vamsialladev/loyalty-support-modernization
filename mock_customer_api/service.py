"""Queries and the adjustment write. Canonical dicts in, canonical dicts out; the API layer renders the customer shape.

The simulated clock (ADR-0037): every read takes `at` (UTC text). Ledger entries posted after `at` and queue items
not yet queued at `at` are invisible, so one seeded world serves every benchmark case at its own request time.
"""

from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from mock_customer_api import db

MAX_PAGE = 100


class Problem(Exception):
    """An RFC 9457 problem the API returns as application/problem+json."""

    def __init__(self, status: int, code: str, title: str, detail: str = "", retry_after: int | None = None) -> None:
        super().__init__(f"{status} {code}: {title}")
        self.status, self.code, self.title, self.detail, self.retry_after = status, code, title, detail, retry_after


def now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise_ts(text: str) -> str:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Problem(400, "invalid_sim_time", "X-Sim-Time is not an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise Problem(400, "invalid_sim_time", "X-Sim-Time must include a time zone (use Z for UTC)")
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_dict(row: db.Base) -> dict[str, Any]:
    return {c.key: getattr(row, c.key) for c in row.__mapper__.column_attrs}


# ---------- reads ----------


def get_member(s: Session, member_number: str) -> dict[str, Any]:
    member = s.get(db.Member, member_number)
    if member is None:
        raise Problem(404, "member_not_found", "No member with this loyalty ID")
    return as_dict(member)


def _fold(name: str) -> str:
    """Case and accents don't count: the name search many loyalty platforms offer (contract 1.1.0, ADR-0062)."""
    return "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)).casefold().strip()


def find_members(
    s: Session, email: str | None, phone: str | None, family_name: str | None = None
) -> list[dict[str, Any]]:
    if not email and not phone and not family_name:
        raise Problem(400, "missing_filter", "Give emailAddress, phoneNumber or familyName")
    query = select(db.Member)
    if email:
        query = query.where(db.Member.email == email)  # exact match, like the legacy search
    if phone:
        query = query.where(db.Member.phone == phone)
    rows = s.scalars(query.order_by(db.Member.member_number)).all()
    if family_name:
        rows = [m for m in rows if _fold(m.last_name) == _fold(family_name)]
    return [as_dict(m) for m in rows[:MAX_PAGE]]


def get_stay_records(s: Session, stay_id: str) -> list[dict[str, Any]]:
    rows = s.scalars(select(db.Stay).where(db.Stay.stay_id == stay_id).order_by(db.Stay.record_id)).all()
    if not rows:
        raise Problem(404, "stay_not_found", "No stay with this confirmation number")
    return [as_dict(r) for r in rows]


def find_stays(s: Session, member_number: str | None, partner_confirmation: str | None) -> list[dict[str, Any]]:
    if not member_number and not partner_confirmation:
        raise Problem(400, "missing_filter", "Give loyaltyId or partnerConfirmation")
    query = select(db.Stay)
    if member_number:
        query = query.where(db.Stay.member_number == member_number)
    if partner_confirmation:
        query = query.where(db.Stay.partner_confirmation == partner_confirmation)
    return [as_dict(r) for r in s.scalars(query.order_by(db.Stay.record_id).limit(MAX_PAGE))]


def encode_cursor(posted: str, entry_id: str) -> str:
    return base64.urlsafe_b64encode(f"{posted}|{entry_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        posted, entry_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Problem(400, "invalid_cursor", "The cursor is not valid") from exc
    return posted, entry_id


def ledger_page(
    s: Session, member_number: str, at: str, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    get_member(s, member_number)
    limit = max(1, min(limit, MAX_PAGE))
    query = select(db.LedgerEntry).where(
        db.LedgerEntry.member_number == member_number, db.LedgerEntry.posted_at_utc <= at
    )
    if cursor:
        query = query.where(tuple_(db.LedgerEntry.posted_at_utc, db.LedgerEntry.entry_id) > decode_cursor(cursor))
    rows = s.scalars(query.order_by(db.LedgerEntry.posted_at_utc, db.LedgerEntry.entry_id).limit(limit + 1)).all()
    items = [as_dict(r) for r in rows[:limit]]
    nxt = encode_cursor(rows[limit - 1].posted_at_utc, rows[limit - 1].entry_id) if len(rows) > limit else None
    return items, nxt


def pending_postings(s: Session, stay_id: str, at: str) -> list[dict[str, Any]]:
    query = select(db.PostingQueueItem).where(
        db.PostingQueueItem.stay_id == stay_id,
        db.PostingQueueItem.queued_at_utc <= at,
        db.PostingQueueItem.expected_post_at_utc > at,
    )
    return [as_dict(r) for r in s.scalars(query.order_by(db.PostingQueueItem.item_id))]


def find_adjustment(s: Session, key: str) -> list[dict[str, Any]]:
    row = s.scalars(select(db.Adjustment).where(db.Adjustment.idempotency_key == key)).first()
    return [as_dict(row)] if row else []


# ---------- writes ----------


def request_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _replay(record: db.IdempotencyRecord, digest: str) -> tuple[int, dict[str, Any], bool]:
    if record.request_hash != digest:
        raise Problem(409, "idempotency_conflict", "This idempotency key was already used for a different request")
    return record.status_code, json.loads(record.response_body), True


def submit_adjustment(
    factory: sessionmaker[Session], key: str, body: dict[str, Any], at: str, crash_before_commit: bool = False
) -> tuple[int, dict[str, Any], bool]:
    """Apply an adjustment once per idempotency key. Returns (status, canonical result, replayed?).

    The idempotency record, the adjustment and its ledger entry are written in ONE transaction: either all three
    commit or none do. A concurrent request with the same key loses on the primary key and replays the winner.
    """
    if not key or len(key) > 200:
        raise Problem(400, "idempotency_key_required", "Send an Idempotency-Key header (1-200 characters)")
    digest = request_hash(body)
    s = factory()
    try:
        existing = s.get(db.IdempotencyRecord, key)
        if existing is not None:
            return _replay(existing, digest)
        member = s.get(db.Member, body["member_number"])
        if member is None:
            raise Problem(404, "member_not_found", "No member with this loyalty ID")
        if member.status == "merged":
            raise Problem(422, "account_merged", "This account was merged; credit the account it was merged into")
        if s.scalar(select(func.count()).select_from(db.Stay).where(db.Stay.stay_id == body["stay_id"])) == 0:
            raise Problem(404, "stay_not_found", "No stay with this confirmation number")
        suffix = uuid.uuid4().hex[:12].upper()
        result = {
            "adjustment_id": f"ADJ-{suffix}",
            "idempotency_key": key,
            "member_number": body["member_number"],
            "stay_id": body["stay_id"],
            "points": body["points"],
            "reason_code": body["reason_code"],
            "note": body.get("note"),
            "requested_by": body["requested_by"],
            "created_at_utc": at,
            "ledger_entry_id": f"L-ADJ-{suffix}",
            "status": "applied",
        }
        s.add(
            db.IdempotencyRecord(
                key=key,
                request_hash=digest,
                status_code=201,
                response_body=json.dumps(result, sort_keys=True),
                created_at_utc=at,
            )
        )
        s.flush()  # a concurrent duplicate key fails here (or blocks until the winner commits, then fails)
        s.add(
            db.LedgerEntry(
                entry_id=result["ledger_entry_id"],
                member_number=body["member_number"],
                stay_id=body["stay_id"],
                kind="adjustment",
                points=body["points"],
                posted_at_utc=at,
                reverses_entry_id=None,
            )
        )
        s.add(db.Adjustment(**result))
        s.flush()
        if crash_before_commit:
            raise Problem(500, "internal_error", "Injected failure before commit (test fault)")
        s.commit()
        return 201, result, False
    except IntegrityError:
        s.rollback()
        s.close()
        with factory() as again:
            record = again.get(db.IdempotencyRecord, key)
            if record is None:
                raise Problem(
                    503, "conflict_retry", "Concurrent write; retry with the same key", retry_after=1
                ) from None
            return _replay(record, digest)
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def create_ticket(factory: sessionmaker[Session], body: dict[str, Any], at: str) -> dict[str, Any]:
    with factory() as s:
        ticket = db.Ticket(
            ticket_id=f"TCK-{uuid.uuid4().hex[:10].upper()}",
            member_number=body.get("member_number"),
            subject=body["subject"],
            body=body["body"],
            created_at_utc=at,
        )
        s.add(ticket)
        s.commit()
        return as_dict(ticket)


# ---------- seed and reset ----------


def counts(s: Session) -> dict[str, int]:
    return {t.__tablename__: int(s.scalar(select(func.count()).select_from(t)) or 0) for t in db.ALL_TABLES}


def wipe(s: Session) -> None:
    for table in db.ALL_TABLES:
        s.execute(delete(table))
