"""Arm B's investigation: read everything once, flag what doesn't add up, and let the engine decide (spec B.7, B.8).

Pure apart from the customer-systems port. Every decision about points comes from `app.domain.eligibility`, never from
here, and never from what a member wrote. Each step names the pre-registered defect it answers:
D01 duplicates, D02 merged numbers, D03 stated channel, D05 partner numbers, D06 posting queue, D07 net by stay,
D13 and D18 lookup, D14 one view, D16 explicit stays, D17 near numbers, D20 multi-issue, D23 language, D24 and D25
escalate.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import Any

from app.arms.conventional import identity as ident
from app.arms.conventional import signals
from app.arms.conventional.config import ConventionalConfig
from app.domain.business_time import business_date
from app.domain.customer_records import LedgerEntry, Member, PendingPosting, StayRecord
from app.domain.eligibility import (
    CustomerRules,
    Eligibility,
    EligibilityResult,
    ExistingCredit,
    NextAction,
    Reason,
    StayClaim,
    combine,
    evaluate_stay,
)
from app.domain.policy import PolicyVersion
from app.ports.customer_systems import CustomerSystems, RecordNotFound

_MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
_MONTH = "|".join(_MONTHS)
_SAME_MONTH = re.compile(rf"\b({_MONTH})\s+(\d{{1,2}})\s*(?:-|to)\s*\d{{1,2}},?\s+(\d{{4}})\b", re.IGNORECASE)
_TWO_MONTHS = re.compile(rf"\b({_MONTH})\s+(\d{{1,2}})\s*(?:-|to)\s*(?:{_MONTH})\s+\d{{1,2}},?\s+(\d{{4}})\b", re.I)
_BARE_DIGITS = re.compile(r"^\d{3,6}$")
_PARTNER_PREFIX = "TRV-"
OTHER_MEMBER_TEXT = "This stay is on another member's profile, so nothing about it can be shown or used."


@dataclass(frozen=True)
class ClaimText:
    """What arrived, from every message on the case, oldest first. All of it is data."""

    text: str
    identity: ident.IdentityClaim
    confirmations: tuple[str, ...]
    received_at_utc: str
    attachments: tuple[str, ...] = ()
    stated_channel: str | None = None
    scope_cleared: bool = False  # a person read the message and dealt with the rest of it


@dataclass(frozen=True)
class StayMatch:
    stay_id: str | None
    how: str  # exact | partner | corrected | by_date | missing | none_given | several_fit | other_member
    records: tuple[StayRecord, ...] = ()


@dataclass(frozen=True)
class Evidence:
    """The one view (D14). JSON-native, so a stored snapshot and a fresh read compare equal."""

    member: Member | None = None
    candidates: tuple[ident.Candidate, ...] = ()
    profiles: tuple[str, ...] = ()
    duplicate_profiles: tuple[str, ...] = ()
    merged_profiles: tuple[str, ...] = ()
    stay: StayMatch | None = None
    ledger: tuple[LedgerEntry, ...] = ()
    postings: tuple[PendingPosting, ...] = ()
    member_stays: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Investigation:
    result: EligibilityResult
    evidence: Evidence
    flags: tuple[str, ...] = ()
    other_confirmations: tuple[str, ...] = ()
    checkout_day: date | None = None
    facts: dict[str, Any] = field(default_factory=dict)


def explicit_arrival_dates(text: str) -> list[date]:
    """Only a date a person can't read two ways: month in words, day and year (D19: anything else is asked about)."""
    out = []
    for pattern in (_SAME_MONTH, _TWO_MONTHS):
        for month, day, year in pattern.findall(text):
            try:
                out.append(date(int(year), _MONTHS.index(month.lower()) + 1, int(day)))
            except ValueError:
                continue
    return out


def _stop(status: Eligibility, action: NextAction, detail: str, text: str, stay_id: str = "") -> EligibilityResult:
    credit = ExistingCredit.UNKNOWN
    return EligibilityResult(stay_id, status, action, detail, credit, 0, 0, 0, (Reason(detail, text),))


def _ask(detail: str, text: str, stay_id: str = "") -> EligibilityResult:
    return _stop(Eligibility.INSUFFICIENT_EVIDENCE, NextAction.REQUEST_INFO, detail, text, stay_id)


def _escalate(detail: str, text: str, stay_id: str = "") -> EligibilityResult:
    return _stop(Eligibility.NEEDS_ESCALATION, NextAction.ESCALATE, detail, text, stay_id)


def _digits_close(given: str, stay_id: str) -> bool:
    """Near in its digits, with the same hotel prefix: `BR-6290` can be `BR-6209`, never `ML-6209`."""
    return given.split("-")[0] == stay_id.split("-")[0] and ident.is_near_number(given, stay_id)


def on_members_profile(systems: CustomerSystems, member: Member, number: str | None) -> bool:
    """No number at all, the member's own, a number merged into it (D02), or the same person's duplicate (D01)."""
    if number is None or number == member.member_number:
        return True
    try:
        other = systems.get_member(number)
    except RecordNotFound:
        return False
    return ident.current_profile(systems, other)[0].member_number == member.member_number or ident.same_person(
        other, member
    )


def resolve_confirmation(
    systems: CustomerSystems, given: str, member_stays: tuple[StayRecord, ...], member: Member, dates: list[date]
) -> StayMatch:
    """D05: partner numbers. D17: a missing prefix, or a near match within this member's own stays. A near match that
    contradicts a date the member wrote isn't a match."""
    records: list[StayRecord] = []
    if given.startswith(_PARTNER_PREFIX):
        found = systems.find_stays(partner_confirmation=given)
        if found:
            return StayMatch(found[0].stay_id, "partner", tuple(systems.get_stay_records(found[0].stay_id)))
    else:
        try:
            records = systems.get_stay_records(given)
        except RecordNotFound:
            records = []
    if records and all(on_members_profile(systems, member, r.member_number) for r in records):
        return StayMatch(given, "exact", tuple(records))
    ids = sorted({r.stay_id for r in member_stays})
    arrivals = {r.stay_id: r.arrival_date for r in member_stays}
    near = [i for i in ids if (i.endswith(given) if _BARE_DIGITS.match(given) else _digits_close(given, i))]
    if dates:
        near = [i for i in near if arrivals[i] in {d.isoformat() for d in dates}]
    if len(near) == 1:
        return StayMatch(near[0], "corrected", tuple(systems.get_stay_records(near[0])))
    if len(near) > 1:
        return StayMatch(None, "several_fit")
    if records:
        return StayMatch(given, "other_member")
    return StayMatch(given, "missing")


def stay_by_date(systems: CustomerSystems, member_stays: tuple[StayRecord, ...], dates: list[date]) -> StayMatch:
    """Reads every record of the stay it finds, not only this member's: a conflicting record must be seen (D25)."""
    wanted = {d.isoformat() for d in dates}
    fits = sorted({r.stay_id for r in member_stays if r.arrival_date in wanted})
    if len(fits) == 1:
        return StayMatch(fits[0], "by_date", tuple(systems.get_stay_records(fits[0])))
    return StayMatch(None, "several_fit" if fits else "none_given")


def _names_agree(record: StayRecord, member: Member) -> bool:
    return not record.guest_name or ident.fold(record.guest_name).endswith(ident.fold(member.last_name))


def read_claim(
    systems: CustomerSystems,
    member: Member,
    records: tuple[StayRecord, ...],
    stay_id: str,
    *,
    received_at_utc: str,
    as_of_utc: str,
    stated_channel: str | None,
) -> tuple[StayClaim, Evidence, dict[str, Any]]:
    """The fresh read behind a recommendation and behind each re-check. The same code both times, so the evidence hash
    means the same thing (ADR-0059)."""
    duplicates, merged = ident.linked_profiles(systems, member)
    on_stay = {r.member_number for r in records if r.member_number and r.member_number != member.member_number}
    for number in sorted(on_stay - set(merged) - set(duplicates)):
        try:
            other = systems.get_member(number)
        except RecordNotFound:
            continue
        if ident.current_profile(systems, other)[0].member_number == member.member_number:
            merged = (*merged, number)
        elif ident.same_person(other, member):
            duplicates = (*duplicates, number)
    profiles = tuple(dict.fromkeys((member.member_number, *duplicates, *merged)))
    ledger = tuple(e for p in profiles for e in systems.get_ledger(p) if e.stay_id == stay_id)
    postings = tuple(systems.get_pending_postings(stay_id))
    claim = StayClaim(
        stay_id=stay_id,
        claimant=member.member_number,
        records=records,
        ledger=ledger,
        postings=postings,
        received_at_utc=received_at_utc,
        as_of_utc=as_of_utc,
        duplicate_profiles=duplicates,
        merged_profiles=merged,
        member_stated_channel=stated_channel,
    )
    evidence = Evidence(
        member=member,
        profiles=profiles,
        duplicate_profiles=duplicates,
        merged_profiles=merged,
        ledger=ledger,
        postings=postings,
    )
    facts = {
        "member": {"member_number": member.member_number, "status": member.status, "merged_into": member.merged_into},
        "records": sorted((asdict(r) for r in records), key=lambda r: r["record_id"]),
        "ledger": sorted([e.entry_id, e.member_number, e.kind, e.points, e.posted_at_utc] for e in ledger),
        "postings": sorted([p.item_id, p.points, p.queued_at_utc, p.expected_post_at_utc] for p in postings),
        "profiles": sorted(profiles),
        "stated_channel": stated_channel,
    }
    return claim, evidence, facts


def member_stays(systems: CustomerSystems, member: Member) -> tuple[StayRecord, ...]:
    duplicates, merged = ident.linked_profiles(systems, member)
    return tuple(r for p in (member.member_number, *duplicates, *merged) for r in systems.find_stays(member_number=p))


def _summaries(stays: tuple[StayRecord, ...]) -> tuple[dict[str, Any], ...]:
    seen: dict[str, dict[str, Any]] = {}
    for r in stays:
        seen.setdefault(
            r.stay_id,
            {"stay_id": r.stay_id, "property": r.property, "arrival_date": r.arrival_date, "nights": r.nights},
        )
    return tuple(sorted(seen.values(), key=lambda row: row["arrival_date"]))


def _data_flags(records: tuple[StayRecord, ...], evidence: Evidence) -> list[str]:
    flags = []
    if len({r.record_id for r in records}) > 1:
        flags.append("several_stay_records")
    if records and any(r.channel is None for r in records):
        flags.append("channel_blank")
    if evidence.duplicate_profiles:
        flags.append("duplicate_profiles")
    if evidence.merged_profiles:
        flags.append("merged_number")
    if evidence.postings:
        flags.append("posting_in_queue")
    if any(e.kind == "reversal" for e in evidence.ledger):
        flags.append("reversal_on_ledger")
    return flags


def _resolve_all(
    systems: CustomerSystems, claim_text: ClaimText, stays: tuple[StayRecord, ...], member: Member, dates: list[date]
) -> tuple[StayMatch, tuple[str, ...]]:
    matches: dict[str, StayMatch] = {}
    first: StayMatch | None = None
    for given in claim_text.confirmations:
        match = resolve_confirmation(systems, given, stays, member, dates)
        first = first or match
        if match.stay_id:
            matches.setdefault(match.stay_id, match)
    if not claim_text.confirmations:
        return stay_by_date(systems, stays, dates), ()
    if not matches:
        return first or StayMatch(None, "none_given"), ()
    ordered = list(matches.values())
    return ordered[0], tuple(m.stay_id for m in ordered[1:] if m.stay_id)


def _gate(result: EligibilityResult, claim_text: ClaimText, flags: list[str]) -> EligibilityResult:
    """D20 and D23: rules can't work these, so the whole message goes to a person. Nothing can be credited from here
    until a person says so."""
    if claim_text.scope_cleared:
        return result
    language = signals.detect_language(claim_text.text)
    topics = signals.out_of_scope_topics(claim_text.text)
    if language is not None:
        flags.append("non_english")
        detail, text = "non_english", f"The message looks like it's written in '{language}': a person needs to read it."
    elif topics:
        flags.append("multi_issue")
        detail, text = "multi_issue", f"The message also raises: {', '.join(topics)}. A person needs to read all of it."
    else:
        return result
    reasons = (Reason(detail, text), *result.reasons)
    return replace(
        result,
        status=Eligibility.NEEDS_ESCALATION,
        action=NextAction.ESCALATE,
        detail=detail,
        points_owed=0,
        reasons=reasons,
    )


def investigate(
    systems: CustomerSystems,
    claim_text: ClaimText,
    *,
    policies: tuple[PolicyVersion, ...],
    customer: CustomerRules,
    config: ConventionalConfig,
    as_of_utc: str,
) -> Investigation:
    flags: list[str] = []
    if claim_text.attachments:
        flags.append("attachment_not_read")
    if signals.mentions_more_stays(claim_text.text):
        flags.append("more_stays_mentioned")
    found = ident.choose(ident.find_candidates(systems, claim_text.identity, config))
    if found.member is None:
        evidence = Evidence(candidates=found.candidates)
        detail = {
            ident.IdentityStatus.NOT_FOUND: "member_not_found",
            ident.IdentityStatus.NEEDS_SECOND_IDENTIFIER: "second_identifier",
            ident.IdentityStatus.AMBIGUOUS: "which_member",
        }[found.status]
        text = "The member isn't confirmed: two identifiers must match (number, email or full name)."
        return Investigation(_gate(_ask(detail, text), claim_text, flags), evidence, tuple(flags))

    member = found.member
    if found.candidates and ident.NEAR_NUMBER in found.candidates[0].matched:
        flags.append("member_number_corrected")
    stays = member_stays(systems, member)
    dates = explicit_arrival_dates(claim_text.text)
    match, others = _resolve_all(systems, claim_text, stays, member, dates)
    base = Evidence(member=member, candidates=found.candidates, stay=match, member_stays=_summaries(stays))

    if match.how == "other_member":
        result = _escalate("stay_on_another_profile", OTHER_MEMBER_TEXT, match.stay_id or "")
        return Investigation(
            _gate(result, claim_text, flags), replace(base, stay=StayMatch(None, match.how)), tuple(flags)
        )
    if match.stay_id is None:
        detail = "which_stay" if match.how == "several_fit" else "confirmation"
        text = (
            "Several stays fit, and nobody may guess." if match.how == "several_fit" else "No stay is identified yet."
        )
        return Investigation(_gate(_ask(detail, text), claim_text, flags), base, tuple(flags))
    if match.how == "corrected":
        flags.append("confirmation_corrected")

    claim, evidence, facts = read_claim(
        systems,
        member,
        match.records,
        match.stay_id,
        received_at_utc=claim_text.received_at_utc,
        as_of_utc=as_of_utc,
        stated_channel=claim_text.stated_channel,
    )
    evidence = replace(evidence, candidates=found.candidates, stay=match, member_stays=base.member_stays)
    flags += _data_flags(match.records, evidence)
    if match.records and not all(_names_agree(r, member) for r in match.records):
        flags.append("guest_name_differs")
        result = _escalate("guest_name_differs", "The name on the stay isn't the member's name.", match.stay_id)
    else:
        result = evaluate_stay(claim, policies, customer)
        verdict = combine([result])  # one stay alone can be over the limit
        if verdict.action is NextAction.ESCALATE and verdict.detail == "over_supervisor_limit":
            reason = Reason("over_supervisor_limit", f"{verdict.points_owed} points is over the supervisor limit.")
            result = replace(
                result, status=verdict.status, action=verdict.action, detail=verdict.detail, reasons=(reason,)
            )
    checkout = None
    if match.records:
        timezone = customer.property_timezones.get(match.records[0].property)
        if timezone:
            checkout = business_date(match.records[0].checkout_at_utc, timezone)
    return Investigation(_gate(result, claim_text, flags), evidence, tuple(flags), others, checkout, facts)
