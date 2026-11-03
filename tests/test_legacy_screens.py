"""Arm A's four evidence screens on real seeded data: each pre-registered screen limit, and that the screens are
correct everywhere else (spec B.8). Labels are read here only to pick cases and check facts; the screens never see
them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.arms.legacy import screens
from app.domain.customer_records import LedgerEntry, PendingPosting
from app.ports.customer_systems import CustomerSystems
from tests.arm_a import ArmA, make_arm_a


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def label(arm: ArmA, code: str, nth: int = 0) -> dict[str, Any]:
    return arm.labels[arm.scenario(code, nth=nth)]


def request(arm: ArmA, case_id: str) -> dict[str, Any]:
    from benchmarks.intake import read_split

    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == case_id)
    first = item.requests[0]
    return {"form_member": first.form_member_number, "form_stay": first.form_confirmation, "email": first.sender_email}


def at(lab: dict[str, Any], arm: ArmA) -> CustomerSystems:
    return arm.systems(lab["facts"]["received_at_utc"])


def test_exact_lookups_find_a_clean_case(arm: ArmA) -> None:
    lab = label(arm, "K01")
    systems = at(lab, arm)
    member = lab["claimant_member_number"]
    (found,) = screens.search_member(systems, member_number=member)
    by_name = screens.search_member(systems, first_name=found.first_name, last_name=found.last_name, email=found.email)
    assert [m.member_number for m in by_name] == [member]
    stay = screens.search_stay(systems, member_number=member, confirmation=lab["facts"]["claimed_stay_ids"][0])
    assert stay is not None and stay.member_number == member


def test_d13_a_mistyped_member_number_does_not_find_the_member(arm: ArmA) -> None:
    lab = label(arm, "D13")
    typed = request(arm, lab["case_id"])["form_member"]
    assert typed and typed != lab["claimant_member_number"]
    found = screens.search_member(at(lab, arm), member_number=typed)
    assert lab["claimant_member_number"] not in [m.member_number for m in found]
    assert screens.search_member(at(lab, arm), member_number=typed.lower()) == []  # case-sensitive too


def test_name_and_email_must_both_match_exactly_d13_d18(arm: ArmA) -> None:
    lab = label(arm, "K01")
    systems = at(lab, arm)
    (member,) = screens.search_member(systems, member_number=lab["claimant_member_number"])
    first, last, email = member.first_name, member.last_name, member.email
    assert screens.search_member(systems, first_name=first.lower(), last_name=last, email=email) == []
    assert screens.search_member(systems, first_name=first, last_name=last, email=email.upper()) == []
    with pytest.raises(screens.SearchInputError):
        screens.search_member(systems, first_name=first, last_name=last)


@pytest.mark.parametrize("nth", [0, 1, 2])
def test_d18_a_married_name_or_nickname_is_not_found(arm: ArmA, nth: int) -> None:
    from benchmarks.agents.legacy_scripted import signoff_name
    from benchmarks.intake import read_split

    lab = label(arm, "D18", nth)
    first_request = next(c for c in read_split("dev", arm.datasets) if c.case_id == lab["case_id"]).requests[0]
    name = first_request.form_name or signoff_name(first_request.text)
    assert name and first_request.sender_email
    first, last = name.split()[0], " ".join(name.split()[1:])
    systems = at(lab, arm)
    (member,) = screens.search_member(systems, member_number=lab["claimant_member_number"])
    assert (member.first_name, member.last_name) != (first, last)
    found = screens.search_member(systems, first_name=first, last_name=last, email=first_request.sender_email)
    assert lab["claimant_member_number"] not in [m.member_number for m in found]


def test_d17_a_partial_confirmation_number_is_not_found(arm: ArmA) -> None:
    lab = label(arm, "D17")
    typed = request(arm, lab["case_id"])["form_stay"]
    assert typed and typed not in lab["facts"]["claimed_stay_ids"]
    assert screens.search_stay(at(lab, arm), member_number=lab["claimant_member_number"], confirmation=typed) is None


def test_d05_a_partner_confirmation_is_not_searchable_though_the_platform_has_it(arm: ArmA) -> None:
    lab = label(arm, "D05")
    systems = at(lab, arm)
    partner = request(arm, lab["case_id"])["form_stay"]
    assert partner.startswith("TRV-")
    assert screens.search_stay(systems, member_number=lab["claimant_member_number"], confirmation=partner) is None
    assert systems.find_stays(partner_confirmation=partner), (
        "the capability exists upstream; the legacy screen lacks it"
    )


@pytest.mark.parametrize("code", ["D01", "D02"])
def test_d01_d02_a_stay_on_another_profile_number_never_appears(arm: ArmA, code: str) -> None:
    lab = label(arm, code)
    stay_id = lab["facts"]["claimed_stay_ids"][0]
    record_owner = next(r["member_number"] for r in lab["facts"]["records"] if r["stay_id"] == stay_id)
    assert record_owner != lab["claimant_member_number"]
    systems = at(lab, arm)
    assert screens.search_stay(systems, member_number=lab["claimant_member_number"], confirmation=stay_id) is None
    if code == "D02":
        (member,) = screens.search_member(systems, member_number=record_owner)
        assert member.merged_into == lab["claimant_member_number"]  # shown, but the screen never follows it


def test_d25_when_two_records_disagree_the_screen_shows_the_first(arm: ArmA) -> None:
    lab = label(arm, "D25")
    stay_id = lab["facts"]["claimed_stay_ids"][0]
    records = sorted((r for r in lab["facts"]["records"] if r["stay_id"] == stay_id), key=lambda r: r["record_id"])
    assert len(records) == 2
    shown = screens.search_stay(at(lab, arm), member_number=lab["claimant_member_number"], confirmation=stay_id)
    assert shown is not None and shown.record_id == records[0]["record_id"]


def test_d07_the_ledger_screen_lists_a_repost_without_its_stay(arm: ArmA) -> None:
    lab = label(arm, "D07")
    view = screens.ledger_view(
        at(lab, arm),
        member_number=lab["claimant_member_number"],
        as_of_utc=lab["facts"]["received_at_utc"],
        show_older=True,
    )
    reposts = [e for e in view.entries if e.kind == "repost"]
    reversals = [e for e in view.entries if e.kind == "reversal" and e.stay_id == lab["facts"]["claimed_stay_ids"][0]]
    assert reposts and all(e.stay_id is None for e in reposts)
    assert reversals, "the reversal still shows against the stay"


def test_ledger_window_defaults_to_90_days_and_older_entries_are_one_click_away(arm: ArmA) -> None:
    lab = label(arm, "K02")
    member, as_of = lab["claimant_member_number"], lab["facts"]["received_at_utc"]
    recent = screens.ledger_view(at(lab, arm), member_number=member, as_of_utc=as_of)
    everything = screens.ledger_view(at(lab, arm), member_number=member, as_of_utc=as_of, show_older=True)
    assert recent.window_start_utc is not None and everything.window_start_utc is None
    assert set(recent.entries) <= set(everything.entries)
    assert all(e.posted_at_utc >= recent.window_start_utc for e in recent.entries)
    assert [e.posted_at_utc for e in everything.entries] == sorted(
        (e.posted_at_utc for e in everything.entries), reverse=True
    )


class Spy:
    def __init__(self, inner: CustomerSystems) -> None:
        self.inner, self.calls = inner, []

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        return getattr(self.inner, name)

    def get_pending_postings(self, stay_id: str) -> list[PendingPosting]:
        self.calls.append("get_pending_postings")
        return self.inner.get_pending_postings(stay_id)

    def get_ledger(self, member_number: str) -> list[LedgerEntry]:
        self.calls.append("get_ledger")
        return self.inner.get_ledger(member_number)


def test_d06_no_legacy_screen_reads_the_posting_queue(arm: ArmA) -> None:
    lab = label(arm, "D06")
    spy = Spy(at(lab, arm))
    member, stay_id = lab["claimant_member_number"], lab["facts"]["claimed_stay_ids"][0]
    screens.search_member(spy, member_number=member)
    screens.search_stay(spy, member_number=member, confirmation=stay_id)
    screens.ledger_view(spy, member_number=member, as_of_utc=lab["facts"]["received_at_utc"], show_older=True)
    assert "get_pending_postings" not in spy.calls and "get_ledger" in spy.calls
    assert at(lab, arm).get_pending_postings(stay_id), "the posting is pending upstream; legacy just can't see it"
