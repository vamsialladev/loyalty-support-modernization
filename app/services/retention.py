"""Retention, data-subject requests and legal hold (spec C.3; SEC-06, ENT-09, ENT-10). SYNTHETIC data; not legal advice.

Removing personal data keeps the case's shape: what was decided and what was credited stay, because that's the audit
record. `case_events` are append-only and hold no message text. Adjustments keep a member number and an amount: a
financial record, kept on purpose. **Backups aren't touched:** data lasts in them until they expire
(`docs/known-limitations.md`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.domain.business_time import format_utc
from app.domain.case_states import TERMINAL, CaseState
from app.domain.roles import Identity, NotPermitted, Role, require_administrator
from app.persistence.models import (
    AdjustmentRequestRow,
    Case,
    CaseAttachment,
    CaseEvidence,
    CaseNote,
    CaseRequest,
    Recommendation,
    SystemEvent,
)
from app.services import jobs
from app.services.instrumentation import record, record_system

DEFAULT_RETENTION_DAYS = 365
REMOVED = "(removed)"


@dataclass(frozen=True)
class RetentionReport:
    examined: int
    removed: int
    held: int
    still_open: int


def _member_cases(s: Session, who: Identity, member_number: str) -> list[Case]:
    """Cases about this member: by an adjustment, or by a confirmed result."""
    ids = set(
        s.scalars(select(AdjustmentRequestRow.case_id).where(AdjustmentRequestRow.member_number == member_number))
    )
    ids |= set(s.scalars(select(Recommendation.case_id).where(Recommendation.member_number == member_number)))
    ids |= set(s.scalars(select(CaseRequest.case_id).where(CaseRequest.form_member_number == member_number)))
    if not ids:
        return []
    query = select(Case).where(Case.id.in_(ids), Case.customer_id == who.customer_id).order_by(Case.id)
    return list(s.scalars(query))


def export_member(s: Session, who: Identity, member_number: str) -> dict[str, Any]:
    """A data-subject access export: what this system holds about a member. Records it was done, not what was in it."""
    require_administrator(who)
    out: dict[str, Any] = {"member_number": member_number, "synthetic": True, "cases": []}
    for case in _member_cases(s, who, member_number):
        requests = s.scalars(select(CaseRequest).where(CaseRequest.case_id == case.id))
        adjustments = s.scalars(select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id == case.id))
        out["cases"].append(
            {
                "reference": case.reference,
                "status": case.status,
                "resolution": case.resolution_code,
                "requests": [{"received": r.received_at_utc, "text": r.text} for r in requests],
                "adjustments": [{"stay": a.stay_id, "points": a.points, "status": a.status} for a in adjustments],
            }
        )
    record_system(s, who, "data_subject_export", cases=len(out["cases"]))
    s.commit()
    return out


def _remove_personal_data(s: Session, case: Case) -> None:
    for request in s.scalars(select(CaseRequest).where(CaseRequest.case_id == case.id)):
        request.text = REMOVED
        request.sender_email = request.form_name = None
        request.form_member_number = request.form_confirmation = None
        request.attachment_names = []
    for note in s.scalars(select(CaseNote).where(CaseNote.case_id == case.id)):
        note.body = REMOVED
    s.execute(delete(CaseEvidence).where(CaseEvidence.case_id == case.id))
    s.execute(delete(CaseAttachment).where(CaseAttachment.case_id == case.id))
    for rec in s.scalars(select(Recommendation).where(Recommendation.case_id == case.id)):
        rec.ai = None
        rec.reasons = []
    case.resolution_note = None
    case.personal_data_removed_at_utc = utc_now()


def erase_member(s: Session, who: Identity, member_number: str) -> RetentionReport:
    """An erasure request. A case on legal hold or still open is left as it is, and counted. Credits stay: they're
    financial records, and removing them would break the ledger's audit trail."""
    require_administrator(who)
    cases = _member_cases(s, who, member_number)
    removed = held = still_open = 0
    for case in cases:
        if case.legal_hold:
            held += 1
        elif CaseState(case.status) not in TERMINAL:
            still_open += 1
        else:
            _remove_personal_data(s, case)
            record(s, case, who, "personal_data_removed", reason="data_subject_request")
            removed += 1
    record_system(s, who, "data_subject_erasure", removed=removed, held=held, still_open=still_open)
    s.commit()
    return RetentionReport(len(cases), removed, held, still_open)


def set_legal_hold(s: Session, who: Identity, case: Case, hold: bool, reason: str) -> None:
    """Only an administrator, and always with a reason. Audited on the case."""
    if who.role is not Role.ADMINISTRATOR:
        raise NotPermitted("only an administrator sets a legal hold")
    if not reason.strip():
        raise ValueError("give the reason")
    case.legal_hold = hold
    record(s, case, who, "legal_hold_set" if hold else "legal_hold_released", reason=reason.strip()[:200])
    s.commit()


def apply_retention(
    s: Session, who: Identity, customer_id: str, days: int = DEFAULT_RETENTION_DAYS, *, dry_run: bool = False
) -> RetentionReport:
    """Closed cases older than `days` lose their personal data. Safe to run again."""
    cutoff = format_utc(datetime.now(UTC) - timedelta(days=days))
    query = select(Case).where(
        Case.customer_id == customer_id, Case.updated_at_utc < cutoff, Case.personal_data_removed_at_utc.is_(None)
    )
    examined = removed = held = still_open = 0
    for case in s.scalars(query).all():
        examined += 1
        if case.legal_hold:
            held += 1
        elif CaseState(case.status) not in TERMINAL:
            still_open += 1
        else:
            removed += 1
            if not dry_run:
                _remove_personal_data(s, case)
                record(s, case, who, "personal_data_removed", reason="retention")
    if not dry_run:
        record_system(s, who, "retention_applied", removed=removed, held=held, still_open=still_open, days=days)
    s.commit()
    return RetentionReport(examined, removed, held, still_open)


def retention_sweep(s: Session, customer_id: str, days: int | None = None) -> RetentionReport | None:
    """Once a day at most, from the worker. The last run is in `system_events`, so a restart doesn't repeat it."""
    last = s.scalars(
        select(SystemEvent).where(SystemEvent.action == "retention_applied").order_by(SystemEvent.id.desc()).limit(1)
    ).first()
    since = format_utc(datetime.now(UTC) - timedelta(days=1))
    if last is not None and last.at_utc[:19] + "Z" > since:
        return None
    keep = days if days is not None else int(os.environ.get("RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
    return apply_retention(s, jobs.SYSTEM, customer_id, keep)
