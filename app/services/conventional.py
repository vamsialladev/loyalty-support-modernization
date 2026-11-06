"""Arm B on the shared case workflow: investigation through the worker, one view of the evidence, recommendations with
citations, the missing-information loop, overrides, and the group's supervisor limit (spec B.8, B.11; ADR-0062,
ADR-0064).

Approval and execution stay on `SharedWritePath`, unchanged, the same as arm A. An agent can't type an amount: the only
way to ask for a credit is the engine's own recommendation.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arms.conventional import signals
from app.arms.conventional.config import conventional_config
from app.arms.conventional.extraction import UnsafeDocument, extract, media_type_for
from app.arms.conventional.identity import Candidate, IdentityClaim
from app.arms.conventional.investigation import ClaimText, Evidence, Investigation, investigate, read_claim
from app.clock import utc_now
from app.domain.approval_binding import evidence_hash
from app.domain.case_states import CaseState
from app.domain.customer_records import Member, StayRecord
from app.domain.eligibility import NextAction, evaluate_stay
from app.domain.policy import MISSING_POINTS, PolicyRef
from app.domain.roles import Identity, require_case_worker
from app.persistence.models import (
    AdjustmentRequestRow,
    Case,
    CaseAttachment,
    CaseEvidence,
    CaseNote,
    CaseRequest,
    Feedback,
    Job,
    Recommendation,
)
from app.ports.customer_systems import CustomerSystems
from app.services import approvals, jobs, policies
from app.services.cases import (
    ARM_B,
    ARM_C,
    CaseNotFound,
    IntakeRequest,
    WorkflowError,
    create_case,
    evidence_rows,
    move,
    read_time,
    request_information,
    requests_of,
)
from app.services.customer_config import customer_config
from app.services.instrumentation import record

INVESTIGATE_JOB = "investigate_case"
INVESTIGATION_EVIDENCE = "consolidated"
ANSWER_EVIDENCE = "member_answer"
CLAIMED_STAY_EVIDENCE = "claimed_stay"
MEMBER_REPLY = "member_reply"
CHANNELS = ("direct", "phone", "ota", "travel_agent")
MIN_OVERRIDE_REASON = 20
RATINGS = ("helpful", "not_helpful")
OPEN_REQUEST_STATUSES = ("pending", "approved", "executing", "execution_unknown", "executed", "execution_conflict")

# The question to send for each thing the engine or the lookup can't settle. All about the member's own records.
PROMPTS = {
    "booking_channel": "How did you book this stay: directly with the hotel, by phone, through an online travel site, "
    "or through a travel agent?",
    "confirmation": "Please send the hotel confirmation number for the stay (for example BR-1234 or ML-1234).",
    "which_stay": "More than one stay could match. Please send the confirmation number for the stay you mean.",
    "second_identifier": "To confirm your account, please send your membership number and its email address.",
    "member_not_found": "We couldn't find your account. Please send your membership number and its email address.",
    "which_member": "To confirm which account is yours, please send your membership number and its email address.",
    "more_stays": "You mentioned another stay. Please send its confirmation number so that we can look at it too.",
}
_CLOSE_CODE_BY_ACTION = {
    NextAction.NO_ADJUSTMENT_CREDITED: "no_adjustment_credited",
    NextAction.NO_ADJUSTMENT_PENDING: "no_adjustment_pending",
    NextAction.WAIT_UNTIL: "wait_until",
    NextAction.NOT_CHECKED_OUT: "not_checked_out",
}
_DENY_CODES = {
    "channel_ineligible": "deny_channel_ineligible",
    "claim_window": "deny_claim_window",
    "not_a_member": "deny_not_a_member",
}
CLOSE_CODES = (
    "no_adjustment_credited",
    "no_adjustment_pending",
    "wait_until",
    "not_checked_out",
    "deny_channel_ineligible",
    "deny_claim_window",
    "deny_not_a_member",
    "deny_other",
)


def _require_arm_b(case: Case) -> None:
    """Arm C is arm B plus the model, so these services are the same for both."""
    if case.arm not in (ARM_B, ARM_C):
        raise WorkflowError("this case is on arm A, which is worked by hand on the legacy screens")


def recommended_close_code(rec: Recommendation) -> str | None:
    """The code the engine's result supports, or None when its result isn't a close (adjust, ask or escalate)."""
    action = NextAction(rec.action)
    if action is NextAction.DENY:
        return _DENY_CODES.get(rec.detail or "")
    return _CLOSE_CODE_BY_ACTION.get(action)


# ---------- attachments: evidence only (Appendix H) ----------


def attachments_of(s: Session, case: Case) -> list[CaseAttachment]:
    query = select(CaseAttachment).where(CaseAttachment.case_id == case.id).order_by(CaseAttachment.id)
    return list(s.scalars(query))


def add_attachment(s: Session, who: Identity, case: Case, filename: str, content: bytes) -> CaseAttachment:
    """Type and size are checked before anything reads it (C.7). The name is cut to its last part and never used as a
    path."""
    require_case_worker(who)
    _require_arm_b(case)
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1][:128]
    try:
        media_type = media_type_for(safe_name, content)
    except UnsafeDocument as exc:
        raise WorkflowError(str(exc)) from exc
    row = CaseAttachment(
        case_id=case.id,
        filename=safe_name,
        media_type=media_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
        added_by=who.username,
        added_at_utc=utc_now(),
    )
    s.add(row)
    s.flush()
    record(s, case, who, "attachment_added", media_type=media_type, size=len(content))
    s.commit()
    return row


# ---------- reading the case ----------


def latest_recommendation(s: Session, case: Case) -> Recommendation | None:
    query = select(Recommendation).where(Recommendation.case_id == case.id).order_by(Recommendation.id.desc())
    return s.scalars(query.limit(1)).first()


def latest_evidence(s: Session, case: Case) -> dict[str, Any] | None:
    rows = [r for r in evidence_rows(s, case) if r.kind == INVESTIGATION_EVIDENCE]
    return rows[-1].snapshot if rows else None


def member_answers(s: Session, case: Case) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    for row in evidence_rows(s, case):
        if row.kind == ANSWER_EVIDENCE:
            answers.update(row.snapshot)
    return answers


def claimed_stay(s: Session, case: Case) -> str | None:
    rows = [r for r in evidence_rows(s, case) if r.kind == CLAIMED_STAY_EVIDENCE]
    return rows[-1].source_ref if rows else None


def group_cases(s: Session, case: Case) -> list[Case]:
    if not case.group_ref:
        return [case]
    return list(s.scalars(select(Case).where(Case.group_ref == case.group_ref).order_by(Case.id)))


def failed_investigation(s: Session, case: Case) -> Job | None:
    """The last investigation job, when it died: the page offers a retry, and says why it can't show a result."""
    query = select(Job).where(Job.case_id == case.id, Job.kind == INVESTIGATE_JOB).order_by(Job.id.desc()).limit(1)
    last = s.scalars(query).first()
    return last if last is not None and last.status == jobs.DEAD else None


def claim_text_for(s: Session, case: Case) -> ClaimText:
    """Every message on the case. A member's reply can correct what they wrote before, so its numbers come first. All
    of this is data: it only ever selects which records get read."""
    requests = requests_of(s, case)
    replies = [r for r in requests if r.contact_channel == MEMBER_REPLY]
    text = "\n".join(r.text for r in requests)
    answers = member_answers(s, case)
    numbers: list[str] = []
    confirmations: list[str] = []
    for request in [*reversed(replies), *(r for r in requests if r.contact_channel != MEMBER_REPLY)]:
        if request.form_member_number and request.form_member_number.strip():
            numbers.append(request.form_member_number.strip().upper())
        numbers += signals.member_numbers_in(request.text)
        if request.form_confirmation and request.form_confirmation.strip():
            confirmations.append(request.form_confirmation.strip().upper())
        confirmations += signals.confirmations_in(request.text)
    claimed = claimed_stay(s, case)
    if claimed:
        confirmations = [claimed]
    elif replies and any(r.form_confirmation or signals.confirmations_in(r.text) for r in replies):
        latest = next(r for r in reversed(replies) if r.form_confirmation or signals.confirmations_in(r.text))
        confirmations = [c.strip().upper() for c in (latest.form_confirmation,) if c]
        confirmations += signals.confirmations_in(latest.text)
    name = next((r.form_name for r in requests if r.form_name), None) or signals.signoff_name(requests[0].text)
    email = next((r.sender_email for r in requests if r.sender_email), None)
    attachments = tuple(a for r in requests for a in r.attachment_names)
    documents = tuple(extract(a.filename, a.content) for a in attachments_of(s, case))
    typed = tuple(dict.fromkeys(confirmations))
    from_documents = tuple(dict.fromkeys(x for d in documents for x in (d.confirmation, d.partner_confirmation) if x))
    return ClaimText(
        text=text,
        # What a document says can point at a stay, but it's never one of the two identifiers (Appendix H: evidence
        # only).
        identity=IdentityClaim(tuple(dict.fromkeys(numbers)), email, name, typed),
        confirmations=typed or from_documents[:1],
        documents=documents,
        from_document=not typed and bool(from_documents),
        received_at_utc=case.received_at_utc,
        attachments=attachments,
        stated_channel=answers.get("booking_channel"),
        scope_cleared=bool(answers.get("scope_cleared")),
    )


# ---------- the investigation ----------


def start_investigation(s: Session, who: Identity, case: Case) -> Job:
    """Queue the investigation for the worker. Starting it again while one is running does nothing new (API-02)."""
    require_case_worker(who)
    _require_arm_b(case)
    if case.queue != signals.POINTS_QUEUE:
        raise WorkflowError("this case is in the billing queue, which the billing team works outside this tool")
    state = CaseState(case.status)
    if state is CaseState.NEW:
        move(case, CaseState.INVESTIGATING)
        case.assigned_to = who.username
    elif state is not CaseState.INVESTIGATING:
        raise WorkflowError(f"an investigation needs the case to be 'New' or 'Investigating'; it is '{case.status}'")
    already = jobs.active_job(s, jobs.dedupe_key(INVESTIGATE_JOB, case.id))
    if already is not None:
        s.commit()
        return already
    job = jobs.enqueue(s, INVESTIGATE_JOB, {"case_id": case.id, "user_id": who.user_id}, case_id=case.id)
    record(s, case, who, "investigation_requested", job=job.id)
    s.commit()
    return job


def _citations(s: Session, case: Case, refs: tuple[PolicyRef, ...]) -> list[dict[str, Any]]:
    """Only sections that exist as stored excerpts: a citation always opens something (spec B.6)."""
    out, seen = [], set()
    for ref in refs:
        if ref.section is None or str(ref) in seen:
            continue
        seen.add(str(ref))
        cited = policies.excerpt(s, case.customer_id, ref.policy_id, ref.version, ref.section)
        if cited is not None:
            out.append(
                {
                    "policy_id": ref.policy_id,
                    "version": ref.version,
                    "section_id": ref.section,
                    "title": cited.title,
                    "heading": cited.heading,
                }
            )
    return out


def _snapshot(found: Investigation) -> dict[str, Any]:
    ev: Evidence = found.evidence

    def candidate(c: Candidate) -> dict[str, Any]:
        return {
            "member_number": c.member.member_number,
            "name": f"{c.member.first_name} {c.member.last_name}",
            "matched": list(c.matched),
        }

    records: tuple[StayRecord, ...] = ev.stay.records if ev.stay else ()
    return {
        "member": asdict(ev.member) if ev.member else None,
        "candidates": [candidate(c) for c in ev.candidates],
        "profiles": list(ev.profiles),
        "duplicate_profiles": list(ev.duplicate_profiles),
        "merged_profiles": list(ev.merged_profiles),
        "stay_id": ev.stay.stay_id if ev.stay else None,
        "stay_found_by": ev.stay.how if ev.stay else None,
        "records": [asdict(r) for r in records],
        "ledger": [asdict(e) for e in ev.ledger],
        "postings": [asdict(p) for p in ev.postings],
        "member_stays": list(ev.member_stays),
        "checkout_day": found.checkout_day.isoformat() if found.checkout_day else None,
        "documents": list(found.documents),
    }


def split_group(s: Session, who: Identity, case: Case, first_stay: str, others: tuple[str, ...]) -> list[Case]:
    """One case per stay, linked (ADR-0062). The new cases are investigated the same way, by the worker."""
    case.group_ref = case.group_ref or case.reference
    claim_stay(s, who, case, first_stay)
    created = []
    original = requests_of(s, case)[0]
    for stay in others:
        request = IntakeRequest(
            received_at_utc=original.received_at_utc,
            contact_channel=original.contact_channel,
            text=original.text,
            sender_email=original.sender_email,
            form_member_number=original.form_member_number,
            form_confirmation=stay,
            form_name=original.form_name,
            form_property=original.form_property,
        )
        sibling = create_case(
            s,
            who,
            request,
            customer_id=case.customer_id,
            source_ref=case.source_ref,
            arm=case.arm,
            group_ref=case.group_ref,
            commit=False,
        )
        sibling.sim_now_utc = case.sim_now_utc
        claim_stay(s, who, sibling, stay)
        move(sibling, CaseState.INVESTIGATING)
        sibling.assigned_to = case.assigned_to
        jobs.enqueue(s, INVESTIGATE_JOB, {"case_id": sibling.id, "user_id": who.user_id}, case_id=sibling.id)
        created.append(sibling)
    record(s, case, who, "case_split_by_stay", stays=1 + len(others))
    return created


def claim_stay(s: Session, who: Identity, case: Case, stay_id: str) -> None:
    s.add(
        CaseEvidence(
            case_id=case.id,
            kind=CLAIMED_STAY_EVIDENCE,
            source_ref=stay_id,
            snapshot={"stay_id": stay_id},
            attached_by=who.username,
            attached_at_utc=utc_now(),
            sim_time_utc=case.received_at_utc,
        )
    )


def investigate_case(s: Session, who: Identity, case: Case, systems: CustomerSystems) -> Recommendation:
    """Read everything, ask the engine, store the evidence and the recommendation. Safe to repeat: each run adds a row
    and the latest one counts. Reads happen before any write, so no lock is held across a customer call."""
    _require_arm_b(case)
    if CaseState(case.status) is not CaseState.INVESTIGATING:
        raise WorkflowError(f"an investigation needs the case to be 'Investigating'; it is '{case.status}'")
    found = investigate(
        systems,
        claim_text_for(s, case),
        policies=policies.published_versions(s, case.customer_id),
        customer=customer_config(case.customer_id).rules,
        config=conventional_config(case.customer_id),
        as_of_utc=read_time(case),
    )
    result = found.result
    stay_id = found.evidence.stay.stay_id if found.evidence.stay else None
    now = utc_now()
    s.add(
        CaseEvidence(
            case_id=case.id,
            kind=INVESTIGATION_EVIDENCE,
            source_ref=stay_id or "-",
            snapshot=_snapshot(found),
            attached_by=who.username,
            attached_at_utc=now,
            sim_time_utc=read_time(case),
        )
    )
    reason_refs = tuple(r.policy_ref for r in result.reasons if r.policy_ref is not None)
    rec = Recommendation(
        case_id=case.id,
        author="engine",
        member_number=found.evidence.member.member_number if found.evidence.member else None,
        stay_id=stay_id,
        status=result.status.value,
        action=result.action.value,
        detail=result.detail,
        points_owed=result.points_owed,
        earned_points=result.earned_points,
        credited_points=result.credited_points,
        reasons=[
            {"code": r.code, "text": r.text, "ref": str(r.policy_ref) if r.policy_ref else None} for r in result.reasons
        ],
        citations=_citations(s, case, (*reason_refs, *result.policy_refs)),
        flags=list(found.flags),
        evidence_hash=evidence_hash(found.facts) if found.facts else None,
        checkout_day=found.checkout_day.isoformat() if found.checkout_day else None,
        created_at_utc=now,
    )
    s.add(rec)
    if found.other_confirmations and stay_id:
        split_group(s, who, case, stay_id, found.other_confirmations)
    s.flush()
    record(
        s,
        case,
        who,
        "investigation_completed",
        result=result.action.value,
        detail=result.detail,
        flags=list(found.flags),
        points=result.points_owed,
        candidates=len(found.evidence.candidates),
    )
    s.commit()
    return rec


def run_investigation_job(s: Session, case_id: int, systems: CustomerSystems) -> None:
    case = s.get(Case, case_id)
    if case is None:
        raise CaseNotFound(case_id)
    if CaseState(case.status) is not CaseState.INVESTIGATING:
        return  # the case moved on while this waited
    investigate_case(s, jobs.SYSTEM, case, systems)


# ---------- the agent's decisions ----------


def _limit_points(s: Session, case: Case, checkout_day: str) -> int:
    rows = policies.in_force_rows(s, case.customer_id, date.fromisoformat(checkout_day))
    for row in rows:
        if row.policy_id == MISSING_POINTS:
            return int(row.rules["supervisor_limit_points"])
    raise WorkflowError(f"no claim policy covers a checkout on {checkout_day}: escalate this case")


def _lock_group(s: Session, case: Case) -> list[Case]:
    """Row locks in ID order, so two agents in one group go one at a time and can't deadlock. A case with no group locks
    only itself, so a double click can't make two requests."""
    where = Case.group_ref == case.group_ref if case.group_ref else Case.id == case.id
    query = select(Case).where(where).order_by(Case.id).with_for_update(key_share=True)
    return list(s.scalars(query.execution_options(populate_existing=True)))


def _group_points(s: Session, cases: list[Case]) -> int:
    query = select(AdjustmentRequestRow).where(
        AdjustmentRequestRow.case_id.in_([c.id for c in cases]),
        AdjustmentRequestRow.status.in_(OPEN_REQUEST_STATUSES),
    )
    return sum(row.points for row in s.scalars(query))


def _escalate_group(s: Session, who: Identity, cases: list[Case], total: int, limit: int) -> None:
    """Policy section 6: over the limit goes to the loyalty manager, as a whole."""
    note = f"The group's total of {total} points is over the supervisor limit of {limit}."
    for case in cases:
        state = CaseState(case.status)
        if state in (CaseState.PENDING_APPROVAL, CaseState.APPROVED):
            query = select(AdjustmentRequestRow).where(
                AdjustmentRequestRow.case_id == case.id, AdjustmentRequestRow.status.in_(("pending", "approved"))
            )
            for row in s.scalars(query):
                approvals.invalidate(s, who, row, case, "over_supervisor_limit")
            state = CaseState(case.status)
        if state in (CaseState.NEW, CaseState.AWAITING_INFORMATION):
            move(case, CaseState.INVESTIGATING)
            state = CaseState.INVESTIGATING
        if state is CaseState.INVESTIGATING:
            s.add(CaseNote(case_id=case.id, author=who.username, body=f"Escalated: {note}", created_at_utc=utc_now()))
            move(case, CaseState.ESCALATED)
            case.resolution_code, case.resolution_note = "over_supervisor_limit", note
            record(s, case, who, "case_escalated", reason="over_supervisor_limit", group_total=total)


@dataclass(frozen=True)
class RequestOutcome:
    status: str  # requested | escalated
    row: AdjustmentRequestRow | None = None


def request_adjustment(s: Session, who: Identity, case: Case) -> RequestOutcome:
    """Ask a supervisor to approve exactly what the engine computed. Over the supervisor limit, across every case in the
    group, the whole group escalates instead (ADR-0062)."""
    require_case_worker(who)
    _require_arm_b(case)
    group = _lock_group(s, case)
    if CaseState(case.status) is not CaseState.INVESTIGATING:
        raise WorkflowError(f"this needs the case to be 'Investigating'; it is '{case.status}'")
    rec = latest_recommendation(s, case)
    if rec is None or NextAction(rec.action) is not NextAction.ADJUST or rec.points_owed <= 0:
        raise WorkflowError("the engine's result doesn't allow an adjustment")
    assert rec.member_number is not None and rec.stay_id is not None and rec.checkout_day is not None
    if not policies.has_single_claim_policy(s, case.customer_id, date.fromisoformat(rec.checkout_day)):
        raise WorkflowError(f"no single published policy covers a checkout on {rec.checkout_day}: escalate this case")
    limit = _limit_points(s, case, rec.checkout_day)
    total = _group_points(s, group) + rec.points_owed
    if total > limit:
        _escalate_group(s, who, group, total, limit)
        s.commit()
        return RequestOutcome("escalated")
    row = AdjustmentRequestRow(
        case_id=case.id,
        member_number=rec.member_number,
        stay_id=rec.stay_id,
        points=rec.points_owed,
        reason_code="missing_points",
        checklist={
            "source": "engine",
            "recommendation_id": rec.id,
            "outcome": rec.action,
            "status": rec.status,
            "reasons": rec.reasons,
            "flags": rec.flags,
        },
        requested_by=who.username,
        requested_at_utc=utc_now(),
        status="pending",
        evidence_hash=rec.evidence_hash,
        policy_refs=policies.claim_policy_refs(s, case.customer_id, date.fromisoformat(rec.checkout_day)),
        checkout_day=rec.checkout_day,
    )
    s.add(row)
    move(case, CaseState.PENDING_APPROVAL)
    s.flush()
    record(s, case, who, "adjustment_requested", points=row.points, checklist_outcome=rec.action)
    s.commit()
    return RequestOutcome("requested", row)


def close_case(s: Session, who: Identity, case: Case, code: str, reason: str = "") -> bool:
    """Close as the engine says, or against it with a reason, which is logged as an override. Returns whether it was an
    override. Nothing here can credit points."""
    require_case_worker(who)
    _require_arm_b(case)
    if CaseState(case.status) is not CaseState.INVESTIGATING:
        raise WorkflowError(f"this needs the case to be 'Investigating'; it is '{case.status}'")
    if code not in CLOSE_CODES:
        raise WorkflowError(f"unknown resolution '{code}'")
    rec = latest_recommendation(s, case)
    if rec is None:
        raise WorkflowError("investigate first: there's no result to close against")
    override = code != recommended_close_code(rec)
    if override and len(reason.strip()) < MIN_OVERRIDE_REASON:
        raise WorkflowError(
            f"the engine's result doesn't support '{code}': give the reason, at least {MIN_OVERRIDE_REASON} characters"
        )
    if reason.strip():
        s.add(CaseNote(case_id=case.id, author=who.username, body=reason.strip(), created_at_utc=utc_now()))
    if override:
        s.add(
            Feedback(
                case_id=case.id,
                recommendation_id=rec.id,
                kind="override",
                reason_code=code,
                comment=reason.strip(),
                author=who.username,
                created_at_utc=utc_now(),
            )
        )
    move(case, CaseState.RESOLVED)
    case.resolution_code, case.resolution_note = code, reason.strip() or None
    record(s, case, who, "case_closed", resolution=code, checklist_outcome=rec.action, override=override)
    s.commit()
    return override


def prompt_for(rec: Recommendation | None) -> str | None:
    """The question to send, when the result is one the member can settle."""
    if rec is None or NextAction(rec.action) is not NextAction.REQUEST_INFO:
        return None
    return PROMPTS.get(rec.detail or "")


def ask_member(s: Session, who: Identity, case: Case, systems: CustomerSystems, message: str = "") -> str:
    """Send the structured question (or the agent's wording), and wait for the reply."""
    _require_arm_b(case)
    rec = latest_recommendation(s, case)
    text = message.strip() or (prompt_for(rec) or "")
    if not text:
        raise WorkflowError("write the message to the member")
    number = rec.member_number if rec else None
    return request_information(s, who, case, systems, text, member_number=number)


def mention_more_stays(s: Session, who: Identity, case: Case, systems: CustomerSystems) -> str:
    """D16: ask about the stays the rules can't identify, without holding up the one they can. The case keeps moving."""
    require_case_worker(who)
    _require_arm_b(case)
    rec = latest_recommendation(s, case)
    ticket = systems.create_ticket(
        subject=f"Your missing points request {case.reference}",
        body=PROMPTS["more_stays"],
        member_number=rec.member_number if rec else None,
    )
    record(s, case, who, "information_requested", ticket=ticket.ticket_id, waiting=False)
    s.commit()
    return ticket.ticket_id


def supply_information(
    s: Session,
    who: Identity,
    case: Case,
    *,
    reply_text: str = "",
    booking_channel: str = "",
    member_number: str = "",
    confirmation: str = "",
    scope_cleared: bool = False,
) -> Job:
    """Store what came back and investigate again. The reply is evidence: it selects records, and a stated channel only
    fills a blank the records can't. It can't set an amount, a permission or a decision."""
    require_case_worker(who)
    _require_arm_b(case)
    state = CaseState(case.status)
    if state not in (CaseState.AWAITING_INFORMATION, CaseState.INVESTIGATING):
        raise WorkflowError(f"this needs the case to be waiting or under investigation; it is '{case.status}'")
    channel = booking_channel.strip()
    if channel and channel not in CHANNELS:
        raise WorkflowError(f"unknown booking channel '{channel}'")
    if not (reply_text.strip() or channel or member_number.strip() or confirmation.strip() or scope_cleared):
        raise WorkflowError("enter what the member sent")
    if reply_text.strip() or member_number.strip() or confirmation.strip():
        s.add(
            CaseRequest(
                case_id=case.id,
                received_at_utc=case.received_at_utc,
                contact_channel=MEMBER_REPLY,
                text=reply_text.strip() or "(answer entered by staff)",
                form_member_number=member_number.strip() or None,
                form_confirmation=confirmation.strip() or None,
                attachment_names=[],
            )
        )
    answers: dict[str, Any] = {}
    if channel:
        answers["booking_channel"] = channel
    if scope_cleared:
        answers["scope_cleared"] = True
    if answers:
        s.add(
            CaseEvidence(
                case_id=case.id,
                kind=ANSWER_EVIDENCE,
                source_ref=who.username,
                snapshot=answers,
                attached_by=who.username,
                attached_at_utc=utc_now(),
                sim_time_utc=case.received_at_utc,
            )
        )
    if state is CaseState.AWAITING_INFORMATION:
        move(case, CaseState.INVESTIGATING)
    record(s, case, who, "information_supplied", kinds=sorted(answers), reply=bool(reply_text.strip()))
    job = jobs.enqueue(s, INVESTIGATE_JOB, {"case_id": case.id, "user_id": who.user_id}, case_id=case.id)
    s.commit()
    return job


def give_feedback(s: Session, who: Identity, case: Case, rating: str, comment: str = "") -> Feedback:
    require_case_worker(who)
    if rating not in RATINGS:
        raise WorkflowError("choose helpful or not helpful")
    rec = latest_recommendation(s, case)
    row = Feedback(
        case_id=case.id,
        recommendation_id=rec.id if rec else None,
        kind="feedback",
        rating=rating,
        comment=comment.strip() or None,
        author=who.username,
        created_at_utc=utc_now(),
    )
    s.add(row)
    record(s, case, who, "feedback_given", rating=rating)
    s.commit()
    return row


def feedback_of(s: Session, case: Case) -> list[Feedback]:
    return list(s.scalars(select(Feedback).where(Feedback.case_id == case.id).order_by(Feedback.id)))


def expand_query(query: str, customer_id: str) -> list[str]:
    """D12: the member's words, then the policy's words for them."""
    lowered = query.lower()
    synonyms = conventional_config(customer_id).synonyms
    extra = [policy for phrase, policy in synonyms.items() if phrase in lowered]
    return list(dict.fromkeys([query, *extra]))


def search_policy(
    s: Session, customer_id: str, query: str, checkout_day: date, limit: int = 5
) -> list[policies.Citation]:
    """D15: only the versions in force on the stay's checkout date. D12: synonyms and full-text search."""
    hits: dict[str, policies.Citation] = {}
    for term in expand_query(query, customer_id):
        for hit in policies.search(s, customer_id, term, checkout_day, limit):
            hits.setdefault(str(hit.ref), hit)
    return list(hits.values())[:limit]


# ---------- the re-check before approval and before execution ----------


def fresh_review_facts(
    s: Session, case: Case, stay_id: str, systems: CustomerSystems, as_of_utc: str
) -> tuple[str, int, str]:
    """(action, points, evidence hash) from fresh reads, by the same code as the investigation."""
    rec = latest_recommendation(s, case)
    if rec is None or rec.member_number is None:
        raise WorkflowError("this case has no recommendation to re-check")
    member: Member = systems.get_member(rec.member_number)
    records = tuple(systems.get_stay_records(stay_id))
    claim, _evidence, facts = read_claim(
        systems,
        member,
        records,
        stay_id,
        received_at_utc=case.received_at_utc,
        as_of_utc=as_of_utc,
        stated_channel=member_answers(s, case).get("booking_channel"),
    )
    result = evaluate_stay(
        claim, policies.published_versions(s, case.customer_id), customer_config(case.customer_id).rules
    )
    return result.action.value, result.points_owed, evidence_hash(facts)
