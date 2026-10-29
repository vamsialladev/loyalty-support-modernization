"""Synthetic 12-month legacy operating history (spec F2). SYNTHETIC: a documented model, not real operations.

Volumes, driver frequencies, outcome probabilities, handling times and member behaviour all come from
`config/scenario_mix.yaml` (assumptions). The analysis built on it (`evaluations/discovery_analysis.py`) therefore
demonstrates the method; its numbers restate those assumptions.
"""

import math
import random
from datetime import date, datetime, timedelta
from typing import Any

from seed_data.generator.models import HistoryAdjustment, HistoryCase, HistoryEvent
from seed_data.generator.rng import rng
from seed_data.generator.timeutil import iso, to_utc
from seed_data.generator.world import PROPERTIES, TIERS, weighted

NOTES = {
    "correct": ["credited", "stay found, points added", "done", "checked ledger and policy, credited", ""],
    "false_denial": ["stay not found", "not eligible per rules", "asked member for hotel conf #, no reply", "denied"],
    "false_approval": ["credited", "credited per member request", "approved", "done"],
    "duplicate_credit": ["credited", "points added"],
    "escalated_correctly": ["escalated to property", "sent to property for confirmation"],
}
MESSAGES = [
    "My points from my stay are missing.",
    "I stayed with you last month and didn't get my points.",
    "Points not posted for my stay, please check.",
    "Hi, my account doesn't show my recent stay.",
    "Where are my points?",
]
COMMENTS = {
    5: "Quick and easy.",
    4: "Fine, took a little while.",
    3: "Had to write twice.",
    2: "Took too long and I had to chase it.",
    1: "Still not sorted. Very frustrating.",
}


def poisson(r: random.Random, lam: float) -> int:
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= r.random()
        if p <= threshold:
            return k
        k += 1


def business_days(start: date, end: date) -> int:
    days, current = 0, start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def build_history(
    seed: int, cfg: dict[str, Any], scale: float
) -> tuple[list[HistoryCase], list[HistoryEvent], list[HistoryAdjustment]]:
    h = cfg["history"]
    start, end = date.fromisoformat(str(h["start"])), date.fromisoformat(str(h["end"]))
    r = rng(seed, "history")
    drivers = list(cfg["driver_frequency"].items())
    k_share = 1 - sum(f for _, f in drivers)
    controls = [(k, v["share"]) for k, v in cfg["control_share"].items()]
    beh = cfg["member_behaviour"]
    # Seasonality is normalised to average 1, so the yearly volume matches assumption A1 (monthly_volume x 12).
    season = {int(m): float(v) for m, v in h["seasonality"].items()}
    mean_season = sum(season.values()) / len(season)
    daily_base = h["monthly_volume"] * 12 / 365 * scale

    # Daily volumes first, so weekly peaks can lengthen resolution (backlog pressure).
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    volumes = {d: poisson(r, daily_base * season[d.month] / mean_season) for d in days}
    weekly: dict[str, int] = {}
    for d, v in volumes.items():
        weekly[_week(d)] = weekly.get(_week(d), 0) + v
    capacity = h["monthly_volume"] * 12 / 52 * scale

    cases: list[HistoryCase] = []
    events: list[HistoryEvent] = []
    adjustments: list[HistoryAdjustment] = []
    n = 0
    for d in days:
        for _ in range(volumes[d]):
            n += 1
            case_id = f"H-{n:06d}"
            driver = r.choices([k for k, _ in drivers] + ["K"], weights=[f for _, f in drivers] + [k_share])[0]
            if driver == "K":
                sub = r.choices([k for k, _ in controls], weights=[s for _, s in controls])[0]
                correct = cfg["control_share"][sub]["correct_action"]
            else:
                correct = cfg["correct_action"][driver]
            probs = cfg["legacy_outcomes"]["K" if driver == "K" else driver]
            outcome = r.choices(list(probs), weights=list(probs.values()))[0]
            points = (r.randrange(129, 390) * r.randrange(1, 6)) * 10
            due = points if correct in ("adjust", "wait") else 0
            if outcome == "false_denial" and due == 0:
                outcome = "correct"
            if outcome == "escalated_correctly" and correct != "escalate":
                outcome = "correct"
            credited = {
                "correct": due,
                "false_denial": 0,
                "false_approval": due + (points if due == 0 else points * 15 // 100),
                "duplicate_credit": 2 * due,
                "escalated_correctly": 0,
            }[outcome]

            info_rate = beh["info_request_rate_control"] if driver == "K" else beh["info_request_rate_defect"]
            info_requests = 1 if r.random() < info_rate else 0
            disputes = outcome == "false_denial" and r.random() < beh["false_denial_recontact"]
            recontacts = r.choice([1, 2]) if disputes else 0
            reopened = outcome == "false_denial" and r.random() < beh["false_denial_reopen"]
            contacts = 1 + info_requests + recontacts
            median = cfg["handling_minutes_median"].get(
                driver, cfg["handling_minutes_median"]["K" if driver == "K" else "default_defect"]
            )
            minutes = round(
                median * math.exp(r.gauss(0, cfg["handling_sigma"]))
                + cfg["minutes_per_repeat_contact"] * (contacts - 1),
                1,
            )

            pressure = max(0.0, (weekly[_week(d)] - capacity) / max(capacity, 1) * 6)
            delay = 1 + 3 * info_requests + (4 if driver == "D20" else 0) + round(pressure) + r.choice([0, 0, 1, 2])
            created = to_utc(d, r.randrange(7, 22), r.randrange(0, 60))
            resolved = created + timedelta(days=delay, hours=r.randrange(1, 6))
            bdays = business_days(d, resolved.date())
            sla = bdays <= int(h["sla_business_days"])

            score: float | None = None
            comment = None
            if r.random() < float(h["survey_response_rate"]):
                raw = (
                    5
                    - 1.5 * (outcome == "false_denial")
                    - 0.7 * (contacts - 1)
                    - 1.0 * reopened
                    - 0.15 * max(0, bdays - 5)
                )
                score = round(min(5.0, max(1.0, raw)), 1)
                comment = COMMENTS[max(1, min(5, round(score)))]

            cases.append(
                HistoryCase(
                    case_id=case_id,
                    created_at_utc=iso(created),
                    resolved_at_utc=iso(resolved),
                    week=_week(d),
                    property=r.choice(list(PROPERTIES)),
                    tier=weighted(r, TIERS),
                    channel=r.choice(["direct", "direct", "phone", "ota", "travel_agent"]),
                    language=r.choice(["es", "fr", "pt", "de"]) if driver == "D23" else "en",
                    driver=driver,
                    correct_action=correct,
                    outcome=outcome,
                    points_due=due,
                    points_credited=credited,
                    handling_minutes=minutes,
                    contacts=contacts,
                    reopened=reopened,
                    business_days_to_resolve=bdays,
                    sla_met=sla,
                    satisfaction_proxy=score,
                    survey_comment=comment,
                    member_message=r.choice(MESSAGES),
                    agent_note=r.choice(NOTES[outcome]),
                )
            )
            events.extend(
                _events(
                    r, case_id, created, resolved, driver, outcome, info_requests, recontacts, reopened, credited > 0
                )
            )
            if credited > 0:
                adjustments.extend(
                    _adjustments(r, case_id, created, resolved, driver, outcome, credited, len(adjustments))
                )
    return cases, events, adjustments


def _week(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _events(
    r: random.Random,
    case_id: str,
    created: datetime,
    resolved: datetime,
    driver: str,
    outcome: str,
    info: int,
    recontacts: int,
    reopened: bool,
    adjusted: bool,
) -> list[HistoryEvent]:
    kinds: list[tuple[str, str]] = [("created", "member")]
    kinds += [("searched", "agent")] * (4 + (0 if driver == "K" else r.randrange(1, 4)))
    kinds += [("info_requested", "agent"), ("member_replied", "member")] * info
    kinds += [("member_replied", "member")] * recontacts
    if outcome == "escalated_correctly":
        kinds.append(("escalated", "agent"))
    if adjusted:
        kinds += [("proposed", "agent"), ("approved", "supervisor"), ("adjusted", "system")]
        if outcome == "duplicate_credit":
            kinds += [("proposed", "agent"), ("approved", "supervisor"), ("adjusted", "system")]
    if reopened:
        kinds.append(("reopened", "member"))
    kinds.append(("resolved", "agent"))
    span = (resolved - created).total_seconds()
    return [
        HistoryEvent(
            case_id=case_id,
            seq=i + 1,
            at_utc=iso(created + timedelta(seconds=span * i / len(kinds))),
            kind=k,
            actor=a,  # type: ignore[arg-type]
        )
        for i, (k, a) in enumerate(kinds)
    ]


def _adjustments(
    r: random.Random,
    case_id: str,
    created: datetime,
    resolved: datetime,
    driver: str,
    outcome: str,
    credited: int,
    offset: int,
) -> list[HistoryAdjustment]:
    approved = created + (resolved - created) * 0.7
    first = HistoryAdjustment(
        adjustment_id=f"HA-{offset + 1:06d}",
        case_id=case_id,
        stay_ref=f"stay-{case_id}",
        points=credited // 2 if outcome == "duplicate_credit" else credited,
        approved_at_utc=iso(approved),
        executed_at_utc=iso(approved + timedelta(hours=r.randrange(1, 30))),
        duplicate_of=None,
        approved_on_stale_evidence=driver == "D11" and outcome == "false_approval",
    )
    if outcome != "duplicate_credit":
        return [first]
    second = first.model_copy(
        update={
            "adjustment_id": f"HA-{offset + 2:06d}",
            "duplicate_of": first.adjustment_id,
            "executed_at_utc": iso(approved + timedelta(hours=r.randrange(31, 60))),
        }
    )
    return [first, second]
