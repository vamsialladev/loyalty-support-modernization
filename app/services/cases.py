"""The case workflow arm A uses: intake, queue, manual evidence, the rules checklist, notes, information requests,
escalation, closing, and asking for a supervisor's approval (spec B.8, B.10, B.13).

Shared by every arm: arm A plugs in its legacy screens and checklist; arms B and C will plug in theirs. Approval and
execution live in `write_path.py`, the one path every arm uses. All checks run here, on the server: the browser and
the scripted agent call the same functions with the same permissions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arms.conventional import signals
from app.arms.legacy import intake, screens
from app.arms.legacy.checklist import Checklist, Evidence, LedgerView, Outcome, evaluate
from app.arms.legacy.keyword_index import KeywordIndex
from app.arms.legacy.revalidation import evidence_facts
from app.arms.legacy.rules import LegacyRules
from app.clock import utc_now
from app.domain.approval_binding import evidence_hash
from app.domain.business_time import business_date
from app.domain.case_states import TERMINAL, CaseState, check_transition
from app.domain.customer_records import LedgerEntry, Member, StayRecord
from app.domain.roles import Identity, NotPermitted, Role, require_case_reader, require_case_worker
from app.persistence.models import AdjustmentRequestRow, Case, CaseEvidence, CaseNote, CaseRequest
from app.ports.customer_systems import CustomerSystemError, CustomerSystems
from app.services import policies
from app.services.customer_config import customer_config
from app.services.instrumentation import events, record

ARM_A = "A"
ARM_B = "B"
ARMS = (ARM_A, ARM_B)
REASON_MISSING_POINTS = "missing_points"

# What an agent may close a case as, and the checklist outcome each code agrees with. A close that disagrees with
# the checklist is an override: it needs a note and is logged as one (spec E.2 "overrides"). ADR-0054: rule-based
# codes need the evidence their rule reads, and "not found" needs the search that found nothing.
DENY_NOT_FOUND = "deny_not_found"
DENY_OTHER = "deny_other"
MIN_DENY_OTHER_NOTE = 20
MIN_REOPEN_REASON = 20
CREDIT_STATUSES = ("executed", "execution_conflict")  # a credit was applied, or something was under this approval's key
CLOSE_CODES: dict[str, set[Outcome]] = {
    "no_adjustment_credited": {Outcome.ALREADY_CREDITED},
    "wait_until": {Outcome.WAIT},
    "not_checked_out": {Outcome.NOT_CHECKED_OUT},
    "deny_channel_ineligible": {Outcome.DENY_CHANNEL},
    "deny_claim_window": {Outcome.DENY_CLAIM_WINDOW},
    DENY_NOT_FOUND: {Outcome.INCOMPLETE},  # member or stay not found on the legacy screens
    DENY_OTHER: set(),  # always an override
}
EVIDENCE_FREE_CODES = (DENY_NOT_FOUND, DENY_OTHER)  # the only codes open while the evidence is incomplete


class WorkflowError(Exception):
    """The action isn't possible in the case's current state or with its current evidence (shown to the user)."""


class CaseNotFound(Exception):
    pass


@dataclass(frozen=True)
class IntakeRequest:
    received_at_utc: str
    contact_channel: str
    text: str
    sender_email: str | None = None
    form_member_number: str | None = None
    form_confirmation: str | None = None
    form_name: str | None = None
    form_property: str | None = None
    attachment_names: list[str] = field(default_factory=list)
    request_ref: str | None = None


# ---------- intake and queue ----------


def create_case(
    s: Session,
    who: Identity,
    request: IntakeRequest,
    *,
    customer_id: str = "hg-demo",
    source_ref: str | None = None,
    arm: str = ARM_A,
    group_ref: str | None = None,
    commit: bool = True,
) -> Case:
    """The arm is fixed here and never changes: nothing offers a way to move a case between arms."""
    require_case_worker(who)
    if not request.text.strip():
        raise WorkflowError("the request text is empty")
    if arm not in ARMS:
        raise WorkflowError(f"unknown arm '{arm}'")
    now = utc_now()
    case = Case(
        reference="pending",
        arm=arm,
        customer_id=customer_id,
        queue=intake.route(request.text) if arm == ARM_A else signals.route(request.text),
        status=CaseState.NEW.value,
        created_by=who.username,
        received_at_utc=request.received_at_utc,
        source_ref=source_ref,
        group_ref=group_ref,
        created_at_utc=now,
        updated_at_utc=now,
    )
    s.add(case)
    s.flush()
    case.reference = f"{arm}-{case.id:06d}"
    s.add(CaseRequest(case_id=case.id, **asdict(request)))
    record(s, case, who, "case_created", queue=case.queue, channel=request.contact_channel)
    if commit:
        s.commit()
    return case


def list_cases(
    s: Session,
    who: Identity,
    *,
    queue: str = intake.POINTS_QUEUE,
    status: str | None = None,
    mine: bool = False,
    arm: str | None = None,
) -> list[Case]:
    require_case_reader(who)
    query = select(Case).where(Case.queue == queue)
    if arm:
        query = query.where(Case.arm == arm)
    if status:
        query = query.where(Case.status == status)
    if mine:
        query = query.where(Case.assigned_to == who.username)
    return list(s.scalars(query.order_by(Case.received_at_utc, Case.id).limit(200)))


def get_case(s: Session, who: Identity, case_id: int) -> Case:
    require_case_reader(who)  # every action that changes a case checks `require_case_worker` itself
    case = s.get(Case, case_id)
    if case is None:
        raise CaseNotFound(case_id)
    return case


def requests_of(s: Session, case: Case) -> list[CaseRequest]:
    return list(s.scalars(select(CaseRequest).where(CaseRequest.case_id == case.id).order_by(CaseRequest.id)))


def notes_of(s: Session, case: Case) -> list[CaseNote]:
    return list(s.scalars(select(CaseNote).where(CaseNote.case_id == case.id).order_by(CaseNote.id)))


def adjustment_requests_of(s: Session, case: Case) -> list[AdjustmentRequestRow]:
    query = select(AdjustmentRequestRow).where(AdjustmentRequestRow.case_id == case.id)
    return list(s.scalars(query.order_by(AdjustmentRequestRow.id)))


def read_time(case: Case) -> str:
    """The simulated time to read this case's records at. Later than its received time only when a test or the benchmark
    moved it, so a re-check can see what happened after the claim."""
    return case.sim_now_utc or case.received_at_utc


def move(case: Case, target: CaseState) -> None:
    check_transition(CaseState(case.status), target)
    case.status = target.value
    case.version += 1
    case.updated_at_utc = utc_now()


def _require(case: Case, *states: CaseState) -> None:
    if CaseState(case.status) not in states:
        allowed = " or ".join(f"'{st}'" for st in states)
        raise WorkflowError(f"this needs the case to be {allowed}; it is '{case.status}'")


def _require_arm_a(case: Case) -> None:
    """Arm B has its own services (`conventional.py`), so nothing can run arm A's checklist on an arm B case."""
    if case.arm != ARM_A:
        raise WorkflowError(f"this action belongs to arm A; this case is on arm {case.arm}")


def start_work(s: Session, who: Identity, case: Case) -> None:
    require_case_worker(who)
    _require_arm_a(case)
    if case.queue != intake.POINTS_QUEUE:
        raise WorkflowError("this case is in the billing queue, which the billing team works outside this tool")
    _require(case, CaseState.NEW)
    move(case, CaseState.INVESTIGATING)
    case.assigned_to = who.username
    record(s, case, who, "work_started")
    s.commit()


# ---------- the legacy screens, logged as steps ----------


def log_search(s: Session, case: Case, who: Identity, screen: str, by: str, results: int) -> None:
    """A search on one of the four screens (D14 step counts). Inputs are recorded by kind, never by value."""
    record(s, case, who, f"search_{screen}", by=by, results=results)
    s.commit()


def _attach(s: Session, case: Case, who: Identity, kind: str, ref: str, snapshot: dict[str, Any]) -> None:
    _require_arm_a(case)
    _require(case, CaseState.INVESTIGATING)
    s.add(
        CaseEvidence(
            case_id=case.id,
            kind=kind,
            source_ref=ref,
            snapshot=snapshot,
            attached_by=who.username,
            attached_at_utc=utc_now(),
            sim_time_utc=case.received_at_utc,
        )
    )
    record(s, case, who, "evidence_attached", kind=kind)
    s.commit()


def attach_member(s: Session, who: Identity, case: Case, systems: CustomerSystems, member_number: str) -> Member:
    """Re-read on the server: what the browser sends is only the record's number, never its contents."""
    require_case_worker(who)
    found = screens.search_member(systems, member_number=member_number)
    if not found:
        raise WorkflowError("no member with that number")
    _attach(s, case, who, "member", found[0].member_number, asdict(found[0]))
    return found[0]


def attach_stay(
    s: Session, who: Identity, case: Case, systems: CustomerSystems, member_number: str, confirmation: str
) -> StayRecord:
    require_case_worker(who)
    stay = screens.search_stay(systems, member_number=member_number, confirmation=confirmation)
    if stay is None:
        raise WorkflowError("no stay with that confirmation number on this member's profile")
    _attach(s, case, who, "stay", stay.stay_id, asdict(stay))
    return stay


def attach_ledger(
    s: Session, who: Identity, case: Case, systems: CustomerSystems, member_number: str, show_older: bool
) -> LedgerView:
    require_case_worker(who)
    view = screens.ledger_view(
        systems, member_number=member_number, as_of_utc=case.received_at_utc, show_older=show_older
    )
    _attach(s, case, who, "ledger", view.member_number, ledger_snapshot(view))
    return view


def attach_policy(s: Session, who: Identity, case: Case, index: KeywordIndex, ref: str) -> None:
    require_case_worker(who)
    section = index.get(ref)
    if section is None:
        raise WorkflowError("that policy section is not in the index")
    _attach(s, case, who, "policy", section.ref, asdict(section))


def ledger_snapshot(view: LedgerView) -> dict[str, Any]:
    return {
        "member_number": view.member_number,
        "as_of_utc": view.as_of_utc,
        "window_start_utc": view.window_start_utc,
        "entries": [asdict(e) for e in view.entries],
    }


def evidence_rows(s: Session, case: Case) -> list[CaseEvidence]:
    return list(s.scalars(select(CaseEvidence).where(CaseEvidence.case_id == case.id).order_by(CaseEvidence.id)))


def current_evidence(s: Session, case: Case) -> Evidence:
    """The latest member, stay and ledger the agent attached, plus every policy excerpt. Arm A handles one stay per
    case: attaching another stay replaces the first (D16, ADR-0043)."""
    latest: dict[str, CaseEvidence] = {}
    policies: list[str] = []
    for row in evidence_rows(s, case):
        if row.kind == "policy":
            if row.source_ref not in policies:
                policies.append(row.source_ref)
        else:
            latest[row.kind] = row
    ledger = None
    if "ledger" in latest:
        snap = latest["ledger"].snapshot
        entries = tuple(LedgerEntry(**e) for e in snap["entries"])
        ledger = LedgerView(snap["member_number"], snap["as_of_utc"], snap["window_start_utc"], entries)
    return Evidence(
        member=Member(**latest["member"].snapshot) if "member" in latest else None,
        stay=StayRecord(**latest["stay"].snapshot) if "stay" in latest else None,
        ledger=ledger,
        policy_refs=tuple(policies),
    )


def checklist_for(s: Session, case: Case, rules: LegacyRules) -> Checklist:
    return evaluate(current_evidence(s, case), case.received_at_utc, rules)


def checklist_dict(checklist: Checklist) -> dict[str, Any]:
    """JSON-native (lists, plain strings), the same before and after a database round trip."""
    data = asdict(checklist)
    data["outcome"] = checklist.outcome.value
    data["lines"] = [asdict(line) for line in checklist.lines]
    return data


# ---------- the agent's decisions ----------


def add_note(s: Session, who: Identity, case: Case, body: str) -> None:
    require_case_worker(who)
    if not body.strip():
        raise WorkflowError("the note is empty")
    s.add(CaseNote(case_id=case.id, author=who.username, body=body.strip(), created_at_utc=utc_now()))
    record(s, case, who, "note_added")
    s.commit()


def request_adjustment(s: Session, who: Identity, case: Case, rules: LegacyRules) -> AdjustmentRequestRow:
    """Ask a supervisor to approve exactly what the rules checklist computed. The agent never types an amount."""
    require_case_worker(who)
    _require_arm_a(case)
    _require(case, CaseState.INVESTIGATING)
    checklist = checklist_for(s, case, rules)
    if checklist.outcome is not Outcome.ADJUST or checklist.points_owed is None:
        raise WorkflowError(f"the rules checklist does not allow an adjustment ({checklist.outcome.value})")
    evidence = current_evidence(s, case)
    assert evidence.member is not None and evidence.stay is not None  # guaranteed by Outcome.ADJUST
    timezone = customer_config(case.customer_id).rules.property_timezones.get(evidence.stay.property)
    if timezone is None:
        raise WorkflowError(f"no time zone is configured for {evidence.stay.property}: escalate this case")
    checkout_day = business_date(evidence.stay.checkout_at_utc, timezone)
    if not policies.has_single_claim_policy(s, case.customer_id, checkout_day):
        raise WorkflowError(f"no single published policy covers a checkout on {checkout_day}: escalate this case")
    row = AdjustmentRequestRow(
        case_id=case.id,
        member_number=evidence.member.member_number,
        stay_id=evidence.stay.stay_id,
        points=checklist.points_owed,
        reason_code=REASON_MISSING_POINTS,
        checklist=checklist_dict(checklist),
        requested_by=who.username,
        requested_at_utc=utc_now(),
        status="pending",
        evidence_hash=evidence_hash(evidence_facts(evidence, evidence.stay.stay_id)),
        policy_refs=policies.claim_policy_refs(s, case.customer_id, checkout_day),
        checkout_day=checkout_day.isoformat(),
    )
    s.add(row)
    move(case, CaseState.PENDING_APPROVAL)
    s.flush()
    record(s, case, who, "adjustment_requested", points=row.points, checklist_outcome=checklist.outcome.value)
    s.commit()
    return row


def close_codes_for(outcome: Outcome) -> list[str]:
    """The codes the console offers. `close_case` enforces the same rule on the server."""
    return list(EVIDENCE_FREE_CODES) if outcome is Outcome.INCOMPLETE else list(CLOSE_CODES)


def missing_record(evidence: Evidence) -> str | None:
    """Which screen's record is still missing: the member first, because the stay search needs one."""
    if evidence.member is None:
        return "member"
    return "stay" if evidence.stay is None else None


def latest_search_found_nothing(s: Session, case: Case, screen: str) -> bool:
    """True when the most recent logged search on this screen returned no records. An outage or a rejected search
    input logs no search, so neither can stand in for "not found"."""
    action = f"search_{screen}"
    searches = [e for e in events(s, case) if e.action == action]
    return bool(searches) and searches[-1].detail["results"] == 0


def _check_close_allowed(s: Session, case: Case, code: str, note: str, outcome: Outcome) -> None:
    if code == DENY_OTHER:
        if len(note.strip()) < MIN_DENY_OTHER_NOTE:
            raise WorkflowError(
                f"{DENY_OTHER} is a logged override: explain it in a note of at least {MIN_DENY_OTHER_NOTE} characters"
            )
    elif code == DENY_NOT_FOUND:
        missing = missing_record(current_evidence(s, case))
        if missing is None:
            raise WorkflowError("the member and the stay are both attached, so neither was 'not found'")
        if not latest_search_found_nothing(s, case, missing):
            raise WorkflowError(f"search the {missing} screen first: '{code}' needs a search that found nothing")
    elif outcome is Outcome.INCOMPLETE:
        raise WorkflowError(f"the evidence is incomplete: attach what the checklist needs before closing as '{code}'")
    elif outcome not in CLOSE_CODES[code] and not note.strip():
        raise WorkflowError(f"the checklist says '{outcome.value}': explain the override in a note")


def close_case(s: Session, who: Identity, case: Case, code: str, note: str, rules: LegacyRules) -> None:
    """Resolve without an adjustment, under the rules in `_check_close_allowed` (ADR-0054). A code the checklist
    doesn't support is an override and is logged as one."""
    require_case_worker(who)
    _require_arm_a(case)
    _require(case, CaseState.INVESTIGATING)
    if code not in CLOSE_CODES:
        raise WorkflowError(f"unknown resolution '{code}'")
    outcome = checklist_for(s, case, rules).outcome
    _check_close_allowed(s, case, code, note, outcome)
    override = outcome not in CLOSE_CODES[code]
    if note.strip():
        s.add(CaseNote(case_id=case.id, author=who.username, body=note.strip(), created_at_utc=utc_now()))
    move(case, CaseState.RESOLVED)
    case.resolution_code, case.resolution_note = code, note.strip() or None
    record(s, case, who, "case_closed", resolution=code, checklist_outcome=outcome.value, override=override)
    s.commit()


def request_information(
    s: Session, who: Identity, case: Case, systems: CustomerSystems, message: str, member_number: str | None = None
) -> str:
    """Ask the member for something, through the ticketing system (simulated). Returns the ticket ID."""
    require_case_worker(who)
    _require(case, CaseState.INVESTIGATING)
    if not message.strip():
        raise WorkflowError("write the message to the member")
    member = current_evidence(s, case).member
    try:
        ticket = systems.create_ticket(
            subject=f"Your missing points request {case.reference}",
            body=message.strip(),
            member_number=member_number or (member.member_number if member else None),
        )
    except CustomerSystemError as exc:
        record(s, case, who, "system_error", operation="create_ticket", code=exc.code or type(exc).__name__)
        s.commit()
        raise WorkflowError("the ticketing system did not accept the message; try again") from exc
    s.add(
        CaseNote(
            case_id=case.id, author=who.username, body=f"Asked the member: {message.strip()}", created_at_utc=utc_now()
        )
    )
    move(case, CaseState.AWAITING_INFORMATION)
    record(s, case, who, "information_requested", ticket=ticket.ticket_id)
    s.commit()
    return ticket.ticket_id


def resume(s: Session, who: Identity, case: Case) -> None:
    require_case_worker(who)
    _require(case, CaseState.AWAITING_INFORMATION)
    move(case, CaseState.INVESTIGATING)
    record(s, case, who, "work_resumed")
    s.commit()


def escalate(s: Session, who: Identity, case: Case, reason: str) -> None:
    require_case_worker(who)
    _require(case, CaseState.INVESTIGATING)
    if not reason.strip():
        raise WorkflowError("give the reason for escalating")
    s.add(CaseNote(case_id=case.id, author=who.username, body=f"Escalated: {reason.strip()}", created_at_utc=utc_now()))
    move(case, CaseState.ESCALATED)
    case.resolution_code, case.resolution_note = "escalated", reason.strip()
    record(s, case, who, "case_escalated")
    s.commit()


def reopen(s: Session, who: Identity, case: Case, reason: str) -> None:
    """Send a resolved, escalated or rejected case back to `Investigating` (spec B.10; ADR-0055, D6). The earlier events
    stay as they are; the new event keeps what the case said before. Reopening grants nothing: any credit still needs a
    new request, a different supervisor and the duplicate checks."""
    require_case_worker(who)
    current = CaseState(case.status)
    if current not in TERMINAL:
        raise WorkflowError(f"only a resolved, escalated or rejected case can be reopened; this one is '{current}'")
    if len(reason.strip()) < MIN_REOPEN_REASON:
        raise WorkflowError(f"give the reason for reopening, in at least {MIN_REOPEN_REASON} characters")
    credited = any(row.status in CREDIT_STATUSES for row in adjustment_requests_of(s, case))
    if credited and who.role is not Role.SUPERVISOR:
        raise NotPermitted("a credit was applied on this case, so only a supervisor can reopen it")
    previous_resolution, previous_note = case.resolution_code, case.resolution_note
    s.add(CaseNote(case_id=case.id, author=who.username, body=f"Reopened: {reason.strip()}", created_at_utc=utc_now()))
    move(case, CaseState.INVESTIGATING)
    case.assigned_to = who.username
    case.resolution_code, case.resolution_note = None, None
    record(
        s,
        case,
        who,
        "case_reopened",
        previous_status=current.value,
        previous_resolution=previous_resolution,
        previous_note=previous_note,
        reason=reason.strip(),
    )
    s.commit()
