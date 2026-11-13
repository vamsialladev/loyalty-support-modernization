"""Every protocol call is rate-limited and audited, like a REST call (spec G.2 harness integration).

Stage 7's call order: rate limit, then permission, then the work, then the audit record, with denied and failed calls
recorded too.

The audit keeps a hash of the arguments, not the arguments, so member details don't spread into the log
(`hotel-tools-mcp` decision 5, reused). The correlation ID ties the record to the request and to any upstream call.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app import correlation
from app.domain.roles import Identity
from app.services import rate_limit
from app.services.instrumentation import record_system

PER_MINUTE = 120  # per caller, across all of that caller's protocol calls


def arguments_hash(arguments: Any) -> str:
    text = json.dumps(arguments, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def limit(s: Session, who: Identity, per_minute: int = PER_MINUTE) -> None:
    """Raises `rate_limit.RateLimited`. Keyed by the caller, so one noisy client can't use up another's allowance."""
    rate_limit.hit(s, f"protocol:{who.username}", per_minute, 60)


def audit(s: Session, who: Identity, protocol: str, operation: str, outcome: str, **detail: Any) -> None:
    """One system event per call, committed with the caller's transaction."""
    if correlation_id := correlation.current():
        detail["correlation_id"] = correlation_id
    record_system(s, who, f"{protocol}_call"[:48], operation=operation[:64], outcome=outcome[:48], **detail)
