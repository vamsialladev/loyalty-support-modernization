"""Security events: one classified view over the audit tables, a SIEM-ready export, retention (spec C.10, E7; SEC-20,
ENT-31).

The events are already written where they happen, as append-only audit rows (`system_events`, `case_events`;
ADR-0058): failed sign-ins, denied access, rate limits, account and token changes, recovery, the kill switch, policy
publishing, approvals and executions, AI runs stopped by a budget. This module **classifies** them (category,
outcome, severity) from one table below, so nothing is logged twice and a new event type is one line here.

Minimal content: event rows hold codes and usernames, never passwords, tokens, request text or case notes. A failed
sign-in records no username at all (it may be a mistyped password). Only administrators and auditors read them.

    python -m app.services.security_events --since 2026-11-01 --out exports/security-2026-11.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.business_time import format_utc
from app.domain.roles import Identity, NotPermitted, Role
from app.persistence.models import Case, CaseEvent, SystemEvent

READERS = (Role.ADMINISTRATOR, Role.AUDITOR)
DEFAULT_RETENTION_DAYS = 400  # for expiring refusals: a year plus a quarter, for year-over-year review; an assumption

AUTH, ACCESS, CHANGE, PRIVILEGE, EXECUTION, BUDGET = (
    "authentication",
    "access",
    "configuration",
    "privilege",
    "execution",
    "budget",
)


@dataclass(frozen=True)
class Kind:
    category: str
    outcome: str  # success | failure | unknown (ECS event.outcome)
    severity: int  # 1 info, 2 notice, 3 warning, 4 high


# action -> classification. Anything not listed is not a security event.
KINDS: dict[str, Kind] = {
    "sign_in_failed": Kind(AUTH, "failure", 2),
    "csrf_failed": Kind(ACCESS, "failure", 3),
    "authorization_denied": Kind(ACCESS, "failure", 3),
    "rate_limited": Kind(ACCESS, "failure", 2),
    "account_activated": Kind(PRIVILEGE, "success", 3),
    "account_deactivated": Kind(PRIVILEGE, "success", 3),
    "role_changed_by_provider": Kind(PRIVILEGE, "success", 4),
    "recovery_issued": Kind(PRIVILEGE, "success", 3),
    "recovery_used": Kind(AUTH, "success", 3),
    "api_token_issued": Kind(PRIVILEGE, "success", 3),
    "api_token_revoked": Kind(PRIVILEGE, "success", 3),
    "kill_switch_changed": Kind(CHANGE, "success", 4),
    "policy_draft_created": Kind(CHANGE, "success", 2),
    "policy_published": Kind(CHANGE, "success", 3),
    "policy_publish_refused": Kind(CHANGE, "failure", 2),
    "retention_applied": Kind(CHANGE, "success", 2),
    "data_subject_export": Kind(ACCESS, "success", 3),
    "data_subject_erasure": Kind(CHANGE, "success", 3),
    "job_requeued": Kind(CHANGE, "success", 2),
    "adjustment_approved": Kind(EXECUTION, "success", 2),
    "adjustment_rejected": Kind(EXECUTION, "success", 2),
    "approval_invalidated": Kind(EXECUTION, "success", 3),
    "adjustment_executed": Kind(EXECUTION, "success", 2),
    "execution_refused_duplicate": Kind(EXECUTION, "failure", 3),
    "execution_conflict": Kind(EXECUTION, "failure", 4),
    "execution_gave_up": Kind(EXECUTION, "failure", 3),
    "execution_unknown": Kind(EXECUTION, "unknown", 4),
    "ai_budget_exhausted": Kind(BUDGET, "failure", 3),
}
# Detail fields that may leave in an export: codes and names only (ENT-31 field map in docs/siem-field-map.md).
SAFE_DETAIL = frozenset(
    {"method", "path", "kind", "engaged", "policy", "version", "points", "stop", "name", "username"}
)


@dataclass(frozen=True)
class SecurityEvent:
    at_utc: str
    source: str  # system | case
    action: str
    category: str
    outcome: str
    severity: int
    actor: str
    actor_kind: str
    case_reference: str | None
    correlation_id: str | None
    detail: dict[str, Any]


def require_reader(who: Identity) -> None:
    if who.role not in READERS:
        raise NotPermitted("only administrators and auditors read security events")


def _action(source: str, action: str, detail: dict[str, Any]) -> str:
    if source == "case" and action == "ai_run_finished" and detail.get("stop") == "budget_exhausted":
        return "ai_budget_exhausted"
    return action


def events(s: Session, who: Identity, since_utc: str = "", limit: int = 10_000) -> list[SecurityEvent]:
    require_reader(who)
    found: list[SecurityEvent] = []
    for row in s.scalars(select(SystemEvent).where(SystemEvent.at_utc >= since_utc).order_by(SystemEvent.id)):
        kind = KINDS.get(row.action)
        if kind:
            found.append(_event("system", row.action, kind, row.actor, row.actor_kind, row.at_utc, row.detail, None))
    query = (
        select(CaseEvent, Case.reference)
        .join(Case, Case.id == CaseEvent.case_id)
        .where(Case.customer_id == who.customer_id, CaseEvent.at_utc >= since_utc)
        .order_by(CaseEvent.id)
    )
    for event, reference in s.execute(query):
        action = _action("case", event.action, event.detail)
        kind = KINDS.get(action)
        if kind:
            found.append(
                _event("case", action, kind, event.actor, event.actor_kind, event.at_utc, event.detail, reference)
            )
    found.sort(key=lambda e: e.at_utc)
    return found[-limit:]


def _event(
    source: str,
    action: str,
    kind: Kind,
    actor: str,
    actor_kind: str,
    at_utc: str,
    detail: dict[str, Any],
    reference: str | None,
) -> SecurityEvent:
    safe = {k: v for k, v in (detail or {}).items() if k in SAFE_DETAIL and isinstance(v, str | int | bool)}
    return SecurityEvent(
        at_utc,
        source,
        action,
        kind.category,
        kind.outcome,
        kind.severity,
        actor,
        actor_kind,
        reference,
        (detail or {}).get("correlation_id"),
        safe,
    )


def to_ecs(event: SecurityEvent) -> dict[str, Any]:
    """Elastic Common Schema field names, the most widely read by SIEMs (docs/siem-field-map.md)."""
    doc: dict[str, Any] = {
        "@timestamp": event.at_utc,
        "event": {
            "kind": "event",
            "category": [event.category],
            "action": event.action,
            "outcome": event.outcome,
            "severity": event.severity,
            "dataset": f"loyalty.{event.source}_events",
        },
        "user": {"name": event.actor},
        "labels": {"actor_kind": event.actor_kind, "synthetic": "true"},
        "service": {"name": "loyalty-app"},
    }
    if event.correlation_id:
        doc["labels"]["correlation_id"] = event.correlation_id
    if event.case_reference:
        doc["labels"]["case_reference"] = event.case_reference
    if event.detail:
        doc["loyalty"] = {"detail": event.detail}
    return doc


def jsonl(items: Iterable[SecurityEvent]) -> Iterator[str]:
    for event in items:
        yield json.dumps(to_ecs(event), sort_keys=True) + "\n"


# Retention (C.10). Audit history is append-only for the app's role (ADR-0058) and stays as the audit record: every
# privilege, configuration and execution event is kept. Only the high-volume refusals below expire, and only the
# owner role can delete them (`--purge`, run through the migrate service), so the running app can't erase its trail.
EXPIRING = frozenset({"sign_in_failed", "authorization_denied", "rate_limited", "csrf_failed"})


def purge(s: Session, days: int, now: datetime | None = None) -> int:
    """Delete expiring refusals older than `days`. Run as the owner role; the app role is refused by the database."""
    if days < 30:
        raise ValueError("keep at least 30 days, so an investigation can still see a recent attack")
    cutoff = format_utc((now or datetime.now(UTC)) - timedelta(days=days))
    result = s.execute(delete(SystemEvent).where(SystemEvent.action.in_(EXPIRING), SystemEvent.at_utc < cutoff))
    s.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.services.security_events")
    parser.add_argument("--since", default="", help="YYYY-MM-DD (UTC)")
    parser.add_argument("--out", type=Path, help="JSON lines file; default: standard output")
    parser.add_argument(
        "--purge", action="store_true", help="delete expiring refusals older than the retention (owner role)"
    )
    args = parser.parse_args(argv)

    from app.persistence.database import make_engine, make_sessions
    from app.settings import AppSettings

    if args.purge:
        # Through the migrate service, which connects as the owner role:
        #   docker compose run --rm migrate python -m app.services.security_events --purge
        # As the app role, the database refuses the delete (audit history is append-only for it).
        days = int(os.environ.get("SECURITY_EVENT_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        with make_sessions(make_engine(os.environ["DATABASE_URL"]))() as s:
            print(f"purged {purge(s, days)} expiring security events older than {days} days")
        return 0

    settings = AppSettings.from_env()
    reader = Identity(0, "export-cli", "Security export", Role.AUDITOR, customer_id=settings.customer_id)
    with make_sessions(make_engine(settings.database_url))() as s:
        lines = list(jsonl(events(s, reader, args.since)))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(lines), encoding="utf-8")
    else:
        sys.stdout.writelines(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
