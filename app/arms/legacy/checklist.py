"""Arm A's rules checklist: the legacy engine's deterministic verdict on the evidence the agent attached by hand.

Pure function. It sees only what the agent attached on the legacy screens (member, one stay record, one ledger view,
policy excerpts), never the customer systems directly, so every screen limitation carries through (spec B.8; ADR-0043).
It is correct where the legacy configuration is correct: points are floor(room revenue x 10), the claim window is
12 months, approval limits apply. The agent cannot type an amount; the points come from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.arms.legacy.rules import LegacyRules
from app.domain.customer_records import LedgerEntry, Member, StayRecord


class Outcome(StrEnum):
    INCOMPLETE = "incomplete_evidence"
    NOT_CHECKED_OUT = "not_checked_out"
    DENY_CLAIM_WINDOW = "deny_claim_window"
    DENY_CHANNEL = "deny_channel_ineligible"
    ALREADY_CREDITED = "no_adjustment_credited"
    WAIT = "wait_until"
    ESCALATE_OVER_LIMIT = "escalate_over_limit"
    ADJUST = "adjust"


@dataclass(frozen=True)
class LedgerView:
    """What the legacy ledger screen showed: entries up to `as_of_utc`, from `window_start_utc` (None = all)."""

    member_number: str
    as_of_utc: str
    window_start_utc: str | None
    entries: tuple[LedgerEntry, ...]


@dataclass(frozen=True)
class Evidence:
    member: Member | None = None
    stay: StayRecord | None = None
    ledger: LedgerView | None = None
    policy_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Line:
    code: str
    label: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class Checklist:
    outcome: Outcome
    lines: tuple[Line, ...]
    earned_points: int | None = None
    credited_points: int | None = None
    points_owed: int | None = None
    wait_until: str | None = None
    rules_revision: str | None = None


def utc_day(timestamp: str) -> date:
    """The legacy engine's calendar date: the UTC date, not the property's business date (defect D04)."""
    return date.fromisoformat(timestamp[:10])


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    for last in (day.day, 30, 29, 28):
        try:
            return date(year, month, min(day.day, last))
        except ValueError:
            continue
    raise ValueError(day)


def evaluate(evidence: Evidence, claim_at_utc: str, rules: LegacyRules) -> Checklist:
    lines: list[Line] = []
    member, stay, ledger = evidence.member, evidence.stay, evidence.ledger

    lines.append(Line("member", "Member profile attached", member is not None))
    stay_ok = stay is not None and member is not None and stay.member_number == member.member_number
    lines.append(
        Line(
            "stay",
            "Stay record attached, on this member's profile",
            stay_ok,
            "" if stay is None or stay_ok else "the attached stay is not on this member's profile",
        )
    )
    covers = False
    if ledger is not None and stay is not None and member is not None and ledger.member_number == member.member_number:
        covers = ledger.window_start_utc is None or utc_day(ledger.window_start_utc) <= utc_day(stay.checkout_at_utc)
    lines.append(
        Line(
            "ledger",
            "Ledger view attached, covering the checkout date",
            covers,
            "" if covers or ledger is None else "the attached view starts after checkout: show older entries",
        )
    )
    lines.append(Line("policy", "Policy excerpt attached", bool(evidence.policy_refs)))
    if not all(line.passed for line in lines) or member is None or stay is None or ledger is None:
        return Checklist(Outcome.INCOMPLETE, tuple(lines))

    claim_day = utc_day(claim_at_utc)
    checkout_day = utc_day(stay.checkout_at_utc)
    revision = rules.revision_on(claim_day)
    rev = f"legacy rules from {revision.effective_from.isoformat()}"
    earned = stay.room_revenue_cents * rules.points_per_usd_room_revenue // 100
    credited = sum(e.points for e in ledger.entries if e.stay_id == stay.stay_id)

    def done(outcome: Outcome, owed: int | None = None, wait_until: str | None = None) -> Checklist:
        return Checklist(outcome, tuple(lines), earned, credited, owed, wait_until, rev)

    checked_out = stay.status == "checked_out"
    lines.append(Line("checked_out", "Stay is checked out", checked_out, f"status: {stay.status}"))
    if not checked_out:
        return done(Outcome.NOT_CHECKED_OUT)

    last_day = add_months(checkout_day, rules.claim_window_months)
    in_window = claim_day <= last_day
    lines.append(Line("claim_window", "Claimed within 12 months of checkout", in_window, f"last day {last_day}"))
    if not in_window:
        return done(Outcome.DENY_CLAIM_WINDOW)

    channel_ok = stay.channel in revision.eligible_channels
    channel = stay.channel or "blank"
    lines.append(Line("channel", "Booking channel earns points", channel_ok, f"channel: {channel}"))
    if not channel_ok:
        return done(Outcome.DENY_CHANNEL)

    not_credited = credited < earned
    lines.append(
        Line("not_credited", "Points not already in the ledger", not_credited, f"{credited} of {earned} posted")
    )
    if not not_credited:
        return done(Outcome.ALREADY_CREDITED)

    wait_days = revision.waiting_period_days[stay.property]
    claimable_from = checkout_day + timedelta(days=wait_days)
    waited = claim_day >= claimable_from
    lines.append(Line("waiting", f"Waiting period ({wait_days} days) has passed", waited, f"from {claimable_from}"))
    if not waited:
        return done(Outcome.WAIT, wait_until=claimable_from.isoformat())

    owed = earned - credited
    within = owed <= rules.supervisor_limit_points
    lines.append(
        Line("limit", "Within the supervisor approval limit", within, f"{owed} of {rules.supervisor_limit_points}")
    )
    if not within:
        return done(Outcome.ESCALATE_OVER_LIMIT, owed=owed)
    return done(Outcome.ADJUST, owed=owed)
