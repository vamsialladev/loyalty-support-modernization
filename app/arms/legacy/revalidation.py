"""What arm A's re-check reads: its own screens again, and the facts about this stay it can see (ADR-0044, ADR-0059).

The re-check uses arm A's own evaluator on arm A's own view, so the shared write path adds safeguards without quietly
fixing arm A's pre-registered defects. Re-posts carry no stay number on the legacy ledger view (D07) and the posting
queue isn't on any legacy screen (D06), so neither is a fact here.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from app.arms.legacy import screens
from app.arms.legacy.checklist import Evidence
from app.ports.customer_systems import CustomerSystems


def fresh_evidence(systems: CustomerSystems, attached: Evidence, as_of_utc: str) -> Evidence:
    """The same records read again through the same screens. All ledger entries: the attached view covered checkout,
    so every entry for this stay was in it, and a later as-of time mustn't slide the 90-day window past them."""
    member = attached.member
    stay = attached.stay
    if member is None or stay is None or attached.ledger is None:
        return attached
    found = screens.search_member(systems, member_number=member.member_number)
    record = screens.search_stay(systems, member_number=member.member_number, confirmation=stay.stay_id)
    view = screens.ledger_view(systems, member_number=member.member_number, as_of_utc=as_of_utc, show_older=True)
    return replace(attached, member=found[0] if found else None, stay=record, ledger=view)


def evidence_facts(evidence: Evidence, stay_id: str) -> dict[str, Any]:
    """The facts an approval rests on. An unrelated stay's posting isn't one of them, nor is the time of the read."""
    member = evidence.member
    entries = evidence.ledger.entries if evidence.ledger else ()
    return {
        "member": (
            {"member_number": member.member_number, "status": member.status, "merged_into": member.merged_into}
            if member
            else None
        ),
        "stay": asdict(evidence.stay) if evidence.stay else None,
        "ledger": sorted(
            (e.entry_id, e.kind, e.points, e.posted_at_utc, e.reverses_entry_id)
            for e in entries
            if e.stay_id == stay_id
        ),
    }
