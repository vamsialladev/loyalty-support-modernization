"""Arm A's four evidence screens: member search, stay search, ledger and policy search (spec B.8; defect D14).

The customer systems behind the port are capable (they can follow merges, search partner confirmations, show the
posting queue). These screens use only what the legacy tool offered, so each limit lives here and names its
pre-registered defect (ADR-0043). Nothing here is broken on purpose: what a screen does, it does correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.arms.legacy.checklist import LedgerView
from app.domain.customer_records import LedgerEntry, Member, StayRecord
from app.ports.customer_systems import CustomerSystems, RecordNotFound

LEDGER_DEFAULT_DAYS = 90


class SearchInputError(ValueError):
    """The screen was given an incomplete search (it says which fields it needs)."""


def search_member(
    systems: CustomerSystems,
    *,
    member_number: str = "",
    first_name: str = "",
    last_name: str = "",
    email: str = "",
) -> list[Member]:
    """Exact member number, or exact first name + last name + email (D13). No fuzzy match, no nickname list or accent
    folding (D18), no duplicate-profile candidates (D01). A merged profile is shown as it is; its `merged_into` number
    is not followed (D02)."""
    member_number = member_number.strip()
    if member_number:
        try:
            return [systems.get_member(member_number)]
        except RecordNotFound:
            return []
    first_name, last_name, email = first_name.strip(), last_name.strip(), email.strip()
    if not (first_name and last_name and email):
        raise SearchInputError("enter a member number, or the first name, last name and email together")
    return [m for m in systems.find_members(email=email) if m.first_name == first_name and m.last_name == last_name]


def search_stay(systems: CustomerSystems, *, member_number: str, confirmation: str) -> StayRecord | None:
    """The hotel confirmation number, exactly, within one member's stays (D17). Partner (OTA) confirmations are not
    searchable (D05), and stays on another profile number never appear (D01, D02). When the PMS holds two records for
    one confirmation number, the screen shows the first one returned (D25)."""
    member_number, confirmation = member_number.strip(), confirmation.strip()
    if not member_number or not confirmation:
        raise SearchInputError("find the member first, then enter the hotel confirmation number")
    for record in systems.find_stays(member_number=member_number):
        if record.stay_id == confirmation:
            return record
    return None


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _fmt(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def ledger_view(
    systems: CustomerSystems, *, member_number: str, as_of_utc: str, show_older: bool = False
) -> LedgerView:
    """The member's posted ledger, newest first, 90 days by default; "Show older entries" shows all of it (ADR-0050).

    Re-posts are listed under their own posting date without the stay's confirmation number, which is how the legacy
    screen groups them (D07): the reversal shows against the stay, the re-post does not. The posting queue is not on
    any legacy screen (D06).
    """
    as_of = _ts(as_of_utc)
    start = None if show_older else _fmt(as_of - timedelta(days=LEDGER_DEFAULT_DAYS))
    entries = [
        e
        for e in systems.get_ledger(member_number.strip())
        if _ts(e.posted_at_utc) <= as_of and (start is None or e.posted_at_utc >= start)
    ]
    shown = tuple(
        LedgerEntry(e.entry_id, e.member_number, e.kind, e.points, e.posted_at_utc, None, e.reverses_entry_id)
        if e.kind == "repost"
        else e
        for e in sorted(entries, key=lambda e: (e.posted_at_utc, e.entry_id), reverse=True)
    )
    return LedgerView(member_number.strip(), _fmt(as_of), start, shown)
