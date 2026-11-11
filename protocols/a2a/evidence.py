"""The evidence artifact the reservation specialist returns, and how the coordinator checks it (spec G.4).

The specialist reads the reservation system (the PMS, here the mock customer API) for one member and returns what a
loyalty agent needs to see a stay: IDs, property, dates, status, booking channel, and any points still queued to post.
Not the guest's name, room revenue or rate, which loyalty doesn't need from this call. Every artifact carries its
provenance (which system, which records, read when, under which correlation ID) and a hash of its content, so the
coordinator can tell it arrived unchanged and a reviewer can trace it back.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.clock import utc_now
from app.ports.customer_systems import CustomerSystems

SOURCE_SYSTEM = "reservations (PMS), via the mock customer API"
SPECIALIST: Literal["reservation-evidence-specialist"] = "reservation-evidence-specialist"
MAX_STAYS = 50


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRequest(_Closed):
    """What the coordinator may ask. The customer isn't here: it comes from the caller's token."""

    case_reference: str = Field(min_length=1, max_length=32)
    member_number: str = Field(min_length=1, max_length=32)
    stay_id: str | None = Field(default=None, max_length=32)


class StayEvidence(_Closed):
    stay_id: str
    record_id: str
    property: str
    arrival_date: str
    nights: int
    checkout_at_utc: str
    status: str
    member_on_booking: bool
    channel: str | None


class QueuedPosting(_Closed):
    item_id: str
    stay_id: str
    points: int
    expected_post_at_utc: str


class Provenance(_Closed):
    source_system: str
    agent: Literal["reservation-evidence-specialist"]
    record_ids: list[str]
    read_at_utc: str
    correlation_id: str | None


class EvidenceArtifact(_Closed):
    case_reference: str
    member_number: str
    stays: list[StayEvidence]
    pending_postings: list[QueuedPosting]
    provenance: Provenance
    content_sha256: str


def _canonical(value: Any) -> Any:
    """A2A 1.0 carries data parts as a protobuf `Struct`, where every number is a double: 3 arrives as 3.0. So whole
    numbers are compared as integers, or a correct artifact would fail its own hash."""
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def content_hash(body: dict[str, Any]) -> str:
    """SHA-256 over the canonical JSON of everything except the hash itself."""
    rest = _canonical({k: v for k, v in body.items() if k != "content_sha256"})
    text = json.dumps(rest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def gather(systems: CustomerSystems, request: EvidenceRequest, correlation_id: str | None) -> dict[str, Any]:
    """The specialist's read. Only stays on this member's own profile; one stay if one was asked for, and only if
    it's theirs. Raises the customer systems' own errors (`RecordNotFound`, `UpstreamTimeout`, ...)."""
    records = [r for r in systems.find_stays(member_number=request.member_number) if r.stay_id]
    if request.stay_id is not None:
        records = [r for r in records if r.stay_id == request.stay_id]
    records = records[:MAX_STAYS]
    stays = [
        StayEvidence(
            stay_id=r.stay_id,
            record_id=r.record_id,
            property=r.property,
            arrival_date=r.arrival_date,
            nights=r.nights,
            checkout_at_utc=r.checkout_at_utc,
            status=r.status,
            member_on_booking=r.member_on_booking,
            channel=r.channel,
        ).model_dump()
        for r in records
    ]
    postings = [
        QueuedPosting(
            item_id=p.item_id, stay_id=p.stay_id, points=p.points, expected_post_at_utc=p.expected_post_at_utc
        ).model_dump()
        for stay_id in dict.fromkeys(r.stay_id for r in records)
        for p in systems.get_pending_postings(stay_id)
        if p.member_number == request.member_number
    ]
    body: dict[str, Any] = {
        "case_reference": request.case_reference,
        "member_number": request.member_number,
        "stays": stays,
        "pending_postings": postings,
        "provenance": Provenance(
            source_system=SOURCE_SYSTEM,
            agent=SPECIALIST,
            record_ids=[s["record_id"] for s in stays] + [p["item_id"] for p in postings],
            read_at_utc=utc_now(),
            correlation_id=correlation_id,
        ).model_dump(),
    }
    body["content_sha256"] = content_hash(body)
    return body


class InvalidArtifact(Exception):
    pass


def check_artifact(data: Any, request: EvidenceRequest) -> EvidenceArtifact:
    """The coordinator's check: the shape is exact, the hash matches, and it's about the member and stay we asked
    for. A remote agent's answer is data, so anything else is refused, not repaired."""
    if not isinstance(data, dict):
        raise InvalidArtifact("not_an_object")
    try:
        artifact = EvidenceArtifact.model_validate(data)
    except ValueError as exc:
        raise InvalidArtifact("schema") from exc
    if artifact.content_sha256 != content_hash(data):
        raise InvalidArtifact("hash_mismatch")
    if artifact.member_number != request.member_number or artifact.case_reference != request.case_reference:
        raise InvalidArtifact("not_what_was_asked")
    if request.stay_id is not None and any(s.stay_id != request.stay_id for s in artifact.stays):
        raise InvalidArtifact("other_stays")
    return artifact
