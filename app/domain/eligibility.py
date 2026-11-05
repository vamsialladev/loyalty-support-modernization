"""Deterministic eligibility (spec B.7; ELIG-01): pure rules, parameterized by policy and customer configuration.

No model, web, database or HTTP code. Written apart from the reference labeler and imports nothing from it, so one
checks the other (`tests/test_eligibility_differential.py`, dev split only).

Two times, on purpose:
- `received_at_utc`, the claim's time, decides the claim window and the waiting period. A later re-check must not change
  whether the claim was on time.
- `as_of_utc`, the moment of reading, decides which ledger and queue entries count. A re-check before execution uses a
  later as-of time, so a posting that landed after approval stops the adjustment.

Used by arms B and C (Milestones 7 and 8). Arm A keeps its own checklist, so its pre-registered defects stay (ADR-0044).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any

from app.domain.business_time import add_months, business_date, parse_utc
from app.domain.customer_records import LedgerEntry, PendingPosting, StayRecord
from app.domain.policy import EARNING, MISSING_POINTS, PolicyRef, PolicyVersion, versions_in_force

_RECORD_FIELDS_THAT_MUST_AGREE = ("checkout_at_utc", "room_revenue_cents", "arrival_date", "member_number", "channel")


class Eligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEEDS_ESCALATION = "needs_escalation"


class NextAction(StrEnum):
    ADJUST = "adjust"
    NO_ADJUSTMENT_CREDITED = "no_adjustment_credited"
    NO_ADJUSTMENT_PENDING = "no_adjustment_pending"
    WAIT_UNTIL = "wait_until"
    NOT_CHECKED_OUT = "not_checked_out"
    DENY = "deny"
    REQUEST_INFO = "request_info"
    REFRESH_EVIDENCE = "refresh_evidence"
    ESCALATE = "escalate"


class ExistingCredit(StrEnum):
    NONE = "none"
    CREDITED = "credited"
    PENDING_POSTING = "pending_posting"
    CREDITED_OTHER_PROFILE = "credited_other_profile"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CustomerRules:
    """The parts of a customer's configuration that eligibility reads (`config/customers/<id>.yaml`)."""

    property_timezones: dict[str, str]
    source_code_channels: dict[str, str | None]
    max_evidence_age_minutes: int = 60


@dataclass(frozen=True)
class StayClaim:
    """Everything the rules may look at for one claimed stay. Identity is already confirmed by the caller."""

    stay_id: str
    claimant: str | None
    records: tuple[StayRecord, ...]
    ledger: tuple[LedgerEntry, ...]  # every entry for this stay, on any profile
    postings: tuple[PendingPosting, ...]  # the posting queue for this stay
    received_at_utc: str
    as_of_utc: str
    duplicate_profiles: tuple[str, ...] = ()  # the same person's other active profiles (two identifiers confirmed)
    merged_profiles: tuple[str, ...] = ()  # numbers merged into the claimant's profile
    member_stated_channel: str | None = None  # the member's answer when the channel can't be derived
    evidence_read_at_utc: str | None = None  # on the same clock as `as_of_utc`; None skips the freshness check


@dataclass(frozen=True)
class Reason:
    code: str
    text: str
    policy_ref: PolicyRef | None = None


@dataclass(frozen=True)
class EligibilityResult:
    stay_id: str
    status: Eligibility
    action: NextAction
    detail: str | None
    existing_credit: ExistingCredit
    earned_points: int
    credited_points: int
    points_owed: int
    reasons: tuple[Reason, ...]
    policy_refs: tuple[PolicyRef, ...] = ()
    supervisor_limit_points: int | None = None


@dataclass(frozen=True)
class CaseVerdict:
    status: Eligibility
    action: NextAction
    detail: str | None
    points_owed: int
    stays: tuple[EligibilityResult, ...] = field(default=())


def _escalate(stay_id: str, detail: str, text: str, refs: tuple[PolicyRef, ...] = ()) -> EligibilityResult:
    ref = refs[0] if refs else None
    return EligibilityResult(
        stay_id,
        Eligibility.NEEDS_ESCALATION,
        NextAction.ESCALATE,
        detail,
        ExistingCredit.UNKNOWN,
        0,
        0,
        0,
        (Reason(detail, text, ref),),
        refs,
    )


def _records_disagree(records: Sequence[StayRecord]) -> bool:
    return len({tuple(getattr(r, f) for f in _RECORD_FIELDS_THAT_MUST_AGREE) for r in records}) > 1


def _channel_earns(rules: dict[str, Any], channel: str, record: StayRecord) -> bool:
    if channel in rules["eligible_channels"]:
        return True
    if channel == "ota" and rules["ota_eligible_with_member_on_booking"]:
        return record.member_on_booking
    prefix = rules["corporate_rate_prefix"]
    return channel == "travel_agent" and bool(prefix) and record.rate_code.startswith(prefix)


def _channel_section(channel: str, policy: PolicyVersion, record: StayRecord) -> PolicyRef:
    prefix = policy.rules["corporate_rate_prefix"]
    if channel == "ota":
        return policy.ref("4.2", "4.1")
    if channel == "travel_agent" and prefix and record.rate_code.startswith(prefix):
        return policy.ref("7.3", "4.1")
    return policy.ref("4.1")


def evaluate_stay(claim: StayClaim, policies: Sequence[PolicyVersion], customer: CustomerRules) -> EligibilityResult:
    stay_id = claim.stay_id

    if not claim.records:
        return _escalate(stay_id, "missing_stay_record", "No system holds a record of this stay; ask the property.")
    if _records_disagree(claim.records):
        return _escalate(stay_id, "conflicting_records", "Stay records disagree; ask the property to confirm.")

    record = claim.records[0]
    timezone = customer.property_timezones.get(record.property)
    if timezone is None:
        return _escalate(stay_id, "unknown_property", f"No time zone is configured for {record.property}.")
    if claim.evidence_read_at_utc is not None:
        age = parse_utc(claim.as_of_utc) - parse_utc(claim.evidence_read_at_utc)
        if age > timedelta(minutes=customer.max_evidence_age_minutes):
            return EligibilityResult(
                stay_id,
                Eligibility.INSUFFICIENT_EVIDENCE,
                NextAction.REFRESH_EVIDENCE,
                "stale_evidence",
                ExistingCredit.UNKNOWN,
                0,
                0,
                0,
                (Reason("stale_evidence", "The evidence is too old to act on; read it again."),),
            )

    checkout_day = business_date(record.checkout_at_utc, timezone)
    claims = versions_in_force(policies, MISSING_POINTS, checkout_day)
    earnings = versions_in_force(policies, EARNING, checkout_day)
    if not claims or not earnings:
        return _escalate(stay_id, "no_policy", f"No published policy covers a checkout on {checkout_day}.")
    if len(claims) > 1 or len(earnings) > 1:
        refs = tuple(v.ref() for v in (*claims, *earnings))
        return _escalate(stay_id, "conflicting_policies", f"Several policies cover {checkout_day}.", refs)
    policy, earning = claims[0], earnings[0]
    rules = policy.rules
    limit = int(rules["supervisor_limit_points"])
    claim_day = business_date(claim.received_at_utc, timezone)
    earned = record.room_revenue_cents * int(earning.rules["points_per_usd_room_revenue"]) // 100
    entries = [e for e in claim.ledger if parse_utc(e.posted_at_utc) <= parse_utc(claim.as_of_utc)]
    profiles = {p for p in (claim.claimant, *claim.duplicate_profiles, *claim.merged_profiles) if p}
    credited = sum(e.points for e in entries if e.member_number in profiles)
    base_refs = (policy.ref(), earning.ref("2"))

    def result(
        status: Eligibility,
        action: NextAction,
        reason: Reason,
        *,
        detail: str | None = None,
        credit: ExistingCredit = ExistingCredit.NONE,
        owed: int = 0,
    ) -> EligibilityResult:
        return EligibilityResult(
            stay_id,
            status,
            action,
            detail,
            credit,
            earned,
            credited,
            owed,
            (reason,),
            base_refs,
            limit,
        )

    if record.status != "checked_out":
        reason = Reason("not_checked_out", f"The stay's status is {record.status}.", policy.ref("3"))
        return result(Eligibility.INELIGIBLE, NextAction.NOT_CHECKED_OUT, reason)
    if record.member_number is None and not claim.claimant:
        reason = Reason("not_a_member", "The stay has no member number and nobody confirmed as the member.")
        return result(Eligibility.INELIGIBLE, NextAction.DENY, reason, detail="not_a_member")

    last_day = add_months(checkout_day, int(rules["claim_window_months"]))
    if claim_day > last_day:
        reason = Reason("claim_window", f"The last day to claim was {last_day}.", policy.ref("3"))
        return result(Eligibility.INELIGIBLE, NextAction.DENY, reason, detail="claim_window")

    channel = record.channel or customer.source_code_channels.get(record.source_code) or claim.member_stated_channel
    if channel is None:
        reason = Reason("booking_channel", "The booking channel is blank and can't be derived; ask the member.")
        return result(Eligibility.INSUFFICIENT_EVIDENCE, NextAction.REQUEST_INFO, reason, detail="booking_channel")
    if not _channel_earns(rules, channel, record):
        reason = Reason(
            "channel_ineligible",
            f"A {channel} booking earns no points here.",
            _channel_section(channel, policy, record),
        )
        return result(Eligibility.INELIGIBLE, NextAction.DENY, reason, detail="channel_ineligible")

    on_duplicates = sum(e.points for e in entries if e.member_number in claim.duplicate_profiles)
    if claim.duplicate_profiles and on_duplicates >= earned:
        reason = Reason(
            "credited_other_profile", "The points are on the member's other profile.", policy.ref("7.1", "5")
        )
        return result(
            Eligibility.ELIGIBLE,
            NextAction.NO_ADJUSTMENT_CREDITED,
            reason,
            detail="credited_other_profile",
            credit=ExistingCredit.CREDITED_OTHER_PROFILE,
        )
    if credited >= earned:
        reason = Reason("credited", f"The ledger shows {credited} of {earned} points.", policy.ref("5"))
        return result(Eligibility.ELIGIBLE, NextAction.NO_ADJUSTMENT_CREDITED, reason, credit=ExistingCredit.CREDITED)

    claimable_from = checkout_day + timedelta(days=int(rules["waiting_period_days"]))
    if claim_day < claimable_from:
        reason = Reason("waiting_period", f"Claims open on {claimable_from}.", policy.ref("3"))
        return result(Eligibility.INELIGIBLE, NextAction.WAIT_UNTIL, reason, detail=claimable_from.isoformat())

    if rules["pending_posting_blocks_adjustment"]:
        as_of = parse_utc(claim.as_of_utc)
        pending = [p for p in claim.postings if parse_utc(p.queued_at_utc) <= as_of < parse_utc(p.expected_post_at_utc)]
        if pending:
            expected = business_date(pending[0].expected_post_at_utc, timezone).isoformat()
            reason = Reason("pending_posting", f"A posting is expected on {expected}.", policy.ref("5.1"))
            return result(
                Eligibility.ELIGIBLE,
                NextAction.NO_ADJUSTMENT_PENDING,
                reason,
                detail=expected,
                credit=ExistingCredit.PENDING_POSTING,
            )

    owed = earned - credited
    reason = Reason("points_missing", f"{owed} points are missing ({credited} of {earned} posted).", earning.ref("2"))
    return result(Eligibility.ELIGIBLE, NextAction.ADJUST, reason, owed=owed)


_ACTION_ORDER = (
    NextAction.ESCALATE,
    NextAction.REFRESH_EVIDENCE,
    NextAction.REQUEST_INFO,
    NextAction.DENY,
    NextAction.ADJUST,
    NextAction.WAIT_UNTIL,
    NextAction.NO_ADJUSTMENT_PENDING,
    NextAction.NO_ADJUSTMENT_CREDITED,
    NextAction.NOT_CHECKED_OUT,
)


def combine(results: Sequence[EligibilityResult]) -> CaseVerdict:
    """One case's verdict over its claimed stays. The supervisor limit applies per case (policy section 6)."""
    if not results:
        raise ValueError("a case verdict needs at least one stay")
    top = min(results, key=lambda r: _ACTION_ORDER.index(r.action))
    owed = sum(r.points_owed for r in results)
    limits = [r.supervisor_limit_points for r in results if r.supervisor_limit_points is not None]
    if top.action is NextAction.ADJUST and limits and owed > min(limits):
        return CaseVerdict(
            Eligibility.NEEDS_ESCALATION, NextAction.ESCALATE, "over_supervisor_limit", owed, tuple(results)
        )
    return CaseVerdict(top.status, top.action, top.detail, owed, tuple(results))
