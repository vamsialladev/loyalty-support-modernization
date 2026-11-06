"""Arm per case, the name filter on the mock API, and arm B's routing (ADR-0062, ADR-0063; D13, D18, D20)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.arms.conventional import signals
from app.arms.legacy import intake as legacy_intake
from app.services import cases as svc
from benchmarks.intake import load_case, read_split
from tests.arm_a import ArmA, make_arm_a
from tests.conftest import ROOT


@pytest.fixture
def arm(mock_template: dict[str, Any], tmp_path: Path) -> ArmA:
    return make_arm_a(mock_template, tmp_path)


def _request(text: str = "My points are missing.") -> svc.IntakeRequest:
    return svc.IntakeRequest(received_at_utc="2026-07-20T14:00:00Z", contact_channel="email", text=text)


def test_the_arm_is_chosen_at_intake_and_shows_in_the_reference(arm: ArmA) -> None:
    who = arm.who("agent.ana")
    with arm.sessions() as s:
        a, b = svc.create_case(s, who, _request()), svc.create_case(s, who, _request(), arm=svc.ARM_B)
        assert (a.arm, b.arm) == ("A", "B")
        assert a.reference.startswith("A-") and b.reference.startswith("B-")
        assert [c.id for c in svc.list_cases(s, who, arm="B")] == [b.id]
        with pytest.raises(svc.WorkflowError, match="unknown arm"):
            svc.create_case(s, who, _request(), arm="Z")


def test_one_request_loads_once_per_arm(arm: ArmA) -> None:
    item = next(c for c in read_split("dev", arm.datasets) if c.case_id == "DV-001")
    with arm.sessions() as s:
        assert len(load_case(s, item)) == 1
        assert load_case(s, item) == []
        assert [c.arm for c in load_case(s, item, arm="B")] == ["B"]
        assert load_case(s, item, arm="B") == []


def test_family_name_filter_ignores_case_and_accents(arm: ArmA) -> None:
    item = next(iter(arm.labels.values()))
    member = arm.systems().get_member(item["facts"]["claimant"])
    systems = arm.systems()
    for spelled in (member.last_name, member.last_name.upper(), member.last_name.lower()):
        assert member.member_number in [m.member_number for m in systems.find_members(family_name=spelled)]
    assert systems.find_members(family_name="Nosuchname") == []


def test_family_name_filter_folds_accents() -> None:
    from mock_customer_api.service import _fold

    assert _fold("Muñoz") == _fold("MUNOZ") == "munoz"


def test_a_search_with_no_filter_is_still_refused(arm: ArmA) -> None:
    from app.ports.customer_systems import RequestRejected

    with pytest.raises(RequestRejected):
        arm.systems().find_members()


def test_the_app_image_carries_arm_bs_config() -> None:
    assert "COPY config/conventional ./config/conventional" in (ROOT / "Dockerfile.app").read_text(encoding="utf-8")


def test_arm_a_never_uses_the_name_filter() -> None:
    """D13 and D18 stay in arm A: its screens have no name search (ADR-0062)."""
    for path in (ROOT / "app/arms/legacy").rglob("*.py"):
        assert "family_name" not in path.read_text(encoding="utf-8"), path.name


def test_arm_a_routing_is_unchanged_by_arm_b_routing() -> None:
    claim_and_refund = "My points are missing for my stay. I also want a refund for the spa."
    assert legacy_intake.route(claim_and_refund) == legacy_intake.BILLING_QUEUE  # D20 stays in arm A
    assert signals.route(claim_and_refund) == signals.POINTS_QUEUE
    assert signals.route("I would like a refund for the parking charge.") == signals.BILLING_QUEUE
