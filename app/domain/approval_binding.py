"""Approval binding (spec B.10, Appendix B; WP-03, ADR-0059). Pure: canonical hashes and an HMAC, standard library.

An approval is bound to the exact action it approved. The binding is keyed, so someone who can write to the database but
doesn't hold the app's secret can't edit a row and recompute it. It doesn't stop someone who holds both.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Any

_KEY_LABEL = b"lsm-approval-binding-v1"  # keeps this key apart from any other use of the app's secret


@dataclass(frozen=True)
class BoundAction:
    customer_id: str
    request_id: int
    approval_uid: str
    member_number: str
    stay_id: str
    points: int
    reason_code: str
    policy_refs: tuple[str, ...]
    evidence_hash: str
    approver: str
    expires_at_utc: str


def canonical(value: Any) -> bytes:
    """One byte sequence for one value, whatever order its keys were built in."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def evidence_hash(facts: Any) -> str:
    return hashlib.sha256(canonical(facts)).hexdigest()


def binding_key(secret: str) -> bytes:
    if not secret:
        raise ValueError("no secret to bind approvals with")
    return hmac.new(secret.encode("utf-8"), _KEY_LABEL, hashlib.sha256).digest()


def binding_mac(action: BoundAction, secret: str) -> str:
    return hmac.new(binding_key(secret), canonical(asdict(action)), hashlib.sha256).hexdigest()


def binding_holds(action: BoundAction, secret: str, stored_mac: str | None) -> bool:
    return stored_mac is not None and hmac.compare_digest(binding_mac(action, secret), stored_mac)
