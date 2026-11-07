"""The simulated member (F6; `docs/hypotheses.md` section 1). Labelled simulated. Pure functions over a case's facts.

When an arm asks for information, the member answers if the question asks for something the scenario holds. Otherwise
they repeat their original request. Every reply is a contact. All arms get the same member: what differs is the question
each one asks, and whether it can use the answer. Real satisfaction is only measured with real participants.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluations.scoring import Label

MAX_REPLIES = 3  # then the member gives up, and the case stays unresolved

# What each arm's question asks for. Arm A's come from its scripted path; arms B and C's from the engine's detail.
ASKS_FOR_STAY = frozenset({"confirmation", "which_stay", "asked_for_confirmation"})
ASKS_FOR_IDENTITY = frozenset({"second_identifier", "member_not_found", "which_member", "asked_for_member_number"})
ASKS_FOR_CHANNEL = frozenset({"booking_channel"})


@dataclass(frozen=True)
class Answer:
    """What came back. `repeated` means the question asked for something the member doesn't hold."""

    text: str = ""
    booking_channel: str = ""
    member_number: str = ""
    confirmation: str = ""
    repeated: bool = False


def answer(question: str, label: Label, original_text: str) -> Answer:
    facts = label["facts"]
    if question in ASKS_FOR_CHANNEL and facts.get("reply_channel"):
        return Answer(text=label.get("member_reply") or "", booking_channel=facts["reply_channel"])
    if question in ASKS_FOR_STAY:
        if label.get("member_reply"):  # what the scenario says the member can say, such as the checkout date
            return Answer(text=label["member_reply"])
        claimed = facts.get("claimed_stay_ids") or []
        if claimed:
            return Answer(text=f"The confirmation number is {claimed[0]}.", confirmation=claimed[0])
    if question in ASKS_FOR_IDENTITY and facts.get("claimant"):
        number = facts["claimant"]
        return Answer(text=f"My membership number is {number}.", member_number=number)
    return Answer(text=original_text, repeated=True)


def other_stays(label: Label) -> list[str]:
    """The stays a member mentioned and can name when asked (D16)."""
    return list(label["facts"].get("unclaimed_stay_ids") or [])


def simulated_days(info_requests: int, waited_days: int = 0, sat_in_the_wrong_queue: bool = False) -> int:
    """Simulated days to resolution, with the delays the synthetic history uses (`seed_data/generator/history.py`)."""
    return 1 + 3 * info_requests + (4 if sat_in_the_wrong_queue else 0) + waited_days


def satisfaction_proxy(contacts: int, reopened: bool, was_false_denial: bool, days: int) -> float:
    """F2's formula, the one the synthetic history uses. **A modelled proxy, not real sentiment.**"""
    raw = 5 - 1.5 * was_false_denial - 0.7 * (contacts - 1) - 1.0 * reopened - 0.15 * max(0, days - 5)
    return round(min(5.0, max(1.0, raw)), 1)
